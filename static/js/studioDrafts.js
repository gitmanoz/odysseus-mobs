// Existing owner-scoped preferences only. No task submission or localStorage.
export function normalizeTaskDraft(value) {
  if (!value || typeof value!=='object' || Array.isArray(value) || value.format!==1) return null;
  if (!['bug','change','test'].includes(value.kind) || typeof value.objective!=='string' || typeof value.acceptance!=='string') return null;
  if (value.objective.length>4000 || value.acceptance.length>8000) return null;
  return {format:1,kind:value.kind,objective:value.objective,acceptance:value.acceptance};
}
export async function taskDraftKey(session,workspace) {
  if(typeof session!=='string'||!session||session.length>256||typeof workspace!=='string'||workspace.length>8192)throw Error('scope unavailable');
  const bytes=new TextEncoder().encode(JSON.stringify([session,workspace]));
  const digest=await crypto.subtle.digest('SHA-256',bytes);
  return 'studio-task-draft-'+Array.from(new Uint8Array(digest),x=>x.toString(16).padStart(2,'0')).join('');
}
export async function taskDraftRequest(key,value,signal) {
  if(!/^studio-task-draft-[0-9a-f]{64}$/.test(key))throw Error('invalid draft key');
  const options={credentials:'same-origin',cache:'no-store',signal};
  if(value!==undefined){const safe=value===null?null:normalizeTaskDraft(value);if(value!==null&&!safe)throw Error('invalid draft');Object.assign(options,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({value:safe})});}
  const response=await fetch('/api/prefs/'+key,options);if(!response.ok)throw Error('draft unavailable');
  const data=await response.json();return normalizeTaskDraft(data?.value);
}
