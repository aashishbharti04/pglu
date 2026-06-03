"""Kivy UI for Pglu."""
from __future__ import annotations

import os
import sys
import threading
import traceback
from pathlib import Path
from typing import Optional

from kivy.app import App
from kivy.clock import mainthread
from kivy.lang import Builder
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.screenmanager import Screen, ScreenManager, FadeTransition
from kivy.core.clipboard import Clipboard
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.utils import platform

from app.engine import DownloadJob, ProgressEvent, MediaInfo, engine_for
from app.ui.storage import (
    default_download_dir,
    request_android_permissions,
    write_crash_log,
)


KV_PATH = Path(__file__).with_name("app.kv")


def _format_duration(seconds: Optional[float]) -> str:
    if not seconds:
        return ""
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _format_count(n: Optional[int]) -> str:
    if not n:
        return ""
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)


# -----------------------------------------------------------------------------

class HomeScreen(Screen):
    def paste_clipboard(self) -> None:
        text = Clipboard.paste() or ""
        self.ids.url_input.text = text.strip()

    def fetch_info(self, url: str) -> None:
        url = (url or "").strip()
        if not url:
            self.ids.status_lbl.text = "Paste a URL first."
            return
        if not (url.startswith("http://") or url.startswith("https://")):
            self.ids.status_lbl.text = "URL must start with http:// or https://"
            return

        self.ids.status_lbl.text = "Fetching info..."
        threading.Thread(target=self._fetch_worker, args=(url,), daemon=True).start()

    def _fetch_worker(self, url: str) -> None:
        try:
            engine = engine_for(url)
            info = engine.fetch_info(url)
            self._on_fetched(info)
        except Exception as e:  # noqa: BLE001
            self._on_fetch_error(str(e))

    @mainthread
    def _on_fetched(self, info: MediaInfo) -> None:
        self.ids.status_lbl.text = ""
        app = App.get_running_app()
        app.show_info(info)

    @mainthread
    def _on_fetch_error(self, msg: str) -> None:
        # Trim noisy yt-dlp prefixes
        if "ERROR:" in msg:
            msg = msg.split("ERROR:", 1)[1].strip()
        self.ids.status_lbl.text = f"Error: {msg[:200]}"


# -----------------------------------------------------------------------------

class InfoScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self._info: Optional[MediaInfo] = None
        self._format_by_label: dict[str, str] = {}

    def populate(self, info: MediaInfo) -> None:
        self._info = info

        self.title_lbl.text = info.title or "(no title)"
        meta_bits = []
        if info.uploader:
            meta_bits.append(info.uploader)
        if info.duration:
            meta_bits.append(_format_duration(info.duration))
        if info.view_count:
            meta_bits.append(f"{_format_count(info.view_count)} views")
        if info.like_count:
            meta_bits.append(f"{_format_count(info.like_count)} likes")
        self.meta_lbl.text = "  .  ".join(meta_bits)

        self.tags_lbl.text = ("#" + "  #".join(info.tags[:15])) if info.tags else ""
        self.desc_lbl.text = (info.description or "")[:1500]
        self.thumb.source = info.thumbnail_url or ""

        # Build the format spinner. "Best available" is always first.
        labels = ["Best available"]
        self._format_by_label = {"Best available": ""}
        for f in info.formats:
            label = f.label
            # Disambiguate identical labels by appending the format_id.
            if label in self._format_by_label:
                label = f"{label} [{f.format_id}]"
            labels.append(label)
            self._format_by_label[label] = f.format_id
        self.fmt_spinner.values = labels
        self.fmt_spinner.text = labels[0]

        # Reset progress
        self.progress.value = 0
        self.progress_lbl.text = ""
        self.download_btn.disabled = False
        self.download_btn.text = "Download"

        # Reset the explain panel for this new item.
        self.explain_lbl.text = ""
        self.explain_btn.disabled = False
        self.explain_btn.text = "Explain"

    def start_download(self) -> None:
        if self._info is None:
            return
        self.download_btn.disabled = True
        self.download_btn.text = "Downloading..."
        self.progress.value = 0
        self.progress_lbl.text = "Starting..."

        chosen_label = self.fmt_spinner.text
        format_id = self._format_by_label.get(chosen_label) or None
        audio_only = bool(self.audio_chk.active)

        threading.Thread(
            target=self._download_worker,
            args=(self._info, format_id, audio_only),
            daemon=True,
        ).start()

    def _download_worker(self, info: MediaInfo, format_id: Optional[str], audio_only: bool) -> None:
        try:
            engine = engine_for(info.url)
            out = default_download_dir()
            job = DownloadJob(
                url=info.url,
                output_dir=out,
                format_id=format_id,
                audio_only=audio_only,
            )
            engine.download(job, info=info, on_progress=self._on_progress)
        except Exception as e:  # noqa: BLE001
            self._on_progress(ProgressEvent(kind="error", message=str(e)))

    @mainthread
    def _on_progress(self, ev: ProgressEvent) -> None:
        if ev.kind == "start":
            self.progress_lbl.text = ev.message or "Starting..."
        elif ev.kind == "progress":
            if ev.percent:
                self.progress.value = ev.percent
            parts = [f"{ev.percent:.1f}%"]
            if ev.speed:
                parts.append(ev.speed.strip())
            if ev.eta:
                parts.append(f"ETA {ev.eta.strip()}")
            if ev.message:
                parts.append(ev.message)
            self.progress_lbl.text = "  ".join(parts)
        elif ev.kind == "done":
            self.progress.value = 100
            self.progress_lbl.text = f"Saved to: {ev.file_path}"
            self.download_btn.disabled = False
            self.download_btn.text = "Download again"
        elif ev.kind == "error":
            self.progress_lbl.text = f"Error: {ev.message[:300]}"
            self.download_btn.disabled = False
            self.download_btn.text = "Retry"

    # ---- "Explain this video" (Gemini) -------------------------------------

    def explain(self) -> None:
        if self._info is None:
            return
        from app.ui.storage import get_gemini_api_key
        if not get_gemini_api_key():
            self._prompt_api_key()
            return
        self.explain_btn.disabled = True
        self.explain_btn.text = "Explaining..."
        self.explain_lbl.text = "[i]Fetching a clip and analyzing with Gemini (30-90s)...[/i]"
        threading.Thread(target=self._explain_worker, args=(self._info,), daemon=True).start()

    def _explain_worker(self, info: MediaInfo) -> None:
        try:
            from app.engine.analyzer import explain_url
            from app.ui.storage import cache_dir, get_gemini_api_key
            text = explain_url(
                info, info.url, get_gemini_api_key(), cache_dir(),
                on_status=self._explain_status,
            )
            self._on_explain_done(text)
        except Exception as e:  # noqa: BLE001
            self._on_explain_error(str(e))

    @mainthread
    def _explain_status(self, msg: str) -> None:
        self.explain_lbl.text = f"[i]{msg}[/i]"

    @mainthread
    def _on_explain_done(self, text: str) -> None:
        self.explain_lbl.text = "[b]What's in this video:[/b]\n" + text
        self.explain_btn.disabled = False
        self.explain_btn.text = "Explain again"

    @mainthread
    def _on_explain_error(self, msg: str) -> None:
        self.explain_lbl.text = f"[color=ff8866]Explain failed: {msg[:300]}[/color]"
        self.explain_btn.disabled = False
        self.explain_btn.text = "Explain"

    def _prompt_api_key(self) -> None:
        """First-run popup to paste a free Gemini key, then continue explaining."""
        show_api_key_popup(on_saved=self.explain)


# -----------------------------------------------------------------------------

