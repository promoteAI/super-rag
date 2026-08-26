#!/bin/bash

# 默认环境为prod，可以通过第一个参数设置为dev或prod
ENV=${1:-dev}

cleanup() {
  echo ""
  echo "收到中断信号，正在取消所有进程..."
  trap - INT TERM
  # 终止所有后台任务及其进程组，避免 Ctrl+C 后残留
  for pid in $(jobs -p); do
    kill -TERM -"$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
  exit 130
}

trap cleanup INT TERM

wait_for_backend() {
  local url="${BACKEND_HEALTH_URL:-http://127.0.0.1:8000/health}"
  local max_attempts="${BACKEND_WAIT_ATTEMPTS:-3600}"
  local attempt=1

  echo "等待后端启动完成..."
  while [ "$attempt" -le "$max_attempts" ]; do
    if curl -sf "$url" >/dev/null 2>&1; then
      echo "后端已就绪，开始启动前端"
      return 0
    fi
    sleep 1
    attempt=$((attempt + 1))
  done

  echo "等待后端启动超时（${max_attempts}s）"
  return 1
}

start_frontend_after_backend() {
  if ! wait_for_backend; then
    for pid in $(jobs -p); do
      kill -TERM -"$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
    done
    wait 2>/dev/null || true
    exit 1
  fi
  make run-ui-dev &
  wait
}

if [ "$ENV" = "dev" ]; then
  make run-dev &
  start_frontend_after_backend
elif [ "$ENV" = "prod" ]; then
  make run-prod &
  start_frontend_after_backend
else
  echo "Usage: $0 [dev|prod]"
  exit 1
fi