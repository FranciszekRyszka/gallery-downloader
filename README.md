# Gallery Downloader

A terminal-based ([Textual](https://textual.textualize.io/)) Python app for
downloading all images from a gallery page on CornPics.

- Scrapes every full-size image URL from a gallery
- Shows metadata (title, image count) before you commit
- Async downloads with retry, concurrency and **pause / resume**
- **Batch mode**: download many galleries from a list file (one URL per line)
- **Actress / model mode**: paste a model page URL to count *all* their
  galleries, then download every one (or just the first N) — saved into a
  folder named after the model
- **Choose the download folder** (defaults to `downloads/`)
- Optional **delay between photos** to rate-limit downloads
- Skips files already on disk (resume across restarts)
- Keeps a SQLite history of downloaded galleries

## Requirements

- Python 3.10+
- Dependencies in [`requirements.txt`](requirements.txt): `textual`,
  `beautifulsoup4`, `httpx`

## Run it (no install)

If you just want to use the app, grab **`GalleryDownloader.exe`** and
double-click it — no Python, no terminal commands, no setup. A console window
opens with the TUI inside. Downloaded galleries and the history database are
saved in `downloads/` and `logs/` folders next to the `.exe`.

Build the executable yourself with:

```powershell
./build.ps1
```

which produces `dist/GalleryDownloader.exe`. (It installs PyInstaller and the
runtime dependencies, then bundles everything into one file — see
[`GalleryDownloader.spec`](GalleryDownloader.spec).)

## Run from source

```bash
pip install -r requirements.txt
python main.py
```

There's a **single input box** — paste any of the three things below and press
**Preview**. The app auto-detects what you gave it, shows what it found, and
enables **Download**. **Pause** holds back new downloads (in-flight ones
finish); press it again to resume. Press **q** to quit.

**Single gallery** — paste a gallery URL. Preview fetches the title and image
count; Download saves to `<download folder>/<gallery title>/` (see **Options**).

**Batch (multiple galleries)** — paste the path to a local `.txt` file with one
gallery URL per line. Blank lines and lines starting with `#` are ignored, and
duplicate URLs are skipped:

```text
# my-list.txt
https://www.cornpics.com/galleries/example-one/
https://www.cornpics.com/galleries/example-two/
```

Preview reports how many URLs it loaded; Download parses and downloads each in
turn with `(i/N)` progress and a final summary. A URL that fails to parse is
logged and skipped — it won't abort the batch.

**All galleries of an actress / model** — paste a model page URL (e.g.
`…/cornstars/<name>/`). Preview pages through the site's listing API and
reports the total (e.g. *"Riley Reid — 1733 galleries"*); Download fetches them
all into `<download folder>/<model name>/<gallery title>/`. Set a **First N**
cap in Options first if you don't want the whole set.

**Options** (in the collapsible *Options* section; apply to whichever download
you start):

- **Download folder** — where files are saved. Single galleries and lists go
  into `<folder>/<gallery title>/`; model downloads add a `<model name>/`
  level. Leave blank to use the app's `downloads/` directory. `~` is expanded.
- **First N galleries** — in model mode, download only the first *N* galleries
  instead of all of them. Leave blank for all.
- **Delay between photos** — seconds to wait between each image request
  (a global rate limit, enforced across concurrent downloads). Leave blank or
  `0` for no delay. Useful to avoid hammering the server.

## Project structure

```text
gallery_downloader/
│── main.py                  # entry point → launches the TUI
│── app.py                   # Textual app: preview, download, pause, batch, model
│── paths.py                 # data locations (source vs. frozen .exe)
│── build.ps1                # one-command Windows build script
│── GalleryDownloader.spec   # PyInstaller build config
├── core/
│   ├── parser.py            # parse_gallery / fetch_model_galleries / read_url_list
│   └── downloader.py        # async downloads: concurrency, retry, resume, pause
├── db/
│   └── history.py           # SQLite history & download-state persistence
├── tui/                     # (reserved for additional TUI components)
├── logs/                    # history.db lives here at runtime
└── downloads/               # downloaded images (one folder per gallery)
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
   optional `asyncio.Event` gate provides pause/resume, and a `delay`
   parameter spaces out request starts as a global rate limit.
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
