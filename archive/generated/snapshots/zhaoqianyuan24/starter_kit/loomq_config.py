import json
import os
from pathlib import Path
from typing import Any, Dict


DEFAULT_CONFIG = {
    "llm_base_url": "",
    "llm_api_key": "",
    "llm_model": "",
    "default_target": "originq",
    "default_shots": 1024,
}


def get_config_dir() -> Path:
    """
    Return LoomQ's user configuration directory.

    Linux:
        ~/.config/loomq/

    If XDG_CONFIG_HOME is set:
        $XDG_CONFIG_HOME/loomq/
    """

    xdg_config_home = os.getenv(
        "XDG_CONFIG_HOME"
    )

    if xdg_config_home:
        root = Path(
            xdg_config_home
        ).expanduser()
    else:
        root = (
            Path.home()
            / ".config"
        )

    return (
        root
        / "loomq"
    )


def get_config_path() -> Path:
    return (
        get_config_dir()
        / "config.json"
    )


def load_config() -> Dict[str, Any]:
    """
    Load user config.

    Missing config is not an error.
    """

    config = dict(
        DEFAULT_CONFIG
    )

    path = get_config_path()

    if not path.exists():
        return config

    try:
        with path.open(
            "r",
            encoding="utf-8",
        ) as handle:
            loaded = json.load(
                handle
            )

    except Exception as exc:
        raise RuntimeError(
            f"Failed to read LoomQ config "
            f"from {path}: {exc}"
        ) from exc

    if not isinstance(
        loaded,
        dict,
    ):
        raise RuntimeError(
            f"Invalid LoomQ config: "
            f"{path} must contain a JSON object."
        )

    config.update(
        loaded
    )

    return config


def save_config(
    config: Dict[str, Any],
):
    """
    Save config with user-only permissions
    whenever supported by the operating system.
    """

    directory = get_config_dir()

    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    path = get_config_path()

    temp_path = (
        path.with_suffix(
            ".tmp"
        )
    )

    with temp_path.open(
        "w",
        encoding="utf-8",
    ) as handle:
        json.dump(
            config,
            handle,
            ensure_ascii=False,
            indent=2,
        )

        handle.write("\n")

    try:
        os.chmod(
            temp_path,
            0o600,
        )
    except OSError:
        pass

    temp_path.replace(
        path
    )

    try:
        os.chmod(
            path,
            0o600,
        )
    except OSError:
        pass


def get_llm_base_url() -> str:
    """
    Environment variables always override
    the local LoomQ config.
    """

    env_value = os.getenv(
        "LOOMQ_LLM_BASE_URL"
    )

    if env_value:
        return env_value

    return str(
        load_config().get(
            "llm_base_url",
            "",
        )
    )


def get_llm_api_key() -> str:

    env_value = os.getenv(
        "LOOMQ_LLM_API_KEY"
    )

    if env_value:
        return env_value

    return str(
        load_config().get(
            "llm_api_key",
            "",
        )
    )


def get_llm_model() -> str:

    env_value = os.getenv(
        "LOOMQ_LLM_MODEL"
    )

    if env_value:
        return env_value

    return str(
        load_config().get(
            "llm_model",
            "",
        )
    )


def get_default_target() -> str:

    target = str(
        load_config().get(
            "default_target",
            "originq",
        )
    ).lower()

    if target not in {
        "spinq",
        "originq",
        "braket",
    }:
        return "originq"

    return target


def get_default_shots() -> int:

    value = load_config().get(
        "default_shots",
        1024,
    )

    try:
        shots = int(
            value
        )
    except Exception:
        return 1024

    if shots <= 0:
        return 1024

    return shots
