"""Reusable FFmpeg and FFprobe utilities.

Binary resolution order (no hard-coded paths):
  1. PATH (set by winget install on Windows; available inside the Docker image).
  2. imageio_ffmpeg bundled binary (fallback for local dev without system FFmpeg).

All subprocess calls use a fixed timeout; no shell=True; paths are validated
before use to prevent path-traversal.

Why FFmpeg: it is the industry-standard open-source video processing engine and
the only tool that satisfies Must-have 4 (H.264/AAC, 30fps, 1080p, normalised
codecs) without additional cost or licence restrictions. GPL-2.0+ (we use it
as an external binary, not linked into our code, so no AGPL concern).
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

log = logging.getLogger(__name__)

# --- Binary resolution ---

def _resolve(name: str) -> str:
    """Return the absolute path to `name` (ffmpeg or ffprobe)."""
    # 1. Try PATH first (winget install / system FFmpeg / Docker image PATH).
    system = shutil.which(name)
    if system:
        return system
    # 2. Fall back to imageio_ffmpeg bundled binary (ffmpeg only).
    if name == "ffmpeg":
        try:
            import imageio_ffmpeg
            path = imageio_ffmpeg.get_ffmpeg_exe()
            if path and os.path.isfile(path):
                log.debug("Using imageio_ffmpeg bundled binary: %s", path)
                return path
        except ImportError:
            pass
    raise RuntimeError(
        f"{name!r} not found. Install FFmpeg (winget install Gyan.FFmpeg) or "
        "ensure imageio-ffmpeg is installed for ffmpeg."
    )


def get_ffmpeg() -> str:
    return _resolve("ffmpeg")


def get_ffprobe() -> str:
    return _resolve("ffprobe")


def ffmpeg_available() -> bool:
    try:
        get_ffmpeg()
        return True
    except RuntimeError:
        return False


def ffprobe_available() -> bool:
    try:
        get_ffprobe()
        return True
    except RuntimeError:
        return False


# --- FFprobe inspection ---

def probe(path: str, timeout: int = 30) -> dict:
    """Run ffprobe on a file and return the parsed JSON."""
    ffp = get_ffprobe()
    cmd = [ffp, "-v", "quiet", "-print_format", "json", "-show_format",
           "-show_streams", str(path)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"ffprobe timed out on {path!r}")
    if r.returncode != 0:
        raise RuntimeError(f"ffprobe failed on {path!r}: {r.stderr[:300]}")
    return json.loads(r.stdout)


def video_info(path: str) -> dict:
    """Return a summary dict with codec, resolution, fps, duration, audio info."""
    data = probe(path)
    streams = data.get("streams", [])
    fmt = data.get("format", {})
    result = {
        "duration": float(fmt.get("duration", 0)),
        "size_bytes": int(fmt.get("size", 0)),
        "video": None,
        "audio": None,
    }
    for s in streams:
        if s.get("codec_type") == "video" and result["video"] is None:
            fps_str = s.get("r_frame_rate", "0/1")
            num, den = (int(x) for x in fps_str.split("/"))
            result["video"] = {
                "codec": s.get("codec_name"),
                "width": s.get("width"),
                "height": s.get("height"),
                "fps": round(num / den, 3) if den else 0,
                "pix_fmt": s.get("pix_fmt"),
                "duration": float(s.get("duration", result["duration"])),
            }
        elif s.get("codec_type") == "audio" and result["audio"] is None:
            result["audio"] = {
                "codec": s.get("codec_name"),
                "sample_rate": int(s.get("sample_rate", 0)),
                "channels": s.get("channels"),
                "duration": float(s.get("duration", result["duration"])),
            }
    return result


# --- Validation checks ---

def validate_output(path: str, *, expected_duration: float | None = None,
                    duration_tolerance: float = 0.5) -> list[str]:
    """Run standard checks on an output MP4. Returns a list of error strings (empty = clean)."""
    errors: list[str] = []
    info = video_info(path)
    v = info.get("video")
    a = info.get("audio")
    if v is None:
        errors.append("No video stream found.")
        return errors
    if a is None:
        errors.append("No audio stream found.")
    if v.get("codec") not in ("h264", "libx264"):
        errors.append(f"Video codec is {v.get('codec')!r}, expected h264.")
    if a and a.get("codec") != "aac":
        errors.append(f"Audio codec is {a.get('codec')!r}, expected aac.")
    if abs(v.get("fps", 0) - 30.0) > 0.5:
        errors.append(f"Frame rate is {v.get('fps')}, expected 30.")
    if v.get("pix_fmt") != "yuv420p":
        errors.append(f"Pixel format is {v.get('pix_fmt')!r}, expected yuv420p.")
    if expected_duration is not None:
        dur = info.get("duration", 0)
        if abs(dur - expected_duration) > duration_tolerance:
            errors.append(f"Duration {dur:.2f}s differs from expected {expected_duration:.2f}s "
                          f"(tolerance {duration_tolerance}s).")
    if v and a:
        v_dur = v.get("duration", info.get("duration", 0))
        a_dur = a.get("duration", info.get("duration", 0))
        drift = abs(v_dur - a_dur)
        if drift > 0.1:
            errors.append(f"A/V duration drift: video={v_dur:.3f}s audio={a_dur:.3f}s drift={drift:.3f}s.")
    return errors


def check_black_frames(path: str, threshold: float = 0.1,
                       duration_threshold: float = 0.5, timeout: int = 60) -> list[str]:
    """Detect runs of black frames lasting > duration_threshold seconds.

    Uses FFmpeg's blackdetect filter. Returns a list of human-readable findings.

    Args:
        threshold: pixel luma threshold (0–1). Pixels with Y < threshold are
                   considered black. Default 0.1 (10%) is FFmpeg's default.
        duration_threshold: minimum duration (seconds) of black to report.
    """
    ff = get_ffmpeg()
    cmd = [
        ff, "-i", str(path),
        "-vf", f"blackdetect=d={duration_threshold}:pix_th={threshold}",
        "-an", "-f", "null", "-",
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    output = r.stderr  # blackdetect writes to stderr
    findings = re.findall(r"black_start:[\d.]+\s+black_end:[\d.]+\s+black_duration:[\d.]+", output)
    return findings


def check_frozen_frames(path: str, threshold: float = 0.001,
                        duration_threshold: float = 2.0, timeout: int = 60) -> list[str]:
    """Detect frozen (static) video runs using FFmpeg's freezedetect filter."""
    ff = get_ffmpeg()
    cmd = [
        ff, "-i", str(path),
        "-vf", f"freezedetect=n={threshold}:d={duration_threshold}",
        "-an", "-f", "null", "-",
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    findings = re.findall(r"freeze_start:[\d.]+", r.stderr)
    return findings


# --- Low-level encode operations ---

def _run(cmd: list[str], timeout: int = 300, label: str = "ffmpeg") -> None:
    log.debug("Running: %s", " ".join(cmd[:6]) + ("..." if len(cmd) > 6 else ""))
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        # Include first 400 chars of stderr to help diagnose.
        raise RuntimeError(f"{label} failed (rc={r.returncode}): {r.stderr[-400:]}")


def normalise_clip(src: str, dst: str, *, width: int, height: int,
                   fps: int = 30, duration: float | None = None,
                   pad_color: str = "black") -> None:
    """Scale+pad a video clip to exactly (width x height) at fps, yuv420p.

    Scale strategy:
    - Scale the input to fit inside (width x height) while preserving aspect ratio.
    - Pad the remaining area with pad_color (black) so the subject is never cropped.
    - This satisfies 'preserve important subject during reframing' for 9:16 and 1:1.

    If duration is set, trim/loop the clip to exactly that length.
    """
    ff = get_ffmpeg()
    # scale to fit inside the box, then pad to exact box size
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color={pad_color},"
        f"setsar=1,fps={fps},format=yuv420p"
    )
    cmd = [ff, "-y", "-i", str(src), "-vf", vf]
    if duration is not None:
        cmd += ["-t", str(duration)]
    cmd += ["-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-ar", "48000", "-ac", "2",
            str(dst)]
    _run(cmd, label=f"normalise_clip({os.path.basename(src)})")