class FileRow(BoxLayout):
    def __init__(self, file_path: Path, **kw):
        super().__init__(orientation="horizontal",
                         size_hint_y=None,
                         height=dp(56),
                         spacing=dp(6),
                         padding=(dp(8), dp(4)),
                         **kw)
        from kivy.graphics import Color, RoundedRectangle, Line
        with self.canvas.before:
            Color(0.102, 0.133, 0.173, 1)
            self._bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[11])
        with self.canvas.after:
            Color(1, 1, 1, 0.06)
            self._border = Line(rounded_rectangle=(self.x, self.y, self.width, self.height, 11), width=1.0)
        self.bind(pos=self._sync_bg, size=self._sync_bg)

        self.file_path = file_path
        size_str = ""
        try:
            size = file_path.stat().st_size
            for u in ["B", "KB", "MB", "GB"]:
                if size < 1024:
                    size_str = f"{size:.1f} {u}"
                    break
                size /= 1024
        except OSError:
            pass

        info = Label(
            text=f"{file_path.name}\n[size=11sp][color=aaaaaa]{size_str}[/color][/size]",
            markup=True,
            halign="left",
            valign="middle",
            color=(1, 1, 1, 1),
        )
        info.bind(size=lambda inst, val: setattr(inst, "text_size", val))
        self.add_widget(info)

        from kivy.uix.button import Button
        open_btn = Button(
            text="Open", size_hint_x=None, width=dp(74),
            background_normal="", background_down="",
            background_color=(0.231, 0.557, 1.0, 1), bold=True,
        )
        open_btn.bind(on_release=lambda *a: self._open())
        self.add_widget(open_btn)

    def _sync_bg(self, *_):
        self._bg.pos = self.pos
        self._bg.size = self.size
        self._border.rounded_rectangle = (self.x, self.y, self.width, self.height, 11)

    def _open(self) -> None:
        path = str(self.file_path)
        try:
            if platform == "android":
                from jnius import autoclass, cast  # type: ignore
                Intent = autoclass("android.content.Intent")
                Uri = autoclass("android.net.Uri")
                File = autoclass("java.io.File")
                PythonActivity = autoclass("org.kivy.android.PythonActivity")
                intent = Intent(Intent.ACTION_VIEW)
                intent.setDataAndType(Uri.fromFile(File(path)), "*/*")
                intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                cast("android.app.Activity", PythonActivity.mActivity).startActivity(intent)
            elif platform == "win":
                os.startfile(path)  # type: ignore[attr-defined]
            else:
                import subprocess
                subprocess.Popen(["xdg-open", path])
        except Exception:
            pass


class DownloadsScreen(Screen):
    def on_pre_enter(self, *_):
        self.refresh()

    def refresh(self) -> None:
        self.files_box.clear_widgets()
        out = default_download_dir()
        files: list[Path] = []
        for p in sorted(out.rglob("*"), key=lambda x: x.stat().st_mtime if x.exists() else 0, reverse=True):
            if p.is_file() and p.suffix.lower() not in {".json", ".part"}:
                files.append(p)

        if not files:
            self.files_box.add_widget(Label(
                text=f"No downloads yet.\nFiles will appear in:\n{out}",
                color=(0.7, 0.7, 0.75, 1),
                size_hint_y=None,
                height=dp(80),
            ))
            return
        for f in files[:200]:
            self.files_box.add_widget(FileRow(f))


# -----------------------------------------------------------------------------

_ICON_PATH = Path(__file__).resolve().parent.parent / "assets" / "icon.png"


def _build_error_screen(message: str) -> BoxLayout:
    """Fallback UI if the real screens fail to build. Shows the traceback
    instead of letting Android kill the process with no feedback."""
    root = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
    root.add_widget(Label(
        text="Pglu hit a startup error",
        font_size="20sp",
        bold=True,
        size_hint_y=None,
        height=dp(40),
        color=(1, 0.5, 0.4, 1),
    ))
    scroll = ScrollView()
    body = Label(
        text=message,
        font_size="12sp",
        color=(1, 1, 1, 1),
        size_hint_y=None,
        halign="left",
        valign="top",
    )
    body.bind(
        width=lambda inst, val: setattr(inst, "text_size", (val, None)),
        texture_size=lambda inst, val: setattr(inst, "height", val[1]),
    )
    scroll.add_widget(body)
    root.add_widget(scroll)
    return root


