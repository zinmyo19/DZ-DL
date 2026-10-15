# DZ-DL — DZ-TERMUX Downloader

A lightweight **yt-dlp** downloader for Termux with a hacker-style terminal UI.

Two scripts, one tool:

| File | What it does |
|---|---|
| `termux-url-opener` | Share any URL to Termux → menu: Best video / File via aria2 / MP3 / ytdl module / Quit |
| `ytdl.py` | The ytdl module: Video (MP4) / Audio (MP3), quality with size estimates, cookies, playlists, Back + Quit navigation |

## Features

- **Quality with real size estimates** — Lowest / Medium / Highest, with the actual resolution and estimated file size shown before you download
- **Cookies support** — drop a `cookies.txt` in your Download folder (or set one with `c` at the URL prompt) for age-restricted / private videos
- **Playlists** — download a single video or the whole playlist
- **Back + Quit everywhere** — `b` goes back one step, `q` quits, in every menu
- **Downloads to** `~/storage/downloads/YT-DLP`

## Install

```sh
pkg install python yt-dlp ffmpeg aria2
pip install -U yt-dlp
```

Copy the scripts into place:

```sh
# ytdl module
cat > ~/ytdl.py
# (paste ytdl.py, then Ctrl+D)

# URL opener (runs when you Share a link to Termux)
mkdir -p ~/bin
cat > ~/bin/termux-url-opener
# (paste termux-url-opener, then Ctrl+D)
chmod +x ~/bin/termux-url-opener
```

## Use

**Share a link to Termux** → the opener menu appears → pick `4` for the ytdl module.

Or run the module directly:

```sh
python ~/ytdl.py
```

Flow: paste URL → Video / Audio → Quality → Playlist? → downloads.

- At the URL prompt: `c` = set a cookies file, `q` = quit
- In every menu: `b` = back, `q` = quit

## Cookies

Export `cookies.txt` from your browser (e.g. with a cookies extension) and put it in your Download folder. The script copies it to a private location before use — your original file is never modified.

## License

GPL v3 — see [LICENSE](LICENSE). Free to use and share; anyone who distributes it (modified or not) must keep it open under the same license — it cannot be closed up and resold as a proprietary product.
