import os
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import psycopg2
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field
from psycopg2.extras import RealDictCursor


DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "iot_tracker")
DB_USER = os.getenv("DB_USER", "iotuser")
DB_PASSWORD = os.getenv("DB_PASSWORD", "iotpass")

STALE_THRESHOLD_MINUTES = int(os.getenv("STALE_THRESHOLD_MINUTES", "30"))
DEFAULT_SITE_ID = os.getenv("DEFAULT_SITE_ID", "site-001")

app = FastAPI(title="IoT Zone Tracker API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"] ,
    allow_headers=["*"],
)


@contextmanager
def get_conn():
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        cursor_factory=RealDictCursor,
    )
    try:
        yield conn
    finally:
        conn.close()


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


@app.on_event("startup")
def ensure_schema():
    # Lightweight migration for existing databases.
    with get_conn() as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("ALTER TABLE IF EXISTS zones ADD COLUMN IF NOT EXISTS x DOUBLE PRECISION;")
            cur.execute("ALTER TABLE IF EXISTS zones ADD COLUMN IF NOT EXISTS y DOUBLE PRECISION;")
            cur.execute("ALTER TABLE IF EXISTS zones ADD COLUMN IF NOT EXISTS z DOUBLE PRECISION;")
            cur.execute("ALTER TABLE IF EXISTS zones ADD COLUMN IF NOT EXISTS audio_id BIGINT;")

            # Create audio_files table if it doesn't exist
            cur.execute("""
                CREATE TABLE IF NOT EXISTS audio_files (
                    id BIGSERIAL PRIMARY KEY,
                    site_id VARCHAR(50) NOT NULL,
                    filename VARCHAR(255) NOT NULL,
                    file_size BIGINT NOT NULL,
                    mime_type VARCHAR(100) NOT NULL,
                    file_data BYTEA NOT NULL,
                    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    uploaded_by VARCHAR(100),
                    description TEXT
                );
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_audio_files_site_id ON audio_files(site_id);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_audio_files_uploaded_at ON audio_files(site_id, uploaded_at DESC);")


class ZoneUpsert(BaseModel):
    siteId: str = Field(default=DEFAULT_SITE_ID, min_length=1)
    zoneId: str = Field(min_length=1)
    zoneName: str = Field(min_length=1)
    x: float | None = None
    y: float | None = None
    z: float | None = None
    audioId: int | None = None


class AnchorUpsert(BaseModel):
    siteId: str = Field(default=DEFAULT_SITE_ID, min_length=1)
    anchorId: str = Field(min_length=1)
    anchorName: str = Field(min_length=1)
    x: float | None = None
    y: float | None = None
    z: float | None = None
    source: str | None = None


def require_any_coord(x: float | None, y: float | None, z: float | None):
    if x is None and y is None and z is None:
        raise HTTPException(status_code=400, detail="at least one of x,y,z is required")


@app.get("/healthz")
def healthz():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 AS ok;")
            row = cur.fetchone()
    return {"ok": bool(row and row.get("ok") == 1)}


@app.get("/zones")
def list_zones(siteId: str | None = None):
    site_id = siteId or DEFAULT_SITE_ID
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT site_id, zone_id, zone_name, x, y, z, audio_id
                FROM zones
                WHERE site_id = %s
                ORDER BY zone_id ASC;
                """,
                (site_id,),
            )
            rows = cur.fetchall() or []

    return {
        "siteId": site_id,
        "items": [
            {
                "siteId": r["site_id"],
                "zoneId": r["zone_id"],
                "zoneName": r["zone_name"],
                "x": r.get("x"),
                "y": r.get("y"),
                "z": r.get("z"),
                "audioId": r.get("audio_id"),
            }
            for r in rows
        ],
    }


