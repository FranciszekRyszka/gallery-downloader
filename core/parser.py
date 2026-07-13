"""Gallery parsing.

Fetches a gallery page and extracts its title and the list of full-size
image URLs.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin, urlsplit

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

# Endpoint the site's own infinite-scroll uses to page through a listing
# (pornstar / category / tag / channel). Returns JSON: a list of galleries,
# each with a ``g_url`` (gallery page URL) and ``desc`` (title).
SEARCH_API = "https://www.pornpics.com/search/srch.php"

# Listing pages whose galleries can be enumerated via SEARCH_API. The last
# path segment is the search term (slug), e.g. /pornstars/riley-reid/.
_LISTING_SEGMENTS = ("pornstars", "channels", "tags", "categories")


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


@dataclass
class ModelPage:
    """A listing page (e.g. an actress) and all its gallery URLs."""

    url: str
    name: str
    gallery_urls: list[str] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.gallery_urls)


def is_listing_url(url: str) -> bool:
    """True if ``url`` looks like an enumerable listing (pornstar/tag/…)."""
    parts = [p for p in urlsplit(url).path.split("/") if p]
    return len(parts) >= 2 and parts[0] in _LISTING_SEGMENTS


def _listing_query_from_url(url: str) -> str:
    """Derive the search term from a listing URL's slug.

    ``/pornstars/riley-reid/`` -> ``riley reid``. The API matches this
    case-insensitively, so the slug-with-spaces form is sufficient.
    """
    parts = [p for p in urlsplit(url).path.split("/") if p]
    if len(parts) < 2:
        raise ValueError(f"Not a listing URL: {url!r}")
    return parts[-1].replace("-", " ")


def fetch_model_galleries(
    url: str,
    *,
    page_size: int = 1000,
    timeout: float = 60.0,
    max_galleries: int | None = None,
    on_page: Callable[[int], None] | None = None,
) -> ModelPage:
    """Enumerate every gallery URL for a listing page (e.g. an actress).

    Pages through :data:`SEARCH_API` with the listing's slug until a short
    page signals the end. ``on_page`` (if given) is called with the running
    total after each page so callers can show progress. ``max_galleries``
    caps the result. Raises ``httpx.HTTPError`` on network/HTTP failure.
    """
    query = _listing_query_from_url(url)
    headers = dict(DEFAULT_HEADERS)
    headers["Referer"] = "https://www.pornpics.com/"

    gallery_urls: list[str] = []
    seen: set[str] = set()
    offset = 0
    with httpx.Client(
        headers=headers, timeout=timeout, follow_redirects=True
    ) as client:
        while True:
            resp = client.get(
                SEARCH_API,
                params={
                    "q": query,
                    "lang": "en",
                    "limit": page_size,
                    "offset": offset,
                },
            )
            resp.raise_for_status()
            batch = resp.json()
            for item in batch:
                g_url = item.get("g_url")
                if g_url and g_url not in seen:
                    seen.add(g_url)
                    gallery_urls.append(g_url)
            if on_page is not None:
                on_page(len(gallery_urls))
            if len(batch) < page_size:
                break
            if max_galleries is not None and len(gallery_urls) >= max_galleries:
                break
            offset += page_size

    if max_galleries is not None:
        gallery_urls = gallery_urls[:max_galleries]
    return ModelPage(url=url, name=query.title(), gallery_urls=gallery_urls)


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
