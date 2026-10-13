// Local recording fixture only. Uses the actual built popup/content UI with
// simulated Chrome APIs and explicitly labelled, frozen recorded excerpts.
import { createServer } from 'node:http';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = fileURLToPath(new URL('../', import.meta.url));
const BUILT = resolve(ROOT, 'dist/extension');
const ORIGIN = 'http://127.0.0.1:8900';
export const KEYFRAMES = [0, 6, 12, 16, 18, 24, 30, 36, 44, 48, 54];
const LOCALES = ['en', 'zh-CN'];
const DURATION = 30;
const FPS = 2;
const MAX_BODY = 8 * 1024 * 1024;
const EVIDENCE = new Set(['live-en-running.jpg', 'release-published.jpg']);
const health = { protocol_version:1,mode:'whisperlivekit',status:'ready',asr:'ready',translation:'configured',source_languages:['en','zh','auto'],target_languages:['zh-CN','en'] };
const copy = {
  en: {
    demo:'UI demonstration · Original sample',recorded:'Recorded result excerpt · Simulated controls · No live inference',scripted:'Scripted sample subtitles · Simulated controls · No live inference',
    tag:'AI subtitles for YouTube livestreams · Local LLM support',mode:'Chinese → English',
    titles:['No English captions? Add them live.','Open a YouTube livestream.','Choose your translation direction.','Click Start captions.','Your subtitles, on the video.','Read the original and translation.','Follow the conversation.','A little care, every day.','Time to read each caption.','Stop whenever you want.','Try StreamLingo.'],
    descriptions:['Let YouTube livestreams speak your language.','Choose a livestream you want to understand.','Open a YouTube livestream, then open the extension.','The button below is the actual extension interface.','This preview replays saved model output on an original scene.','Saved model output, unchanged. This is a selected excerpt.','The source sentence stays with its own translation.','English or Chinese: choose the direction you need.','Automatic pages give each caption at least four seconds.','Stop captions. Keep watching your video.','Find the project, downloads and requirements on GitHub.'],
    chips:['No streamer captions needed','Local Ollama support','English ↔ Chinese'],
    prerequisites:'Requires Ollama + local service. Windows preview: NVIDIA GPU, CUDA 12 and cuDNN 9. See installation requirements.',
    download:'View on GitHub',popup:'Actual extension popup · simulated session',player:'Original garden scene · recorded subtitle excerpt',
    garden:['THE LANGUAGE WORKSHOP','A small garden.','A little care, every day.'],
    frame:'Recording controls (outside the video)',previous:'Previous keyframe',next:'Next keyframe',play:'Play 30-second preview',capture:'Save captured frames',preview:'preview',replay:'Silent, edited UI walkthrough · Not an accuracy benchmark',
  },
  'zh-CN': {
    demo:'界面演示 · 原创样例',recorded:'录制结果节选回放 · 模拟操作状态 · 非现场推理',scripted:'原创脚本字幕 · 模拟操作状态 · 非现场推理',
    tag:'YouTube 直播 AI 翻译字幕 · 支持本地大模型',mode:'英语 → 中文',
    titles:['直播没中文字幕？直接看译文。','打开想看的 YouTube 直播。','选好需要的翻译方向。','点击「开始字幕」。','字幕直接显示在视频上。','原文与译文，一起看懂。','跟上对话，也留时间阅读。','每天一点悉心照料。','每页字幕，至少四秒。','想停就停，继续看直播。','开始使用 StreamLingo。'],
    descriptions:['直接识别直播声音，不依赖主播提供字幕。','找到想听懂的直播，直接在视频页面使用。','打开 YouTube 直播，再打开扩展弹窗。','右侧使用实际构建的扩展界面演示操作。','这里回放已保存的模型结果，画面为原创样例。','模型原文和译文保持不变，仅选取其中片段。','每句原文对应自己的译文，避免中英错位。','英语译中文，或中文译英语，自由选择。','字幕自动分页，无需滚动或手动翻页。','停止翻译字幕，视频仍可继续观看。','前往 GitHub，查看项目、下载和运行要求。'],
    chips:['不依赖主播提供字幕','支持本地 Ollama','英语 ↔ 中文'],
    prerequisites:'需 Ollama 与本地服务；Windows 预览版需 NVIDIA 显卡、CUDA 12 与 cuDNN 9，详见安装要求。',
    download:'前往 GitHub',popup:'实际扩展弹窗 · 会话状态为模拟',player:'原创花园画面 · 已录制字幕节选',
    garden:['语言小课堂','一座小花园。','每天一点悉心照料。'],
    frame:'录制控制（不进入视频画面）',previous:'上一关键帧',next:'下一关键帧',play:'播放 30 秒预览',capture:'保存已截取的帧',preview:'预览版',replay:'无声剪辑界面演示 · 不代表识别准确率测试',
  },
};

