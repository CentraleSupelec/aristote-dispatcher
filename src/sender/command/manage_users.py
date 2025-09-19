import typer
from sqlalchemy.exc import IntegrityError

from src.sender.db import Database
from src.sender.entities.user import User
from src.sender.settings import Settings

app = typer.Typer(help="Database management CLI")


@app.command("add-user")
def add_user(
    token: str = typer.Option(..., help="User token (required)"),
    priority: int = typer.Option(..., help="Priority value (required)"),
    threshold: int = typer.Option(..., help="Threshold value (required)"),
    name: str = typer.Option(..., help="User's full name (required)"),
    organization: str = typer.Option(..., help="Organization name (required)"),
    email: str = typer.Option(..., help="Email address (required)"),
    client_type: str = typer.Option(None, help="Client type (optional, omit for NULL)"),
    default_routing_mode: str = typer.Option(
        "any",
        help="Routing mode (choices: any, private-first, private-only)",
    ),
):
    """
    Insert a new user into the database with ORM (SQLAlchemy).
    """
    settings = Settings()
    database = Database(settings)

    with database.get_session() as session:
        new_user = User(
            token=token,
            priority=priority,
            threshold=threshold,
            client_type=client_type,
            name=name,
            organization=organization,
            email=email,
            default_routing_mode=default_routing_mode,
        )
        session.add(new_user)

        try:
            session.commit()
            typer.echo(f"✅ User '{name}' inserted successfully!")
        except IntegrityError as e:
            session.rollback()
            typer.echo(f"❌ Failed to insert user: {e.orig}")


@app.command("delete-user")
def delete_user(
    token: str = typer.Argument(..., help="The token of the user to delete")
):
    """
    Delete a user from the database by token.
    """
    settings = Settings()
    database = Database(settings)

    with database.get_session() as session:
        user = session.query(User).filter(User.token == token).first()
        if not user:
            typer.echo(f"❌ No user found with token '{token}'")
            raise typer.Exit(code=1)

        session.delete(user)
        session.commit()
        typer.echo(f"🗑️ User '{user.name}' (token={token}) deleted successfully.")


@app.command("list-users")
def list_users():
    """
    List all users in the database.
    """
    settings = Settings()
    database = Database(settings)

    with database.get_session() as session:
        users = session.query(User).all()
        if not users:
            typer.echo("ℹ️ No users found in the database.")
            return

        typer.echo("📋 Users:")
        for user in users:
            typer.echo(
                f"- ID: {user.id}, Token: {user.token}, Name: {user.name}, "
                f"Org: {user.organization}, Email: {user.email}, "
                f"Priority: {user.priority}, Threshold: {user.threshold}, "
                f"ClientType: {user.client_type}"
            )


if __name__ == "__main__":
    app()
