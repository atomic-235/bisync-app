# Bisync — Android App Specification

## Overview

A native Android app that provides a GUI for `rclone bisync` — bidirectional file synchronization between local storage and any rclone remote (S3, SFTP, WebDAV, etc.). Must work in **any GrapheneOS user profile** (not just owner), unlike Termux which is restricted to the owner profile.

Primary use cases:
- KeePass database sync (`.kdbx` ↔ Yandex Cloud S3)
- General bidirectional file sync with any rclone remote
- Conflict-safe sync with "keep both versions" semantics

## Problem Statement

Current setup requires Termux to run `rclone bisync` for bidirectional sync. Termux only works in the owner profile on Android due to hardcoded `$PREFIX` paths. On GrapheneOS with multiple user profiles, this makes sync impossible from secondary profiles. Existing Android apps (RCX, FolderSync) only support one-way sync or lack conflict resolution.

## Architecture

- **Language**: Python 3
- **Framework**: Kivy (cross-platform Python UI) + Buildozer (APK packaging)
- **Core**: Bundled `rclone` arm64 static binary, invoked via `subprocess`
- **Storage**: App private directory for config/cache, `/sdcard/` for synced files

## Functional Requirements

### Sync Pairs (Profiles)

The app manages one or more **sync pairs** — each defines a local path and a remote path with associated filters and options.

Each sync pair has:
- **Name**: user-defined label (e.g., "KeePass", "Documents", "Photos")
- **Local path**: directory on `/sdcard/` (e.g., `/sdcard/keepass/`)
- **Remote path**: rclone remote path (e.g., `yandex:keepass-bucket/`)
- **Filters**: include/exclude patterns (e.g., `+ *.kdbx`, `- *.keyx`, `- *`)
- **Conflict resolution**: `newer` (default), or `larger`, `none`
- **Lock timeout**: default 2m
- **Last synced**: timestamp

### Sync Operations

For each sync pair:

1. **Sync** (bidirectional)
   - `rclone bisync <local> <remote>` with configured filters and flags
   - Conflict resolution: `--conflict-resolve newer` (keeps both versions, renames loser)
   - Safety flags: `--suffix-keep-extension --resilient --recover --max-lock <timeout>`
   - First run requires `--resync` (detect automatically if no listing cache exists)

2. **Resync** (forced full resync)
   - Same as sync but with `--resync` flag
   - Use sparingly — resets bisync listing state
   - Warn user before executing ("This will reset sync state. Continue?")

3. **Status**
   - Show local files with sizes and timestamps
   - Show remote files with sizes and timestamps
   - Show conflict files if any
   - Show last sync timestamp
   - Show sync pair health (listing cache exists, rclone config valid)

4. **Conflict awareness**
   - List any `*.conflict*` files found locally
   - Conflict files are synced to cloud by regular sync, so they're accessible from other devices

### Home Screen Widget

- Single widget showing last sync status and timestamp
- Tap widget → opens app
- Widget shows:
  - App name ("Bisync")
  - Last sync time or "Never synced"
  - Status icon: ✓ (synced), ⟳ (syncing), ✗ (error), — (not configured)
- Optional: single "Sync All" button on widget

### Configuration Screen

- **rclone config**: Allow pasting or importing an rclone config (raw INI text)
  - Config stored at app private storage (`/data/data/<app>/files/rclone.conf`), chmod 600
  - Import from clipboard or file picker
  - Remotes listed from config for selection in sync pairs
- **Sync pairs**: CRUD for sync pair configuration
  - Pick local directory (file picker or manual path)
  - Pick remote from rclone config remotes
  - Configure filters (include/exclude patterns)
  - Configure conflict resolution strategy
- **Defaults for new sync pair**: empty filters (sync everything), conflict-resolve newer, max-lock 2m

### Predefined Templates

To simplify setup for common use cases, provide templates when creating a new sync pair:

- **KeePass**: local `/sdcard/keepass/`, filters `+ *.kdbx / - *.keyx / - *`, conflict-resolve newer
- **Photos**: local `/sdcard/DCIM/`, no filters, one-way (future — not bisync)
- **Custom**: blank, user configures everything

Templates are just defaults — user can modify any field after selection.

### Auto-Sync (Future)

- Not in v1 scope
- Placeholder in UI: "Auto-sync: coming soon"

## Non-Functional Requirements

### Security

- rclone config (containing credentials) stored in app private storage, NEVER on sdcard
- Filter rules can exclude sensitive file types (e.g., `.keyx` for KeePass)
- No credentials logged or displayed in UI
- App private storage is only accessible to the app itself (Android sandbox)

### Compatibility

- Android 14+ (GrapheneOS, stock Android)
- arm64-v8a (primary), armv7 (secondary)
- Must work in **any Android user profile**, not just owner
- No root required
- No Termux dependency

### rclone Binary

