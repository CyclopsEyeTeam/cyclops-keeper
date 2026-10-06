// Presentation mapping is a strict reduction of host evidence. It never reads
// tool payloads, prompt text, identifiers other than the already-hashed key,
// or any inferred model state.
const EVENTS = new Set(['SessionStart','UserPromptSubmit','PreToolUse','PermissionRequest',
  'PostToolUse','Stop','Interrupt','SessionEnd','PreCompact','PostCompact',
  'SubagentStart','SubagentStop']);
const STATES = new Set(['unknown','idle','working','tool','branching','compacting',
  'waiting','stopped','interrupted','ended']);
const KINDS = new Set(['inspect','change','execute','service','other']);
const labels = {unknown:'No signal yet', idle:'Session ready', working:'Working',
  tool:'Tool activity', branching:'Parallel work', compacting:'Context fold',
  waiting:'Approval requested', stopped:'Turn stopped', interrupted:'Interrupted',
  ended:'Session ended'};
const empty = (label='No signal yet') => ({phase:'unobserved', label, work:0,
  branches:0, suspended:0, receive:0, interrupted:0, dim:true, tools:[],
  subagents:[], transitions:[], relationsFrozen:true});
const validKey = key => typeof key==='string' && /^[0-9a-f]{64}$/.test(key);

function activeEntries(value, tool=false) {
  if (!Array.isArray(value)) return [];
  const entries=[];
  for (const item of value) {
    if (!item || !validKey(item.key) || !Number.isSafeInteger(item.sequence) || item.sequence<0) continue;
    const entry={key:item.key,sequence:item.sequence};
    if (tool) entry.kind=KINDS.has(item.kind)?item.kind:'other';
    entries.push(entry);
  }
  entries.sort((a,b)=>a.sequence-b.sequence || a.key.localeCompare(b.key));
  return entries;
}

function safeTransitions(value) {
  if (!Array.isArray(value)) return [];
  return value.slice(-32).filter(item=>item && Number.isSafeInteger(item.sequence) && item.sequence>0 &&
    EVENTS.has(item.event) && Number.isFinite(item.at) &&
    (item.key==null || validKey(item.key)) && (item.kind==null || KINDS.has(item.kind)))
    .map(({sequence,event,at,kind,key})=>({sequence,event,at,kind:kind??null,key:key??null}))
    .sort((a,b)=>a.sequence-b.sequence);
}

function observeRecord(record, {now=Date.now()/1000, connected=true}={}) {
  if (!record) return connected ? empty() : empty('Signal unavailable');
  if (!record || record.schema!=='activity-face/v1' || !STATES.has(record.state) ||
      !EVENTS.has(record.event) || !Number.isFinite(record.updated_at) ||
      record.updated_at>now+2 || !Number.isSafeInteger(record.sequence)) return empty();
  const tools=activeEntries(record.active_tools,true);
  const subagents=activeEntries(record.active_subagents);
  const ribbon=safeTransitions(record.transitions);
  if (!connected) return {...empty('Signal unavailable'),tools,subagents,transitions:ribbon};
  if (record.stale || now-record.updated_at>300)
    return {...empty('Last signal old'),tools,subagents,transitions:ribbon};
  const result={...empty(labels[record.state]),phase:'resting',dim:record.state==='ended',
    tools,subagents,transitions:ribbon,relationsFrozen:false};
  const toolCount=tools.length || (Number.isInteger(record.active_tool_count) && record.active_tool_count>0
    ? record.active_tool_count : 0);
  const suspendedCount=tools.length+subagents.length || toolCount;
  if (record.state==='working') {
    const receiving=record.event==='UserPromptSubmit' && now-record.updated_at<1.4;
    result.phase=receiving?'receiving':'working'; result.work=receiving?0:1;
    result.receive=receiving?1:0; result.label=receiving?'Request received':'Working';
  } else if (record.state==='tool') {
    result.phase='tool'; result.work=1;
    result.branches=Math.min(3,toolCount);
    result.label=toolCount>1?`Tool activity · ${toolCount}`:'Tool activity';
  } else if (record.state==='branching') {
    result.phase='branching'; result.work=1;
    result.branches=subagents.length;
    result.label=`Parallel work · ${subagents.length} branch${subagents.length===1?'':'es'}`+
      (tools.length?` · ${tools.length} tool${tools.length===1?'':'s'}`:'');
  } else if (record.state==='compacting') {
    result.phase='compacting'; result.work=.55;
  } else if (record.state==='waiting') {
    result.phase='waiting'; result.suspended=suspendedCount;
    if(tools.length)result.label=`Approval requested · ${tools.length} held call${tools.length===1?'':'s'}`;
  } else if (record.state==='interrupted') {
    result.phase='interrupted'; result.interrupted=1; result.suspended=suspendedCount;
    if(tools.length)result.label=`Interrupted · ${tools.length} unresolved call${tools.length===1?'':'s'}`;
  } else if (record.state==='stopped') {
    result.phase='resting'; result.suspended=suspendedCount;
    if(tools.length)result.label=`Turn stopped · ${tools.length} unresolved call${tools.length===1?'':'s'}`;
  } else if (record.state==='ended') {
    result.phase='ended'; result.suspended=suspendedCount;
    if(suspendedCount)result.label=`Session ended · ${suspendedCount} unresolved relation${suspendedCount===1?'':'s'}`;
  }
  return result;
}

export function observe(record, options={}) {
  const result=observeRecord(record,options);
  if(record?.relations_incomplete)result.label+=" · additional relations untracked";
  return result;
}
