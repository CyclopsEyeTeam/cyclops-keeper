const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const target = path.join(__dirname, '../plugins/cyclops-keeper/scripts/painting_renderer.js');
assert.ok(fs.existsSync(target), 'shared painting renderer is not implemented');
const keeper = require(target);
assert.deepEqual(keeper.fitBox('wide',0,0,800,800),{x:0,y:200,w:800,h:400});
const reference = {};
vm.runInNewContext(fs.readFileSync(path.join(__dirname, 'fixtures/painting-reference.js'), 'utf8'), reference);
function context() {
  const ops=[]; let serial=0;
  const g=new Proxy({}, {set(o,k,v){ops.push(['set',k,v]);o[k]=v;return true},get(o,k){
    if(k in o)return o[k];
    if(k.startsWith('create'))return (...args)=>{const id=++serial;ops.push([k,...args,id]);return {addColorStop(...a){ops.push(['stop',id,...a])}}};
    return (...args)=>ops.push([k,...args]);
  }});
  return {g,ops};
}
const marks=[
  {k:'line',pts:[[.1,.2],[.5,.9],[.9,.2]],w:.01},
  {k:'line',pts:[[.1,.2],[.9,.7],[.1,.2]],w:.02},
  {k:'curve',pts:[[.1,.2],[.5,.9],[.9,.2]],w:.015},
  {k:'fill',pts:[[0,0],[1,0],[.5,1]],grad:.125},
  {k:'arc',x:.4,y:.5,r:.2,w:.02,a0:.8,a1:.3},
  {k:'ring',x:.4,y:.5,r:.2,w:.02},
  {k:'dot',x:.4,y:.5,r:.2},
  {k:'glow',x:.4,y:.5,r:.2},
  {k:'spray',x:.4,y:.5,r:.2,n:200,s:.01,seed:918}
].map(m=>({...m,c:[.3,.7,.9],c2:[.9,.3,.4],a:.6}));
(async()=>{
 for(const mirror of [null,'x','y','xy'])for(const [w,h] of [[800,400],[400,800],[400,400]]){
  const p={marks,mirror};const expected=context(),actual=context();
  reference.paintMarks(expected.g,p,w,h);
  for(const _ of keeper.paintMarks(actual.g,p,w,h)){}
  assert.deepEqual(JSON.parse(JSON.stringify(actual.ops)),JSON.parse(JSON.stringify(expected.ops)),'drawing operations differ from Studio');
 }
 const heavy={marks:Array.from({length:96},()=>marks[8]),mirror:'xy'};
 let yields=0, clock=0;
 const result=await keeper.paintAsync(context().g,heavy,800,400,{clock:()=>++clock,yieldTask:async()=>{yields++}});
 assert.ok(yields>100,'dense spray must yield within marks');
 assert.ok(result.maxBurstMs<=20,'drawing burst budget exceeded');
 const cancelled=await keeper.paintAsync(context().g,heavy,800,400,{cancelled:()=>true});
 assert.equal(cancelled.cancelled,true);
 console.log('PASS: 12 Studio operation comparisons; dense spray yields; <=20ms simulated bursts; cancellation');
})().catch(e=>{console.error(e);process.exitCode=1});
