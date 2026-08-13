"""
Central constants for contract validation.

These are engineering defaults, not claims of universal correctness. They are
kept in one module so developers can review and change them deliberately.

Changing a validation constant can alter which records the platform accepts.
Such a change should therefore result in a package-version increment and should
be tested against previously stored contracts.
"""

from typing import Final

# Contract and schema identity.
CONTRACT_PACKAGE_VERSION: Final[str] = "0.1.0"
JSON_SCHEMA_DIALECT: Final[str] = "https://json-schema.org/draft/2020-12/schema"

# Defensive size limits. The contracts should contain references to large
# artifacts, not entire source trees, prompts, traces, or test suites.
MAX_IDENTIFIER_LENGTH: Final[int] = 128
MAX_SHORT_TEXT_LENGTH: Final[int] = 512
MAX_DESCRIPTION_LENGTH: Final[int] = 20_000
MAX_REASON_LENGTH: Final[int] = 4_000
MAX_METADATA_ENTRIES: Final[int] = 200
MAX_METADATA_KEY_LENGTH: Final[int] = 128
MAX_METADATA_VALUE_LENGTH: Final[int] = 2_000
MAX_LIST_ITEMS: Final[int] = 10_000

# Budget ceilings protect against accidental use of absurd values. They do not
# authorize this level of consumption; each task package should set much lower
# limits appropriate to its task type and risk tier.
MAX_LLM_CALLS: Final[int] = 10_000
MAX_TOKEN_BUDGET: Final[int] = 100_000_000
MAX_TOOL_CALLS: Final[int] = 1_000_000
MAX_ITERATIONS: Final[int] = 100_000
MAX_RUNTIME_SECONDS: Final[int] = 604_800  # Seven days.
MAX_ESTIMATED_COST: Final[float] = 1_000_000.0

# Git object IDs may be SHA-1 (40 hexadecimal characters) or SHA-256
# (64 hexadecimal characters), depending on repository configuration.
GIT_COMMIT_PATTERN: Final[str] = r"^(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})$"

# Identifiers are intentionally conservative because they appear in storage
# paths, logs, pipeline variables, and URLs.
SAFE_IDENTIFIER_PATTERN: Final[str] = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"

# Semantic versions accepted by this POC. This handles normal versions such as
# 1.2.3, 1.2.3-rc.1, and 1.2.3+build.5.
SEMANTIC_VERSION_PATTERN: Final[str] = (
    r"^(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)
