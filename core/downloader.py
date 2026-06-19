"""Async image downloader with retry and resume support."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable
from urllib.parse import unquote, urlsplit

import httpx

from .parser import DEFAULT_HEADERS

ProgressCallback = Callable[["DownloadResult"], Awaitable[None] | None]


@dataclass
class DownloadResult:
    """Outcome of a single image download."""

    url: str
    path: Path | None
    ok: bool
    skipped: bool = False
    error: str | None = None


def _filename_for(url: str) -> str:
    name = os.path.basename(unquote(urlsplit(url).path))
    return name or "image"


async def _download_one(
    client: httpx.AsyncClient,
    url: str,
    dest_dir: Path,
    *,
    retries: int,
) -> DownloadResult:
    target = dest_dir / _filename_for(url)

    # Resume support: skip files that already exist with content.
    if target.exists() and target.stat().st_size > 0:
        return DownloadResult(url=url, path=target, ok=True, skipped=True)

    last_error: str | None = None
    for attempt in range(1, retries + 1):
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            tmp = target.with_suffix(target.suffix + ".part")
            tmp.write_bytes(resp.content)
            tmp.replace(target)
            return DownloadResult(url=url, path=target, ok=True)
        except (httpx.HTTPError, OSError) as exc:
            last_error = str(exc)
            if attempt < retries:
                await asyncio.sleep(min(2 ** attempt, 10))

    return DownloadResult(url=url, path=None, ok=False, error=last_error)


async def download_images(
    urls: list[str],
    dest_dir: str | os.PathLike[str],
    *,
    concurrency: int = 5,
    retries: int = 3,
    timeout: float = 60.0,
    on_progress: ProgressCallback | None = None,
) -> list[DownloadResult]:
    """Download ``urls`` into ``dest_dir`` concurrently.

    Returns one :class:`DownloadResult` per URL. Already-downloaded files are
    skipped (resume), and each download is retried up to ``retries`` times.
    """
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)

    semaphore = asyncio.Semaphore(concurrency)
    results: list[DownloadResult] = []

    async with httpx.AsyncClient(
        headers=DEFAULT_HEADERS, timeout=timeout, follow_redirects=True
    ) as client:

        async def worker(u: str) -> None:
            async with semaphore:
                result = await _download_one(client, u, dest, retries=retries)
            results.append(result)
            if on_progress is not None:
                outcome = on_progress(result)
                if asyncio.iscoroutine(outcome):
                    await outcome

        await asyncio.gather(*(worker(u) for u in urls))

    return results
