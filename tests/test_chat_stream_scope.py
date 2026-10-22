from pathlib import Path


def test_stream_render_helpers_are_visible_to_catch_block():
    source = Path("static/js/chat.js").read_text(encoding="utf-8")
    try_start = source.index("    try {\n      // Re-enable auto-scroll")
    catch_start = source.index("    } catch (err) {", try_start)

    outer_scope = source[:try_start]
    try_body = source[try_start:catch_start]

    assert "let _renderStream = () => {};" in outer_scope
    assert "let _cancelThinkingTimer = () => {};" in outer_scope
    assert "let _removeThinkingSpinner = () => {};" in outer_scope

    assert "_renderStream = () => {" in try_body
    assert "_cancelThinkingTimer = () => {" in try_body
    assert "_removeThinkingSpinner = () => {" in try_body
    assert "function _renderStream()" not in try_body


def test_early_http_error_settles_only_its_holder_and_destroys_spinner():
    import shutil
    import subprocess
    import pytest
    if not shutil.which('node'):
        pytest.skip('Node unavailable')
    source = Path('static/js/chat.js').read_text(encoding='utf-8')
    begin = source.index('    } finally {', source.index('    } catch (err) {'))
    cleanup = source[begin + len('    } finally {'):source.index('      clearResponseTimeout();', begin)]
    script = """
const assert=require('node:assert/strict');
let destroyed=0, settled=0;
let spinner={destroy(){destroyed++;}};
const holder={classList:{remove(name){assert.equal(name,'streaming');settled++;}}};
""" + cleanup + """
assert.equal(destroyed,1);assert.equal(settled,1);assert.equal(spinner,null);
"""
    result = subprocess.run(['node','-e',script],capture_output=True,text=True,timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
