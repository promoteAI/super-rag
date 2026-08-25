# 🚀 快速启动指南

## 前置要求

- Node.js 16+ 
- npm 或 yarn

## 启动步骤

### 方法 1: 使用启动脚本（推荐）

```bash
cd frontend
./start.sh
```

### 方法 2: 手动启动

```bash
# 1. 进入前端目录
cd frontend

# 2. 安装依赖（首次运行）
npm install

# 3. 启动开发服务器
npm run dev
```

## 访问应用

启动成功后，在浏览器中打开：

**http://localhost:3000**

## 常见问题

### 1. 端口被占用

如果 3000 端口被占用，Vite 会自动使用下一个可用端口（如 3001），请查看终端输出。

### 2. 依赖安装失败

```bash
# 清除缓存后重新安装
rm -rf node_modules package-lock.json
npm install
```

### 3. 页面空白

- 检查浏览器控制台是否有错误
- 确认后端 API 服务是否运行在 `http://localhost:8000`
- 检查网络请求是否正常

### 4. API 连接失败

确保后端服务正在运行：
```bash
# 在后端项目目录
uvicorn super_rag.app:app --reload --port 8000
```

## 开发命令

- `npm run dev` - 启动开发服务器
- `npm run build` - 构建生产版本
- `npm run preview` - 预览生产构建
- `npm run lint` - 代码检查

## 项目结构

```
frontend/
├── src/
│   ├── api/          # API 客户端
│   ├── components/   # React 组件
│   ├── pages/        # 页面组件
│   ├── types/        # TypeScript 类型
│   ├── App.tsx       # 主应用
│   └── main.tsx      # 入口文件
├── index.html
└── package.json
```

## 功能特性

✅ Collections 列表展示  
✅ 实时搜索过滤  
✅ 创建新集合  
✅ 删除集合  
✅ 加载骨架屏  
✅ 错误处理  
✅ 响应式设计  
✅ 深色主题 UI  

## 下一步

- 实现编辑集合功能
- 实现查看详情页面
- 实现导入数据功能
- 实现与数据聊天功能
