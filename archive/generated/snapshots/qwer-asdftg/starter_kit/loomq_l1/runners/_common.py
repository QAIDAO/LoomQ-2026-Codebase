"""SDK-independent helpers shared by LoomQ provider runners."""

from collections.abc import Mapping
from importlib.metadata import PackageNotFoundError, version as distribution_version
import uuid


def sdk_version(value: object) -> str:
    """Return a safe provider SDK version marker without inspecting secrets."""
    return value if type(value) is str and value else "unknown"


def installed_sdk_version(distribution: str, module_version: object) -> str:
    """Prefer installed distribution metadata over optional module attributes."""
    try:
        return sdk_version(distribution_version(distribution))
    except PackageNotFoundError:
        return sdk_version(module_version)


def metadata(target: str, provider: str, sdk: str, version: object) -> dict[str, str]:
    """Build the fixed, credential-safe metadata emitted by every runner."""
    return {
        "target": target,
        "provider": provider,
        "sdk": sdk,
        "sdk_version": sdk_version(version),
    }


def metadata_id(value: object) -> object:
    """Safely obtain an ID from a provider task-metadata object or mapping."""
    if isinstance(value, Mapping):
        return value.get("id")
    return getattr(value, "id", None)


def local_job_id(provider: str, *provider_ids: object) -> str:
    """Prefer a non-empty provider ID, otherwise make a non-mock local UUID ID."""
    for provider_id in provider_ids:
        if type(provider_id) is str and provider_id:
            return provider_id
    return f"{provider}-local-{uuid.uuid4()}"