export function frameOptions(search) {
  const params = new URLSearchParams(search);
  const language = params.get('lang') === 'zh-CN' ? 'zh-CN' : 'en';
  const raw = params.has('frame') ? Number(params.get('frame')) : Number(params.get('t') ?? 0) * FPS;
  const frame = Number.isFinite(raw) ? Math.max(0, Math.min(59, Math.floor(raw))) : 0;
  const time = frame / FPS;
  const stage = KEYFRAMES.findLastIndex(value => value <= frame);
  return { language, frame, time, stage, mode:language === 'en' ? 'zh-en' : 'en-zh', running:time < 3 || (time >= 9 && time < 24) };
}

async function replay(language) {
  const sourceLanguage = language === 'en' ? 'zh' : 'en';
  const file = resolve(ROOT, `output/release-acceptance/20261013/restored-smoke-${sourceLanguage}.json`);
  try {
    const recorded = JSON.parse(await readFile(file, 'utf8'));
    if (recorded.passed !== true || recorded.source_language !== sourceLanguage) throw new Error('Unexpected replay metadata');
    const cues = [3, 4].map(segmentId => recorded.events.filter(event => event.type === 'subtitle' && event.segment_id === segmentId && event.translation?.status === 'complete' && event.translation.is_mock === false).at(-1));
    if (cues.some(cue => !cue || typeof cue.source_text !== 'string' || typeof cue.translation.text !== 'string')) throw new Error('Missing recorded subtitle excerpts');
    return { kind:'recorded', cues, source:`output/release-acceptance/20261013/restored-smoke-${sourceLanguage}.json`, segments:[3,4] };
  } catch (error) {
    if (error.code !== 'ENOENT') throw error;
    // Public clones do not contain local validation captures. Never label this
    // clearly marked original fallback as a recorded model result.
    const originals = [
      ['Put the blue flowers beside the window.', '把蓝色的花放在窗边。'],
      ['Give the flowers fresh water every morning.', '每天早上给花园里的花浇水。'],
    ];
    return { kind:'scripted', source:null, segments:[3,4], cues:originals.map(([english,chinese],index) => ({
      type:'subtitle',session_id:'promo',segment_id:index+3,revision:1,start_ms:index*4000,end_ms:(index+1)*4000,
      source_final:true,source_language:sourceLanguage,target_language:language === 'en' ? 'en' : 'zh-CN',
      source_text:language === 'en' ? chinese : english,
      translation:{status:'complete',text:language === 'en' ? english : chinese,is_mock:true},
    })) };
  }
}

async function config(search) {
  const options = frameOptions(search);
  return { ...options, text:copy[options.language], replay:await replay(options.language), health,
    settings:{backendBaseUrl:'http://127.0.0.1:8765',fontSizePx:26,showSourceText:true,translationMode:options.mode} };
}

