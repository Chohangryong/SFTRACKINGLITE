from __future__ import annotations

import base64
import hashlib


def build_msg_digest(msg_data: str, timestamp: str, checkword: str) -> str:
    raw = f"{msg_data}{timestamp}{checkword}".encode("utf-8")
    return base64.b64encode(hashlib.md5(raw).digest()).decode("utf-8")
