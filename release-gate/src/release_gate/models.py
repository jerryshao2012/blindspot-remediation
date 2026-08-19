"""Immutable configuration models for the v1 release-gate contract."""

from __future__ import annotations

import math
import posixpath
import re
from collections.abc import Iterator, Mapping
from enum import StrEnum
from typing import Annotated, Any, TypeVar

from pathspec import PathSpec
from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    model_validator,
)


class FrozenDict(dict[str, str]):
    """A JSON-serializable mapping that rejects mutation."""

    def __setitem__(self, key: str, value: str) -> None:
        del key, value
        raise TypeError("mapping is immutable")

    def __delitem__(self, key: str) -> None:
        del key
        raise TypeError("mapping is immutable")

    def clear(self) -> None:
        raise TypeError("mapping is immutable")

    def pop(self, key: str, default: str | None = None) -> str:  # type: ignore[override]
        del key, default
        raise TypeError("mapping is immutable")

    def popitem(self) -> tuple[str, str]:
        raise TypeError("mapping is immutable")

    def setdefault(self, key: str, default: str = "") -> str:
        del key, default
        raise TypeError("mapping is immutable")

    def update(  # type: ignore[override]
        self, other: Mapping[str, str] | None = None, **kwargs: str
    ) -> None:
        del other, kwargs
        raise TypeError("mapping is immutable")


def _freeze_mapping(value: dict[str, str]) -> FrozenDict:
    return FrozenDict(value)


Environment = Annotated[dict[str, str], AfterValidator(_freeze_mapping)]
Scalar = float | int | str | bool | None


class FrozenModel(BaseModel):
    """Base for immutable, strictly shaped public models."""

    model_config = ConfigDict(extra="forbid", frozen=True, use_enum_values=False)


class PlatformName(StrEnum):
    LINUX = "linux"
    MACOS = "macos"
    WINDOWS = "windows"


class CheckMode(StrEnum):
    CANDIDATE = "candidate"
    DIFFERENTIAL = "differential"


class Severity(StrEnum):
    BLOCKING = "blocking"
    ADVISORY = "advisory"
    INFORMATIONAL = "informational"


class ReportParser(StrEnum):
    JUNIT_XML = "junit-xml"
    COVERAGE_JSON = "coverage-json"
    JSON_METRICS = "json-metrics"


class Comparison(StrEnum):
    CANDIDATE = "candidate"
    BASELINE = "baseline"
    CANDIDATE_MINUS_BASELINE = "candidate-minus-baseline"


class AssertionOperator(StrEnum):
    EQ = "eq"
    NE = "ne"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"


class ExitClasses(FrozenModel):
    """Configured process result classifications."""

    passed: tuple[int, ...] = Field(default=(0,), alias="pass")
    fail: tuple[int, ...] = (1,)
    error: tuple[int, ...] = ()

    model_config = ConfigDict(
        extra="forbid", frozen=True, populate_by_name=True, serialize_by_alias=True
    )

    @model_validator(mode="after")
    def validate_classes(self) -> ExitClasses:
        groups = {
            "pass": set(self.passed),
            "fail": set(self.fail),
            "error": set(self.error),
        }
        if groups["pass"] & groups["fail"] or groups["pass"] & groups["error"]:
            raise ValueError("exit class values overlap")
        if groups["fail"] & groups["error"]:
            raise ValueError("exit class values overlap")
        if any(code < 0 for code in (*self.passed, *self.fail)):
            raise ValueError("negative exit codes are valid only in the error class")
        return self


class CommandOverride(FrozenModel):
    argv: tuple[str, ...] | None = None
    cwd: str | None = None
    timeout: int | None = None
    environment: Environment | None = None
    inherit_environment: tuple[str, ...] | None = None
    exit_classes: ExitClasses | None = None


class PlatformOverrides(FrozenModel):
    linux: CommandOverride | None = None
    macos: CommandOverride | None = None
    windows: CommandOverride | None = None

    def for_platform(self, platform: PlatformName) -> CommandOverride | None:
        return {
            PlatformName.LINUX: self.linux,
            PlatformName.MACOS: self.macos,
            PlatformName.WINDOWS: self.windows,
        }[platform]


class ResolvedCommand(FrozenModel):
    argv: tuple[str, ...]
    cwd: str
    timeout: int
    environment: Environment
    inherit_environment: tuple[str, ...]
    exit_classes: ExitClasses


