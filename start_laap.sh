#!/usr/bin/env bash
# LAAP Brain API 一键启动脚本 (cognitive engine + OpenCode plugin endpoints)
# 用法: ./start_laap.sh [start|stop|restart|status]   默认 start
set -euo pipefail
cd "$(dirname "$0")"

PORT="${LAAP_PORT:-11546}"
PYTHON="${PYTHON:-.venv/bin/python}"
PID_FILE="laap_api.pid"
LOG_DIR="logs"
LOG_FILE="$LOG_DIR/laap_api.log"

is_running() {
  [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null
}

start() {
  if is_running; then
    echo "已在运行 (pid $(cat "$PID_FILE")) :$PORT"
    return 0
  fi
  mkdir -p "$LOG_DIR"
  nohup "$PYTHON" -m laap_brain.api --port "$PORT" >>"$LOG_FILE" 2>&1 &
  echo $! > "$PID_FILE"
  echo "已启动 LAAP API :$PORT (pid $!, 日志 $LOG_FILE)"
}

stop() {
  if is_running; then
    pid="$(cat "$PID_FILE")"
    kill "$pid" 2>/dev/null && echo "已停止 (pid $pid)" || echo "进程 $pid 未找到"
  else
    echo "未运行"
  fi
  rm -f "$PID_FILE"
}

status() {
  if is_running; then
    echo "运行中 (pid $(cat "$PID_FILE")) :$PORT"
  else
    echo "未运行"
  fi
}

case "${1:-start}" in
  start) start ;;
  stop) stop ;;
  restart) stop; start ;;
  status) status ;;
  *) echo "用法: $0 {start|stop|restart|status}"; exit 1 ;;
esac
