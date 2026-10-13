// Local, original UI demonstration. Actual built UI with simulated Chrome APIs.
// Never included in the shipped extension or used as evidence of real ASR quality.
import { createServer } from 'node:http';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';
const root = fileURLToPath(new URL('../', import.meta.url));
const built = resolve(root, 'dist/extension');
const health = {protocol_version:1,mode:'whisperlivekit',status:'ready',asr:'ready',translation:'configured',source_languages:['en','zh','auto'],target_languages:['zh-CN','en']};
// This function is also embedded in the browser shims. Explicit URL settings win
// over stored demo preferences; without a query the normal persistence is kept.
export function resolveFixtureConfig(search, saved = {}) {
  const params = new URLSearchParams(search);
  const languages = ['en', 'zh-CN'];
  const modes = ['en-zh', 'zh-en', 'auto-zh', 'auto-en'];
  const stored = saved && typeof saved === 'object' && !Array.isArray(saved) ? saved : {};
  const settings = stored.settings && typeof stored.settings === 'object' && !Array.isArray(stored.settings) ? stored.settings : {};
  return {
    uiLanguage: languages.includes(params.get('lang')) ? params.get('lang') : languages.includes(stored.uiLanguage) ? stored.uiLanguage : 'en',
    settings: {
      backendBaseUrl:'http://127.0.0.1:8765',fontSizePx:24,showSourceText:true,...settings,
      translationMode: modes.includes(params.get('mode')) ? params.get('mode') : modes.includes(settings.translationMode) ? settings.translationMode : 'en-zh',
    },
  };
}
const fixtureConfig = `${resolveFixtureConfig.toString()}
let saved={};try{saved=JSON.parse(localStorage.getItem('release-fixture')||'{}');}catch{}
const store=resolveFixtureConfig(location.search,saved);`;
const popupShim = `
${fixtureConfig}
const changes=new Set();
let state={phase:'idle'};
function snap(){document.documentElement.dataset.fixture=JSON.stringify({state,store});return structuredClone({state,settings:store.settings,uiLanguage:store.uiLanguage,extensionId:'ggakbplmndfijhdcepbafoibilffbhmg',health:${JSON.stringify(health)}});}
const storage={async get(key){return {[key]:store[key]}},async set(values){const update={};for(const [key,newValue] of Object.entries(values)){update[key]={oldValue:store[key],newValue};store[key]=newValue;}localStorage.setItem('release-fixture',JSON.stringify(store));for(const fn of changes)fn(update,'local');if(parent!==window)parent.postMessage({type:'fixture-settings',language:store.uiLanguage,mode:store.settings.translationMode},location.origin);}};
window.chrome={runtime:{id:'ggakbplmndfijhdcepbafoibilffbhmg',async sendMessage(m){if(m.type==='SET_UI_LANGUAGE')await storage.set({uiLanguage:m.language});if(m.type==='SAVE_SETTINGS')await storage.set({settings:m.settings});if(m.type==='START_SESSION')state={phase:'running',tabId:1,sessionId:'demo'};if(m.type==='STOP_SESSION')state={phase:'idle'};return {ok:true,snapshot:snap()};}},tabs:{async query(){return [{id:1,url:'https://www.youtube.com/watch?v=ui-demo'}]}},storage:{local:storage,onChanged:{addListener:fn=>changes.add(fn),removeListener:fn=>changes.delete(fn)}}};`;
const playerShim = `
${fixtureConfig}
const listeners=[],changes=[]; let language=store.uiLanguage, mode=store.settings.translationMode;
window.chrome={runtime:{id:'demo',onMessage:{addListener:fn=>listeners.push(fn)},sendMessage:async()=>({ok:true})},storage:{local:{get:async()=>({uiLanguage:language})},onChanged:{addListener:fn=>changes.push(fn),removeListener:()=>{}}}};
function emit(m){for(const fn of listeners)fn({target:'content',...m},{id:'demo'},()=>{});}
function setLanguage(selected){const oldValue=language;language=selected;document.documentElement.lang=language;const scene=language==='en'?['THE LANGUAGE WORKSHOP','A small garden.','A little care, every day.']:['语言小课堂','一座小花园。','每天一点悉心照料。'];document.querySelectorAll('[data-scene-copy]').forEach((element,index)=>element.textContent=scene[index]);for(const fn of changes)fn({uiLanguage:{oldValue,newValue:language}},'local');}
function show(selected){mode=selected; const target=mode.endsWith('en')?'en':'zh-CN';const source=mode.startsWith('auto')?'auto':mode.split('-')[0];
emit({type:'CONTENT_STOP',sessionId:'demo'});emit({type:'CONTENT_START',sessionId:'demo',settings:{...store.settings,translationMode:mode}});
emit({type:'CONTENT_STATUS',sessionId:'demo',status:{key:'statusConnected'}});emit({type:'CONTENT_SUBTITLE',subtitle:{type:'subtitle',session_id:'demo',segment_id:1,revision:1,start_ms:0,end_ms:3000,source_text:target==='en'?'每天早上给花园里的花浇水。':'Give the flowers fresh water every morning.',source_final:true,source_language:source,target_language:target,translation:{status:'complete',text:target==='en'?'Give the flowers fresh water every morning.':'每天早上给花园里的花浇水。',is_mock:false}}});}
addEventListener('DOMContentLoaded',()=>{setLanguage(language);show(mode);setInterval(()=>show(mode),10000);});
addEventListener('message',e=>{if(e.origin!==location.origin||e.source!==parent)return;if(['en','zh-CN'].includes(e.data?.language))setLanguage(e.data.language);if(['en-zh','zh-en','auto-zh','auto-en'].includes(e.data?.mode))show(e.data.mode);});`;
const scene = `<svg viewBox="0 0 760 440" xmlns="http://www.w3.org/2000/svg"><defs><linearGradient id="bg" x2="1" y2="1"><stop stop-color="#162e4d"/><stop offset="1" stop-color="#256766"/></linearGradient></defs><rect width="760" height="440" fill="url(#bg)"/><circle cx="610" cy="114" r="70" fill="#ffdb99"/><path d="M0 330 Q190 160 370 310 T800 260 V440 H0Z" fill="#214d59"/><path d="M0 395 Q200 270 480 360 T800 350 V440 H0Z" fill="#35756f"/><g fill="none" stroke="#89beae" stroke-width="8"><path d="M570 332V205m0 70-36-22m36 2 37-21"/><path d="M640 332V246m0 55 23-20"/></g><g fill="#9ac4ff"><circle cx="570" cy="199" r="18"/><circle cx="558" cy="182" r="18"/><circle cx="582" cy="182" r="18"/><circle cx="639" cy="241" r="14"/></g><g fill="#eadba6"><circle cx="570" cy="189" r="9"/><circle cx="639" cy="241" r="6"/></g><text x="42" y="62" fill="#afdbc9" font-size="14" font-family="Segoe UI,sans-serif" letter-spacing="3">THE LANGUAGE WORKSHOP</text><text x="40" y="125" fill="white" font-size="38" font-weight="600" font-family="Segoe UI,sans-serif">A small garden.</text><text x="42" y="165" fill="#dbedee" font-size="20" font-family="Segoe UI,sans-serif">A little care, every day.</text></svg>`;
const player = `<!doctype html><html lang="en"><meta charset="utf-8"><style>body{margin:0;background:#152b46}#movie_player{position:relative;width:100%;aspect-ratio:760/440;overflow:hidden}svg{display:block;width:100%}</style><div id="movie_player">${scene.replaceAll('<text ', '<text data-scene-copy ')}</div><script src="/player-shim.js"></script><script src="/content.js"></script></html>`;
const overviewCopy = {
  en: {
    title:'StreamLingo · Local UI demonstration',tag:'AI subtitles for YouTube livestreams · Local LLM support',headline:'Live streams. AI-translated.',
    promise:'Let YouTube livestreams speak your language.',setup:'Already using Ollama? Setup once. Start daily.',
    independent:'No streamer captions needed',readable:'Captions at a readable pace',local:'Local AI support',
    note:'UI demonstration · Original sample content · Requires Ollama and the local companion service',
    video:'Subtitle demonstration',popup:'StreamLingo extension popup',toChinese:'English to Chinese demo',toEnglish:'Chinese to English demo',capture:'Save captured screenshot',
    modes:{'en-zh':'English → Chinese','zh-en':'Chinese → English','auto-zh':'Auto-detect → Chinese','auto-en':'Auto-detect → English'},
  },
  'zh-CN': {
    title:'StreamLingo · 本地界面演示',tag:'YouTube 直播 AI 翻译字幕 · 支持本地大模型',headline:'让 YouTube 直播说你的语言。',
    promise:'直接识别直播声音，实时生成翻译字幕。',setup:'已有 Ollama？配置一次，日常一键启动。',
    independent:'不依赖主播提供字幕',readable:'从容阅读，字幕自动分页',local:'支持本地大模型',
    note:'界面演示 · 原创示例内容 · 需配合 Ollama 与本地服务使用',
    video:'字幕演示',popup:'StreamLingo 扩展弹窗',toChinese:'英语译中文演示',toEnglish:'中文译英语演示',capture:'保存已截取的图片',
    modes:{'en-zh':'英语 → 中文','zh-en':'中文 → 英语','auto-zh':'自动识别 → 中文','auto-en':'自动识别 → 英语'},
  },
};
const overview = `<!doctype html><html lang="en"><meta charset="utf-8"><title>StreamLingo · Local UI demonstration</title><style>*{box-sizing:border-box}html{scrollbar-width:none}body{margin:0;background:#eef4fb;color:#132642;font:16px/1.5 'Segoe UI',sans-serif}.page{width:1280px;height:800px;padding:28px 42px;overflow:clip}.top{display:flex;align-items:center;gap:16px}.logo{width:60px;height:60px}h1{margin:0;font-size:32px;letter-spacing:-.7px}.tag{margin:0;color:#415f80}.badge{margin-left:auto;color:#24538e;border:1px solid #c3d5ef;padding:8px 14px;border-radius:50px;font-size:13px}.layout{display:grid;grid-template-columns:780px 382px;gap:30px;margin-top:30px}h2{font-size:30px;line-height:1.2;margin:0 0 16px}.sub{margin:0 0 22px;color:#506982;max-width:680px}iframe{border:0;width:100%;display:block}.video{height:452px;border-radius:18px;box-shadow:0 14px 32px #153e5520}.popup{height:604px;background:#f8fafc;border-radius:18px;box-shadow:0 14px 32px #153e5518;border:1px solid #d5e0ed}.features{display:flex;gap:10px;margin-top:20px}.features span{background:white;border:1px solid #d6e1ef;padding:8px 12px;border-radius:8px;font-size:13px;color:#294b74}.note{margin-top:16px;font-size:12px;color:#5a6e84}.controls{position:absolute;top:828px;left:42px;display:flex;gap:10px}button{padding:12px;font:inherit}</style><main class="page"><div class="top"><img class="logo" src="/icon128.png" alt=""><div><h1>StreamLingo</h1><p class="tag" data-copy="tag"></p></div><span class="badge"></span></div><div class="layout"><section><h2 data-copy="headline"></h2><p class="sub"><span data-copy="promise"></span><br><span data-copy="setup"></span></p><iframe title="Subtitle demonstration" class="video"></iframe><div class="features"><span data-copy="independent"></span><span data-copy="readable"></span><span data-copy="local"></span></div><p class="note" data-copy="note"></p></section><iframe title="StreamLingo extension popup" class="popup"></iframe></div></main><div class="controls"><button data-mode="en-zh" data-copy="toChinese"></button><button data-mode="zh-en" data-copy="toEnglish"></button><a href="/capture" data-copy="capture"></a></div><script src="/overview.js"></script></html>`;
const overviewScript = `
${fixtureConfig}
const copy=${JSON.stringify(overviewCopy)},video=document.querySelector('.video'),popup=document.querySelector('.popup');
function renderCopy(){const text=copy[store.uiLanguage];document.documentElement.lang=store.uiLanguage;document.title=text.title;document.querySelectorAll('[data-copy]').forEach(element=>element.textContent=text[element.dataset.copy]);document.querySelector('.badge').textContent=text.modes[store.settings.translationMode];video.title=text.video;popup.title=text.popup;}
function loadFrames(){const query=new URLSearchParams({lang:store.uiLanguage,mode:store.settings.translationMode});video.src='/player?'+query;popup.src='/popup?'+query;}
renderCopy();loadFrames();
document.querySelectorAll('[data-mode]').forEach(button=>button.onclick=()=>{store.settings.translationMode=button.dataset.mode;localStorage.setItem('release-fixture',JSON.stringify(store));renderCopy();loadFrames();});
addEventListener('message',event=>{if(event.origin!==location.origin||event.source!==popup.contentWindow||event.data?.type!=='fixture-settings')return;if(!['en','zh-CN'].includes(event.data.language)||!['en-zh','zh-en','auto-zh','auto-en'].includes(event.data.mode))return;store.uiLanguage=event.data.language;store.settings.translationMode=event.data.mode;renderCopy();video.contentWindow.postMessage({language:store.uiLanguage,mode:store.settings.translationMode},location.origin);});`;
const assets = new Set(['streamlingo-overview.jpg','popup.jpg','store-chinese-to-english.jpg',
  'popup-en.jpg','popup-zh-CN.jpg','streamlingo-overview-en.jpg','streamlingo-overview-zh-CN.jpg',
  'popup-en.png','popup-zh-CN.png','streamlingo-overview-en.png','streamlingo-overview-zh-CN.png']);
