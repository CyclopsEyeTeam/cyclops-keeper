// Recipes evaluated by the user's unmodified DrawPlayer Colour Language.
import {createColourSeed, createColourRecipe, evaluateColourRecipe, toRGB255} from '../assets/colour-engine.js';
import {writeFileSync} from 'node:fs';
const seeds={idle:[.42,.78,.57],working:[.88,.69,.32],tool:[.35,.76,.86],waiting:[.72,.55,.88],stopped:[.59,.83,.63],interrupted:[.86,.56,.37],ended:[.43,.49,.46],unknown:[.56,.61,.57]};
const recipes={},colours={};
for(const [state,rgb] of Object.entries(seeds)){
 const recipe=createColourRecipe({id:`CODEX_FACE_${state.toUpperCase()}`,seeds:[createColourSeed(...rgb),createColourSeed(.78,.83,.80)],mixWeights:[.75,.25],mix:{method:'LINEAR_LIGHT'},transforms:{saturation:.85}});
 const c=toRGB255(evaluateColourRecipe(recipe));recipes[state]=recipe;colours[state]=[c.r,c.g,c.b];
}
writeFileSync(new URL('../assets/palette.json',import.meta.url),JSON.stringify({engine:'DrawPlayer Colour Language v1',recipes,colours},null,2)+'\n');