function popupClient(data) {
  const changes = new Set();
  const store = { uiLanguage:data.language, settings:data.settings };
  let state = data.running ? {phase:'running',tabId:1,sessionId:'promo'} : {phase:'idle'};
  const snap = () => structuredClone({state,settings:store.settings,uiLanguage:store.uiLanguage,extensionId:'ggakbplmndfijhdcepbafoibilffbhmg',health:data.health});
  const storage = { async get(key) { return {[key]:store[key]}; }, async set(values) {
    const update={}; for(const [key,newValue] of Object.entries(values)){update[key]={oldValue:store[key],newValue};store[key]=newValue;}
    for(const fn of changes)fn(update,'local');
  }};
  window.chrome={runtime:{id:'ggakbplmndfijhdcepbafoibilffbhmg',async sendMessage(message){
    if(message.type==='START_SESSION')state={phase:'running',tabId:1,sessionId:'promo'};
    if(message.type==='STOP_SESSION')state={phase:'idle'};
    if(message.type==='SET_UI_LANGUAGE')await storage.set({uiLanguage:message.language});
    if(message.type==='SAVE_SETTINGS')await storage.set({settings:message.settings});
    return {ok:true,snapshot:snap()};
  }},tabs:{async query(){return [{id:1,url:'https://www.youtube.com/watch?v=original-demo'}];}},storage:{local:storage,onChanged:{addListener:fn=>changes.add(fn),removeListener:fn=>changes.delete(fn)}}};
  const ready=()=>{
    if(document.documentElement.lang!==data.language||document.querySelector('#phase')?.dataset.state!==state.phase||document.querySelector('#session-button')?.disabled)return;
    observer.disconnect();document.documentElement.dataset.ready='true';
    parent.postMessage({type:'promo-ready',surface:'popup'},location.origin);
  };
  const observer=new MutationObserver(ready);observer.observe(document.documentElement,{subtree:true,childList:true,attributes:true});
  addEventListener('DOMContentLoaded',ready);
}

function playerClient(data) {
  const listeners=[];
  const layout=document.createElement('style');layout.textContent='#movie_player{height:100vh;aspect-ratio:auto}svg{height:100%}';document.head.append(layout);
  // A keyframe is deliberately frozen: screenshot delays cannot consume its cue.
  // This clock belongs only to this local fixture, never the shipped extension.
  window.setTimeout=()=>0;window.clearTimeout=()=>{};
  Object.defineProperty(performance,'now',{value:()=>0});
  Object.defineProperty(document,'hidden',{get:()=>false});
  window.chrome={runtime:{id:'promo',onMessage:{addListener:fn=>listeners.push(fn)},sendMessage:async()=>({ok:true})},storage:{local:{get:async()=>({uiLanguage:data.language})},onChanged:{addListener(){},removeListener(){}}}};
  function emit(message){for(const fn of listeners)fn({target:'content',...message},{id:'promo'},()=>{});}
  addEventListener('DOMContentLoaded',()=>{
    if(data.running){
      emit({type:'CONTENT_START',sessionId:'promo',settings:data.settings});
      emit({type:'CONTENT_STATUS',sessionId:'promo',status:{key:data.replay.kind==='recorded'?'statusConnected':'statusMock'}});
      if(data.time<3||data.time>=12){const cue=data.replay.cues[data.time<18?0:1];emit({type:'CONTENT_SUBTITLE',subtitle:{...cue,session_id:'promo'}});}
    }
    requestAnimationFrame(()=>requestAnimationFrame(()=>{document.documentElement.dataset.ready='true';parent.postMessage({type:'promo-ready',surface:'player'},location.origin);}));
  });
}

function pageClient(data) {
  // Reserve a stable disclosure area below both built UI surfaces.
  const layout=document.createElement('style');layout.textContent='.description{min-height:52px}.player{height:400px}.popup{height:592px}';document.head.append(layout);
  document.querySelector('.download a').href='https://github.com/michael-chow-arch/StreamLingo';
  const ready=new Set();
  const checkReady=()=>{
    for(const surface of ['player','popup'])if(document.querySelector(`#${surface}-frame`)?.contentDocument?.documentElement.dataset.ready==='true')ready.add(surface);
    if(ready.size===2){document.documentElement.dataset.ready='true';document.querySelector('#capture-status').textContent=`${data.frame}/59 · ready`;}
  };
  addEventListener('message',event=>{
    if(event.origin!==location.origin||event.data?.type!=='promo-ready')return;
    const frame=document.querySelector(`#${event.data.surface}-frame`);
    if(!frame||event.source!==frame.contentWindow)return;
    ready.add(event.data.surface);
    checkReady();
  });
  for(const frame of document.querySelectorAll('iframe'))frame.addEventListener('load',checkReady);
  checkReady();
  // Optional continuous preview reloads at the 11 keyframe boundaries. Recording
  // uses fixed URLs instead, so a slow screenshot tool cannot change timing.
  const params=new URLSearchParams(location.search);
  if(params.get('play')==='1'){
    const next=data.keyframes.find(frame=>frame>data.frame);
    if(next!==undefined)setTimeout(()=>{location.href=`/?lang=${data.language}&frame=${next}&play=1`;},(next-data.frame)*500);
  }
}

