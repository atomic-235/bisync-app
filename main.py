from __future__ import annotations

import os

from threading import Thread

__version__ = "0.1.0"

from kivy.app import App
from kivy.clock import Clock
from kivy.properties import BooleanProperty, ListProperty, ObjectProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen, ScreenManager

from config import has_config, read_config_masked, write_config, get_remotes, rclone_path
from models import TEMPLATES, SyncFilter, SyncPair
from store import add_pair, delete_pair, get_pair, load_pairs, save_pairs, update_pair
from sync import SyncResult, run_sync, run_push, run_pull, test_remote


class BisyncScreenManager(ScreenManager):
    pass


class HomeScreen(Screen):
    pairs = ListProperty([])

    def on_enter(self, *_args):
        self.refresh()

    def refresh(self):
        self.pairs = load_pairs()
        self.ids.pairs_list.clear_widgets()
        for pair in self.pairs:
            card = SyncPairCard(pair=pair)
            self.ids.pairs_list.add_widget(card)


class SyncPairCard(BoxLayout):
    pair = ObjectProperty(None, rebind=True)
    pair_name = StringProperty("")
    pair_local = StringProperty("")
    pair_remote = StringProperty("")
    pair_status = StringProperty("—")

    def __init__(self, pair: SyncPair, **kwargs):
        self.pair = pair
        super().__init__(**kwargs)
        self.pair_name = pair.name
        self.pair_local = pair.local_path
        self.pair_remote = pair.remote_path
        self.pair_status = pair.last_synced[11:16] if pair.last_synced else "—"

    def do_sync(self):
        app = App.get_running_app()
        app.run_sync_with_log(self.pair)

    def do_push(self):
        app = App.get_running_app()
        app.run_push_with_log(self.pair)

    def do_pull(self):
        app = App.get_running_app()
        app.run_pull_with_log(self.pair)

    def do_resync(self):
        content = ConfirmPopup(
            message="This will reset sync state. Continue?",
            on_confirm=lambda: App.get_running_app().run_sync_with_log(self.pair, force_resync=True),
        )
        popup = Popup(title="Confirm Resync", content=content, size_hint=(0.8, 0.4))
        content.popup = popup
        popup.open()

    def do_edit(self):
        app = App.get_running_app()
        app.edit_pair(self.pair)

    def do_delete(self):
        content = ConfirmPopup(
            message=f"Delete sync pair '{self.pair.name}'?",
            on_confirm=self._do_delete,
        )
        popup = Popup(title="Confirm Delete", content=content, size_hint=(0.8, 0.4))
        content.popup = popup
        popup.open()

    def _do_delete(self):
        delete_pair(self.pair.id)
        app = App.get_running_app()
        app.go_home()


class EditScreen(Screen):
    pair = ObjectProperty(None, rebind=True)
    pair_name = StringProperty("")
    local_path = StringProperty("")
    remote_path = StringProperty("")
    conflict_resolve = StringProperty("newer")
    lock_timeout = StringProperty("2m")
    filters_text = StringProperty("")
    is_new = BooleanProperty(False)

    def on_enter(self, *_args):
        if self.pair:
            self.pair_name = self.pair.name
            self.local_path = self.pair.local_path
            self.remote_path = self.pair.remote_path
            self.conflict_resolve = self.pair.conflict_resolve
            self.lock_timeout = self.pair.lock_timeout
            self.filters_text = "\n".join(str(f) for f in self.pair.filters)
        elif self.is_new:
            self.pair_name = ""
            self.local_path = ""
            self.remote_path = ""
            self.conflict_resolve = "newer"
            self.lock_timeout = "2m"
            self.filters_text = ""

    def apply_template(self, template_name: str):
        tpl = TEMPLATES.get(template_name, {})
        if not tpl:
            return
        self.pair_name = tpl.get("name", "")
        self.local_path = tpl.get("local_path", "")
        self.filters_text = "\n".join(
            f"{f['direction']} {f['pattern']}" for f in tpl.get("filters", [])
        )
        self.conflict_resolve = tpl.get("conflict_resolve", "newer")

    def save(self):
        filters = self._parse_filters()
        if self.pair:
            self.pair.name = self.pair_name
            self.pair.local_path = self.local_path
            self.pair.remote_path = self.remote_path
            self.pair.filters = filters
            self.pair.conflict_resolve = self.conflict_resolve
            self.pair.lock_timeout = self.lock_timeout
            update_pair(self.pair)
        else:
            new_pair = SyncPair(
                name=self.pair_name,
                local_path=self.local_path,
                remote_path=self.remote_path,
                filters=filters,
                conflict_resolve=self.conflict_resolve,
                lock_timeout=self.lock_timeout,
            )
            add_pair(new_pair)
        app = App.get_running_app()
        app.go_home()

    def _parse_filters(self) -> list[SyncFilter]:
        filters = []
        for line in self.filters_text.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(None, 1)
            if len(parts) == 2 and parts[0] in ("+", "-"):
                filters.append(SyncFilter(direction=parts[0], pattern=parts[1]))
        return filters


