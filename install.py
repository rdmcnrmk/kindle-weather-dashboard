#!/usr/bin/env python3
"""Install, update, or roll back the dashboard on the supported Kindle.

This utility does not execute device code or replace the KOReader runtime.
"""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sys

ROOT = Path(__file__).resolve().parent
# Keep the original state paths so installations made before 1.1 still update.
INSTALL_RECORD = 'hava-panosu-installation.json'
ENABLED_FLAG = 'hava-panosu-enabled'
LEGACY_PATHS = (
    'documents/Hava-Panosu.sh',
    'documents/Hava-Panosunu-Durdur.sh',
    'koreader/patches/2-weather-station.lua',
)


def digest(path):
    hasher = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            hasher.update(block)
    return hasher.hexdigest()


def safe_path(base, relative):
    relative = PurePosixPath(relative)
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Invalid package path')
    target = base.joinpath(*relative.parts)
    if not target.resolve().is_relative_to(base.resolve()):
        raise ValueError('A symbolic link points outside the selected drive')
    return target


def verify_volume(target):
    version = target / 'system/version.txt'
    if not version.is_file() or not version.read_text().startswith('Kindle 5.16.2.1.1 '):
        raise ValueError('Expected a Kindle running firmware 5.16.2.1.1')
    marker = target / 'documents/JAILBROKEN.txt'
    if not marker.is_file() or 'You are jailbroken!' not in marker.read_text():
        raise ValueError('The jailbreak success marker was not found; installation stopped')


def install(target, dry_run=False, update=False):
    target = target.resolve()
    verify_volume(target)
    marker = safe_path(target, INSTALL_RECORD)
    flag = safe_path(target, ENABLED_FLAG)
    previous = None
    if marker.exists():
        if not update:
            raise ValueError('The dashboard is already installed; use --update')
        previous = json.loads(marker.read_text())
        for relative, info in previous['files'].items():
            old = safe_path(target, relative)
            if old.exists() and digest(old) != info['installed_sha256']:
                raise ValueError('Preserving a manually edited file: ' + relative)
    elif update:
        raise ValueError('No existing dashboard installation was found')

    manifest = json.loads((ROOT / 'manifest.json').read_text())
    files = manifest['payload']
    if not files:
        raise ValueError('The package manifest is empty')
    for relative, expected in files.items():
        destination = safe_path(target, relative)
        if destination.exists() and not destination.is_file():
            raise ValueError('Expected a file, found a directory: ' + relative)
        if digest(safe_path(ROOT / 'payload', relative)) != expected:
            raise ValueError('Package integrity check failed: ' + relative)
    for relative in LEGACY_PATHS:
        safe_path(target, relative)
    if not (target / 'koreader/koreader.sh').is_file():
        raise ValueError('Install KOReader first, using ;kpm install koreader on the Kindle')
    payload_size = sum(safe_path(ROOT / 'payload', p).stat().st_size for p in files)
    if shutil.disk_usage(target).free < payload_size + 100 * 1024 * 1024:
        raise ValueError('Not enough free space; leave at least 100 MiB plus the app size')
    print('Target:', target)
    print('KOReader: preserving the existing installation')
    print('Package verified. Books and annotations will be preserved.', flush=True)
    if dry_run:
        return {'needs_runtime': False, 'files': len(files)}

    backup = ROOT / 'device-backups' / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    backup.mkdir(parents=True)
    record = {
        'version': manifest['version'], 'target': str(target),
        'backup': str(backup), 'files': {}, 'runtime_added': False,
        'removed_files': [],
    }
    if previous:
        record['previous_record'] = previous
    record_path = backup / 'installation.json'

    def save_record():
        record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2))

    save_record()
    for relative, expected in files.items():
        source = safe_path(ROOT / 'payload', relative)
        destination = safe_path(target, relative)
        existed = destination.is_file()
        if existed:
            saved = safe_path(backup, relative)
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(destination, saved)
        record['files'][relative] = {'existed': existed, 'installed_sha256': expected}
        save_record()
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(destination.name + '.weather-dashboard.tmp')
        shutil.copyfile(source, temporary)
        os.replace(temporary, destination)
        if destination.suffix == '.sh':
            destination.chmod(0o755)
        if digest(destination) != expected:
            raise ValueError('Transfer verification failed: ' + relative)

    # Rename the visible launchers, retaining backed-up aliases for rollback.
    for relative in LEGACY_PATHS:
        old = safe_path(target, relative)
        if old.is_file():
            saved = safe_path(backup, relative)
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(old, saved)
            record['removed_files'].append(relative)
            save_record()
            old.unlink()
    flag.touch()
    save_record()
    marker.write_text(json.dumps(record, ensure_ascii=False, indent=2))
    if hasattr(os, 'sync'):
        os.sync()
    print('\nINSTALLATION COMPLETE. All transferred app files were verified.', flush=True)
    print('Safely eject the Kindle, unplug USB, then open Weather-Dashboard in its library.')
    print('Keep Wi-Fi enabled for the first launch. Use the power button to wake it.')
    print('Backup record:', record_path)
    return record


def rollback(target):
    target = target.resolve()
    verify_volume(target)
    settings = target / 'koreader/settings.reader.lua'
    if settings.exists() and 'fridge_saved_settings' in settings.read_text():
        raise ValueError('First select Stop dashboard and return to reading, then quit KOReader')
    marker = safe_path(target, INSTALL_RECORD)
    record = json.loads(marker.read_text())
    backup = Path(record['backup'])
    removed = record.get('removed_files', [])
    if record.get('removed_conflict'):  # Compatibility with 1.0.x records.
        removed = removed + [record['removed_conflict']]
    for relative, info in record['files'].items():
        destination = safe_path(target, relative)
        if destination.exists() and digest(destination) != info['installed_sha256']:
            raise ValueError('Preserving a file edited after installation: ' + relative)
        if info['existed'] and not safe_path(backup, relative).is_file():
            raise ValueError('Backup file not found: ' + relative)
    for relative in removed:
        if not safe_path(backup, relative).is_file():
            raise ValueError('Backup file not found: ' + relative)
        if safe_path(target, relative).exists():
            raise ValueError('Preserving a newly created file at: ' + relative)
    for relative, info in reversed(list(record['files'].items())):
        destination = safe_path(target, relative)
        if info['existed']:
            shutil.copyfile(safe_path(backup, relative), destination)
        elif destination.exists():
            destination.unlink()
    for relative in removed:
        shutil.copyfile(safe_path(backup, relative), safe_path(target, relative))
    safe_path(target, ENABLED_FLAG).unlink(missing_ok=True)
    if record.get('previous_record'):
        marker.write_text(json.dumps(record['previous_record'], ensure_ascii=False, indent=2))
    else:
        marker.unlink()
    print('Dashboard changes rolled back. KOReader, books, and annotations were preserved.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', type=Path, default=Path('/Volumes/Kindle'))
    parser.add_argument('--dry-run', action='store_true', help='Read-only installation preflight')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--rollback', action='store_true')
    group.add_argument('--update', action='store_true')
    args = parser.parse_args()
    try:
        if args.rollback:
            rollback(args.target)
        else:
            install(args.target, args.dry_run, args.update)
    except Exception as error:
        print('\nSTOPPED:', error, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
