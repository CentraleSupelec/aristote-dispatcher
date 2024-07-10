# Development

To test the project locally, you need to have docker and docker-compose installed.

First, change the init_db files to put the right tokens and priorities. Example files are provided for both mysql and postgresql.

Then, run the following command:

```bash
docker compose up --build
```

You need to have a model running at localhost:50000 (the port and the host are customizable) or at least any kind of service that can be used to test the system.
