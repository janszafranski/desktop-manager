#!/usr/bin/env bash
# Re-apply the pure-black AMOLED surface ramp to the Caelestia scheme, keeping
# the catppuccin accents. Run this after `caelestia scheme set` or a wallpaper
# change, both of which regenerate scheme.json and reset surfaces to dark-gray.
# The shell reads scheme.json live (FileView watch), so this applies instantly.
set -euo pipefail
scheme="${XDG_STATE_HOME:-$HOME/.local/state}/caelestia/scheme.json"

python3 - "$scheme" <<'PY'
import json, os, sys, tempfile
p = sys.argv[1]
d = json.load(open(p))
d.setdefault("colours", {}).update({
    "background": "000000", "surface": "000000", "surfaceDim": "000000",
    "surfaceBright": "1a1a1a", "surfaceContainerLowest": "000000",
    "surfaceContainerLow": "0a0a0a", "surfaceContainer": "0d0d0d",
    "surfaceContainerHigh": "141414", "surfaceContainerHighest": "1c1c1c",
    "surfaceVariant": "2a2a2a", "surface0": "121212", "surface1": "1a1a1a",
    "surface2": "222222",
})
fd, t = tempfile.mkstemp(dir=os.path.dirname(p))
os.write(fd, json.dumps(d).encode()); os.close(fd); os.replace(t, p)
PY
echo "Black surfaces re-applied to $scheme"