class SettingsScreen(Screen):
    config_text = StringProperty("")
    config_masked = StringProperty("")
    remotes_text = StringProperty("")

    def on_enter(self, *_args):
        self._refresh_config()

    def _refresh_config(self):
        self.config_masked = read_config_masked()
        remotes = get_remotes()
        self.remotes_text = f"Remotes: {', '.join(remotes)}" if remotes else "Remotes: (none)"
        try:
            rp = rclone_path()
            if rp.exists():
                ver = os.popen(f"{rp} --version").read().strip().split("\n")[0]
            else:
                ver = "not found"
        except Exception:
            ver = "not found"
        self.ids.about_label.text = f"rclone: {ver}\nApp: 0.1.0"

    def import_clipboard(self):
        from kivy.core.clipboard import Clipboard

        text = Clipboard.paste()
        if text:
            write_config(text)
            self._refresh_config()

    def import_text(self):
        content = ConfigInputPopup(on_save=self._save_config)
        popup = Popup(title="Import rclone Config", content=content, size_hint=(0.9, 0.7))
        content.popup = popup
        popup.open()

    def _save_config(self, text: str):
        write_config(text)
        self._refresh_config()


class ConfirmPopup(BoxLayout):
    message = StringProperty("")
    popup = ObjectProperty(None, rebind=True)

    def __init__(self, on_confirm=None, **kwargs):
        self._on_confirm = on_confirm
        super().__init__(**kwargs)

    def confirm(self):
        if self._on_confirm:
            self._on_confirm()
        if self.popup:
            self.popup.dismiss()

    def cancel(self):
        if self.popup:
            self.popup.dismiss()


class ConfigInputPopup(BoxLayout):
    popup = ObjectProperty(None, rebind=True)

    def __init__(self, on_save=None, **kwargs):
        self._on_save = on_save
        super().__init__(**kwargs)

    def save(self):
        text = self.ids.config_input.text
        if self._on_save and text:
            self._on_save(text)
        if self.popup:
            self.popup.dismiss()

    def cancel(self):
        if self.popup:
            self.popup.dismiss()


class ResultPopup(BoxLayout):
    result_text = StringProperty("")
    popup = ObjectProperty(None, rebind=True)

    def copy_to_clipboard(self):
        from kivy.core.clipboard import Clipboard
        Clipboard.copy(self.result_text)

    def dismiss(self):
        if self.popup:
            self.popup.dismiss()


class SyncLogPopup(BoxLayout):
    log_text = StringProperty("")
    popup = ObjectProperty(None, rebind=True)

    def dismiss(self):
        if self.popup:
            self.popup.dismiss()


