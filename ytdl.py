#!/usr/bin/env python3
"""DZ-DL downloader for Termux: cookies + quality with size estimates + hacker-style UI."""
import os
import shutil
import sys
from yt_dlp import YoutubeDL

HOME = os.path.expanduser("~")
OUT_DIR = os.path.join(HOME, "storage", "downloads", "YT-DLP")
COOKIE_CANDIDATES = [
    os.path.join(HOME, "storage", "downloads", "cookies.txt"),
    os.path.join(HOME, "cookies.txt"),
]
COOKIE_COPY = os.path.join(HOME, ".ytdl_cookies.txt")
LEVELS = {"1": "low", "2": "mid", "3": "high"}
LEVEL_NAMES = {"low": "Lowest", "mid": "Medium", "high": "Highest"}

# ---------- hacker-style colours (ANSI) ----------
GREEN = "\033[92m"
CYAN = "\033[96m"
RED = "\033[91m"
YELLOW = "\033[93m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

BANNER = r"""
████  █████       ████  █
█   █    █        █   █ █
█   █   █   █████ █   █ █
█   █  █          █   █ █
████  █████       ████  █████
"""

def banner():
    print(GREEN + BANNER + RESET)
    print(CYAN + BOLD + "  [+] DZ-TERMUX DOWNLOADER // DZ-DL MODULE" + RESET)
    print(DIM + "  [~] cookies | quality | playlist | mp4 / mp3" + RESET)
    print(MAGENTA + "  " + "=" * 46 + RESET + "\n")

os.makedirs(OUT_DIR, exist_ok=True)

# ---------- cookies ----------
def find_cookies():
    for path in COOKIE_CANDIDATES:
        if os.path.isfile(path):
            return path
    return None

def prepare_cookies(path):
    """Copy the cookies file to a private location so the original is never modified."""
    if not path:
        return None
    try:
        shutil.copyfile(path, COOKIE_COPY)
        return COOKIE_COPY
    except OSError as e:
        print(RED + f"  Cannot read cookies file: {e}" + RESET)
        return None

