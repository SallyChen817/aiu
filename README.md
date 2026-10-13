# AIU 面试项目提交材料

本仓库整理了本地学习任务助手、YOLO 笔目标识别、雷霆空战和华小牛桌宠四个项目，包含源码、工作流、必要数据资源及开发记录。整理日期：2026-10-13。

## 项目导航

| 项目 | 主要内容 | 阅读入口 |
| --- | --- | --- |
| 学习任务助手 | Ollama 本地模型、Dify Chatflow、多清单管理、人工确认、SQLite 和 Web | [项目说明](projects/01-learning-assistant/README.md) |
| YOLO 笔识别 | YOLO11-OBB 训练、旋转框检测、摄像头和 FastAPI 网页 | [项目说明](projects/02-pen-detection/README.md) |
| 雷霆空战 | Canvas 射击游戏、积分存档、Ollama 赛后点评 | [项目说明](projects/03-air-combat/README.md) |
| 华小牛桌宠 | Python/PySide6 界面、pi Agent RPC、受控项目读取和会话管理 | [项目说明](projects/04-huaxiaoniu/README.md) |

## 目录

```text
aiu/
├── README.md
├── .gitignore
├── .gitattributes
├── docs/
│   ├── 项目综述.md
│   ├── 早期工作日志整理.md
│   ├── 提交说明.md
│   ├── 检查记录.md
│   └── 文件清单.tsv
└── projects/
    ├── 01-learning-assistant/
    ├── 02-pen-detection/
    ├── 03-air-combat/
    └── 04-huaxiaoniu/
```

建议先阅读[项目综述](docs/项目综述.md)，再按项目查看实现、工作日志和验证记录。各项目分别管理依赖，没有统一的一键启动入口。

## 当前状态

前三个项目的原开发记录包含本机运行与联调结果；华小牛的本地协议和界面测试已有记录，但真实 Anthropic 请求最近一次认证失败，真实模型读取项目的成功闭环仍待验证。历史测试结果与本次整理检查分别说明，不将历史结果视为新环境已通过验证。

本仓库收录四个 AIU 面试项目的整理材料。首次运行需按各项目说明安装依赖并配置自己的服务及账号。

## 资料与隐私

提交版已排除本机启动入口、依赖缓存、账号配置、个人数据库和会话数据。原始 Word 日志改为脱敏文字摘要；图片附带信息与模型内嵌路径已检查处理。范围见[提交说明](docs/提交说明.md)。

本项目使用了 AI 辅助实现、解释与排错；各项目工作日志说明了个人工作与 AI 辅助部分。第三方框架、模型和参考资料的来源说明保留在对应项目中。

本次文件核对、隐私扫描和局部运行验证见[检查记录](docs/检查记录.md)。
