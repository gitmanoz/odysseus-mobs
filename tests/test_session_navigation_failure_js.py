"""Navigation failure cannot show another chat or erase a newer navigation."""
import shutil
import subprocess
from pathlib import Path

import pytest


def test_session_error_replaces_only_its_unloaded_history_and_is_literal():
    if not shutil.which('node'):
        pytest.skip('Node unavailable')
    source = (Path(__file__).resolve().parents[1] / 'static/js/sessions.js').read_text(encoding='utf-8')
    at = source.index("    console.error('Error in selectSession:', error);")
    start = source.rfind('  } catch (error) {', 0, at) + len('  } catch (error) {')
    end = source.index('  } finally {', at)
    script = r'''
import assert from 'node:assert/strict';
let navToken=1,_sessionNavToken=2,currentSessionId='new',id='old',historyLoaded=false,notices=0;
const history={innerHTML:'newer chat',style:{},children:[],classList:{remove(){}},appendChild(e){this.children.push(e)}};
const uiModule={el:()=>history,showError(){notices++}};
const document={createElement:()=>({children:[],appendChild(e){this.children.push(e)}})};
const console={error(){}};
function failure(error){ BODY }
failure(new Error('late old error'));assert.equal(history.innerHTML,'newer chat');assert.equal(notices,0);
navToken=2;currentSessionId=id='current';failure(new Error('<script>literal</script>'));
assert.equal(history.innerHTML,'');assert.equal(notices,1);
assert.equal(history.children[0].children[0].textContent,'Não foi possível carregar esta conversa. <script>literal</script>');
assert.equal(history.children[0].innerHTML,undefined);
historyLoaded=true;history.innerHTML='already loaded current chat';failure(new Error('later side panel failure'));
assert.equal(history.innerHTML,'already loaded current chat');assert.equal(notices,2);
'''.replace('BODY', source[start:end])
    result = subprocess.run(['node', '--input-type=module', '-e', script], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
