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


def print_user(user: User):
    """
    Helper function to format and print user details.
    """
    typer.echo(
        f"- ID: {user.id}, Token: {user.token}, Name: {user.name}, "
        f"Org: {user.organization}, Email: {user.email}, "
        f"Priority: {user.priority}, Threshold: {user.threshold}, "
        f"ClientType: {user.client_type}, Default Routing Mode: {user.default_routing_mode}"
    )


@app.command("list-users")
def list_users(
    token: str = typer.Option(None, "--token", help="Filter by user token"),
    name: str = typer.Option(None, "--name", help="Filter by user's full name"),
    organization: str = typer.Option(
        None, "--organization", help="Filter by organization name"
    ),
    email: str = typer.Option(None, "--email", help="Filter by email address"),
    priority: int = typer.Option(
        None, "--priority", help="Filter by exact priority value"
    ),
    threshold: int = typer.Option(
        None, "--threshold", help="Filter by exact threshold value"
    ),
    client_type: str = typer.Option(
        None, "--client-type", help="Filter by client type"
    ),
    default_routing_mode: str = typer.Option(
        None,
        "--default-routing-mode",
        help="Filter by default routing mode (choices: any, private-first, private-only)",
    ),
):
    """
    List all users in the database, with optional filtering on any field (SQL WHERE clause).
    """
    settings = Settings()
    database = Database(settings)

    with database.get_session() as session:
        query = session.query(User)

        filters = {
            "token": token,
            "name": name,
            "organization": organization,
            "email": email,
            "priority": priority,
            "threshold": threshold,
            "client_type": client_type,
            "default_routing_mode": default_routing_mode,
        }

        for key, value in filters.items():
            if value is not None:
                column = getattr(User, key)
                query = query.filter(column == value)

        users = query.all()

        if not users:
            typer.echo("ℹ️ No users found matching the criteria.")
            return

        typer.echo("---")
        typer.echo("📋 Users:")
        for user in users:
            print_user(user)


@app.command("edit-user")
def edit_user(
    token: str = typer.Argument(..., help="The token of the user to edit"),
    priority: int = typer.Option(None, help="New Priority value"),
    threshold: int = typer.Option(None, help="New Threshold value"),
    organization: str = typer.Option(None, help="New Organization name"),
    email: str = typer.Option(None, help="New Email address"),
    client_type: str = typer.Option(
        None, help="New Client type (set to NULL if not passed)"
    ),
    default_routing_mode: str = typer.Option(
        None,
        help="New Routing mode (choices: any, private-first, private-only)",
    ),
):
    """
    Update a user's details by token, setting any field passed as an argument.
    """
    settings = Settings()
    database = Database(settings)

    updates = {
        "priority": priority,
        "threshold": threshold,
        "organization": organization,
        "email": email,
        "client_type": client_type,
        "default_routing_mode": default_routing_mode,
    }

    updates = {k: v for k, v in updates.items() if v is not None}

    if not updates:
        typer.echo("⚠️ No fields provided for update. Nothing changed.")
        raise typer.Exit(code=0)

    with database.get_session() as session:
        user = session.query(User).filter(User.token == token).first()

        if not user:
            typer.echo(f"❌ No user found with token '{token}'")
            raise typer.Exit(code=1)

        typer.echo(f"📝 Found user '{user.name}' (token={token}). Applying updates...")

        for key, value in updates.items():
            setattr(user, key, value)
            typer.echo(f"   -> Updated {key} to '{value}'")

        try:
            session.commit()
            typer.echo(f"✅ User '{user.name}' updated successfully!")
        except IntegrityError as e:
            session.rollback()
            typer.echo(f"❌ Failed to update user: {e.orig}")
            raise typer.Exit(code=1)
        except Exception as e:
            session.rollback()
            typer.echo(f"❌ An unexpected error occurred: {e}")
            raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
