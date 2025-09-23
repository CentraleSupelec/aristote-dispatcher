-- delete client_type type, and use varchar instead
ALTER TABLE users ALTER COLUMN client_type TYPE VARCHAR(255);
DROP TYPE IF EXISTS client_type;

-- create up to date alembic_version table
CREATE TABLE alembic_version (
   version_num VARCHAR(32)
);
INSERT INTO alembic_version (version_num) VALUES ('9cf7cf124677');
