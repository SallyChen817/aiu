# 任务数据结构与早期查询工具

`schema.sql` 是本提交版提供的完整空数据库结构，包含清单、任务、版本号、操作收据和确认写入触发器。初始化命令见[上级说明](../README.md)。此文件只提供结构，不包含个人任务、聊天或密钥。

`task_api.py`、`openapi.json` 和 `assistant_prompt.txt` 保留早期只读 Agent 查询工具的实现。它支持查询全部任务或按状态筛选；当前多清单 Chatflow 使用 SQLite 插件写入。

```powershell
python task_api.py --host localhost
```

接口为 `http://localhost:8765/tasks` 和 `http://localhost:8765/openapi.json`。默认脚本初次创建旧数据库时会写入历史示例进度；复现多清单版本应先按项目说明执行完整空库结构，避免把示例状态当作真实成果。OpenAPI 中的主机名需要按自己的 Docker 网络调整。
