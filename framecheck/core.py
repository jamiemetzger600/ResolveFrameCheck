"""Pure comparison logic: pair raw clips with transcodes and compare frame counts."""
import csv
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Dict, List, Optional

OK = "OK"
MISMATCH = "MISMATCH"
MISSING = "MISSING_TRANSCODE"
AMBIGUOUS = "AMBIGUOUS"
ORPHAN = "ORPHAN_TRANSCODE"

DEFAULT_SUFFIXES = ["_proxy", "_pm", "_prores", "_transcode", "_dnx"]


@dataclass
class Clip:
    name: str
    path: str = ""
    frames: Optional[int] = None
    fps: Optional[float] = None
    start_tc: str = ""
    bin: str = ""


@dataclass
class Result:
    status: str
    stem: str
    raw: Optional[Clip] = None
    transcode: Optional[Clip] = None
    delta: Optional[int] = None  # transcode - raw
    warnings: List[str] = field(default_factory=list)
    raw_probe: Optional[int] = None
    transcode_probe: Optional[int] = None


def _to_float(v):
    try:
        return float(str(v).split()[0])
    except (ValueError, IndexError, TypeError):
        return None


def _tc_to_frames(tc, fps):
    m = re.match(r"^(\d+):(\d+):(\d+)[:;](\d+)$", (tc or "").strip())
    if not m or not fps:
        return None
    h, mi, s, f = (int(x) for x in m.groups())
    return int(round((h * 3600 + mi * 60 + s) * round(fps))) + f


def clip_from_props(props: dict, bin_name: str = "") -> Clip:
    """Build a Clip from a Resolve GetClipProperty() dict."""
    fps = _to_float(props.get("FPS"))
    frames = None
    raw_frames = str(props.get("Frames", "")).strip()
    if raw_frames.isdigit() and int(raw_frames) > 0:
        frames = int(raw_frames)
    else:
        # Fallback: End TC - Start TC (+1) when Frames is blank
        s = _tc_to_frames(props.get("Start TC"), fps)
        e = _tc_to_frames(props.get("End TC"), fps)
        if s is not None and e is not None and e >= s:
            frames = e - s
    path = props.get("File Path", "") or ""
    return Clip(
        name=props.get("Clip Name", "") or os.path.basename(path),
        path=path,
        frames=frames,
        fps=fps,
        start_tc=props.get("Start TC", "") or "",
        bin=bin_name,
    )


def normalize_stem(name: str, suffixes=None) -> str:
    stem = os.path.splitext(os.path.basename(name))[0].lower()
    for suf in sorted(suffixes if suffixes is not None else DEFAULT_SUFFIXES, key=len, reverse=True):
        suf = suf.lower()
        if suf and stem.endswith(suf):
            stem = stem[: -len(suf)]
            break
    return stem


def _key(clip: Clip, suffixes, is_transcode: bool) -> str:
    base = clip.path or clip.name
    return normalize_stem(base, suffixes if is_transcode else [])


def compare(raws: List[Clip], transcodes: List[Clip], suffixes=None, fps_tol=0.01) -> List[Result]:
    by_stem: Dict[str, List[Clip]] = {}
    for t in transcodes:
        by_stem.setdefault(_key(t, suffixes, True), []).append(t)

    results: List[Result] = []
    used = set()
    for r in raws:
        stem = _key(r, suffixes, False)
        matches = by_stem.get(stem, [])
        used.add(stem)
        if not matches:
            results.append(Result(MISSING, stem, raw=r))
            continue
        if len(matches) > 1:
            results.append(Result(AMBIGUOUS, stem, raw=r, warnings=["%d transcodes share this name" % len(matches)]))
            continue
        t = matches[0]
        res = Result(OK, stem, raw=r, transcode=t)
        if r.frames is None or t.frames is None:
            res.status = MISMATCH
            res.warnings.append("frame count unavailable")
        else:
            res.delta = t.frames - r.frames
            if res.delta != 0:
                res.status = MISMATCH
        if r.fps and t.fps and abs(r.fps - t.fps) > fps_tol:
            res.warnings.append("FPS differs (%s vs %s)" % (r.fps, t.fps))
        if r.start_tc and t.start_tc and r.start_tc != t.start_tc:
            res.warnings.append("Start TC differs (%s vs %s)" % (r.start_tc, t.start_tc))
        results.append(res)

    for stem, ts in by_stem.items():
        if stem not in used:
            for t in ts:
                results.append(Result(ORPHAN, stem, transcode=t))

    return sort_results(results)


def sort_results(results: List[Result]) -> List[Result]:
    order = {MISSING: 0, MISMATCH: 1, AMBIGUOUS: 2, ORPHAN: 3, OK: 4}
    return sorted(results, key=lambda x: (order[x.status], x.stem))


def probe_frames(path: str) -> Optional[int]:
    """Count video packets with ffprobe; None if unavailable/unreadable."""
    ffprobe = shutil.which("ffprobe") or "/opt/homebrew/bin/ffprobe"
    if not path or not os.path.exists(path) or not os.path.exists(ffprobe):
        return None
    try:
        out = subprocess.run(
            [ffprobe, "-v", "error", "-count_packets", "-select_streams", "v:0",
             "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", path],
            capture_output=True, text=True, timeout=300,
        ).stdout.strip().split(",")[0]
        return int(out) if out.isdigit() else None
    except Exception:
        return None


def deep_check(results: List[Result]) -> None:
    """Fill *_probe for mismatches only."""
    for r in results:
        if r.status == MISMATCH and r.raw and r.transcode:
            r.raw_probe = probe_frames(r.raw.path)
            r.transcode_probe = probe_frames(r.transcode.path)


def summary(results: List[Result]) -> str:
    counts: Dict[str, int] = {}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1
    return " / ".join("%d %s" % (counts[s], s) for s in (OK, MISMATCH, MISSING, AMBIGUOUS, ORPHAN) if s in counts) or "no clips"


def write_csv(results: List[Result], path: str) -> None:
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["status", "stem", "raw_bin", "raw_file", "raw_frames", "transcode_file",
                    "transcode_frames", "delta", "raw_probe", "transcode_probe", "warnings"])
        for r in results:
            w.writerow([
                r.status, r.stem,
                r.raw.bin if r.raw else "", r.raw.path if r.raw else "", r.raw.frames if r.raw else "",
                r.transcode.path if r.transcode else "", r.transcode.frames if r.transcode else "",
                "" if r.delta is None else r.delta,
                "" if r.raw_probe is None else r.raw_probe,
                "" if r.transcode_probe is None else r.transcode_probe,
                "; ".join(r.warnings),
            ])
