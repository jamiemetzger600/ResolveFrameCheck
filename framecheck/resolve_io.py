"""Thin wrappers around the DaVinci Resolve scripting API."""
import sys
from typing import List, Tuple

from .core import Clip, clip_from_props

MODULES = "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules"


def get_resolve():
    """Return the resolve object (inside Resolve it is a global; externally import it)."""
    import builtins
    r = getattr(builtins, "resolve", None)
    if r is not None:
        return r
    sys.path.append(MODULES)
    import DaVinciResolveScript as dvr
    return dvr.scriptapp("Resolve")


def list_bins(project) -> List[Tuple[str, object]]:
    """Flatten bin tree to [(path like 'Master/A1', folder), ...]."""
    out = []

    def walk(folder, prefix):
        name = folder.GetName()
        path = name if not prefix else prefix + "/" + name
        out.append((path, folder))
        for sub in folder.GetSubFolderList() or []:
            walk(sub, path)

    walk(project.GetMediaPool().GetRootFolder(), "")
    return out


def clips_in(folder, bin_path: str, recursive=False) -> List[Clip]:
    clips = []
    for item in folder.GetClipList() or []:
        props = item.GetClipProperty() or {}
        clips.append(clip_from_props(props, bin_path))
    if recursive:
        for sub in folder.GetSubFolderList() or []:
            clips += clips_in(sub, bin_path + "/" + sub.GetName(), True)
    return clips


def flag_clips(folder_list, names, color="Red") -> int:
    """Set clip color on clips whose file path is in `names`. Modifies the project."""
    n = 0
    for folder in folder_list:
        for item in folder.GetClipList() or []:
            if (item.GetClipProperty("File Path") or "") in names:
                n += bool(item.SetClipColor(color))
    return n
