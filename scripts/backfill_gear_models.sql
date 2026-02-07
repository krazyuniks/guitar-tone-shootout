-- Backfill gear_models from archive database (gts_restore_temp)
-- One-time data migration script — NOT an Alembic migration.
--
-- Run against gts_core:
--   docker exec <db-container> psql -U gts -d gts_core -f /path/to/backfill_gear_models.sql
--
-- Prerequisites:
--   - gts_restore_temp database exists with archive gear_model table
--   - dblink extension available
--   - gear table already populated in gts_core

-- Enable dblink for cross-database query
CREATE EXTENSION IF NOT EXISTS dblink;

-- Create staging table
CREATE TABLE IF NOT EXISTS _archive_gear_model (
    id uuid NOT NULL,
    gear_id uuid NOT NULL,
    download_url text,
    file_hash varchar(128)
);

-- Copy from archive via dblink
INSERT INTO _archive_gear_model (id, gear_id, download_url, file_hash)
SELECT *
FROM dblink(
    'dbname=gts_restore_temp user=gts',
    'SELECT gm.id, gm.gear_id, gm.download_url, gm.file_hash FROM gear_model gm'
) AS t(id uuid, gear_id uuid, download_url text, file_hash varchar(128));

-- Insert into gear_models, deriving platform from gear table
INSERT INTO gear_models (id, gear_id, platform, size, download_url, download_status, file_hash)
SELECT
    a.id,
    a.gear_id,
    g.platform,
    'standard',
    a.download_url,
    'pending',
    a.file_hash
FROM _archive_gear_model a
JOIN gear g ON g.id = a.gear_id
WHERE NOT EXISTS (SELECT 1 FROM gear_models gm WHERE gm.id = a.id);

-- Clean up
DROP TABLE _archive_gear_model;

-- Verify
SELECT COUNT(*) AS gear_models_count FROM gear_models;
SELECT platform, COUNT(*) FROM gear_models GROUP BY platform ORDER BY count DESC;
