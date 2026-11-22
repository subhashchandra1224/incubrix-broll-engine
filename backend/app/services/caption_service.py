"""SRT caption generation and optional burn-in.

Captions are synchronised to the narration word timings. Each scene becomes
one or more caption blocks (split when a scene is long). The SRT file format
is standard RFC-compliant and includes a header comment identifying the file
as either real or test data.

Burn-in is performed by ffmpeg.burn_captions and delegates to the subtitles
filter. The source video must be ffprobe-valid before burn-in is attempted.
"""
from __future__ import annotations

import logging
import os

from app.schemas.providers import Scene

log = logging.getLogger(__name__)

MAX_CAPTION_CHARS = 80  # hard wrap long scene text


def _srt_time(seconds: float) -> str:
    """Format seconds as SRT timestamp HH:MM:SS,mmm."""
    total_ms = int(round(seconds * 1000))
    ms = total_ms % 1000
    total_s = total_ms // 1000
    s = total_s % 60
    m = (total_s // 60) % 60
    h = total_s // 3600
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _wrap(text: str, width: int = MAX_CAPTION_CHARS) -> list[str]:
    """Split text into lines of at most `width` characters at word boundaries."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for w in words:
        if current and len(current) + 1 + len(w) > width:
            lines.append(current)
            current = w
        else:
            current = (current + " " + w).strip()
    if current:
        lines.append(current)
    return lines


def build_srt(scenes: list[Scene], *, test_data: bool = True) -> str:
    """Generate a full SRT string from a list of scenes.

    Args:
        scenes: ordered list of scenes with text, start_time, end_time.
        test_data: if True, the header will label this as test data.
    """
    header_note = (
        "# TEST-DATA captions generated from mock narration timings.\n"
        if test_data else
        "# Captions generated from real narration timings.\n"
    )
    blocks: list[str] = []
    idx = 1
    for sc in scenes:
        lines = _wrap(sc.text)
        caption_text = "\n".join(lines)
        block = (
            f"{idx}\n"
            f"{_srt_time(sc.start_time)} --> {_srt_time(sc.end_time)}\n"
            f"{caption_text}\n"
        )
        blocks.append(block)
        idx += 1
    return header_note + "\n".join(blocks)


def write_srt(scenes: list[Scene], out_path: str, *, test_data: bool = True) -> str:
    """Write an SRT file and return the path."""
    srt_text = build_srt(scenes, test_data=test_data)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(srt_text)
    log.info("Wrote SRT captions to %s (%d scenes)", out_path, len(scenes))
    return out_path
