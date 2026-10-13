# 华小牛 Implementation Plan

> For agentic workers: Use superpowers:executing-plans to implement inline. 用户已要求常规可逆操作直接推进，无需额外设计批准。

**Goal:** Windows 上运行具有真实只读项目理解能力的 pi 桌宠。
**Architecture:** PySide6 → Python Harness/QProcess → pi RPC → 受控 Python 工具。
**Tech Stack:** Python 3.14、PySide6、Node 24、pi 1.2.0。
**Spec:** design.md

## Global Constraints
不执行任意命令或修改项目；不输出认证数据；所有界面等待异步；完成以真实事件及证据为准。

## Review Focus
JSONL 字节分片和 Unicode；异常退出及停止竞态；文件链接/越界/凭据；换项目串会话；认证失败不能显示成功。

## Tasks
- [x] 1. 桌宠外壳：main.py、ui/pet_window.py，绘制、拖动、双击、右键、置顶；Qt 启动检查。
- [x] 2. 通信与安全：tests/test_protocol.py、test_files.py 先失败；agent/protocol.py 提供 JsonlDecoder.feed(bytes)，agent/file_tools.py 提供 list_files(root,path,depth)/read_text(root,path)；extension.ts 注册实际工具。测试通过后真实 RPC 握手。
- [x] 3. 状态控制和持久化：tests/test_state.py、test_storage.py；TaskState.consume(event)、Store.load/save；覆盖完成、错误、停止、预算、重启恢复。
- [x] 4. 异步连接：agent/pi_client.py、controller.py，QProcess 启动/命令关联/恢复/超时；ui/chat_window.py 显示流式文本、证据、会话状态、项目及模型选择。
- [x] 5. 端到端验证：真实 pi、Qt 无阻塞、读取项目、保存恢复。有效模型不可用则明确记录并提供诊断/配置入口，不使用模拟输出冒充。
- [x] 6. README、架构说明、演示与最终验证记录；代码独立复核，修复后重跑相关测试。

最终验证：44 passed, 1 skipped；真实 Anthropic 成功闭环因认证失败待用户登录后复验，详见 verification.md。
