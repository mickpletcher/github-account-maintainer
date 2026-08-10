from enum import StrEnum
from pathlib import Path
from typing import Annotated, NoReturn

import typer
import yaml
from pydantic import ValidationError

from github_account_maintainer import __version__
from github_account_maintainer.auth import AuthenticationPreflightError, run_auth_check
from github_account_maintainer.config import AppConfig, default_config, default_config_path, load_config, write_config
from github_account_maintainer.credentials import CredentialResolutionError
from github_account_maintainer.github_api import GitHubApiError, GitHubTransportError
from github_account_maintainer.inventory import collect_inventory
from github_account_maintainer.models import RunStatus
from github_account_maintainer.reporting import render_auth_markdown, render_inventory_markdown, render_json

app = typer.Typer(
    help="Audit GitHub account resources against an explicit policy.",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)
auth_app = typer.Typer(help="Inspect authentication without exposing credentials.")
app.add_typer(auth_app, name="auth")


class OutputFormat(StrEnum):
    JSON = "json"
    MARKDOWN = "markdown"


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
    typer.echo(f"{command} is reserved for a later Release 0.1 implementation.", err=True)
    raise typer.Exit(2)


@auth_app.command("check")
def auth_check(
    config_path: Annotated[Path | None, typer.Option("--config", help="Local configuration path.")] = None,
    output_format: Annotated[OutputFormat, typer.Option("--format", help="Output format.")] = OutputFormat.JSON,
) -> None:
    config = load_app_config(config_path or default_config_path())
    try:
        report = run_auth_check(config)
    except (CredentialResolutionError, AuthenticationPreflightError, GitHubApiError, GitHubTransportError) as error:
        fail_operational(error)
    typer.echo(render_json(report) if output_format is OutputFormat.JSON else render_auth_markdown(report), nl=False)


@app.command("inventory")
def inventory(
    config_path: Annotated[Path | None, typer.Option("--config", help="Local configuration path.")] = None,
    output_format: Annotated[OutputFormat, typer.Option("--format", help="Output format.")] = OutputFormat.JSON,
) -> None:
    config = load_app_config(config_path or default_config_path())
    try:
        report = collect_inventory(config)
    except (CredentialResolutionError, AuthenticationPreflightError, GitHubApiError, GitHubTransportError) as error:
        fail_operational(error)
    typer.echo(
        render_json(report) if output_format is OutputFormat.JSON else render_inventory_markdown(report), nl=False
    )
    if report.status is RunStatus.PARTIAL:
        raise typer.Exit(2)


@app.command("audit")
def audit() -> None:
    unavailable("audit")


def load_app_config(path: Path) -> AppConfig:
    try:
        return load_config(path)
    except (FileNotFoundError, OSError, ValidationError, yaml.YAMLError) as error:
        typer.echo(f"Invalid configuration: {type(error).__name__}", err=True)
        raise typer.Exit(3) from None


def fail_operational(error: Exception) -> NoReturn:
    typer.echo(str(error), err=True)
    raise typer.Exit(2) from None


def main() -> None:
    app()
