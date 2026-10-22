"""Long-code disclosure preserves source, controls, streaming and evidence nodes."""
import shutil
import subprocess
from pathlib import Path

import pytest


def test_long_code_disclosure_keeps_original_nodes_and_skips_live_or_evidence_blocks():
    if not shutil.which('node'):
        pytest.skip('Node unavailable')
    module = (Path(__file__).resolve().parents[1] / 'static/js/studioCodeDisclosure.js').as_uri()
    script = r'''
import assert from 'node:assert/strict';
class Element {
  constructor(tag) { this.tagName=tag; this.children=[]; this.className=''; this.dataset={}; this.textContent=''; this.attrs={}; }
  append(...items) { for (const item of items) this.appendChild(item); }
  appendChild(item) { if(item.parentNode) item.parentNode.children.splice(item.parentNode.children.indexOf(item),1); this.children.push(item); item.parentNode=this; }
  before(item) { const parent=this.parentNode; parent.children.splice(parent.children.indexOf(this),0,item); item.parentNode=parent; }
  closest(selector) { let n=this; while(n) { if(selector.split(',').some(s=>n.className.split(' ').includes(s.trim().slice(1)))) return n; n=n.parentNode; } return null; }
  hasAttribute(name) { return name in this.attrs; }
  querySelector(selector) { return this.children.find(c=>c.tagName===selector) || null; }
}
globalThis.document={createElement:tag=>new Element(tag)};
const {foldLongCode}=await import(MODULE);
const history=new Element('div');
const all=[];
history.querySelectorAll=()=>all;
function block(text, flags={}) {
  const message=new Element('div'); message.className=flags.streaming?'msg-ai streaming':'msg-ai'; history.appendChild(message);
  const pre=new Element('pre'), code=new Element('code'), copy=new Element('button');
  code.textContent=text; code.dataset.lang='python'; copy.dataset.code=text;
  if(flags.evidence) pre.attrs['data-copy-content']='';
  pre.append(code,copy); message.appendChild(pre); all.push(pre); return {pre,code,copy,message};
}
const source=Array.from({length:12},(_,i)=>`print("<tag> & ${i}")`).join('\n');
const long=block(source), small=block('print(1)'), live=block(source,{streaming:true}), evidence=block(source,{evidence:true});
foldLongCode(history);
const details=long.pre.parentNode;
assert.equal(details.tagName,'details'); assert.equal(details.open,undefined);
assert.equal(details.children[1],long.pre);
assert.equal(long.pre.querySelector('code'),long.code);
assert.equal(long.pre.querySelector('button'),long.copy);
assert.equal(long.code.textContent,source); assert.equal(long.copy.dataset.code,source);
assert.match(details.children[0].children[0].textContent,/python · 12 linhas/);
assert.equal(small.pre.parentNode,small.message);
assert.equal(live.pre.parentNode,live.message); assert.equal(evidence.pre.parentNode,evidence.message);
details.open=true; foldLongCode(history);
assert.equal(long.pre.parentNode,details); assert.equal(details.open,true);
live.message.className='msg-ai'; foldLongCode(history);
assert.equal(live.pre.parentNode.tagName,'details');
console.log('disclosure: source/control identity, short/live/evidence exclusions, state and completion verified');
'''.replace('MODULE', repr(module))
    result = subprocess.run(['node', '--input-type=module', '-e', script], text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