# ---------- quality selection ----------
def pick_height(heights, level):
    if not heights:
        return None
    if level == "low":
        return heights[0]
    if level == "high":
        return heights[-1]
    return heights[len(heights) // 2]

def make_selector(level, holder):
    """Per-video format selector: looks at the heights that video really offers."""
    def selector(ctx):
        heights = sorted({
            int(f["height"])
            for f in ctx["formats"]
            if f.get("height") and f.get("vcodec") != "none"
        })
        h = pick_height(heights, level)
        if h is None:
            spec = "wv*+ba/w" if level == "low" else "bv*+ba/b"
        else:
            spec = f"bv*[height<={h}]+ba/b[height<={h}]"
            avail = ", ".join(f"{x}p" for x in heights)
            print(GREEN + f"\n  [>] Available: {avail}  ->  using {h}p" + RESET)
        return holder["ydl"].build_format_selector(spec)(ctx)
    return selector

def fmt_size(n):
    """Human-readable size: 12.5 MB / 1.2 GB / -- if unknown."""
    if not n:
        return "--"
    if n >= 1 << 30:
        return f"{n / (1 << 30):.2f} GB"
    if n >= 1 << 20:
        return f"{n / (1 << 20):.1f} MB"
    if n >= 1 << 10:
        return f"{n / (1 << 10):.0f} KB"
    return f"{n} B"

def estimate_sizes(url, cookies):
    """Fetch video info once and estimate download size per quality level.

    Returns {level: (height, size_bytes or None)}. Real sizes vary per video —
    these are estimates from yt-dlp's format metadata, not guarantees.
    """
    opts = {"quiet": True, "no_warnings": True, "noplaylist": True}
    if cookies:
        opts["cookiefile"] = cookies
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    formats = info.get("formats", []) or []
    heights = sorted({
        int(f["height"])
        for f in formats
        if f.get("height") and f.get("vcodec") != "none"
    })
    result = {}
    for level in ("low", "mid", "high"):
        h = pick_height(heights, level)
        if h is None:
            result[level] = (None, None)
            continue
        vids = [f for f in formats
                if f.get("height") and f.get("vcodec") != "none"
                and int(f["height"]) <= h]
        auds = [f for f in formats
                if f.get("vcodec") == "none" and f.get("acodec") != "none"]
        size = 0
        if vids:
            v = max(vids, key=lambda f: (f.get("filesize") or f.get("filesize_approx") or 0))
            size += v.get("filesize") or v.get("filesize_approx") or 0
        if auds:
            a = max(auds, key=lambda f: (f.get("filesize") or f.get("filesize_approx") or 0))
            size += a.get("filesize") or a.get("filesize_approx") or 0
        result[level] = (h, size if size > 0 else None)
    return result

# ---------- download ----------
def progress(d):
    if d["status"] == "downloading":
        done = d.get("downloaded_bytes") or 0
        total = d.get("total_bytes") or d.get("total_bytes_estimate")
        pct = f"{done * 100 / total:5.1f}%" if total else "  ...  "
        speed = d.get("speed")
        spd = f"{speed / 1048576:5.2f} MiB/s" if speed else "    --    "
        eta = d.get("eta")
        eta_s = f"{int(eta) // 60:02d}:{int(eta) % 60:02d}" if eta is not None else "--:--"
        print(GREEN + f"\r  [DL] {pct}  {spd}  ETA {eta_s}   " + RESET, end="", flush=True)
    elif d["status"] == "finished":
        print(YELLOW + "\n  [~] Download finished, post-processing..." + RESET)

def build_opts(mode, level, playlist, cookies, holder):
    if playlist:
        tmpl = "%(playlist_title)s/%(playlist_index)03d - %(title).150s.%(ext)s"
    else:
        tmpl = "%(title).150s [%(id)s].%(ext)s"
    opts = {
        "outtmpl": os.path.join(OUT_DIR, tmpl),
        "noplaylist": not playlist,
        "retries": 10,
        "fragment_retries": 10,
        "continuedl": True,
        "no_warnings": True,
        "quiet": True,
        "progress_hooks": [progress],
        "ignoreerrors": playlist,
    }
    if cookies:
        opts["cookiefile"] = cookies
    if mode == "audio":
        opts["format"] = "bestaudio/best"
        opts["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ]
    else:
        opts["format"] = make_selector(level, holder)
        opts["merge_output_format"] = "mp4"
    return opts

# ---------- menu input: b = back, q = quit ----------
BACK = "BACK"
QUIT = "QUIT"

def menu(prompt, valid):
    """Prompt that understands b = back, q = quit. Returns value, BACK, or QUIT."""
    while True:
        v = input(prompt).strip().lower()
        if v == "b":
            return BACK
        if v == "q":
            return QUIT
        if v in valid:
            return v
        print(RED + "  Invalid choice, try again." + RESET)

def main():
    banner()
    print(f"  Save to : {OUT_DIR}")
    cookies_src = find_cookies()
    print(f"  Cookies : {cookies_src or 'none (put cookies.txt in your Download folder)'}\n")

    first = sys.argv[1] if len(sys.argv) > 1 else None
    while True:  # URL loop
        raw = first or input(CYAN + "URL (c = set cookies, q = quit): " + RESET).strip()
        first = None
        cmd = raw.lower()
        if cmd == "q":
            break
        if cmd == "c":
            p = input("Cookies file path (empty = no cookies): ").strip()
            if not p:
                cookies_src = None
                print("  Cookies disabled.\n")
            else:
                p = os.path.abspath(os.path.expanduser(p))
                if os.path.isfile(p):
                    cookies_src = p
                    print(GREEN + f"  [+] Using cookies: {p}\n" + RESET)
                else:
                    print(RED + "  File not found.\n" + RESET)
            continue
        if not raw:
            continue
        url = raw

        # Cookies prepared early so size estimates work for restricted videos too.
        cookies = prepare_cookies(cookies_src)

        # Per-URL wizard: mode -> quality -> playlist -> download.
        # b = back to previous step, q = quit program.
        stage = "mode"
        mode = None
        level = "high"
        sizes = None  # cached per URL so back-and-forth doesn't re-fetch
        while stage != "done":
            if stage == "mode":
                print(CYAN + "\n  1) Video (mp4)\n  2) Audio (mp3)" + RESET)
                print(DIM + "  b) Back   q) Quit" + RESET)
                r = menu("  Choose [1/2/b/q]: ", {"1", "2"})
                if r == BACK:
                    break  # back to URL prompt
                if r == QUIT:
                    print("\nBye.")
                    return
                mode = "video" if r == "1" else "audio"
                stage = "quality" if mode == "video" else "playlist"
            elif stage == "quality":
                if sizes is None:
                    print(YELLOW + "\n  [~] Fetching video info for size estimates..." + RESET)
                    try:
                        sizes = estimate_sizes(url, cookies)
                    except Exception as e:
                        print(RED + f"  Could not fetch sizes: {e}" + RESET)
                        sizes = {}
                print(CYAN + "\n  Quality:" + RESET)
                for k, lv in LEVELS.items():
                    tag = ""
                    if sizes.get(lv):
                        h, sz = sizes[lv]
                        parts = []
                        if h:
                            parts.append(f"{h}p")
                        if sz:
                            parts.append(f"~{fmt_size(sz)}")
                        if parts:
                            tag = "  (" + ", ".join(parts) + ")"
                    print(f"  {k}) {LEVEL_NAMES[lv]}{tag}")
                print(DIM + "  b) Back   q) Quit" + RESET)
                r = menu("  Choose [1-3/b/q]: ", set(LEVELS))
                if r == BACK:
                    stage = "mode"
                    continue
                if r == QUIT:
                    print("\nBye.")
                    return
                level = LEVELS[r]
                stage = "playlist"
            elif stage == "playlist":
                print(DIM + "  b) Back   q) Quit" + RESET)
                r = menu("  Download the whole playlist? [y/n/b/q]: ", {"y", "n"})
                if r == BACK:
                    stage = "quality" if mode == "video" else "mode"
                    continue
                if r == QUIT:
                    print("\nBye.")
                    return
                playlist = (r == "y")
                stage = "download"
            elif stage == "download":
                holder = {}
                try:
                    with YoutubeDL(build_opts(mode, level, playlist, cookies, holder)) as ydl:
                        holder["ydl"] = ydl
                        ydl.download([url])
                    print(GREEN + "\n  [+] Done.\n" + RESET)
                except KeyboardInterrupt:
                    print(YELLOW + "\n  [!] Cancelled.\n" + RESET)
                except Exception as e:
                    print(RED + f"\n  [!] Error: {e}\n" + RESET)
                stage = "done"
        # stage loop ended -> back to URL prompt

if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nBye.")
