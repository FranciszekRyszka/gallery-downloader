# Blueprint: Terminal Python Gallery Downloader (Textual TUI)

## Project Overview

A terminal-based Python application for downloading all images from a
gallery page on PornPics.

Features: - Scrapes all image URLs from the gallery - Displays metadata
(title, image count) - Lets the user choose download location -
Downloads images with progress tracking - Supports pause/resume - Logs
failed downloads - Keeps a history of downloaded galleries

## Tech Stack

-   Python
-   Textual
-   BeautifulSoup
-   httpx (async HTTP client — required for the async downloads in
    `downloader.py`; `requests` is synchronous and cannot do async I/O)
-   SQLite

## Project Structure

``` text
gallery_downloader/
│── main.py
│── app.py
├── tui/
├── core/
│   ├── parser.py
│   └── downloader.py
├── db/
│   └── history.py
├── logs/
└── downloads/
```

## Core Modules

### core/parser.py

Responsible for: - Fetching HTML - Extracting gallery title - Extracting
image URLs

### core/downloader.py

Responsible for: - Async downloads - Retry logic - Resume support

### db/history.py

Responsible for: - SQLite history storage - Download state persistence

## Application Flow

1.  User inputs gallery URL
2.  Validate URL
3.  Parse gallery
4.  Show preview
5.  Start downloads
6.  Save history

## Future Features

-   Proxy support
-   Batch downloads
-   ZIP export
-   Metadata export
