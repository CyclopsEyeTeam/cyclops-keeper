import {test} from 'node:test';
import assert from 'node:assert/strict';

test('sound selects only real fresh semantic events and has no waiting queue', async () => {
  const {createSoundGate,soundFor}=await import('../plugins/cyclops-keeper/assets/keeper-sound.mjs');
  const gate=createSoundGate();
  assert.equal(soundFor({type:'invented'}),null);
  assert.equal(soundFor({type:'tool.return'}),null);
  assert.equal(gate.take({type:'turn.receive',t:100},100),null,'off by default');
  gate.setEnabled(true);
  assert.equal(gate.take({type:'turn.receive',t:100},100).name,'catch');
  assert.equal(gate.take({type:'approval.request',t:100.1},100.1),null);
  assert.equal(gate.take({type:'approval.request',t:100.1},104),null,'no old queued sounds');
  assert.equal(gate.take({type:'turn.stop',t:104},104).name,'settle');
});
test('Keeper sound material is deterministic, mono, finite and bounded with a gentle onset', async () => {
  const {synthesize,CUES}=await import('../plugins/cyclops-keeper/assets/keeper-sound.mjs');
  for(const name of Object.keys(CUES)){
    const a=synthesize(name,48000),b=synthesize(name,48000);
    assert.deepEqual(a,b);assert.ok(a.length<48000*3);
    assert.ok(Math.max(...a.subarray(0,500))<.15);
    let peak=0;for(const v of a){assert.ok(Number.isFinite(v));peak=Math.max(peak,Math.abs(v));}
    assert.ok(peak<=.55&&peak>.01);assert.ok(Math.abs(a.at(-1))<.0001);
  }
});
