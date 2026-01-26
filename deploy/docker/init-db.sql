-- =============================================================================
-- Eleanor Database Initialization Script
-- =============================================================================
-- This script runs on first database creation
-- Creates extensions and initial configuration
-- =============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE eleanor TO eleanor;

-- Function to update timestamps automatically
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Print completion message
DO $$
BEGIN
    RAISE NOTICE 'Eleanor database initialization complete';
END $$;
