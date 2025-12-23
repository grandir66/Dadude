-- DaDude v2.0 - PostgreSQL Database Initialization
-- This script runs on first container start

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For text search

-- Create custom types (if needed)
-- Note: Most types are handled by SQLAlchemy/Alembic migrations

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE dadude TO dadude;

-- Create schema for organizing tables (optional)
-- CREATE SCHEMA IF NOT EXISTS dadude;
-- ALTER ROLE dadude SET search_path TO dadude, public;

-- Log initialization
DO $$
BEGIN
    RAISE NOTICE 'DaDude v2.0 database initialized successfully';
END $$;
