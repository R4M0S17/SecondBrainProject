from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from pathlib import Path

from loguru import logger



class SecretsManager:
    """Encrypted secrets store with keychain-first, encrypted-file fallback.

    Platform keychain is the primary storage:
    - macOS: Keychain via ``keyring`` library
    - Linux: Secret Service via ``keyring``
    - Windows: Credential Manager via ``keyring``

    If keyring is unavailable (Docker, headless, CI), falls back to
    an encrypted file with a machine-derived key + warning.
    """

    def __init__(self, state_dir: Path, env_api_key: str | None = None):
        self.state_dir = state_dir
        self.env_api_key = env_api_key
        self.secrets_path = state_dir / "secrets.enc"
        self._key: bytes | None = None
        self._using_fallback = False
        self._load_or_create_key()

    def _load_or_create_key(self) -> None:
        try:
            import keyring
            stored = keyring.get_password("cerebro", "secrets_key")
            if stored:
                import base64
                self._key = base64.urlsafe_b64decode(stored.encode())
                return
        except ImportError:
            pass

        try:
            import base64
            import keyring
            from cryptography.fernet import Fernet
            self._key = Fernet.generate_key()
            keyring.set_password(
                "cerebro", "secrets_key",
                base64.urlsafe_b64encode(self._key).decode(),
            )
            return
        except (ImportError, Exception):
            pass

        self._using_fallback = True
        logger.warning(
            "No system keychain available. Secrets stored in encrypted file "
            "with machine-derived key. Install keyring for stronger protection."
        )
        fallback_key_path = self.state_dir / ".secrets_master_key"
        if fallback_key_path.exists():
            self._key = fallback_key_path.read_bytes()
        else:
            from cryptography.fernet import Fernet
            self._key = Fernet.generate_key()
            self.state_dir.mkdir(parents=True, exist_ok=True)
            fallback_key_path.write_bytes(self._key)
            fallback_key_path.chmod(0o400)

    def _get_fernet(self):
        from cryptography.fernet import Fernet
        return Fernet(self._key)

    def load(self) -> dict[str, str]:
        if not self.secrets_path.exists():
            return {}
        f = self._get_fernet()
        return json.loads(f.decrypt(self.secrets_path.read_bytes()))

    def save(self, secrets: dict[str, str]) -> None:
        f = self._get_fernet()
        self.secrets_path.write_bytes(f.encrypt(json.dumps(secrets).encode()))
        self.secrets_path.chmod(0o600)

    def get(self, key: str) -> str | None:
        return self.load().get(key)

    def set(self, key: str, value: str) -> None:
        secrets = self.load()
        secrets[key] = value
        self.save(secrets)

    def delete(self, key: str) -> None:
        secrets = self.load()
        secrets.pop(key, None)
        self.save(secrets)

    def is_using_fallback(self) -> bool:
        return self._using_fallback

    def rotate_cerebro_api_key(self) -> str:
        new_key = f"ck_{secrets.token_urlsafe(32)}"
        self.set("CEREBRO_API_KEY", new_key)
        return new_key


@dataclass
class AuthState:
    api_key: str | None = None
    fail_closed: bool = False

