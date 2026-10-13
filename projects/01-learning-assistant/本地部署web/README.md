# 学习助手 Web

`server.py` 提供页面、只读清单接口、后端连接配置、聊天和人工确认表单转发；`dify_client.py` 处理 Dify 鉴权请求与 SSE 事件；`static/` 保存页面、样式和交互脚本。

首次建库、导入流程、绑定插件和运行方法见[项目说明](../README.md)。在本目录可执行 `python -X utf8 server.py`，然后访问 `http://localhost:8766`。标准库实现，无额外 Python 依赖。

服务使用相邻 `task_tool/tasks.db`，将 API 密钥保存到本目录 `config.local.json`，该文件不属于提交材料。聊天会话也可能保存在浏览器 localStorage 中，不包含在源码包中。新环境要自行发布 Dify 应用并连接自己的密钥。

增删改交给 Dify 人工确认流程和 SQLite 事务，网页清单接口只读。开发阶段的测试结果为历史记录；此前归档的测试文件不在本提交目录。
