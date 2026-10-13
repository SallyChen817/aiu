# YOLO 笔目标识别

使用 Ultralytics YOLO11-OBB 训练单类别 `pen` 模型，通过 OpenCV 读取摄像头、绘制旋转框，由 FastAPI 向浏览器发送 MJPEG 视频流。网页支持开始和停止识别。

## 文件结构

| 路径 | 用途 |
| --- | --- |
| `main.py` | 网页、开始/停止接口和 CPU 摄像头推理 |
| `camera_yolo.py` | OpenCV 窗口推理，原实现使用 GPU |
| `train_pen.py` | 训练入口：50 轮、640 图像尺寸、batch 8、device 0 |
| `test_pen.py` | 用随附验证图片进行单图推理 |
| `pen_dataset/` | 278 张训练图、68 张验证图及各自标注 |
| `yolo11n-obb.pt` | 训练所用初始权重 |
| `runs/pen_obb/train1/` | 训练参数、逐轮指标、曲线、样本预览和 best.pt |
| `WORK_LOG.md` | 数据补充、训练和 Web 接入的历史记录 |

路径已改为按项目位置解析；数据 YAML 使用相对路径。权重中的机器路径已脱敏，张量存储保留。此前归档的 last.pt、ONNX 文件和旧预测结果没有加入本次提交。

## 环境与运行

使用 Python 3.11 环境。`requirements.txt` 根据原项目记录整理主要依赖版本，未锁定所有间接依赖；本次没有重新安装验证完整环境。

在本项目目录安装依赖并运行：

```powershell
python -m pip install -r requirements.txt
python -m uvicorn main:app --host localhost --port 8000
```

浏览器访问 `http://localhost:8000`。使用的是运行服务的电脑摄像头；先只打开一个识别页面，当前未实现多人摄像头会话管理。

已有 best.pt 可直接用于网页推理。`python test_pen.py` 用于单图检测，`python train_pen.py` 用于重训。训练脚本及 OpenCV 窗口脚本沿用 GPU `device=0`，需要可用 GPU 和匹配的 PyTorch；仅 CPU 环境需自行改为 `device="cpu"`。重复训练会使用新的输出目录，推理不会自动选择新权重。

## 效果与限制

训练数据主要是笔在桌面等背景下的图片，真实摄像头场景可能误检。提高显示阈值不能代替补充困难场景数据。已实现 Python + Web 版，未交付 Rust/ONNX 推理应用。本次整理没有启动摄像头或重新训练。

## 开源来源

- [Ultralytics](https://github.com/ultralytics/ultralytics)：模型、训练与推理。
- [PyTorch](https://github.com/pytorch/pytorch)：模型运行。
- [OpenCV](https://github.com/opencv/opencv)：摄像头与编码。
- [FastAPI](https://github.com/fastapi/fastapi) 和 [Uvicorn](https://github.com/encode/uvicorn)：Web 与视频流服务。

模型架构来自开源项目，本项目完成数据整理、训练、调用及 Web 接入。数据沿用原项目已有素材；本次未补充其外部授权证明。工作过程和 AI 辅助情况见工作日志。

## 数据集核对补充

实盘共有 278 张训练图片、276 个训练标注文件；68 张验证图片均有同名标注。训练目录中的 `pen_20260823T010921153223_left.png` 和 `pen_20260823T010921153223_right.png` 在原材料中没有同名标注。提交版原样保留两张图片，不推断它们是背景样本，也未补造标注；重训前应人工确认。
