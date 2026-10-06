#!/bin/zsh
# Install into Resolve's Scripts menu (Workspace > Scripts > Utility). Safe to re-run to update.
set -e
HERE="${0:A:h}"
LIB="$HOME/Library/Application Support/ResolveFrameCheck"
DEST="$HOME/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility"
mkdir -p "$LIB" "$DEST"
rm -rf "$LIB/framecheck"
cp -R "$HERE/framecheck" "$LIB/framecheck"
find "$LIB" -name __pycache__ -prune -exec rm -rf {} +
sed "s|__INSTALL_DIR__|$LIB|" "$HERE/Raw vs Transcode Frame Check.py" > "$DEST/Raw vs Transcode Frame Check.py"
echo "Installed. Restart Resolve, then Workspace > Scripts > Utility > Raw vs Transcode Frame Check"
