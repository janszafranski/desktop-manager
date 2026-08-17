source /usr/share/cachyos-fish-config/cachyos-config.fish

# overwrite greeting
# potentially disabling fastfetch
#function fish_greeting
#    # smth smth
#end

# uv
fish_add_path "/home/jan/.local/bin"

# launch claude with permission prompts disabled
alias claude+="claude --allow-dangerously-skip-permissions --permission-mode bypassPermissions"
