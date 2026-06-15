[app]

title = Bisync
package.name = bisync
package.domain = dev.kraftnix
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
source.include_patterns = assets/*,ui/*
version = 0.1

requirements = python3,kivy

orientation = portrait
fullscreen = 0

android.permissions = INTERNET,FOREGROUND_SERVICE,POST_NOTIFICATIONS,(name=android.permission.READ_EXTERNAL_STORAGE;maxSdkVersion=32),(name=android.permission.WRITE_EXTERNAL_STORAGE;maxSdkVersion=28)
android.archs = arm64-v8a
android.allow_backup = False
android.api = 33
android.minapi = 24
android.enable_androidx = True

android.add_assets = assets/rclone-arm64:rclone-arm64

[buildozer]
log_level = 2
warn_on_root = 1
