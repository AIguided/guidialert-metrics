This `README.md` is designed to be ingested by an AI coding agent (like Cursor, Windsurf, or a GPT-based dev tool) to scaffold and build the entire system autonomously. It provides strict logic rules, schema definitions, and architectural boundaries.

---

# IoT Zone Tracker: State-Based Stay Duration System

## Project Overview

This project is an IoT-based tracking system that monitors `deviceId` movements across various `zoneId` locations using MQTT. Unlike simple logging, this system implements a **State Machine** in the database to track "Visits" (Arrival/Departure/Duration) rather than just points in time.

## 1. System Architecture

* **Broker:** MQTT (e.g., Mosquitto) - Source of truth for device events.
* **Ingestor:** Python/Node.js service - Subscribes to MQTT, handles logic, and writes to DB.
* **Database:** PostgreSQL - Stores relational data and historical visits.
* **Backend:** FastAPI (Python) - Serves metrics via JSON API.
* **Frontend:** React with Chart.js (or Grafana) - Displays stay-duration heatmaps and analytics.

## 2. Database Schema (PostgreSQL)

The database must follow this structure to ensure data integrity and query performance.

```sql
-- Core Table for Master Data
CREATE TABLE IF NOT EXISTS zones (
    zone_id VARCHAR(50) PRIMARY KEY,
    zone_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS devices (
    device_id VARCHAR(50) PRIMARY KEY,
    device_name TEXT NOT NULL,
    last_seen TIMESTAMPTZ
);

-- The State-Tracking Table
CREATE TABLE IF NOT EXISTS zone_history (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR(50) REFERENCES devices(device_id),
    zone_id VARCHAR(50) REFERENCES zones(zone_id),
    start_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    end_time TIMESTAMPTZ, -- NULL means the device is currently in this zone
    duration INTERVAL GENERATED ALWAYS AS (end_time - start_time) STORED
);

-- Indexing for performance
CREATE INDEX idx_device_end_time ON zone_history(device_id) WHERE (end_time IS NULL);
CREATE INDEX idx_start_time ON zone_history(start_time);

```

## 3. Ingestion Logic (The "Brain")

The AI Agent must implement the following logic in the MQTT Subscriber to prevent redundant data and handle state transitions:

### Event: Message Received on topic `telemetry/location`

**Payload:** `{"deviceId": "string", "zoneId": "string"}`

1. **Check Open Visit:** Query the database for a record where `device_id = payload.deviceId` AND `end_time IS NULL`.
2. **Compare States:**
* **Case A (No Open Visit):** Insert a new record with `start_time = now()`.
* **Case B (Same Zone):** If `payload.zoneId == open_record.zone_id`, update `devices.last_seen` but **do not** touch `zone_history`.
* **Case C (Zone Change):** 1. Update `open_record.end_time = now()`.
2. Insert a new record for the new `zoneId` with `start_time = now()`.


3. **Transaction Integrity:** Ensure the "Close" and "Open" actions occur within a single SQL transaction.

## 4. Analytical Queries (Metrics)

The following SQL queries must be exposed via the API:

### Total Time Spent per Zone (Last 24h)

```sql
SELECT zone_id, SUM(duration) as total_duration
FROM zone_history
WHERE start_time > NOW() - INTERVAL '24 hours'
AND end_time IS NOT NULL
GROUP BY zone_id
ORDER BY total_duration DESC;

```

### Most Frequent Zone Transitions

```sql
SELECT zone_id as current_zone, 
       LEAD(zone_id) OVER (PARTITION BY device_id ORDER BY start_time) as next_zone,
       COUNT(*) as frequency
FROM zone_history
GROUP BY current_zone, next_zone;

```

## 5. Implementation Roadmap for AI Agent

1. **Setup Environment:** Initialize a Docker Compose file with `postgres` and `mosquitto`.
2. **Database Migration:** Execute the SQL schema provided above.
3. **Develop Ingestor:** Use `paho-mqtt` (Python) to listen to topics and implement the "Check Open Visit" logic.
4. **Develop API:** Use `FastAPI` to create endpoints:
* `GET /metrics/most-visited`: Returns zone rankings.
* `GET /device/{id}/history`: Returns the timeline for a specific device.


5. **Develop Dashboard:** Create a simple React dashboard that fetches these endpoints and displays a **Horizontal Bar Chart** for "Total Time in Zone."

## 6. Error Handling Requirements

* **Stale States:** If a device hasn't been seen for > 30 minutes, the API should treat the "Open Visit" as "Inactive" even if `end_time` is NULL.
* **MQTT Reconnect:** The ingestor must handle broker disconnections without losing the local state.

---

**Next Step:** Would you like me to generate the **Docker Compose** file and the **Python Ingestor** code based on this README to get you started immediately?