# Security Policy

## Supported versions

VideoToSprite is a young project; only the latest `main` is supported. There are no
backported fixes.

## Reporting a vulnerability

Please report privately via GitHub's
[Security Advisories](https://github.com/siloebb/videoToSpriteDilo/security/advisories/new)
rather than opening a public issue. I'll acknowledge within a week.

## Scope notes

VideoToSprite is a local desktop app. It runs no server and opens no listening
ports. It makes exactly three kinds of outbound request, all user-initiated:

1. **ffmpeg/ffprobe download** — the **Install ffmpeg** button fetches static builds
   from [`eugeneware/ffmpeg-static`](https://github.com/eugeneware/ffmpeg-static)
   over HTTPS into `~/.videotosprite/bin`
   ([`core/ffmpeg_setup.py`](src/videotosprite/core/ffmpeg_setup.py)). The binaries
   are verified only by running `-version`; there is **no checksum or signature
   check**, so the download is trust-on-first-use over TLS. If that isn't acceptable
   in your environment, install ffmpeg yourself (`brew install ffmpeg`) and the app
   will find it on `PATH`.
2. **AI model download** — `rembg` fetches its model weights into `~/.u2net/` on
   first use.
3. **Nothing else.** No telemetry, no analytics, no crash reporting. Your videos
   never leave your machine.

The app also shells out to `ffmpeg`/`ffprobe` with user-supplied file paths
(argument lists, never a shell string) and writes to a `tempfile.mkdtemp()`
directory plus the output folder you choose.