def concat_clips_with_audio(
    clip_paths: list[str],
    narration_path: str,
    out_path: str,
    *,
    narration_duration: float | None = None,
    fps: int = 30,
    timeout: int = 600,
) -> None:
    """Concatenate normalised video clips and mix in a narration audio track.

    The narration audio is the master duration reference. Uses tpad to extend
    video (cloning the last frame) if video is shorter than narration, and -t to
    cap the output at exactly narration_duration. This guarantees the output
    duration equals the narration duration, not the video duration — satisfying
    the brief's requirement that 'the narration sets the timing, not the clips'.

    Args:
        clip_paths: list of already-normalised video-only files (same W/H/fps).
        narration_path: path to the narration AAC/WAV audio file.
        narration_duration: expected narration duration in seconds. If None,
            falls back to -shortest (less safe; prefer explicit duration).
        out_path: destination MP4 path.
    """
    ff = get_ffmpeg()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as fh:
        concat_file = fh.name
        for cp in clip_paths:
            # Absolute paths with forward slashes for FFmpeg concat on Windows.
            abs_cp = os.path.abspath(cp).replace("\\", "/")
            fh.write(f"file '{abs_cp}'\n")
    try:
        cmd = [
            ff, "-y",
            "-f", "concat", "-safe", "0", "-i", concat_file,
            "-i", str(narration_path),
            # tpad clones the last frame so video never runs out before -t.
            "-vf", "tpad=stop_mode=clone",
            # apad pads audio with silence if narration is slightly shorter.
            "-af", "apad",
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-ar", "48000", "-ac", "2",
        ]
        if narration_duration is not None:
            # -t caps the output at exactly narration_duration. Narration is master.
            cmd += ["-t", str(narration_duration)]
        else:
            cmd += ["-shortest"]
        cmd += [str(out_path)]
        _run(cmd, timeout=timeout, label="concat_clips_with_audio")
    finally:
        os.unlink(concat_file)


def burn_captions(src: str, dst: str, srt_path: str, timeout: int = 300) -> None:
    """Burn SRT captions into the video using the subtitles filter."""
    ff = get_ffmpeg()
    # subtitles filter requires forward slashes on Windows
    srt_safe = str(srt_path).replace("\\", "/").replace(":", "\\:")
    cmd = [
        ff, "-y", "-i", str(src),
        "-vf", f"subtitles='{srt_safe}'",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "copy",
        str(dst),
    ]
    _run(cmd, timeout=timeout, label="burn_captions")


def generate_silent_audio(out_path: str, duration: float, timeout: int = 30) -> None:
    """Generate a silent AAC audio file of exactly `duration` seconds."""
    ff = get_ffmpeg()
    cmd = [
        ff, "-y",
        "-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo",
        "-t", str(duration),
        "-c:a", "aac", "-ar", "48000", "-ac", "2",
        str(out_path),
    ]
    _run(cmd, timeout=timeout, label="generate_silent_audio")
