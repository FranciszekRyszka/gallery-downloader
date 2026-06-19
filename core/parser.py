"""Gallery parsing.

Fetches a gallery page and extracts its title and the list of full-size
image URLs.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}

_IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".gif")


@dataclass
class Gallery:
    """Parsed gallery metadata."""

    url: str
    title: str
    image_urls: list[str] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.image_urls)


def fetch_html(url: str, *, timeout: float = 30.0) -> str:
    """Fetch the raw HTML of a page."""
    resp = httpx.get(
        url, headers=DEFAULT_HEADERS, timeout=timeout, follow_redirects=True
    )
    resp.raise_for_status()
    return resp.text


def _extract_title(soup: BeautifulSoup) -> str:
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    h1 = soup.find("h1")
    if h1:
        return h1.get_text(strip=True)
    return "Untitled gallery"


def _extract_image_urls(soup: BeautifulSoup, base_url: str) -> list[str]:
    """Collect full-size image URLs from the gallery.

    PornPics renders each gallery image as an ``<a class="rel-link">`` that
    links straight to the full-resolution file on its CDN
    (``cdni.pornpics.com``). We target those anchors first to avoid picking up
    site chrome, ads and related-gallery thumbnails, then fall back to generic
    anchors and finally to ``<img>`` sources for other sites / markup changes.
    """
    urls: list[str] = []
    seen: set[str] = set()

    def add(candidate: str | None) -> None:
        if not candidate:
            return
        absolute = urljoin(base_url, candidate)
        if not absolute.lower().split("?")[0].endswith(_IMAGE_EXTS):
            return
        if absolute not in seen:
            seen.add(absolute)
            urls.append(absolute)

    # 1. PornPics: full-size images are anchors with class "rel-link".
    for a in soup.select("a.rel-link[href]"):
        add(a["href"])

    # 2. Fallback: any anchor pointing straight at an image file.
    if not urls:
        for a in soup.find_all("a", href=True):
            add(a["href"])

    # 3. Last resort: image tags (handles lazy-loaded data-src).
    if not urls:
        for img in soup.find_all("img"):
            add(img.get("data-src") or img.get("src"))

    return urls


def parse_gallery(url: str, *, timeout: float = 30.0) -> Gallery:
    """Fetch and parse a gallery page into a :class:`Gallery`."""
    html = fetch_html(url, timeout=timeout)
    soup = BeautifulSoup(html, "html.parser")
    title = _extract_title(soup)
    image_urls = _extract_image_urls(soup, url)
    return Gallery(url=url, title=title, image_urls=image_urls)


def read_url_list(path: str | os.PathLike[str]) -> list[str]:
    """Read gallery URLs from a text file, one URL per line.

    Blank lines and lines starting with ``#`` (comments) are ignored, and
    duplicate URLs are dropped while preserving order. Raises ``OSError`` if
    the file cannot be read.
    """
    urls: list[str] = []
    seen: set[str] = set()
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line not in seen:
            seen.add(line)
            urls.append(line)
    return urls
