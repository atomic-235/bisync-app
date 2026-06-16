from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone

from config import config_path, get_rclone_env, rclone_path, resolve_local_path, bisync_workdir
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
        "--workdir", str(bisync_workdir()),
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
        cmd.extend(["--resync-mode", "newer"])
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
    lock_dir = bisync_workdir()
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
    cmd = _build_cmd(pair, resync=force_resync)

    try:
        result = _run_cmd(cmd, on_log=on_log)
    except FileNotFoundError:
        return SyncResult(
            success=False,
            errors=["rclone binary not found"],
        )

    if not force_resync and not result.success:
        output = result.raw_stderr + result.raw_stdout
        if "cannot find prior listing" in output or "prior lock" in output:
            return SyncResult(
                success=False,
                errors=["No prior listing found. Run with 'Resync' to re-establish."],
            )

    if result.success:
        pair.last_synced = datetime.now(timezone.utc).isoformat()

    return result


def run_push(pair: SyncPair, on_log=None) -> SyncResult:
    local = resolve_local_path(pair)
    os.makedirs(local, exist_ok=True)
    cmd = [
        str(rclone_path()),
        "copy",
        local,
        pair.remote_path,
        "--config", str(config_path()),
    ]
    for f in pair.filters:
        cmd.append(f"--filter={f.direction} {f.pattern}")
    cmd.extend(["--verbose"])
    try:
        return _run_cmd(cmd, on_log=on_log)
    except FileNotFoundError:
        return SyncResult(success=False, errors=["rclone binary not found"])


def run_pull(pair: SyncPair, on_log=None) -> SyncResult:
    local = resolve_local_path(pair)
    os.makedirs(local, exist_ok=True)
    cmd = [
        str(rclone_path()),
        "copy",
        pair.remote_path,
        local,
        "--config", str(config_path()),
    ]
    for f in pair.filters:
        cmd.append(f"--filter={f.direction} {f.pattern}")
    cmd.extend(["--verbose"])
    try:
        return _run_cmd(cmd, on_log=on_log)
    except FileNotFoundError:
        return SyncResult(success=False, errors=["rclone binary not found"])


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
