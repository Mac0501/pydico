from dataclasses import dataclass

import click

from examples.click_cli.container import build_provider
from examples.click_cli.services import UserService
from pydico import ServiceProvider


@dataclass(frozen=True, slots=True)
class CliState:
    provider: ServiceProvider


@click.group()
def cli() -> None:
    """Manage the users in the example application."""


@cli.command("users")
@click.option("--all", "show_all", is_flag=True, help="Include inactive users.")
@click.pass_obj
def list_users(state: CliState, show_all: bool) -> None:
    with state.provider.create_scope() as scope:
        service = scope.get_service(UserService)
        if service is None:
            raise RuntimeError("UserService is not registered.")
        for user in service.list(active_only=not show_all):
            status = "active" if user.active else "inactive"
            click.echo(f"{user.id}: {user.name} ({status})")


@cli.command()
@click.argument("user_id", type=int)
@click.pass_obj
def deactivate(state: CliState, user_id: int) -> None:
    with state.provider.create_scope() as scope:
        service = scope.get_service(UserService)
        if service is None:
            raise RuntimeError("UserService is not registered.")
        user = service.deactivate(user_id)
        if user is None:
            raise click.ClickException(f"User {user_id} does not exist.")
        click.echo(f"Deactivated {user.name}.")


def main() -> None:
    provider = build_provider()
    try:
        cli(obj=CliState(provider=provider), standalone_mode=True)
    finally:
        provider.close()


if __name__ == "__main__":
    main()
