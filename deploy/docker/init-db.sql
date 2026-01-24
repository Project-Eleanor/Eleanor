-- Eleanor Database Initialization
-- This script runs on first PostgreSQL startup

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE eleanor TO eleanor;
