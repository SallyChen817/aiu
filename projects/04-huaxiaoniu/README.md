# 华小牛 — 基于 pi Agent 的 Python AI 桌宠 Harness

华小牛是一个面向 Windows 的 Python AI 桌宠课程项目。它以小牛形象陪伴用户，通过 pi Agent 调用受控工具阅读本地项目，并在聊天工作台展示回复、工具活动和任务状态。

**版本：** 0.1.0 · **平台：** Windows · **当前模型接入方案：** Anthropic

**验证状态（2026-10-13）：** 开发阶段完整测试记录为 44 项通过、1 项因文件符号链接权限跳过。真实 pi RPC 握手、工具调用链和会话恢复已验证；最近一次真实 Anthropic 请求认证失败，**真实模型“阅读项目并介绍”的成功闭环仍待重新登录后验证**。本地协议测试替身的回复不计作真实 AI 联调成功。详见 [验证记录](docs/verification.md)。

## 项目背景

开发过程见 [华小牛开发工作日志](docs/华小牛开发工作日志.md)。

课程要求“参考 pi Agent 的架构，结合专业或兴趣，搭建自己的 Harness”。本项目选择桌宠作为交互入口，使用熟悉的 Python 构建桌面界面和控制层，复用 pi 的模型交互、Agent 循环和会话能力。

这里的 Harness 是围绕 Agent 的应用运行层：它决定用户如何发送任务、Agent 可以访问哪些工具、任务如何停止和恢复，以及如何把真实执行事件呈现给用户。华小牛的核心任务是：**选择一个本地项目，读取真实文件，介绍项目结构和主要功能。**

## 第一版功能

| 模块 | 已实现内容 |
| --- | --- |
| 桌宠 | 程序绘制的小牛、透明背景、拖动、置顶、双击打开聊天、右键退出 |
| 聊天工作台 | 发送消息、流式显示回复、选择项目、选择模型、显示工具活动 |
| 任务管理 | 待机/思考/工作/完成/失败五种状态、停止任务、超时、异常提示 |
| 只读工具 | 列出目录、读取文本、项目路径边界、读取大小限制、常见凭据过滤 |
| 会话管理 | 复用 pi 会话文件、重启恢复、按项目关联会话、新建对话 |
| 宠物档案 | 保存名字、用户称呼、项目目录和置顶设置 |

第一版不自动修改代码、执行任意命令或提交 Git。任务次数和装饰解锁仅预留数据结构。

## 技术栈

| 技术 | 用途 | 版本要求或开发记录 |
| --- | --- | --- |
| Python | 桌面程序、Harness 控制层和文件工具 | 开发验证版本为 3.14 x64 |
| PySide6 / Qt | 双窗口界面、绘制、信号槽、异步进程 | 6.10.2 |
| Node.js | 运行 pi Agent | ≥22.19；开发使用 24.21.0 |
| pi coding agent | 模型请求、工具调度、RPC、认证与会话 | 锁定 1.2.0 |
| JSON / JSONL | 本地设置和 pi 原生会话 | 设置与会话分开保存 |
| pytest / pytest-qt | 核心逻辑和 Qt 集成测试 | 见 requirements-dev.txt |

## 项目目录

```text
huaxiaoniu/
├── main.py                     # 应用入口、双窗口连接和退出流程
├── storage.py                  # 设置、宠物档案、会话关联
├── ui/
│   ├── pet_window.py           # 桌宠绘制、拖动和右键菜单
│   └── chat_window.py          # 聊天、项目选择、模型与工具活动
├── agent/
│   ├── controller.py          # 任务、停止、超时、项目和会话控制
│   ├── pi_client.py           # QProcess 异步 RPC 客户端
│   ├── protocol.py            # JSONL 字节流解析
│   ├── state.py               # 根据真实事件转换任务状态
│   ├── extension.ts           # pi 受控工具扩展
│   └── file_tools.py          # Python 项目文件读取边界
├── assets/                    # 美术资源预留；当前角色由代码绘制
├── tests/                     # 单元测试与本地协议集成测试
├── scripts/probe_rpc.py       # 真实模型和会话恢复验证脚本
├── docs/
│   ├── design.md              # 设计说明
│   ├── implementation-plan.md # 实施计划
│   └── verification.md        # 实际验证结果与未验证项
├── requirements.txt           # Python 运行依赖
├── requirements-dev.txt       # 开发与测试依赖
├── package.json               # pi 依赖声明
├── package-lock.json          # Node 依赖锁定
└── README.md
```

