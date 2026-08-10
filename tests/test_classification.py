import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

import pytest
from pydantic import ValidationError

from github_account_maintainer.classification import (
    ActivityState,
    ClassificationDecision,
    ClassificationDimension,
    MaintenanceTier,
    OwnershipType,
    ProjectType,
    RepositoryClass,
    RepositoryClassification,
    RepositoryClassificationError,
    RepositoryClassificationEvidence,
    RepositoryKind,
    RepositoryPolicyBindingTarget,
    bind_repository_policy,
    classification_evidence_from_github,
    classify_and_bind_repository,
    classify_repository,
)
from github_account_maintainer.config import PolicyHierarchyConfig, default_config
from github_account_maintainer.models import PolicySource, RepositoryInventoryRecord, RepositoryPermissions
from github_account_maintainer.reporting import render_json, render_policy_binding_markdown

EVALUATED_AT = datetime(2026, 8, 10, 12, tzinfo=UTC)
FIXTURES = Path(__file__).parent / "fixtures" / "github"


def test_github_contract_fixture_creates_excluded_classification_evidence() -> None:
    metadata = cast(
        dict[str, object], json.loads((FIXTURES / "classification-metadata.json").read_text(encoding="utf-8"))
    )
    languages = cast(
        dict[str, object], json.loads((FIXTURES / "classification-languages.json").read_text(encoding="utf-8"))
    )

    evidence = classification_evidence_from_github(metadata, languages)
    classification = classify_repository(_inventory(), evidence, classified_at=EVALUATED_AT)

    assert evidence.repository_id == 101
    assert _value(classification, ClassificationDimension.PROJECT_TYPE) == ProjectType.POWERSHELL
    assert _value(classification, ClassificationDimension.REPOSITORY_CLASS) == RepositoryClass.CLI
    serialized = evidence.model_dump_json()
    assert "PowerShell" not in serialized
    assert "automation" not in serialized


@pytest.mark.parametrize(
    ("metadata_change", "languages", "message"),
    [
        ({"id": True}, {}, "id"),
        ({"owner": {"type": "Bot"}}, {}, "owner type"),
        ({"topics": "invalid"}, {}, "topics"),
        ({"pushed_at": "invalid"}, {}, "push timestamp"),
        ({}, {"Python": -1}, "languages response"),
    ],
)
def test_invalid_github_classification_contract_fails_closed(
    metadata_change: dict[str, object],
    languages: dict[str, object],
    message: str,
) -> None:
    metadata = cast(
        dict[str, object], json.loads((FIXTURES / "classification-metadata.json").read_text(encoding="utf-8"))
    )
    metadata.update(metadata_change)

    with pytest.raises(RepositoryClassificationError, match=message):
        classification_evidence_from_github(metadata, languages)


def test_classifies_active_python_source_from_inventory_and_metadata() -> None:
    classification = classify_repository(
        _inventory(),
        _evidence(
            owner_type="User",
            primary_language="Python",
            languages={"Python": 9_000},
            pushed_at=EVALUATED_AT - timedelta(days=30),
        ),
        classified_at=EVALUATED_AT,
    )

    assert _value(classification, ClassificationDimension.VISIBILITY) == "public"
    assert _value(classification, ClassificationDimension.ACTIVITY) == ActivityState.ACTIVE
    assert _value(classification, ClassificationDimension.REPOSITORY_KIND) == RepositoryKind.SOURCE
    assert _value(classification, ClassificationDimension.OWNERSHIP) == OwnershipType.PERSONAL_ACCOUNT
    assert _value(classification, ClassificationDimension.PROJECT_TYPE) == ProjectType.PYTHON
    assert _value(classification, ClassificationDimension.REPOSITORY_CLASS) == RepositoryClass.APPLICATION
    assert _value(classification, ClassificationDimension.MAINTENANCE_TIER) == MaintenanceTier.ACTIVE
    assert len(classification.classification_hash) == 64
    assert tuple(decision.dimension for decision in classification.decisions) == tuple(ClassificationDimension)


def test_allowlisted_topic_classifies_mcp_service_without_serializing_raw_inputs() -> None:
    evidence = _evidence(
        owner_type="Organization",
        primary_language="Python",
        languages={"Python": 1_000},
        topics=("mcp-server", "private-project-label"),
    )
    classification = classify_repository(_inventory(), evidence, classified_at=EVALUATED_AT)

    assert _value(classification, ClassificationDimension.OWNERSHIP) == OwnershipType.ORGANIZATION
    assert _value(classification, ClassificationDimension.PROJECT_TYPE) == ProjectType.MCP_SERVER
    assert _value(classification, ClassificationDimension.REPOSITORY_CLASS) == RepositoryClass.SERVICE
    assert "mcp-server" not in evidence.model_dump_json()
    assert "private-project-label" not in evidence.model_dump_json()
    assert "Python" not in evidence.model_dump_json()


