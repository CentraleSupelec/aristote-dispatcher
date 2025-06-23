ALTER TABLE users ADD COLUMN name VARCHAR(255);

UPDATE users SET name = CONCAT('name_', id);

ALTER TABLE users
MODIFY COLUMN name VARCHAR(255) NOT NULL,
ADD UNIQUE KEY users_name_unique (name);

ALTER TABLE users
ADD CONSTRAINT unique_token UNIQUE (token);

CREATE TABLE metrics (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    user_name VARCHAR(255) NOT NULL,
    request_date DATETIME,
    sent_to_llm_date DATETIME,
    response_date DATETIME,
    model VARCHAR(255),
    prompt_tokens INT,
    completion_tokens INT,
    CONSTRAINT fk_user_name FOREIGN KEY (user_name) REFERENCES users(name)
);
