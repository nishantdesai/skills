---
name: wwdc-session-notes
description: Fetch full Apple Developer WWDC video transcripts, attached Code tab snippets, and About tab resource links from a session URL, then write them as Markdown files. Use when a user provides an Apple Developer video link such as developer.apple.com/videos/play/wwdc2026/339 and wants the complete transcript, timestamps, code snippets, resources, or session notes saved to .md, named by session title or session number.
---

# WWDC Session Notes

Use the bundled script to fetch a complete transcript, Code tab snippets, and About tab resources for a WWDC session URL and write them to Markdown.

## Quick Start

Run from this skill directory:

```bash
python3 scripts/fetch_wwdc_session_notes.py "https://developer.apple.com/videos/play/wwdc2026/339" --output-dir .
```

By default the script:

- Parses the event/session from the Apple Developer URL.
- Fetches Apple's Developer app config.
- Reads the English transcript manifest.
- Fetches the per-session transcript JSON in one request.
- Reads attached Code tab snippets from Apple's contents feed.
- Reads About tab resource links from Apple's contents feed.
- Prefixes transcript paragraphs with readable timestamps.
- Writes a Markdown file named from the session title when available.

Use `--filename-style session` to name the file like `wwdc2026-339.md`.

Transcript paragraph timestamps are included by default. Use `--no-timestamps` only when the user asks for untimestamped transcript text:

```bash
python3 scripts/fetch_wwdc_session_notes.py "https://developer.apple.com/videos/play/wwdc2026/339" --output-dir . --no-timestamps
```

Use `--timestamp-style segment` only when raw per-segment timing is needed; it is much noisier because Apple timestamps short phrase segments.

Code snippets and resources are included by default. Use `--no-code-snippets` and `--no-resources` only when the user asks for transcript-only output:

```bash
python3 scripts/fetch_wwdc_session_notes.py "https://developer.apple.com/videos/play/wwdc2026/339" --output-dir . --no-code-snippets --no-resources
```

Use `--only-code-snippets` when the user asks for code snippets without the transcript:

```bash
python3 scripts/fetch_wwdc_session_notes.py "https://developer.apple.com/videos/play/wwdc2026/339" --output-dir . --filename-style session --only-code-snippets
```

Use `--only-resources` when the user asks for the About tab resource links without the transcript or code snippets:

```bash
python3 scripts/fetch_wwdc_session_notes.py "https://developer.apple.com/videos/play/wwdc2026/339" --output-dir . --filename-style session --only-resources
```

## Notes

- The English feed locale is `en`. Other Apple feed locales can be selected with `--locale`, such as `zho`, `jpn`, `kor`, `spa`, `por`, or `fra`, when Apple provides that transcript.
- Apple transcript JSON stores timestamps as seconds from the start of the video. The script renders these as `[MM:SS]` or `[H:MM:SS]`.
- Code snippets come from the session entry in Apple's `contents.json`, not from the transcript manifest. The script uses `unstyledCode` when available and falls back to stripping Apple's highlighted HTML.
- Resources come from the session entry's `related.resources` IDs in Apple's `contents.json`, resolved through the top-level `resources` array.
- The manifest URL is versioned by Apple. The script accepts `--config-url` if the default Developer app config URL stops working.
- If the title lookup fails but the transcript is available, the script still writes the transcript using the session key as the filename and heading.
