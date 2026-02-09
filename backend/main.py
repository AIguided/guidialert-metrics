import os
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import base64

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
            # Floorplan table migrations
            cur.execute("""
                CREATE TABLE IF NOT EXISTS floorplan (
                    site_id VARCHAR(50) NOT NULL,
                    floor_id VARCHAR(50) NOT NULL,
                    floor_name TEXT NOT NULL,
                    image_data BYTEA,
                    image_mime_type TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (site_id, floor_id)
                );
            """)
            cur.execute("ALTER TABLE IF EXISTS floorplan ADD COLUMN IF NOT EXISTS image_data BYTEA;")
            cur.execute("ALTER TABLE IF EXISTS floorplan ADD COLUMN IF NOT EXISTS image_mime_type TEXT;")
            cur.execute("ALTER TABLE IF EXISTS floorplan ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP;")
            cur.execute("ALTER TABLE IF EXISTS floorplan ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP;")


class ZoneUpsert(BaseModel):
    siteId: str = Field(default=DEFAULT_SITE_ID, min_length=1)
    zoneId: str = Field(min_length=1)
    zoneName: str = Field(min_length=1)
    x: float | None = None
    y: float | None = None
    z: float | None = None


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
                SELECT site_id, zone_id, zone_name, x, y, z
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
                    INSERT INTO zones (site_id, zone_id, zone_name, x, y, z)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (site_id, zone_id)
                    DO UPDATE SET
                        zone_name = EXCLUDED.zone_name,
                        x = EXCLUDED.x,
                        y = EXCLUDED.y,
                        z = EXCLUDED.z;
                    """,
                    (zone.siteId, zone.zoneId, zone.zoneName, zone.x, zone.y, zone.z),
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
                        INSERT INTO zones (site_id, zone_id, zone_name, x, y, z)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (site_id, zone_id)
                        DO UPDATE SET
                            zone_name = EXCLUDED.zone_name,
                            x = EXCLUDED.x,
                            y = EXCLUDED.y,
                            z = EXCLUDED.z;
                        """,
                        (zone.siteId, zone.zoneId, zone.zoneName, zone.x, zone.y, zone.z),
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


# ─────────────────────────────────────────────────────────────────────────────
# Floorplan endpoints
# ─────────────────────────────────────────────────────────────────────────────

ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB


@app.get("/floorplans")
def list_floorplans(siteId: str | None = None):
    site_id = siteId or DEFAULT_SITE_ID
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT site_id, floor_id, floor_name, image_mime_type,
                       created_at, updated_at,
                       (image_data IS NOT NULL) AS has_image
                FROM floorplan
                WHERE site_id = %s
                ORDER BY floor_id ASC;
                """,
                (site_id,),
            )
            rows = cur.fetchall() or []

    return {
        "siteId": site_id,
        "items": [
            {
                "siteId": r["site_id"],
                "floorId": r["floor_id"],
                "floorName": r["floor_name"],
                "imageMimeType": r.get("image_mime_type"),
                "hasImage": r.get("has_image", False),
                "createdAt": r["created_at"].isoformat() if r.get("created_at") else None,
                "updatedAt": r["updated_at"].isoformat() if r.get("updated_at") else None,
            }
            for r in rows
        ],
    }


@app.post("/floorplans")
async def upsert_floorplan(
    floorId: str = Form(...),
    floorName: str = Form(...),
    siteId: str = Form(default=None),
    image: UploadFile | None = File(default=None),
):
    site_id = siteId or DEFAULT_SITE_ID
    floor_id = floorId.strip()
    floor_name = floorName.strip()

    if not floor_id or not floor_name:
        raise HTTPException(status_code=400, detail="floorId and floorName are required")

    image_data = None
    image_mime_type = None

    if image and image.filename:
        content_type = image.content_type or "application/octet-stream"
        if content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid image type: {content_type}. Allowed: {', '.join(ALLOWED_IMAGE_TYPES)}",
            )
        image_data = await image.read()
        if len(image_data) > MAX_IMAGE_SIZE:
            raise HTTPException(status_code=400, detail=f"Image too large. Max size: {MAX_IMAGE_SIZE // (1024*1024)} MB")
        image_mime_type = content_type

    with get_conn() as conn:
        conn.autocommit = False
        try:
            with conn.cursor() as cur:
                if image_data is not None:
                    # Upsert with new image
                    cur.execute(
                        """
                        INSERT INTO floorplan (site_id, floor_id, floor_name, image_data, image_mime_type, updated_at)
                        VALUES (%s, %s, %s, %s, %s, NOW())
                        ON CONFLICT (site_id, floor_id)
                        DO UPDATE SET
                            floor_name = EXCLUDED.floor_name,
                            image_data = EXCLUDED.image_data,
                            image_mime_type = EXCLUDED.image_mime_type,
                            updated_at = NOW();
                        """,
                        (site_id, floor_id, floor_name, psycopg2.Binary(image_data), image_mime_type),
                    )
                else:
                    # Upsert without changing image
                    cur.execute(
                        """
                        INSERT INTO floorplan (site_id, floor_id, floor_name, updated_at)
                        VALUES (%s, %s, %s, NOW())
                        ON CONFLICT (site_id, floor_id)
                        DO UPDATE SET
                            floor_name = EXCLUDED.floor_name,
                            updated_at = NOW();
                        """,
                        (site_id, floor_id, floor_name),
                    )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    return {"ok": True}


@app.get("/floorplans/{floor_id}/image")
def get_floorplan_image(floor_id: str, siteId: str | None = None):
    site_id = siteId or DEFAULT_SITE_ID
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT image_data, image_mime_type
                FROM floorplan
                WHERE site_id = %s AND floor_id = %s;
                """,
                (site_id, floor_id),
            )
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Floorplan not found")

    if not row.get("image_data"):
        raise HTTPException(status_code=404, detail="No image uploaded for this floorplan")

    return Response(
        content=bytes(row["image_data"]),
        media_type=row.get("image_mime_type") or "application/octet-stream",
    )


@app.delete("/floorplans/{floor_id}")
def delete_floorplan(floor_id: str, siteId: str | None = None):
    site_id = siteId or DEFAULT_SITE_ID
    with get_conn() as conn:
        conn.autocommit = False
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM floorplan
                    WHERE site_id = %s AND floor_id = %s;
                    """,
                    (site_id, floor_id),
                )
                deleted = cur.rowcount
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    if deleted == 0:
        raise HTTPException(status_code=404, detail="Floorplan not found")

    return {"ok": True}
