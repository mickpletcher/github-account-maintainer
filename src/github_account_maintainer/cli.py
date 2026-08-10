from pathlib import Path
from typing import Annotated

import typer

from github_account_maintainer import __version__
from github_account_maintainer.config import default_config, default_config_path, write_config

app = typer.Typer(
    help="Audit GitHub account resources against an explicit policy.",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)
auth_app = typer.Typer(help="Inspect authentication without exposing credentials.")
app.add_typer(auth_app, name="auth")


def version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def root(
    version: Annotated[
        bool,
        typer.Option("--version", callback=version_callback, is_eager=True, help="Show the version and exit."),
    ] = False,
) -> None:
    pass


@app.command("init")
def init_command(
    login: Annotated[str, typer.Option("--login", help="GitHub login to place in the local configuration.")],
    output: Annotated[Path | None, typer.Option("--output", help="Explicit configuration output path.")] = None,
    overwrite: Annotated[
        bool, typer.Option("--overwrite", help="Replace an existing configuration atomically.")
    ] = False,
) -> None:
    target = output if output is not None else default_config_path()
    try:
        write_config(default_config(login), target, overwrite=overwrite)
    except FileExistsError:
        typer.echo(f"Configuration already exists: {target}", err=True)
        raise typer.Exit(3) from None
    typer.echo(f"Created configuration: {target.resolve()}")


def unavailable(command: str) -> None:
    typer.echo(f"{command} is reserved for the authentication and inventory implementation.", err=True)
    raise typer.Exit(2)


@auth_app.command("check")
def auth_check() -> None:
    unavailable("auth check")


@app.command("inventory")
def inventory() -> None:
    unavailable("inventory")


@app.command("audit")
def audit() -> None:
    unavailable("audit")


def main() -> None:
    app()
