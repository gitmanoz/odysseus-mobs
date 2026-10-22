"""Stable, non-overlapping reading/composer and contextual lane geometry."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest


def test_columns_fit_wide_resized_and_narrow_workspaces():
    if not shutil.which('node'):
        pytest.skip('Node unavailable')
    module = (Path(__file__).resolve().parents[1] / 'static/js/studioColumns.js').as_uri()
    result = subprocess.run(['node', '--input-type=module', '-e',
        f"import {{studioColumns}} from {json.dumps(module)}; "
        "console.log(JSON.stringify([1920,1636,1280,1040,1039,960,640,320,0].flatMap(width=>[false,true].map(open=>({width,open,...studioColumns(width,open)})))))"],
        check=True, text=True, capture_output=True)
    for geometry in json.loads(result.stdout):
        assert 0 <= geometry['reading'] <= 720
        assert geometry['left'] >= 0
        assert geometry['left'] + geometry['reading'] + geometry['right'] == pytest.approx(geometry['width'])
        if geometry['hasLane'] and geometry['open']:
            assert geometry['panelLeft'] - (geometry['left'] + geometry['reading']) >= 24
            assert 320 <= geometry['panel'] <= 560
            assert geometry['panelLeft'] + geometry['panel'] <= geometry['width'] - 20
            # Equal margins inside the area remaining between navigation and Context.
            assert geometry['left'] == pytest.approx(geometry['panelLeft'] - 24 - geometry['left'] - geometry['reading'] + 20)
        else:
            assert geometry['left'] == pytest.approx(geometry['right'])
    wide = next(g for g in json.loads(result.stdout) if g['width'] == 1636 and not g['open'])
    assert wide['reading'] == 720
    assert wide['left'] == 458
