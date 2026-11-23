"""Verify the keepable sample render with ffprobe.
Run from the project root: python scripts/verify_sample_render.py
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
from app.utils.ffmpeg import video_info, check_black_frames

SAMPLE = os.path.join(os.path.dirname(__file__), '..', 'test_data', 'sample_render')

EXPECTED = {
    'video_16_9.mp4': (1920, 1080),
    'video_9_16.mp4': (1080, 1920),
    'video_1_1.mp4':  (1080, 1080),
}

for fname, (ew, eh) in EXPECTED.items():
    path = os.path.join(SAMPLE, fname)
    info = video_info(path)
    v, a = info['video'], info['audio']
    bf = check_black_frames(path, duration_threshold=0.5)
    drift = round(abs(v.get('duration', 0) - a.get('duration', 0)), 3) if a else 'no_audio'
    ok = (v['width'] == ew and v['height'] == eh and v['codec'] == 'h264'
          and a is not None and a['codec'] == 'aac'
          and abs(v['fps'] - 30) < 1 and len(bf) == 0)
    status = 'PASS' if ok else 'FAIL'
    print(f"{status}  {fname}: {v['width']}x{v['height']}  fps={v['fps']}  "
          f"codec={v['codec']}  dur={round(info['duration'],2)}s  "
          f"av_drift={drift}s  black_frames={len(bf)}")