def test_language_order_does_not_change_mixed_classification_or_hash() -> None:
    first = classify_repository(
        _inventory(),
        _evidence(primary_language="Python", languages={"Python": 600, "TypeScript": 400}),
        classified_at=EVALUATED_AT,
    )
    second = classify_repository(
        _inventory(),
        _evidence(primary_language="Python", languages={"TypeScript": 400, "Python": 600}),
        classified_at=EVALUATED_AT,
    )

    assert _value(first, ClassificationDimension.PROJECT_TYPE) == ProjectType.MIXED
    assert first == second
    assert first.classification_hash == second.classification_hash


def test_empty_archived_repository_has_empty_class_and_legacy_tier() -> None:
    inventory = _inventory(archived=True)
    classification = classify_repository(
        inventory,
        _evidence(archived=True, size_kb=0, pushed_at=None),
        classified_at=EVALUATED_AT,
    )

    assert _value(classification, ClassificationDimension.ACTIVITY) == ActivityState.ARCHIVED
    assert _value(classification, ClassificationDimension.REPOSITORY_KIND) == RepositoryKind.EMPTY
    assert _value(classification, ClassificationDimension.REPOSITORY_CLASS) == RepositoryClass.EMPTY
    assert _value(classification, ClassificationDimension.MAINTENANCE_TIER) == MaintenanceTier.LEGACY


def test_unknown_evidence_is_explicit_with_zero_confidence() -> None:
    classification = classify_repository(
        _inventory(),
        _evidence(primary_language=None, languages={}, owner_type=None, pushed_at=None),
        classified_at=EVALUATED_AT,
    )

    for dimension in (
        ClassificationDimension.ACTIVITY,
        ClassificationDimension.OWNERSHIP,
        ClassificationDimension.PROJECT_TYPE,
    ):
        decision = _decision(classification, dimension)
        assert decision.value == "unknown"
        assert decision.confidence == 0
    assert _value(classification, ClassificationDimension.REPOSITORY_CLASS) == RepositoryClass.UNKNOWN
    assert _value(classification, ClassificationDimension.MAINTENANCE_TIER) == MaintenanceTier.STANDARD