class CommandSpec(FrozenModel):
    argv: tuple[str, ...]
    cwd: str = "."
    timeout: int = 600
    environment: Environment = Field(default_factory=FrozenDict)
    inherit_environment: tuple[str, ...] = ()
    exit_classes: ExitClasses = Field(default_factory=ExitClasses)
    platform: PlatformOverrides | None = None

    def resolve(self, platform: PlatformName) -> ResolvedCommand:
        override = self.platform.for_platform(platform) if self.platform else None
        argv = override.argv if override and override.argv is not None else self.argv
        cwd = override.cwd if override and override.cwd is not None else self.cwd
        timeout = (
            override.timeout
            if override and override.timeout is not None
            else self.timeout
        )
        exit_classes = (
            override.exit_classes
            if override and override.exit_classes is not None
            else self.exit_classes
        )
        inherited = (
            override.inherit_environment
            if override and override.inherit_environment is not None
            else self.inherit_environment
        )
        literal = _merge_environment(
            self.environment,
            override.environment if override else None,
            platform,
        )
        if platform is PlatformName.WINDOWS:
            inherited = tuple(name.upper() for name in inherited)
        return ResolvedCommand(
            argv=argv,
            cwd=cwd,
            timeout=timeout,
            environment=literal,
            inherit_environment=inherited,
            exit_classes=exit_classes,
        )


class PrepareStep(CommandSpec):
    id: str


class Report(FrozenModel):
    id: str
    parser: ReportParser
    path: str
    required: bool = True
    max_bytes: int | None = None


class Assertion(FrozenModel):
    report: str
    metric: str
    comparison: Comparison
    operator: AssertionOperator
    value: Scalar

    @model_validator(mode="after")
    def normalize_number(self) -> Assertion:
        if isinstance(self.value, float):
            if not math.isfinite(self.value):
                raise ValueError("assertion values must be finite")
            if self.value == 0.0 and math.copysign(1.0, self.value) < 0:
                object.__setattr__(self, "value", 0.0)
        return self


class Check(CommandSpec):
    id: str
    mode: CheckMode
    severity: Severity
    reports: tuple[Report, ...] = ()
    assertions: tuple[Assertion, ...] = ()


class Scope(FrozenModel):
    allowed_paths: tuple[str, ...]
    forbidden_paths: tuple[str, ...] = ()
    review_required_paths: tuple[str, ...] = ()

    _review_spec: PathSpec[Any] = PrivateAttr()

    def model_post_init(self, context: Any, /) -> None:
        del context
        object.__setattr__(
            self,
            "_review_spec",
            PathSpec.from_lines("gitwildmatch", self.review_required_paths),
        )

    def requires_review(self, path: str) -> bool:
        return self._review_spec.match_file(path)


class Limits(FrozenModel):
    stream_bytes: int = 1_048_576
    report_bytes: int = 5_242_880
    total_bytes: int = 209_715_200


class GateConfig(FrozenModel):
    version: int
    scope: Scope
    prepare: tuple[PrepareStep, ...] = ()
    limits: Limits = Field(default_factory=Limits)
    checks: tuple[Check, ...]

    @property
    def requires_base_workspace(self) -> bool:
        return any(check.mode is CheckMode.DIFFERENTIAL for check in self.checks)

    @model_validator(mode="after")
    def validate_semantics(self) -> GateConfig:
        _validate_unique_ids(self)
        _validate_assertions(self)
        _validate_report_limits(self)
        _validate_commands(self)
        return self


def _merge_environment(
    common: Mapping[str, str],
    override: Mapping[str, str] | None,
    platform: PlatformName,
) -> FrozenDict:
    if platform is not PlatformName.WINDOWS:
        merged = dict(common)
        if override:
            merged.update(override)
        return FrozenDict(merged)

    merged_windows = {key.upper(): value for key, value in common.items()}
    if override:
        merged_windows.update({key.upper(): value for key, value in override.items()})
    return FrozenDict(merged_windows)


def _validate_unique_ids(config: GateConfig) -> None:
    seen: set[str] = set()
    controls: tuple[PrepareStep | Check, ...] = (*config.prepare, *config.checks)
    for control in controls:
        if control.id in seen:
            raise ValueError(f"duplicate control id: {control.id}")
        seen.add(control.id)
    for check in config.checks:
        report_ids: set[str] = set()
        for report in check.reports:
            if report.id in report_ids:
                raise ValueError(f"duplicate report id {report.id} in check {check.id}")
            report_ids.add(report.id)


