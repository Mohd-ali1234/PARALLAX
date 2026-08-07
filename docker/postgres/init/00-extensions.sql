-- Runs once, on first initialization of the data volume.
-- Alembic also creates `vector`; this makes a fresh DB usable before migrations.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
