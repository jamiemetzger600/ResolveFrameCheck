"""Fusion UIManager window: pick bins, run the check, view/export results."""
import json
import os

from . import core, resolve_io

CONFIG = os.path.expanduser("~/.resolve_framecheck.json")
COLORS = {core.OK: "#2e7d32", core.MISMATCH: "#c62828", core.MISSING: "#ef6c00",
          core.AMBIGUOUS: "#6a1b9a", core.ORPHAN: "#1565c0"}


def _load():
    try:
        with open(CONFIG) as f:
            return json.load(f)
    except Exception:
        return {}


def _save(cfg):
    try:
        with open(CONFIG, "w") as f:
            json.dump(cfg, f)
    except Exception:
        pass


def run(resolve, fusion, bmd):
    project = resolve.GetProjectManager().GetCurrentProject()
    if not project:
        print("No project open")
        return
    bins = resolve_io.list_bins(project)
    names = [b[0] for b in bins]
    cfg = _load()

    ui = fusion.UIManager
    disp = bmd.UIDispatcher(ui)
    win = disp.AddWindow({"ID": "FC", "WindowTitle": "Raw vs Transcode Frame Check",
                          "Geometry": [200, 200, 900, 640]}, ui.VGroup([
        ui.HGroup({"Weight": 0}, [
            ui.VGroup({"Weight": 1}, [
                ui.Label({"Text": "Select a Day bin (or a TX bin + its raw bins) - cmd/shift-click for several", "Weight": 0}),
                ui.Tree({"ID": "RawTree", "SelectionMode": "ExtendedSelection", "HeaderHidden": True, "MinimumSize": [300, 160]}),
            ]),
            ui.VGroup({"Weight": 1}, [
                ui.Label({"Text": "Transcode bin name", "Weight": 0}),
                ui.LineEdit({"ID": "TxName", "Text": cfg.get("tx_name", "TX"), "Weight": 0}),
                ui.Label({"Text": "Ignore bins named (comma separated)", "Weight": 0}),
                ui.LineEdit({"ID": "Skip", "Text": cfg.get("skip", "Audio"), "Weight": 0}),
                ui.Label({"Text": "Ignore transcode suffixes (comma separated)", "Weight": 0}),
                ui.LineEdit({"ID": "Suffixes", "Text": ",".join(cfg.get("suffixes", core.DEFAULT_SUFFIXES)), "Weight": 0}),
                ui.CheckBox({"ID": "Sub", "Text": "Include sub-bins", "Checked": cfg.get("sub", True), "Weight": 0}),
                ui.CheckBox({"ID": "Deep", "Text": "ffprobe deep check on mismatches", "Checked": cfg.get("deep", False), "Weight": 0}),
                ui.HGroup({"Weight": 0}, [ui.Button({"ID": "Run", "Text": "Run Check"}),
                                          ui.Button({"ID": "Csv", "Text": "Export CSV"}),
                                          ui.Button({"ID": "Flag", "Text": "Flag problems Red"})]),
            ]),
        ]),
        ui.Label({"ID": "Sum", "Text": "", "Weight": 0, "Alignment": {"AlignHCenter": True}}),
        ui.Tree({"ID": "Out", "Weight": 1, "SortingEnabled": False}),
    ]))
    itm = win.GetItems()

    for n in names:
        row = itm["RawTree"].NewItem()
        row.Text[0] = n
        itm["RawTree"].AddTopLevelItem(row)
    rawtree_items = [itm["RawTree"].TopLevelItem(i) for i in range(len(names))]
    # Preselect the day you're sitting in: current bin's TX + sibling raw bins.
    tx0 = cfg.get("tx_name", "TX").lower()
    skip0 = [x.strip().lower() for x in cfg.get("skip", "Audio").split(",")]
    cur = project.GetMediaPool().GetCurrentFolder()
    cur_name = cur.GetName() if cur else None
    day = None
    for p, f in bins:
        if f.GetName() == cur_name and any(c.GetName().lower() == tx0 for c in f.GetSubFolderList() or []):
            day = p
        elif p.endswith("/" + cur_name if cur_name else "\0") and day is None:
            parent = p.rsplit("/", 1)[0]
            pf = dict(bins)[parent]
            if any(c.GetName().lower() == tx0 for c in pf.GetSubFolderList() or []):
                day = parent
    if day:
        rawtree_items[names.index(day)].Selected = True

    cols = ["Status", "Name", "Raw frames", "Transcode frames", "Delta", "ffprobe raw/tc", "Notes"]
    hdr = itm["Out"].NewItem()
    for i, c in enumerate(cols):
        hdr.Text[i] = c
    itm["Out"].SetHeaderItem(hdr)
    itm["Out"].ColumnCount = len(cols)
    state = {"results": [], "folders": []}

    def selected_bins():
        return [names[i] for i, it in enumerate(rawtree_items) if it.Selected]

    def on_run(ev):
        tx_name = itm["TxName"].Text.strip()
        skip = [x.strip().lower() for x in itm["Skip"].Text.split(",") if x.strip()]
        sel = selected_bins()
        suffixes = [s.strip() for s in itm["Suffixes"].Text.split(",") if s.strip()]
        sub = itm["Sub"].Checked
        _save({"tx_name": tx_name, "skip": itm["Skip"].Text, "suffixes": suffixes, "sub": sub, "deep": itm["Deep"].Checked})
        folders = dict(bins)

        def base(n):
            return n.rsplit("/", 1)[-1].lower()

        def child_paths(n):
            return [n + "/" + c.GetName() for c in folders[n].GetSubFolderList() or []]

        # Groups of (raw bin paths, tx bin path). A selected "Day" bin is one that contains a TX child.
        groups, claimed = [], set()
        for n in sel:
            kids = child_paths(n)
            tx = [k for k in kids if base(k) == tx_name.lower()]
            if tx:
                raws_ = [k for k in kids if k != tx[0] and base(k) not in skip]
                groups.append((raws_, tx[0]))
                claimed.update(kids + [n])
        rest = [n for n in sel if n not in claimed]
        if rest:  # manual mode: one TX bin + its raw bins selected directly
            tx_sel = [n for n in rest if base(n) == tx_name.lower()]
            if len(tx_sel) != 1:
                itm["Sum"].Text = "Select a Day bin, or exactly one '%s' bin plus raw bins (found %d)" % (tx_name, len(tx_sel))
                return
            groups.append(([n for n in rest if n != tx_sel[0] and base(n) not in skip], tx_sel[0]))
        if not groups or not any(g[0] for g in groups):
            itm["Sum"].Text = "Select a Day bin (containing a '%s' bin)" % tx_name
            return
        res, flag_folders = [], []
        for raw_sel, tc_name in groups:
            raws = []
            for n in raw_sel:
                raws += resolve_io.clips_in(folders[n], n, sub)
            tcs = resolve_io.clips_in(folders[tc_name], tc_name, sub)
            res += core.compare(raws, tcs, suffixes)
            flag_folders += [folders[n] for n in raw_sel] + [folders[tc_name]]
        res = core.sort_results(res)
        if itm["Deep"].Checked:
            itm["Sum"].Text = "Running ffprobe..."
            core.deep_check(res)
        state["results"], state["folders"] = res, flag_folders
        itm["Out"].Clear()
        for r in res:
            row = itm["Out"].NewItem()
            probe = "" if r.raw_probe is None else "%s / %s" % (r.raw_probe, r.transcode_probe)
            vals = [r.status, r.stem, r.raw.frames if r.raw else "", r.transcode.frames if r.transcode else "",
                    "" if r.delta is None else "%+d" % r.delta, probe, "; ".join(r.warnings)]
            for i, v in enumerate(vals):
                row.Text[i] = str(v)
                row.TextColor[i] = {"R": 1, "G": 1, "B": 1, "A": 1} if i else _rgb(COLORS[r.status])
            itm["Out"].AddTopLevelItem(row)
        for i in range(len(cols)):
            itm["Out"].ColumnWidth[i] = 150 if i != 1 else 220
        itm["Sum"].Text = core.summary(res)

    def on_csv(ev):
        if state["results"]:
            path = os.path.expanduser("~/Desktop/framecheck_report.csv")
            core.write_csv(state["results"], path)
            itm["Sum"].Text = "Saved " + path

    def on_flag(ev):
        bad = {c.path for r in state["results"] if r.status != core.OK
               for c in (r.raw, r.transcode) if c}
        n = resolve_io.flag_clips(state["folders"], bad)
        itm["Sum"].Text = "Flagged %d clips Red" % n

    win.On.Run.Clicked = on_run
    win.On.Csv.Clicked = on_csv
    win.On.Flag.Clicked = on_flag
    win.On.FC.Close = lambda ev: disp.ExitLoop()
    win.Show()
    disp.RunLoop()
    win.Hide()


def _rgb(hexstr):
    h = hexstr.lstrip("#")
    return {"R": int(h[0:2], 16) / 255, "G": int(h[2:4], 16) / 255, "B": int(h[4:6], 16) / 255, "A": 1}
