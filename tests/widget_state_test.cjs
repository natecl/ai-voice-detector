const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync('ui/index.html','utf8');
const scripts=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];
const elements=new Map();
const get=id=>{
 if(!elements.has(id))elements.set(id,{textContent:'',hidden:false,style:{},classList:{add(){},remove(){},toggle(){}},attributes:{},setAttribute(k,v){this.attributes[k]=v;},addEventListener(){},pause(){}});
 return elements.get(id);
};
const root={dataset:{},classList:{toggle(){}}},messages=[];
const context={document:{getElementById:get,documentElement:root},window:{webkit:{messageHandlers:{systemAudio:{postMessage:x=>messages.push(x)}}},addEventListener(){}},console,Date,URL,Blob,setInterval:()=>1,clearInterval:()=>{}};
vm.createContext(context);vm.runInContext(scripts.at(-1)[1],context);
get('systemListen').onclick();assert.deepEqual(messages,['start']);
context.window.onSystemAudioEvent({state:'listening'});assert.equal(get('overlayState').textContent,'Listening');
for(const prediction of ['HUMAN','AI']){
 context.window.onSystemAudioEvent({state:'result',result:{status:'ok',prediction,synthetic_score:prediction==='AI'?.9:.1,analyzed_start_seconds:0,analyzed_end_seconds:5,duration_seconds:5,inference_seconds:.2,model:'test'}});
 assert.equal(get('overlayState').textContent,prediction==='AI'?'AI':'Human');
 context.window.onSystemAudioEvent({state:'analyzing'});
 assert.equal(get('overlayState').textContent,prediction==='AI'?'AI':'Human','Do not flicker between results');
}
context.window.onSystemAudioEvent({state:'result',result:{status:'insufficient_speech'}});
assert.equal(get('overlayState').textContent,'Waiting');
assert.equal(root.dataset.verdict,'waiting');
context.window.onSystemAudioEvent({state:'levels',values:[0,.1,.3,.5,.8,1,NaN,Infinity]});
assert.equal(get('waveBar6').attributes.height,'16.00');
assert.equal(get('waveBar0').attributes.height,'2.00');
assert.equal(get('overlayState').textContent,'Waiting','Levels must not overwrite verdict/status');
get('systemListen').onclick();assert.deepEqual(messages,['start','stop']);
context.window.onSystemAudioEvent({state:'stopped'});
assert.equal(get('overlayState').textContent,'','Idle must have no instruction or stale verdict');
assert.equal(get('waveBar6').attributes.height,'2.00');
context.window.onSystemAudioEvent({state:'levels',values:[1,1,1]});
assert.equal(get('waveBar6').attributes.height,'2.00','Late level events after stop must be ignored');
context.window.onSystemAudioEvent({state:'error',message:'Permission denied'});
assert.equal(get('overlayState').textContent,'Access');
assert.equal(get('error').textContent,'Permission denied');
console.log('Widget state checks passed: click start/stop, human, AI, analysis stability, silence, idle, and error.');
