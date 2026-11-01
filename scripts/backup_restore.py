#!/usr/bin/env python3
"""Automated backup/restore for AZAD Medical Centre Platform."""
from __future__ import annotations

import gzip
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PG_DUMP = r"C:\Program Files\PostgreSQL\18\bin\pg_dump.exe"
PSQL = r"C:\Program Files\PostgreSQL\18\bin\psql.exe"

BACKUP_DIR = Path("backups")
BACKUP_DIR.mkdir(exist_ok=True)

def create_backup():
    """Create a gzipped pg_dump backup."""
    db_url = os.environ.get('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/medical_local')
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"backup_{timestamp}.sql.gz"
    filepath = BACKUP_DIR / filename

    try:
        # Run pg_dump and compress with Python gzip
        dump_proc = subprocess.Popen([PG_DUMP, db_url], stdout=subprocess.PIPE)
        with gzip.open(filepath, 'wb') as gz:
            import shutil
            shutil.copyfileobj(dump_proc.stdout, gz)
        dump_proc.wait()
        if dump_proc.returncode != 0:
            raise RuntimeError(f"pg_dump failed with code {dump_proc.returncode}")

        print(f"Backup created: {filepath} ({filepath.stat().st_size} bytes)")
        return str(filepath)
    except Exception as e:
        print(f"Backup failed: {e}")
        return None

def restore_backup(filepath: str):
    """Restore from a gzipped backup."""
    filepath = Path(filepath)
    if not filepath.exists():
        print(f"Backup file not found: {filepath}")
        return False

    db_url = os.environ.get('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/medical_local')

    try:
        # Decompress and restore
        with gzip.open(filepath, 'rb') as f:
            subprocess.run([PSQL, db_url], stdin=f, check=True)
        print(f"Restored from: {filepath}")
        return True
    except Exception as e:
        print(f"Restore failed: {e}")
        return False

def list_backups():
    """List all available backups."""
    backups = sorted(BACKUP_DIR.glob("backup_*.sql.gz"))
    print(f"Available backups: {len(backups)}")
    for b in backups:
        print(f"  {b.name} ({b.stat().st_size} bytes)")
    return backups

def cleanup_old_backups(keep: int = 7):
    """Remove old backups, keeping only the most recent N."""
    backups = sorted(BACKUP_DIR.glob("backup_*.sql.gz"))
    if len(backups) > keep:
        for b in backups[:-keep]:
            b.unlink()
            print(f"Removed old backup: {b.name}")
    print(f"Kept {min(keep, len(backups))} most recent backups")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Backup/Restore medical database')
    parser.add_argument('action', choices=['create', 'restore', 'list', 'cleanup'], help='Action to perform')
    parser.add_argument('--file', help='Backup file path for restore')
    parser.add_argument('--keep', type=int, default=7, help='Number of backups to keep (cleanup)')
    args = parser.parse_args()

    if args.action == 'create':
        create_backup()
    elif args.action == 'restore':
        if not args.file:
            print("Error: --file required for restore")
            sys.exit(1)
        restore_backup(args.file)
    elif args.action == 'list':
        list_backups()
    elif args.action == 'cleanup':
        cleanup_old_backups(args.keep)
