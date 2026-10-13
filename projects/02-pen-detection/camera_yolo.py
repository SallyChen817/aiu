from pathlib import Path
ROOT = Path(__file__).resolve().parent

#这个也是在读取官方训练好的东西，是电脑摄像头识别，这里面我把单张照片改成训练好的那个best的路径了
import cv2
from ultralytics import YOLO

# 加载训练好的 pen OBB 模型

model = YOLO(
    str(ROOT / 'runs/pen_obb/train1/weights/best.pt')
)

# 2. 打开电脑摄像头（连接其他摄像头再说）

cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("摄像头打开失败！")
    exit()

print("摄像头打开成功！按 Q 退出。")


# 3. 实时读取摄像头并识别 pen

while True:

    ret, frame = cap.read()

    if not ret:
        print("无法读取摄像头画面！")
        break

    # 使用训练的模型进行识别
    results = model.predict(
        source=frame,
        conf=0.5,
        device=0,
        verbose=False
    )

    # 将识别到的 OBB 旋转框画在画面上
    annotated_frame = results[0].plot()

    # 显示画面
    cv2.imshow("Pen Detection", annotated_frame)

    # 按 Q 退出
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break


# 4. 释放摄像头

cap.release()
cv2.destroyAllWindows()
