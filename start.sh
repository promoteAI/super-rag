#!/bin/bash

# 默认环境为prod，可以通过第一个参数设置为dev或prod
ENV=${1:-dev}

if [ "$ENV" = "dev" ]; then
  make run-ui-dev &
  make run-dev
  wait
elif [ "$ENV" = "prod" ]; then
  make run-ui-dev &
  make run-prod
  wait
else
  echo "Usage: $0 [dev|prod]"
  exit 1
fi