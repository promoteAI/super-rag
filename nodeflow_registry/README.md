# Nodeflow Registry

本目录存放 **Nodeflow 节点注册表** 的 `index.json`，用于列出可安装的 Node Pack（节点包）。

- **index.json**：可安装包列表，每项包含 name、description、repo_id、install 命令、node_types 等。
- 内置节点由 super-rag 自带，无需安装；第三方 pack 通过 `pip install git+https://...` 安装后在应用启动时通过 entry point 自动注册。

详见 [NODE_REGISTRY.md](../docs/design/nodeflow/NODE_REGISTRY.md)。
