-- GTS Database Initialization
-- Creates dual database architecture: gts_core and gts_t3k_source

-- The default database (gts_core) is created by POSTGRES_DB env var.
-- This script creates the T3K source database.

-- Create T3K source database
CREATE DATABASE gts_t3k_source
    WITH OWNER = gts
    ENCODING = 'UTF8'
    LC_COLLATE = 'en_US.utf8'
    LC_CTYPE = 'en_US.utf8'
    TEMPLATE = template0;

-- Grant full privileges to gts user on both databases
GRANT ALL PRIVILEGES ON DATABASE gts_core TO gts;
GRANT ALL PRIVILEGES ON DATABASE gts_t3k_source TO gts;