@app.post("/zones")
def upsert_zone(zone: ZoneUpsert):
    with get_conn() as conn:
        conn.autocommit = False
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO zones (site_id, zone_id, zone_name, x, y, z, audio_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (site_id, zone_id)
                    DO UPDATE SET
                        zone_name = EXCLUDED.zone_name,
                        x = EXCLUDED.x,
                        y = EXCLUDED.y,
                        z = EXCLUDED.z,
                        audio_id = EXCLUDED.audio_id;
                    """,
                    (zone.siteId, zone.zoneId, zone.zoneName, zone.x, zone.y, zone.z, zone.audioId),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    return {"ok": True}


@app.get("/anchors")
def list_anchors(siteId: str | None = None):
    site_id = siteId or DEFAULT_SITE_ID
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT site_id, anchor_id, anchor_name, x, y, z, updated_at
                FROM anchors
                WHERE site_id = %s
                ORDER BY anchor_id ASC;
                """,
                (site_id,),
            )
            rows = cur.fetchall() or []

    return {
        "siteId": site_id,
        "items": [
            {
                "siteId": r["site_id"],
                "anchorId": r["anchor_id"],
                "anchorName": r["anchor_name"],
                "x": r.get("x"),
                "y": r.get("y"),
                "z": r.get("z"),
                "updatedAt": r["updated_at"].isoformat() if r.get("updated_at") else None,
            }
            for r in rows
        ],
    }


@app.post("/anchors")
def upsert_anchor(anchor: AnchorUpsert):
    require_any_coord(anchor.x, anchor.y, anchor.z)
    with get_conn() as conn:
        conn.autocommit = False
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO anchors (site_id, anchor_id, anchor_name, x, y, z, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (site_id, anchor_id)
                    DO UPDATE SET
                        anchor_name = EXCLUDED.anchor_name,
                        x = EXCLUDED.x,
                        y = EXCLUDED.y,
                        z = EXCLUDED.z,
                        updated_at = NOW();
                    """,
                    (
                        anchor.siteId,
                        anchor.anchorId,
                        anchor.anchorName,
                        anchor.x,
                        anchor.y,
                        anchor.z,
                    ),
                )
                cur.execute(
                    """
                    INSERT INTO anchor_history (site_id, anchor_id, x, y, z, source, observed_at)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW());
                    """,
                    (
                        anchor.siteId,
                        anchor.anchorId,
                        anchor.x,
                        anchor.y,
                        anchor.z,
                        anchor.source,
                    ),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    return {"ok": True}


@app.get("/anchors/{anchor_id}/history")
def anchor_history(anchor_id: str, limit: int = 200, siteId: str | None = None):
    if limit <= 0 or limit > 2000:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 2000")

    site_id = siteId or DEFAULT_SITE_ID
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT anchor_name
                FROM anchors
                WHERE site_id = %s AND anchor_id = %s;
                """,
                (site_id, anchor_id),
            )
            anchor = cur.fetchone()
            if not anchor:
                raise HTTPException(status_code=404, detail="anchor not found")

            cur.execute(
                """
                SELECT id, x, y, z, source, observed_at
                FROM anchor_history
                WHERE site_id = %s AND anchor_id = %s
                ORDER BY observed_at DESC
                LIMIT %s;
                """,
                (site_id, anchor_id, limit),
            )
            rows = cur.fetchall() or []

    return {
        "siteId": site_id,
        "anchorId": anchor_id,
        "anchorName": anchor["anchor_name"],
        "items": [
            {
                "id": r["id"],
                "x": r.get("x"),
                "y": r.get("y"),
                "z": r.get("z"),
                "source": r.get("source"),
                "observedAt": r["observed_at"].isoformat() if r.get("observed_at") else None,
            }
            for r in rows
        ],
    }


