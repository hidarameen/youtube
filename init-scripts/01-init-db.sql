-- =================================
-- Ultra High-Performance Video Downloader Bot
-- Database Initialization Script
-- =================================

-- Create database if it doesn't exist
-- This script runs automatically when PostgreSQL container starts

-- Set optimal configuration for the video bot database
ALTER SYSTEM SET shared_preload_libraries = 'pg_stat_statements';
ALTER SYSTEM SET max_connections = 100;
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';
ALTER SYSTEM SET maintenance_work_mem = '64MB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET wal_buffers = '16MB';
ALTER SYSTEM SET default_statistics_target = 100;
ALTER SYSTEM SET random_page_cost = 1.1;
ALTER SYSTEM SET effective_io_concurrency = 200;

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE video_bot TO postgres;

-- Create indexes for better performance (will be created by SQLAlchemy too)
-- These are additional performance optimizations