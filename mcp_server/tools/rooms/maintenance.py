"""Operator-only consistent SQLite snapshots; no MCP registration or live credentials.

Run as the service OS user. A restore is a verified snapshot to a NEW path, never
an in-place overwrite of the running database. No scheduling or off-host transfer.
"""
import argparse
import json
import os
from pathlib import Path
import sqlite3
import stat
import time
from .store import RoomError, private_path


def _source(path):
    path = private_path(path)
    info = path.stat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or
            info.st_nlink != 1 or stat.S_IMODE(info.st_mode) & 0o077):
        raise RoomError('unsafe_snapshot_source')
    return path


def _connect_readonly(path):
    return sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=5)


def _verify(connection):
    if connection.execute('PRAGMA user_version').fetchone()[0] != 1:
        raise RoomError('unsupported_database_version')
    if connection.execute('PRAGMA page_size').fetchone()[0] != 4096:
        raise RoomError('unsupported_database_page_size')
    if connection.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
        raise RoomError('snapshot_integrity_failed')
    if connection.execute('PRAGMA foreign_key_check').fetchone() is not None:
        raise RoomError('snapshot_foreign_keys_failed')
    tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not {'actors', 'rooms', 'members', 'messages'} <= tables:
        raise RoomError('snapshot_schema_invalid')
    # Only aggregate counts leave the utility; never print message text or tokens.
    return {table: connection.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0]
            for table in ('actors', 'rooms', 'members', 'messages')}


def verify_database(path):
    path = _source(path)
    connection = _connect_readonly(path)
    try:
        return {'ok': True, 'counts': _verify(connection)}
    finally:
        connection.close()


def backup_database(source, destination, timeout=15):
    source, destination = _source(source), private_path(destination)
    if source == destination:
        raise RoomError('snapshot_destination_exists')
    if type(timeout) not in (int, float) or not 0 < timeout <= 60:
        raise RoomError('invalid_backup_timeout')
    # O_EXCL is also the no-symlink/no-overwrite guard. Output starts private.
    fd = os.open(destination, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600)
    created = os.fstat(fd)
    os.close(fd)
    reader = writer = None
    complete = False
    try:
        reader = _connect_readonly(source)
        _verify(reader)
        writer = sqlite3.connect(str(destination), timeout=5)
        deadline = time.monotonic() + timeout
        def progress(status, remaining, total):
            if time.monotonic() > deadline:
                raise RoomError('snapshot_timeout')
        reader.backup(writer, pages=128, progress=progress, sleep=0.05)
        counts = _verify(writer)
        writer.close(); writer = None
        # fsync the completed file and directory before reporting success.
        with destination.open('rb') as snapshot:
            os.fsync(snapshot.fileno())
        directory = os.open(destination.parent, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        complete = True
        return {'ok': True, 'counts': counts}
    finally:
        if writer is not None:
            writer.close()
        if reader is not None:
            reader.close()
        if not complete:
            # Never remove a concurrent replacement or a pre-existing file.
            try:
                current = destination.lstat()
                if (current.st_dev, current.st_ino) == (created.st_dev, created.st_ino):
                    destination.unlink()
            except FileNotFoundError:
                pass


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    verify = commands.add_parser('verify')
    verify.add_argument('source')
    backup = commands.add_parser('backup')
    backup.add_argument('source'); backup.add_argument('destination')
    args = parser.parse_args(argv)
    try:
        if args.action == 'verify':
            result = verify_database(args.source)
        else:
            result = backup_database(args.source, args.destination)
    except RoomError as exc:
        print(json.dumps({'ok': False, 'error': exc.code}))
        return 1
    except (OSError, sqlite3.Error):
        print(json.dumps({'ok': False, 'error': 'snapshot_storage_error'}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