function captureClient() {
  const form=document.querySelector('form');
  form.addEventListener('submit',async event=>{
    event.preventDefault();const status=document.querySelector('#save-status'),button=form.querySelector('button');
    button.disabled=true;status.textContent='Saving locally…';
    try{
      const response=await fetch('/capture',{method:'POST',body:new URLSearchParams(new FormData(form))});
      const result=await response.json();if(!response.ok)throw new Error(result.error||'Save failed');
      status.textContent=`Saved: ${result.file} (${result.bytes} bytes)`;form.elements.data.value='';
    }catch(error){status.textContent=`Not saved: ${error.message}`;}finally{button.disabled=false;}
  });
}

const script = (fn,data) => `(${fn.toString()})(${JSON.stringify(data)});`;
const html = value => String(value).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');

async function garden(language) {
  const source=await readFile(resolve(ROOT,'scripts/demo-preview.mjs'),'utf8');
  const svg=source.match(/const scene = `(<svg[\s\S]+?<\/svg>)`;/)?.[1];
  if(!svg)throw new Error('Original garden scene not found in demo-preview.mjs');
  let index=0;
  return svg.replace(/(<text\b[^>]*>)[\s\S]*?(<\/text>)/g,(_match,open,close)=>`${open}${html(copy[language].garden[index++])}${close}`);
}

