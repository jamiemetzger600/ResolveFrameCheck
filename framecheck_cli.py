#!/usr/bin/env python3
"""External runner (Resolve Studio; Preferences > General > External scripting using: Local).

Example: ./framecheck_cli.py --raw A1 B1 A2 --transcode Transcodes --csv report.csv --deep
Bin names may be a bare name or a path like 'Master/A1'.
"""
import argparse
import sys

from framecheck import core, resolve_io


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", nargs="+", required=True)
    ap.add_argument("--transcode", required=True)
    ap.add_argument("--suffixes", default=",".join(core.DEFAULT_SUFFIXES))
    ap.add_argument("--no-sub", action="store_true", help="don't recurse into sub-bins")
    ap.add_argument("--deep", action="store_true")
    ap.add_argument("--csv")
    a = ap.parse_args()

    resolve = resolve_io.get_resolve()
    if not resolve:
        sys.exit("Could not connect to Resolve (is it running with external scripting enabled?)")
    project = resolve.GetProjectManager().GetCurrentProject()
    bins = resolve_io.list_bins(project)

    def find(name):
        hits = [f for p, f in bins if p == name or p.split("/")[-1] == name]
        if len(hits) != 1:
            sys.exit("Bin '%s' matched %d bins; use a full path" % (name, len(hits)))
        return hits[0]

    sub = not a.no_sub
    raws = [c for n in a.raw for c in resolve_io.clips_in(find(n), n, sub)]
    tcs = resolve_io.clips_in(find(a.transcode), a.transcode, sub)
    res = core.compare(raws, tcs, [s for s in a.suffixes.split(",") if s])
    if a.deep:
        core.deep_check(res)
    for r in res:
        if r.status != core.OK:
            print("%-18s %s  raw=%s tc=%s delta=%s %s" % (
                r.status, r.stem, r.raw.frames if r.raw else "-", r.transcode.frames if r.transcode else "-",
                r.delta, "; ".join(r.warnings)))
    print(core.summary(res))
    if a.csv:
        core.write_csv(res, a.csv)
    sys.exit(1 if any(r.status != core.OK for r in res) else 0)


if __name__ == "__main__":
    main()
