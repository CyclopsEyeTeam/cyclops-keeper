/*
 * Infinite Colour / DrawPlayer Colour Language
 *
 * Colours are recipes, not terminal RGB values. The engine has no knowledge of
 * canvas, audio or geometry, which keeps it portable and lets later renderers
 * add mixers and transformers without changing stored recipes.
 *
 * Originated in the Cyclops Eye Team's DrawPlayer work and released here as a
 * reusable component, under this project's MIT licence (see LICENSE).
 */

export const COLOUR_RECIPE_VERSION=1;

const mixMethods=new Map();
const transformerMethods=new Map();
const transformerOrder=['exposure','brightness','contrast','saturation','hueShift','temperature','tint'];
const clamp=(value,min=0,max=1)=>Math.max(min,Math.min(max,Number.isFinite(value)?value:0));
const clone=value=>JSON.parse(JSON.stringify(value));
const srgbToLinear=value=>value<=.04045?value/12.92:Math.pow((value+.055)/1.055,2.4);
const linearToSrgb=value=>value<=.0031308?value*12.92:1.055*Math.pow(Math.max(0,value),1/2.4)-.055;

function normaliseRgb(input={}){
  const source=input.rgb||input;
  return{r:clamp(source.r??source.red),g:clamp(source.g??source.green),b:clamp(source.b??source.blue)};
}

function rgbToHsl({r,g,b}){
  const max=Math.max(r,g,b),min=Math.min(r,g,b),light=(max+min)/2,delta=max-min;
  if(delta===0)return{h:0,s:0,l:light};
  const saturation=delta/(1-Math.abs(2*light-1));
  let hue=max===r?((g-b)/delta)%6:max===g?(b-r)/delta+2:(r-g)/delta+4;
  hue=(hue/6+1)%1;
  return{h:hue,s:saturation,l:light};
}

function hslToRgb({h,s,l}){
  const hue=((h%1)+1)%1,saturation=clamp(s),light=clamp(l),chroma=(1-Math.abs(2*light-1))*saturation,x=chroma*(1-Math.abs((hue*6)%2-1)),m=light-chroma/2;
  let rgb=hue<1/6?[chroma,x,0]:hue<2/6?[x,chroma,0]:hue<3/6?[0,chroma,x]:hue<4/6?[0,x,chroma]:hue<5/6?[x,0,chroma]:[chroma,0,x];
  return{r:clamp(rgb[0]+m),g:clamp(rgb[1]+m),b:clamp(rgb[2]+m)};
}

export function createColourSeed(red=0,green=0,blue=0,options={}){
  if(typeof red==='object'){
    const source=red,metadata=green&&typeof green==='object'?green:{};
    return{version:1,id:source.id||metadata.id||'SEED',rgb:normaliseRgb(source),meta:clone(source.meta||metadata.meta||{})};
  }
  return{version:1,id:options.id||'SEED',rgb:{r:clamp(red),g:clamp(green),b:clamp(blue)},meta:clone(options.meta||{})};
}

export function normaliseWeights(weights=[],count=weights.length){
  const clean=Array.from({length:count},(_,index)=>Math.max(0,Number.isFinite(weights[index])?weights[index]:1));
  const total=clean.reduce((sum,value)=>sum+value,0);
  return total>0?clean.map(value=>value/total):clean.map(()=>count?1/count:0);
}

export function registerColourMixMethod(name,mixer){
  if(typeof name!=='string'||typeof mixer!=='function')throw new TypeError('A colour mixer needs a name and function.');
  mixMethods.set(name.toUpperCase(),mixer);
}

export function registerColourTransformer(name,transformer,{orderAfter}={}){
  if(typeof name!=='string'||typeof transformer!=='function')throw new TypeError('A colour transformer needs a name and function.');
  transformerMethods.set(name,transformer);
  if(!transformerOrder.includes(name)){
    const position=orderAfter?transformerOrder.indexOf(orderAfter)+1:-1;
    position>0?transformerOrder.splice(position,0,name):transformerOrder.push(name);
  }
}

registerColourMixMethod('LINEAR_LIGHT',(colours,weights)=>{
  const result={r:0,g:0,b:0};
  colours.forEach((colour,index)=>{result.r+=srgbToLinear(colour.r)*weights[index];result.g+=srgbToLinear(colour.g)*weights[index];result.b+=srgbToLinear(colour.b)*weights[index]});
  return{r:linearToSrgb(result.r),g:linearToSrgb(result.g),b:linearToSrgb(result.b)};
});
registerColourMixMethod('SRGB',(colours,weights)=>colours.reduce((result,colour,index)=>({r:result.r+colour.r*weights[index],g:result.g+colour.g*weights[index],b:result.b+colour.b*weights[index]}),{r:0,g:0,b:0}));
registerColourMixMethod('SCREEN',(colours,weights)=>colours.reduce((result,colour,index)=>({r:1-(1-result.r)*(1-colour.r*weights[index]),g:1-(1-result.g)*(1-colour.g*weights[index]),b:1-(1-result.b)*(1-colour.b*weights[index])}),{r:0,g:0,b:0}));
registerColourMixMethod('MULTIPLY',(colours,weights)=>colours.reduce((result,colour,index)=>({r:result.r*Math.pow(Math.max(.0001,colour.r),weights[index]),g:result.g*Math.pow(Math.max(.0001,colour.g),weights[index]),b:result.b*Math.pow(Math.max(.0001,colour.b),weights[index])}),{r:1,g:1,b:1}));

