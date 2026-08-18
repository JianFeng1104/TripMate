"""Load optional local environment values without weakening deployment config."""

import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_local_environment(
    env_file: Path | None = None,
    *,
    environment: str | None = None,
) -> bool:
    """Load a development ``.env`` file while preserving existing OS values.

    Test, demo and production processes deliberately skip local files.
    Hosting-platform variables and values explicitly set in PowerShell win because
    ``override`` is disabled.
    """

    effective_environment = str(
        environment
        or os.environ.get("TRIPMATE_ENV")
        or os.environ.get("APP_ENV")
        or "development"
    ).strip().lower()
    if effective_environment != "development":
        return False

    dotenv_path = Path(env_file) if env_file is not None else PROJECT_ROOT / ".env"
    return load_dotenv(dotenv_path=dotenv_path, override=False)
