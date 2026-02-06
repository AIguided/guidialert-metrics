-- IoT Zone Tracker Database Schema
-- This script initializes the database with all required tables and indexes

-- Core Table for Master Data
CREATE TABLE IF NOT EXISTS zones (
    site_id VARCHAR(50) NOT NULL,
    zone_id VARCHAR(50) NOT NULL,
    zone_name TEXT NOT NULL,
    x DOUBLE PRECISION,
    y DOUBLE PRECISION,
    z DOUBLE PRECISION,
    PRIMARY KEY (site_id, zone_id)
);

CREATE TABLE IF NOT EXISTS devices (
    site_id VARCHAR(50) NOT NULL,
    device_id VARCHAR(50) NOT NULL,
    device_name TEXT NOT NULL,
    last_seen TIMESTAMPTZ,
    PRIMARY KEY (site_id, device_id)
);

-- Anchor positions (current snapshot) + history
CREATE TABLE IF NOT EXISTS anchors (
    site_id VARCHAR(50) NOT NULL,
    anchor_id VARCHAR(50) NOT NULL,
    anchor_name TEXT NOT NULL,
    x DOUBLE PRECISION,
    y DOUBLE PRECISION,
    z DOUBLE PRECISION,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (site_id, anchor_id)
);

CREATE TABLE IF NOT EXISTS anchor_history (
    site_id VARCHAR(50) NOT NULL,
    id BIGSERIAL NOT NULL,
    anchor_id VARCHAR(50) NOT NULL,
    x DOUBLE PRECISION,
    y DOUBLE PRECISION,
    z DOUBLE PRECISION,
    source TEXT,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (site_id, id),
    CONSTRAINT anchor_history_anchor_fk FOREIGN KEY (site_id, anchor_id)
        REFERENCES anchors(site_id, anchor_id)
);

-- The State-Tracking Table (partitioned by site_id)
CREATE TABLE IF NOT EXISTS zone_history (
    site_id VARCHAR(50) NOT NULL,
    id BIGSERIAL NOT NULL,
    device_id VARCHAR(50) NOT NULL,
    zone_id VARCHAR(50) NOT NULL,
    start_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    end_time TIMESTAMPTZ, -- NULL means the device is currently in this zone
    duration INTERVAL GENERATED ALWAYS AS (end_time - start_time) STORED,
    PRIMARY KEY (site_id, id),
    CONSTRAINT zone_history_device_fk FOREIGN KEY (site_id, device_id)
        REFERENCES devices(site_id, device_id),
    CONSTRAINT zone_history_zone_fk FOREIGN KEY (site_id, zone_id)
        REFERENCES zones(site_id, zone_id)
) PARTITION BY LIST (site_id);

-- Ensure a default partition exists for unknown/new sites
CREATE TABLE IF NOT EXISTS zone_history_default
    PARTITION OF zone_history DEFAULT;

-- Indexing for performance
CREATE INDEX IF NOT EXISTS idx_site_device_end_time ON zone_history(site_id, device_id) WHERE (end_time IS NULL);
CREATE INDEX IF NOT EXISTS idx_site_start_time ON zone_history(site_id, start_time);

CREATE INDEX IF NOT EXISTS idx_anchor_history_latest
ON anchor_history(site_id, anchor_id, observed_at DESC);

-- Prevent two workers from creating two "open" visits for the same device
CREATE UNIQUE INDEX IF NOT EXISTS uq_open_visit_per_device
ON zone_history(site_id, device_id)
WHERE (end_time IS NULL);

-- Insert sample zones for testing
INSERT INTO zones (site_id, zone_id, zone_name, x, y, z) VALUES
    ('site-001', 'zone-A', 'Entrance Hall', 0, 0, 0),
    ('site-001', 'zone-B', 'Main Office', 10, 0, 0),
    ('site-001', 'zone-C', 'Conference Room', 10, 5, 0),
    ('site-001', 'zone-D', 'Cafeteria', 0, 5, 0),
    ('site-001', 'zone-E', 'Parking Lot', -10, 0, 0)
ON CONFLICT (site_id, zone_id) DO NOTHING;

-- Insert sample devices for testing
INSERT INTO devices (site_id, device_id, device_name, last_seen) VALUES
    ('site-001', 'device-001', 'Tracker Alpha', NULL),
    ('site-001', 'device-002', 'Tracker Beta', NULL),
    ('site-001', 'device-003', 'Tracker Gamma', NULL)
ON CONFLICT (site_id, device_id) DO NOTHING;