@app.post("/zones/bulk")
def bulk_upsert_zones(zones: list[ZoneUpsert]):
    if len(zones) == 0:
        return {"ok": True, "count": 0}
    if len(zones) > 5000:
        raise HTTPException(status_code=400, detail="too many zones in one request")

    with get_conn() as conn:
        conn.autocommit = False
        try:
            with conn.cursor() as cur:
                for zone in zones:
                    cur.execute(
                        """
                        INSERT INTO zones (site_id, zone_id, zone_name, x, y, z, audio_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (site_id, zone_id)
                        DO UPDATE SET
                            zone_name = EXCLUDED.zone_name,
                            x = EXCLUDED.x,
                            y = EXCLUDED.y,
                            z = EXCLUDED.z,
                            audio_id = EXCLUDED.audio_id;
                        """,
                        (zone.siteId, zone.zoneId, zone.zoneName, zone.x, zone.y, zone.z, zone.audioId),
                    )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    return {"ok": True, "count": len(zones)}


@app.get("/metrics/most-visited")
def most_visited(hours: int = 24, siteId: str | None = None):
    if hours <= 0 or hours > 24 * 30:
        raise HTTPException(status_code=400, detail="hours must be between 1 and 720")

    site_id = siteId or DEFAULT_SITE_ID

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT zh.zone_id,
                       z.zone_name,
                       COALESCE(SUM(EXTRACT(EPOCH FROM zh.duration)), 0)::bigint AS total_seconds
                FROM zone_history zh
                                JOIN zones z ON z.site_id = zh.site_id AND z.zone_id = zh.zone_id
                                WHERE zh.site_id = %s
                                    AND zh.start_time > NOW() - (%s || ' hours')::interval
                  AND zh.end_time IS NOT NULL
                GROUP BY zh.zone_id, z.zone_name
                ORDER BY total_seconds DESC;
                """,
                                (site_id, str(hours)),
            )
            rows = cur.fetchall() or []

    return {
        "siteId": site_id,
        "windowHours": hours,
        "items": [
            {
                "zoneId": r["zone_id"],
                "zoneName": r["zone_name"],
                "totalSeconds": int(r["total_seconds"]),
            }
            for r in rows
        ],
    }


@app.get("/metrics/transitions")
def transitions(limit: int = 50, siteId: str | None = None):
    if limit <= 0 or limit > 500:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 500")

    site_id = siteId or DEFAULT_SITE_ID

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                WITH ordered AS (
                  SELECT device_id,
                         zone_id AS current_zone,
                         LEAD(zone_id) OVER (PARTITION BY device_id ORDER BY start_time) AS next_zone
                  FROM zone_history
                                    WHERE site_id = %s
                )
                SELECT current_zone,
                       next_zone,
                       COUNT(*)::bigint AS frequency
                FROM ordered
                WHERE next_zone IS NOT NULL
                GROUP BY current_zone, next_zone
                ORDER BY frequency DESC
                LIMIT %s;
                """,
                                (site_id, limit),
            )
            rows = cur.fetchall() or []

    return {
                "siteId": site_id,
        "items": [
            {
                "currentZone": r["current_zone"],
                "nextZone": r["next_zone"],
                "frequency": int(r["frequency"]),
            }
            for r in rows
        ]
    }


