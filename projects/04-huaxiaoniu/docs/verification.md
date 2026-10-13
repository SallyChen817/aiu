# 验证记录 · 2026-10-13

## 环境

Windows；Python 3.14；Node.js 24.21.0；npm 11.19.0；PySide6 6.10.2；pi `@earendil-works/pi-coding-agent` 1.2.0（package-lock 锁定）。工作目录不是 Git 仓库，在独立 `huaxiaoniu` 子目录开发，未改动已有项目。

## 已完成的验证

最终命令 `.venv/Scripts/python.exe -m pytest -q --tb=short`：**44 passed, 1 skipped（30.59 秒）**。`compileall` 通过，`npm ls --depth=0` 确认 pi 1.2.0。`main.py` 已通过 pythonw 实际启动，桌面进程响应正常；对 42 个生成文件与真实联调会话检查已有认证值，无匹配泄漏。

- Qt 两个真实窗口可创建并渲染；已检查窗口截图，角色为程序绘制的小牛。
- 真实 Node/pi RPC 握手，白名单恰为 `project_list`、`project_read`；异步等待期间 Qt 定时器持续触发。
- JSONL 分片、UTF-8/CRLF/Unicode 行分隔符、非法记录、超大消息。
- Python 工具读取真实文件；越界、绝对路径、UNC、ADS、凭据名称、硬编码凭据、二进制、大文件、硬链接、Windows junction 均有拒绝测试。
- 从真实 pi 消息/工具事件驱动状态；prompt 响应或 agent_end 不标记完成。
- 本地 HTTP 协议测试服务 + 真实 pi + 真实 Python worker：列目录、读取实际 README 内容、展示证据、完成状态、保存会话并重启恢复。
- 项目切换不串会话，新对话不恢复旧会话；设置重新加载。
- 模型等待时以 Qt 鼠标事件拖动桌宠，动画定时器仍工作。
- 手动停止、超时、后台异常退出、认证错误均恢复可操作状态；可重连。
- 反复工具循环在最多 12 次模型请求后停止；单个并行工具批次成功执行不超过 24 次。
- 切换模型期间不接受新任务；失败保留原模型；可清除失效的保存模型。
- 无模型配置、缺少 pi、动态 `!command` 凭据配置都有明确提示。

协议测试服务是自动化测试替身，**没有真实 AI 能力**；测试文件与产品执行路径分离。工具结果来自实际文件，未硬编码工具回复，但仍不等于外部真实模型联调成功。

## 外部真实模型联调

使用现有 Anthropic 环境认证发起过一次真实请求，结果：

```json
{
  "model": "anthropic/claude-opus-4-8",
  "live_model": false,
  "stop_reason": "error",
  "error_category": "authentication",
  "tool_reads": [],
  "session_persisted": true,
  "restored_messages": 3,
  "session_restored": true,
  "result": "incomplete"
}
```

这是服务端认证失败，不能认为“已接通模型”。原始错误、密钥和请求正文未打印。用户选择 Anthropic 并表示稍后本机重新登录；未继续重试外部模型。

**仍待验证：** 重新登录后，真实 Anthropic 流式回复 + 工具读取 + 项目介绍的完整成功流程，以及输出内容准确性。README 中的 `scripts/probe_rpc.py` 可复验，报告须满足 `result: verified`。

## 限制

- 本机没有创建文件符号链接的权限，相应测试跳过；Windows junction 和硬链接边界另有实际通过的测试。
- 桌面截图与 Qt 事件测试通过；未完成安装包签名、多屏混合 DPI、系统注销时进程清理或长时间压力测试。
- 工具边界不是系统沙箱，凭据过滤不是完备的秘密识别器。具体威胁模型见 README。
- pi 会话含聊天和工具读取正文，源码包排除本机运行数据。
