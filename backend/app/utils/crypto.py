from __future__ import annotations

import base64
import os
import platform
from pathlib import Path

from cryptography.fernet import Fernet


class SecretCipher:
    def __init__(self, key_path: Path) -> None:
        self.key_path = key_path

    def encrypt(self, plaintext: str) -> str:
        if platform.system() == "Windows":
            try:
                import win32crypt  # type: ignore

                encrypted = win32crypt.CryptProtectData(plaintext.encode("utf-8"), None, None, None, None, 0)
                return base64.b64encode(encrypted).decode("utf-8")
            except Exception:
                pass
        return self._fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        if platform.system() == "Windows":
            try:
                import win32crypt  # type: ignore

                decrypted = win32crypt.CryptUnprotectData(base64.b64decode(ciphertext), None, None, None, 0)[1]
                return decrypted.decode("utf-8")
            except Exception:
                pass
        return self._fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")

    def _fernet(self) -> Fernet:
        key = self._load_or_create_key()
        return Fernet(key)

    def _load_or_create_key(self) -> bytes:
        if self.key_path.exists():
            return self.key_path.read_bytes()
        self.key_path.parent.mkdir(parents=True, exist_ok=True)
        key = Fernet.generate_key()
        self.key_path.write_bytes(key)
        try:
            os.chmod(self.key_path, 0o600)
        except PermissionError:
            pass
        return key


def mask_secret(value: str, keep: int = 4) -> str:
    if len(value) <= keep:
        return "*" * len(value)
    return f"{'*' * max(len(value) - keep, 4)}{value[-keep:]}"