function page(data) {
  const {text,language,frame,stage}=data;
  const query=new URLSearchParams({lang:language,frame:String(frame)});
  const previous=KEYFRAMES.filter(value=>value<frame).at(-1)??0;
  const next=KEYFRAMES.find(value=>value>frame)??59;
  const ending=stage===10;
  return `<!doctype html><html lang="${language}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>StreamLingo · ${html(text.demo)}</title><style>
  :root{color-scheme:light;--ink:#132642;--muted:#48627e;--brand:#2563eb;--border:#cbdbea;--surface:#eef4fb}*{box-sizing:border-box}html{scrollbar-width:none}body{margin:0;background:var(--surface);color:var(--ink);font:16px/1.5 'Segoe UI','Microsoft YaHei',sans-serif}.stage{width:1280px;height:800px;padding:24px 40px;position:relative;overflow:hidden}.top{height:66px;display:flex;align-items:center;gap:14px}.logo{width:54px;height:54px}h1{font-size:28px;letter-spacing:-.5px;margin:0}.tag{font-size:15px;color:var(--muted);margin:0}.demo{margin-left:auto;text-align:right;font-size:13px;font-weight:650;color:#315778}.layout{display:grid;grid-template-columns:1fr 382px;gap:26px;margin-top:20px}.story{min-width:0}.step{font-size:13px;text-transform:uppercase;letter-spacing:1px;color:#23549b;font-weight:650;margin:0 0 8px}h2{font-size:34px;line-height:1.2;letter-spacing:-.7px;margin:0;height:48px;display:flex;align-items:center}.description{color:var(--muted);margin:6px 0 12px;min-height:26px;max-width:730px;font-size:17px}iframe{border:0;display:block;width:100%}.player{height:434px;border-radius:16px;box-shadow:0 12px 28px #17384d15}.popup{height:604px;background:#f8fafc;border:1px solid var(--border);border-radius:16px;box-shadow:0 12px 28px #17384d15}.caption{font-size:12px;margin:6px 0;color:var(--muted)}.features{display:flex;gap:10px;margin-top:13px}.features span{border:1px solid var(--border);background:#fff;border-radius:7px;font-size:13px;padding:6px 10px}.footer{position:absolute;left:40px;right:40px;bottom:19px;display:flex;align-items:flex-end;gap:20px;border-top:1px solid var(--border);padding-top:10px;font-size:12px;color:#3e5873}.disclosure{font-weight:650}.requirements{max-width:670px;margin:2px 0 0}.mode{margin-left:auto;text-align:right;white-space:nowrap}.progress{position:absolute;left:0;bottom:0;height:5px;background:var(--brand);width:${(frame+1)/60*100}%}.download{display:${ending?'block':'none'};position:absolute;left:66px;top:392px;width:742px;border:1px solid #bad0e9;border-radius:18px;background:#f8fbfff5;box-shadow:0 14px 32px #17384d20;padding:28px}.download a{display:inline-flex;align-items:center;min-height:46px;padding:10px 18px;background:var(--brand);color:white;border-radius:8px;text-decoration:none;font-weight:650}.repo{font-size:19px;margin:17px 0 0;overflow-wrap:anywhere}.download small{color:var(--muted)}.controls{margin:25px 40px 40px;max-width:1200px}.controls a{display:inline-block;min-height:44px;padding:10px 14px;margin:4px;border:1px solid var(--border);border-radius:6px;color:#1e4f97;background:white;text-decoration:none}a:focus-visible{outline:3px solid #d97706;outline-offset:3px}a:hover{filter:brightness(.96)}.keyframes{font-size:14px}.keyframes a[aria-current="true"]{background:#dbeafe;font-weight:700}
  </style><script src="/page.js?${query}" defer></script></head><body><main class="stage" id="promo-frame" data-frame="${frame}"><header class="top"><img class="logo" src="/icon128.png" alt=""><div><h1>StreamLingo</h1><p class="tag">${html(text.tag)}</p></div><div class="demo">${html(text.demo)}<br>${html(text[data.replay.kind])}</div></header><div class="layout"><section class="story"><p class="step">0${Math.min(5,Math.floor(stage/2)+1)} / 05 · ${html(text.mode)}</p><h2>${html(text.titles[stage])}</h2><p class="description">${html(text.descriptions[stage])}</p><iframe id="player-frame" class="player" title="${html(text.player)}" src="/player?${query}"></iframe><div class="features">${text.chips.map(value=>`<span>${html(value)}</span>`).join('')}</div></section><aside><iframe id="popup-frame" class="popup" title="${html(text.popup)}" src="/popup?${query}"></iframe><p class="caption">${html(text.popup)}</p></aside></div><div class="download"><a href="https://github.com/michael-chow-arch/StreamLingo/releases">${html(text.download)}</a><p class="repo">github.com/michael-chow-arch/StreamLingo</p><small>${html(text.prerequisites)}</small></div><footer class="footer"><div><span class="disclosure">${html(text.replay)}</span><p class="requirements">${html(text.prerequisites)}</p></div><div class="mode">StreamLingo v0.2.0 ${html(text.preview)}<br>${html(text.mode)}</div></footer><div class="progress"></div></main><nav class="controls" aria-label="${html(text.frame)}"><strong>${html(text.frame)}</strong><span id="capture-status"> ${frame}/59 · loading</span><p><a href="/?lang=${language}&frame=${previous}">${html(text.previous)}</a><a href="/?lang=${language}&frame=${next}">${html(text.next)}</a><a href="/?lang=${language}&frame=0&play=1">${html(text.play)}</a><a href="/capture?${query}">${html(text.capture)}</a></p><div class="keyframes">${KEYFRAMES.map(value=>`<a href="/?lang=${language}&frame=${value}" aria-current="${value===frame}">${String(value).padStart(5,'0')} · ${value/FPS}s</a>`).join('')}</div></nav></body></html>`;
}