registerColourTransformer('exposure',(colour,value)=>{const multiplier=Math.pow(2,value);return{...colour,r:colour.r*multiplier,g:colour.g*multiplier,b:colour.b*multiplier}});
registerColourTransformer('brightness',(colour,value)=>({...colour,r:colour.r*value,g:colour.g*value,b:colour.b*value}));
registerColourTransformer('contrast',(colour,value)=>({...colour,r:(colour.r-.5)*value+.5,g:(colour.g-.5)*value+.5,b:(colour.b-.5)*value+.5}));
registerColourTransformer('saturation',(colour,value)=>{const luma=colour.r*.2126+colour.g*.7152+colour.b*.0722;return{...colour,r:luma+(colour.r-luma)*value,g:luma+(colour.g-luma)*value,b:luma+(colour.b-luma)*value}});
registerColourTransformer('hueShift',(colour,value)=>{const hsl=rgbToHsl(colour);return hslToRgb({...hsl,h:hsl.h+value})});
registerColourTransformer('temperature',(colour,value)=>({...colour,r:colour.r+value*.14,g:colour.g+value*.025,b:colour.b-value*.14}));
registerColourTransformer('tint',(colour,value)=>value>=0?{...colour,g:colour.g+value*.12,r:colour.r-value*.035,b:colour.b-value*.035}:{...colour,g:colour.g+value*.12,r:colour.r-value*.07,b:colour.b-value*.07});

export function mixColours(colours=[],weights=[],options={}){
  const resolved=colours.map(colour=>normaliseRgb(colour)),normalised=normaliseWeights(weights,resolved.length),method=(typeof options==='string'?options:options.method||'LINEAR_LIGHT').toUpperCase(),mixer=mixMethods.get(method)||mixMethods.get('LINEAR_LIGHT');
  if(!resolved.length)return{r:0,g:0,b:0,a:1,emission:0};
  const mixed=mixer(resolved,normalised,options);
  return{r:clamp(mixed.r),g:clamp(mixed.g),b:clamp(mixed.b),a:1,emission:0};
}

export function applyTransforms(colour,transforms={}){
  let result={...normaliseRgb(colour),a:clamp(colour.a??1),emission:Math.max(0,colour.emission||0)};
  for(const name of transformerOrder){
    const transformer=transformerMethods.get(name);
    if(!transformer||!Number.isFinite(transforms[name]))continue;
    result=transformer(result,transforms[name],transforms);
  }
  result.r=clamp(result.r);result.g=clamp(result.g);result.b=clamp(result.b);
  result.a=clamp((transforms.opacity??result.a));
  result.emission=Math.max(0,transforms.emission??result.emission);
  return result;
}

export function createColourRecipe({id='COLOUR',seeds=[],mixWeights=[],mix={method:'LINEAR_LIGHT'},transforms={},mapping={mode:'WHOLE',fractions:[]},meta={}}={}){
  const cleanSeeds=seeds.map((entry,index)=>entry?.colour?{colour:createColourSeed(entry.colour),weight:Number.isFinite(entry.weight)?entry.weight:mixWeights[index]}:{colour:createColourSeed(entry),weight:mixWeights[index]}),weights=normaliseWeights(cleanSeeds.map(entry=>entry.weight),cleanSeeds.length);
  return{version:COLOUR_RECIPE_VERSION,id,seeds:cleanSeeds.map((entry,index)=>({colour:entry.colour,weight:weights[index]})),mix:{...clone(mix),method:(mix.method||'LINEAR_LIGHT').toUpperCase()},transforms:{brightness:1,saturation:1,hueShift:0,temperature:0,tint:0,opacity:1,emission:0,...clone(transforms)},mapping:{mode:'WHOLE',fractions:[],...clone(mapping)},meta:clone(meta)};
}

export function evaluateColourRecipe(recipe,overrides={}){
  const clean=createColourRecipe(recipe||{}),mixed=mixColours(clean.seeds.map(entry=>entry.colour),clean.seeds.map(entry=>entry.weight),clean.mix),transforms={...clean.transforms,...(overrides.transforms||{})};
  return{...applyTransforms(mixed,transforms),recipeId:clean.id,method:clean.mix.method};
}

export function toRGB255(colour){const rgb=normaliseRgb(colour);return{r:Math.round(rgb.r*255),g:Math.round(rgb.g*255),b:Math.round(rgb.b*255),a:clamp(colour.a??1)}}
export function toHex(colour,includeAlpha=false){const rgb=toRGB255(colour),hex=value=>value.toString(16).padStart(2,'0').toUpperCase();return`#${hex(rgb.r)}${hex(rgb.g)}${hex(rgb.b)}${includeAlpha?hex(Math.round(rgb.a*255)):''}`}
export function toCssRgba(colour,alphaMultiplier=1){const rgb=toRGB255(colour);return`rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, ${clamp(rgb.a*alphaMultiplier).toFixed(4)})`}

export const ColourLanguage=Object.freeze({
  version:COLOUR_RECIPE_VERSION,
  createColourSeed,createColourRecipe,mixColours,applyTransforms,evaluateColourRecipe,toRGB255,toHex,toCssRgba,normaliseWeights,
  registerColourMixMethod,registerColourTransformer,
  listMixMethods:()=>[...mixMethods.keys()],
  listTransformers:()=>[...transformerOrder,'opacity','emission']
});
