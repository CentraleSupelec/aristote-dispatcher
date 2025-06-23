ALTER TABLE users ADD COLUMN name VARCHAR(255);

UPDATE users SET name = 'name_' || id;

ALTER TABLE users
ALTER COLUMN name SET NOT NULL,
ADD CONSTRAINT users_name_unique UNIQUE (name);


ALTER TABLE users
ADD CONSTRAINT unique_token UNIQUE (token);

CREATE TABLE metrics (
    id SERIAL PRIMARY KEY,
    user_name VARCHAR(255) NOT NULL,
    request_date TIMESTAMP,
    sent_to_llm_date TIMESTAMP,
    response_date TIMESTAMP,
    model VARCHAR(255),
    prompt_tokens INT,
    completion_tokens INT,
    CONSTRAINT fk_user_name FOREIGN KEY(user_name) REFERENCES users(name)
);
