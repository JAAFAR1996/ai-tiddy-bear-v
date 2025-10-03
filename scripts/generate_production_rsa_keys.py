#!/usr/bin/env python3
"""Generate production RSA key pair and helper assets."""

from __future__ import annotations

import base64
import os
import secrets
import shutil
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Tuple

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def generate_rsa_key_pair(key_size: int = 4096) -> Tuple[str, str]:
    """Generate RSA key pair and return PEM strings."""
    print(f"[*] Generating RSA-{key_size} key pair ...")
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=key_size,
        backend=default_backend(),
    )

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")

    return private_pem, public_pem


def write_text(path: Path, content: str, mode: int | None = None) -> None:
    path.write_text(content)
    if mode is not None:
        try:
            os.chmod(path, mode)
        except PermissionError:
            pass


def backup_existing(path: Path, timestamp: str) -> None:
    if path.exists():
        backup = path.with_name(f"{path.stem}_{timestamp}{path.suffix}")
        path.replace(backup)
        print(f"[i] Existing {path.name} backed up to {backup.name}")


def upsert_env_line(text: str, key: str, value: str) -> str:
    pattern = re.compile(rf'^{{re.escape(key)}}=.*$', re.MULTILINE)
    line = f"{key}={value}"
    if pattern.search(text):
        return pattern.sub(line, text)
    text = text.rstrip() + "\n"
    return text + line + "\n"


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    keys_dir = repo_root / "keys"
    keys_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    private_key, public_key = generate_rsa_key_pair()

    private_path = keys_dir / "jwt_private_key.pem"
    public_path = keys_dir / "jwt_public_key.pem"
    encryption_path = keys_dir / "encryption_key.txt"

    backup_existing(private_path, timestamp)
    backup_existing(public_path, timestamp)
    backup_existing(encryption_path, timestamp)

    write_text(private_path, private_key, 0o600)
    write_text(public_path, public_key, 0o644)

    encryption_key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("utf-8")
    write_text(encryption_path, encryption_key + "\n", 0o600)

    print(f"[+] Private key written to {private_path.relative_to(repo_root)}")
    print(f"[+] Public key written to {public_path.relative_to(repo_root)}")
    print(f"[+] Symmetric encryption key written to {encryption_path.relative_to(repo_root)}")

    env_path = repo_root / ".env"
    env_updates = {
        "JWT_ALGORITHM": "RS256",
        "JWT_PRIVATE_KEY_FILE": "keys/jwt_private_key.pem",
        "JWT_PUBLIC_KEY_FILE": "keys/jwt_public_key.pem",
        "ENCRYPTION_KEY_FILE": "keys/encryption_key.txt",
    }

    if env_path.exists():
        backup_path = env_path.with_name(f".env.backup_{timestamp}")
        shutil.copy2(env_path, backup_path)
        env_content = env_path.read_text(encoding='utf-8')
        for key, value in env_updates.items():
            env_content = upsert_env_line(env_content, key, value)
        env_path.write_text(env_content, encoding='utf-8')
        print(f"[+] Updated {env_path.relative_to(repo_root)} with RSA key references (backup saved to {backup_path.name})")
    else:
        print("[!] .env file not found; please add the following entries manually:")
        for key, value in env_updates.items():
            print(f"    {key}={value}")

    print("\n=== NEXT STEPS ===")
    print("1. Keep files inside keys/ private and never commit them to source control.")
    print("2. Ensure the application container can access the generated files (mount or copy as needed).")
    print("3. Redeploy the stack so the new keys are loaded.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
