#!/bin/sh
# Run one ai-forward pack hook with a Python 3 interpreter resolved at run time (PLAT-A, PLAT-C).
#
# Antigravity runs hook commands through cmd.exe on Windows, from <repo>/.agents (measured 2026-09-24,
# agy 1.2.10), so its hook config cannot hold POSIX shell syntax. Each agy hook command is therefore one
# plain `git` invocation, parsed alike by cmd.exe and sh, that runs this script as a git alias:
#   git -c alias.aif-hook=!sh aif-hook docs/ai-forward-pack/hooks/run-hook.sh <hook>.py --host agy ...
# git runs `!` aliases through its own sh, from the top of the working tree, and passes stdin and the
# exit status through, so a hook's JSON payload and its blocking exit code both reach the host unchanged.
#
# Usage: run-hook.sh <hook file name> [hook arguments...]
hook="$1"
shift
py=$(python3 -c 'import sys;print(sys.executable)' 2>/dev/null)
[ -x "$py" ] || py=$(python -c 'import sys;print(sys.executable)')
exec "$py" "docs/ai-forward-pack/hooks/$hook" "$@"
