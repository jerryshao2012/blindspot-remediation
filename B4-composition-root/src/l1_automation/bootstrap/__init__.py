"""
Composition/bootstrap package.
This package is deliberately small.
The composition root is the ONE place where concrete implementations are
selected and connected to the domain/application services.
Domain components must not import this package.
Dependency direction should remain approximately:
    bootstrap
        ↓
    application/domain
        ↓
    ports
and:
    bootstrap
        ↓
    infrastructure adapters
        ↓
    ports
The domain therefore knows the interfaces it requires, while the composition
root decides which implementation satisfies each interface.
This prevents Azure SDK concerns, model-provider concerns, storage concerns,
and workflow-provider concerns from leaking into the release-gating and
evaluation logic.
"""

