# 华小牛：第一版设计

目的：Windows 课程演示，可独立启动、真实调用 pi 的只读项目阅读桌宠。名字为“华小牛”，占位形象按需求绘制小牛。

Python/PySide6 负责宠物、聊天、任务控制和存储。QProcess 直接启动本地安装的 Node/pi CLI，严格 JSONL 编解码，所有网络等待都留在子进程。pi 负责模型、Agent 循环、工具调度和 JSONL 会话；一个可信 TypeScript 扩展仅注册两个工具，调用固定 Python worker，不接受 shell 命令。

安全选择：不用仅指定 cwd 的内置 read/bash；禁用内置工具、MCP、发现的扩展、skills、模板和项目上下文。独立配置目录；仅复用可识别的认证和模型配置，不加载用户扩展。文件工具拒绝越界、链接、凭据名称、二进制、超大文本；Windows 校验已打开句柄的最终路径。操作系统进程未沙箱化，pi 和本扩展为可信代码，不宣称能隔离恶意本机进程。

状态：idle/thinking/working/done/error。agent_start/turn_start、tool_execution_*、message_end 和 agent_settled 决定状态；prompt 成功和 agent_end 不代表整次成功。停止回 idle，失败保持短暂提示后可再次提交。项目介绍要求本轮至少一次成功读文件且有最终模型文本，否则不标成功。

限制：每任务 120 秒，最多 12 个模型 turn、24 次工具调用、单文件 64 KiB、目录最多 200 项，工具子进程 8 秒；停止 2 秒未完成则杀死 pi。提示词中的语气与证据要求不是安全边界。

存储：%LOCALAPPDATA%/XiaomaoHarness；settings.json 保存名字、称呼、项目、模型选择及按项目隔离的会话关联，进度结构预留。pi 会话在应用私有 sessions 目录。换项目重启子进程，按项目恢复会话；新对话清除当前关联。API 密钥不写源码、settings 或日志。

验收：真实 pi 握手和会话恢复；有有效认证才做真实模型端到端，不以测试替身冒充成功。核心 tests 覆盖协议、文件和生命周期，Qt 测试覆盖界面在异步等待时继续响应。