def show_api_key_popup(on_saved=None) -> None:
    """Themed modal to paste / update the free Gemini API key. If a non-empty
    key is saved, ``on_saved`` (if given) is called — used to auto-continue an
    Explain action right after the user enters their key."""
    from kivy.uix.popup import Popup
    from kivy.uix.textinput import TextInput
    from kivy.uix.button import Button
    from app.ui.storage import get_gemini_api_key, set_gemini_api_key

    box = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(12))
    box.add_widget(Label(
        text=("Paste your free Google Gemini API key.\n"
              "Get one at aistudio.google.com/apikey\n"
              "It's stored only on this device."),
        size_hint_y=None, height=dp(74), halign="center", valign="middle",
        color=(0.85, 0.87, 0.92, 1),
    ))
    ti = TextInput(
        text=get_gemini_api_key(), multiline=False, password=True,
        size_hint_y=None, height=dp(46), hint_text="AIza...",
        background_normal="", background_active="",
        background_color=(0.102, 0.133, 0.173, 1),
        foreground_color=(1, 1, 1, 1), cursor_color=(0.231, 0.557, 1.0, 1),
        padding=[dp(12), dp(13)],
    )
    box.add_widget(ti)

    row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(48), spacing=dp(8))
    popup = Popup(
        title="Gemini API key", content=box, size_hint=(0.92, None), height=dp(264),
        title_color=(1, 1, 1, 1), separator_color=(0.231, 0.557, 1.0, 1),
        background_color=(0.039, 0.055, 0.078, 1),
    )

    def _save(*_):
        val = ti.text.strip()
        set_gemini_api_key(val)
        popup.dismiss()
        if val and on_saved:
            on_saved()

    cancel_btn = Button(text="Cancel", background_normal="", background_down="",
                        background_color=(0.16, 0.19, 0.25, 1))
    cancel_btn.bind(on_release=lambda *_: popup.dismiss())
    save_btn = Button(text="Save key", background_normal="", background_down="",
                      background_color=(0.231, 0.557, 1.0, 1), bold=True)
    save_btn.bind(on_release=_save)
    row.add_widget(cancel_btn)
    row.add_widget(save_btn)
    box.add_widget(row)
    popup.open()


class PgluApp(App):
    title = "Pglu"
    icon = str(_ICON_PATH) if _ICON_PATH.exists() else ""

    def build(self):
        try:
            Builder.load_file(str(KV_PATH))
            request_android_permissions()
            if platform != "android":
                Window.size = (380, 720)
                if _ICON_PATH.exists():
                    try:
                        Window.set_icon(str(_ICON_PATH))
                    except Exception:
                        pass

            sm = ScreenManager(transition=FadeTransition(duration=0.15))
            sm.add_widget(HomeScreen(name="home"))
            sm.add_widget(InfoScreen(name="info"))
            sm.add_widget(DownloadsScreen(name="downloads"))
            self.sm = sm
            return sm
        except Exception:
            tb = traceback.format_exc()
            log_path = write_crash_log(tb)
            return _build_error_screen(
                f"Saved to:\n{log_path}\n\n{tb}"
            )

    def show_info(self, info: MediaInfo) -> None:
        info_screen: InfoScreen = self.sm.get_screen("info")  # type: ignore[assignment]
        info_screen.populate(info)
        self.sm.current = "info"

    def go_to(self, name: str) -> None:
        self.sm.current = name

    def open_settings(self) -> None:
        """Open the Gemini API-key modal from anywhere (e.g. the home 'Key' button)."""
        show_api_key_popup()


def _install_excepthook() -> None:
    """Catch uncaught exceptions and write them to a log file so the user can
    see *why* the app died instead of just watching it disappear."""
    prev = sys.excepthook

    def hook(exc_type, exc, tb):
        try:
            write_crash_log("".join(traceback.format_exception(exc_type, exc, tb)))
        except Exception:
            pass
        if prev:
            prev(exc_type, exc, tb)

    sys.excepthook = hook


def main() -> None:
    _install_excepthook()
    PgluApp().run()


if __name__ == "__main__":
    main()
