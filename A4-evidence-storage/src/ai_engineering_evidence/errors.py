"""
Typed failures for immutable evidence storage.

Integrity failures are intentionally distinguished from ordinary I/O failures.

For an assurance platform:

    "I could not read the object"

and

    "I read the object and its digest changed"

are materially different events.
"""


class EvidenceStorageError(Exception):
    """Base class for expected evidence-storage failures."""


class EvidenceConfigurationError(EvidenceStorageError):
    """Evidence storage configuration is invalid."""


class EvidenceObjectNotFoundError(EvidenceStorageError):
    """A referenced immutable object does not exist."""


class EvidenceIntegrityError(EvidenceStorageError):
    """Stored bytes do not match their expected digest."""


class ManifestAlreadyExistsError(EvidenceStorageError):
    """
    A manifest already exists for this run ID with different content.

    The correct response is never to overwrite it.
    """


class ManifestNotFoundError(EvidenceStorageError):
    """No immutable manifest exists for the requested run."""


class ManifestValidationError(EvidenceStorageError):
    """Manifest content is internally inconsistent."""


class UnsupportedEvidenceLocationError(EvidenceStorageError):
    """The current backend cannot ingest the requested artifact location."""
