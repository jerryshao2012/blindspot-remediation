"""
Primary service for Component 11.

The registry has two important operations:

    register()

and:

    resolve()

Registration validates and fingerprints a task specification.

Resolution returns an immutable approved contract that Component 9 can bind
to an engineering run.
"""

from __future__ import annotations

from .errors import (
    DuplicateSpecificationError,
    SpecificationIntegrityError,
    SpecificationNotApprovedError,
    SpecificationNotFoundError,
)
from .hashing import specification_hash
from .models import (
    RegisteredSpecification,
    ResolvedTaskContract,
    SpecificationStatus,
    TaskSpecification,
)
from .repository import SpecificationRepositoryPort
from .validation import TaskSpecificationValidator


class TaskSpecificationRegistry:
    """
    Deterministic authority for engineering task capability definitions.
    """

    def __init__(
        self,
        *,
        repository: SpecificationRepositoryPort,
        validator: TaskSpecificationValidator | None = None,
    ) -> None:
        self._repository = repository
        self._validator = (
            validator
            or TaskSpecificationValidator()
        )

    def register(
        self,
        specification: TaskSpecification,
    ) -> RegisteredSpecification:
        """
        Register a new immutable specification version.

        Existing versions cannot be edited in place.
        """

        existing = self._repository.get(
            task_type=specification.task_type,
            version=specification.version,
        )

        if existing is not None:
            raise DuplicateSpecificationError(
                "Specification already exists: "
                f"{specification.task_type}@{specification.version}"
            )

        self._validator.validate(specification)

        digest = specification_hash(specification)

        registered = RegisteredSpecification(
            specification=specification,
            specification_sha256=digest,
        )

        self._repository.put(registered)

        return registered

    def resolve(
        self,
        *,
        task_type: str,
        version: str,
        require_approved: bool = True,
    ) -> ResolvedTaskContract:
        """
        Resolve the exact contract for an engineering run.

        Component 9 should normally call this once at run creation and persist
        the resulting specification digest with the run.
        """

        registered = self._repository.get(
            task_type=task_type,
            version=version,
        )

        if registered is None:
            raise SpecificationNotFoundError(
                f"Unknown specification: {task_type}@{version}"
            )

        actual_digest = specification_hash(
            registered.specification
        )

        if actual_digest != registered.specification_sha256:
            raise SpecificationIntegrityError(
                "Stored specification failed content-integrity validation."
            )

        if (
            require_approved
            and registered.specification.status
            != SpecificationStatus.APPROVED
        ):
            raise SpecificationNotApprovedError(
                "Task capability is not approved for production execution: "
                f"{task_type}@{version}"
            )

        self._validator.validate(
            registered.specification
        )

        return ResolvedTaskContract(
            task_type=task_type,
            version=version,
            specification_sha256=actual_digest,
            specification=registered.specification,
        )

    def list_versions(
        self,
        *,
        task_type: str,
    ) -> tuple[RegisteredSpecification, ...]:
        return self._repository.list_versions(
            task_type=task_type
        )
