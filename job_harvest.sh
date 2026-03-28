#!/usr/bin/env bash

set -u

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_CONFIG="$ROOT_DIR/config.yaml"
DEFAULT_HOST="127.0.0.1"
DEFAULT_PORT="8000"

CONFIG_PATH="$DEFAULT_CONFIG"
HOST="$DEFAULT_HOST"
PORT="$DEFAULT_PORT"

choose_python() {
  if [[ -x "$ROOT_DIR/.venv/Scripts/python.exe" ]]; then
    echo "$ROOT_DIR/.venv/Scripts/python.exe"
    return
  fi

  if command -v python >/dev/null 2>&1; then
    command -v python
    return
  fi

  if command -v py >/dev/null 2>&1; then
    echo "py -3"
    return
  fi

  echo ""
}

PYTHON_CMD="$(choose_python)"

print_header() {
  clear
  cat <<EOF
========================================
 job_harvest command menu
========================================
 workspace : $ROOT_DIR
 python    : ${PYTHON_CMD:-not found}
 config    : $CONFIG_PATH
 server    : http://$HOST:$PORT
========================================
1) Install or update dependencies
2) Start web server
3) Start web server with reload
4) Run one collection from config
5) Show generated queries
6) Run tests
7) Change config/host/port
8) Exit
EOF
}

pause() {
  read -rp "Press Enter to continue... " _
}

ensure_python() {
  if [[ -n "$PYTHON_CMD" ]]; then
    return 0
  fi

  echo "Python was not found. Create .venv or install Python first."
  pause
  return 1
}

run_python() {
  if [[ "$PYTHON_CMD" == "py -3" ]]; then
    py -3 "$@"
    return
  fi

  "$PYTHON_CMD" "$@"
}

run_command() {
  local title="$1"
  shift

  clear
  echo "== $title =="
  echo
  "$@"
  local status=$?
  echo
  if [[ $status -eq 0 ]]; then
    echo "Completed successfully."
  else
    echo "Command failed with exit code $status."
  fi
  pause
}

change_settings() {
  clear
  echo "Current config : $CONFIG_PATH"
  read -rp "New config path (Enter keeps current): " input_config
  if [[ -n "$input_config" ]]; then
    if [[ "$input_config" = /* || "$input_config" =~ ^[A-Za-z]:[\\/].* ]]; then
      CONFIG_PATH="$input_config"
    else
      CONFIG_PATH="$ROOT_DIR/$input_config"
    fi
  fi

  echo "Current host   : $HOST"
  read -rp "New host (Enter keeps current): " input_host
  if [[ -n "$input_host" ]]; then
    HOST="$input_host"
  fi

  echo "Current port   : $PORT"
  read -rp "New port (Enter keeps current): " input_port
  if [[ -n "$input_port" ]]; then
    PORT="$input_port"
  fi

  echo
  echo "Updated settings:"
  echo "config : $CONFIG_PATH"
  echo "server : http://$HOST:$PORT"
  pause
}

while true; do
  print_header
  read -rp "Select menu: " choice

  case "$choice" in
    1)
      ensure_python || continue
      run_command \
        "Install dependencies" \
        run_python -m pip install -r "$ROOT_DIR/requirements.txt"
      ;;
    2)
      ensure_python || continue
      run_command \
        "Start web server (Ctrl+C to stop)" \
        run_python -m job_harvest serve --host "$HOST" --port "$PORT"
      ;;
    3)
      ensure_python || continue
      run_command \
        "Start web server with reload (Ctrl+C to stop)" \
        run_python -m job_harvest serve --host "$HOST" --port "$PORT" --reload
      ;;
    4)
      ensure_python || continue
      run_command \
        "Run one collection" \
        run_python -m job_harvest --config "$CONFIG_PATH" run
      ;;
    5)
      ensure_python || continue
      run_command \
        "Show generated queries" \
        run_python -m job_harvest --config "$CONFIG_PATH" show-queries
      ;;
    6)
      ensure_python || continue
      run_command \
        "Run tests" \
        run_python -m unittest discover -s "$ROOT_DIR/tests" -v
      ;;
    7)
      change_settings
      ;;
    8)
      echo "Exiting."
      exit 0
      ;;
    *)
      echo
      echo "Invalid selection: $choice"
      pause
      ;;
  esac
done