@app.get("/device/{device_id}/history")
def device_history(device_id: str, limit: int = 200, siteId: str | None = None):
    if limit <= 0 or limit > 2000:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 2000")

    site_id = siteId or DEFAULT_SITE_ID

    stale_cutoff = now_utc() - timedelta(minutes=STALE_THRESHOLD_MINUTES)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT device_id, device_name, last_seen
                FROM devices
                WHERE site_id = %s AND device_id = %s;
                """,
                (site_id, device_id),
            )
            device = cur.fetchone()
            if not device:
                raise HTTPException(status_code=404, detail="device not found")

            cur.execute(
                """
                SELECT zh.id,
                       zh.zone_id,
                       z.zone_name,
                       zh.start_time,
                       zh.end_time
                FROM zone_history zh
                JOIN zones z ON z.site_id = zh.site_id AND z.zone_id = zh.zone_id
                WHERE zh.site_id = %s AND zh.device_id = %s
                ORDER BY zh.start_time DESC
                LIMIT %s;
                """,
                (site_id, device_id, limit),
            )
            visits = cur.fetchall() or []

    last_seen = device.get("last_seen")
    if last_seen is not None and last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)

    items = []
    for v in visits:
        start_time = v["start_time"]
        end_time = v["end_time"]
        if start_time is not None and start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)
        if end_time is not None and end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=timezone.utc)

        is_open = end_time is None
        is_active = False
        effective_end = end_time

        if is_open and last_seen is not None:
            is_active = last_seen >= stale_cutoff
            if not is_active:
                effective_end = last_seen

        duration_seconds = None
        if effective_end is not None and start_time is not None:
            duration_seconds = int(max(0, (effective_end - start_time).total_seconds()))

        items.append(
            {
                "id": v["id"],
                "zoneId": v["zone_id"],
                "zoneName": v["zone_name"],
                "startTime": start_time.isoformat() if start_time else None,
                "endTime": end_time.isoformat() if end_time else None,
                "effectiveEndTime": effective_end.isoformat() if effective_end else None,
                "durationSeconds": duration_seconds,
                "isOpen": is_open,
                "isActive": is_active,
            }
        )

    return {
        "device": {
            "siteId": site_id,
            "deviceId": device["device_id"],
            "deviceName": device["device_name"],
            "lastSeen": last_seen.isoformat() if last_seen else None,
            "staleThresholdMinutes": STALE_THRESHOLD_MINUTES,
        },
        "items": items,
    }


class QueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=10000)


@app.post("/query")
def execute_query(request: QueryRequest):
    """Execute a SQL query and return results. Only SELECT queries are allowed."""
    query = request.query.strip()

    # Basic security check - only allow SELECT queries
    query_upper = query.upper()
    if not query_upper.startswith("SELECT"):
        raise HTTPException(
            status_code=400,
            detail="Only SELECT queries are allowed for security reasons"
        )

    # Block potentially dangerous keywords
    dangerous_keywords = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "CREATE", "TRUNCATE"]
    for keyword in dangerous_keywords:
        if keyword in query_upper:
            raise HTTPException(
                status_code=400,
                detail=f"Query contains forbidden keyword: {keyword}"
            )

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                rows = cur.fetchall() or []

                # Get column names from cursor description
                columns = [desc[0] for desc in cur.description] if cur.description else []

                # Convert rows to list of dicts
                results = []
                for row in rows:
                    result_row = {}
                    for col_name, value in row.items():
                        # Convert datetime objects to ISO format strings
                        if isinstance(value, datetime):
                            result_row[col_name] = value.isoformat()
                        else:
                            result_row[col_name] = value
                    results.append(result_row)

                return {
                    "columns": columns,
                    "rows": results,
                    "rowCount": len(results)
                }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Query execution failed: {str(e)}")


@app.post("/audio/upload")
async def upload_audio(
    file: UploadFile = File(...),
    siteId: str = Form(default=DEFAULT_SITE_ID),
    description: str = Form(default=""),
    uploadedBy: str = Form(default="")
):
    """Upload an audio file (.mp3, .wav) to the database."""
    # Validate file type
    allowed_types = ["audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav"]
    allowed_extensions = [".mp3", ".wav"]

    file_ext = os.path.splitext(file.filename)[1].lower()

    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Only audio files are allowed (.mp3, .wav). Got: {file_ext}"
        )

    # Read file content
    file_content = await file.read()
    file_size = len(file_content)

    # Limit file size to 50MB
    max_size = 50 * 1024 * 1024  # 50MB
    if file_size > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"File size ({file_size} bytes) exceeds maximum allowed size (50MB)"
        )

    # Determine mime type
    mime_type = file.content_type or "audio/mpeg"

    try:
        with get_conn() as conn:
            conn.autocommit = False
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO audio_files (site_id, filename, file_size, mime_type, file_data, uploaded_by, description)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        RETURNING id, uploaded_at;
                        """,
                        (siteId, file.filename, file_size, mime_type, file_content, uploadedBy, description)
                    )
                    result = cur.fetchone()
                conn.commit()

                return {
                    "ok": True,
                    "id": result["id"],
                    "filename": file.filename,
                    "fileSize": file_size,
                    "uploadedAt": result["uploaded_at"].isoformat() if result["uploaded_at"] else None
                }
            except Exception:
                conn.rollback()
                raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")