function capturePage(search) {
  const {language,frame}=frameOptions(search);
  return `<!doctype html><html lang="en"><meta charset="utf-8"><title>Save promo frames locally</title><style>body{font:16px/1.5 system-ui;max-width:880px;margin:36px auto;padding:0 20px}label{display:block;margin:15px 0}input,select,button{font:inherit;min-height:44px}textarea{display:block;width:100%;height:190px}#save-status{white-space:pre-wrap;overflow-wrap:anywhere}</style><h1>Save original browser JPEG frames</h1><p>Local only. No upload. Capture the 1280 × 800 <code>#promo-frame</code> region. Use the original JPEG bytes; do not rename PNG data to JPEG.</p><form method="post" action="/capture"><label>Save kind <select name="kind"><option value="frame">Video frame</option><option value="evidence">Actual acceptance evidence</option></select></label><label>Language <select name="lang">${LOCALES.map(value=>`<option${value===language?' selected':''}>${value}</option>`).join('')}</select></label><label>Frame number (0–59) <input name="frame" type="number" min="0" max="59" step="1" value="${frame}" required></label><label>Evidence filename (used only for evidence) <select name="name">${[...EVIDENCE].map(value=>`<option>${value}</option>`).join('')}</select></label><label>Original JPEG base64<textarea name="data" aria-label="Original JPEG base64" required></textarea></label><button>Save locally</button></form><p id="save-status" role="status" aria-live="polite"></p><p>Keyframes: ${KEYFRAMES.join(', ')}. Each video holds these 11 captures for exactly 30 seconds.</p><a href="/?lang=${language}&frame=${frame}">Return to frozen preview</a><script src="/capture.js"></script></html>`;
}

export function jpegSize(bytes) {
  if(bytes.length<4||bytes[0]!==255||bytes[1]!==216||bytes.at(-2)!==255||bytes.at(-1)!==217)return null;
  let offset=2;
  while(offset+4<=bytes.length){
    if(bytes[offset++]!==255)return null;
    while(bytes[offset]===255)offset++;
    const marker=bytes[offset++];
    if(marker===217||marker===218)return null;
    if(marker===1||(marker>=208&&marker<=215))continue;
    const length=bytes.readUInt16BE(offset);
    if(length<2||offset+length>bytes.length)return null;
    if([192,193,194,195,197,198,199,201,202,203,205,206,207].includes(marker)){
      if(length<8)return null;
      return {width:bytes.readUInt16BE(offset+5),height:bytes.readUInt16BE(offset+3)};
    }
    offset+=length;
  }
  return null;
}

export function captureTarget(form) {
  if(form.get('kind')==='evidence')return EVIDENCE.has(form.get('name'))?`evidence/${form.get('name')}`:null;
  if(form.get('kind')!=='frame'||!LOCALES.includes(form.get('lang'))||! /^(?:0|[1-5]?\d)$/.test(form.get('frame')??''))return null;
  return `${form.get('lang')}/frame-${String(Number(form.get('frame'))).padStart(5,'0')}.jpg`;
}

