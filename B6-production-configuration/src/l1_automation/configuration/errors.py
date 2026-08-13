"""
Typed configuration errors.
Configuration failure is an infrastructure/startup concern.
It should not be converted into:
    GateOutcome.FAIL
because a missing Azure resource name says nothing about whether a candidate
patch is technically correct.
"""
class ConfigurationError(RuntimeError):
    """
    Raised when runtime configuration is missing, malformed, contradictory,
    or inappropriate for the selected runtime mode.
    """