@app.get("/audio/list")
def list_audio_files(siteId: str | None = None, limit: int = 100):
    """List all uploaded audio files."""
    site_id = siteId or DEFAULT_SITE_ID

    if limit <= 0 or limit > 500:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 500")

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, site_id, filename, file_size, mime_type, uploaded_at, uploaded_by, description
                FROM audio_files
                WHERE site_id = %s
                ORDER BY uploaded_at DESC
                LIMIT %s;
                """,
                (site_id, limit)
            )
            rows = cur.fetchall() or []

    return {
        "siteId": site_id,
        "items": [
            {
                "id": r["id"],
                "siteId": r["site_id"],
                "filename": r["filename"],
                "fileSize": r["file_size"],
                "mimeType": r["mime_type"],
                "uploadedAt": r["uploaded_at"].isoformat() if r.get("uploaded_at") else None,
                "uploadedBy": r.get("uploaded_by"),
                "description": r.get("description")
            }
            for r in rows
        ]
    }


@app.get("/audio/{audio_id}")
def get_audio_file(audio_id: int, siteId: str | None = None):
    """Download an audio file by ID."""
    site_id = siteId or DEFAULT_SITE_ID

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT filename, file_data, mime_type
                FROM audio_files
                WHERE id = %s AND site_id = %s;
                """,
                (audio_id, site_id)
            )
            result = cur.fetchone()

            if not result:
                raise HTTPException(status_code=404, detail="Audio file not found")

            return Response(
                content=bytes(result["file_data"]),
                media_type=result["mime_type"],
                headers={
                    "Content-Disposition": f'attachment; filename="{result["filename"]}"'
                }
            )


@app.delete("/audio/{audio_id}")
def delete_audio_file(audio_id: int, siteId: str | None = None):
    """Delete an audio file by ID and clean up references in zones table."""
    site_id = siteId or DEFAULT_SITE_ID

    with get_conn() as conn:
        conn.autocommit = False
        try:
            with conn.cursor() as cur:
                # First, set audio_id to NULL in zones table where it matches
                cur.execute(
                    """
                    UPDATE zones
                    SET audio_id = NULL
                    WHERE site_id = %s AND audio_id = %s;
                    """,
                    (site_id, audio_id)
                )

                # Then delete the audio file
                cur.execute(
                    """
                    DELETE FROM audio_files
                    WHERE id = %s AND site_id = %s
                    RETURNING id;
                    """,
                    (audio_id, site_id)
                )
                result = cur.fetchone()

                if not result:
                    raise HTTPException(status_code=404, detail="Audio file not found")

            conn.commit()
            return {"ok": True, "id": audio_id}
        except Exception:
            conn.rollback()
            raise


@app.post("/audio/cleanup-orphaned")
def cleanup_orphaned_audio_references(siteId: str | None = None):
    """Clean up zone audio_id references where the audio file no longer exists."""
    site_id = siteId or DEFAULT_SITE_ID

    with get_conn() as conn:
        conn.autocommit = False
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE zones
                    SET audio_id = NULL
                    WHERE site_id = %s
                      AND audio_id IS NOT NULL
                      AND NOT EXISTS (
                          SELECT 1 FROM audio_files
                          WHERE audio_files.id = zones.audio_id
                            AND audio_files.site_id = zones.site_id
                      )
                    RETURNING zone_id;
                    """,
                    (site_id,)
                )
                cleaned_zones = cur.fetchall()
            conn.commit()

            return {
                "ok": True,
                "cleanedCount": len(cleaned_zones),
                "cleanedZones": [row["zone_id"] for row in cleaned_zones]
            }
        except Exception:
            conn.rollback()
            raise
