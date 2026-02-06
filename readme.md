# IoT Zone Tracker

Stateful IoT tracking: devices move through zones via MQTT events, with visits tracked as open/close rows in Postgres. The system is multi-service: Mosquitto -> ingestor (Python) -> Postgres -> backend (FastAPI) -> frontend (React/Chart.js).

## Architecture & data flow
- MQTT events on shared topic `$share/workers/site/+/device/+/location`.
- Ingestor normalizes payloads (camel or snake keys) and writes to Postgres.
- `zone_history` stores visits; exactly one open row per device+site.
- `anchors` stores current anchor position and `anchor_history` is append-only history.
- Backend serves metrics and admin APIs; frontend calls `/api/*` via Vite proxy.

## Running
- Dev (default): `docker compose up -d`
  - UI: `http://localhost:3000`
  - API docs: `http://localhost:8000/docs`
- Prod-like UI: `docker compose -f docker-compose.yml --profile prod up -d --build`
  - UI served by nginx at `http://localhost:3000`

## Database schema
- Authoritative schema: [db/init.sql](db/init.sql) (includes `site_id`, partitions, anchors, indexes).
- `zone_history` is partitioned by `site_id` and has a unique partial index to prevent two open visits per device.
- `anchors` is the current snapshot; `anchor_history` is the time series.

If you already have a running DB volume, re-apply the schema once:
```bash
docker compose exec -T postgres psql -U iotuser -d iot_tracker -f /docker-entrypoint-initdb.d/init.sql
```

## MQTT payloads
Accepted fields (any mix of camel/snake):
- `deviceId` or `device_id`
- `zoneId` or `zone_id`
- `siteId` or `site_id` (optional; falls back to topic or `DEFAULT_SITE_ID`)

Topic format for site+device: `site/{siteId}/device/{deviceId}/location`.

## Backend endpoints
- `GET /healthz`
- `GET /zones`, `POST /zones`, `POST /zones/bulk`
- `GET /metrics/most-visited`, `GET /metrics/transitions`
- `GET /device/{device_id}/history`
- `GET /anchors`, `POST /anchors`, `GET /anchors/{anchor_id}/history`

## Frontend
- Vite dev server proxies `/api/*` to backend container `http://backend:8000`.
- `frontend/src/App.jsx` includes Zone Admin and Anchor Admin panels.

## Operational notes
- Stale handling: open visits are treated as inactive if `devices.last_seen` is older than `STALE_THRESHOLD_MINUTES`.
- Mosquitto allows anonymous dev connections and exposes MQTT (1883) + WebSocket (9001).