- Bundle `rclone` static binary for arm64 as app asset
- Version: latest stable (1.74.x as of June 2026)
- Download from: https://downloads.rclone.org/rclone-current-linux-arm64.zip
- Extract binary, bundle as asset in APK
- On first run, extract to app private storage and `chmod +x`
- Path: `/data/data/<app>/files/rclone`

### Permissions

- `READ_EXTERNAL_STORAGE` / `WRITE_EXTERNAL_STORAGE` (or scoped storage equivalent)
- `INTERNET` (for rclone remote access)
- `FOREGROUND_SERVICE` (for sync running in background)
- `POST_NOTIFICATIONS` (for sync status notifications)

## UI Design

### Main Screen (Sync Pairs List)

```
┌─────────────────────────────┐
│  Bisync                     │
│                             │
│  ┌─────────────────────────┐│
│  │ KeePass          ✓ 12:30││
│  │ /sdcard/keepass/        ││
│  │ ↔ yandex:keepass-bucket ││
│  │ [Sync] [Resync] [Status]││
│  └─────────────────────────┘│
│                             │
│  ┌─────────────────────────┐│
│  │ Documents        ✓ 09:15││
│  │ /sdcard/Documents/      ││
│  │ ↔ nas:docs/             ││
│  │ [Sync] [Resync] [Status]││
│  └─────────────────────────┘│
│                             │
│  [+ Add sync pair]         │
│                             │
│  [Settings]                │
└─────────────────────────────┘
```

### Sync Pair Detail Screen

```
┌─────────────────────────────┐
│  KeePass                    │
│                             │
│  Last sync: 2026-06-14 12:30│
│                             │
│  ┌─────────┐ ┌───────────┐  │
│  │  Sync   │ │  Resync   │  │
│  └─────────┘ └───────────┘  │
│                             │
│  ┌─────────────────────────┐│
│  │  Status                 ││
│  └─────────────────────────┘│
│                             │
│  Local:                     │
│   database.kdbx  236KB      │
│   safe.kdbx      13KB       │
│   work.kdbx      19KB       │
│                             │
│  Remote:                    │
│   database.kdbx  236KB      │
│   safe.kdbx      13KB       │
│   work.kdbx      19KB       │
│                             │
│  Conflicts: none            │
│                             │
│  [Edit] [Delete]           │
└─────────────────────────────┘
```

### Edit Sync Pair Screen

```
┌─────────────────────────────┐
│  Edit Sync Pair             │
│                             │
│  Name: [KeePass          ]  │
│  Template: [KeePass ▾]     │
│                             │
│  Local path:                │
│  [/sdcard/keepass/       ]  │
│                             │
│  Remote:                    │
│  [yandex:keepass-bucket/]  │
│                             │
│  Filters:                   │
│  + *.kdbx          [−]     │
│  - *.keyx          [−]     │
│  - *               [−]     │
│  [+ Add filter]            │
│                             │
│  Conflict resolution:       │
│  [newer ▾]                 │
│                             │
│  Lock timeout: [2m      ]  │
│                             │
│  [Save] [Cancel]           │
└─────────────────────────────┘
```

### Settings Screen

```
┌─────────────────────────────┐
│  Settings                   │
│                             │
│  rclone Config              │
│  [Import from clipboard]   │
│  [Import from file]        │
│  [View current config *]   │
│                             │
│  * masks credentials       │
│                             │
│  About                      │
│  rclone version: 1.74.3    │
│  App version: 1.0.0        │
└─────────────────────────────┘
```

## Technical Details

### Data Model

```python
@dataclass
class SyncPair:
    id: str                    # UUID
    name: str                  # User label
    local_path: str            # e.g. "/sdcard/keepass/"
    remote_path: str            # e.g. "yandex:keepass-bucket/"
    filters: list[SyncFilter]  # Include/exclude rules
    conflict_resolve: str      # "newer" | "larger" | "none"
    lock_timeout: str          # e.g. "2m"
    last_synced: str | None    # ISO timestamp

@dataclass
class SyncFilter:
    direction: str   # "+" or "-"
    pattern: str     # e.g. "*.kdbx"
```

Stored as JSON in app private storage.

### rclone Invocation

The app calls rclone as a subprocess. Example for a sync pair:

```python
cmd = [
    rclone_path,
    "bisync",
    pair.local_path,
    pair.remote_path,
    "--config", config_path,
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
result = subprocess.run(cmd, capture_output=True, text=True)
```

### First-Run Detection

Try sync first, if it fails with "cannot find prior listing", automatically retry with `--resync`.

### Parsing rclone Output

- Parse stdout for "Copied (new)", "Copied (replaced existing)", conflict names
- Parse stderr for errors
- Show parsed results in UI (file counts, conflict names)
- Full log available in a scrollable view for debugging

### Build Configuration (Buildozer)

```ini
[app]
title = Bisync
package.name = bisync
package.domain = dev.kraftnix
source.dir = .
source.include_ext = py,png,jpg,kv,atlas
requirements = python3,kivy
android.permissions = INTERNET,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,FOREGROUND_SERVICE,POST_NOTIFICATIONS
android.archs = arm64-v8a
android.allow_backup = False
```

