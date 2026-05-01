from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    profiles_root: Path
    keys_file: Path | None
    api_token: str | None
    listen_addr: str
    log_level: str
    static_dir: Path
    templates_dir: Path

    @classmethod
    def from_env(cls) -> "Settings":
        profiles_root = Path(
            os.environ.get("PROFILES_ROOT", "./profiles")
        ).expanduser().resolve()

        keys_file_env = os.environ.get("KEYS_FILE")
        keys_file = Path(keys_file_env).expanduser().resolve() if keys_file_env else None

        pkg_root = Path(__file__).parent
        repo_root = pkg_root.parent.parent

        return cls(
            profiles_root=profiles_root,
            keys_file=keys_file,
            api_token=os.environ.get("API_TOKEN") or None,
            listen_addr=os.environ.get("LISTEN_ADDR", "127.0.0.1:8080"),
            log_level=os.environ.get("LOG_LEVEL", "info"),
            static_dir=repo_root / "static",
            templates_dir=pkg_root / "templates",
        )


def load_keys(settings: Settings) -> dict[str, str]:
    """Load API keys from KEYS_FILE (YAML) and/or API_KEY_* env vars.

    Env vars take precedence: API_KEY_FOO_BAR -> key_ref "foo_bar".
    """
    keys: dict[str, str] = {}

    if settings.keys_file and settings.keys_file.exists():
        import yaml
        data = yaml.safe_load(settings.keys_file.read_text()) or {}
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, str):
                    keys[str(k).lower()] = v

    for env_name, value in os.environ.items():
        if env_name.startswith("API_KEY_") and value:
            keys[env_name[len("API_KEY_"):].lower()] = value

    return keys
