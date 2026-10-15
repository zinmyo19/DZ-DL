#!/usr/bin/env python3
"""DZ-DL // yt-dlp front-end for Termux: cookies + size-aware quality menu + Back/Quit."""
import os
import shutil
import sys
import threading
import time

from yt_dlp import YoutubeDL
from yt_dlp.version import __version__ as YTDLP_VERSION

HOME = os.path.expanduser("~")
OUT_DIR = os.path.join(HOME, "storage", "downloads", "YT-DLP")
COOKIE_CANDIDATES = [
    os.path.join(HOME, "storage", "downloads", "cookies.txt"),
    os.path.join(HOME, "cookies.txt"),
]
COOKIE_COPY = os.path.join(HOME, ".ytdl_cookies.txt")

LEVEL_KEYS = {"1": "low", "2": "mid", "3": "high"}
LEVEL_NAMES = {"low": "Lowest", "mid": "Medium", "high": "Highest"}

BANNER = [
    r" ____ _____     ____  _     ",
    r"|  _ \__  /    |  _ \| |    ",
    r"| | | |/ /_____| | | | |    ",
    r"| |_| / /|_____| |_| | |___ ",
    r"|____/____|    |____/|_____|",
]

os.makedirs(OUT_DIR, exist_ok=True)
TTY = sys.stdout.isatty()


# ---------- ui helpers ----------

def paint(code, text):
    return f"\033[{code}m{text}\033[0m" if TTY else text


def green(t):
    return paint("92", t)


def cyan(t):
    return paint("96", t)


def yellow(t):
    return paint("93", t)


def red(t):
    return paint("91", t)


def dim(t):
    return paint("90", t)


def bold(t):
    return paint("1", t)


def pause(sec):
    if TTY:
        time.sleep(sec)


def short(path):
    return path.replace(HOME, "~", 1)


def trunc(text, n):
    text = text or "?"
    return text if len(text) <= n else text[: n - 1] + "~"


def say(tag, text, delay=0.005):
    """Print a tagged status line with a small typewriter effect."""
    tags = {"+": green("[+]"), "*": cyan("[*]"), "!": yellow("[!]"), "x": red("[x]")}
    sys.stdout.write(tags[tag] + " ")
    for ch in text:
        sys.stdout.write(ch)
        if TTY:
            sys.stdout.flush()
            time.sleep(delay)
    sys.stdout.write("\n")
    sys.stdout.flush()


class Spinner:
    FRAMES = "|/-\\"

    def __init__(self, text):
        self.text = text
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        i = 0
        while not self.stop.is_set():
            sys.stdout.write(f"\r{cyan('[*]')} {self.text} {self.FRAMES[i % 4]} ")
            sys.stdout.flush()
            i += 1
            time.sleep(0.1)

    def __enter__(self):
        if TTY:
            self.thread.start()
        return self

    def __exit__(self, *exc):
        self.stop.set()
        if TTY:
            self.thread.join()
            sys.stdout.write("\r" + " " * 50 + "\r")
            sys.stdout.flush()


def banner():
    if TTY:
        os.system("clear")
    print()
    for line in BANNER:
        print(green("  " + line))
        pause(0.05)
    print(cyan(bold("  [+] DZ-TERMUX DOWNLOADER // DZ-DL MODULE")))
    print(dim("  [~] cookies | quality | playlist | mp4 / mp3"))
    print(dim("  " + "-" * 46))


def boot(cookies_src):
    say("+", f"engine  : yt-dlp {YTDLP_VERSION}")
    if shutil.which("ffmpeg"):
        say("+", "ffmpeg  : ok")
    else:
        say("!", "ffmpeg  : missing (needed for merge + mp3)")
    say("+", f"output  : {short(OUT_DIR)}")
    if cookies_src:
        say("+", f"cookies : {short(cookies_src)}")
    else:
        say("!", "cookies : none (put cookies.txt in Download)")


