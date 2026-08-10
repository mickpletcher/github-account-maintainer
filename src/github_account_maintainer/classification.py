import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Annotated, Literal, cast

from pydantic import Field, field_validator, model_validator

from github_account_maintainer.config import AppConfig, StrictModel
from github_account_maintainer.models import CoverageState, PolicySource, RepositoryInventoryRecord
from github_account_maintainer.policy import PolicyTarget, ResolvedPolicy, resolve_policy

type JsonObject = dict[str, object]

ACTIVE_WITHIN_DAYS = 180
ABANDONED_AFTER_DAYS = 730


class ClassificationDimension(StrEnum):
    VISIBILITY = "visibility"
    ACTIVITY = "activity"
    REPOSITORY_KIND = "repository_kind"
    OWNERSHIP = "ownership"
    PROJECT_TYPE = "project_type"
    REPOSITORY_CLASS = "repository_class"
    MAINTENANCE_TIER = "maintenance_tier"


class ActivityState(StrEnum):
    ACTIVE = "active"
    DORMANT = "dormant"
    ABANDONED_CANDIDATE = "abandoned_candidate"
    ARCHIVED = "archived"
    UNKNOWN = "unknown"


class RepositoryKind(StrEnum):
    SOURCE = "source"
    FORK = "fork"
    TEMPLATE = "template"
    MIRROR = "mirror"
    EMPTY = "empty"


class OwnershipType(StrEnum):
    PERSONAL_ACCOUNT = "personal_account"
    ORGANIZATION = "organization"
    UNKNOWN = "unknown"


class ProjectType(StrEnum):
    PYTHON = "python"
    POWERSHELL = "powershell"
    NODEJS = "nodejs"
    MCP_SERVER = "mcp_server"
    DOCUMENTATION = "documentation"
    CONFIGURATION = "configuration"
    WEB_APPLICATION = "web_application"
    INFRASTRUCTURE = "infrastructure"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class RepositoryClass(StrEnum):
    APPLICATION = "application"
    LIBRARY = "library"
    CLI = "cli"
    SERVICE = "service"
    DESKTOP_APPLICATION = "desktop_application"
    GITHUB_PAGES = "github_pages"
    INFRASTRUCTURE = "infrastructure"
    DOCUMENTATION = "documentation"
    CONFIGURATION = "configuration"
    EMPTY = "empty"
    UNKNOWN = "unknown"


class MaintenanceTier(StrEnum):
    FLAGSHIP = "flagship"
    ACTIVE = "active"
    STANDARD = "standard"
    EXPERIMENTAL = "experimental"
    LEGACY = "legacy"
    EXEMPT = "exempt"


