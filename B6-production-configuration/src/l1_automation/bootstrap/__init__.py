"""
Application composition package.
Only bootstrap/composition code should decide which concrete infrastructure
adapters satisfy application/domain ports.
Domain services must not call:
    PlatformSettings.from_environment()
or:
    DefaultAzureCredential()
or:
    BlobServiceClient(...)
inside their constructors.
Those are composition/infrastructure responsibilities.
"""

