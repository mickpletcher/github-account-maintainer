from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from github_account_maintainer.config import (
    AppConfig,
    PolicyExceptionConfig,
    PolicyHierarchyConfig,
    ReadmeConfig,
    default_config,
)
from github_account_maintainer.models import PolicySource
from github_account_maintainer.policy import PolicyTarget, resolve_policy

FIXTURES = Path(__file__).parent / "fixtures"
EVALUATED_AT = datetime(2026, 8, 10, tzinfo=UTC)


def test_policy_resolution_uses_required_precedence_and_trace() -> None:
    hierarchy = PolicyHierarchyConfig.model_validate(
        {
            "repository_classes": {"application": {"readme": {"validate_links": True}}},
            "project_types": {"python": {"readme": {"validate_links": False}}},
            "repositories": {"mick/example": {"readme": {"validate_links": True}}},
        }
    )
    config = default_config("mick").model_copy(
        update={"readme": ReadmeConfig(validate_links=False), "policy": hierarchy}
    )

    resolved = resolve_policy(
        config,
        PolicyTarget(
            repository="Mick/Example",
            repository_class="application",
            project_type="python",
            evaluated_at=EVALUATED_AT,
        ),
    )

    assert resolved.settings.readme.validate_links is True
    entries = [entry for entry in resolved.trace if entry.path == "readme.validate_links"]
    assert [(entry.source, entry.value) for entry in entries] == [
        (PolicySource.BUILT_IN, True),
        (PolicySource.ACCOUNT, False),
        (PolicySource.REPOSITORY_CLASS, True),
        (PolicySource.PROJECT_TYPE, False),
        (PolicySource.REPOSITORY, True),
    ]


def test_equivalent_policy_fixtures_have_identical_results_and_hashes() -> None:
    first = _config_from_fixture("policy-equivalent-a.yaml")
    second = _config_from_fixture("policy-equivalent-b.yaml")
    target = PolicyTarget(
        repository="Mick/Example",
        repository_class="application",
        project_type="python",
        evaluated_at=EVALUATED_AT,
    )

    first_result = resolve_policy(first, target)
    second_result = resolve_policy(second, target)

    assert first_result == second_result
    assert len(first_result.policy_hash) == 64
    assert first_result.suppressed_checks == ("community.readme", "metadata.description")


def test_active_and_expired_exceptions_are_distinguished() -> None:
    hierarchy = PolicyHierarchyConfig.model_validate(
        {
            "exceptions": [
                {
                    "exception_id": "EXC-ACTIVE",
                    "target_selector": "mick/*",
                    "check_ids": ["metadata.description"],
                    "reason": "Active migration",
                    "creator": "mick",
                    "created_at": "2026-08-01T00:00:00Z",
                    "expires_at": "2026-09-01T00:00:00Z",
                },
                {
                    "exception_id": "EXC-EXPIRED",
                    "target_selector": "mick/example",
                    "check_ids": ["community.readme"],
                    "reason": "Old migration",
                    "creator": "mick",
                    "created_at": "2026-07-01T00:00:00Z",
                    "expires_at": "2026-08-01T00:00:00Z",
                },
                {
                    "exception_id": "EXC-OTHER",
                    "target_selector": "other/*",
                    "check_ids": ["metadata.description"],
                    "reason": "Different repository",
                    "creator": "mick",
                    "created_at": "2026-08-01T00:00:00Z",
                    "permanent": True,
                },
                {
                    "exception_id": "EXC-PENDING",
                    "target_selector": "mick/example",
                    "check_ids": ["metadata.homepage"],
                    "reason": "Future migration",
                    "creator": "mick",
                    "created_at": "2026-08-20T00:00:00Z",
                    "expires_at": "2026-09-20T00:00:00Z",
                },
            ]
        }
    )

    resolved = resolve_policy(
        default_config("mick").model_copy(update={"policy": hierarchy}),
        PolicyTarget(repository="Mick/Example", evaluated_at=EVALUATED_AT),
    )

    assert [exception.exception_id for exception in resolved.active_exceptions] == ["EXC-ACTIVE"]
    assert resolved.expired_exception_ids == ("EXC-EXPIRED",)
    assert resolved.pending_exception_ids == ("EXC-PENDING",)
    assert resolved.suppressed_checks == ("metadata.description",)
    assert "community.readme" not in resolved.suppressed_checks


@pytest.mark.parametrize(
    "changes",
    [
        {},
        {"permanent": True, "expires_at": "2026-09-01T00:00:00Z"},
        {"expires_at": "2026-07-01T00:00:00Z"},
        {"created_at": "2026-08-01T00:00:00-05:00", "expires_at": "2026-09-01T00:00:00Z"},
    ],
)
def test_invalid_exception_expiration_is_rejected(changes: dict[str, object]) -> None:
    raw: dict[str, object] = {
        "exception_id": "EXC-001",
        "target_selector": "mick/*",
        "check_ids": ["metadata.description"],
        "reason": "Temporary migration",
        "creator": "mick",
        "created_at": "2026-08-01T00:00:00Z",
    }
    raw.update(changes)

    with pytest.raises(ValidationError):
        PolicyExceptionConfig.model_validate(raw)


@pytest.mark.parametrize(
    "policy",
    [
        {"repository_classes": {"application": {"unknown": True}}},
        {"repositories": {"mick/example": {"safety": {"automatic_merge": "allowed"}}}},
        {"exceptions": [{"exception_id": "EXC-001"}]},
    ],
)
def test_unknown_or_incomplete_policy_fields_are_rejected(policy: dict[str, object]) -> None:
    raw = default_config("mick").model_dump(mode="json")
    raw["policy"] = policy

    with pytest.raises(ValidationError):
        AppConfig.model_validate(raw)


def test_resolved_hash_changes_when_effective_policy_changes() -> None:
    target = PolicyTarget(repository="mick/example", evaluated_at=EVALUATED_AT)
    default_result = resolve_policy(default_config("mick"), target)
    changed_config = default_config("mick").model_copy(update={"readme": ReadmeConfig(validate_links=False)})
    changed_result = resolve_policy(changed_config, target)

    assert default_result.policy_hash != changed_result.policy_hash


def test_metadata_and_community_requirements_follow_policy_precedence() -> None:
    hierarchy = PolicyHierarchyConfig.model_validate(
        {
            "repository_classes": {
                "library": {
                    "metadata": {"minimum_topics": 2},
                    "community": {"security": "optional"},
                }
            },
            "repositories": {"mick/example": {"community": {"security": "required"}}},
        }
    )
    config = default_config("mick").model_copy(update={"policy": hierarchy})

    resolved = resolve_policy(
        config,
        PolicyTarget(
            repository="mick/example",
            repository_class="library",
            evaluated_at=EVALUATED_AT,
        ),
    )

    assert resolved.settings.metadata.minimum_topics == 2
    assert resolved.settings.community.security == "required"
    entries = [entry for entry in resolved.trace if entry.path == "community.security"]
    assert [(entry.source, entry.value) for entry in entries] == [
        (PolicySource.BUILT_IN, "required"),
        (PolicySource.REPOSITORY_CLASS, "optional"),
        (PolicySource.REPOSITORY, "required"),
    ]


def _config_from_fixture(name: str) -> AppConfig:
    raw = yaml.safe_load((FIXTURES / name).read_text(encoding="utf-8"))
    hierarchy = PolicyHierarchyConfig.model_validate(raw)
    return default_config("mick").model_copy(update={"policy": hierarchy})
