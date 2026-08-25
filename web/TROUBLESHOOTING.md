# 🔧 故障排除指南

## 问题：看不到页面

### 检查清单

#### 1. 确认依赖已安装

```bash
cd frontend
ls node_modules
```

如果 `node_modules` 目录不存在或为空，运行：
```bash
npm install
```

#### 2. 确认开发服务器已启动

在终端中应该看到类似输出：
```
  VITE v5.0.8  ready in 500 ms

  ➜  Local:   http://localhost:3000/
  ➜  Network: use --host to expose
```

如果没有，运行：
```bash
npm run dev
```

#### 3. 检查浏览器控制台

打开浏览器开发者工具（F12），查看：
- **Console** 标签：是否有 JavaScript 错误
- **Network** 标签：API 请求是否成功

#### 4. 检查后端服务

前端需要连接到后端 API。确保后端服务运行在 `http://localhost:8000`

```bash
# 测试后端是否可访问
curl http://localhost:8000/health
```

应该返回：
```json
{"status":"healthy","service":"super_rag-api"}
```

#### 5. 清除缓存

```bash
# 清除 npm 缓存
npm cache clean --force

# 删除 node_modules 和重新安装
rm -rf node_modules package-lock.json
npm install
```

#### 6. 检查端口占用

如果 3000 端口被占用：
```bash
# 查看端口占用
lsof -i :3000

# 或者修改 vite.config.ts 中的端口
```

#### 7. 检查文件完整性

确认以下关键文件存在：
- ✅ `src/main.tsx`
- ✅ `src/App.tsx`
- ✅ `src/index.css`
- ✅ `index.html`
- ✅ `package.json`
- ✅ `vite.config.ts`

#### 8. 检查 TypeScript 编译错误

```bash
npm run build
```

如果有 TypeScript 错误，会在这里显示。

## 常见错误

### 错误：Cannot find module 'react'

**解决方案：**
```bash
npm install react react-dom
```

### 错误：Port 3000 is already in use

**解决方案：**
- 关闭占用端口的进程
- 或修改 `vite.config.ts` 中的端口号

### 错误：Failed to load collections

**原因：** 后端 API 未运行或无法连接

**解决方案：**
1. 启动后端服务
2. 检查 `vite.config.ts` 中的代理配置
3. 检查后端 CORS 设置

### 页面空白但无错误

**可能原因：**
1. React 组件渲染错误
2. CSS 样式问题
3. 路由配置问题

**解决方案：**
1. 检查浏览器控制台
2. 检查 React DevTools
3. 查看 Network 标签中的请求

## 调试技巧

### 1. 启用详细日志

在 `vite.config.ts` 中添加：
```typescript
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    strictPort: true,
  },
  logLevel: 'info',
})
```

### 2. 检查构建输出

```bash
npm run build
npm run preview
```

### 3. 使用 React DevTools

安装 React Developer Tools 浏览器扩展，检查组件树和状态。

## 获取帮助

如果以上方法都无法解决问题，请提供：
1. 浏览器控制台的完整错误信息
2. 终端中的完整输出
3. `package.json` 内容
4. Node.js 版本 (`node -v`)
