import json
import os
import re
import signal
import sys
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import RealDictCursor
import paho.mqtt.client as mqtt


MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "$share/workers/site/+/device/+/location")

DEFAULT_SITE_ID = os.getenv("DEFAULT_SITE_ID", "site-001")

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "iot_tracker")
DB_USER = os.getenv("DB_USER", "iotuser")
DB_PASSWORD = os.getenv("DB_PASSWORD", "iotpass")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def get_conn():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        cursor_factory=RealDictCursor,
    )


def ensure_master_data(cur, device_id: str, zone_id: str):
    cur.execute(
        """
        INSERT INTO devices (site_id, device_id, device_name, last_seen)
        VALUES (%s, %s, %s, NOW())
        ON CONFLICT (site_id, device_id) DO UPDATE SET last_seen = EXCLUDED.last_seen;
        """,
        (DEFAULT_SITE_ID, device_id, device_id),
    )
    cur.execute(
        """
        INSERT INTO zones (site_id, zone_id, zone_name)
        VALUES (%s, %s, %s)
        ON CONFLICT (site_id, zone_id) DO NOTHING;
        """,
        (DEFAULT_SITE_ID, zone_id, zone_id),
    )


def parse_topic_site_device(topic: str) -> tuple[str | None, str | None]:
    # Expected publish topic: site/{siteId}/device/{deviceId}/location
    m = re.match(r"^site/([^/]+)/device/([^/]+)/location$", topic)
    if not m:
        return None, None
    return m.group(1), m.group(2)


def normalize_event(payload: dict, topic: str) -> tuple[str, str, str]:
    """Return (site_id, device_id, zone_id) accepting either payload or topic-derived fields."""

    payload_device = payload.get("deviceId") or payload.get("device_id")
    payload_zone = payload.get("zoneId") or payload.get("zone_id")
    payload_site = payload.get("siteId") or payload.get("site_id")

    topic_site, topic_device = parse_topic_site_device(topic)

    site_id = payload_site or topic_site or DEFAULT_SITE_ID
    device_id = payload_device or topic_device
    zone_id = payload_zone

    if not device_id or not zone_id:
        raise ValueError("Event must contain device and zone (deviceId/device_id and zoneId/zone_id)")

    return site_id, device_id, zone_id


def ensure_master_data_site(cur, site_id: str, device_id: str, zone_id: str):
    cur.execute(
        """
        INSERT INTO devices (site_id, device_id, device_name, last_seen)
        VALUES (%s, %s, %s, NOW())
        ON CONFLICT (site_id, device_id) DO UPDATE SET last_seen = EXCLUDED.last_seen;
        """,
        (site_id, device_id, device_id),
    )
    cur.execute(
        """
        INSERT INTO zones (site_id, zone_id, zone_name)
        VALUES (%s, %s, %s)
        ON CONFLICT (site_id, zone_id) DO NOTHING;
        """,
        (site_id, zone_id, zone_id),
    )


def process_event(payload: dict, topic: str):
    site_id, device_id, zone_id = normalize_event(payload, topic)

    conn = get_conn()
    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            ensure_master_data_site(cur, site_id, device_id, zone_id)

            cur.execute(
                """
                SELECT site_id, id, zone_id
                FROM zone_history
                WHERE site_id = %s AND device_id = %s AND end_time IS NULL
                ORDER BY start_time DESC
                LIMIT 1
                FOR UPDATE;
                """,
                (site_id, device_id),
            )
            open_visit = cur.fetchone()

            if open_visit is None:
                # No open visit row exists to lock; rely on unique partial index
                # uq_open_visit_per_device to prevent two workers creating two open visits.
                try:
                    cur.execute(
                        """
                        INSERT INTO zone_history (site_id, device_id, zone_id, start_time)
                        VALUES (%s, %s, %s, NOW());
                        """,
                        (site_id, device_id, zone_id),
                    )
                    conn.commit()
                    return
                except psycopg2.errors.UniqueViolation:
                    conn.rollback()
                    conn.autocommit = False
                    with conn.cursor() as cur2:
                        ensure_master_data_site(cur2, site_id, device_id, zone_id)
                        cur2.execute(
                            """
                            SELECT site_id, id, zone_id
                            FROM zone_history
                            WHERE site_id = %s AND device_id = %s AND end_time IS NULL
                            ORDER BY start_time DESC
                            LIMIT 1
                            FOR UPDATE;
                            """,
                            (site_id, device_id),
                        )
                        open_visit = cur2.fetchone()
                        if open_visit is None:
                            raise
                        # continue with same-zone / zone-change logic below

            if open_visit["zone_id"] == zone_id:
                cur.execute(
                    "UPDATE devices SET last_seen = NOW() WHERE site_id = %s AND device_id = %s;",
                    (site_id, device_id),
                )
                conn.commit()
                return

            cur.execute(
                "UPDATE zone_history SET end_time = NOW() WHERE site_id = %s AND id = %s;",
                (site_id, open_visit["id"]),
            )
            cur.execute(
                """
                INSERT INTO zone_history (site_id, device_id, zone_id, start_time)
                VALUES (%s, %s, %s, NOW());
                """,
                (site_id, device_id, zone_id),
            )
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(f"[ingestor] Connected to MQTT {MQTT_BROKER}:{MQTT_PORT}")
        client.subscribe(MQTT_TOPIC, qos=1)
        print(f"[ingestor] Subscribed to {MQTT_TOPIC}")
    else:
        print(f"[ingestor] MQTT connect failed rc={rc}")


def on_message(client, userdata, msg):
    try:
        raw = msg.payload.decode("utf-8")
        payload = json.loads(raw)
        process_event(payload, msg.topic)
    except Exception as e:
        print(f"[ingestor] Error processing message: {e}")


def on_disconnect(client, userdata, rc, properties=None):
    print(f"[ingestor] Disconnected rc={rc}; will auto-reconnect")


def main():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect
    client.reconnect_delay_set(min_delay=1, max_delay=30)

    stopping = {"value": False}

    def _stop(*_args):
        stopping["value"] = True
        try:
            client.disconnect()
        except Exception:
            pass

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    print(f"[ingestor] Starting at {now_utc().isoformat()}")
    print(f"[ingestor] Broker={MQTT_BROKER}:{MQTT_PORT} Topic={MQTT_TOPIC}")
    print(f"[ingestor] DB={DB_HOST}:{DB_PORT}/{DB_NAME}")

    client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)

    while not stopping["value"]:
        client.loop(timeout=1.0)

    print("[ingestor] Stopped")


if __name__ == "__main__":
    main()