class ClassificationDecision(StrictModel):
    dimension: ClassificationDimension
    value: str
    confidence: Annotated[float, Field(ge=0, le=1)]
    evidence: tuple[str, ...]

    @field_validator("value")
    @classmethod
    def validate_value(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("classification value must not be empty")
        return normalized


class RepositoryClassificationEvidence(StrictModel):
    repository_id: int
    visibility: Literal["public", "private", "internal"]
    archived: bool
    fork: bool
    owner_type: Literal["User", "Organization"] | None = None
    is_template: bool = False
    mirror: bool = False
    size_kb: Annotated[int, Field(ge=0)]
    primary_language: str | None = Field(default=None, exclude=True, repr=False)
    languages: dict[str, Annotated[int, Field(ge=0)]] = Field(default={}, exclude=True, repr=False)
    topics: tuple[str, ...] = Field(default=(), exclude=True, repr=False)
    has_pages: bool = False
    pushed_at: datetime | None = None

    @field_validator("primary_language")
    @classmethod
    def validate_primary_language(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("primary_language must not be empty")
        return normalized

    @field_validator("languages")
    @classmethod
    def validate_languages(cls, value: dict[str, int]) -> dict[str, int]:
        if any(not language.strip() for language in value):
            raise ValueError("language names must not be empty")
        return value

    @field_validator("topics")
    @classmethod
    def validate_topics(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(topic.strip() for topic in value)
        if any(not topic for topic in normalized):
            raise ValueError("topics must not be empty")
        return normalized

    @field_validator("pushed_at")
    @classmethod
    def validate_pushed_at(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() != timedelta(0):
            raise ValueError("pushed_at must use RFC 3339 UTC")
        return value


class RepositoryClassification(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    repository_id: int
    repository_display: str
    classified_at: datetime
    classification_hash: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    coverage_state: Literal[CoverageState.AUDITED] = CoverageState.AUDITED
    decisions: tuple[ClassificationDecision, ...]

    @field_validator("classified_at")
    @classmethod
    def validate_classified_at(cls, value: datetime) -> datetime:
        if value.utcoffset() != timedelta(0):
            raise ValueError("classified_at must use RFC 3339 UTC")
        return value

    @model_validator(mode="after")
    def validate_dimensions(self) -> "RepositoryClassification":
        dimensions = tuple(decision.dimension for decision in self.decisions)
        if dimensions != tuple(ClassificationDimension):
            raise ValueError("classification decisions must contain every dimension in canonical order")
        allowed_values = {
            ClassificationDimension.VISIBILITY: {"public", "private", "internal"},
            ClassificationDimension.ACTIVITY: {value.value for value in ActivityState},
            ClassificationDimension.REPOSITORY_KIND: {value.value for value in RepositoryKind},
            ClassificationDimension.OWNERSHIP: {value.value for value in OwnershipType},
            ClassificationDimension.PROJECT_TYPE: {value.value for value in ProjectType},
            ClassificationDimension.REPOSITORY_CLASS: {value.value for value in RepositoryClass},
            ClassificationDimension.MAINTENANCE_TIER: {value.value for value in MaintenanceTier},
        }
        if any(decision.value not in allowed_values[decision.dimension] for decision in self.decisions):
            raise ValueError("classification decision used a value outside the canonical vocabulary")
        if self.classification_hash != _classification_hash(self.repository_id, self.decisions):
            raise ValueError("classification hash did not match the classification decisions")
        return self

    def value_for(self, dimension: ClassificationDimension) -> str:
        return next(decision.value for decision in self.decisions if decision.dimension is dimension)


class RepositoryPolicyBindingTarget(StrictModel):
    repository_id: int
    api_name: Annotated[str, Field(pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")]

    @field_validator("api_name")
    @classmethod
    def validate_api_name(cls, value: str) -> str:
        owner, repository = value.split("/", 1)
        if owner in {".", ".."} or repository in {".", ".."}:
            raise ValueError("api_name must contain literal GitHub owner and repository names")
        return value


class RepositoryPolicyBindingRecord(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    repository_id: int
    repository_display: str
    classification: RepositoryClassification
    repository_class: str
    project_type: str
    policy_hash: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    policy_sources: tuple[PolicySource, ...]
    bound_at: datetime

    @field_validator("bound_at")
    @classmethod
    def validate_bound_at(cls, value: datetime) -> datetime:
        if value.utcoffset() != timedelta(0):
            raise ValueError("bound_at must use RFC 3339 UTC")
        return value

    @model_validator(mode="after")
    def validate_binding(self) -> "RepositoryPolicyBindingRecord":
        if self.repository_id != self.classification.repository_id:
            raise ValueError("binding repository identity did not match classification")
        if self.repository_display != self.classification.repository_display:
            raise ValueError("binding repository display did not match classification")
        if self.repository_class != self.classification.value_for(ClassificationDimension.REPOSITORY_CLASS):
            raise ValueError("binding repository class did not match classification")
        if self.project_type != self.classification.value_for(ClassificationDimension.PROJECT_TYPE):
            raise ValueError("binding project type did not match classification")
        if self.bound_at != self.classification.classified_at:
            raise ValueError("binding timestamp did not match classification")
        return self


@dataclass(frozen=True)
class BoundRepository:
    record: RepositoryPolicyBindingRecord
    resolved_policy: ResolvedPolicy


class RepositoryClassificationError(ValueError):
    pass


def classification_evidence_from_github(
    metadata: dict[str, object],
    languages: dict[str, object],
) -> RepositoryClassificationEvidence:
    repository_id = metadata.get("id")
    visibility = metadata.get("visibility")
    archived = metadata.get("archived")
    fork = metadata.get("fork")
    owner = metadata.get("owner")
    is_template = metadata.get("is_template")
    mirror_url = metadata.get("mirror_url")
    size_kb = metadata.get("size")
    primary_language = metadata.get("language")
    topics = metadata.get("topics")
    has_pages = metadata.get("has_pages")
    pushed_at = metadata.get("pushed_at")

    if not isinstance(repository_id, int) or isinstance(repository_id, bool):
        raise RepositoryClassificationError("Repository metadata did not contain a valid id")
    if visibility not in {"public", "private", "internal"}:
        raise RepositoryClassificationError("Repository metadata did not contain a valid visibility")
    if not isinstance(archived, bool) or not isinstance(fork, bool):
        raise RepositoryClassificationError("Repository metadata did not contain valid lifecycle state")
    if not isinstance(owner, dict):
        raise RepositoryClassificationError("Repository metadata did not contain a valid owner")
    owner_values = cast(dict[str, object], owner)
    owner_type = owner_values.get("type")
    if owner_type not in {"User", "Organization"}:
        raise RepositoryClassificationError("Repository metadata did not contain a supported owner type")
    if not isinstance(is_template, bool):
        raise RepositoryClassificationError("Repository metadata did not contain a valid template state")
    if mirror_url is not None and (not isinstance(mirror_url, str) or not mirror_url.strip()):
        raise RepositoryClassificationError("Repository metadata did not contain a valid mirror state")
    if not isinstance(size_kb, int) or isinstance(size_kb, bool) or size_kb < 0:
        raise RepositoryClassificationError("Repository metadata did not contain a valid size")
    if primary_language is not None and not isinstance(primary_language, str):
        raise RepositoryClassificationError("Repository metadata did not contain a valid primary language")
    if not isinstance(topics, list) or any(not isinstance(topic, str) for topic in cast(list[object], topics)):
        raise RepositoryClassificationError("Repository metadata did not contain valid topics")
    if not isinstance(has_pages, bool):
        raise RepositoryClassificationError("Repository metadata did not contain a valid Pages state")

    language_bytes: dict[str, int] = {}
    for language, byte_count in languages.items():
        if not language.strip() or not isinstance(byte_count, int) or isinstance(byte_count, bool) or byte_count < 0:
            raise RepositoryClassificationError("Repository languages response was invalid")
        language_bytes[language] = byte_count

    return RepositoryClassificationEvidence(
        repository_id=repository_id,
        visibility=cast(Literal["public", "private", "internal"], visibility),
        archived=archived,
        fork=fork,
        owner_type=cast(Literal["User", "Organization"], owner_type),
        is_template=is_template,
        mirror=mirror_url is not None,
        size_kb=size_kb,
        primary_language=primary_language,
        languages=language_bytes,
        topics=tuple(cast(list[str], topics)),
        has_pages=has_pages,
        pushed_at=_parse_github_timestamp(pushed_at),
    )


def classify_repository(
    inventory: RepositoryInventoryRecord,
    evidence: RepositoryClassificationEvidence,
    *,
    classified_at: datetime,
) -> RepositoryClassification:
    _validate_inventory_evidence(inventory, evidence)
    _validate_utc(classified_at, "classified_at")
    topics = {topic.casefold() for topic in evidence.topics}

    visibility = _decision(
        ClassificationDimension.VISIBILITY,
        evidence.visibility,
        1,
        "visibility confirmed by inventory and repository metadata",
    )
    activity = _classify_activity(evidence, classified_at)
    repository_kind = _classify_repository_kind(evidence)
    ownership = _classify_ownership(evidence)
    project_type = _classify_project_type(evidence, topics)
    repository_class = _classify_repository_class(evidence, topics, repository_kind.value, project_type.value)
    maintenance_tier = _classify_maintenance_tier(activity.value, repository_kind.value)
    decisions = (
        visibility,
        activity,
        repository_kind,
        ownership,
        project_type,
        repository_class,
        maintenance_tier,
    )
    classification_hash = _classification_hash(inventory.repository_id, decisions)
    return RepositoryClassification(
        repository_id=inventory.repository_id,
        repository_display=inventory.display_name,
        classified_at=classified_at,
        classification_hash=classification_hash,
        decisions=decisions,
    )


def bind_repository_policy(
    config: AppConfig,
    target: RepositoryPolicyBindingTarget,
    classification: RepositoryClassification,
    *,
    evaluated_at: datetime,
) -> BoundRepository:
    if target.repository_id != classification.repository_id:
        raise RepositoryClassificationError("Policy target identity did not match the repository classification")
    _validate_utc(evaluated_at, "evaluated_at")
    if classification.classified_at != evaluated_at:
        raise RepositoryClassificationError("Classification timestamp did not match policy evaluation time")
    repository_class = classification.value_for(ClassificationDimension.REPOSITORY_CLASS)
    project_type = classification.value_for(ClassificationDimension.PROJECT_TYPE)
    resolved = resolve_policy(
        config,
        PolicyTarget(
            repository=target.api_name,
            repository_class=repository_class,
            project_type=project_type,
            evaluated_at=evaluated_at,
        ),
    )
    sources = tuple(dict.fromkeys(trace.source for trace in resolved.trace))
    record = RepositoryPolicyBindingRecord(
        repository_id=classification.repository_id,
        repository_display=classification.repository_display,
        classification=classification,
        repository_class=repository_class,
        project_type=project_type,
        policy_hash=resolved.policy_hash,
        policy_sources=sources,
        bound_at=evaluated_at,
    )
    return BoundRepository(record=record, resolved_policy=resolved)


def classify_and_bind_repository(
    config: AppConfig,
    target: RepositoryPolicyBindingTarget,
    inventory: RepositoryInventoryRecord,
    evidence: RepositoryClassificationEvidence,
    *,
    evaluated_at: datetime,
) -> BoundRepository:
    if target.repository_id != inventory.repository_id:
        raise RepositoryClassificationError("Policy target identity did not match the inventory record")
    classification = classify_repository(inventory, evidence, classified_at=evaluated_at)
    return bind_repository_policy(config, target, classification, evaluated_at=evaluated_at)


def _classify_activity(evidence: RepositoryClassificationEvidence, classified_at: datetime) -> ClassificationDecision:
    if evidence.pushed_at is not None and evidence.pushed_at > classified_at:
        raise RepositoryClassificationError("push timestamp cannot be after classification time")
    if evidence.archived:
        return _decision(ClassificationDimension.ACTIVITY, ActivityState.ARCHIVED, 1, "archived state is explicit")
    if evidence.pushed_at is None:
        return _decision(ClassificationDimension.ACTIVITY, ActivityState.UNKNOWN, 0, "push timestamp was unavailable")
    age = classified_at - evidence.pushed_at
    if age <= timedelta(days=ACTIVE_WITHIN_DAYS):
        return _decision(ClassificationDimension.ACTIVITY, ActivityState.ACTIVE, 0.95, "recent push is within 180 days")
    if age <= timedelta(days=ABANDONED_AFTER_DAYS):
        return _decision(
            ClassificationDimension.ACTIVITY, ActivityState.DORMANT, 0.9, "last push is between 181 and 730 days"
        )
    return _decision(
        ClassificationDimension.ACTIVITY,
        ActivityState.ABANDONED_CANDIDATE,
        0.85,
        "last push is older than 730 days",
    )


def _classify_repository_kind(evidence: RepositoryClassificationEvidence) -> ClassificationDecision:
    if evidence.size_kb == 0:
        return _decision(ClassificationDimension.REPOSITORY_KIND, RepositoryKind.EMPTY, 1, "repository size is zero")
    if evidence.mirror:
        return _decision(ClassificationDimension.REPOSITORY_KIND, RepositoryKind.MIRROR, 1, "mirror state is explicit")
    if evidence.is_template:
        return _decision(
            ClassificationDimension.REPOSITORY_KIND, RepositoryKind.TEMPLATE, 1, "template state is explicit"
        )
    if evidence.fork:
        return _decision(ClassificationDimension.REPOSITORY_KIND, RepositoryKind.FORK, 1, "fork state is explicit")
    return _decision(
        ClassificationDimension.REPOSITORY_KIND,
        RepositoryKind.SOURCE,
        1,
        "repository is not empty, mirrored, templated, or forked",
    )


def _classify_ownership(evidence: RepositoryClassificationEvidence) -> ClassificationDecision:
    if evidence.owner_type == "User":
        return _decision(ClassificationDimension.OWNERSHIP, OwnershipType.PERSONAL_ACCOUNT, 1, "owner type is user")
    if evidence.owner_type == "Organization":
        return _decision(ClassificationDimension.OWNERSHIP, OwnershipType.ORGANIZATION, 1, "owner type is organization")
    return _decision(ClassificationDimension.OWNERSHIP, OwnershipType.UNKNOWN, 0, "owner type was unavailable")


def _classify_project_type(
    evidence: RepositoryClassificationEvidence,
    topics: set[str],
) -> ClassificationDecision:
    topic_rules = (
        ({"mcp", "mcp-server", "model-context-protocol"}, ProjectType.MCP_SERVER, "MCP"),
        (
            {"infrastructure", "infrastructure-as-code", "iac", "terraform"},
            ProjectType.INFRASTRUCTURE,
            "infrastructure",
        ),
        ({"documentation", "docs"}, ProjectType.DOCUMENTATION, "documentation"),
        ({"configuration", "dotfiles"}, ProjectType.CONFIGURATION, "configuration"),
        ({"web", "web-app", "web-application"}, ProjectType.WEB_APPLICATION, "web application"),
    )
    for candidates, project_type, label in topic_rules:
        if topics & candidates:
            return _decision(
                ClassificationDimension.PROJECT_TYPE,
                project_type,
                0.95,
                f"matched an allowlisted {label} topic",
            )

    families = _language_family_weights(evidence.languages)
    significant = [family for family, share in families.items() if share >= 0.2]
    if len(significant) >= 2:
        return _decision(
            ClassificationDimension.PROJECT_TYPE,
            ProjectType.MIXED,
            0.9,
            "multiple language families each represent at least 20 percent",
        )
    primary_family = _language_family(evidence.primary_language)
    if primary_family is not None:
        return _decision(
            ClassificationDimension.PROJECT_TYPE,
            primary_family,
            0.85,
            f"primary language matched the {primary_family.value} family",
        )
    return _decision(
        ClassificationDimension.PROJECT_TYPE,
        ProjectType.UNKNOWN,
        0,
        "no recognized project-type evidence was available",
    )


def _classify_repository_class(
    evidence: RepositoryClassificationEvidence,
    topics: set[str],
    repository_kind: str,
    project_type: str,
) -> ClassificationDecision:
    if repository_kind == RepositoryKind.EMPTY:
        return _decision(
            ClassificationDimension.REPOSITORY_CLASS,
            RepositoryClass.EMPTY,
            1,
            "empty repository requires bootstrap classification",
        )
    topic_rules = (
        ({"library", "sdk", "package"}, RepositoryClass.LIBRARY, "library"),
        ({"cli", "command-line", "command-line-tool"}, RepositoryClass.CLI, "CLI"),
        ({"service", "api", "server"}, RepositoryClass.SERVICE, "service"),
        ({"desktop", "desktop-application"}, RepositoryClass.DESKTOP_APPLICATION, "desktop application"),
    )
    for candidates, repository_class, label in topic_rules:
        if topics & candidates:
            return _decision(
                ClassificationDimension.REPOSITORY_CLASS,
                repository_class,
                0.95,
                f"matched an allowlisted {label} topic",
            )
    if evidence.has_pages:
        return _decision(
            ClassificationDimension.REPOSITORY_CLASS, RepositoryClass.GITHUB_PAGES, 0.95, "GitHub Pages is enabled"
        )
    project_map = {
        ProjectType.MCP_SERVER: RepositoryClass.SERVICE,
        ProjectType.INFRASTRUCTURE: RepositoryClass.INFRASTRUCTURE,
        ProjectType.DOCUMENTATION: RepositoryClass.DOCUMENTATION,
        ProjectType.CONFIGURATION: RepositoryClass.CONFIGURATION,
    }
    project = ProjectType(project_type)
    if project in project_map:
        repository_class = project_map[project]
        return _decision(
            ClassificationDimension.REPOSITORY_CLASS,
            repository_class,
            0.85,
            f"repository class follows the {project.value} project type",
        )
    if project is ProjectType.UNKNOWN:
        return _decision(
            ClassificationDimension.REPOSITORY_CLASS,
            RepositoryClass.UNKNOWN,
            0,
            "repository-class evidence was unavailable",
        )
    return _decision(
        ClassificationDimension.REPOSITORY_CLASS,
        RepositoryClass.APPLICATION,
        0.6,
        "nonempty recognized project defaults to application",
    )


def _classify_maintenance_tier(activity: str, repository_kind: str) -> ClassificationDecision:
    activity_state = ActivityState(activity)
    kind = RepositoryKind(repository_kind)
    if activity_state in {ActivityState.ARCHIVED, ActivityState.ABANDONED_CANDIDATE}:
        return _decision(
            ClassificationDimension.MAINTENANCE_TIER,
            MaintenanceTier.LEGACY,
            0.85,
            "lifecycle state indicates legacy maintenance",
        )
    if kind in {RepositoryKind.EMPTY, RepositoryKind.TEMPLATE}:
        return _decision(
            ClassificationDimension.MAINTENANCE_TIER,
            MaintenanceTier.EXPERIMENTAL,
            0.75,
            "repository kind indicates experimental maintenance",
        )
    if activity_state is ActivityState.ACTIVE:
        return _decision(
            ClassificationDimension.MAINTENANCE_TIER,
            MaintenanceTier.ACTIVE,
            0.8,
            "recent activity indicates active maintenance",
        )
    return _decision(
        ClassificationDimension.MAINTENANCE_TIER,
        MaintenanceTier.STANDARD,
        0.7,
        "no explicit flagship, experimental, legacy, or exempt evidence",
    )


def _language_family_weights(languages: dict[str, int]) -> dict[ProjectType, float]:
    totals: dict[ProjectType, int] = {}
    for language, byte_count in languages.items():
        family = _language_family(language)
        if family is not None and byte_count > 0:
            totals[family] = totals.get(family, 0) + byte_count
    total = sum(totals.values())
    if total == 0:
        return {}
    return {family: byte_count / total for family, byte_count in totals.items()}


def _language_family(language: str | None) -> ProjectType | None:
    if language is None:
        return None
    normalized = language.casefold()
    families = {
        ProjectType.PYTHON: {"python", "cython"},
        ProjectType.POWERSHELL: {"powershell"},
        ProjectType.NODEJS: {"javascript", "typescript", "vue", "svelte"},
        ProjectType.WEB_APPLICATION: {"html", "css", "scss", "less"},
        ProjectType.INFRASTRUCTURE: {"hcl", "bicep", "dockerfile"},
        ProjectType.DOCUMENTATION: {"markdown"},
    }
    return next((family for family, names in families.items() if normalized in names), None)


def _decision(
    dimension: ClassificationDimension,
    value: StrEnum | str,
    confidence: float,
    evidence: str,
) -> ClassificationDecision:
    return ClassificationDecision(
        dimension=dimension,
        value=value.value if isinstance(value, StrEnum) else value,
        confidence=confidence,
        evidence=(evidence,),
    )


def _classification_hash(repository_id: int, decisions: tuple[ClassificationDecision, ...]) -> str:
    canonical: JsonObject = {
        "schema_version": "1.0",
        "repository_id": repository_id,
        "decisions": [cast(object, decision.model_dump(mode="json")) for decision in decisions],
    }
    encoded = json.dumps(canonical, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def _validate_inventory_evidence(
    inventory: RepositoryInventoryRecord,
    evidence: RepositoryClassificationEvidence,
) -> None:
    if inventory.repository_id != evidence.repository_id:
        raise RepositoryClassificationError("Classification evidence identity did not match inventory")
    comparisons = (
        ("visibility", inventory.visibility, evidence.visibility),
        ("archived", inventory.archived, evidence.archived),
        ("fork", inventory.fork, evidence.fork),
    )
    for field, inventory_value, evidence_value in comparisons:
        if inventory_value != evidence_value:
            raise RepositoryClassificationError(f"Classification evidence {field} did not match inventory")


def _validate_utc(value: datetime, field: str) -> None:
    if value.utcoffset() != timedelta(0):
        raise RepositoryClassificationError(f"{field} must use RFC 3339 UTC")


def _parse_github_timestamp(value: object) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise RepositoryClassificationError("Repository metadata did not contain a valid push timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise RepositoryClassificationError("Repository metadata did not contain a valid push timestamp") from None
    _validate_utc(parsed, "pushed_at")
    return parsed
