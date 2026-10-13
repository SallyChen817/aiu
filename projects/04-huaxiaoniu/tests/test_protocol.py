import json
import pytest
from agent.protocol import JsonlDecoder, ProtocolError


def test_utf8_fragments_crlf_and_unicode_line_separator():
    wire = (json.dumps({'type': 'message_update', 'text': '华小牛\u2028好'}, ensure_ascii=False) + '\r\n').encode()
    decoder = JsonlDecoder()
    events = []
    for byte in wire:
        events.extend(decoder.feed(bytes([byte])))
    assert events == [{'type': 'message_update', 'text': '华小牛\u2028好'}]


@pytest.mark.parametrize('wire', [b'bad\n', b'[]\n', b'{"x":1}\n', b'\xff\n'])
def test_malformed_records_fail_closed(wire):
    with pytest.raises(ProtocolError):
        JsonlDecoder().feed(wire)


def test_oversized_unterminated_or_complete_record_is_rejected():
    for wire in [b'x' * 101, b'x' * 101 + b'\n']:
        with pytest.raises(ProtocolError):
            JsonlDecoder(max_bytes=100).feed(wire)