# ---------- menu input: b = back, q = quit ----------
BACK = "BACK"
QUIT = "QUIT"


def menu(prompt, valid, default=None):
    """Prompt that understands b = back, q = quit. Returns value, BACK, or QUIT."""
    while True:
        v = input(f"{cyan('[?]')} {prompt}").strip().lower()
        if not v and default:
            return default
        if v == "b":
            return BACK
        if v == "q":
            return QUIT
        if v in valid:
            return v
        say("!", "invalid choice, try again")


def url_prompt():
    print(green("+--(") + bold("dz-dl") + green("@") + "termux" + green(")-[") + cyan("url") + green("]"))
    return input(green("+-$ ")).strip()


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
        say("x", f"cannot read cookies file: {e}")
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


def heights_of(formats):
    return sorted({
        int(f["height"])
        for f in formats
        if f.get("height") and f.get("vcodec") != "none"
    })


def spec_for(h):
    return f"bv*[height<={h}]+ba/b[height<={h}]"


def human_size(n):
    if not n:
        return "size unknown"
    n = float(n)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if n < 1024:
            return f"~{n:.0f}{unit}" if unit == "B" else f"~{n:.1f}{unit}"
        n /= 1024
    return f"~{n:.1f}TiB"


def entry_size(entry):
    """Total size of one selected format (video + audio when merged)."""
    if not entry:
        return None
    total = 0
    for part in entry.get("requested_formats") or [entry]:
        size = part.get("filesize") or part.get("filesize_approx")
        if not size:
            return None
        total += size
    return total


def fmt_duration(sec):
    sec = int(sec)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def probe(url, cookies):
    """Read video info and the size of the Lowest/Medium/Highest picks."""
    opts = {"quiet": True, "no_warnings": True, "noplaylist": True, "skip_download": True}
    if cookies:
        opts["cookiefile"] = cookies
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
        rows = None
        formats = (info or {}).get("formats") or []
        hs = heights_of(formats)
        if hs:
            ctx = {"formats": formats, "incomplete_formats": False}
            rows = {}
            for level in LEVEL_NAMES:
                h = pick_height(hs, level)
                entry = next(iter(ydl.build_format_selector(spec_for(h))(ctx)), None)
                rows[level] = (h, entry_size(entry))
        return info, rows


def show_menu(rows):
    print(f"{cyan('[?]')} quality:")
    for key, level in LEVEL_KEYS.items():
        if rows:
            h, size = rows[level]
            extra = f"{h:>5}p  {human_size(size)}"
        else:
            extra = dim("(picked per video)")
        print(f"    {green(key + ')')} {LEVEL_NAMES[level]:<8}{extra}")
    print(f"    {dim('b) Back   q) Quit')}")


def make_selector(level, holder):
    """Per-video format selector: looks at the heights that video really offers."""

    def selector(ctx):
        h = pick_height(heights_of(ctx["formats"]), level)
        if h is None:
            spec = "wv*+ba/w" if level == "low" else "bv*+ba/b"
        else:
            spec = spec_for(h)
            print(f"\n{cyan('[*]')} using {h}p")
        return holder["ydl"].build_format_selector(spec)(ctx)

    return selector


# ---------- download ----------

def progress(d):
    if d["status"] == "downloading":
        done = d.get("downloaded_bytes") or 0
        total = d.get("total_bytes") or d.get("total_bytes_estimate")
        frac = min(done / total, 1.0) if total else 0.0
        filled = int(frac * 20)
        bar = green("#" * filled) + dim("-" * (20 - filled))
        pct = f"{frac * 100:5.1f}%" if total else "  ... "
        speed = d.get("speed")
        spd = f"{speed / 1048576:5.2f}MiB/s" if speed else "    --    "
        eta = d.get("eta")
        eta_s = f"{int(eta) // 60:02d}:{int(eta) % 60:02d}" if eta is not None else "--:--"
        sys.stdout.write(f"\r  [{bar}] {pct} {spd} ETA {eta_s}  ")
        sys.stdout.flush()
    elif d["status"] == "finished":
        sys.stdout.write("\n")
        say("+", "stream complete", delay=0.002)


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
        "noprogress": True,
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


