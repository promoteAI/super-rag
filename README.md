# Super RAG

一个功能强大的检索增强生成（RAG）系统，支持智能知识库管理、多格式文档解析、混合搜索和AI智能助手。

## 📋 目录

- [项目简介](#项目简介)
- [技术栈](#技术栈)
- [核心功能](#核心功能)
- [项目结构](#项目结构)
- [环境要求](#环境要求)
- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [使用指南](#使用指南)
- [开发指南](#开发指南)
- [部署说明](#部署说明)

## 🎯 项目简介

Super RAG 是一个企业级的RAG（Retrieval-Augmented Generation）系统，集成了文档解析、向量检索、全文搜索、知识图谱和智能Agent等功能。系统支持多种文档格式，提供混合搜索能力，并内置了基于MCP协议的智能Agent系统。

## 🛠 技术栈

### 后端
- **框架**: FastAPI
- **语言**: Python 3.11+
- **数据库**: MySQL (通过SeekDB/OceanBase)
- **向量数据库**: SeekDB (支持向量搜索和全文搜索)
- **对象存储**: RustFS (S3兼容) / 本地存储
- **任务调度**: Ray
- **ORM**: SQLAlchemy (异步)
- **数据库迁移**: Alembic

### 核心依赖
- **LLM集成**: LiteLLM (支持多种大模型)
- **文档解析**: Docling, MinerU
- **向量化**: 支持多种Embedding模型
- **Agent框架**: MCP Agent, MS Agent
- **可观测性**: OpenTelemetry

### 前端
- React + TypeScript

## ✨ 核心功能

### 1. 知识库管理
- 创建和管理多个知识库（Collections）
- 支持文档上传和批量导入
- 文档版本管理和状态跟踪
- 知识库订阅和分享

### 2. 文档处理
- **多格式支持**: PDF, Word, Markdown, 图片等
- **智能解析**: 
  - Docling: 结构化文档解析
  - MinerU: 学术论文和复杂文档解析
- **自动分块**: 可配置的文档分块策略
- **OCR支持**: 图片文字识别

### 3. 混合搜索
- **向量搜索**: 基于语义相似度的检索
- **全文搜索**: 基于关键词的精确匹配
- **图搜索**: 知识图谱关系检索（规划中）
- **重排序**: 搜索结果智能排序

### 4. 智能Agent
- **MCP协议支持**: 基于Model Context Protocol的Agent系统
- **工具调用**: 支持多种工具和技能
- **会话管理**: 多轮对话和上下文管理
- **流式响应**: 实时流式输出
- **多语言支持**: 中英文智能切换

### 5. 工作流引擎
- **NodeFlow**: 可配置的RAG工作流
- **节点类型**: 向量搜索、图搜索、LLM、合并、重排序等
- **灵活编排**: YAML配置工作流

### 6. 聊天系统
- 多Bot管理
- 会话历史记录
- 文件上传和搜索
- 知识库关联

### 7. 其他功能
- 播客、总结、脑图、PPT生成
- 学习计划和记忆曲线复习
- 视频AI分析、课件、文稿提取
- 个性化知识库
- 笔记管理
- 题库、错题本、AI出题、AI判题
- 习惯追踪和AI监督

## 📁 项目结构

```
super-rag/
├── super_rag/              # 主应用代码
│   ├── agent/              # Agent相关模块
│   │   ├── agent_session_manager.py
│   │   ├── mcp_app_factory.py
│   │   └── ...
│   ├── agent_pro/          # Agent Pro模块
│   ├── api/                # API路由
│   │   ├── bot.py
│   │   ├── chat.py
│   │   ├── collections.py
│   │   └── llm.py
│   ├── chunk/              # 文档分块
│   ├── db/                 # 数据库模型和操作
│   ├── fileparser/         # 文档解析器
│   ├── index/              # 索引管理
│   ├── llm/                # LLM相关
│   │   ├── completion/     # 文本生成
│   │   ├── embed/          # 向量化
│   │   └── rerank/         # 重排序
│   ├── nodeflow/           # 工作流引擎
│   ├── objectstore/        # 对象存储
│   ├── service/            # 业务逻辑服务
│   ├── source/             # 数据源
│   ├── tasks/              # 后台任务
│   ├── vectorstore/        # 向量存储连接器
│   └── ...
├── config/                 # 配置文件
├── deploy/                 # 部署配置
│   ├── docker-compose.yaml
│   └── start.sh
├── scripts/               # 脚本文件
├── migration/              # 数据库迁移
└── pyproject.toml          # 项目配置
```

## 📦 环境要求

- Python 3.11+
- Docker & Docker Compose
- MySQL/SeekDB
- RustFS (对象存储) 或 S3兼容存储
- (可选) Redis (缓存)

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone <repository-url>
cd super-rag
```

### 2. 安装依赖

项目使用 `uv` 作为包管理器：

```bash
# 安装 uv (如果未安装)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 安装项目依赖
uv sync
```

### 3. 启动基础设施

使用 Docker Compose 启动依赖服务：

```bash
cd deploy
docker compose up -d
```

这将启动：
- **SeekDB**: 向量数据库和关系数据库 (端口 2881, 2886)
- **RustFS**: 对象存储服务 (端口 9000, 9001)

### 4. 配置环境变量

创建 `.env` 文件（参考 `.env.example` 如果存在）：

```bash
# 数据库配置
MYSQL_HOST=127.0.0.1
MYSQL_PORT=2881
MYSQL_DB=super_rag
MYSQL_USER=root
MYSQL_PASSWORD=123456

# 向量数据库配置
VECTOR_DB_TYPE=seekdb
VECTOR_DB_CONTEXT='{"host":"localhost", "port":2881, "distance":"cosine", "user":"root", "password":"123456", "database":"test"}'

# 对象存储配置
OBJECT_STORE_TYPE=local  # 或 s3
OBJECT_STORE_LOCAL_ROOT_DIR=.objects

# 如果使用 S3
# OBJECT_STORE_S3_ENDPOINT=http://127.0.0.1:9000
# OBJECT_STORE_S3_ACCESS_KEY=minioadmin
# OBJECT_STORE_S3_SECRET_KEY=minioadmin
# OBJECT_STORE_S3_BUCKET=super_rag

# 其他配置
DEBUG=false
CHUNK_SIZE=400
CHUNK_OVERLAP_SIZE=20
```

### 5. 初始化数据库

```bash
# 运行数据库迁移
make migrate
```

### 6. 启动服务

```bash
# 开发模式（支持热重载）
make run-dev

# 生产模式
make run-prod

# 启动 Ray 调度器（后台任务）
make run-ray
```

服务将在 `http://localhost:8000` 启动。

### 7. 访问API文档

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## ⚙️ 配置说明

### 环境变量

主要配置项通过环境变量设置，完整列表见 `super_rag/config.py`：

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `MYSQL_HOST` | MySQL主机 | `127.0.0.1` |
| `MYSQL_PORT` | MySQL端口 | `2881` |
| `MYSQL_DB` | 数据库名 | `super_rag` |
| `VECTOR_DB_TYPE` | 向量数据库类型 | `seekdb` |
| `OBJECT_STORE_TYPE` | 对象存储类型 | `local` |
| `CHUNK_SIZE` | 文档分块大小 | `400` |
| `CHUNK_OVERLAP_SIZE` | 分块重叠大小 | `20` |
| `MAX_DOCUMENT_SIZE` | 最大文档大小(字节) | `100 * 1024 * 1024` |
| `CACHE_ENABLED` | 启用缓存 | `true` |

### 模型配置

LLM模型配置通过 `model_configs.json` 文件管理，支持多种模型提供商：
- OpenAI
- Anthropic
- DeepSeek
- ModelScope
- 其他 LiteLLM 支持的提供商

## 📖 使用指南

### 创建知识库

```bash
curl -X POST "http://localhost:8000/api/v1/collections" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "我的知识库",
    "description": "示例知识库"
  }'
```

### 上传文档

```bash
curl -X POST "http://localhost:8000/api/v1/collections/{collection_id}/documents" \
  -F "file=@document.pdf"
```

### 搜索知识库

```bash
curl -X POST "http://localhost:8000/api/v1/collections/{collection_id}/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "搜索内容",
    "top_k": 5
  }'
```

### 创建聊天会话

```bash
curl -X POST "http://localhost:8000/api/v1/bots/{bot_id}/chats" \
  -H "Content-Type: application/json"
```

## 🔧 开发指南

### 代码结构

- **API层** (`super_rag/api/`): FastAPI路由定义
- **服务层** (`super_rag/service/`): 业务逻辑实现
- **数据层** (`super_rag/db/`): 数据库模型和仓库模式
- **工具层** (`super_rag/utils/`): 工具函数

### 数据库迁移

```bash
# 创建新迁移
make makemigration

# 应用迁移
make migrate

# 回滚迁移
make downgrade
```

### 运行测试

```bash
# 使用 pytest
uv run pytest
```

### 代码规范

项目遵循 Python 标准代码规范，建议使用：
- `black` 进行代码格式化
- `ruff` 进行代码检查
- `mypy` 进行类型检查

## 🐳 部署说明

### Docker Compose 部署

项目提供了完整的 Docker Compose 配置：

```bash
cd deploy
docker compose up -d
```

### 生产环境建议

1. **数据库**: 使用独立的MySQL/OceanBase实例
2. **对象存储**: 使用生产级S3服务或RustFS集群
3. **缓存**: 配置Redis集群
4. **监控**: 集成OpenTelemetry进行链路追踪
5. **日志**: 配置集中式日志收集
6. **安全**: 
   - 使用HTTPS
   - 配置API密钥管理
   - 启用用户认证

### 环境变量管理

生产环境建议使用：
- Kubernetes Secrets
- HashiCorp Vault
- AWS Secrets Manager
- 其他密钥管理服务

## 📝 Makefile 命令

```bash
make help           # 显示帮助信息
make makemigration  # 生成数据库迁移
make migrate        # 应用数据库迁移
make run-dev        # 开发模式运行
make run-prod       # 生产模式运行
make run-ray        # 启动Ray调度器
```

## 🤝 贡献指南

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 📄 许可证

[添加许可证信息]

## 🔗 相关链接

- [FastAPI文档](https://fastapi.tiangolo.com/)
- [LiteLLM文档](https://docs.litellm.ai/)
- [SeekDB文档](https://www.oceanbase.com/)
- [MCP协议](https://modelcontextprotocol.io/)

## 📧 联系方式

[添加联系方式]

---

**注意**: 这是一个活跃开发中的项目，API和配置可能会发生变化。建议查看最新版本的代码和文档。
