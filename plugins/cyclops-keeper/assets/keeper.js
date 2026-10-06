import {createColourRecipe, createColourSeed, evaluateColourRecipe, toCssRgba} from './colour-engine.js';
import {observe} from './presence-state.mjs';
import {createSoundGate,prepareBuffer} from './keeper-sound.mjs';

const soundGate=createSoundGate();let audioContext=null,audioSource=null,audioEnabled=false,manifested=false,audioGeneration=0;
async function sound(ev){
  if(!audioEnabled||!connected||document.hidden||!visible||audioSource)return;
  const generation=audioGeneration;
  const cue=soundGate.take(ev,Date.now()/1000);if(!cue)return;
  try{const buffer=await prepareBuffer(cue.name,audioContext);
    if(generation!==audioGeneration||audioSource||document.hidden||!visible||!audioEnabled||!connected)return;
    const source=audioContext.createBufferSource(),gain=audioContext.createGain();gain.gain.value=.12;source.buffer=buffer;source.connect(gain).connect(audioContext.destination);
    audioSource=source;source.onended=()=>{if(audioSource===source)audioSource=null;source.disconnect();gain.disconnect()};source.start();
  }catch{/* optional audio is silent when unavailable */}
}
function quiet(){audioGeneration++;if(audioSource){audioSource.stop();audioSource=null}}
const hostSounds={UserPromptSubmit:'turn.receive',PostToolUse:'tool.return',PermissionRequest:'approval.request',PreCompact:'context.fold',PostCompact:'context.unfold',SubagentStart:'branch.start',SubagentStop:'branch.return',Stop:'turn.stop'};
const canvas=document.getElementById('keeper'),ctx=canvas.getContext('2d',{alpha:true});
const status=document.getElementById('status'),scope=document.getElementById('scope');
const params=new URLSearchParams(location.search);
const size=['tiny','expanded'].includes(params.get('size'))?params.get('size'):'panel';
const mono=params.get('mono')==='1',calm=params.get('calm')==='1';
const motion=matchMedia('(prefers-reduced-motion: reduce)');
document.body.dataset.size=size;document.documentElement.dataset.size=size;
document.body.dataset.calm=String(calm);
const recipe=createColourRecipe({seeds:[createColourSeed(.47,.5,.83),createColourSeed(.77,.38,.83),createColourSeed(.11,.4,.89)],
  mixWeights:[.4,.35,.25],mix:{method:'LINEAR_LIGHT'},transforms:{saturation:.68,brightness:1.16}});
let record=null,connected=true,source={selection:'latest',test_feed:false};
let fixtureSeed=null;
try {
  const value=document.querySelector('meta[name="keeper-fixture"]')?.content;
  if(value)fixtureSeed=JSON.parse(atob(value));
} catch {fixtureSeed=null;}
let evidence=observe(null),visible=true,timer,raf,pollTimer,last=0,fetching=false;
let width=0,height=0,dpr=0,sessionKey=null,transitionCursor=null;
const gestureQueue=[];
let gesture=null;
const smooth={work:0,receive:0,interrupted:0,opacity:.5};
const colours=new Map(),tau=Math.PI*2;
const metrics={phase:'unobserved',start:performance.now(),frames:0,cpu:0,samples:[],published:0};