## 安装与运行

开发环境为 Windows、Python 3.14 x64、Node.js ≥22.19，pi 版本由 package-lock.json 锁定。进入本项目目录后执行：

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
npm ci --ignore-scripts
.\.venv\Scripts\python.exe main.py
```

可加 `--project "你的项目目录"`、`--pet-only` 或 `--data-dir "你的数据目录"`；也可用 `XIAOMAO_DATA_DIR` 指定数据位置。数据不写入源码仓库。


## Anthropic 配置

首次登录时，在应用“模型配置说明”中复制适用于当前数据目录的 PowerShell 命令，进入 pi 后输入 `/login` 并选择 Anthropic，完成后回应用重连。

默认认证数据使用 `%LOCALAPPDATA%\XiaomaoHarness\pi`，这是应用独立的 pi 配置目录。pi 的 `/login` 管理认证；华小牛不提供密钥输入框，不把密钥写进源码或 `settings.json`。

也可在本机设置 `ANTHROPIC_API_KEY`，再完全退出并重启华小牛。不要将真实密钥粘贴进聊天、命令行截图、Git 或演示材料。pi 的 `auth.json` 属于凭据存储，不应提交或分享。系统中已有的 `ANTHROPIC_AUTH_TOKEN` 可能过期：它“存在”不等于服务端接受。

重连后可在模型下拉框选择 Anthropic 模型。清单中的模型表示 pi 能找到相关配置；认证、余额、服务权限和网络状态仍需实际请求验证。第一版复用环境变量和本应用 pi 登录，不自动导入全局 pi 扩展/配置；需要自定义代理的用户可编辑应用私有 `pi/models.json`，但不支持其中的 `!command` 动态凭据（见安全说明）。

## 使用与演示

1. 拖动桌宠；双击打开聊天窗口；右键切换置顶或退出。关闭聊天窗口只隐藏工作台。
2. 选择一个不包含敏感信息的课程项目，点击“介绍这个项目”。
3. 观察“思考 → 工作 → 完成/失败”。右侧显示真实 `tool_execution_start/end` 对应的文件路径和读取字节数。
4. 等待模型时拖动宠物、操作窗口，界面保持响应。
5. 点“停止任务”。正常发送 `abort`；2 秒未结束则强制结束 pi，点击重连可继续。
6. 重启华小牛，检查宠物名称、称呼、项目目录和历史会话恢复。
7. 切换项目会换用该项目自己的会话；“新对话”创建新会话，不删除历史 JSONL 文件。

**成功条件：** 点击“介绍这个项目”后，本轮必须有成功的 `project_read` 工具事件、最终模型文本以及 `agent_settled`；否则不展示成功状态。文本内容的正确性仍需人工对照引用文件判断，程序不能自动证明每个结论都正确。

## 架构及课程对应关系

```text
PetWindow / ChatWindow  (PySide6)
          ↓ signals
Controller             (任务、停止、截止时间、项目/会话关联)
          ↓ allowlisted commands
PiClient / QProcess    (异步 stdin/stdout JSONL、命令 ID、握手)
          ↓
pi 1.2.0 RPC           (模型请求、Agent 循环、工具调度、会话)
          ↓
extension.ts           (仅两个工具、调用预算、固定 worker)
          ↓ fixed subprocess, no shell
