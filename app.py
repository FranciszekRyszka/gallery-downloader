"""Textual TUI for the gallery downloader."""

from __future__ import annotations

import asyncio
from pathlib import Path

from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    ProgressBar,
    RichLog,
)

from core.downloader import DownloadResult, download_images
from core.parser import Gallery, parse_gallery, read_url_list
from db.history import History

DOWNLOADS_DIR = Path(__file__).resolve().parent / "downloads"


class GalleryDownloaderApp(App):
    """Terminal UI: enter a URL, preview the gallery, download it."""

    TITLE = "Gallery Downloader"
    CSS = """
    #url_row, #list_row { height: auto; padding: 1 0 0 0; }
    #url, #list_file { width: 1fr; }
    #meta { padding: 1 0; color: $text-muted; }
    ProgressBar { margin: 1 0; }
    RichLog { height: 1fr; border: round $primary; }
    """
    BINDINGS = [("q", "quit", "Quit")]

    def __init__(self) -> None:
        super().__init__()
        self.gallery: Gallery | None = None
        self.history = History()
        self._pause_event: asyncio.Event | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll():
            with Horizontal(id="url_row"):
                yield Input(placeholder="Gallery URL…", id="url")
                yield Button("Preview", id="preview", variant="primary")
                yield Button("Download", id="download", disabled=True)
                yield Button("Pause", id="pause", disabled=True)
            with Horizontal(id="list_row"):
                yield Input(
                    placeholder="…or path to a .txt file (one URL per line)",
                    id="list_file",
                )
                yield Button("Download List", id="download_list")
            yield Label("Enter a gallery URL to begin.", id="meta")
            yield ProgressBar(id="progress", total=100, show_eta=False)
            yield RichLog(id="log", highlight=True, markup=True)
        yield Footer()

    def on_unmount(self) -> None:
        self.history.close()

    def _log(self, message: str) -> None:
        self.query_one("#log", RichLog).write(message)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "preview":
            url = self.query_one("#url", Input).value.strip()
            if not url:
                self._log("[red]Please enter a URL.[/red]")
                return
            self.preview(url)
        elif event.button.id == "download":
            if self.gallery:
                self.download(self.gallery)
        elif event.button.id == "download_list":
            path = self.query_one("#list_file", Input).value.strip()
            if not path:
                self._log("[red]Please enter a path to a URL list file.[/red]")
                return
            self.download_list(path)
        elif event.button.id == "pause":
            self._toggle_pause(event.button)

    def _toggle_pause(self, button: Button) -> None:
        if self._pause_event is None:
            return
        if self._pause_event.is_set():
            self._pause_event.clear()
            button.label = "Resume"
            button.variant = "warning"
            self._log("[yellow]Paused.[/yellow] Finishing in-flight downloads…")
        else:
            self._pause_event.set()
            button.label = "Pause"
            button.variant = "default"
            self._log("[green]Resumed.[/green]")

    @work(exclusive=True, thread=True)
    def preview(self, url: str) -> None:
        self._log(f"Parsing [cyan]{url}[/cyan] …")
        try:
            gallery = parse_gallery(url)
        except Exception as exc:  # noqa: BLE001 - surface any parse failure
            self.call_from_thread(self._log, f"[red]Parse failed:[/red] {exc}")
            return
        self.gallery = gallery
        self.call_from_thread(self._on_preview_ready, gallery)

    def _on_preview_ready(self, gallery: Gallery) -> None:
        self.query_one("#meta", Label).update(
            f"[b]{gallery.title}[/b] — {gallery.count} images"
        )
        self._log(f"Found [green]{gallery.count}[/green] images.")
        self.query_one("#download", Button).disabled = gallery.count == 0

    def _begin_run(self) -> None:
        """Set up shared state for a download run (single or batch)."""
        # Pause gate: set = running.
        self._pause_event = asyncio.Event()
        self._pause_event.set()
        pause_button = self.query_one("#pause", Button)
        pause_button.disabled = False
        pause_button.label = "Pause"
        pause_button.variant = "default"
        self.query_one("#download", Button).disabled = True
        self.query_one("#download_list", Button).disabled = True

    def _end_run(self) -> None:
        """Tear down run state and restore the controls."""
        pause_button = self.query_one("#pause", Button)
        pause_button.disabled = True
        pause_button.label = "Pause"
        pause_button.variant = "default"
        self._pause_event = None
        self.query_one("#download_list", Button).disabled = False
        has_gallery = self.gallery is not None and self.gallery.count > 0
        self.query_one("#download", Button).disabled = not has_gallery

    async def _download_gallery(self, gallery: Gallery) -> tuple[int, int]:
        """Download one gallery, update history, return (downloaded, failed).

        Assumes a run is active (``self._pause_event`` set up by the caller).
        """
        dest = DOWNLOADS_DIR / _safe_name(gallery.title)
        done = 0
        failed = 0
        progress = self.query_one("#progress", ProgressBar)
        progress.update(total=gallery.count or 1, progress=0)

        gallery_id = self.history.record_start(
            gallery.url, gallery.title, str(dest), gallery.count
        )
        self._log(
            f"Downloading [b]{gallery.title}[/b] "
            f"({gallery.count}) → [cyan]{dest}[/cyan]"
        )

        # This worker runs on the app's event-loop thread, and the
        # download_images coroutine calls on_progress from that same thread,
        # so we update widgets directly (call_from_thread is only valid from
        # a *different* thread).
        def on_progress(result: DownloadResult) -> None:
            nonlocal done, failed
            if result.ok:
                done += 1
            else:
                failed += 1
                self._log(f"[red]Failed:[/red] {result.url} ({result.error})")
            progress.advance(1)

        await download_images(
            gallery.image_urls,
            dest,
            on_progress=on_progress,
            pause_event=self._pause_event,
        )
        self.history.update_progress(gallery_id, downloaded=done, failed=failed)
        self.history.record_finish(
            gallery_id, "complete" if not failed else "complete_with_errors"
        )
        self._log(f"[green]✓[/green] {gallery.title}: {done} ok, {failed} failed")
        return done, failed

    @work(exclusive=True)
    async def download(self, gallery: Gallery) -> None:
        self._begin_run()
        try:
            done, failed = await self._download_gallery(gallery)
        finally:
            self._end_run()
        self._log(f"[green]Done.[/green] {done} downloaded, {failed} failed.")

    @work(exclusive=True)
    async def download_list(self, path: str) -> None:
        try:
            urls = read_url_list(path)
        except OSError as exc:
            self._log(f"[red]Could not read list:[/red] {exc}")
            return
        if not urls:
            self._log("[red]No URLs found in file.[/red]")
            return
        self._log(
            f"Loaded [green]{len(urls)}[/green] URL(s) from [cyan]{path}[/cyan]."
        )

        self._begin_run()
        total_done = 0
        total_failed = 0
        try:
            for i, url in enumerate(urls, start=1):
                self._log(f"[b]({i}/{len(urls)})[/b] Parsing [cyan]{url}[/cyan] …")
                try:
                    # parse_gallery does blocking I/O; keep the loop responsive.
                    gallery = await asyncio.to_thread(parse_gallery, url)
                except Exception as exc:  # noqa: BLE001 - surface & continue
                    self._log(f"[red]Parse failed:[/red] {url} ({exc})")
                    continue
                done, failed = await self._download_gallery(gallery)
                total_done += done
                total_failed += failed
        finally:
            self._end_run()
        self._log(
            f"[green]Batch done.[/green] {total_done} downloaded, "
            f"{total_failed} failed across {len(urls)} galleries."
        )


def _safe_name(name: str) -> str:
    keep = "-_ "
    cleaned = "".join(c for c in name if c.isalnum() or c in keep).strip()
    return (cleaned or "gallery")[:100]


if __name__ == "__main__":
    GalleryDownloaderApp().run()
