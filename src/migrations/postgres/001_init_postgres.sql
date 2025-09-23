CREATE TYPE client_type as ENUM ('chat');

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    token VARCHAR(255),
    priority INT NOT NULL,
    threshold INT NOT NULL,
    client_type client_type
);

INSERT INTO users (token, priority, threshold, client_type) VALUES 
('tokenwithlowerpriority', 1, 5, NULL),
('tokenwithhigherpriority', 2, 10, 'chat');