file_tools.py          (项目路径校验、文件过滤、有界读取)
```

| 功能 | 归属 |
| --- | --- |
| 模型供应商、流式 API、模型工具选择与执行循环 | 复用 pi |
| RPC 协议、事件、认证、JSONL 会话及恢复 | 复用 pi |
| 桌宠绘制/拖动、聊天、工具进度、五种状态 | 本项目 Python/PySide6 |
| QProcess 管理、响应关联、超时和停止、项目会话隔离 | 本项目 Python Harness |
| 工具允许清单、文件边界、凭据过滤、工具/轮数预算 | 本项目受控扩展 + Python 工具 |
| 宠物档案、设置、装饰和任务计数预留结构 | 本项目 JSON 存储 |

`agent_end` 只表示一次底层运行结束；整次任务完成使用 `agent_settled`。`prompt` 的成功响应只代表接收/处理请求。流式内容以 `text_delta` 更新，以 `message_end` 校正最终文本。模型出错、停止、没有文件证据都不会冒充成功。

| 状态 | 触发条件或含义 |
| --- | --- |
| 待机 | 尚未执行任务、连接就绪或用户停止后 |
| 思考 | 请求已发出，或收到 `agent_start` / `turn_start` |
| 工作 | 收到真实 `tool_execution_start` |
| 完成 | 收到 `agent_settled`，有最终文本，且项目介绍任务有本轮成功读取证据 |
| 失败 | 认证/网络/进程错误、超时、超出预算，或项目介绍缺少读取证据 |

界面通过 Qt 信号槽接收这些变化，动画随状态更新。模型等待和工具运行由子进程承担，主界面不使用阻塞式进程等待。

## 工具边界

pi 官方明确说明：**pi 没有内置的文件/进程/网络权限沙箱，cwd 不构成安全隔离。** 默认内置工具含 `read`、`bash`、`edit`、`write`；仅启用内置 `read` 仍不能阻止访问项目外路径。

本项目采取的代码边界：

- 启动时禁用内置工具、MCP、发现的扩展、skills、模板和上下文文件；忽略项目配置，仅加载本项目扩展。
- 工作目录为应用数据目录，选定项目路径单独传给文件 worker。模型只看见 `project_list`、`project_read`。扩展在执行前再次拒绝所有其他工具。
- 不开放 `bash` RPC、斜杠命令、写文件、Git 提交、任意命令或动态工具加载。
- 仅允许项目内相对路径；拒绝 `..`、绝对路径、UNC 输入、NTFS 备用数据流、符号链接、junction、重解析点和硬链接。Windows 打开文件后再检查句柄的最终路径。
- 列目录最多 200 项、最多扫描 2000 项、深度 1–4；读取 UTF-8 文本且单文件最多 64 KiB。拒绝二进制和其他文件类型。
- 排除所有隐藏路径、常见凭据文件名、私钥扩展名、依赖与构建目录；文本中检测到常见密钥格式或硬编码凭据时拒绝整个文件。**这不是能识别一切秘密的分类器，普通文件内未识别的敏感内容仍可能发送给模型。只选择你愿意提供给模型的项目。**
- worker 使用固定 Python 可执行文件、固定脚本和 JSON stdin，`shell=false`，不继承模型凭据；执行超时 8 秒。
- 每任务 120 秒、最多 12 轮、24 次工具尝试，关闭自动重试和自动压缩。限制由计时器、事件控制与扩展执行检查实施。正常停止会取消工具；pi 不响应时由 Python 强制结束 pi。8 秒工具计时器位于 pi 扩展内，不能保证 pi 被强制结束后的残留 worker 也在该期限内退出，因此不宣称具有操作系统级的进程树隔离。

语气、要求引用证据和忽略文件内指令属于提示词要求；路径校验、工具白名单和预算才是程序约束。本方案信任 pi、模型供应商配置、本项目扩展与同一用户的本机环境，**没有操作系统级隔离**。不能防御被替换的依赖、恶意本机进程或所有并发目录修改攻击；对不可信程序执行应另加 Windows 沙箱/容器，第一版不执行这些程序。

## 数据存储

```text
%LOCALAPPDATA%/XiaomaoHarness/
├── settings.json        # 名字、称呼、项目、模型、置顶、每项目会话关联
├── sessions/*.jsonl     # pi 原生会话，含聊天和工具读取内容
└── pi/                 # 独立 pi 认证/模型配置
```

`settings.json` 以同目录临时文件 + 原子替换写入。损坏时显示提示并恢复默认值。会话引用仅接受应用 sessions 目录内的现存 JSONL。`progression.task_count` 和 `unlocked_decorations` 只预留结构，第一版没有解锁逻辑。

项目已更名为“华小牛”；数据目录 `XiaomaoHarness` 和环境变量 `XIAOMAO_DATA_DIR` 保留原标识，以继续使用已有设置、认证和会话。

聊天和工具读取内容会保存在 pi 会话中；它们不是诊断日志，但仍可能包含项目资料，请妥善保管。应用不记录原始 stdout/stderr、环境变量或认证错误详情。

## 测试与验证

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m compileall -q main.py agent ui storage.py scripts
```

测试含真实 pi 进程，不依赖有效外部密钥：协议分片/Unicode、文件边界、Windows junction、状态转换、停止/超时、设置、项目会话隔离、Qt 交互和进程握手。`tests/provider_fixture.py` 是显式的本地 HTTP 协议测试替身，只有测试导入它；它驱动真实 pi 调度真实文件工具，不在应用中作为模型或演示兜底。

重新配置 Anthropic 后，执行真实模型闭环验证（会产生正常模型请求费用）：

```powershell
.\.venv\Scripts\python.exe scripts/probe_rpc.py --data-dir "$env:LOCALAPPDATA\XiaomaoHarness" --project "D:\你的项目"
```

可加 `--model "anthropic/你选择的模型ID"`。只有报告中 `live_model:true`、`session_restored:true` 和 `result:"verified"` 同时成立，才说明真实模型工具读取与重启恢复闭环通过。脚本不打印密钥、原始错误或项目正文。

详细验证结果见 `docs/verification.md`。

## 常见问题

| 现象 | 处理 |
| --- | --- |
| 没有 Node/pi | 安装 Node.js，然后 `npm ci --ignore-scripts` |
| 无可用模型 / 认证失败 | 按“模型配置说明”完成登录，再重连；环境变量变更后重启应用 |
| 启动握手失败 | 使用锁定的 pi 1.2.0；检查应用私有模型配置，恢复后重连 |
| 保存的模型已失效，无法重连 | 打开“模型配置说明”，点击“恢复默认模型并重连” |
| 读文件被拒绝 | 检查路径、大小、UTF-8 编码、凭据/隐藏文件过滤；不要降低边界来读取密钥 |
| 停止后显示断开 | 触发了强制结束；点击重连，已经保存的会话仍保留 |
| 没有读取证据却生成回复 | 项目介绍会被标记为失败，请再次要求读取文件 |

## 核对过的官方文档

于 2026-10-13 阅读官方仓库 RPC 文档，安装后又核对 `pi --help` 与包内文档，版本固定为 1.2.0。

- [官方仓库和权限说明](https://github.com/earendil-works/pi)
- [RPC 模式](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/rpc.md)
- [RPC 命令](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/rpc-commands.md)
- [JSON 事件](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/json.md)
- [CLI 工具与资源选项](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/cli.md)
- [扩展工具接口](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/extensions.md)

## 后续计划

- 增加受控的 Git 改动摘要和提交说明草稿。
- 增加报错解释和项目问答体验。
- 用原创角色素材替换占位绘制，加入装饰解锁。
- 展示供应商返回的 Token 用量和费用估算。

以上均为后续计划，不代表当前版本已经实现。第一阶段优先完成重新登录后的真实模型项目阅读演示。
