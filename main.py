"""Entry point for the gallery downloader."""

from __future__ import annotations

from app import GalleryDownloaderApp


def main() -> None:
    GalleryDownloaderApp().run()


if __name__ == "__main__":
    main()
