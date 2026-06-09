#!/usr/bin/env python3
"""Fetch an Apple Developer WWDC transcript and write it as Markdown."""

from __future__ import annotations

import argparse
import gzip
import html
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_CONFIG_URL = (
    "https://devimages-cdn.apple.com/wwdc-services/w9f43630/"
    "73A40F02-6975-439F-BA6E-F5C834BFEAC5/config.json"
)


def fetch_json(url: str, timeout: int = 30) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "User-Agent": "Codex WWDC session notes fetcher",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = response.read()
            encoding = response.headers.get("Content-Encoding", "").lower()
            if "gzip" in encoding or data.startswith(b"\x1f\x8b"):
                data = gzip.decompress(data)
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"HTTP {error.code} fetching {url}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Could not fetch {url}: {error.reason}") from error

    try:
        return json.loads(data.decode("utf-8"))
    except json.JSONDecodeError as error:
        raise RuntimeError(f"Response was not valid JSON: {url}") from error


def parse_session_url(url: str) -> tuple[str, str, str]:
    parsed = urllib.parse.urlparse(url)
    path = parsed.path.rstrip("/")
    match = re.search(r"/videos/play/(wwdc\d{4})/([^/]+)$", path)
    if not match:
        raise RuntimeError(
            "Expected an Apple Developer WWDC URL like "
            "https://developer.apple.com/videos/play/wwdc2026/339"
        )

    event_id, session_id = match.groups()
    return event_id, session_id, f"{event_id}-{session_id}"


def safe_filename(value: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|]+", "-", value)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = cleaned.rstrip(". ")
    return cleaned or "wwdc-session-notes"


def find_content(contents_feed: Any, content_key: str) -> dict[str, Any] | None:
    if not isinstance(contents_feed, dict):
        return None
    contents = contents_feed.get("contents")
    if not isinstance(contents, list):
        return None
    for item in contents:
        if isinstance(item, dict) and item.get("id") == content_key:
            return item
    return None


