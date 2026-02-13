# super-rag-nodes-example（模板）

可作为 **Node Pack** 模板：复制到新仓库后改名为你的包，实现自己的节点并发布到 Git，再在 [nodeflow_registry/index.json](../index.json) 中注册。

## 本地安装测试

在 super-rag 项目虚拟环境中：

```bash
cd nodeflow_registry/pack_template
pip install -e .
```

重启 super-rag 服务后，访问 `GET /api/v1/nodeflow/node-types` 应能看到 `echo` 节点。

## 发布到 Git 并注册

1. 复制本目录到新仓库（如 `your-org/super-rag-nodes-xxx`）。
2. 修改 `pyproject.toml` 的 name、description 和 entry point 名称。
3. 实现你的节点并打 tag 发布。
4. 在 super-rag 仓库的 `nodeflow_registry/index.json` 中新增一条记录，并提交 PR。

详见 [NODE_REGISTRY.md](../../../docs/design/nodeflow/NODE_REGISTRY.md)。
