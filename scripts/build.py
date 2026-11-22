#!/usr/bin/env python3
"""Build deterministic device/source archives using only the Python standard library."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = ['README.md', 'LICENSE', 'NOTICE.md', 'CHANGELOG.md', 'install.py',
              'manifest.json', 'Install.command', 'Update.command', 'Uninstall.command']
SOURCE_FILES = ROOT_FILES + ['AGENTS.md', 'CONTRIBUTING.md', 'pyproject.toml',
                            'requirements-dev.txt', 'Makefile', '.gitignore', '.gitattributes']


def version():
    return tomllib.loads((ROOT / 'pyproject.toml').read_text())['project']['version']


def expected_manifest():
    files = {}
    for path in sorted((ROOT / 'payload').rglob('*')):
        if path.is_symlink():
            raise ValueError('Payload symlinks are not supported: ' + str(path))
        if path.is_file():
            relative = path.relative_to(ROOT / 'payload').as_posix()
            files[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {'version': version(), 'payload': files}


def archive(output, files):
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as result:
        for path in sorted(set(files)):
            relative = path.relative_to(ROOT).as_posix()
            info = zipfile.ZipInfo('kindle-home-dashboard/' + relative, (2020, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = ((0o100755 if path.suffix in {'.sh', '.command'} else 0o100644) << 16)
            result.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    with zipfile.ZipFile(output) as result:
        if result.testzip():
            raise ValueError('ZIP verification failed')
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(output.suffix + '.sha256').write_text(digest + '  ' + output.name + '\n')
    print(output)


def tree_files(directory):
    return [p for p in (ROOT / directory).rglob('*') if p.is_file()
            and '__pycache__' not in p.parts and p.suffix != '.pyc']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Verify the tracked payload manifest')
    parser.add_argument('--source', action='store_true', help='Also create a portable project source archive')
    args = parser.parse_args()
    expected = expected_manifest()
    manifest = ROOT / 'manifest.json'
    if args.check:
        if not manifest.exists() or json.loads(manifest.read_text()) != expected:
            print('Manifest is stale. Run python3 scripts/build.py and commit manifest.json.', file=sys.stderr)
            return 1
        print('Manifest verified:', len(expected['payload']), 'files, version', version())
        return 0
    manifest.write_text(json.dumps(expected, ensure_ascii=False, indent=2) + '\n')
    dist = ROOT / 'dist'
    dist.mkdir(exist_ok=True)
    files = [ROOT / p for p in ROOT_FILES] + tree_files('payload') + tree_files('docs')
    archive(dist / ('kindle-home-dashboard-' + version() + '.zip'), files)
    if args.source:
        source_files = [ROOT / p for p in SOURCE_FILES]
        for directory in ['payload', 'tests', 'scripts', 'docs', '.github']:
            source_files += tree_files(directory)
        archive(dist / ('kindle-home-dashboard-' + version() + '-source.zip'), source_files)
    return 0


if __name__ == '__main__':
    sys.exit(main())
