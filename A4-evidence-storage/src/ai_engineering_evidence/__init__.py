"""
Immutable evidence storage for the AI engineering platform.

The public API deliberately exposes three concepts:

EvidenceStore
    Stores and retrieves immutable bytes.

EvidenceRecorder
    Converts engineering-run outputs into an immutable RunManifest.

ManifestVerifier
    Independently verifies that a published manifest and all referenced
    evidence remain intact.

The package contains no LLM calls.

Storage integrity is deterministic and must remain deterministic even after
AI-assisted evaluation capabilities are introduced elsewhere in the platform.
"""

from .models import (
    ArtifactManifestEntry,
    EvidenceStorageSettings,
    ManifestVerificationResult,
    RunManifest,
    RunPhase,
)
from .recorder import EvidenceRecorder
from .store import EvidenceStore, LocalContentAddressedEvidenceStore
from .verifier import ManifestVerifier

__all__ = [
    "ArtifactManifestEntry",
    "EvidenceRecorder",
    "EvidenceStorageSettings",
    "EvidenceStore",
    "LocalContentAddressedEvidenceStore",
    "ManifestVerificationResult",
    "ManifestVerifier",
    "RunManifest",
    "RunPhase",
]

__version__ = "0.1.0"
