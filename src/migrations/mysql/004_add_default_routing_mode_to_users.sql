ALTER TABLE users
ADD COLUMN default_routing_mode VARCHAR(20) NOT NULL DEFAULT 'any';
