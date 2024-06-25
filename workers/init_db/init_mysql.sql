CREATE TABLE users (id INT NOT NULL AUTO_INCREMENT PRIMARY KEY, token VARCHAR(255), priority INT NOT NULL, threshold INT NOT NULL);
INSERT INTO users (token, priority) VALUES ('Token with lower priority', 1, 5);
INSERT INTO users (token, priority) VALUES ('Token with higher priority', 2, 10);