The rclone binary should be included in the `assets/` directory and extracted on first run.

### Project Structure

```
bisync-app/
├── main.py              # App entry point
├── sync.py              # rclone bisync logic
├── config.py            # rclone config management
├── models.py            # SyncPair, SyncFilter data models
├── store.py             # JSON persistence for sync pairs
├── widget.py            # Home screen widget provider
├── ui/
│   ├── main.kv          # Sync pairs list screen
│   ├── detail.kv        # Sync pair detail screen
│   ├── edit.kv          # Edit sync pair screen
│   └── settings.kv      # Settings screen
├── assets/
│   └── rclone-arm64     # Bundled rclone binary
├── buildozer.spec       # Build configuration
└── README.md
```

## Bisync Behavior Reference

rclone bisync flags and their purpose:

| Flag | Purpose |
|------|---------|
| `--filter="+ <pattern>"` | Include files matching pattern |
| `--filter="- <pattern>"` | Exclude files matching pattern |
| `--conflict-resolve newer` | On conflict, keep newer as winner, rename older with conflict suffix |
| `--conflict-resolve larger` | On conflict, keep larger as winner |
| `--conflict-resolve none` | On conflict, abort (requires manual resolution) |
| `--suffix-keep-extension` | Conflict file keeps original extension (e.g., `file.conflict1.kdbx`) |
| `--resilient` | Continue on individual file errors instead of aborting |
| `--recover` | Auto-recover from listing drift without full resync |
| `--max-lock 2m` | Lock timeout for concurrent access protection |
| `--resync` | Forced full resync (resets listing state, use sparingly) |
| `--verbose` | Detailed output for parsing |

## KeePass Use Case Reference

The primary use case that inspired this app. Default values for a KeePass sync pair:

- **Local**: `/sdcard/keepass/`
- **Remote**: `yandex:keepass-bucket/`
- **Filters**: `+ *.kdbx`, `- *.keyx`, `- *`
- **Conflict resolve**: `newer`
- **Critical**: `.keyx` (key file) must NEVER be uploaded to cloud. The `- *.keyx` filter enforces this.

## Nix Flake

The project must include a Nix flake for reproducible development on NixOS. Follow the pattern from existing projects in `~/projects/personal/`.

### Requirements

- **Python**: 3.12 via `uv2nix` (same as adb project flake)
- **rclone**: available in dev shell for testing sync logic locally
- **uv**: available in dev shell for dependency management
- **direnv**: `.envrc` with `use flake` for automatic shell loading

### flake.nix structure

```nix
{
  description = "Bisync - Android app for bidirectional file sync via rclone";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, uv2nix, pyproject-nix, pyproject-build-systems }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs { inherit system; };

      workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./.; };
      overlay = workspace.mkPyprojectOverlay { sourcePreference = "wheel"; };

      python = pkgs.python312;

      pythonSet =
        (pkgs.callPackage pyproject-nix.build.packages { inherit python; })
        .overrideScope (pkgs.lib.composeManyExtensions [
          pyproject-build-systems.overlays.default
          overlay
        ]);

      venv = pythonSet.mkVirtualEnv "bisync-env" workspace.deps.default;
    in
    {
      devShells.${system}.default = pkgs.mkShell {
        packages = [ venv pkgs.uv pkgs.rclone ];
        env = {
          UV_NO_SYNC             = "1";
          UV_PYTHON              = "${venv}/bin/python";
          UV_PYTHON_DOWNLOADS    = "never";
          UV_PROJECT_ENVIRONMENT = "${venv}";
        };
        shellHook = ''unset PYTHONPATH'';
      };
    };
}
```

### Additional files

- `.envrc`: `use flake` (for direnv auto-loading)
- `pyproject.toml`: Python project config with Kivy dependency, managed by `uv`
- `.python-version`: `3.12`

### Notes

- Buildozer runs on Linux x86_64 and cross-compiles for arm64 — it does NOT need to be in the nix shell (it installs its own Android SDK/NDK). Run `buildozer android debug` directly after `pip install buildozer`.
- `rclone` in the dev shell is for local testing only (verify sync logic on PC before building APK)
- The bundled rclone binary in the APK is downloaded separately (arm64 static build), not from nixpkgs

## Out of Scope (v1)

- Auto-sync / scheduled sync
- One-way sync (copy/move) — bisync only
- rclone config auto-generation (user must provide config)
- Encryption (user can configure rclone crypt remote in config)
- File browsing / management
- proot / opencode / other Termux features

## Testing

- Verify app works in GrapheneOS secondary user profile
- Verify `.keyx` files are never uploaded to remote (KeePass use case)
- Verify conflict resolution creates `.conflict1.*` file
- Verify resync works after first-run (no prior listing)
- Verify rclone config is not world-readable
- Verify app works offline (status shows local files, remote shows error gracefully)
- Verify multiple sync pairs can coexist independently
