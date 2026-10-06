/* Keeper's material voice: rubbed membrane, irregular woven modes, short
   filament catches. Mono by design: a host may place it in a room. No stock samples,
   melody, outcome verdict, loop or waiting queue. */
export const VERSION = 'keeper-sound/2';
export const CUES = Object.freeze({
  catch: {seconds:.72, base:173, bend:-.16, friction:.30, knots:[.035,.086], decay:.21},
  stitch: {seconds:.56, base:211, bend:-.09, friction:.16, knots:[.02,.073,.137], decay:.14},
  hold: {seconds:1.12, base:149, bend:.12, friction:.23, knots:[.10], decay:.38},
  fold: {seconds:.96, base:184, bend:-.37, friction:.42, knots:[.07,.21], decay:.24},
  unfold: {seconds:1.04, base:139, bend:.22, friction:.27, knots:[.12,.27], decay:.31},
  satellite: {seconds:.66, base:263, bend:-.17, friction:.24, knots:[.028,.123], decay:.17},
  settle: {seconds:.62, base:121, bend:-.12, friction:.16, knots:[.075], decay:.19},
  release: {seconds:.74, base:191, bend:.19, friction:.22, knots:[.042,.102,.19], decay:.22},
  manifest: {seconds:2.12, base:147, bend:-.05, friction:.32, knots:[.16,.39,.71], decay:.42},
});
const EVENT_CUES = {
  'presence.open':'manifest', 'turn.receive':'catch', 'approval.request':'hold', 'context.fold':'fold',
  'context.unfold':'unfold', 'turn.stop':'settle', 'reply.copied':'release',
};
export function soundFor(ev) {
  if (!ev || typeof ev !== 'object') return null;
  let name = EVENT_CUES[ev.type];
  if (ev.type === 'tool.return' && /^[a-f0-9]{64}$/.test(ev.key||'')) name='stitch';
  if (ev.type === 'branch.start' && /^[a-f0-9]{64}$/.test(ev.key||'')) name='satellite';
  if (ev.type === 'branch.return' && /^[a-f0-9]{64}$/.test(ev.key||'')) name='stitch';
  return name ? {name,seconds:CUES[name].seconds} : null;
}
export function createSoundGate() {
  let enabled=false, until=0;
  return {
    setEnabled(value) {enabled=Boolean(value);if(!enabled)until=0;},
    take(ev, now) {
      const cue=soundFor(ev);
      if (!enabled || !cue || !Number.isFinite(ev.t) || ev.t>now || now-ev.t>1.5 || now<until) return null;
      until=now+cue.seconds;return cue;
    },
  };
}

export function synthesize(name, sampleRate=48000, {variant='woven'}={}) {
  const c=CUES[name];if(!c)throw Error('Unknown Keeper sound');
  if(!Number.isFinite(sampleRate)||sampleRate<8000||sampleRate>96000)throw Error('Invalid sample rate');
  const length=Math.round(c.seconds*sampleRate), out=new Float32Array(length);
  const ratios=variant==='glass' ? [1,1.5,2,3,4.5,6] : [1,1.437,2.293,3.781,5.173,7.119];
  const phases=ratios.map((_,i)=>.71+i*1.391);
  const fluid=variant==='woven';
  let seed=0x713c9241, low=0, previousNoise=0, rounded=0, peak=0;
  const rnd=()=>{seed^=seed<<13;seed^=seed>>>17;seed^=seed<<5;return (seed>>>0)/0xffffffff*2-1;};
  for(let i=0;i<length;i++) {
    const t=i/sampleRate,u=t/c.seconds;
    const n=rnd();low+=(fluid?.035:.085)*(n-low);
    const brushed=fluid?low*.9:(n-previousNoise)*.13+low*.8;previousNoise=n;
    let excitation=0;
    for(let j=0;j<c.knots.length;j++) {
      const age=t-c.knots[j];
      if(age>=0)excitation+=(1-j*.16)*(1-Math.exp(-age/(fluid?.025:.012)))*Math.exp(-age/c.decay);
    }
    // A yielding material rather than a sequence of notes: modes share one
    // excitation and bend together through the same physical change.
    const tension=1+c.bend*(1-Math.exp(-t/.21));
    const base=c.base*(variant==='glass'?2.2:variant==='dry'?1.14:1);
    let mode=0;
    for(let j=0;j<ratios.length;j++) {
      phases[j]+=2*Math.PI*base*ratios[j]*tension/sampleRate;
      const decay=Math.exp(-t*(.75+j*.74));
      mode+=Math.sin(phases[j]+.027*Math.sin(t*39+j))*decay/(1+j*.72);
    }
    const friction=c.friction*(variant==='dry'?2.4:variant==='glass'?.22:fluid?.48:1);
    // Yielding water pockets round each filament contact within the same body.
    let water=0;
    if(fluid)for(let j=0;j<c.knots.length;j++){
      const age=t-c.knots[j]-.018;
      if(age>=0){const radius=.075+j*.011;
        const cavity=(1-Math.exp(-age/.019))*Math.exp(-age/radius);
        const pressurePhase=2*Math.PI*c.base*(1.62*age+.17*radius*(1-Math.exp(-age/radius)));
        water+=Math.sin(pressurePhase+.63*j)*cavity*(1-j*.16);
      }
    }
    const body=mode*(fluid?.235:.22) + brushed*friction*(.6+.4*Math.sin(t*(fluid?23:67))**2) + water*.09;
    const envelope=(1-Math.exp(-t/.035))*Math.min(1,(c.seconds-t)/.09);
    const arriving=name==='manifest' ? (.38+.62*Math.sin(Math.PI*Math.min(1,t/1.35))**2) : 1;
    // Closely spaced, nonperiodic contact reflections are kept within the body.
    const lag=Math.round((.0137+(name==='fold'?.007:0))*sampleRate);
    const reflected=i>=lag?out[i-lag]*.19:0;
    const raw=Math.tanh((body*excitation*arriving+reflected)*1.3)*envelope;
    rounded+=.28*(raw-rounded);
    const value=fluid?rounded:raw;
    out[i]=value;peak=Math.max(peak,Math.abs(value));
  }
  const gain=peak>.0?Math.min(1.8,(fluid?.43:.48)/peak):1;
  for(let i=0;i<length;i++)out[i]*=gain;
  out[length-1]=0;
  return out;
}

// The rare voiced identity is an authored mono asset. Other cues are material
// synthesis. Hosts request a buffer; the host still owns gain and room position.
const buffers=new WeakMap();
export async function prepareBuffer(name,context){
  let cache=buffers.get(context);if(!cache){cache=new Map();buffers.set(context,cache)}
  if(!cache.has(name))cache.set(name,(async()=>{
    if(name==='manifest') {
      const response=await fetch(new URL('./keeper-manifest.wav',import.meta.url));
      if(!response.ok)throw Error('Keeper identity sound unavailable');
      const result=await context.decodeAudioData(await response.arrayBuffer());
      if(result.numberOfChannels!==1||result.duration>3)throw Error('Invalid Keeper identity sound');
      return result;
    }
    const samples=synthesize(name,context.sampleRate),buffer=context.createBuffer(1,samples.length,context.sampleRate);
    buffer.copyToChannel(samples,0);return buffer;
  })());
  return cache.get(name);
}
