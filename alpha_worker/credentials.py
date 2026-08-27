"""macOS Keychain backed worker credentials; no secrets logged or persisted in files."""

import subprocess


class KeychainError(RuntimeError):
    """Raised for unavailable or rejected macOS Keychain operations."""


class MacOSKeychain:
    def __init__(self, service: str) -> None:
        self.service = service

    def get(self, account: str) -> str:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", self.service, "-a", account, "-w"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0 or not result.stdout.strip():
            raise KeychainError(f"Missing Keychain credential: {account}")
        return result.stdout.strip()

    def set(self, account: str, secret: str) -> None:
        if not secret:
            raise ValueError("Credential secret cannot be empty")
        result = subprocess.run(
            [
                "security",
                "add-generic-password",
                "-U",
                "-s",
                self.service,
                "-a",
                account,
                "-w",
                secret,
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise KeychainError(f"Could not store Keychain credential: {account}")
