#!/usr/bin/env bash
# build-help.sh — generate the offline HTML help doc from DOCUMENTATION.md.
# DOCUMENTATION.md is the single source of truth; this derives help.html from it
# (styled header + "updates on GitHub" banner). Local images are inlined as
# base64 data URIs so the help renders fully OFFLINE, wherever it's opened.
# Prefers pandoc, falls back to python-markdown (markdown_py). Exit 3 = no converter.
set -euo pipefail
SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$SELF/DOCUMENTATION.md"
OUT="${1:-$HOME/.local/share/steady-mouse/help.html}"
HDR="$SELF/assets/help-header.html"
BAN="$SELF/assets/help-banner.html"
mkdir -p "$(dirname "$OUT")"

# 1. inline every local image reference as a base64 data URI (offline-proof).
#    remote (raw.githubusercontent) URLs are mapped back to assets/<basename>.
TMP="$(mktemp --suffix=.md)"
trap 'rm -f "$TMP"' EXIT
python3 - "$SRC" "$SELF" "$TMP" <<'PY'
import base64, mimetypes, os, re, sys
src, root, out = sys.argv[1], sys.argv[2], sys.argv[3]
md = open(src, encoding="utf-8").read()
def repl(m):
    path = m.group(2)
    if path.startswith(("http://", "https://", "data:")):
        cand = os.path.join(root, "assets", os.path.basename(path))
        if not os.path.exists(cand):
            return m.group(0)
        path = cand
    fp = path if os.path.isabs(path) else os.path.join(root, path)
    if not os.path.exists(fp):
        return m.group(0)
    mime = mimetypes.guess_type(fp)[0] or "image/png"
    b64 = base64.b64encode(open(fp, "rb").read()).decode()
    return f'{m.group(1)}"data:{mime};base64,{b64}"'
md = re.sub(r'(src=)"([^"]+)"', repl, md)
open(out, "w", encoding="utf-8").write(md)
PY

# 2. convert to standalone HTML
if command -v pandoc >/dev/null 2>&1; then
  pandoc "$TMP" -s --metadata title="Steady Mouse — Help" \
    --include-in-header "$HDR" --include-before-body "$BAN" -o "$OUT"
elif command -v markdown_py >/dev/null 2>&1; then
  {
    echo '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
    echo '<meta name="viewport" content="width=device-width, initial-scale=1">'
    echo '<title>Steady Mouse — Help</title>'
    cat "$HDR"
    echo '</head><body>'
    cat "$BAN"
    markdown_py -x tables -x fenced_code "$TMP"
    echo '</body></html>'
  } > "$OUT"
else
  echo "build-help: no markdown converter (pandoc / markdown_py) found" >&2
  exit 3
fi
echo "build-help: wrote $OUT"
