"""
Persistence abstraction for Component 11.

The POC includes an in-memory repository.

A production implementation can use:

    Git-backed approved specifications
    Azure Blob Storage
    a metadata database
    or another governed configuration store

without changing the registry domain service.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .models import RegisteredSpecification


class SpecificationRepositoryPort(ABC):

    @abstractmethod
    def get(
        self,
        *,
        task_type: str,
        version: str,
    ) -> RegisteredSpecification | None:
        raise NotImplementedError(
            "SpecificationRepositoryPort.get must be implemented."
        )

    @abstractmethod
    def put(
        self,
        specification: RegisteredSpecification,
    ) -> None:
        raise NotImplementedError(
            "SpecificationRepositoryPort.put must be implemented."
        )

    @abstractmethod
    def list_versions(
        self,
        *,
        task_type: str,
    ) -> tuple[RegisteredSpecification, ...]:
        raise NotImplementedError(
            "SpecificationRepositoryPort.list_versions must be implemented."
        )


class InMemorySpecificationRepository(
    SpecificationRepositoryPort
):
    """
    Fully functional repository for POC execution and unit tests.

    It deliberately refuses overwrite.

    Published task specifications are immutable.
    A changed specification requires a new version.
    """

    def __init__(self) -> None:
        self._items: dict[
            tuple[str, str],
            RegisteredSpecification,
        ] = {}

    def get(
        self,
        *,
        task_type: str,
        version: str,
    ) -> RegisteredSpecification | None:
        return self._items.get((task_type, version))

    def put(
        self,
        specification: RegisteredSpecification,
    ) -> None:
        key = (
            specification.specification.task_type,
            specification.specification.version,
        )

        if key in self._items:
            raise ValueError(
                f"Immutable specification already exists: {key!r}"
            )

        self._items[key] = specification

    def list_versions(
        self,
        *,
        task_type: str,
    ) -> tuple[RegisteredSpecification, ...]:
        return tuple(
            item
            for (stored_task_type, _), item in self._items.items()
            if stored_task_type == task_type
        )