class BisyncApp(App):
    def build(self):
        self.sm = BisyncScreenManager()
        self.sm.add_widget(HomeScreen(name="home"))
        self.sm.add_widget(SettingsScreen(name="settings"))
        self._request_permissions()
        return self.sm

    def _request_permissions(self):
        try:
            from android.permissions import request_permissions, Permission
            request_permissions([Permission.POST_NOTIFICATIONS])
        except ImportError:
            pass

        try:
            from jnius import autoclass
            Build_VERSION = autoclass("android.os.Build$VERSION")
            if Build_VERSION.SDK_INT >= 30:
                Environment = autoclass("android.os.Environment")
                if not Environment.isExternalStorageManager():
                    PythonActivity = autoclass("org.kivy.android.PythonActivity")
                    Intent = autoclass("android.content.Intent")
                    Settings = autoclass("android.provider.Settings")
                    Uri = autoclass("android.net.Uri")
                    mActivity = PythonActivity.mActivity
                    intent = Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION)
                    intent.setData(Uri.parse(f"package:{mActivity.getPackageName()}"))
                    mActivity.startActivity(intent)
        except Exception:
            pass

    def go_home(self):
        if self.sm.current != "home":
            self.sm.current = "home"
        home = self.sm.get_screen("home")
        if home:
            home.refresh()

    def run_sync_with_log(self, pair: SyncPair, force_resync: bool = False, on_done=None):
        log_popup = SyncLogPopup()
        popup = Popup(title=f"Syncing: {pair.name}", content=log_popup, size_hint=(0.9, 0.7), auto_dismiss=False)
        log_popup.popup = popup
        popup.open()

        def on_log(line):
            Clock.schedule_once(lambda dt: setattr(log_popup, "log_text", log_popup.log_text + line + "\n"))

        def worker():
            result = run_sync(pair, force_resync=force_resync, on_log=on_log)
            Clock.schedule_once(lambda dt: self._on_sync_done(pair, result, popup, on_done))

        Thread(target=worker, daemon=True).start()

    def _on_sync_done(self, pair, result, log_popup, on_done):
        log_popup.dismiss()
        self.show_result(pair, result)
        if on_done:
            on_done()

    def edit_pair(self, pair: SyncPair | None = None):
        if not self.sm.has_screen("edit"):
            self.sm.add_widget(EditScreen(name="edit"))
        screen = self.sm.get_screen("edit")
        screen.pair = pair
        screen.is_new = pair is None
        self.sm.current = "edit"

    def run_push_with_log(self, pair: SyncPair):
        log_popup = SyncLogPopup()
        popup = Popup(title=f"Push: {pair.name}", content=log_popup, size_hint=(0.9, 0.7), auto_dismiss=False)
        log_popup.popup = popup
        popup.open()

        def on_log(line):
            Clock.schedule_once(lambda dt: setattr(log_popup, "log_text", log_popup.log_text + line + "\n"))

        def worker():
            result = run_push(pair, on_log=on_log)
            Clock.schedule_once(lambda dt: self._on_sync_done(pair, result, popup, None))

        Thread(target=worker, daemon=True).start()

    def run_pull_with_log(self, pair: SyncPair):
        log_popup = SyncLogPopup()
        popup = Popup(title=f"Pull: {pair.name}", content=log_popup, size_hint=(0.9, 0.7), auto_dismiss=False)
        log_popup.popup = popup
        popup.open()

        def on_log(line):
            Clock.schedule_once(lambda dt: setattr(log_popup, "log_text", log_popup.log_text + line + "\n"))

        def worker():
            result = run_pull(pair, on_log=on_log)
            Clock.schedule_once(lambda dt: self._on_sync_done(pair, result, popup, None))

        Thread(target=worker, daemon=True).start()

    def test_remote_connection(self, remote_path: str):
        log_popup = SyncLogPopup()
        popup = Popup(title=f"Testing: {remote_path}", content=log_popup, size_hint=(0.9, 0.7), auto_dismiss=False)
        log_popup.popup = popup
        popup.open()

        def on_log(line):
            Clock.schedule_once(lambda dt: setattr(log_popup, "log_text", log_popup.log_text + line + "\n"))

        def worker():
            success, output = test_remote(remote_path, on_log=on_log)
            Clock.schedule_once(lambda dt: self._on_test_done(popup, success, output))

        Thread(target=worker, daemon=True).start()

    def _on_test_done(self, popup, success, output):
        popup.dismiss()
        result = SyncResult(success=success, raw_stdout=output)
        self.show_result(None, result)

    def show_result(self, pair: SyncPair, result: SyncResult):
        lines = []
        if result.success:
            lines.append("Sync completed successfully")
        else:
            lines.append("Sync failed")
        if result.copied_to_remote:
            lines.append(f"\nCopied to remote ({len(result.copied_to_remote)}):")
            for f in result.copied_to_remote:
                lines.append(f"  {f}")
        if result.copied_to_local:
            lines.append(f"\nCopied to local ({len(result.copied_to_local)}):")
            for f in result.copied_to_local:
                lines.append(f"  {f}")
        if result.conflicts:
            lines.append(f"\nConflicts ({len(result.conflicts)}):")
            for f in result.conflicts:
                lines.append(f"  {f}")
        if result.errors:
            lines.append(f"\nErrors ({len(result.errors)}):")
            for e in result.errors:
                lines.append(f"  {e}")

        log = result.raw_stdout.strip()
        if log:
            lines.append(f"\n--- stdout ---\n{log[:2000]}")
        log_err = result.raw_stderr.strip()
        if log_err:
            lines.append(f"\n--- stderr ---\n{log_err[:2000]}")

        if result.success and pair is not None:
            update_pair(pair)

        content = ResultPopup(result_text="\n".join(lines))
        popup = Popup(title="Sync Result", content=content, size_hint=(0.85, 0.6))
        content.popup = popup
        popup.open()


if __name__ == "__main__":
    BisyncApp().run()