@pytest.mark.parametrize(
    ("inventory_changes", "evidence_changes", "message"),
    [
        ({"repository_id": 2}, {}, "identity"),
        ({"visibility": "private", "private": True}, {}, "visibility"),
        ({"archived": True}, {}, "archived"),
        ({"fork": True}, {}, "fork"),
    ],
)
def test_inventory_and_metadata_mismatch_fails_closed(
    inventory_changes: dict[str, object],
    evidence_changes: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(RepositoryClassificationError, match=message):
        classify_repository(
            _inventory(**inventory_changes),
            _evidence(**evidence_changes),
            classified_at=EVALUATED_AT,
        )


def test_future_push_timestamp_and_non_utc_inputs_fail_closed() -> None:
    with pytest.raises(RepositoryClassificationError, match="after classification"):
        classify_repository(
            _inventory(archived=True),
            _evidence(archived=True, pushed_at=EVALUATED_AT + timedelta(seconds=1)),
            classified_at=EVALUATED_AT,
        )

    with pytest.raises(ValidationError, match="pushed_at"):
        _evidence(pushed_at=datetime(2026, 8, 10, 12))

    with pytest.raises(RepositoryClassificationError, match="classified_at"):
        classify_repository(_inventory(), _evidence(), classified_at=datetime(2026, 8, 10, 12))


def test_binding_uses_class_project_and_repository_policy_precedence() -> None:
    hierarchy = PolicyHierarchyConfig.model_validate(
        {
            "repository_classes": {"library": {"metadata": {"minimum_topics": 2}}},
            "project_types": {"python": {"community": {"security": "optional"}}},
            "repositories": {"example/synthetic": {"metadata": {"minimum_topics": 3}}},
        }
    )
    config = default_config("example").model_copy(update={"policy": hierarchy})
    classification = classify_repository(
        _inventory(),
        _evidence(primary_language="Python", topics=("library",)),
        classified_at=EVALUATED_AT,
    )
    bound = bind_repository_policy(config, _target(), classification, evaluated_at=EVALUATED_AT)

    assert bound.record.repository_class == RepositoryClass.LIBRARY
    assert bound.record.project_type == ProjectType.PYTHON
    assert bound.resolved_policy.settings.metadata.minimum_topics == 3
    assert bound.resolved_policy.settings.community.security == "optional"
    assert bound.record.policy_hash == bound.resolved_policy.policy_hash
    assert bound.record.policy_sources == (
        PolicySource.BUILT_IN,
        PolicySource.REPOSITORY_CLASS,
        PolicySource.PROJECT_TYPE,
        PolicySource.REPOSITORY,
    )


def test_classify_and_bind_validates_target_identity() -> None:
    with pytest.raises(RepositoryClassificationError, match="inventory record"):
        classify_and_bind_repository(
            default_config("example"),
            _target(repository_id=2),
            _inventory(),
            _evidence(),
            evaluated_at=EVALUATED_AT,
        )

    classification = classify_repository(_inventory(), _evidence(), classified_at=EVALUATED_AT)
    with pytest.raises(RepositoryClassificationError, match="classification"):
        bind_repository_policy(
            default_config("example"),
            _target(repository_id=2),
            classification,
            evaluated_at=EVALUATED_AT,
        )

    with pytest.raises(RepositoryClassificationError, match="timestamp"):
        bind_repository_policy(
            default_config("example"),
            _target(),
            classification,
            evaluated_at=EVALUATED_AT + timedelta(seconds=1),
        )


def test_classification_rejects_tampered_values_and_hashes() -> None:
    classification = classify_repository(_inventory(), _evidence(), classified_at=EVALUATED_AT)
    raw = classification.model_dump(mode="json")
    raw["classification_hash"] = "f" * 64

    with pytest.raises(ValidationError, match="hash"):
        type(classification).model_validate(raw)

    raw = classification.model_dump(mode="json")
    raw["decisions"][0]["value"] = "secret"
    raw["classification_hash"] = "f" * 64

    with pytest.raises(ValidationError, match="canonical vocabulary"):
        type(classification).model_validate(raw)

    bound = bind_repository_policy(
        default_config("example"),
        _target(),
        classification,
        evaluated_at=EVALUATED_AT,
    )
    raw_binding = bound.record.model_dump(mode="json")
    raw_binding["repository_class"] = "service"

    with pytest.raises(ValidationError, match="repository class"):
        type(bound.record).model_validate(raw_binding)


def test_binding_renderers_are_schema_versioned_and_privacy_safe() -> None:
    inventory = _inventory(display_name="nonpublic-repository:101", visibility="private", private=True)
    evidence = _evidence(
        visibility="private",
        primary_language="PowerShell",
        languages={"PowerShell": 500},
        topics=("private-customer-name",),
    )
    bound = classify_and_bind_repository(
        default_config("example"),
        _target(),
        inventory,
        evidence,
        evaluated_at=EVALUATED_AT,
    )

    json_output = render_json(bound.record)
    markdown_output = render_policy_binding_markdown(bound.record)

    assert '"schema_version": "1.0"' in json_output
    assert "nonpublic-repository:101" in json_output
    assert "example/synthetic" not in json_output
    assert "private-customer-name" not in json_output
    assert "PowerShell" not in json_output
    assert "# GitHub Repository Classification and Policy Binding" in markdown_output
    assert "`project_type`: `powershell`" in markdown_output


def _inventory(**changes: object) -> RepositoryInventoryRecord:
    values: dict[str, object] = {
        "repository_id": 101,
        "node_id": "R_101",
        "display_name": "example/synthetic",
        "private": False,
        "visibility": "public",
        "archived": False,
        "fork": False,
        "permissions": RepositoryPermissions(admin=True, pull=True),
    }
    values.update(changes)
    return RepositoryInventoryRecord.model_validate(values)


def _evidence(**changes: object) -> RepositoryClassificationEvidence:
    values: dict[str, object] = {
        "repository_id": 101,
        "visibility": "public",
        "archived": False,
        "fork": False,
        "owner_type": "User",
        "size_kb": 10,
        "primary_language": "Python",
        "languages": {"Python": 1_000},
        "pushed_at": EVALUATED_AT - timedelta(days=30),
    }
    values.update(changes)
    return RepositoryClassificationEvidence.model_validate(values)


def _target(**changes: object) -> RepositoryPolicyBindingTarget:
    values: dict[str, object] = {"repository_id": 101, "api_name": "example/synthetic"}
    values.update(changes)
    return RepositoryPolicyBindingTarget.model_validate(values)


def _decision(
    classification: RepositoryClassification,
    dimension: ClassificationDimension,
) -> ClassificationDecision:
    return next(decision for decision in classification.decisions if decision.dimension is dimension)


def _value(classification: RepositoryClassification, dimension: ClassificationDimension) -> str:
    return _decision(classification, dimension).value
