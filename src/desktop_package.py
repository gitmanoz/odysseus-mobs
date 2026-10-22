"""Build-time source/payload evidence; never installs, activates or executes payloads."""
import argparse
import hashlib
import json
import os
from pathlib import Path

REQUIRED = ('MOBS Studio.exe', '_internal/webview2-runtime/msedgewebview2.exe',
            '_internal/python-toolchain/python.exe', '_internal/static/js/studioShell.js',
            '_internal/static/js/studioEngineering.js', '_internal/static/js/studioSources.js')
MANIFEST = 'build-manifest.json'


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''): h.update(chunk)
    return h.hexdigest()


def reject_link(path):
    if path.is_symlink() or getattr(path.lstat(), 'st_file_attributes', 0) & 0x400:
        raise ValueError('Linked source/package paths are not admissible')


def capture_source(root):
    from src.mobs_institutional_boot import _git
    root = Path(root).resolve(strict=True)
    names = _git(root, 'ls-files', '--cached', '--others', '--exclude-standard', '-z').decode('utf-8').split('\0')
    files = {}
    for name in sorted(set(filter(None, names))):
        parts = Path(name).parts
        if not (Path(name).suffix == '.py' or parts[0] in {'static', 'scripts', 'config', 'desktop', 'mcp_servers'}
                or name.startswith('services/hwfit/data/') or name in {'.env.example', 'requirements.txt', 'requirements-desktop.txt', 'Odysseus.spec', 'build-windows-portable.ps1'}):
            continue
        path = root/name
        for parent in [path, *path.parents]:
            if parent == root: break
            if parent.exists() or parent.is_symlink(): reject_link(parent)
        files[name] = digest(path) if path.is_file() else None  # deleted tracked input is explicit
    return {'head': _git(root, 'rev-parse', 'HEAD').decode().strip(),
            'dirty': bool(_git(root, 'status', '--porcelain', '--untracked-files=normal').strip()),
            'files': files,
            'scope': 'Git-visible Python sources and configured build resources; not a reproducible-build or origin signature',
            'source_digest': hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()}


def package_inventory(root):
    root = Path(root)
    reject_link(root)
    for name in REQUIRED:
        if not (root/name).is_file(): raise ValueError('Required package component missing: '+name)
    files = {}
    for folder, dirs, names in os.walk(root, followlinks=False):
        for name in dirs + names: reject_link(Path(folder)/name)
        for name in names:
            path = Path(folder)/name; relative = path.relative_to(root).as_posix()
            if relative != MANIFEST: files[relative] = {'bytes': path.stat().st_size, 'sha256': digest(path)}
    return files


def write_manifest(package, source, expected_source=None):
    package = Path(package)
    current = capture_source(source)
    if expected_source is not None and current != expected_source:
        raise ValueError('Build inputs changed during packaging; do not activate this package')
    record = {'format_version': 1, 'source': current, 'files': package_inventory(package),
              'scope': 'Inventory and observed source only; not operational certification'}
    (package/MANIFEST).write_text(json.dumps(record, indent=2, sort_keys=True), encoding='utf-8')
    return record


def verify_manifest(package):
    package = Path(package)
    reject_link(package/MANIFEST)
    record = json.loads((package/MANIFEST).read_text(encoding='utf-8'))
    if type(record.get('format_version')) is not int or record['format_version'] != 1 or record.get('files') != package_inventory(package):
        raise ValueError('Package inventory differs from its build manifest')
    return record


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--package', type=Path); p.add_argument('--source', type=Path)
    p.add_argument('--capture-source', type=Path); p.add_argument('--expected-source', type=Path)
    p.add_argument('--verify', action='store_true'); a = p.parse_args()
    if a.capture_source:
        a.capture_source.write_text(json.dumps(capture_source(a.source), sort_keys=True), encoding='utf-8')
    elif a.verify:
        verify_manifest(a.package); print('Package inventory verified; activation not performed.')
    else:
        expected = json.loads(a.expected_source.read_text(encoding='utf-8')) if a.expected_source else None
        write_manifest(a.package, a.source, expected); print('Build manifest written; activation not performed.')


if __name__ == '__main__': main()
