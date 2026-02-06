# Copilot instructions

## Big picture
- System is multi-service: MQTT (Mosquitto) -> ingestor (Python) -> Postgres -> backend (FastAPI) -> frontend (React/Chart.js).
- Device/zone events are stateful: zone_history tracks open visit (end_time NULL) per device+site; transitions close then open within a transaction.
- Multi-tenant by site: tables keyed by site_id; zone_history is partitioned by site_id with a default partition.

## Key workflows
- Dev (default): `docker compose up -d` runs backend reload + Vite dev server on 5173 (mapped to 3000).
- Prod-like UI: `docker compose -f docker-compose.yml --profile prod up -d --build` serves nginx on :3000.
- API docs at `http://localhost:8000/docs` when backend is running.

## Service boundaries and data flow
- MQTT ingestor subscribes to shared topic `$share/workers/site/+/device/+/location` and accepts payload fields `deviceId/zoneId` (camel) or `device_id/zone_id` (snake), with site from payload or topic.
- Ingestor enforces single open visit using unique partial index `uq_open_visit_per_device` and row locks; see [ingestor/main.py](../ingestor/main.py).
- Backend reads `zone_history`, joins `zones`, and applies stale handling (open visit marked inactive if `devices.last_seen` older than `STALE_THRESHOLD_MINUTES`).

## Frontend integration
- Vite dev proxy rewrites `/api/*` -> backend container on 8000; frontend always calls `/api/...` paths.
- Charts are driven by `/metrics/most-visited` and zone admin uses `/zones` + `/zones` POST.

## Conventions and patterns
- Postgres schema is defined in [db/init.sql](../db/init.sql); keep site_id in all FK joins and indexes.
- Anchors use a current snapshot table plus append-only history: anchors + anchor_history (position tracking).
- Startup schema tweaks live in backend `ensure_schema()` (adds zone x/y/z columns) for lightweight migrations.
- Compose env vars are the source of truth for DB/MQTT config; see [docker-compose.yml](../docker-compose.yml).

## Integration points
- Mosquitto config allows anonymous dev connections and exposes MQTT (1883) + WebSocket (9001).
- Backend CORS is wide-open for dev; adjust only if required by deployments.
