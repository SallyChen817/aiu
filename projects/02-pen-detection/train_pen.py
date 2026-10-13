from pathlib import Path
ROOT = Path(__file__).resolve().parent

from ultralytics import YOLO
#构建好cvat照片的dataset之后开始训练模型


def main():
    print("=== Start ===")

    model = YOLO(str(ROOT / 'yolo11n-obb.pt'))

    print("=== Model loaded, starting training ===")

    model.train(
        data=str(ROOT / 'pen_dataset/data.yaml'),
        epochs=50,
        imgsz=640,
        device=0,
        batch=8,

        # Windows先关闭DataLoader多进程
        workers=0,

        project=str(ROOT / 'runs/pen_obb'),
        name="train1"
    )

    print("=== Training finished ===")


if __name__ == "__main__":
    main()
