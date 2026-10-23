import json
import os
import shutil
import subprocess
from pathlib import Path
import pytest
from tests.test_studio_development_workbench_js import run_js

ROOT=Path(__file__).resolve().parents[1]


def test_service_worker_prefers_new_shell_and_never_falls_back_to_old_cache_names():
    run_js(r'''
const vm=await import('node:vm'),fs=await import('node:fs');
const handlers={},opens=[];let offline=false,fetches=0;
const old={name:'cached',ok:true,clone(){return this}},fresh={name:'network',ok:true,clone(){return this}};
vm.runInNewContext(fs.readFileSync(SW_PATH,'utf8'),{URL,console,self:{addEventListener:(name,fn)=>handlers[name]=fn},
 caches:{open:async name=>{opens.push(name);return{match:async()=>old,put:async()=>{}}},match:()=>{throw Error('cross-version fallback')}},
 fetch:async()=>{fetches++;if(offline)throw Error('offline');return fresh}});
let promise;const request=(path,mode='cors',method='GET')=>{promise=undefined;handlers.fetch({request:{url:'http://localhost'+path,mode,method},respondWith:p=>promise=p});return promise;};
assert.equal((await request('/','navigate')).name,'network');offline=true;
assert.equal((await request('/','navigate')).name,'cached');assert.equal((await request('/static/app.js')).name,'cached');
const n=fetches;assert.equal(request('/api/prefs'),undefined);assert.equal(request('/static/app.js','cors','POST'),undefined);assert.equal(fetches,n);
assert.equal(new Set(opens).size,1);
'''.replace('SW_PATH',json.dumps(str(ROOT/'static/sw.js'))))


@pytest.mark.parametrize('case,blocked',[('enough',False),('low',True),('unknown',True),('large',True)])
def test_build_space_guard_precedes_cleanup_and_uses_observed_output_size(tmp_path,case,blocked):
    shell=shutil.which('pwsh') or shutil.which('powershell')
    if not shell:pytest.skip('PowerShell unavailable')
    script=r'''
$ErrorActionPreference='Stop'
$ast=[Management.Automation.Language.Parser]::ParseFile($env:SPACE_SOURCE,[ref]$null,[ref]$null)
$f=$ast.Find({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq 'Assert-BuildSpace'},$true)
Invoke-Expression ($f.Extent.Text.Replace('$PSScriptRoot','$env:SPACE_ROOT'))
function Get-PSDrive { param($Name,$ErrorAction) if($env:SPACE_CASE -eq 'unknown'){[pscustomobject]@{Free=$null}}elseif($env:SPACE_CASE -eq 'low'){[pscustomobject]@{Free=1GB}}elseif($env:SPACE_CASE -eq 'large'){[pscustomobject]@{Free=3GB}}else{[pscustomobject]@{Free=8GB}} }
function Test-Path { $true }
function Get-ChildItem { if($env:SPACE_CASE -eq 'large'){[pscustomobject]@{Length=3GB}}else{[pscustomobject]@{Length=1GB}} }
function Remove-Item { throw 'must not delete' }
try{Assert-BuildSpace;@{blocked=$false}|ConvertTo-Json -Compress}catch{@{blocked=$true;reason=$_.Exception.Message}|ConvertTo-Json -Compress}
'''
    result=subprocess.run([shell,'-NoProfile','-NonInteractive','-Command',script],env={**os.environ,'SPACE_SOURCE':str(ROOT/'build-windows-portable.ps1'),'SPACE_ROOT':str(tmp_path),'SPACE_CASE':case},capture_output=True,text=True,timeout=30,check=True)
    record=json.loads(result.stdout.strip().splitlines()[-1]);assert record['blocked'] is blocked
    assert 'must not delete' not in record.get('reason','')


def test_extended_sealed_review_keeps_copy_exact_and_pages_only_the_presentation():
    run_js(r'''
let active=true;const raw='@@ -1 +1 @@\n'+Array(450).fill('+value \t').join('\n');
const file={path:'src/a.py',effect:'write',before:'a \r\n',after:'a\n',diff:raw};
const preview=P.sealedFilePreview(file,()=>active);
assert.match(preview.textContent,/CRLF 1\/0/);assert.match(preview.textContent,/apenas de espaços/);
assert.ok(preview.children[1].textContent.split('\n').length<=200);
await preview.children[5].onclick();assert.equal(copied[0],raw);
preview.querySelectorAll('button').find(b=>b.textContent==='Próxima parte').onclick();assert.match(preview.textContent,/parte 2\/3/);
preview.querySelectorAll('button').find(b=>b.textContent==='Destacar espaços no diff').onclick();assert.match(preview.children[1].textContent,/·⇥/);
const group=P.sealedArtifactPreview([file],'exact-digest',()=>active);group.querySelector('textarea').value='review concern';
await group.querySelectorAll('button').find(b=>b.textContent==='Copiar anotações com referência').onclick();assert.match(copied[1],/exact-digest/);assert.match(copied[1],/src\/a.py/);assert.match(copied[1],/não aprovam/);
active=false;await group.querySelectorAll('button').find(b=>b.textContent==='Copiar anotações com referência').onclick();assert.equal(copied.length,2);
''')