def format_timestamp(seconds: float) -> str:
    total_seconds = int(seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def render_plain_transcript(segments: list[tuple[float, str]]) -> str:
    return "".join(text for _, text in segments).strip()


def render_segment_timestamps(segments: list[tuple[float, str]]) -> str:
    lines: list[str] = []
    for seconds, text in segments:
        text = text.strip()
        if text:
            lines.append(f"[{format_timestamp(seconds)}] {text}")
    return "\n".join(lines).strip()


def render_paragraph_timestamps(segments: list[tuple[float, str]]) -> str:
    paragraphs: list[str] = []
    pending = ""
    paragraph_start: float | None = None

    for seconds, text in segments:
        if paragraph_start is None and text.strip():
            paragraph_start = seconds

        pending += text
        while "\n\n" in pending:
            paragraph, pending = pending.split("\n\n", 1)
            paragraph = paragraph.strip()
            if paragraph:
                start = format_timestamp(paragraph_start if paragraph_start is not None else seconds)
                paragraphs.append(f"[{start}] {paragraph}")
            paragraph_start = seconds if pending.strip() else None

    pending = pending.strip()
    if pending:
        start = format_timestamp(paragraph_start if paragraph_start is not None else 0)
        paragraphs.append(f"[{start}] {pending}")

    return "\n\n".join(paragraphs).strip()


def code_fence_for(code: str) -> str:
    longest = max((len(match.group(0)) for match in re.finditer(r"`+", code)), default=0)
    return "`" * max(3, longest + 1)


def clean_code_snippet(snippet: dict[str, Any]) -> str:
    unstyled_code = snippet.get("unstyledCode")
    if isinstance(unstyled_code, str) and unstyled_code.strip():
        return unstyled_code.rstrip()

    highlighted_code = snippet.get("code")
    if isinstance(highlighted_code, str) and highlighted_code.strip():
        without_tags = re.sub(r"<[^>]+>", "", highlighted_code)
        return html.unescape(without_tags).rstrip()

    return ""


def render_code_snippets(content: dict[str, Any] | None) -> str:
    snippets = content.get("codeSnippets") if content else None
    lines = [
        "## Code Snippets",
        "",
        "Each snippet below is taken from the session's Code tab; the metadata line shows the video time range where the snippet appears followed by the code language, so `*02:00-02:37 | swift*` means a Swift snippet appears from 02:00 to 02:37 in the video.",
    ]

    if not isinstance(snippets, list) or not snippets:
        lines.extend(["", "No code snippets found for this session."])
        return "\n".join(lines)

    for index, snippet in enumerate(snippets, start=1):
        if not isinstance(snippet, dict):
            continue

        title = snippet.get("title")
        title_text = title.strip() if isinstance(title, str) and title.strip() else f"Snippet {index}"
        lines.extend(["", f"### {index}. {title_text}"])

        metadata: list[str] = []
        start = snippet.get("startTimeSeconds")
        end = snippet.get("endTimeSeconds")
        if isinstance(start, (int, float)) and isinstance(end, (int, float)):
            metadata.append(f"{format_timestamp(start)}-{format_timestamp(end)}")
        elif isinstance(start, (int, float)):
            metadata.append(format_timestamp(start))

        language = snippet.get("language")
        language_name = language.strip() if isinstance(language, str) else ""
        if language_name:
            metadata.append(language_name)

        if metadata:
            lines.extend(["", f"*{' | '.join(metadata)}*"])

        code = clean_code_snippet(snippet)
        if code:
            fence_language = re.sub(r"[^A-Za-z0-9_+.-]", "", language_name)
            fence = code_fence_for(code)
            lines.extend(["", f"{fence}{fence_language}", code, fence])
        else:
            lines.extend(["", "_No code text available for this snippet._"])

    return "\n".join(lines).strip()


def render_resources(content: dict[str, Any] | None, contents_feed: Any) -> str | None:
    related = content.get("related") if content else None
    resource_ids = related.get("resources") if isinstance(related, dict) else None
    if not isinstance(resource_ids, list) or not resource_ids:
        return None

    resources = contents_feed.get("resources") if isinstance(contents_feed, dict) else None
    if not isinstance(resources, list):
        return None

    resources_by_id = {
        resource.get("id"): resource
        for resource in resources
        if isinstance(resource, dict) and "id" in resource
    }

    lines = ["## Resources"]
    for resource_id in resource_ids:
        resource = resources_by_id.get(resource_id)
        if not isinstance(resource, dict):
            continue

        title = resource.get("title")
        title_text = title.strip() if isinstance(title, str) and title.strip() else str(resource_id)

        url = resource.get("url")
        if isinstance(url, str) and url.strip():
            item = f"- [{title_text}]({url.strip()})"
        else:
            item = f"- {title_text}"

        resource_type = resource.get("resource_type")
        if isinstance(resource_type, str) and resource_type.strip():
            item += f" ({resource_type.strip()})"

        description = resource.get("description")
        if isinstance(description, str) and description.strip():
            clean_description = re.sub(r"\s+", " ", description).strip()
            item += f": {clean_description}"

        lines.append(item)

    if len(lines) == 1:
        return None

    return "\n".join(lines)


def transcript_text(
    transcript_payload: Any,
    content_key: str,
    timestamp_style: str,
) -> tuple[str, str]:
    if not isinstance(transcript_payload, dict) or content_key not in transcript_payload:
        raise RuntimeError(f"Transcript payload did not contain {content_key}")

    session_data = transcript_payload[content_key]
    if not isinstance(session_data, dict):
        raise RuntimeError(f"Transcript payload for {content_key} is malformed")

    transcript = session_data.get("transcript")
    if not isinstance(transcript, list):
        raise RuntimeError(f"Transcript payload for {content_key} has no transcript list")

    segments: list[tuple[float, str]] = []
    for segment in transcript:
        if (
            isinstance(segment, list)
            and len(segment) >= 2
            and isinstance(segment[0], (int, float))
            and isinstance(segment[1], str)
        ):
            segments.append((float(segment[0]), segment[1]))

    if timestamp_style == "paragraph":
        text = render_paragraph_timestamps(segments)
    elif timestamp_style == "segment":
        text = render_segment_timestamps(segments)
    else:
        text = render_plain_transcript(segments)

    if not text:
        raise RuntimeError(f"Transcript for {content_key} was empty")

    language = str(session_data.get("language") or "")
    return text, language


def write_markdown(
    output_dir: Path,
    filename_base: str,
    title: str,
    source_url: str,
    content_key: str,
    language: str,
    transcript: str | None,
    code_snippets: str | None,
    resources: str | None,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{safe_filename(filename_base)}.md"
    markdown = [
        f"# {title}",
        "",
        f"- Source: {source_url}",
        f"- Session: {content_key}",
    ]
    if language:
        markdown.append(f"- Language: {language}")

    extra_sections = [section for section in (code_snippets, resources) if section]
    if transcript and extra_sections:
        markdown.extend(["", "## Transcript", "", transcript])
        for section in extra_sections:
            markdown.extend(["", section])
        markdown.append("")
    elif transcript:
        markdown.extend(["", transcript, ""])
    elif extra_sections:
        for section in extra_sections:
            markdown.extend(["", section])
        markdown.append("")
    else:
        markdown.extend(["", "_No transcript, code snippets, or resources were available for this session._", ""])

    output_path.write_text("\n".join(markdown), encoding="utf-8")
    return output_path


def fetch_transcript(args: argparse.Namespace) -> Path:
    event_id, session_id, content_key = parse_session_url(args.url)

    config = fetch_json(args.config_url, timeout=args.timeout)
    feeds = config.get("feeds") if isinstance(config, dict) else None
    if not isinstance(feeds, dict):
        raise RuntimeError("Config JSON did not contain feeds")

    locale_feed = feeds.get(args.locale)
    if not isinstance(locale_feed, dict):
        available = ", ".join(sorted(feeds.keys()))
        raise RuntimeError(f"Locale {args.locale!r} was not in config. Available: {available}")

    title = content_key
    content: dict[str, Any] | None = None
    contents_feed: Any = None
    contents_info = locale_feed.get("contents")
    if isinstance(contents_info, dict) and contents_info.get("url"):
        try:
            contents_feed = fetch_json(str(contents_info["url"]), timeout=args.timeout)
            content = find_content(contents_feed, content_key)
            if content and isinstance(content.get("title"), str):
                title = content["title"].strip() or title
        except RuntimeError as error:
            if (
                args.include_code_snippets
                or args.only_code_snippets
                or args.include_resources
                or args.only_resources
            ):
                raise RuntimeError(f"Could not fetch contents metadata: {error}")
            print(f"Warning: could not fetch title metadata: {error}", file=sys.stderr)

    transcript: str | None = None
    transcript_language = ""
    if not args.only_code_snippets and not args.only_resources:
        transcript_info = locale_feed.get("transcripts")
        if not isinstance(transcript_info, dict) or not transcript_info.get("url"):
            raise RuntimeError(f"Locale {args.locale!r} has no transcript manifest URL")

        manifest = fetch_json(str(transcript_info["url"]), timeout=args.timeout)
        individual = manifest.get("individual") if isinstance(manifest, dict) else None
        if not isinstance(individual, dict) or content_key not in individual:
            raise RuntimeError(f"No transcript manifest entry found for {content_key}")

        entry = individual[content_key]
        if not isinstance(entry, dict) or not entry.get("url"):
            raise RuntimeError(f"Transcript manifest entry for {content_key} had no URL")

        transcript_payload = fetch_json(str(entry["url"]), timeout=args.timeout)
        timestamp_style = args.timestamp_style
        transcript, transcript_language = transcript_text(
            transcript_payload,
            content_key,
            timestamp_style,
        )

    code_snippets = None
    if (args.include_code_snippets and not args.only_resources) or args.only_code_snippets:
        code_snippets = render_code_snippets(content)

    resources = None
    if args.include_resources and not args.only_code_snippets:
        resources = render_resources(content, contents_feed)
        if args.only_resources and not resources:
            resources = "## Resources\n\nNo resources found for this session."

    source_url = f"https://developer.apple.com/videos/play/{event_id}/{session_id}/"
    filename_base = content_key if args.filename_style == "session" else title
    return write_markdown(
        Path(args.output_dir),
        filename_base,
        title,
        source_url,
        content_key,
        transcript_language,
        transcript,
        code_snippets,
        resources,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch Apple Developer WWDC session notes as Markdown."
    )
    parser.add_argument("url", help="Apple Developer video URL")
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory to write the Markdown file into. Defaults to the current directory.",
    )
    parser.add_argument(
        "--filename-style",
        choices=("title", "session"),
        default="title",
        help="Name output file by session title or session key. Defaults to title.",
    )
    parser.add_argument(
        "--locale",
        default="en",
        help="Apple Developer feed locale to use. Defaults to en.",
    )
    parser.add_argument(
        "--timestamps",
        action="store_const",
        const="paragraph",
        dest="timestamp_style",
        default=argparse.SUPPRESS,
        help="Add readable paragraph-level timestamps to the Markdown transcript. This is the default.",
    )
    parser.add_argument(
        "--no-timestamps",
        action="store_const",
        const="none",
        dest="timestamp_style",
        default=argparse.SUPPRESS,
        help="Do not add timestamps to transcript text.",
    )
    parser.add_argument(
        "--timestamp-style",
        choices=("none", "paragraph", "segment"),
        default="paragraph",
        help=(
            "Timestamp style for transcript text. 'paragraph' prefixes each paragraph; "
            "'segment' prefixes every raw transcript segment. Defaults to paragraph."
        ),
    )
    parser.set_defaults(timestamp_style="paragraph")
    parser.add_argument(
        "--include-code-snippets",
        action="store_true",
        default=True,
        help="Append the session's Code tab snippets from Apple's contents feed. This is the default.",
    )
    parser.add_argument(
        "--no-code-snippets",
        action="store_false",
        dest="include_code_snippets",
        help="Do not append Code tab snippets; write only the transcript.",
    )
    parser.add_argument(
        "--only-code-snippets",
        action="store_true",
        help="Write only the session's Code tab snippets, without fetching transcript text.",
    )
    parser.add_argument(
        "--include-resources",
        action="store_true",
        default=True,
        help="Append the session's About tab resources from Apple's contents feed. This is the default.",
    )
    parser.add_argument(
        "--no-resources",
        action="store_false",
        dest="include_resources",
        help="Do not append About tab resources.",
    )
    parser.add_argument(
        "--only-resources",
        action="store_true",
        help="Write only the session's About tab resources, without fetching transcript text or code snippets.",
    )
    parser.add_argument(
        "--config-url",
        default=DEFAULT_CONFIG_URL,
        help="Apple Developer app config URL. Override if Apple rotates the default.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Network timeout in seconds. Defaults to 30.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        output_path = fetch_transcript(args)
    except RuntimeError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
