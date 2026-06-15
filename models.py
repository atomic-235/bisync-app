from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SyncFilter:
    direction: str
    pattern: str

    def to_dict(self) -> dict[str, str]:
        return {"direction": self.direction, "pattern": self.pattern}

    @classmethod
    def from_dict(cls, d: dict[str, str]) -> SyncFilter:
        return cls(direction=d["direction"], pattern=d["pattern"])

    def __str__(self) -> str:
        return f"{self.direction} {self.pattern}"


@dataclass
class SyncPair:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    local_path: str = ""
    remote_path: str = ""
    filters: list[SyncFilter] = field(default_factory=list)
    conflict_resolve: str = "newer"
    lock_timeout: str = "2m"
    last_synced: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "local_path": self.local_path,
            "remote_path": self.remote_path,
            "filters": [f.to_dict() for f in self.filters],
            "conflict_resolve": self.conflict_resolve,
            "lock_timeout": self.lock_timeout,
            "last_synced": self.last_synced,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SyncPair:
        return cls(
            id=d.get("id", str(uuid.uuid4())),
            name=d.get("name", ""),
            local_path=d.get("local_path", ""),
            remote_path=d.get("remote_path", ""),
            filters=[SyncFilter.from_dict(f) for f in d.get("filters", [])],
            conflict_resolve=d.get("conflict_resolve", "newer"),
            lock_timeout=d.get("lock_timeout", "2m"),
            last_synced=d.get("last_synced"),
        )


TEMPLATES: dict[str, dict[str, Any]] = {
    "KeePass": {
        "name": "KeePass",
        "local_path": "/sdcard/keepass/",
        "filters": [
            {"direction": "+", "pattern": "*.kdbx"},
            {"direction": "-", "pattern": "*.keyx"},
            {"direction": "-", "pattern": "*"},
        ],
        "conflict_resolve": "newer",
    },
    "Custom": {
        "name": "",
        "local_path": "",
        "filters": [],
        "conflict_resolve": "newer",
    },
}