def _validate_assertions(config: GateConfig) -> None:
    for check in config.checks:
        report_ids = {report.id for report in check.reports}
        for assertion in check.assertions:
            if assertion.report not in report_ids:
                raise ValueError(
                    f"assertion in {check.id} references undeclared report "
                    f"{assertion.report}"
                )
            if (
                check.mode is CheckMode.CANDIDATE
                and assertion.comparison is not Comparison.CANDIDATE
            ):
                raise ValueError(
                    f"{assertion.comparison.value} comparison requires a "
                    "differential check"
                )


def _validate_report_limits(config: GateConfig) -> None:
    for check in config.checks:
        for report in check.reports:
            if (
                report.max_bytes is not None
                and report.max_bytes > config.limits.report_bytes
            ):
                raise ValueError(
                    f"report {check.id}/{report.id} max_bytes exceeds "
                    "limits.report_bytes"
                )


def _validate_commands(config: GateConfig) -> None:
    for control in (*config.prepare, *config.checks):
        _validate_one_command(control, config.scope, None)
        if control.platform:
            for platform in PlatformName:
                override = control.platform.for_platform(platform)
                if override:
                    _validate_override_environment(override, platform)
                    resolved = control.resolve(platform)
                    _validate_argv(resolved.argv)
                    _validate_launcher(resolved.argv[0], config.scope)
        _validate_common_environment(control)


def _validate_one_command(
    command: CommandSpec, scope: Scope, platform: PlatformName | None
) -> None:
    del platform
    _validate_argv(command.argv)
    _validate_launcher(command.argv[0], scope)


def _validate_argv(argv: tuple[str, ...]) -> None:
    shell_tokens = {"&&", "||", "|", ";", ">", ">>", "<", "<<"}
    for argument in argv:
        if (
            argument in shell_tokens
            or re.fullmatch(r"\d*(?:>|>>|<|<<)", argument)
            or "$(" in argument
            or "`" in argument
        ):
            raise ValueError(f"shell syntax is not allowed in argv: {argument!r}")


def _validate_launcher(argv0: str, scope: Scope) -> None:
    portable = argv0.replace("\\", "/")
    if re.match(r"^[A-Za-z]:", portable) or portable.startswith("/"):
        return
    if "/" not in portable:
        return
    normalized = posixpath.normpath(portable.removeprefix("./"))
    if normalized == ".." or normalized.startswith("../"):
        raise ValueError("repository launcher cannot escape the clone")
    if not scope.requires_review(normalized):
        raise ValueError(
            f"repository-local launcher {normalized!r} must match "
            "scope.review_required_paths"
        )


def _validate_common_environment(command: CommandSpec) -> None:
    for platform in PlatformName:
        _validate_environment_names(
            command.environment,
            command.inherit_environment,
            platform,
        )


def _validate_override_environment(
    override: CommandOverride, platform: PlatformName
) -> None:
    _validate_environment_names(
        override.environment or FrozenDict(),
        override.inherit_environment or (),
        platform,
    )


def _validate_environment_names(
    literal: Mapping[str, str], inherited: tuple[str, ...], platform: PlatformName
) -> None:
    names = [*literal, *inherited]
    if platform is PlatformName.WINDOWS:
        for collection in (tuple(literal), inherited):
            folded = [name.upper() for name in collection]
            if len(folded) != len(set(folded)):
                raise ValueError("Windows environment contains case-colliding names")
    for name in names:
        comparison = name.upper() if platform is PlatformName.WINDOWS else name
        reserved = {"HOME", "RELEASE_GATE_"}
        if platform in (PlatformName.LINUX, PlatformName.MACOS):
            reserved.add("TMPDIR")
        else:
            reserved.update({"USERPROFILE", "HOMEDRIVE", "HOMEPATH", "TEMP", "TMP"})
        if comparison in reserved or comparison.startswith("RELEASE_GATE_"):
            raise ValueError(f"reserved environment name: {name}")


ModelT = TypeVar("ModelT", bound=FrozenModel)


def iter_commands(config: GateConfig) -> Iterator[PrepareStep | Check]:
    """Yield controls in deterministic configuration order."""

    yield from config.prepare
    yield from config.checks
