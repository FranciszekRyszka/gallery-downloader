# Gallery Downloader

A terminal-based ([Textual](https://textual.textualize.io/)) Python app for
downloading all images from a gallery page on CornPics.

- Scrapes every full-size image URL from a gallery
- Shows metadata (title, image count) before you commit
- Async downloads with retry, concurrency and **pause / resume**
- Skips files already on disk (resume across restarts)
- Keeps a SQLite history of downloaded galleries

## Requirements

- Python 3.10+
- Dependencies in [`requirements.txt`](requirements.txt): `textual`,
  `beautifulsoup4`, `httpx`

## Install

```bash
pip install -r requirements.txt
```

## Usage

Run the TUI:

```bash
python main.py
```

Then:

1. Paste a gallery URL into the input box.
2. Press **Preview** to fetch the title and image count.
3. Press **Download** to start. Images are saved to
   `downloads/<gallery title>/`.
4. Press **Pause** to hold back new downloads (in-flight ones finish);
   press **Resume** to continue. Press **q** to quit.

## Project structure

```text
gallery_downloader/
│── main.py            # entry point → launches the TUI
│── app.py             # Textual app: input, preview, progress, pause
├── core/
│   ├── parser.py      # httpx fetch + BeautifulSoup → Gallery(title, urls)
│   └── downloader.py  # async downloads: concurrency, retry, resume, pause
├── db/
│   └── history.py     # SQLite history & download-state persistence
├── tui/               # (reserved for additional TUI components)
├── logs/              # history.db lives here at runtime
└── downloads/         # downloaded images (one folder per gallery)
```

## How it works

1. **Parse** — `core.parser.parse_gallery(url)` fetches the page and extracts
   the title and full-size image URLs. CornPics renders each image as an
   `<a class="rel-link">` pointing at its CDN (`cdni.cornpics.com`); those
   anchors are targeted first, with generic `<a>` and `<img>` fallbacks for
   other markup.
2. **Download** — `core.downloader.download_images(...)` fetches images
   concurrently with a semaphore, retries with backoff, and writes via a
   `.part` temp file. Existing non-empty files are skipped (resume). An
   optional `asyncio.Event` gate provides pause/resume.
3. **History** — `db.history.History` records each gallery (title, dest,
   counts, status) in `logs/history.db`.

## Notes

- The image-URL selectors in `core/parser.py` are tuned for CornPics' current
  markup; if the site changes, adjust `_extract_image_urls`.
- Pause is *soft*: downloads already in flight when you pause will finish
  (up to the concurrency limit) before new ones are held back.

## Planned

Proxy support · batch downloads · ZIP export · metadata export
