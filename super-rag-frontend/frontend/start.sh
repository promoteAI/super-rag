#!/bin/bash

echo "🚀 启动 SuperRAG 前端应用..."
echo ""

# 检查 node_modules 是否存在
if [ ! -d "node_modules" ]; then
    echo "📦 正在安装依赖..."
    npm install
    echo ""
fi

echo "✅ 启动开发服务器..."
echo "📍 应用将在 http://localhost:3000 启动"
echo ""

npm run dev
