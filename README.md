# Gallery Downloader

A terminal-based ([Textual](https://textual.textualize.io/)) Python app for
downloading all images from a gallery page on CornPics.

- Scrapes every full-size image URL from a gallery
- Shows metadata (title, image count) before you commit
- Async downloads with retry, concurrency and **pause / resume**
- **Batch mode**: download many galleries from a list file (one URL per line)
- **Actress / model mode**: paste a model page URL to count *all* their
  galleries, then download every one
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

**Single gallery:**

1. Paste a gallery URL into the input box.
2. Press **Preview** to fetch the title and image count.
3. Press **Download** to start. Images are saved to
   `downloads/<gallery title>/`.
4. Press **Pause** to hold back new downloads (in-flight ones finish);
   press **Resume** to continue. Press **q** to quit.

**Batch (multiple galleries):**

1. Create a text file with one gallery URL per line. Blank lines and lines
   starting with `#` are ignored, and duplicate URLs are skipped:

   ```text
   # my-list.txt
   https://www.cornpics.com/galleries/example-one/
   https://www.cornpics.com/galleries/example-two/
   ```

2. Enter the path to that file in the second input box.
3. Press **Download List**. Each gallery is parsed and downloaded in turn,
   with `(i/N)` progress and a final summary. A URL that fails to parse is
   logged and skipped — it won't abort the batch. **Pause** applies across the
   whole run.

**All galleries of an actress / model:**

1. Paste a model page URL (e.g. `…/cornstars/<name>/`) into the third input.
2. Press **Count Galleries**. The app pages through the site's listing API
   and reports the total (e.g. *"Riley Reid: 1733 galleries"*).
3. Press **Download All** to fetch every gallery, using the same sequential
   batch engine (progress, skip-on-parse-error, pause/resume all apply).

## Project structure

```text
gallery_downloader/
│── main.py            # entry point → launches the TUI
│── app.py             # Textual app: preview, download, pause, batch, model
├── core/
│   ├── parser.py      # parse_gallery / fetch_model_galleries / read_url_list
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

Batch mode reads URLs with `core.parser.read_url_list(path)` and runs the
same parse → download steps for each gallery in sequence.

Actress / model mode uses `core.parser.fetch_model_galleries(url)`, which
pages through the site's listing endpoint (`/search/srch.php`, the same API
the page's infinite scroll calls) to enumerate every gallery URL, then feeds
that list into the batch engine.

## Notes

- The image-URL selectors in `core/parser.py` are tuned for CornPics' current
  markup; if the site changes, adjust `_extract_image_urls`.
- Pause is *soft*: downloads already in flight when you pause will finish
  (up to the concurrency limit) before new ones are held back.

## Planned

Proxy support · ZIP export · metadata export
