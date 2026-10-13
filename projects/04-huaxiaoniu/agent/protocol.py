import json


class ProtocolError(ValueError):
    pass


class JsonlDecoder:
    """Byte framing deliberately splits only LF, including across UTF-8 chunks."""

    def __init__(self, max_bytes=8 * 1024 * 1024):
        self.buffer = bytearray()
        self.max_bytes = max_bytes

    def feed(self, chunk: bytes) -> list[dict]:
        self.buffer.extend(chunk)
        records = []
        while (end := self.buffer.find(b'\n')) >= 0:
            if end > self.max_bytes:
                raise ProtocolError('RPC 单条消息超过大小限制')
            line = bytes(self.buffer[:end]).removesuffix(b'\r')
            del self.buffer[:end + 1]
            if not line:
                continue
            try:
                record = json.loads(line.decode('utf-8'))
            except (UnicodeError, ValueError):
                raise ProtocolError('pi 返回了无效 JSONL；请检查版本和扩展') from None
            if not isinstance(record, dict) or not isinstance(record.get('type'), str):
                raise ProtocolError('pi 返回了无效的事件结构')
            records.append(record)
        if len(self.buffer) > self.max_bytes:
            raise ProtocolError('RPC 未结束消息超过大小限制')
        return records
