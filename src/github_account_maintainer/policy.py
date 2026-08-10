import hashlib
import json
from datetime import datetime, timedelta
from enum import StrEnum
from fnmatch import fnmatchcase
from typing import Literal, cast

from pydantic import Field, JsonValue, field_validator

from github_account_maintainer.config import (
    AppConfig,
    CommunityConfig,
    MetadataConfig,
    NotificationConfig,
    PinConfig,
    PolicyExceptionConfig,
    PolicySettingsPatch,
    ReadmeConfig,
    RepositoryConfig,
    SecurityConfig,
    SocialPreviewConfig,
    StrictModel,
)
from github_account_maintainer.models import PolicySource, PolicyTraceRecord

type JsonObject = dict[str, JsonValue]


class PolicySettings(StrictModel):
    repositories: RepositoryConfig = RepositoryConfig()
    pins: PinConfig = PinConfig()
    readme: ReadmeConfig = ReadmeConfig()
    metadata: MetadataConfig = MetadataConfig()
    community: CommunityConfig = CommunityConfig()
    social_preview: SocialPreviewConfig = SocialPreviewConfig()
    security: SecurityConfig = SecurityConfig()
    notifications: NotificationConfig = NotificationConfig()


class PolicyTarget(StrictModel):
    repository: str
    repository_class: str | None = None
    project_type: str | None = None
    evaluated_at: datetime

    @field_validator("repository", "repository_class", "project_type")
    @classmethod
    def validate_nonempty_selector(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("policy target values must not be empty")
        return normalized

    @field_validator("evaluated_at")
    @classmethod
    def validate_utc_timestamp(cls, value: datetime) -> datetime:
        if value.utcoffset() != timedelta(0):
            raise ValueError("evaluated_at must use RFC 3339 UTC")
        return value


class ExceptionState(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"
    PENDING = "pending"


class ResolvedPolicy(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    target: PolicyTarget
    settings: PolicySettings
    active_exceptions: tuple[PolicyExceptionConfig, ...] = ()
    expired_exception_ids: tuple[str, ...] = ()
    pending_exception_ids: tuple[str, ...] = ()
    suppressed_checks: tuple[str, ...] = ()
    trace: tuple[PolicyTraceRecord, ...]
    policy_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


def resolve_policy(config: AppConfig, target: PolicyTarget) -> ResolvedPolicy:
    built_in = PolicySettings()
    built_in_values = cast(JsonObject, built_in.model_dump(mode="json"))
    resolved = built_in_values.copy()
    trace = _default_trace(resolved)

    account = cast(
        JsonObject,
        PolicySettings(
            repositories=config.repositories,
            pins=config.pins,
            readme=config.readme,
            metadata=config.metadata,
            community=config.community,
            social_preview=config.social_preview,
            security=config.security,
            notifications=config.notifications,
        ).model_dump(mode="json"),
    )
    _apply_layer(
        resolved,
        _changed_values(built_in_values, account),
        PolicySource.ACCOUNT,
        None,
        trace,
    )

    layers = (
        (PolicySource.REPOSITORY_CLASS, target.repository_class, config.policy.repository_classes),
        (PolicySource.PROJECT_TYPE, target.project_type, config.policy.project_types),
        (PolicySource.REPOSITORY, target.repository, config.policy.repositories),
    )
    for source, source_key, available in layers:
        if source_key is None:
            continue
        patch = _case_insensitive_get(available, source_key)
        if patch is not None:
            _apply_layer(resolved, _patch_values(patch), source, source_key, trace)

    active, expired, pending = _matching_exceptions(config.policy.exceptions, target)
    suppressed_checks = tuple(sorted({check_id for exception in active for check_id in exception.check_ids}))
    for exception in active:
        trace.append(
            PolicyTraceRecord(
                path=f"exceptions.{exception.exception_id}.check_ids",
                source=PolicySource.EXCEPTION,
                source_key=exception.target_selector,
                value=list(exception.check_ids),
            )
        )
    for exception_id in expired:
        trace.append(
            PolicyTraceRecord(
                path=f"exceptions.{exception_id}.state",
                source=PolicySource.EXCEPTION,
                value=ExceptionState.EXPIRED.value,
            )
        )
    for exception_id in pending:
        trace.append(
            PolicyTraceRecord(
                path=f"exceptions.{exception_id}.state",
                source=PolicySource.EXCEPTION,
                value=ExceptionState.PENDING.value,
            )
        )

    settings = PolicySettings.model_validate(resolved)
    canonical: JsonObject = {
        "schema_version": "1.0",
        "settings": cast(JsonObject, settings.model_dump(mode="json")),
        "active_exceptions": [cast(JsonObject, exception.model_dump(mode="json")) for exception in active],
        "expired_exception_ids": list(expired),
        "pending_exception_ids": list(pending),
        "suppressed_checks": list(suppressed_checks),
    }
    return ResolvedPolicy(
        target=target,
        settings=settings,
        active_exceptions=active,
        expired_exception_ids=expired,
        pending_exception_ids=pending,
        suppressed_checks=suppressed_checks,
        trace=tuple(trace),
        policy_hash=_canonical_sha256(canonical),
    )


def _default_trace(values: JsonObject) -> list[PolicyTraceRecord]:
    return [PolicyTraceRecord(path=path, source=PolicySource.BUILT_IN, value=value) for path, value in _flatten(values)]


def _patch_values(patch: PolicySettingsPatch) -> JsonObject:
    return cast(JsonObject, patch.model_dump(mode="json", exclude_none=True))


def _changed_values(defaults: JsonObject, configured: JsonObject) -> JsonObject:
    changes: JsonObject = {}
    for key in sorted(configured):
        current = configured[key]
        default = defaults.get(key)
        if isinstance(current, dict) and isinstance(default, dict):
            nested = _changed_values(cast(JsonObject, default), cast(JsonObject, current))
            if nested:
                changes[key] = nested
        elif current != default:
            changes[key] = current
    return changes


def _apply_layer(
    resolved: JsonObject,
    patch: JsonObject,
    source: PolicySource,
    source_key: str | None,
    trace: list[PolicyTraceRecord],
    prefix: str = "",
) -> None:
    for key in sorted(patch):
        path = f"{prefix}.{key}" if prefix else key
        value = patch[key]
        existing = resolved.get(key)
        if isinstance(value, dict) and isinstance(existing, dict):
            _apply_layer(
                cast(JsonObject, existing),
                cast(JsonObject, value),
                source,
                source_key,
                trace,
                path,
            )
            continue
        resolved[key] = value
        trace.append(PolicyTraceRecord(path=path, source=source, source_key=source_key, value=value))


def _flatten(values: JsonObject, prefix: str = "") -> list[tuple[str, JsonValue]]:
    flattened: list[tuple[str, JsonValue]] = []
    for key in sorted(values):
        path = f"{prefix}.{key}" if prefix else key
        value = values[key]
        if isinstance(value, dict):
            flattened.extend(_flatten(cast(JsonObject, value), path))
        else:
            flattened.append((path, value))
    return flattened


def _case_insensitive_get(values: dict[str, PolicySettingsPatch], key: str) -> PolicySettingsPatch | None:
    normalized = key.casefold()
    return next((value for candidate, value in values.items() if candidate.casefold() == normalized), None)


def _matching_exceptions(
    exceptions: tuple[PolicyExceptionConfig, ...], target: PolicyTarget
) -> tuple[tuple[PolicyExceptionConfig, ...], tuple[str, ...], tuple[str, ...]]:
    matching = sorted(
        (
            exception
            for exception in exceptions
            if fnmatchcase(target.repository.casefold(), exception.target_selector.casefold())
        ),
        key=lambda exception: exception.exception_id.casefold(),
    )
    active: list[PolicyExceptionConfig] = []
    expired: list[str] = []
    pending: list[str] = []
    for exception in matching:
        if exception.created_at > target.evaluated_at:
            pending.append(exception.exception_id)
        elif exception.permanent or (exception.expires_at is not None and exception.expires_at > target.evaluated_at):
            active.append(exception)
        else:
            expired.append(exception.exception_id)
    return tuple(active), tuple(expired), tuple(pending)


def _canonical_sha256(value: JsonObject) -> str:
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()
