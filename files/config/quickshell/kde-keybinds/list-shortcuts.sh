#!/usr/bin/env bash
# Emit "<combo>\t<action>" for every ACTIVE KDE global shortcut, sorted by key combo.
# Parses ~/.config/kglobalshortcutsrc: component action lines
# (Action=shortcut,default,friendly) and [services][*.desktop] _launch= entries.
# Reads a plain file, so it works from any session.
set -uo pipefail
CONF="${1:-$HOME/.config/kglobalshortcutsrc}"

awk '
  function trim(s){ sub(/^[ \t]+/,"",s); sub(/[ \t]+$/,"",s); return s }
  /^\[/ {
      svc=""; skip=($0=="[$Version]")
      if ($0 ~ /^\[services\]\[/) {
          svc=$0; sub(/^\[services\]\[/,"",svc); sub(/\]$/,"",svc); sub(/\.desktop$/,"",svc)
      }
      next
  }
  skip { next }
  /^_k_friendly_name=/ { next }
  /^update_info=/ { next }
  /=/ {
      eq=index($0,"="); key=substr($0,1,eq-1); val=substr($0,eq+1)
      c=index(val,","); sc=(c>0)?substr(val,1,c-1):val      # active = before first comma
      t=index(sc,"\\t"); if(t>0) sc=substr(sc,1,t-1)        # first of the \t-escaped list
      sc=trim(sc)
      if (sc=="" || sc=="none") next
      if (key=="_launch") {
          if      (svc=="floorp")                  action="Floorp"
          else if (svc=="org.kde.plasma.emojier")  action="Emoji selector"
          else if (svc=="caelestia-launcher")      action="App launcher"
          else if (svc=="openclaw-chat")           action="OpenClaw chat"
          else if (svc=="claude-code")             action="Claude Code"
          else if (svc=="floorp-fe0c47aa-eaaf-4a45-8cda-01aca864f927") action="YouTube (webapp)"
          else if (svc!="")                        action="Launch " svc
          else                                     action="Launch"
      } else {
          n=split(val,a,","); action=(n>=3 && a[3]!="")? a[3] : key
      }
      printf "%s\t%s\n", sc, action
  }
' "$CONF" \
  | awk -F'\t' '!seen[$0]++' \
  | awk -F'\t' '
      # Prepend two sort columns: the bare key (modifiers stripped) and a
      # modifier rank, so variants of a key group together — bare bind first,
      # then Alt, Shift, Ctrl (and combos) — instead of scattering by prefix.
      {
        combo=$1; key=combo; sub(/.*\+/,"",key)       # strip up to the last +
        rank=0
        if (combo ~ /[Aa]lt/)                rank+=1
        if (combo ~ /[Ss]hift/)              rank+=2
        if (combo ~ /[Cc]trl|[Cc]ontrol/)    rank+=4
        printf "%s\t%d\t%s\n", tolower(key), rank, $0
      }' \
  | sort -f -t "$(printf '\t')" -k1,1 -k2,2n \
  | cut -f3-
