import {test} from 'node:test';
import assert from 'node:assert/strict';
import {existsSync} from 'node:fs';

const moduleURL = new URL('../plugins/cyclops-keeper/assets/presence-state.mjs', import.meta.url);
async function mapper() {
  assert.ok(existsSync(moduleURL), 'The evidence-based presence mapper must exist');
  return (await import(moduleURL)).observe;
}
const record = (state, event, extra = {}) => ({schema:'activity-face/v1', provider:'codex',
  session:'a'.repeat(64), state, event, updated_at:1000, sequence:2, stale:false,
  active_tool_count:0, ...extra});

test('receipt is bounded to an observed recent prompt, never a hidden reading claim', async () => {
  const observe = await mapper();
  assert.equal(observe(record('working','UserPromptSubmit'), {now:1000.5}).phase, 'receiving');
  assert.equal(observe(record('working','UserPromptSubmit'), {now:1002}).phase, 'working');
  assert.equal(observe(record('working','PostToolUse'), {now:1000.5}).phase, 'working');
});
test('a stopped turn resolves inward without a success claim', async () => {
  const observe = await mapper();
  const result = observe(record('stopped','Stop'), {now:1001});
  assert.equal(result.phase, 'resting');
  assert.equal(result.label, 'Turn stopped');
  assert.equal(result.work, 0);
  assert.equal(result.branches, 0);
  assert.doesNotMatch(JSON.stringify(result), /success|error/);
});
test('stale and offline observations suspend work and branches without inventing failure', async () => {
  const observe = await mapper();
  for (const options of [{now:1301}, {now:1001, connected:false}]) {
    const relation=entry('a','execute',2);
    const result = observe(record('tool','PreToolUse',{active_tool_count:4,active_tools:[relation]}), options);
    assert.equal(result.work, 0);
    assert.equal(result.branches, 0);
    assert.equal(result.phase, 'unobserved');
    assert.equal(result.dim, true);
    assert.deepEqual(result.tools,[relation]);
    assert.equal(result.relationsFrozen,true);
    assert.match(result.label, /Last signal old|Signal unavailable/);
  }
});
test('only observed tools extend reach and approval requests suspend them', async () => {
  const observe = await mapper();
  assert.equal(observe(record('tool','PreToolUse',{active_tool_count:2}),{now:1001}).branches, 2);
  const waiting = observe(record('waiting','PermissionRequest',{active_tool_count:2}),{now:1001});
  assert.equal(waiting.phase,'waiting');
  assert.equal(waiting.work,0);
  assert.equal(waiting.branches,0);
  assert.equal(waiting.suspended,2);
  assert.match(waiting.label,/Approval requested/);
});
test('missing and malformed records show ambient presence only', async () => {
  const observe = await mapper();
  for (const value of [null, {}, record('success','Stop'), record('tool','InventedEvent'),
    record('working','UserPromptSubmit',{updated_at:NaN}), record('tool','PreToolUse',{updated_at:1010})]) {
    const result = observe(value,{now:1001});
    assert.equal(result.phase,'unobserved');
    assert.equal(result.work,0);
    assert.equal(result.branches,0);
    assert.equal(result.label,'No signal yet');
  }
  assert.equal(observe(null,{connected:false}).label,'Signal unavailable');
  assert.equal(observe(null,{connected:true}).label,'No signal yet');
});

const key = char => char.repeat(64);
const indexedKey = index => index.toString(16).padStart(2,'0').repeat(32);
const entry = (char, kind='other', sequence=1) => ({key:key(char), kind, sequence});
const agent = (char, sequence=1) => ({key:key(char), sequence});
const transitions = (...events) => events.map(([sequence,event,kind=null,id=null]) =>
  ({sequence,event,at:1000+sequence,kind,key:id?key(id):null}));

test('compaction has distinct fold and return phases in the observed ribbon', async () => {
  const observe = await mapper();
  const fold=observe(record('compacting','PreCompact',{transitions:transitions([1,'PreCompact'])}),{now:1001});
  const returnPose=observe(record('working','PostCompact',{sequence:3,transitions:transitions(
    [1,'PreCompact'],[3,'PostCompact'])}),{now:1003});
  assert.equal(fold.phase,'compacting');
  assert.deepEqual(fold.transitions.map(x=>x.event),['PreCompact']);
  assert.equal(returnPose.phase,'working');
  assert.deepEqual(returnPose.transitions.map(x=>x.event),['PreCompact','PostCompact']);
});

test('subagent satellites follow independently observed active host records', async () => {
  const observe=await mapper();
  const branches=[agent('a',7),agent('b',9)];
  const result=observe(record('branching','SubagentStart',{active_subagents:branches,
    transitions:transitions([7,'SubagentStart',null,'a'],[9,'SubagentStart',null,'b'])}),{now:1001});
  assert.deepEqual(result.subagents,branches);
  assert.equal(result.branches,2);
  assert.equal(result.transitions.length,2);
});

test('each parallel tool keeps its own tether until its matching out-of-order return', async () => {
  const observe=await mapper();
  const a=entry('a','inspect',5), b=entry('b','execute',6);
  const result=observe(record('tool','PostToolUse',{active_tools:[b],active_tool_count:1,
    transitions:transitions([5,'PreToolUse','inspect','a'],[6,'PreToolUse','execute','b'],
      [8,'PostToolUse','inspect','a'])}),{now:1008});
  assert.deepEqual(result.tools,[b]);
  assert.deepEqual(result.transitions.filter(x=>x.event==='PostToolUse').map(x=>x.key),[a.key]);
});

test('dense relations preserve stable unique keys and finite visual kinds', async () => {
  const observe=await mapper();
  const tools=Array.from({length:24},(_,i)=>({key:indexedKey(i+10),kind:['inspect','change','execute','service','other'][i%5],sequence:i+1}));
  const subagents=Array.from({length:8},(_,i)=>({key:indexedKey(i+40),sequence:i+30}));
  const result=observe(record('branching','SubagentStart',{active_tools:tools,active_subagents:subagents,
    active_tool_count:tools.length,transitions:transitions([50,'SubagentStart'])}),{now:1050});
  assert.deepEqual(result.tools,tools);
  assert.deepEqual(result.subagents,subagents);
  assert.equal(new Set(result.tools.map(x=>x.key)).size,tools.length);
  assert.ok(result.tools.every(x=>['inspect','change','execute','service','other'].includes(x.kind)));
});

test('calm and reduced motion preserve identical event geometry', async () => {
  const observe=await mapper();
  const input=record('tool','PreToolUse',{active_tools:[entry('a','change',4)],
    transitions:transitions([4,'PreToolUse','change','a'])});
  const standard=observe(input,{now:1004});
  const calm=observe(input,{now:1004,calm:true});
  const reduced=observe(input,{now:1004,reducedMotion:true});
  assert.deepEqual(calm.tools,standard.tools);
  assert.deepEqual(reduced.tools,standard.tools);
  assert.deepEqual(calm.transitions,standard.transitions);
  assert.deepEqual(reduced.transitions,standard.transitions);
});