export function createPromoServer() {
  return createServer(async(req,res)=>{
    const json=(status,value)=>{res.writeHead(status,{'Content-Type':'application/json; charset=utf-8'});res.end(JSON.stringify(value));};
    try{
      res.setHeader('Cache-Control','no-store');res.setHeader('X-Content-Type-Options','nosniff');
      // Loopback binding plus a fixed Host guards DNS rebinding; POST additionally
      // requires an exact same origin. No arbitrary output paths are accepted.
      if(req.headers.host!=='127.0.0.1:8900'){json(403,{error:'Use http://127.0.0.1:8900'});return;}
      const url=new URL(req.url,ORIGIN),path=url.pathname;
      if(req.method==='POST'&&path==='/capture'){
        if(req.headers.origin!==ORIGIN){json(403,{error:'Same-origin local capture only'});return;}
        if(!String(req.headers['content-type']).startsWith('application/x-www-form-urlencoded')){json(415,{error:'Expected form data'});return;}
        const chunks=[];let total=0;
        for await(const chunk of req){total+=chunk.length;if(total>MAX_BODY){json(413,{error:'Capture exceeds 8 MiB request limit'});return;}chunks.push(chunk);}
        const form=new URLSearchParams(Buffer.concat(chunks).toString('utf8')),target=captureTarget(form);
        if(!target){json(400,{error:'Invalid locale, frame number or evidence filename'});return;}
        const encoded=(form.get('data')??'').trim().replace(/^data:image\/jpeg;base64,/, '').replace(/\s/g,'');
        if(!/^[A-Za-z0-9+/]+={0,2}$/.test(encoded)||encoded.length%4!==0){json(400,{error:'Invalid JPEG base64'});return;}
        const bytes=Buffer.from(encoded,'base64'),size=jpegSize(bytes);
        if(!size){json(400,{error:'Expected complete original JPEG bytes'});return;}
        if(form.get('kind')==='frame'&&(size.width!==1280||size.height!==800)){json(400,{error:`Expected 1280 x 800 video frame; received ${size.width} x ${size.height}`});return;}
        const file=resolve(ROOT,'output/promo-video',target);await mkdir(resolve(file,'..'),{recursive:true});await writeFile(file,bytes);
        json(200,{file:`output/promo-video/${target}`,bytes:bytes.length,...size});return;
      }
      if(req.method!=='GET'){json(405,{error:'Method not allowed'});return;}
      const respond=(type,body)=>{res.setHeader('Content-Type',type);res.end(body);};
      if(path==='/capture'){respond('text/html; charset=utf-8',capturePage(url.search));return;}
      if(path==='/capture.js'){respond('text/javascript; charset=utf-8',script(captureClient));return;}
      if(['/','/page.js','/player','/player-shim.js','/popup','/popup-shim.js','/plan.json'].includes(path)){
        const data=await config(url.search),query=new URLSearchParams({lang:data.language,frame:String(data.frame)});
        if(path==='/'){respond('text/html; charset=utf-8',page(data));return;}
        if(path==='/page.js'){respond('text/javascript; charset=utf-8',script(pageClient,{...data,keyframes:KEYFRAMES}));return;}
        if(path==='/player-shim.js'){respond('text/javascript; charset=utf-8',script(playerClient,data));return;}
        if(path==='/popup-shim.js'){respond('text/javascript; charset=utf-8',script(popupClient,data));return;}
        if(path==='/player'){respond('text/html; charset=utf-8',`<!doctype html><html lang="${data.language}"><meta charset="utf-8"><style>body{margin:0;background:#162e4d}#movie_player{position:relative;width:100%;aspect-ratio:760/440;overflow:hidden}svg{display:block;width:100%}</style><div id="movie_player">${await garden(data.language)}</div><script src="/player-shim.js?${query}"></script><script src="/content.js"></script></html>`);return;}
        if(path==='/popup'){let body=await readFile(resolve(BUILT,'popup.html'),'utf8');body=body.replace('<head>',`<head><script src="/popup-shim.js?${query}"></script>${data.stage===3?'<style>#session-button{outline:4px solid #d97706;outline-offset:3px}</style>':''}`);respond('text/html; charset=utf-8',body);return;}
        json(200,{language:data.language,duration:DURATION,fps:FPS,width:1280,height:800,replay:data.replay.kind,source:data.replay.source,segments:data.replay.segments,frames:KEYFRAMES.map((frame,index)=>({frame,time:frame/FPS,duration:((KEYFRAMES[index+1]??60)-frame)/FPS,file:`frame-${String(frame).padStart(5,'0')}.jpg`,url:`${ORIGIN}/?lang=${data.language}&frame=${frame}`}))});return;
      }
      const files={'/popup.css':['popup.css','text/css'],'/popup.js':['popup.js','text/javascript'],'/content.js':['content.js','text/javascript'],'/icon128.png':['icons/icon128.png','image/png']};
      const file=files[path];if(!file){json(404,{error:'Not found'});return;}
      respond(file[1],await readFile(resolve(BUILT,file[0])));
    }catch(error){console.error(error);if(!res.headersSent)json(500,{error:'Build output or replay data is not ready'});else res.end();}
  });
}

if(process.argv[1]&&resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  createPromoServer().listen(8900,'127.0.0.1',()=>console.log(`Local promo: ${ORIGIN}/?lang=en&frame=0\nChinese: ${ORIGIN}/?lang=zh-CN&frame=0\nCapture: ${ORIGIN}/capture\n11 frozen keyframes per 30-second video; no live inference or audio.`));
}
