#!/usr/bin/env python3
"""Build the com.inq.final_shot World of Tanks package."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Dict, Iterable, Tuple

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / 'build.json'
BUILD_DIR = ROOT / 'build'
PYTHON_SOURCES: Tuple[Path, ...] = (
    ROOT / 'python/gui/mods/mod_inq_final_shot.py',
    ROOT / 'python/gui/mods/mod_zz_inq_final_shot_health.py',
    ROOT / 'python/gui/mods/mod_zzz_inq_final_shot_impacts.py',
    ROOT / 'python/gui/mods/mod_zzzz_inq_final_shot_impact_view.py',
    ROOT / 'python/gui/mods/mod_zzzzz_inq_final_shot_battle_viewer.py',
)
PYTHON_BYTECODE: Tuple[Path, ...] = tuple(path.with_suffix('.pyc') for path in PYTHON_SOURCES)

PACKAGE_FILES: Tuple[Tuple[Path, str], ...] = (
    (PYTHON_BYTECODE[0], 'res/scripts/client/gui/mods/mod_inq_final_shot.pyc'),
    (PYTHON_BYTECODE[1], 'res/scripts/client/gui/mods/mod_zz_inq_final_shot_health.pyc'),
    (PYTHON_BYTECODE[2], 'res/scripts/client/gui/mods/mod_zzz_inq_final_shot_impacts.pyc'),
    (PYTHON_BYTECODE[3], 'res/scripts/client/gui/mods/mod_zzzz_inq_final_shot_impact_view.pyc'),
    (PYTHON_BYTECODE[4], 'res/scripts/client/gui/mods/mod_zzzzz_inq_final_shot_battle_viewer.pyc'),
    (ROOT / 'as3/bin/FinalShotPanelBattle.swf', 'res/gui/flash/FinalShotPanelBattle.swf'),
    (ROOT / 'as3/bin/FinalShotBattleViewer.swf', 'res/gui/flash/FinalShotBattleViewer.swf'),
    (ROOT / 'resources/in/mods/inq.final_shot/en.json', 'res/mods/inq.final_shot/en.json'),
    (ROOT / 'resources/in/mods/inq.final_shot/ru.json', 'res/mods/inq.final_shot/ru.json'),
    (ROOT / 'resources/in/mods/inq.final_shot/uk.json', 'res/mods/inq.final_shot/uk.json'),
)


def load_config() -> Dict[str, object]:
    if not CONFIG_PATH.is_file():
        raise FileNotFoundError('Config not found: build.json')
    with CONFIG_PATH.open('r', encoding='utf-8-sig') as stream:
        data = json.load(stream)
    if not isinstance(data, dict):
        raise ValueError('build.json must contain an object')
    return data


def require_text(container: Dict[str, object], key: str, section: str) -> str:
    value = container.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'Missing {section}.{key} in build.json')
    return value.strip()


def compile_python(python_executable: str) -> None:
    for source, bytecode in zip(PYTHON_SOURCES, PYTHON_BYTECODE):
        if not source.is_file():
            raise FileNotFoundError(source)
        bytecode.unlink(missing_ok=True)
        subprocess.run(
            [python_executable, '-m', 'py_compile', str(source)],
            cwd=str(ROOT),
            check=True,
        )
        if not bytecode.is_file():
            raise RuntimeError(f'Python 2.7 did not create {bytecode.name}')


def create_meta(info: Dict[str, object]) -> bytes:
    root = ET.Element('root')
    for key in ('id', 'version', 'name', 'description'):
        ET.SubElement(root, key).text = require_text(info, key, 'info')
    ET.indent(root, space='    ')
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)


def write_stored(zip_file: zipfile.ZipFile, archive_path: str, data: bytes) -> None:
    entry = zipfile.ZipInfo(archive_path, date_time=(1980, 1, 1, 0, 0, 0))
    entry.compress_type = zipfile.ZIP_STORED
    entry.external_attr = 0o100644 << 16
    zip_file.writestr(entry, data)


def validate_sources(files: Iterable[Tuple[Path, str]]) -> None:
    missing = [str(source.relative_to(ROOT)) for source, _ in files if not source.is_file()]
    if missing:
        raise FileNotFoundError('Missing package files: ' + ', '.join(missing))


def build_package(config: Dict[str, object]) -> Path:
    software = config.get('software')
    info = config.get('info')
    if not isinstance(software, dict) or not isinstance(info, dict):
        raise ValueError('build.json requires software and info objects')

    python_executable = require_text(software, 'python', 'software')
    mod_id = require_text(info, 'id', 'info')
    version = require_text(info, 'version', 'info')
    if mod_id != 'com.inq.final_shot':
        raise ValueError('The package id must be com.inq.final_shot')

    compile_python(python_executable)
    validate_sources(PACKAGE_FILES)

    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    BUILD_DIR.mkdir(parents=True)
    output = BUILD_DIR / f'{mod_id}_{version}.wotmod'

    expected = {'meta.xml'}
    expected.update(archive_path for _, archive_path in PACKAGE_FILES)

    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_STORED) as archive:
        write_stored(archive, 'meta.xml', create_meta(info))
        for source, archive_path in PACKAGE_FILES:
            write_stored(archive, archive_path, source.read_bytes())

    with zipfile.ZipFile(output, 'r') as archive:
        actual = set(archive.namelist())
        if actual != expected:
            extra = sorted(actual - expected)
            missing = sorted(expected - actual)
            raise RuntimeError(f'Invalid package contents; extra={extra}, missing={missing}')
        bad = archive.testzip()
        if bad is not None:
            raise RuntimeError(f'Corrupt package entry: {bad}')

    return output


def main() -> int:
    try:
        output = build_package(load_config())
        print(f'Built: {output.relative_to(ROOT)}')
        return 0
    except Exception as exc:
        print(f'Build failed: {exc}', file=sys.stderr)
        return 1
    finally:
        for bytecode in PYTHON_BYTECODE:
            bytecode.unlink(missing_ok=True)


if __name__ == '__main__':
    raise SystemExit(main())
