from __future__ import annotations

import os
import shutil
import stat
from pathlib import Path

from models import SyncPair


def _app_dir() -> Path:
    if os.environ.get("BISYNC_DATA"):
        return Path(os.environ["BISYNC_DATA"])
    try:
        from android.storage import app_storage_path

        return Path(app_storage_path())
    except ImportError:
        return Path.home() / ".bisync"


def is_android() -> bool:
    try:
        from android.storage import app_storage_path
        return True
    except ImportError:
        return False


def resolve_local_path(pair: SyncPair) -> str:
    if is_android():
        return pair.local_path
    project = Path(__file__).parent
    local = project / "sync" / pair.local_path.strip("/").replace(":", "_")
    local.mkdir(parents=True, exist_ok=True)
    return str(local)


def config_path() -> Path:
    p = _app_dir() / "rclone.conf"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def rclone_path() -> Path:
    bundled = _app_dir() / "rclone"
    if bundled.exists():
        return bundled
    from shutil import which
    system = which("rclone")
    if system:
        return Path(system)
    return bundled


def _extract_rclone(dest: Path) -> None:
    asset = Path(__file__).parent / "assets" / "rclone-arm64"
    if asset.exists():
        shutil.copy2(asset, dest)
        dest.chmod(dest.stat().st_mode | stat.S_IEXEC)


def has_config() -> bool:
    p = config_path()
    return p.exists() and p.stat().st_size > 0


def read_config_masked() -> str:
    p = config_path()
    if not p.exists():
        return ""
    text = p.read_text()
    lines = []
    for line in text.splitlines():
        if "=" in line and not line.strip().startswith("["):
            key, _, _ = line.partition("=")
            lines.append(f"{key}=***")
        else:
            lines.append(line)
    return "\n".join(lines)


def write_config(content: str) -> None:
    p = config_path()
    p.write_text(content)
    p.chmod(0o600)


def get_remotes() -> list[str]:
    p = config_path()
    if not p.exists():
        return []
    remotes: list[str] = []
    for line in p.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            remotes.append(stripped[1:-1])
    return remotes


def listing_cache_exists(pair: SyncPair) -> bool:
    cache_dir = _app_dir() / "cache"
    if not cache_dir.exists():
        return False
    safe_name = pair.name.replace("/", "_").replace(" ", "_")
    return any(cache_dir.glob(f"*{safe_name}*.lst"))


def get_rclone_env() -> dict[str, str]:
    env = os.environ.copy()
    env["RCLONE_CONFIG"] = str(config_path())
    env["TMPDIR"] = str(_app_dir() / "tmp")
    tmp = Path(env["TMPDIR"])
    tmp.mkdir(parents=True, exist_ok=True)
    return env
