[app]

title = Bisync
package.name = bisync
package.domain = dev.kraftnix
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
source.include_patterns = assets/*
version = 0.1

requirements = python3,kivy==2.3.0,filetype

orientation = portrait
fullscreen = 0

android.permissions = INTERNET,FOREGROUND_SERVICE,POST_NOTIFICATIONS,(name=android.permission.READ_EXTERNAL_STORAGE;maxSdkVersion=32),(name=android.permission.WRITE_EXTERNAL_STORAGE;maxSdkVersion=28)
android.archs = arm64-v8a
android.allow_backup = False
android.api = 33
android.minapi = 24
android.ndk = 25b
android.enable_androidx = True
android.accept_sdk_license = True

android.add_libs = assets/librclone.so:lib/arm64-v8a/librclone.so

[buildozer]
log_level = 2
warn_on_root = 1
