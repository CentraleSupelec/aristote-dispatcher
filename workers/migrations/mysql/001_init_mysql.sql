CREATE TABLE users (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    token VARCHAR(255),
    priority INT NOT NULL,
    threshold INT NOT NULL,
    client_type ENUM('chat')
);

INSERT INTO users (token, priority, threshold, client_type) VALUES ('tokenwithlowerpriority', 1, 5, NULL);
INSERT INTO users (token, priority, threshold, client_type) VALUES ('tokenwithhigherpriority', 2, 10, 'chat');
