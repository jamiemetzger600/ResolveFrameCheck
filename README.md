# Raw vs Transcode Frame Check (DaVinci Resolve)

Compares frame counts of raw clips against their transcodes, matched by filename.

## Install (macOS)
1. Unzip, open Terminal, run: `./install.sh` (in the unzipped folder)
2. Restart Resolve. Open a project, then Workspace > Scripts > Utility > Raw vs Transcode Frame Check.

Works in Resolve Free and Studio. Re-run `install.sh` to update.

## Use
Bin layout expected: `Day03/{TX, A7-8, A9, A10, Audio}`. Select the Day bin (Cmd-click for several days) and click Run Check.
Missing transcodes and mismatches are listed first. Export CSV saves to the Desktop.
"Flag problems Red" sets clip colour on affected clips (modifies the project).

Command line (Studio only): `./framecheck_cli.py --raw A1 B1 --transcode TX`