# ---------- per-URL wizard: mode -> playlist -> quality -> download ----------
# b = back to previous step, q = quit program.

def handle_url(url, cookies_src):
    cookies = prepare_cookies(cookies_src)
    has_playlist = "list=" in url or "playlist" in url
    stage = "mode"
    mode = None
    playlist = False
    level = "high"
    rows = None
    probed = False
    while stage != "done":
        if stage == "mode":
            print(f"{cyan('[?]')} mode:")
            print(f"    {green('1)')} Video (mp4)")
            print(f"    {green('2)')} Audio (mp3)")
            print(f"    {dim('b) Back   q) Quit')}")
            r = menu("select [1/2/b/q]: ", {"1", "2"})
            if r == BACK:
                return BACK
            if r == QUIT:
                return QUIT
            mode = "video" if r == "1" else "audio"
            stage = "playlist" if has_playlist else ("quality" if mode == "video" else "download")
        elif stage == "playlist":
            print(f"{cyan('[?]')} playlist:")
            print(f"    {green('1)')} Yes - whole playlist")
            print(f"    {green('2)')} No  - this video only")
            print(f"    {dim('b) Back   q) Quit')}")
            r = menu("select [1/2/b/q]: ", {"1", "2"})
            if r == BACK:
                stage = "mode"
                continue
            if r == QUIT:
                return QUIT
            playlist = (r == "1")
            stage = "quality" if (mode == "video" and not playlist) else "download"
        elif stage == "quality":
            if not probed:
                try:
                    with Spinner("scanning formats"):
                        info, rows = probe(url, cookies)
                    probed = True
                    if info:
                        say("+", f"title    : {trunc(info.get('title'), 40)}")
                        if info.get("duration"):
                            say("+", f"duration : {fmt_duration(info['duration'])}")
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    say("!", f"could not scan formats: {trunc(str(e), 60)}")
                    probed = True
            show_menu(rows)
            r = menu("select [1-3/b/q]: ", set(LEVEL_KEYS))
            if r == BACK:
                stage = "playlist" if has_playlist else "mode"
                continue
            if r == QUIT:
                return QUIT
            level = LEVEL_KEYS[r]
            stage = "download"
        elif stage == "download":
            holder = {}
            say("*", "starting download...")
            with YoutubeDL(build_opts(mode, level, playlist, cookies, holder)) as ydl:
                holder["ydl"] = ydl
                ydl.download([url])
            say("+", f"done -> {short(OUT_DIR)}")
            stage = "done"
    return None


def main():
    banner()
    cookies_src = find_cookies()
    boot(cookies_src)

    first = sys.argv[1] if len(sys.argv) > 1 else None

    while True:
        print()
        if first:
            raw, first = first, None
            say("*", f"target: {trunc(raw, 55)}")
        else:
            print(dim("   c = set cookies   q = quit"))
            raw = url_prompt()
        cmd = raw.lower()

        if cmd == "q":
            break
        if cmd == "c":
            p = input(f"{cyan('[?]')} cookies file path (empty = none): ").strip()
            if not p:
                cookies_src = None
                say("!", "cookies disabled")
            else:
                p = os.path.abspath(os.path.expanduser(p))
                if os.path.isfile(p):
                    cookies_src = p
                    say("+", f"using cookies: {short(p)}")
                else:
                    say("x", "file not found")
            continue
        if not raw:
            continue

        try:
            r = handle_url(raw, cookies_src)
        except KeyboardInterrupt:
            print()
            say("!", "cancelled")
            continue
        except Exception as e:
            print()
            say("x", f"error: {trunc(str(e), 200)}")
            continue
        if r == QUIT:
            break
        # BACK or done -> back to URL prompt


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print()
        say("!", "bye")
