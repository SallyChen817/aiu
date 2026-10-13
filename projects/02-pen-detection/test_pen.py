from pathlib import Path
ROOT = Path(__file__).resolve().parent

#权重生成完的文件，下面这个还是识别单张照片的
from ultralytics import YOLO

# 对应 train_pen.py 首次训练生成的 best.pt 路径
model = YOLO(
    str(ROOT / 'runs/pen_obb/train1/weights/best.pt')
)

results = model.predict(
    source=str(ROOT / 'pen_dataset/images/val/IMG_20260406_160352_jpg.rf.174340ce00d19ab7c0a086fac7c9c407.jpg'),
    conf=0.25,
    show=True,
    save=True,
    project=str(ROOT / 'runs/pen_predict')
)

print("pen模型检测完成！")