export function imageMatchesAsset(name, bytes) {
  if (!assets.has(name)) return false;
  const isPng = bytes.length >= 8 && bytes.subarray(0, 8).equals(Buffer.from([137,80,78,71,13,10,26,10]));
  const isJpeg = bytes.length >= 3 && bytes[0] === 255 && bytes[1] === 216 && bytes[2] === 255;
  return name.endsWith('.png') ? isPng : name.endsWith('.jpg') && isJpeg;
}
const capture = `<!doctype html><meta charset="utf-8"><title>Save local UI screenshot</title><h1>Save a browser screenshot locally</h1><p>This form saves only to this repository's docs/assets directory. No external upload. Select a filename matching the screenshot's actual PNG or JPEG format.</p><form method="POST" action="/capture"><label>Asset name <select name="name">${[...assets].map(name=>`<option>${name}</option>`).join('')}</select></label><p><label>PNG or JPEG base64 <textarea name="data" aria-label="PNG or JPEG base64"></textarea></label></p><button>Save screenshot</button></form>`;
const server=createServer(async(req,res)=>{
 try {
 const pathname=new URL(req.url,'http://127.0.0.1').pathname;
 res.setHeader('Cache-Control','no-store');
 if(req.method==='POST'&&pathname==='/capture'){
   if(req.headers.origin!=='http://127.0.0.1:8899'){res.writeHead(403);res.end();return;}
   let body='';for await(const chunk of req){body+=chunk;if(body.length>3_000_000){res.writeHead(413);res.end();return;}}
   const form=new URLSearchParams(body),name=form.get('name'),bytes=Buffer.from(form.get('data')||'','base64');
   if(!imageMatchesAsset(name,bytes)){res.writeHead(400);res.end('Expected PNG or JPEG bytes matching an allowlisted filename');return;}
   await mkdir(resolve(root,'docs/assets'),{recursive:true});await writeFile(resolve(root,'docs/assets',name),bytes);
   res.setHeader('Content-Type','text/html; charset=utf-8');res.end(`<p>Saved ${name} (${bytes.length} bytes) locally.</p><a href="/capture">Save another</a>`);return;
 }
 const pages={'/':overview,'/player':player,'/capture':capture};
 if(pages[pathname]){res.setHeader('Content-Type','text/html; charset=utf-8');res.end(pages[pathname]);return;}
 const js={'/popup-shim.js':popupShim,'/player-shim.js':playerShim,'/overview.js':overviewScript};
 if(js[pathname]){res.setHeader('Content-Type','text/javascript; charset=utf-8');res.end(js[pathname]);return;}
 const file={'/popup':'popup.html','/popup.css':'popup.css','/popup.js':'popup.js','/content.js':'content.js','/icon128.png':'icons/icon128.png'}[pathname];
 if(!file){res.writeHead(404);res.end();return;}
 let data=await readFile(resolve(built,file));
 if(file==='popup.html')data=data.toString().replace('<head>','<head><script src="/popup-shim.js"></script>');
 res.setHeader('Content-Type',file.endsWith('.png')?'image/png':file.endsWith('.html')?'text/html; charset=utf-8':file.endsWith('.css')?'text/css; charset=utf-8':'text/javascript; charset=utf-8');res.end(data);
 }catch(error){console.error(error);res.writeHead(500);res.end('Build output is not ready');}
});
// Importing the pure config/image validators must not start the preview service.
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  server.listen(8899,'127.0.0.1',()=>console.log('Local UI demo: http://127.0.0.1:8899/?lang=en&mode=en-zh (Ctrl+C to stop)'));
}
