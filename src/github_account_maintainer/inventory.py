from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, cast

from github_account_maintainer import __version__
from github_account_maintainer.auth import (
    ClientFactory,
    CredentialResolver,
    auth_report_from_response,
    client_factory,
)
from github_account_maintainer.config import AppConfig
from github_account_maintainer.constants import GITHUB_API_VERSION
from github_account_maintainer.credentials import resolve_credential
from github_account_maintainer.github_api import GitHubApiError, GitHubTransportError, accepted_permissions
from github_account_maintainer.models import (
    CoverageRecord,
    CoverageState,
    InventoryReport,
    RepositoryInventoryRecord,
    RepositoryPermissions,
    RunStatus,
)


class InventoryCollectionError(RuntimeError):
    pass


@dataclass(frozen=True)
class InventoryTarget:
    record: RepositoryInventoryRecord
    api_name: str


@dataclass(frozen=True)
class InventorySnapshot:
    report: InventoryReport
    targets: tuple[InventoryTarget, ...]


def collect_inventory(
    config: AppConfig,
    *,
    credential_resolver: CredentialResolver = resolve_credential,
    make_client: ClientFactory = client_factory,
) -> InventoryReport:
    return collect_inventory_snapshot(
        config,
        credential_resolver=credential_resolver,
        make_client=make_client,
    ).report


def collect_inventory_snapshot(
    config: AppConfig,
    *,
    credential_resolver: CredentialResolver = resolve_credential,
    make_client: ClientFactory = client_factory,
) -> InventorySnapshot:
    started_at = datetime.now(UTC)
    credential = credential_resolver(config.credentials.discovery)
    records: dict[int, RepositoryInventoryRecord] = {}
    targets: dict[int, InventoryTarget] = {}
    coverage: list[CoverageRecord] = []
    permissions: set[str] = set()
    pages_read = 0
    duplicates_removed = 0
    failure_detail: str | None = None

    with make_client(credential.secret.get_secret_value(), config.account.github_host) as client:
        user_response = client.get("/user")
        auth_report_from_response(config, credential, user_response)
        try:
            for response, items in client.paginate_pages("/user/repos", params=_inventory_params(config)):
                pages_read += 1
                permission_header = accepted_permissions(response)
                if permission_header:
                    permissions.add(permission_header)
                for item in items:
                    target = _repository_target(item, detail=config.local_data.report_detail)
                    record = target.record
                    if record.repository_id in records:
                        duplicates_removed += 1
                        continue
                    records[record.repository_id] = record
                    targets[record.repository_id] = target
                    coverage.append(
                        CoverageRecord(
                            repository_id=record.repository_id,
                            check_id="inventory.repository",
                            state=CoverageState.AUDITED,
                        )
                    )
        except GitHubApiError as error:
            if error.accepted_permissions:
                permissions.add(error.accepted_permissions)
            retry = f":retry_after={error.retry_after}" if error.retry_after else ""
            failure_detail = f"{error.kind}:{error.status_code}{retry}"
        except GitHubTransportError as error:
            failure_detail = str(error)
        except (TypeError, ValueError, InventoryCollectionError) as error:
            failure_detail = str(error)

    if failure_detail is None:
        status = RunStatus.COMPLETE
        collection_state = CoverageState.AUDITED
    else:
        status = RunStatus.PARTIAL
        collection_state = CoverageState.FAILED
    coverage.append(
        CoverageRecord(
            check_id="inventory.repositories",
            state=collection_state,
            detail=failure_detail,
        )
    )

    report = InventoryReport(
        tool_version=__version__,
        github_api_version=GITHUB_API_VERSION,
        account_display=config.account.login,
        credential_source=credential.source,
        declared_affiliations=tuple(config.account.affiliations),
        started_at=started_at,
        completed_at=datetime.now(UTC),
        status=status,
        pages_read=pages_read,
        duplicates_removed=duplicates_removed,
        accepted_permissions=tuple(sorted(permissions)),
        repositories=tuple(sorted(records.values(), key=lambda item: item.repository_id)),
        coverage=tuple(coverage),
    )
    return InventorySnapshot(
        report=report,
        targets=tuple(sorted(targets.values(), key=lambda item: item.record.repository_id)),
    )


def _inventory_params(config: AppConfig) -> dict[str, str | int]:
    return {
        "affiliation": ",".join(config.account.affiliations),
        "visibility": "all" if config.account.include_private else "public",
        "sort": "full_name",
        "direction": "asc",
        "per_page": 100,
    }


def _repository_target(payload: dict[str, object], *, detail: str) -> InventoryTarget:
    repository_id = payload.get("id")
    node_id = payload.get("node_id")
    full_name = payload.get("full_name")
    private = payload.get("private")
    archived = payload.get("archived")
    fork = payload.get("fork")
    visibility = payload.get("visibility")
    html_url = payload.get("html_url")

    if not isinstance(repository_id, int):
        raise InventoryCollectionError("Repository response did not contain a valid id")
    if not isinstance(node_id, str) or not isinstance(full_name, str):
        raise InventoryCollectionError(f"Repository {repository_id} did not contain valid identity fields")
    if not isinstance(private, bool) or not isinstance(archived, bool) or not isinstance(fork, bool):
        raise InventoryCollectionError(f"Repository {repository_id} did not contain valid state fields")
    if not isinstance(visibility, str) or visibility not in {"public", "private", "internal"}:
        raise InventoryCollectionError(f"Repository {repository_id} returned an unknown visibility")
    if private != (visibility == "private"):
        raise InventoryCollectionError(f"Repository {repository_id} returned inconsistent visibility")
    if html_url is not None and not isinstance(html_url, str):
        raise InventoryCollectionError(f"Repository {repository_id} did not contain a valid URL")

    normalized_visibility = cast(Literal["public", "private", "internal"], visibility)
    redact = normalized_visibility != "public" and detail == "minimal"
    record = RepositoryInventoryRecord(
        repository_id=repository_id,
        node_id=node_id,
        display_name=f"nonpublic-repository:{repository_id}" if redact else full_name,
        private=private,
        visibility=normalized_visibility,
        archived=archived,
        fork=fork,
        html_url=None if redact else html_url,
        permissions=_permissions(payload.get("permissions")),
    )
    return InventoryTarget(record=record, api_name=full_name)


def _permissions(value: object) -> RepositoryPermissions:
    if value is None:
        return RepositoryPermissions()
    if not isinstance(value, dict):
        raise InventoryCollectionError("Repository permissions were not a JSON object")
    permission_values = cast(dict[str, object], value)
    return RepositoryPermissions(
        admin=_optional_bool(permission_values.get("admin")),
        maintain=_optional_bool(permission_values.get("maintain")),
        push=_optional_bool(permission_values.get("push")),
        triage=_optional_bool(permission_values.get("triage")),
        pull=_optional_bool(permission_values.get("pull")),
    )


def _optional_bool(value: object) -> bool | None:
    return value if isinstance(value, bool) else None
