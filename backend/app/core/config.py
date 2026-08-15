import os
import re
import logging
from pathlib import Path
from typing import Any, Dict, Optional
import yaml

LOGGER = logging.getLogger(__name__)

# Find project root directory containing config/
_CURRENT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _CURRENT_DIR
while _PROJECT_ROOT.parent != _PROJECT_ROOT:
    if (_PROJECT_ROOT / "config").exists() or (_PROJECT_ROOT / "backend").exists():
        break
    _PROJECT_ROOT = _PROJECT_ROOT.parent

# Default to project root / config if found, else fallback relative to app
CONFIG_DIR = _PROJECT_ROOT / "config"
if not CONFIG_DIR.exists():
    CONFIG_DIR = _CURRENT_DIR.parent.parent.parent / "config"


def _interpolate_env_vars(raw_text: str) -> str:
    """
    Interpolate ${ENV_VAR} or ${ENV_VAR:-default} references in YAML raw text.
    """
    def _replacer(match: re.Match) -> str:
        var_expr = match.group(1)
        if ":-" in var_expr:
            var_name, default_val = var_expr.split(":-", 1)
            return os.environ.get(var_name, default_val)
        return os.environ.get(var_expr, "")

    pattern = re.compile(r"\$\{([^}]+)\}")
    return pattern.sub(_replacer, raw_text)


def _load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        LOGGER.warning("Config file not found at: %s", path)
        return {}

    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()

    interpolated = _interpolate_env_vars(raw)
    try:
        data = yaml.safe_load(interpolated)
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        LOGGER.error("Failed to parse YAML from %s: %s", path, exc)
        return {}


class ConfigLoader:
    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or CONFIG_DIR

    def load_config(self, profile_name: Optional[str] = None) -> Dict[str, Any]:
        profile = profile_name or os.environ.get("CITYOS_PROFILE", "local")

        city_data = _load_yaml(self.config_dir / "city.yaml")
        scoring_data = _load_yaml(self.config_dir / "scoring.yaml")
        profile_path = self.config_dir / "profiles" / f"{profile}.yaml"
        profile_data = _load_yaml(profile_path)

        if not profile_data and not profile_path.exists():
            LOGGER.warning("Profile '%s' file does not exist at %s", profile, profile_path)

        return {
            "profile_name": profile,
            "city": city_data.get("city", city_data),
            "scoring": scoring_data,
            "profile": profile_data,
        }


# Global instance
_loader = ConfigLoader()


def load_config(profile_name: Optional[str] = None) -> Dict[str, Any]:
    return _loader.load_config(profile_name)


def get_city_config() -> Dict[str, Any]:
    return load_config().get("city", {})


def get_scoring_config() -> Dict[str, Any]:
    return load_config().get("scoring", {})


def get_profile_config() -> Dict[str, Any]:
    return load_config().get("profile", {})
