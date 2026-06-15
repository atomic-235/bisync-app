from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone

from config import config_path, get_rclone_env, rclone_path, listing_cache_exists, resolve_local_path
from models import SyncPair


@dataclass
class SyncResult:
    success: bool = False
    exit_code: int = -1
    copied_to_remote: list[str] = field(default_factory=list)
    copied_to_local: list[str] = field(default_factory=list)
    deleted_remote: list[str] = field(default_factory=list)
    deleted_local: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    raw_stdout: str = ""
    raw_stderr: str = ""


def _build_cmd(pair: SyncPair, resync: bool = False) -> list[str]:
    local = resolve_local_path(pair)
    cmd = [
        str(rclone_path()),
        "bisync",
        local,
        pair.remote_path,
        "--config", str(config_path()),
    ]
    for f in pair.filters:
        cmd.append(f"--filter={f.direction} {f.pattern}")
    cmd.extend([
        "--conflict-resolve", pair.conflict_resolve,
        "--suffix-keep-extension",
        "--resilient",
        "--recover",
        "--max-lock", pair.lock_timeout,
        "--verbose",
    ])
    if resync:
        cmd.append("--resync")
    return cmd


def parse_output(stdout: str, stderr: str, exit_code: int) -> SyncResult:
    result = SyncResult(
        success=exit_code == 0,
        exit_code=exit_code,
        raw_stdout=stdout,
        raw_stderr=stderr,
    )

    for line in (stdout + "\n" + stderr).splitlines():
        m = re.match(r".*Queue copy to Path2\s+-\s+(.*)", line)
        if m:
            result.copied_to_remote.append(m.group(1).strip())
            continue

        m = re.match(r".*Queue copy to Path1\s+-\s+(.*)", line)
        if m:
            result.copied_to_local.append(m.group(1).strip())
            continue

        m = re.match(r".*Queue delete\s+-\s+(.*)", line)
        if m:
            dest = result.deleted_remote if "Path2" in line else result.deleted_local
            dest.append(m.group(1).strip())
            continue

        m = re.match(r".*New or changed in both paths\s+-\s+(.*)", line)
        if m:
            result.conflicts.append(m.group(1).strip())
            continue

        if line.strip().startswith("ERROR"):
            result.errors.append(line.strip())

    return result


def _run_cmd(cmd: list[str], on_log=None) -> SyncResult:
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=get_rclone_env(),
        )
    except FileNotFoundError:
        raise

    lines = []
    for line in proc.stdout:
        line = line.rstrip()
        lines.append(line)
        if on_log:
            on_log(line)

    proc.wait()
    stdout = "\n".join(lines)
    return parse_output(stdout, "", proc.returncode)


def _clean_lock_files(pair: SyncPair) -> None:
    from config import _app_dir
    lock_dir = _app_dir() / "tmp" / "rclone" / "bisync"
    if not lock_dir.exists():
        return
    for f in lock_dir.glob("*.lck"):
        try:
            os.remove(f)
        except OSError:
            pass


def run_sync(pair: SyncPair, force_resync: bool = False, on_log=None) -> SyncResult:
    _clean_lock_files(pair)
    local = resolve_local_path(pair)
    os.makedirs(local, exist_ok=True)
    needs_resync = force_resync or not listing_cache_exists(pair)
    cmd = _build_cmd(pair, resync=needs_resync)

    try:
        result = _run_cmd(cmd, on_log=on_log)
    except FileNotFoundError:
        return SyncResult(
            success=False,
            errors=["rclone binary not found"],
        )

    if not needs_resync and not result.success:
        output = result.raw_stderr + result.raw_stdout
        if "cannot find prior listing" in output or "prior lock" in output:
            _clean_lock_files(pair)
            cmd2 = _build_cmd(pair, resync="cannot find prior listing" in output)
            try:
                result = _run_cmd(cmd2, on_log=on_log)
            except FileNotFoundError:
                return SyncResult(
                    success=False,
                    errors=["rclone binary not found"],
                )

    if result.success:
        pair.last_synced = datetime.now(timezone.utc).isoformat()

    return result


def get_status(pair: SyncPair) -> dict:
    result: dict = {
        "local_files": [],
        "remote_files": [],
        "conflicts": [],
        "last_synced": pair.last_synced,
        "listing_ok": listing_cache_exists(pair),
        "config_ok": config_path().exists(),
    }

    local = _list_local(pair)
    result["local_files"] = local

    remote = _list_remote(pair)
    result["remote_files"] = remote

    conflicts = _find_conflicts(pair)
    result["conflicts"] = conflicts

    return result


def _list_local(pair: SyncPair) -> list[dict]:
    import os

    path = resolve_local_path(pair)
    if not os.path.isdir(path):
        return []
    files = []
    for name in sorted(os.listdir(path)):
        full = os.path.join(path, name)
        if os.path.isfile(full):
            st = os.stat(full)
            files.append({"name": name, "size": st.st_size})
    return files


def test_remote(remote_path: str, on_log=None) -> tuple[bool, str]:
    cmd = [
        str(rclone_path()),
        "lsf",
        remote_path,
        "--config", str(config_path()),
        "--verbose",
    ]
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=get_rclone_env(),
        )
    except FileNotFoundError:
        return False, "rclone binary not found"

    lines = []
    for line in proc.stdout:
        line = line.rstrip()
        lines.append(line)
        if on_log:
            on_log(line)
    proc.wait()
    return proc.returncode == 0, "\n".join(lines)


def _list_remote(pair: SyncPair) -> list[dict]:
    cmd = [
        str(rclone_path()),
        "lsf",
        pair.remote_path,
        "--config", str(config_path()),
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=get_rclone_env(),
            timeout=30,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []

    if proc.returncode != 0:
        return []

    files = []
    for line in proc.stdout.strip().splitlines():
        name = line.strip().rstrip(";")
        if name:
            files.append({"name": name, "size": -1})
    return files


def _find_conflicts(pair: SyncPair) -> list[str]:
    import os

    path = resolve_local_path(pair)
    if not os.path.isdir(path):
        return []
    return sorted(
        f
        for f in os.listdir(path)
        if "conflict" in f.lower() and os.path.isfile(os.path.join(path, f))
    )
