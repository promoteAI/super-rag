# SuperRAG Frontend

React + TypeScript 前端应用，用于 SuperRAG 知识管理系统。

## 🚀 快速开始

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

启动成功后，在浏览器中打开：**http://localhost:3000**

> 💡 **提示**：如果看不到页面，请查看 [故障排除指南](./TROUBLESHOOTING.md)

## 功能特性

- 📁 Collections 管理页面
- 🔍 实时搜索过滤（带防抖）
- ➕ 创建新集合（模态框）
- 🗑️ 删除集合（带确认）
- ⏳ 加载骨架屏
- 🎨 精美的深色主题 UI
- 📱 响应式设计
- ♿ 键盘快捷键支持（ESC 关闭模态框）
- 🔒 错误处理和状态管理

## 技术栈

- **React 18** - UI 框架
- **TypeScript** - 类型安全
- **Vite** - 构建工具
- **React Router** - 路由管理
- **Axios** - HTTP 客户端
- **Lucide React** - 图标库
- **date-fns** - 日期格式化

## 开发命令

```bash
npm run dev      # 启动开发服务器
npm run build    # 构建生产版本
npm run preview  # 预览生产构建
npm run lint     # 代码检查
```

## API 集成

前端通过 `/api/v1` 路径与后端 API 通信。

**开发模式**：Vite 代理配置会将 `/api` 请求转发到 `http://localhost:8000`

**生产模式**：需要配置环境变量或反向代理

### 主要 API 端点

- `GET /api/v1/collections` - 获取集合列表
- `POST /api/v1/collections` - 创建集合
- `GET /api/v1/collections/{id}` - 获取单个集合
- `PUT /api/v1/collections/{id}` - 更新集合
- `DELETE /api/v1/collections/{id}` - 删除集合

详细 API 文档请查看 [API_DOCUMENTATION.md](./API_DOCUMENTATION.md)

## 项目结构

```
frontend/
├── src/
│   ├── api/              # API 客户端
│   │   └── client.ts     # Axios 配置和 API 方法
│   ├── components/       # React 组件
│   │   ├── Header.tsx    # 顶部导航栏
│   │   ├── Sidebar.tsx   # 侧边栏导航
│   │   ├── Layout.tsx    # 布局组件
│   │   ├── CollectionCard.tsx    # 集合卡片
│   │   ├── SearchBar.tsx         # 搜索栏
│   │   ├── AddCollectionButton.tsx  # 添加按钮和模态框
│   │   └── LoadingSkeleton.tsx  # 加载骨架屏
│   ├── pages/            # 页面组件
│   │   └── CollectionsPage.tsx  # Collections 页面
│   ├── types/           # TypeScript 类型定义
│   │   └── index.ts
│   ├── App.tsx          # 主应用组件
│   ├── main.tsx         # 入口文件
│   └── index.css        # 全局样式
├── index.html           # HTML 模板
├── package.json         # 依赖配置
├── vite.config.ts      # Vite 配置
├── start.sh            # 启动脚本
├── QUICK_START.md      # 快速启动指南
└── TROUBLESHOOTING.md  # 故障排除指南
```

## 样式系统

使用 CSS 变量管理主题颜色，支持深色主题：

```css
--bg-primary: #0f0f0f
--bg-secondary: #1a1a1a
--accent-blue: #3b82f6
--success-green: #10b981
```

## 浏览器支持

- Chrome (最新版)
- Firefox (最新版)
- Safari (最新版)
- Edge (最新版)

## 故障排除

如果遇到问题，请查看：
- [快速启动指南](./QUICK_START.md)
- [故障排除指南](./TROUBLESHOOTING.md)

## 下一步开发

- [ ] 实现编辑集合功能
- [ ] 实现查看详情页面
- [ ] 实现导入数据功能
- [ ] 实现与数据聊天功能
- [ ] 添加用户认证
- [ ] 添加更多页面（Marketplace, Chats, Settings）
