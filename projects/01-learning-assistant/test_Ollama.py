import json
import sys
import urllib.request
import urllib.error

# 模型可能输出 emoji，使用 UTF-8 避免 Windows 默认 GBK 编码报错。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# 本机 Ollama 的聊天接口
url = "http://localhost:11434/api/chat"

# 本地 API 直接连接，避免 urllib 自动使用系统代理而返回 502。
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

data = {
    "model": "qwen3.5:4b",
    "messages": [
        {
            "role": "user",
            "content": "请给我制定一个三天的 Python 入门学习计划。"
        }
    ],
    "stream": False,  # 等回答完成后一次性返回
    "think": False,   # 本次先使用非思考模式
    "options": {
        "num_ctx": 4096
    }
}

request = urllib.request.Request(
    url,
    data=json.dumps(data, ensure_ascii=False).encode("utf-8"),
    headers={"Content-Type": "application/json; charset=utf-8"},
    method="POST"
)

try:
    print("正在等待本地模型回答……")

    with opener.open(request, timeout=300) as response:
        result = json.loads(response.read().decode("utf-8"))

    print("\n模型回答：")
    print(result["message"]["content"])

except urllib.error.HTTPError as error:
    print(f"API 请求失败，状态码：{error.code}")
    print(error.read().decode("utf-8", errors="replace"))

except urllib.error.URLError as error:
    print(f"连接失败：{error.reason}")
    print("请检查 Ollama 是否已启动。")

except TimeoutError:
    print("请求超时，模型可能仍在加载或生成回答。")
