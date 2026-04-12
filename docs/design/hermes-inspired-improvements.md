# Super-RAG 借鉴 Hermes Agent：范围确认、检索式记忆与 Doctor 规格

本文档落实 [Hermes Agent](https://github.com/NousResearch/hermes-agent) 对标思路下的**产品范围决策清单**、**检索式记忆技术设计**、**`super-rag doctor` 自检规格**与**可执行 backlog（§4）**，供评审与分阶段实现使用。

---

## 1. P0 / P1 范围确认（产品决策清单）

### 1.1 推荐默认优先级（工程侧建议）

在无法一揽子实现 Hermes 全部能力的前提下，建议按价值与现有架构契合度排序：

| 优先级 | 能力包 | 是否建议纳入首波 | 理由 |
|--------|--------|------------------|------|
| **P0** | 检索式记忆 + `context_limit` 可配置 | **是** | 与现有 [MySQL 会话历史](../../super_rag/utils/history.py)、[AgentMemoryManager](../../super_rag/agent/agent_memory_manager.py)、SeekDB 向量能力天然衔接，不依赖新渠道 |
| **P0** | Doctor 类部署自检 | **是** | 私有化 / 多组件部署排障成本高，纯增量、风险低 |
| **P0** | 工具与多租户安全基线（文档 + 配置项） | **是** | 企业场景刚需，可与现有鉴权并行演进 |
| **P1** | Skills 与 agentskills.io 对齐、Marketplace 统一元数据 | 视产品路线 | 已有 [AgentSkill](../../super_rag/agent_pro/agent_skill.py) / MCP，重在标准与发布流程 |
| **P1** | NodeFlow 并行分支、超时、取消 | 视工作流复杂度 | 与「子代理」体验部分等价 |
| **P1** | 用户级自然语言定时任务 | **有条件** | 需独立队列、权限与审计；与 [Ray 索引调度](../../super_rag/tasks/scheduler.py) 职责不同，避免混在同一调度器 |
| **P2** | Telegram/Discord/Slack 等消息网关 | **仅在有明确 IM 场景时** | 会话绑定、推送、配对与安全成本高 |
| **P2** | 轨迹导出与离线评测 | 研究/微调阶段 | 可与 OpenTelemetry 扩展衔接 |

### 1.2 需产品 / 负责人勾选的决策项

请在实施前确认（可复制到 issue 或评审纪要）：

- [ ] **记忆检索**：是否对「单会话全文/语义检索」与「跨会话检索（同用户多 chat）」同时立项，还是先做单会话？
- [ ] **消息网关**：未来 6 个月内是否有 IM 端硬需求？若无，P2 冻结。
- [ ] **用户定时任务**：是否允许 Agent 代表用户发起到聊天/邮件/ webhook？若否，仅保留运维级定时（与 Hermes cron 不同）。
- [ ] **合规**：记忆索引是否需排除某些 Bot/租户或消息类型（如含敏感标记的消息）？

---

## 2. 检索式记忆设计（P0）

### 2.1 目标

在保留「最近 N 轮」滑动窗口（当前 [create_memory_from_history](../../super_rag/agent/agent_memory_manager.py) 的 `context_limit`，默认 4 轮即约 `context_limit * 2` 条消息）的同时，从**更长历史**中检索与当前 query 相关的片段，注入模型上下文，对标 Hermes 的跨会话回忆能力（实现路径可采用 FTS + 向量，而非照搬 FTS5）。

### 2.2 索引源（Index source）

| 数据源 | 内容 | 说明 |
|--------|------|------|
| **主源** | `MySQLChatMessageHistory` 持久化的消息 | 与现有 `get_messages`（见 [history.py](../../super_rag/utils/history.py)）一致，`raw_message` / `StoredChatMessage` 可还原 role 与文本 |
| **可选增强** | 异步生成的「会话摘要」表或字段 | 长会话先摘要再索引摘要，降低存储与检索噪声；可与现有/未来 summarization 任务结合 |
| **排除** | 工具原始 JSON 超大负载 | 可配置仅索引 `human` / `ai` 的 `content` 文本，工具调用可摘要后入库 |

**跨会话范围（可配置）**

- `scope=chat`：仅 `chat_id` 当前会话（默认，合规友好）。
- `scope=user`：同一 `user_id` 下多个 `chat_id`（需权限与配额，防越权）。

### 2.3 索引形态（建议两阶段）

**阶段 A（快落地）**

- MySQL：`FULLTEXT` 或在应用层对近期消息做关键词检索（若 DBA 限制全文，可用 SeekDB 仅存 memory 向量）。
- 检索单位：**单条消息**或**固定窗口拼接**（例如相邻 user+assistant 为一条 chunk）。

**阶段 B（与 RAG 一致）**

- 使用现有 [VectorStoreConnectorAdaptor](../../super_rag/config.py)（`VECTOR_DB_TYPE` / `VECTOR_DB_CONTEXT`）建立独立 **memory collection**（命名建议：`memory_{tenant_or_user}` 或单 collection + 过滤字段 `chat_id` / `user_id`）。
- 写入时机：消息落库成功后异步任务（与文档索引类似的队列，可 Ray 或应用内 background task），embedding 与文档 chunk 共用同一套 embed 配置。

### 2.4 注入位置（Injection point）

推荐在 **组装发给 LLM 的 messages 之前** 完成，与 Hermes「检索 → 再对话」一致：

1. `AgentChatService.process_agent_message`（或等价入口）在 `create_memory_from_history` **之后**调用新组件 `MemoryRetriever.retrieve(query, chat_id, user_id, config)`。
2. 将检索结果格式化为 **一条 `system` 或 `user` 前缀块**（建议 `system`，名如 `Relevant past conversation`），**放在**滑动窗口记忆之前或之后需固定顺序并写死规范：
   - **推荐顺序**：`[system 主指令] → [检索记忆块] → [SimpleMemory 中最近 context_limit 轮]`，避免检索块被截断在末尾。
3. 总 token 预算：对检索块设 `max_chars` / `max_tokens`，与 `maxTokens`（当前如 8192）协调，避免挤占工具结果。

### 2.5 与 `context_limit` 的关系

| 参数 | 职责 |
|------|------|
| `context_limit` | **精确连贯上下文**：最近 N 轮对话，保证指代消解与工具链连续性 |
| 检索 Top-K | **长期相关片段**：补充窗口外的事实，不替代最近轮次 |
| 配置建议 | Bot 级或全局：`context_limit`（默认可保持 4）、`memory_retrieval_top_k`、`memory_retrieval_enabled`、`memory_scope` |

**合并算法（逻辑描述）**

1. 始终加载最近 `context_limit * 2` 条消息进入 `SimpleMemory`（与现实现一致）。
2. 若开启检索：用**当前用户最新一条 user 文本**（或完整 comprehensive_prompt 的摘要）作为 query，检索 Top-K。
3. 对检索结果做 **去重**（与滑动窗口内 message id 或内容 hash 去重），再拼接为单一上下文块注入。

### 2.6 隐私与合规

- 检索范围默认 `chat`；`user` 跨会话需显式功能开关与用户同意策略。
- 删除会话时需级联删除或失效 memory 索引条目。

---

## 3. `super-rag doctor` 自检规格（P0）

对标 `hermes doctor`：在部署现场快速判断「哪一环坏了」，输出**可复制**的诊断报告，供运维与技术支持使用。

### 3.1 交付形态

- **CLI**：`python -m super_rag.doctor` 或 `super-rag doctor`（若后续在 `pyproject` 定义 entry point）。
- **可选 HTTP**：`GET /api/v1/health/deep` 或 `GET /api/v1/doctor`（需 **admin / 内网** 权限，避免信息泄露）。

### 3.2 检查项（与当前仓库配置对齐）

每项结果枚举：`ok` | `warn` | `fail` | `skipped`（不适用时）。

| ID | 检查项 | 实现要点 |
|----|--------|----------|
| `db` | MySQL / `DATABASE_URL` 连通 | 使用与 [new_async_engine](../../super_rag/config.py) 相同 URL，`SELECT 1` 或轻量查询 |
| `vector` | SeekDB（或 `VECTOR_DB_TYPE`） | 解析 `VECTOR_DB_CONTEXT` JSON，执行连接 + 最小读操作（如 list collection 或 ping，依 adaptor 能力） |
| `object_store` | 对象存储 | `local`：目录可写；`s3`：head bucket 或 put/delete 探测小对象（可配置仅 head） |
| `model_configs` | `model_configs.json` | 文件存在、JSON 可解析、至少一个 completion 配置 |
| `ray` | Ray 集群（若启用索引任务） | 尝试 `ray.init` 或与 [ray_schedule.py](../../config/ray_schedule.py) 相同策略；若部署未用 Ray，标记 `skipped` 并说明依据环境变量 |
| `neo4j` | 图模块（若使用 Graphiti） | `NEO4J_URI` 连通；若不启用图功能，`skipped` |
| `jwt` | 生产安全配置 | `DEPLOYMENT_MODE=production` 或等价时，`JWT_SECRET` 不得为默认值（与 [config](../../super_rag/config.py) 默认对比） |
| `optional_services` | 非核心依赖 | `WHISPER_HOST`、`PADDLEOCR_HOST`、`DOCRAY_HOST`：能解析则 TCP/HTTP ping，失败为 `warn` |
| `mcp` | MCP 子应用挂载 | 可选：请求 `SUPER_RAG_MCP_URL` 或本机 `/mcp` 的 metadata（若可匿名探测） |

### 3.3 输出格式

**stdout（人类可读）**

- 头部：时间、主机名、`DEPLOYMENT_MODE`、应用版本/commit（若可得）。
- 每项一行：`[ok|warn|fail|skipped] id — 简短说明`。
- 尾部：若有 `fail`，打印「建议下一步」一行（如检查 `MYSQL_HOST`）。

**JSON（`--json`）**

```json
{
  "generated_at": "ISO-8601",
  "summary": { "ok": 0, "warn": 0, "fail": 0, "skipped": 0 },
  "checks": [
    { "id": "db", "status": "ok", "latency_ms": 12, "detail": "..." }
  ]
}
```

### 3.4 退出码

| 退出码 | 含义 |
|--------|------|
| 0 | 无 `fail`（允许存在 `warn`） |
| 1 | 至少一项 `fail` |
| 2 | 工具自身异常（无法完成检查） |

### 3.5 安全要求

- JSON/文本中**禁止**打印密码、完整 DSN 密钥；`detail` 仅描述性信息。
- HTTP 接口必须鉴权且默认关闭或仅内网。

---

## 4. 可执行 backlog（差异化借鉴清单）

本节将 §1～§3 收敛为**可拆 issue / 排期**的表格：Hermes 对标点、Super-RAG 挂钩、落地动作与验收标准。差异化定位：**企业级文档 RAG + 工作流 + 多租户**；用检索式记忆、doctor、向量/索引管道对齐 Hermes 的「长期记忆 + 运维体验」，不必复刻 IM 网关亦可形成产品区隔。

### 4.1 实施前边界（与 §1.2 一致，可复制到评审）

| 决策 | 选项 | 影响 |
|------|------|------|
| 记忆检索范围 | 仅 `chat` / 允许 `user` 跨会话 | 合规、配额、越权风险 |
| 是否做 IM 网关 | 6 个月内要 / 不要 | Telegram 等整包可 P2 冻结 |
| 用户级 NL 定时任务 | 允许 agent 触发外呼 / 仅运维调度 | 是否与 [Ray 索引调度](../../super_rag/tasks/scheduler.py) 分离 |
| 记忆索引排除 | 按租户/Bot/消息类型过滤 | 审计与删会话时索引失效策略 |

### 4.2 P0 backlog

| ID | Hermes 启发 | 现状 / 挂钩 | 落地动作 | 验收 |
|----|-------------|-------------|----------|------|
| **P0-M1** | 跨会话回忆 | [AgentMemoryManager](../../super_rag/agent/agent_memory_manager.py) 仅滑动窗口；[history.py](../../super_rag/utils/history.py) 持久化消息 | 实现 `MemoryRetriever.retrieve(query, chat_id, user_id, config)`；在 [AgentChatService](../../super_rag/service/agent_chat_service.py) 组装 LLM messages **前**注入检索块（顺序见 §2.4） | 长会话中窗口外事实可答；与最近 N 轮去重；`top_k` / `max_chars` 可配 |
| **P0-M2** | 异步记忆索引 | 文档侧已有向量/队列模式 | 消息落库后异步索引：§2.3 阶段 A（FULLTEXT/关键词）→ 阶段 B（独立 memory collection，`VECTOR_DB_*`） | 新消息 T 秒内可检索；删会话后索引不可命中 |
| **P0-M3** | 可调上下文 | `context_limit=4` 当前写死在 [AgentChatService](../../super_rag/service/agent_chat_service.py) | Bot/全局：`context_limit`、`memory_retrieval_enabled`、`memory_retrieval_top_k`、`memory_scope`（§2.5） | 不调代码即可调窗口与检索强度 |
| **P0-M4** | 默认合规 | — | 默认 `scope=chat`；`scope=user` 显式开关 + 产品同意策略 | 无跨 chat 泄漏；权限/集成测覆盖 |
| **P0-D1** | `hermes doctor` | 多组件私有化排障成本高 | CLI：`python -m super_rag.doctor` 或 pyproject entry；`--json`；检查项 §3.2 | 一条命令可复制报告；退出码 §3.4；详情无密钥 |
| **P0-D2** | 深度健康 | — | 可选 HTTP：`GET .../doctor`，admin/内网，默认关 | 与轻量 liveness 分离 |
| **P0-S1** | 工具审批叙事 | 企业交付刚需 | 命令/工具审批、allowlist 与现有 JWT/租户隔离写入运维文档 + 默认安全配置 | 交付 checklist 可勾选 |

### 4.3 P1 backlog

| ID | Hermes 启发 | 现状 / 挂钩 | 落地动作 | 验收 |
|----|-------------|-------------|----------|------|
| **P1-K1** | agentskills.io | [AgentSkill](../../super_rag/agent_pro/agent_skill.py) | 元数据与目录结构与 agentskills.io 对齐；Hub/Marketplace 字段统一 | 同一 skill 包可多环境导入 |
| **P1-K2** | 使用中改进技能 | — | 可选：成功任务后写回 SKILL 草稿 + 人工审核（优于全自动写生产） | 审计轨迹可查 |
| **P1-N1** | 子代理并行 | NodeFlow | DAG：分支并行、节点超时、用户取消 | 长流程 P95 改善；取消无悬挂副作用 |
| **P1-C1** | 自然语言 cron | — | **独立**队列+权限+审计，不与 Ray 索引调度混用 | 职责清晰；若不做外呼可限「到点生成报告进会话」 |

### 4.4 P2 backlog（有明确场景再立项）

| ID | 说明 |
|----|------|
| **P2-G1** | Telegram/Discord/Slack 等消息网关：配对、推送、安全成本高 |
| **P2-R1** | 轨迹导出与离线评测：对接 OpenTelemetry / 批量 trajectory |

### 4.5 最小两迭代建议

1. **P0-M3 + P0-M1 v0**（检索可先关键词或向量二选一）。  
2. **P0-D1 v0**（至少 `db`、`vector`、`jwt`、`model_configs` 四项即有运维价值）。

---

## 5. 文档维护

- 与 Hermes 能力对标随产品迭代更新「§1.2 决策项」、检查项（§3.2）与 backlog（§4）。
- 检索式记忆落地后，将实际 collection 命名、异步管道与 API 字段补充到本文档或链路到 Nodeflow/Agent 专项设计。
