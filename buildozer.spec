[app]

title = Bisync
package.name = bisync
package.domain = dev.kraftnix
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
source.include_patterns = assets/*
version.regex = __version__ = ['"](.*)['"]
version.filename = %(source.dir)s/main.py

requirements = python3,kivy==2.3.1,filetype

orientation = portrait
fullscreen = 0

android.permissions = INTERNET,FOREGROUND_SERVICE,POST_NOTIFICATIONS,MANAGE_EXTERNAL_STORAGE
android.archs = arm64-v8a
android.allow_backup = False
android.api = 33
android.minapi = 24
android.enable_androidx = True
android.accept_sdk_license = True

p4a.branch = v2026.05.09

android.add_libs_arm64_v8a = assets/librclone.so
android.release_artifact = apk

[buildozer]
log_level = 2
warn_on_root = 1
