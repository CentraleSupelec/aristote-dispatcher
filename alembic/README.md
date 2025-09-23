# Migrations

Migrations are handled with `alembic`. They are auto-generated in the folder `alembic/versions` from entities' models.

## Launch migration

It is done at sender startup (in the container's entrypoint), but it can be done manually:

```bash
docker compose exec -it sender alembic upgrade head
```

## Generate a new migration

If it is a new entity, make sure it has been imported in [alembic/env.py](alembic/env.py) file.

Generate migrations with the following command :

```shell
docker compose exec -it sender alembic revision --autogenerate -m "my migration name"
```

Please read carefully the file before committing, and add your migration to the table in [History.md](History.md) to
make the tracking easier.
