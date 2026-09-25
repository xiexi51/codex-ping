#!/usr/bin/env bash
set -euo pipefail

source_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
codex_binary=""
start_service=false

while (( $# )); do
  case "$1" in
    --codex-bin)
      [[ $# -ge 2 ]] || { echo '--codex-bin requires an executable path' >&2; exit 2; }
      codex_binary="$2"; shift 2 ;;
    --start) start_service=true; shift ;;
    -h|--help)
      echo 'Usage: ./install.sh [--codex-bin /path/to/codex] [--start]'
      echo 'Default: install files; --start enables linger and starts the service.'
      exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done

for dependency in python3 systemctl install readlink; do
  command -v "$dependency" >/dev/null || { echo "Missing dependency: $dependency" >&2; exit 1; }
done
if [[ -z "$codex_binary" ]]; then
  codex_binary="$(command -v codex || true)"
fi
if [[ ! -x "$codex_binary" ]]; then
  echo 'Codex CLI not found. Supply --codex-bin with the installed executable path.' >&2
  exit 1
fi
codex_binary="$(readlink -f -- "$codex_binary")"
codex_host="$(dirname -- "$codex_binary")/codex-code-mode-host"

export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=$XDG_RUNTIME_DIR/bus}"
systemctl --user show-environment >/dev/null
if $start_service; then
  loginctl enable-linger "$(id -un)"
fi

task_lib="$HOME/.local/lib/codex-ping"
task_config="$HOME/.config/codex-ping"
task_state="$HOME/.local/state/codex-ping"
was_running=false
if systemctl --user is-active --quiet codex-ping.service; then
  was_running=true
  systemctl --user stop codex-ping.service
fi

install -d -m 700 "$task_lib" "$task_config" "$task_state" "$task_state/work"
install -d "$HOME/.local/bin" "$HOME/.config/systemd/user"
for name in scheduler.py run.py limits.py display.py; do
  install -m 600 "$source_dir/src/$name" "$task_lib/$name"
done
install -m 700 "$source_dir/bin/codex-ping" "$HOME/.local/bin/codex-ping"
install -m 600 "$source_dir/systemd/codex-ping.service" "$HOME/.config/systemd/user/codex-ping.service"
if [[ ! -e "$task_config/settings.json" ]]; then
  install -m 600 "$source_dir/config/settings.example.json" "$task_config/settings.json"
fi
if [[ ! -e "$task_config/instructions.txt" ]]; then
  install -m 600 "$source_dir/config/instructions.txt" "$task_config/instructions.txt"
fi
install -m 600 "$source_dir/README.md" "$task_config/README.md"

pin_binary() {
  local source_binary="$1" destination="$2"
  if [[ "$source_binary" -ef "$destination" ]]; then return; fi
  # A hard link survives removal of an extension's original directory.
  rm -f -- "$destination.new"
  if ! ln -- "$source_binary" "$destination.new" 2>/dev/null; then
    cp -- "$source_binary" "$destination.new"
  fi
  mv -f -- "$destination.new" "$destination"
}
pin_binary "$codex_binary" "$task_lib/codex"
if [[ -x "$codex_host" ]]; then
  pin_binary "$codex_host" "$task_lib/codex-code-mode-host"
fi

systemctl --user daemon-reload
if $start_service; then
  systemctl --user enable --now codex-ping.service
elif $was_running; then
  systemctl --user start codex-ping.service
fi
echo 'Installed. Existing settings, login and schedule state were preserved.'
echo 'Manage with ~/.local/bin/codex-ping {status|logs|start|stop|restart|run|uninstall}'
if ! $start_service && ! $was_running; then
  echo 'To run after SSH logout: loginctl enable-linger "$(id -un)"'
  echo 'Then start: ~/.local/bin/codex-ping start'
fi
