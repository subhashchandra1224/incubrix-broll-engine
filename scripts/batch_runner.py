"""Batch runner — Integration Standard point 10.

Usage (from the project root):

    python scripts/batch_runner.py <inputs_path> <out_dir> [--api http://localhost:8000]

<inputs_path> is a JSON file or a directory of JSON files.  Each JSON file
contains one job request (the same body as POST /api/v1/broll/jobs).

The runner:
  1. Submits each input as a job (with an Idempotency-Key per file).
  2. Polls until every job reaches a terminal state.
  3. Downloads all output files into <out_dir>/<job_id>/.
  4. Writes a summary.json (job_id, status, timings, warnings, failures).

One command for keyless tests (all mock providers):
    python scripts/batch_runner.py test_data/batch_inputs test_results/batch_run
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

DEFAULT_API = "http://localhost:8000"
POLL_INTERVAL = 3.0  # seconds
MAX_WAIT = 600       # seconds


def _api(api_base: str, path: str) -> str:
    return api_base.rstrip("/") + path


def _get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read())


def _post(url: str, body: dict, idem_key: str) -> dict:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json", "Idempotency-Key": idem_key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as exc:
        return json.loads(exc.read())


def _download(url: str, dest: str) -> None:
    with urllib.request.urlopen(url, timeout=120) as r:
        with open(dest, "wb") as fh:
            while True:
                chunk = r.read(1024 * 256)
                if not chunk:
                    break
                fh.write(chunk)


def _stable_key(input_path: str, body: dict) -> str:
    h = hashlib.sha256(
        (input_path + json.dumps(body, sort_keys=True)).encode("utf-8")
    ).hexdigest()[:24]
    return f"batch-{h}"


def load_inputs(inputs_path: str) -> list[tuple[str, dict]]:
    p = Path(inputs_path)
    if p.is_file():
        with open(p) as fh:
            body = json.load(fh)
        return [(str(p), body)]
    files = sorted(p.glob("*.json"))
    if not files:
        sys.exit(f"No JSON files found in {inputs_path}")
    result = []
    for f in files:
        with open(f) as fh:
            result.append((str(f), json.load(fh)))
    return result


def run(inputs_path: str, out_dir: str, api_base: str = DEFAULT_API) -> None:
    os.makedirs(out_dir, exist_ok=True)
    inputs = load_inputs(inputs_path)
    print(f"Loaded {len(inputs)} input(s) from {inputs_path}")

    # Submit all jobs.
    jobs: dict[str, dict] = {}  # job_id -> {input_file, body, status_url, ...}
    for input_file, body in inputs:
        idem_key = _stable_key(input_file, body)
        resp = _post(_api(api_base, "/api/v1/broll/jobs"), body, idem_key)
        if "error" in resp:
            print(f"  SUBMIT FAILED [{input_file}]: {resp['error']}")
            jobs[f"failed-{os.path.basename(input_file)}"] = {
                "input_file": input_file, "status": "failed",
                "error": resp["error"], "timings": {}, "outputs": [],
            }
            continue
        job_id = resp["job_id"]
        jobs[job_id] = {
            "input_file": input_file, "status": resp["status"],
            "status_url": resp["status_url"],
            "submitted_at": time.time(), "timings": {}, "outputs": [],
        }
        print(f"  Submitted [{os.path.basename(input_file)}] -> {job_id}")

    # Poll until all terminal.
    pending = {jid for jid, info in jobs.items() if info["status"] not in ("succeeded", "failed")}
    start_all = time.time()
    while pending:
        if time.time() - start_all > MAX_WAIT:
            for jid in list(pending):
                jobs[jid]["status"] = "timeout"
            break
        time.sleep(POLL_INTERVAL)
        for jid in list(pending):
            try:
                st = _get(_api(api_base, f"/api/v1/jobs/{jid}"))
            except Exception as exc:
                print(f"  Poll error for {jid}: {exc}")
                continue
            jobs[jid]["status"] = st.get("status")
            jobs[jid]["progress"] = st.get("progress", 0)
            jobs[jid]["result"] = st.get("result")
            jobs[jid]["error"] = st.get("error")
            jobs[jid]["links"] = st.get("links", {})
            if st.get("status") in ("succeeded", "failed"):
                jobs[jid]["timings"]["finished_at"] = time.time()
                pending.discard(jid)
                print(f"  {st['status'].upper():9s} [{jid}]")

    # Download artifacts for succeeded jobs.
    for job_id, info in jobs.items():
        if info.get("status") != "succeeded":
            continue
        job_out = os.path.join(out_dir, job_id)
        os.makedirs(job_out, exist_ok=True)
        links = info.get("links", {})
        result = info.get("result", {})
        # Gather download URLs from links.
        for fname, url in links.items():
            if fname in ("self", "outputs", "timeline", "manifest"):
                continue
            if not url.startswith("http"):
                url = _api(api_base, url) if url.startswith("/") else url
            dest = os.path.join(job_out, fname)
            try:
                _download(url, dest)
                info["outputs"].append(fname)
                print(f"  Downloaded {fname} ({os.path.getsize(dest)//1024}kB)")
            except Exception as exc:
                print(f"  Download FAILED [{fname}]: {exc}")
        # Also fetch timeline + manifest.
        for fname in ("timeline.json", "manifest.json"):
            url = links.get(fname) or _api(api_base, f"/api/v1/broll/jobs/{job_id}/outputs/{fname}")
            dest = os.path.join(job_out, fname)
            try:
                _download(url, dest)
                info["outputs"].append(fname)
            except Exception:
                # Try JSON endpoint.
                try:
                    tl = _get(_api(api_base, f"/api/v1/broll/jobs/{job_id}/"
                                             f"{'timeline' if fname == 'timeline.json' else 'manifest'}"))
                    with open(dest, "w") as fh:
                        json.dump(tl, fh, indent=2)
                    info["outputs"].append(fname)
                except Exception as exc2:
                    print(f"  Could not fetch {fname}: {exc2}")

    # Write summary.
    summary = {
        "inputs_path": inputs_path,
        "api_base": api_base,
        "run_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total": len(jobs),
        "succeeded": sum(1 for j in jobs.values() if j.get("status") == "succeeded"),
        "failed": sum(1 for j in jobs.values() if j.get("status") == "failed"),
        "timeout": sum(1 for j in jobs.values() if j.get("status") == "timeout"),
        "jobs": {jid: {
            "status": info["status"],
            "input_file": info["input_file"],
            "outputs": info.get("outputs", []),
            "warnings": (info.get("result") or {}).get("warnings", []),
            "error": info.get("error"),
        } for jid, info in jobs.items()},
    }
    summary_path = os.path.join(out_dir, "summary.json")
    with open(summary_path, "w") as fh:
        json.dump(summary, fh, indent=2)
    print(f"\n--- Summary ---")
    print(f"Succeeded: {summary['succeeded']} / {summary['total']}")
    print(f"Failed:    {summary['failed']} / {summary['total']}")
    print(f"Summary:   {summary_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="B-roll Engine batch runner")
    parser.add_argument("inputs", help="JSON file or folder of JSON files")
    parser.add_argument("out_dir", help="Output directory for downloaded artifacts")
    parser.add_argument("--api", default=DEFAULT_API, help="API base URL")
    args = parser.parse_args()
    run(args.inputs, args.out_dir, args.api)
