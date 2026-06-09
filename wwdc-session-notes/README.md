# WWDC Session Notes

Fetch Apple Developer WWDC session notes from a video URL and write them to Markdown.

The generated Markdown includes, by default:

- The full transcript with paragraph-level timestamps.
- Code snippets from the Developer app Code tab.
- Resource links from the Developer app About tab.

## Usage

Use it as a skill by asking for WWDC session notes from an Apple Developer video URL, for example:

```text
Use WWDC Session Notes for https://developer.apple.com/videos/play/wwdc2026/339 and write the Markdown output here.
```

You can also run the script used by the skill independently. It uses only Python's standard library, so it does not require Codex.

Run from this skill directory:

```bash
python3 scripts/fetch_wwdc_session_notes.py "https://developer.apple.com/videos/play/wwdc2026/339" --output-dir .
```

Name the output by session ID instead of title:

```bash
python3 scripts/fetch_wwdc_session_notes.py "https://developer.apple.com/videos/play/wwdc2026/339" --output-dir . --filename-style session
```

Generate untimestamped transcript text:

```bash
python3 scripts/fetch_wwdc_session_notes.py "https://developer.apple.com/videos/play/wwdc2026/339" --output-dir . --no-timestamps
```

Generate transcript only:

```bash
python3 scripts/fetch_wwdc_session_notes.py "https://developer.apple.com/videos/play/wwdc2026/339" --output-dir . --no-code-snippets --no-resources
```

Generate only code snippets or only resources:

```bash
python3 scripts/fetch_wwdc_session_notes.py "https://developer.apple.com/videos/play/wwdc2026/339" --output-dir . --only-code-snippets
python3 scripts/fetch_wwdc_session_notes.py "https://developer.apple.com/videos/play/wwdc2026/339" --output-dir . --only-resources
```

## Notes

- The script uses only the Python standard library.
- English is the default locale. Use `--locale` for other Apple feed locales when available.
- Transcript paragraphs are timestamped by default. Use `--no-timestamps` for clean prose or `--timestamp-style segment` for Apple's raw short-segment timing.
- Code snippet metadata such as `*02:00-02:37 | swift*` means the snippet appears from 02:00 to 02:37 in the video and is written in Swift.
