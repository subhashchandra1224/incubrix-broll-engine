"""Deterministic test fixture generator.

Generates small, locally-produced media files for automated rendering tests.
No downloads. No real footage. No real narration. Everything is clearly labelled.

Each fixture is generated with FFmpeg from first principles:
  - Narration audio: a sequence of pure sine-tone segments, one per scene,
    at different frequencies so scenes are audibly distinct.
  - Video clips: colour-bar test patterns (one per scene), H.264 MP4.

All generated files carry a metadata title tag starting with
"TEST-DATA" so they are never mistaken for real content.

The fixtures are written to a temp directory per test run; callers are
responsible for cleanup (or use the `fixture_dir` context manager).
"""
from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from app.utils.ffmpeg import get_ffmpeg

log = logging.getLogger(__name__)

# Scene durations used in fixtures (seconds).  Three scenes = 9s narration.
DEFAULT_SCENE_DURATIONS = [3.0, 3.0, 3.0]
# Frequencies of the sine tones, one per scene.
DEFAULT_TONES_HZ = [440, 528, 660]
# Colour-bar hue offsets for each scene's test clip.
DEFAULT_HUE_OFFSETS = [0, 60, 120]


@dataclass
class FixtureScene:
    index: int               # 0-based
    text: str
    start_time: float
    end_time: float
    audio_path: str = ""
    video_path: str = ""


@dataclass
class FixtureSet:
    """A complete deterministic test fixture set.  All files are TEST-DATA."""
    work_dir: str
    scenes: list[FixtureScene]
    narration_path: str      # single concatenated narration audio
    total_duration: float
    test_data: bool = True


def _run(cmd: list[str], timeout: int = 60, label: str = "") -> None:
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"fixture generation failed [{label}]: {r.stderr[-300:]}")


def generate_fixtures(
    work_dir: str,
    *,
    scene_durations: list[float] = DEFAULT_SCENE_DURATIONS,
    tones_hz: list[int] = DEFAULT_TONES_HZ,
    hue_offsets: list[int] = DEFAULT_HUE_OFFSETS,
    width: int = 1920,
    height: int = 1080,
) -> FixtureSet:
    """Generate per-scene audio + video test fixtures and a concatenated narration.

    Every generated file has title metadata starting with 'TEST-DATA'.
    """
    ff = get_ffmpeg()
    os.makedirs(work_dir, exist_ok=True)
    n = len(scene_durations)
    tones_hz = (tones_hz * n)[:n]
    hue_offsets = (hue_offsets * n)[:n]

    scenes: list[FixtureScene] = []
    offset = 0.0
    audio_parts: list[str] = []

    for i, dur in enumerate(scene_durations):
        texts = [
            "Saving money starts with small decisions.",
            "Track your monthly expenses carefully.",
            "A clear budget builds long-term security.",
        ]
        sc = FixtureScene(
            index=i,
            text=texts[i % len(texts)],
            start_time=round(offset, 3),
            end_time=round(offset + dur, 3),
        )

        # --- per-scene narration audio (sine tone, AAC) ---
        audio_path = os.path.join(work_dir, f"scene_{i:03d}_audio.aac")
        _run([
            ff, "-y",
            "-f", "lavfi", "-i", f"sine=frequency={tones_hz[i]}:sample_rate=48000",
            "-t", str(dur),
            "-c:a", "aac", "-ar", "48000", "-ac", "2",
            "-metadata", f"title=TEST-DATA scene {i} audio",
            audio_path,
        ], label=f"scene_{i}_audio")
        sc.audio_path = audio_path
        audio_parts.append(audio_path)

        # --- per-scene video (colour bars + hue, H.264 MP4) ---
        video_path = os.path.join(work_dir, f"scene_{i:03d}_video.mp4")
        hue_filter = (
            f"color=c=0x{_hue_to_hex(hue_offsets[i])}:size={width}x{height}:rate=30,"
            "format=yuv420p"
        )
        _run([
            ff, "-y",
            "-f", "lavfi", "-i", hue_filter,
            "-t", str(dur),
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
            "-metadata", f"title=TEST-DATA scene {i} video",
            video_path,
        ], label=f"scene_{i}_video")
        sc.video_path = video_path

        scenes.append(sc)
        offset += dur

    # --- concatenated narration audio ---
    narration_path = os.path.join(work_dir, "narration_full.aac")
    if len(audio_parts) == 1:
        import shutil as _sh
        _sh.copy2(audio_parts[0], narration_path)
    else:
        import tempfile as _tf
        with _tf.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as fh:
            concat_file = fh.name
            for ap in audio_parts:
                fh.write(f"file '{ap}'\n")
        try:
            _run([
                ff, "-y",
                "-f", "concat", "-safe", "0", "-i", concat_file,
                "-c:a", "aac", "-ar", "48000", "-ac", "2",
                "-metadata", "title=TEST-DATA narration",
                narration_path,
            ], label="concat_narration")
        finally:
            os.unlink(concat_file)

    return FixtureSet(
        work_dir=work_dir,
        scenes=scenes,
        narration_path=narration_path,
        total_duration=round(offset, 3),
        test_data=True,
    )


def _hue_to_hex(hue_offset: int) -> str:
    """Convert a hue-offset (0-360) into a hex colour string."""
    import colorsys
    r, g, b = colorsys.hsv_to_rgb(hue_offset / 360.0, 0.8, 0.8)
    return f"{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"


@contextmanager
def fixture_dir():
    """Context manager that creates a temp dir and cleans up after the test."""
    d = tempfile.mkdtemp(prefix="broll_fix_")
    try:
        yield d
    finally:
        import shutil
        shutil.rmtree(d, ignore_errors=True)
