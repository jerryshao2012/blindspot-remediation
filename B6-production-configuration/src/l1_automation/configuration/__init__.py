"""
Runtime configuration package.
This package owns infrastructure/runtime configuration only.
It must not become the home of release-gate assurance policy.
Examples of values that belong here:
    runtime mode
    Azure resource names
    Azure endpoints
    evidence-storage location
    workflow-system identifiers
Examples of values that DO NOT belong here:
    minimum mutation score
    required evidence categories
    gate PASS threshold
    allowed source paths for X1
    qualification false-release tolerance
Those belong to versioned capability / assurance-policy artifacts.
"""
from .errors import ConfigurationError
from .loader import load_platform_settings
from .models import (
    AzurePocSettings,
    PlatformSettings,
    RuntimeMode,
)
__all__ = [
    "AzurePocSettings",
    "ConfigurationError",
    "PlatformSettings",
    "RuntimeMode",
    "load_platform_settings",
]

