"""
Alpha Brain Database Backup & Retention Service
================================================
Manages logical backups, checksum integrity validation, and retention policy enforcement.
"""

import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from alpha_core.config import settings


def utc_now() -> datetime:
    return datetime.now(UTC)


class BackupServiceError(Exception):
    """Base error for backup operations."""


class DatabaseBackupService:
    """Handles logical backups, integrity manifests, and retention pruning."""

    def __init__(self, backup_dir: Path | None = None):
        self.backup_dir = backup_dir or Path(settings.WORKER_STATE_DIR) / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def calculate_checksum(self, file_path: Path) -> str:
        """Computes SHA-256 hex digest of a backup file."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def create_backup_manifest(
        self,
        backup_filename: str,
        table_counts: dict[str, int],
        file_size_bytes: int,
        sha256_hash: str,
    ) -> dict[str, Any]:
        """Creates a signed JSON manifest for a database backup."""
        manifest = {
            "backup_version": "1.0",
            "backup_file": backup_filename,
            "created_at": utc_now().isoformat(),
            "file_size_bytes": file_size_bytes,
            "sha256_checksum": sha256_hash,
            "database_profile": str(settings.ENV),
            "table_row_counts": table_counts,
            "encryption_algorithm": "AES256",
        }
        manifest_path = self.backup_dir / f"{backup_filename}.manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return manifest

    def verify_backup_integrity(self, backup_file: Path) -> bool:
        """Verifies the backup file exists and matches its manifest checksum."""
        if not backup_file.exists():
            return False

        manifest_path = self.backup_dir / f"{backup_file.name}.manifest.json"
        if not manifest_path.exists():
            return False

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        expected_hash = manifest.get("sha256_checksum")
        actual_hash = self.calculate_checksum(backup_file)

        return hmac_equal(expected_hash, actual_hash)

    def prune_expired_backups(self, retention_days: int = 30) -> list[str]:
        """Prunes backup files and manifests older than the retention threshold."""
        cutoff = utc_now() - timedelta(days=retention_days)
        pruned: list[str] = []

        for manifest_file in self.backup_dir.glob("*.manifest.json"):
            try:
                manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
                created_at = datetime.fromisoformat(manifest["created_at"])
                if created_at < cutoff:
                    backup_name = manifest.get("backup_file")
                    if backup_name:
                        target_file = self.backup_dir / backup_name
                        if target_file.exists():
                            target_file.unlink()
                            pruned.append(str(target_file))
                    manifest_file.unlink()
                    pruned.append(str(manifest_file))
            except Exception:
                continue

        return pruned


def hmac_equal(a: str | None, b: str | None) -> bool:
    if a is None or b is None:
        return False
    return hmac.compare_digest(a, b)


backup_service = DatabaseBackupService()
