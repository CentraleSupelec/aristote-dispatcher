import typer
from db import Database
from settings import Settings
from sqlalchemy import text

app = typer.Typer()


@app.command()
def add_user(
    token: str = typer.Option(..., help="User token (required)"),
    priority: int = typer.Option(..., help="Priority value (required)"),
    threshold: int = typer.Option(..., help="Threshold value (required)"),
    name: str = typer.Option(..., help="User's full name (required)"),
    organization: str = typer.Option(..., help="Organization name (required)"),
    email: str = typer.Option(..., help="Email address (required)"),
    client_type: str = typer.Option(None, help="Client type (optional, omit for NULL)"),
):
    """
    Insert a new user into the database with all required fields enforced.
    """
    settings = Settings()
    database = Database(settings)

    with database.get_session() as session:
        session.execute(
            text(
                """
                INSERT INTO users (token, priority, threshold, client_type, name, organization, email)
                VALUES (:token, :priority, :threshold, :client_type, :name, :organization, :email)
            """
            ),
            {
                "token": token,
                "priority": priority,
                "threshold": threshold,
                "client_type": client_type,  # Will be NULL if not provided
                "name": name,
                "organization": organization,
                "email": email,
            },
        )
        session.commit()

    typer.echo(f"✅ User '{name}' inserted successfully!")


if __name__ == "__main__":
    app()