function ink(t,offset=0,alpha=1) {
  const calmFactor=calm?.7:1;
  if(mono)return `rgba(215,224,236,${alpha*calmFactor})`;
  if(!colours.has(offset))colours.set(offset,evaluateColourRecipe(recipe,{transforms:{hueShift:(t/210+offset)%1}}));
  return toCssRgba(colours.get(offset),alpha*calmFactor);
}
function path(points,colour,lineWidth=1,dash=[]) {
  if(points.length<2)return;
  ctx.beginPath();points.forEach((p,i)=>i?ctx.lineTo(...p):ctx.moveTo(...p));
  ctx.strokeStyle=colour;ctx.lineWidth=lineWidth;ctx.setLineDash(dash);ctx.stroke();ctx.setLineDash([]);
}
function curve(a,b,c,d,u) {
  const v=1-u;return [0,1].map(i=>v*v*v*a[i]+3*v*v*u*b[i]+3*v*u*u*c[i]+u*u*u*d[i]);
}
function sampledCurve(a,b,c,d,count=28,until=1,from=0) {
  return Array.from({length:Math.max(2,Math.ceil(count*(until-from))+1)},(_,i)=>curve(a,b,c,d,from+(until-from)*i/Math.max(1,Math.ceil(count*(until-from)))));
}
function pin(x,y,t,offset,alpha=1,r=1.7) {
  const glow=ctx.createRadialGradient(x,y,0,x,y,r*5);
  glow.addColorStop(0,ink(t,offset,alpha*.38));glow.addColorStop(1,ink(t,offset,0));
  ctx.fillStyle=glow;ctx.beginPath();ctx.arc(x,y,r*5,0,tau);ctx.fill();
  ctx.fillStyle=ink(t,offset,alpha);ctx.beginPath();ctx.arc(x,y,r,0,tau);ctx.fill();
}
function ring(x,y,r,t,offset,alpha=1,width=.7) {
  ctx.beginPath();ctx.arc(x,y,r,0,tau);ctx.strokeStyle=ink(t,offset,alpha);ctx.lineWidth=width;ctx.stroke();
}
function poseFor(key) {
  const a=parseInt(key.slice(0,8),16)/0xffffffff;
  const b=parseInt(key.slice(8,16),16)/0xffffffff;
  const angle=-.96+a*1.9;
  const radius=104+b*62;
  const end=[146+Math.cos(angle)*radius,-107+Math.sin(angle)*radius*1.08];
  return {start:[83,-153],control1:[122,-107],control2:[end[0]-20,end[1]-15],end,angle,offset:(parseInt(key.slice(16,20),16)%97)/97};
}
function route(pose,until=1,from=0) {
  return sampledCurve(pose.start,pose.control1,pose.control2,pose.end,30,until,from);
}
function satellitePose(key) {
  const a=parseInt(key.slice(0,8),16)/0xffffffff*tau;
  const b=parseInt(key.slice(8,16),16)/0xffffffff;
  return {start:[70,-155],control1:[104,-184],control2:null,
    end:[180+Math.cos(a)*48,-158+Math.sin(a)*Math.min(92,55+b*40)],a};
}
function satelliteCurve(key) {
  const p=satellitePose(key);p.control2=[p.end[0]-12,p.end[1]-20];return p;
}
function aperture(t,s,fold=0) {
  const active=Math.min(1,s.work*.82+s.receive*.28);
  const waiting=evidence.phase==='waiting';
  const radius=28+active*1.6-fold*5;
  for(let i=0;i<3;i++) {
    const angle=i*tau/3+(motion.matches?0:t*.085*active);
    ctx.beginPath();ctx.ellipse(0,0,radius+i*3,radius+i*2,-.2,angle,angle+1.1);
    ctx.strokeStyle=ink(t,i*.21,(calm?.12:.2)+active*.24);ctx.lineWidth=.55;ctx.stroke();
  }
  if(evidence.phase==='unobserved') {
    ctx.beginPath();ctx.ellipse(0,0,2.1,10,0,0,tau);
    ctx.strokeStyle=ink(0,.2,.55);ctx.lineWidth=.8;ctx.stroke();
  } else {
    const halfHeight=waiting?7:12+active*2.5-fold*2;
    const halfWidth=waiting?1.35:2.2+active*.8;
    const glow=ctx.createRadialGradient(0,0,0,0,0,24);
    glow.addColorStop(0,ink(t,.32,.48));glow.addColorStop(.35,ink(t,.32,.09));glow.addColorStop(1,ink(t,.32,0));
    ctx.fillStyle=glow;ctx.beginPath();ctx.arc(0,0,24,0,tau);ctx.fill();
    ctx.beginPath();ctx.moveTo(0,-halfHeight);ctx.bezierCurveTo(halfWidth,-3,halfWidth,3,0,halfHeight);
    ctx.bezierCurveTo(-halfWidth,3,-halfWidth,-3,0,-halfHeight);
    ctx.fillStyle='rgba(247,241,255,.96)';ctx.fill();
  }
  if(active>.01)for(let i=0;i<3;i++) {
    const a=(motion.matches?0:t*.12)+i*tau/3;
    pin(Math.cos(a)*33,Math.sin(a)*32,t,i*.22,active*.58,.9);
  }
}
function toolTether(item,t,{frozen=false,brokenPose=false}={}) {
  const p=poseFor(item.key),alpha=frozen?.34:evidence.phase==='ended'?.48:evidence.phase==='resting'?.49:calm?.38:.6;
  let dash=[],lineWidth=.72,offset=p.offset;
  if(item.kind==='change'){lineWidth=.82;}
  if(item.kind==='execute')dash=[2,3];
  if(item.kind==='other')dash=[1,3];
  if(evidence.phase==='waiting')dash=[4,2];
  if(frozen||evidence.phase==='ended'||evidence.phase==='resting')dash=[2,3];
  const stopAt=brokenPose?.72:1;
  const points=route(p,stopAt);
  path(points,ink(t,offset,alpha),lineWidth,dash);
  if(item.kind==='change') {
    const second=points.map(([x,y],i)=>[x+Math.sin(i*.14)*1.45,y+Math.cos(i*.14)*1.45]);
    path(second,ink(t,offset+.08,alpha*.58),.42);
  }
  if(brokenPose) {
    const gap=curve(p.start,p.control1,p.control2,p.end,.72), end=curve(p.start,p.control1,p.control2,p.end,1);
    path([[gap[0]-4,gap[1]-3],[gap[0]-1,gap[1]-1]],ink(t,offset,.72),.8);
    path([[gap[0]+2,gap[1]+2],end],ink(t,offset,alpha),.55,dash);
  }
  const [x,y]=p.end;
  if(evidence.phase==='waiting') {
    ring(x,y,5,t,offset,.85,.8);ring(x,y,2.6,t,offset,.6,.65);
    path([[x-1.7,y],[x+1.7,y]],ink(t,offset,.78),.65);
  } else if(frozen||evidence.phase==='ended'||evidence.phase==='resting'||evidence.phase==='interrupted'||brokenPose) {
    ring(x,y,3,t,offset,.75,.7);
  } else if(item.kind==='service') {
    ring(x,y,4,t,offset,.75,.65);pin(x,y,t,offset,.6,1.1);
  } else pin(x,y,t,offset,.84,1.25);
}
function satellite(item,t,{frozen=false}={}) {
  const {start,control1:c1,control2:c2,end}=satelliteCurve(item.key);
  const severed=evidence.phase==='ended';
  path(sampledCurve(start,c1,c2,end,24,severed?.72:1),ink(t,.36,frozen?.27:.43),.62,frozen||severed?[2,3]:[1,3]);
  const [x,y]=end;
  ring(x,y,5.8,t,.36,frozen?.42:.74,.7);ring(x,y,2.2,t,.16,.75,.55);
}
function transitionGesture(t,s,g,progress) {
  if(!g)return 0;
  const k=g.key,hasKey=typeof k==='string'&&/^[0-9a-f]{64}$/.test(k);
  if(g.event==='PreCompact')return Math.sin(Math.PI*progress)*.22;
  if(g.event==='PostCompact') {
    const alpha=(1-progress)*.42;
    for(let i=0;i<5;i++) {
      const a=i*tau/5+progress*.5;
      path([[Math.cos(a)*38,Math.sin(a)*36],[Math.cos(a+.08)*50,Math.sin(a+.08)*48]],ink(t,.28,alpha),.75);
    }
  }
  if(g.event==='UserPromptSubmit') {
    const u=progress;
    const p=curve([-220,-68],[-146,-98],[-92,-38],[-28,0],u);
    path(sampledCurve([-220,-68],[-146,-98],[-92,-38],[-28,0],24,u),ink(t,.08,.55),.8);
    pin(...p,t,.08,.9,1.3);
    if(g.reconnect) {
      const splice=curve([66,61],[75,69],[92,68],[101,78],progress);
      ring(...splice,3.5,t,.35,(1-progress)*.85,.7);
      path([[splice[0]-4,splice[1]],[splice[0]-1,splice[1]+1]],ink(t,.35,(1-progress)*.9),.75);
      path([[splice[0]+2,splice[1]-1],[splice[0]+5,splice[1]]],ink(t,.35,(1-progress)*.7),.6);
    }
    return Math.sin(Math.PI*progress)*.11;
  }
  if(hasKey&&(g.event==='PreToolUse'||g.event==='PostToolUse')) {
    const p=poseFor(k),u=g.event==='PreToolUse'?progress:1-progress;
    const point=curve(p.start,p.control1,p.control2,p.end,u);
    path(route(p,g.event==='PreToolUse'?u:Math.max(.04,1-progress)),ink(t,p.offset,.4*(1-progress*.4)),.8,[2,2]);
    pin(...point,t,p.offset,.95,1.4);
  }
  if(hasKey&&(g.event==='SubagentStart'||g.event==='SubagentStop')) {
    const p=satelliteCurve(k),u=g.event==='SubagentStart'?progress:1-progress;
    const point=curve(p.start,p.control1,p.control2,p.end,u);
    path(sampledCurve(p.start,p.control1,p.control2,p.end,24,g.event==='SubagentStart'?u:Math.max(.04,1-progress)),ink(t,.36,.42),.62,[1,3]);
    pin(...point,t,.36,.92,1.45);
    ring(...p.end,5.8,t,.36,(1-progress)*.65,.7);
  }
  if(g.event==='Interrupt') {
    const p=curve([89,-119],[110,-89],[132,-74],[155,-58],.45+progress*.25);
    ring(...p,4+progress*2,t,.17,.78,.75);
    path([[p[0]-6,p[1]-5],[p[0]-2,p[1]-1]],ink(t,.17,.78),.75);
    path([[p[0]+3,p[1]+3],[p[0]+6,p[1]+6]],ink(t,.17,.58),.6);
  }
  if((g.event==='SubagentStop')&&hasKey) {
    const a=parseInt(k.slice(0,8),16)/0xffffffff*tau;
    ring(180+Math.cos(a)*62,-158+Math.sin(a)*64,7,t,.36,.72,.7);
  }
  if(g.event==='Stop') {
    for(const item of evidence.tools) {
      const p=poseFor(item.key),point=curve(p.start,p.control1,p.control2,p.end,1-progress);
      pin(...point,t,p.offset,(1-progress)*.7,1.1);
    }
    return (1-progress)*.08;
  }
  if(g.event==='SessionStart')return Math.sin(Math.PI*progress)*.09;
  return 0;
}
function drawArt(t,s,g,progress,gestureFold) {
  const phaseScale=evidence.phase==='waiting'?.985:evidence.phase==='ended'?.96:1;
  const breath=motion.matches?0:Math.sin(t*.22)*(calm?.003:.006);
  const catchPose=g?.event==='UserPromptSubmit'?Math.sin(Math.PI*progress)*.013:0;
  const scaleX=phaseScale+breath+catchPose-gestureFold*.18;
  const scaleY=phaseScale+breath+catchPose*.25-gestureFold*.08;
  ctx.scale(scaleX,scaleY);
  // Keeper's own woven signature, shared with the terminal's subcell drawing.
  // The membrane has an open upper-right crown and loose downward filaments.
  const crown=[112,-160];
  function filament(points,offset,alpha,width=.7,dash=[],until=1) {
    path(sampledCurve(...points,42,until),ink(t,offset,alpha),width,dash);
  }
  const wash=ctx.createRadialGradient(12,-42,8,12,-42,158);
  wash.addColorStop(0,ink(t,.08,.055));wash.addColorStop(1,ink(t,.08,0));
  ctx.fillStyle=wash;ctx.beginPath();ctx.arc(12,-42,158,0,tau);ctx.fill();
  for(let i=0;i<9;i++) {
    const u=i/8;
    filament([crown,[-18+u*72,-125-u*12],[-141+u*36,-36+u*23],[-39+u*63,64]],
      i%3?.02:.19,i===0||i===8?.8:.3,i===0||i===8?1.15:.55);
    filament([crown,[145-u*24,-82+u*24],[74-u*18,50-u*12],[-24+u*39,64]],
      i%3?.19:.02,i===0||i===8?.72:.28,i===0||i===8?1.1:.55);
  }
  for(let i=0;i<5;i++) {
    const y=-90+i*25;
    filament([[-55-i*6,y],[0,y-30],[58,y+5],[93-i*11,y-24]],.26,.16,.45,[1,3]);
  }
  path([[91,-150],[135,-181],[159,-143]],ink(t,.2,.84),1.05);
  path([[111,-158],[118,-128]],ink(t,.32,.6),.7);
  pin(112,-160,t,.32,.87,1.25);
  const tails=[[[ -40,58],[-94,100],[-106,155],[-147,190]],
    [[-22,64],[-57,111],[-38,171],[-73,216]],
    [[-8,61],[13,106],[-21,156],[-22,208]],
    [[12,61],[47,106],[27,155],[54,185]]];
  tails.forEach((points,i)=>filament(points,i%2?.19:.02,.58-i*.08,i<2?.78:.5,i<2?[]:[1,3],
    evidence.phase==='interrupted'&&i===3?.43:1));
  ring(0,0,34,t,.19,.79,1.05);
  ctx.beginPath();ctx.arc(0,0,27,-2.7,1.7);ctx.strokeStyle=ink(t,.32,.72);ctx.lineWidth=.85;ctx.stroke();
  aperture(t,s,gestureFold);
}
function drawRelations(t,s,g,progress) {
  const frozen=evidence.relationsFrozen;
  const ended=evidence.phase==='ended';
  const ordered=evidence.tools;
  ordered.forEach(item=>toolTether(item,t,{frozen,brokenPose:ended}));
  evidence.subagents.forEach(item=>satellite(item,t,{frozen}));
  if(g?.event==='PermissionRequest') {
    const alpha=.35+Math.sin(progress*Math.PI*2)*.16;
    for(let i=0;i<3;i++)path([[83,-153+i*4],[104,-149+i*4],[125,-145+i*4]],ink(t,.2,alpha),.7,[3,2]);
  }
  if(g?.event==='PreToolUse'&&g.key) {
    const p=poseFor(g.key),q=curve(p.start,p.control1,p.control2,p.end,progress);
    pin(...q,t,p.offset,.96,1.6);
  }
  if(g?.event==='UserPromptSubmit') {
    const alpha=Math.sin(Math.PI*progress)*.45;
    ring(-5,0,15+progress*12,t,.11,alpha,.8);
  }
  if(s.receive>.01) {
    for(let i=0;i<3;i++) {
      const from=[-202,-40+i*18],end=[-31,-7+i*6];
      const u=motion.matches?.82:Math.min(.92,.48+(t*(calm?.18:.36)+i*.17)% .44);
      const points=sampledCurve(from,[-151,-70+i*15],[-71,-47+i*11],end,22,u);
      path(points,ink(t,.08+i*.1,s.receive*(calm?.33:.43)),.6);
      pin(...points.at(-1),t,.08+i*.1,s.receive*.58,.9);
    }
  }
  if(evidence.phase==='interrupted') {
    // The interruption is turn-level; it does not identify which outstanding
    // invocation caused it. Break a body filament, not a guessed tool tether.
    const tail=[[12,61],[47,106],[27,155],[54,185]];
    path(sampledCurve(...tail,24,1,.62),ink(t,.19,.3),.5,[1,3]);
    ring(...curve(...tail,.52),3.2,t,.19,.82,.7);
  }
  if(g?.event==='PostCompact') {
    for(let i=0;i<4;i++) {
      const a=tau*i/4+progress*.7;
      pin(Math.cos(a)*43,Math.sin(a)*41,t,.34,(1-progress)*.65,.9);
    }
  }
  if(frozen) {
    ring(0,0,37,t,.2,.33,.6);
    path([[-14,36],[-7,41],[0,36],[7,41],[14,36]],ink(t,.22,.3),.5,[1,4]);
  }
}
function drawMini(t,s,local=false) {
  if(!local)ctx.translate(width/2,height/2);
  // Same small-scale signature: open membrane, upper-right crown, leftward
  // trailing thread, single vertical aperture, and satellites on the right.
  ctx.beginPath();ctx.moveTo(9,-13);ctx.bezierCurveTo(13,-5,8,6,-2,7);
  ctx.bezierCurveTo(-12,7,-9,-5,9,-13);ctx.closePath();
  ctx.fillStyle=ink(t,.15,.09);ctx.fill();ctx.strokeStyle=ink(t,.15,.9);ctx.lineWidth=.9;ctx.stroke();
  path([[9,-13],[5,-6],[-5,2],[-2,8],[-7,13]],ink(t,.35,.82),.85);
  path([[8,-12],[12,-15],[14,-12]],ink(t,.2,.85),.65);
  ring(0,0,4.4,t,.23,.95,.8);
  if(evidence.phase==='unobserved') {
    ctx.beginPath();ctx.ellipse(0,0,1.2,2.5,0,0,tau);ctx.strokeStyle=ink(t,.2,.55);ctx.lineWidth=.6;ctx.stroke();
  } else path([[0,-2.5],[0,2.5]],ink(t,.4,.98),1.25);
  const tools=evidence.tools,subagents=evidence.subagents;
  for(let i=0;i<tools.length;i++) {
    const item=tools[i],p=poseFor(item.key),end=[6+Math.cos(p.angle)*8,-7+Math.sin(p.angle)*7];
    path([[6,-8],end],ink(t,p.offset,.78),.52,item.kind==='execute'?[1,2]:[]);
    ring(...end,1.35,t,p.offset,.9,.45);
  }
  for(let i=0;i<subagents.length;i++) {
    const a=parseInt(subagents[i].key.slice(0,4),16)/65535*1.2-.6;
    path([[7,-10],[12+Math.cos(a)*4,-13+Math.sin(a)*5]],ink(t,.36,.75),.45,[1,2]);
    ring(12+Math.cos(a)*4,-13+Math.sin(a)*5,1.55,t,.36,.88,.45);
  }
  if(s.receive>.05)pin(-10,-3,t,.08,s.receive,1);
  if(s.interrupted>.05)path([[5,7],[7,9],[8,11]],ink(t,.3,.8),.75);
}
function percentile(values,q) {return values[Math.min(values.length-1,Math.floor(values.length*q))]||0;}
function publishMetrics(now,cost) {
  metrics.frames++;metrics.cpu+=cost;metrics.samples.push(cost);if(metrics.samples.length>600)metrics.samples.shift();
  if(now-metrics.published<1000)return;
  const ordered=[...metrics.samples].sort((a,b)=>a-b);
  canvas.dataset.metrics=JSON.stringify({phase:metrics.phase,frames:metrics.frames,cpu_ms:metrics.cpu,
    wall_ms:now-metrics.start,median_ms:percentile(ordered,.5),p95_ms:percentile(ordered,.95),
    samples:ordered.length,gesture_queue:gestureQueue.length,tool_relations:evidence.tools.length,
    subagent_relations:evidence.subagents.length,viewport:{width,height,dpr},
    reduced_motion:motion.matches,calm,renderer:'Canvas 2D / Keeper'});
  if(source.test_feed) {
    const base=status.title.split(' · Render work:')[0];
    status.title=`${base} · Render work: median ${percentile(ordered,.5).toFixed(3)} ms, `+
      `p95 ${percentile(ordered,.95).toFixed(3)} ms, ${ordered.length} samples; `+
      `transition queue ${gestureQueue.length}/32, active tethers ${evidence.tools.length}, `+
      `satellites ${evidence.subagents.length}.`;
    status.setAttribute('aria-description',status.title);
  }
  metrics.published=now;
}
function takeGesture(now) {
  if(gesture&&now-gesture.started<gesture.duration)return gesture;
  gesture=null;
  if(gestureQueue.length) {
    const item=gestureQueue.shift();
    if(hostSounds[item.event])void sound({type:hostSounds[item.event],t:item.at,key:item.key});
    gesture={...item,started:now,duration:(item.event==='PreCompact'||item.event==='PostCompact'?900:540)*(calm?1.25:1)};
  }
  return gesture;
}
function draw(now) {
  if(!ctx||document.hidden||!visible)return;
  const begin=performance.now(),dt=Math.min(.25,last?(now-last)/1000:.08);last=now;
  if((motion.matches||evidence.relationsFrozen)&&gestureQueue.length)gestureQueue.length=0;
  if(evidence.relationsFrozen)gesture=null;
  const target={work:evidence.work,receive:evidence.receive,interrupted:evidence.interrupted,opacity:evidence.dim?.43:1};
  const response=calm?1.8:4;
  for(const key of Object.keys(smooth))smooth[key]=motion.matches?target[key]:smooth[key]+(target[key]-smooth[key])*(1-Math.exp(-dt*response));
  if(evidence.phase==='unobserved'&&evidence.relationsFrozen)Object.assign(smooth,{work:0,receive:0,interrupted:0});
  const box=canvas.getBoundingClientRect(),ratio=Math.min(2,devicePixelRatio);
  if(width!==box.width||height!==box.height||dpr!==ratio) {
    width=box.width;height=box.height;dpr=ratio;canvas.width=Math.round(width*dpr);canvas.height=Math.round(height*dpr);
  }
  ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,width,height);ctx.save();
  ctx.lineCap='round';ctx.lineJoin='round';ctx.globalAlpha=smooth.opacity;
  const t=motion.matches||evidence.relationsFrozen?0:now/1000*(calm?.42:1);colours.clear();
  const g=motion.matches||evidence.relationsFrozen?null:takeGesture(now);
  const progress=g?Math.min(1,(now-g.started)/g.duration):1;
  // Compute deformation without drawing. Event gestures are painted only
  // after entering the same body coordinate space as their keyed tethers.
  const pulse=Math.sin(Math.PI*progress);
  const gestureFold=g?.event==='PreCompact'?pulse*.22:g?.event==='UserPromptSubmit'?pulse*.11:
    g?.event==='Stop'?(1-progress)*.08:g?.event==='SessionStart'?pulse*.09:0;
  const fold=evidence.phase==='compacting'?.2:gestureFold;
  if(size==='tiny') {
    drawMini(t,smooth);
  } else {
    const compact=size==='expanded';
    const scale=Math.min(width/(compact?435:580),height/570)*.92;
    const drift=motion.matches||evidence.relationsFrozen?0:Math.sin(t*.13)*2.2*(calm?.42:1);
    ctx.translate(width*.5,height*.37+drift*scale);
    ctx.scale(scale,scale);
    drawArt(t,smooth,g,progress,fold);
    transitionGesture(t,smooth,g,progress);
    drawRelations(t,smooth,g,progress);
  }
  ctx.restore();publishMetrics(now,performance.now()-begin);
}
function fps() {
  if(motion.matches||evidence.relationsFrozen)return 0;
  if(evidence.phase==='tool'||evidence.phase==='branching'||evidence.phase==='receiving')return calm?12:24;
  if(evidence.phase==='waiting')return calm?4:7;
  if(gesture||gestureQueue.length)return calm?10:18;
  return calm?4:8;
}
function schedule() {const rate=fps();if(document.hidden||!visible||!ctx||!rate)return;timer=setTimeout(()=>raf=requestAnimationFrame(tick),1000/rate);}
function tick(now){draw(now);schedule();}
function restart(){clearTimeout(timer);cancelAnimationFrame(raf);last=0;draw(performance.now());schedule();}
function ingest(nextRecord,nextEvidence) {
  const nextSession=nextRecord?.session||null;
  const ribbon=nextEvidence.transitions;
  const latest=ribbon.at(-1)?.sequence??nextRecord?.sequence??0;
  if(nextSession!==sessionKey) {
    sessionKey=nextSession;gestureQueue.length=0;gesture=null;
    const replayFixture=source.test_feed&&!nextRecord?.stale&&nextEvidence.phase!=='unobserved';
    transitionCursor=replayFixture&&ribbon.length?ribbon[0].sequence-1:latest;
    if(replayFixture)for(const item of ribbon)gestureQueue.push(item);
    transitionCursor=latest;
  } else if(transitionCursor===null) transitionCursor=latest;
  else {
    for(const item of ribbon)if(item.sequence>transitionCursor) {
      gestureQueue.push({...item,reconnect:evidence.phase==='interrupted'&&item.event==='UserPromptSubmit'});
    }
    if(latest>transitionCursor)transitionCursor=latest;
    if(gestureQueue.length>32)gestureQueue.splice(0,gestureQueue.length-32);
  }
}
function adopt() {
  const next=observe(record,{connected});
  ingest(record,next);evidence=next;
  status.textContent=evidence.label;
  scope.textContent=(source.test_feed?'Test feed / ':'')+(source.selection==='pinned'?'This chat':'Latest local session');
  const detail=!connected?'Local connection unavailable.':record?.stale?'Last observation over five minutes old.':record?`Observed ${record.event}.`:'No host activity observed.';
  canvas.setAttribute('aria-label',`Cyclops Keeper · ${evidence.label}. ${detail}`);
  status.title=`${detail} A stopped turn does not establish success. Motion is an artistic interpretation of observed activity.`;
  if(!source.test_feed)status.removeAttribute('aria-description');
  document.body.dataset.dim=String(evidence.dim);canvas.dataset.phase=evidence.phase;
  canvas.dataset.observation=[record?.session,record?.event,record?.sequence].join('|');
  if(metrics.phase!==evidence.phase)Object.assign(metrics,{phase:evidence.phase,start:performance.now(),frames:0,cpu:0,samples:[],published:0});
  restart();
}
async function poll() {
  if(fetching)return;fetching=true;clearTimeout(pollTimer);
  try {
    const response=await fetch('/api/state',{cache:'no-store',signal:AbortSignal.timeout(1800)});
    if(!response.ok)throw Error('Local feed unavailable');
    const data=await response.json();if(data.schema!=='activity-face/v1'||!Array.isArray(data.sessions))throw Error('Invalid feed');
    record=data.sessions[0]||null;source=data;connected=true;
  } catch {connected=false;quiet();}
  fetching=false;adopt();pollTimer=setTimeout(poll,document.hidden?5000:500);
}
const observer=new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;restart();});observer.observe(canvas);
document.addEventListener('visibilitychange',()=>{if(document.hidden)quiet();restart();if(!document.hidden)poll();});
addEventListener('resize',restart);motion.addEventListener('change',restart);
if(!ctx){status.textContent='Graphics unavailable';canvas.textContent='Canvas 2D unavailable. The terminal presentation remains usable.';}
else if(fixtureSeed&&fixtureSeed.test_feed===true) {
  source=fixtureSeed;record=fixtureSeed.sessions?.[0]||null;connected=true;adopt();
} else {adopt();poll();}

document.getElementById('sound-mode')?.addEventListener('click',async(event)=>{
  audioEnabled=!audioEnabled;soundGate.setEnabled(audioEnabled);
  event.currentTarget.textContent=audioEnabled?'Sound: Soft':'Sound: Off';event.currentTarget.setAttribute('aria-pressed',String(audioEnabled));
  if(!audioEnabled){quiet();return}
  try{audioContext ||= new AudioContext();await audioContext.resume();if(!manifested){manifested=true;void sound({type:'presence.open',t:Date.now()/1000})}}catch{audioEnabled=false;soundGate.setEnabled(false)}
});
