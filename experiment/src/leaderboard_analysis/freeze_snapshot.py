from __future__ import annotations

import os
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import wandb
from dotenv import load_dotenv

from leaderboard_analysis.common import (
    CONFIG_PATH,
    MANIFEST_DIR,
    PROJECT_ROOT,
    WORKSPACE_ROOT,
    load_config,
    sha256_file,
    write_json,
)


def git_output(repo: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), *args],
        text=True,
        stderr=subprocess.DEVNULL,
    ).strip()


def source_info(repo: Path) -> dict[str, str]:
    return {
        "commit": git_output(repo, "rev-parse", "HEAD"),
        "remote": git_output(repo, "remote", "get-url", "origin"),
    }


def main() -> None:
    load_dotenv(WORKSPACE_ROOT / ".env", override=False)
    config = load_config()
    timezone = config["snapshot"]["timezone"]
    now = datetime.now(ZoneInfo(timezone))

    lock_path = PROJECT_ROOT / "uv.lock"
    sources = {
        "wandb_llm_leaderboard": source_info(PROJECT_ROOT / "vendor" / "llm-leaderboard"),
        "wandb_fails": source_info(PROJECT_ROOT / "vendor" / "fails"),
    }

    snapshot = {
        "snapshot_date": config["snapshot"]["date"],
        "timezone": timezone,
        "captured_at": now.isoformat(),
        "workspace": {
            "analysis_detail_sha256": sha256_file(WORKSPACE_ROOT / "analysis_detail.md"),
            "instruction_sha256": sha256_file(WORKSPACE_ROOT / "instruction.md"),
            "analysis_config_sha256": sha256_file(CONFIG_PATH),
            "pyproject_sha256": sha256_file(PROJECT_ROOT / "pyproject.toml"),
            "uv_lock_sha256": sha256_file(lock_path),
        },
        "environment": {
            "python": sys.version.split()[0],
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "wandb_sdk": wandb.__version__,
            "credential_env_names_present": [
                key for key in ["WANDB_API_KEY"] if bool(os.environ.get(key))
            ],
        },
        "sources": sources,
    }

    output = MANIFEST_DIR / "snapshot.json"
    write_json(output, snapshot)
    print(f"Wrote {output.relative_to(PROJECT_ROOT)}")
    print(
        "Pinned sources:",
        ", ".join(f"{name}={item['commit'][:12]}" for name, item in sources.items()),
    )


if __name__ == "__main__":
    main()
