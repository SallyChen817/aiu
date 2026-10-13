from pathlib import Path
ROOT = Path(__file__).resolve().parent

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import cv2
from fastapi.responses import StreamingResponse
from ultralytics import YOLO
from threading import Event

app = FastAPI()
stop_event = Event()
stop_event.set()
model = YOLO(
    str(ROOT / 'runs/pen_obb/train1/weights/best.pt'))
@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <button onclick="startDetection()">开始识别</button>
    <button onclick="stopDetection()">停止识别</button>
<p id="status">尚未开始</p><img id="camera" width="640" alt="点击开始识别后显示画面">

<script>
async function startDetection() {
    const response = await fetch("/start", {method: "POST"});
    const data = await response.json();
    document.getElementById("status").textContent = data.message;
    document.getElementById("camera").src = "/video";
}
async function stopDetection() {
    const response = await fetch("/stop", {method: "POST"});
    const data = await response.json();

    document.getElementById("status").textContent = data.message;
    document.getElementById("camera").removeAttribute("src");
}
</script>
    """

@app.post("/start")
def start():
    global stop_event
    stop_event.set()
    stop_event = Event()
    return {"message": "收到开始识别的请求"}

@app.post("/stop")
def stop():
    stop_event.set()
    return {"message": "已发送停止请求"}

def camera_frames(session_stop):
    cap = cv2.VideoCapture(0)#打开摄像头

    try:
        while cap.isOpened() and not session_stop.is_set():
            success, frame = cap.read()
            if not success:
                break
            results = model.predict(
                      source=frame,
                       conf=0.5,
                       device="cpu",
                       verbose=False)
            
            frame = results[0].plot()

            success, buffer = cv2.imencode(".jpg", frame)
            if not success:
                continue


            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n"
                + buffer.tobytes()
                + b"\r\n"
            )
    finally:
        cap.release()

#画面展示接口

@app.get("/video")
def video():
    return StreamingResponse(
        camera_frames(stop_event),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )
