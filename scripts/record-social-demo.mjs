// Native, user-selected Chrome tab recording. No simulated UI or subtitles.
// Start: node scripts/record-social-demo.mjs -> http://127.0.0.1:8901/
import { createServer } from 'node:http';
import { mkdir, open, stat, unlink } from 'node:fs/promises';
import { createReadStream } from 'node:fs';
import { pipeline } from 'node:stream/promises';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT=fileURLToPath(new URL('../',import.meta.url));
const DIRECTORY=resolve(ROOT,'output/social-video/capture');
const ORIGIN='http://127.0.0.1:8901';
const MAX_BYTES=96*1024*1024;
const MIME='video/webm';
const words={
  en:{
    title:'Record real YouTube usage',subtitle:'Native Chrome tab recording · Saved only on this computer',
    instructions:'Open your YouTube livestream with the real StreamLingo extension. Select that Chrome tab below and enable “Share tab audio” in Chrome’s picker. This page cannot preselect or verify the tab’s URL.',
    scope:'Records the selected tab’s actual picture, audio and live subtitles. Browser toolbar / extension popup are outside a tab recording. No sample subtitles, microphone or system-audio capture is added.',
    choose:'1. Select YouTube tab',start:'2. Start recording',stop:'Stop & save',release:'Release selected tab',retry:'Retry local save',discard:'Discard unsaved preview',
    duration:'Recording length',seconds:'seconds',locale:'Filename language label',take:'Take number (01–99)',audio:'Require shared tab audio',
    hint:'Selection does not start recording. After “Ready”, click Start recording, then switch to YouTube and use the extension naturally. Keep this helper tab open; hiding it does not stop capture.',
    target:'Requests up to 1920 × 1080 at 30 fps. Actual capture settings are shown after selection; a smaller source tab is not presented as native 1080p.',
    idle:'Select a tab to prepare recording.',picking:'Choose the YouTube tab in Chrome’s native sharing picker…',ready:'Ready — selected tab is shared; recording has not started.',
    recording:'Recording',saving:'Recording stopped. Saving locally…',saved:'Saved on this computer',saveFailed:'Local save failed. The preview is retained: retry or download the original WebM.',
    noAudio:'No audio track was shared. Select the YouTube tab again and enable “Share tab audio”, or explicitly turn off the audio requirement.',
    wrongSurface:'Select a Chrome tab, not a window or entire screen. The selected stream was released.',
    noVideo:'Chrome returned no live video track.',focus:'Click this helper page first, then use the selection button.',unsupported:'This browser does not expose getDisplayMedia and MediaRecorder. Open the page in Chrome.',
    denied:'Sharing was cancelled or denied. Nothing was recorded.',ended:'The shared video ended.',limit:'Recording reached the local size limit and was stopped.',
    download:'Download original WebM',preview:'Local preview (muted initially)',none:'None',yes:'Yes',no:'No',surface:'Surface',resolution:'Resolution',fps:'Reported frame rate',tracks:'Audio tracks',
    unsaved:'Save or download this recording before starting another. Discard only if you no longer need the preview.',
    durationActual:'Elapsed recording time',localPath:'Files: output/social-video/capture/youtube-<language>-take-<number>.webm. Existing files are never overwritten.',
    privacy:'Only an explicit click opens the native sharing picker. Each selection requires Chrome’s permission. Record only the intended YouTube tab; the recording is uploaded to this loopback service, not an external service.',
  },
  'zh-CN':{
    title:'录制真实 YouTube 使用过程',subtitle:'Chrome 原生标签页录屏 · 仅保存到本机',
    instructions:'先打开 YouTube 直播并使用真实 StreamLingo 扩展。点击下方按钮，在 Chrome 原生选择器中选择该标签，并勾选“分享标签页音频”。本页无法预选或核验被选标签的网址。',
    scope:'录下所选标签真实的画面、声音和翻译字幕。Chrome 工具栏及扩展弹窗不属于标签页画面；本页不添加样例字幕，也不采集麦克风或系统声音。',
    choose:'1. 选择 YouTube 标签',start:'2. 开始录制',stop:'停止并保存',release:'释放所选标签',retry:'重试本地保存',discard:'丢弃未保存的预览',
    duration:'录制时长',seconds:'秒',locale:'文件语言标记',take:'录制编号（01–99）',audio:'必须包含共享标签页音频',
    hint:'选择共享画面后暂不录制。显示“就绪”后再点开始，切回 YouTube 自然操作扩展。保持本辅助页打开；切到其他标签不会让本页停止录制。',
    target:'请求最高 1920 × 1080、30 fps；选取后显示真实采集参数。源标签尺寸较小时，不将其当作原生 1080p。',
    idle:'先选择标签，准备录制。',picking:'请在 Chrome 原生共享选择器中选择 YouTube 标签…',ready:'已就绪：标签页正在共享，尚未开始录制。',
    recording:'正在录制',saving:'录制已停止，正在保存到本机…',saved:'已保存到本机',saveFailed:'本地保存失败，已保留预览，可重试或下载原始 WebM。',
    noAudio:'没有共享音轨。请重新选择 YouTube 标签并勾选“分享标签页音频”，或明确取消本页的音频要求。',
    wrongSurface:'请选择 Chrome 标签页，不要选择窗口或整个屏幕。已释放刚才选取的画面。',
    noVideo:'Chrome 没有返回可用的视频轨道。',focus:'请先点击本辅助页面，再点击选择标签按钮。',unsupported:'此浏览器未提供 getDisplayMedia 与 MediaRecorder，请用 Chrome 打开。',
    denied:'已取消或拒绝共享，没有开始录制。',ended:'共享视频已结束。',limit:'已达到本地文件大小限制，录制已停止。',
    download:'下载原始 WebM',preview:'本地预览（初始静音）',none:'无',yes:'有',no:'无',surface:'共享类型',resolution:'分辨率',fps:'报告帧率',tracks:'音轨数量',
    unsaved:'开始下一次之前，请保存或下载本次录像；不再需要时可丢弃预览。',
    durationActual:'实际经过录制时间',localPath:'文件：output/social-video/capture/youtube-<语言>-take-<编号>.webm；不会覆盖已有文件。',
    privacy:'只有明确点击按钮才会打开原生共享选择器；每次选择均需 Chrome 授权。仅选择计划录制的 YouTube 标签；录像只上传到本机回环服务，不发送到外部服务。',
  },
};

function recorderPageClient({text,language,maxBytes}){
  const element=id=>document.getElementById(id);
  const choose=element('choose'),start=element('start'),stop=element('stop'),release=element('release'),retry=element('retry'),discard=element('discard');
  const duration=element('duration'),locale=element('locale'),take=element('take'),audio=element('audio');
  const status=element('status'),details=element('details'),progress=element('progress'),preview=element('preview'),download=element('download'),result=element('result');
  let stream=null,recorder=null,busy=false,selecting=false,blob=null,objectUrl=null,saved=true;
  let chunks=[],bytes=0,startedAt=0,elapsed=0,stopTimer=null,tickTimer=null,requestedSeconds=30,selectedSettings=null,recordingAudio=false,stopReason='';
  const fields=[duration,locale,take,audio];
  const recording=()=>recorder?.state==='recording';
  function update(){
    const active=recording(),unsaved=blob&&!saved;
    choose.disabled=busy||selecting||active||Boolean(unsaved);
    start.disabled=busy||selecting||active||!stream||Boolean(unsaved);
    stop.disabled=!active;release.disabled=!stream||active||busy||selecting;
    retry.hidden=!unsaved;retry.disabled=busy;
    discard.hidden=!unsaved;discard.disabled=busy;
    for(const field of fields)field.disabled=active||busy||selecting;
    document.documentElement.dataset.state=active?'recording':busy?'saving':selecting?'selecting':stream?'ready':blob?'finished':'idle';
  }
  function message(value,error=false){status.textContent=value;status.dataset.error=String(error);}
  function stopTracks(){for(const track of stream?.getTracks()??[])track.stop();stream=null;update();}
  function clearTimers(){clearTimeout(stopTimer);clearInterval(tickTimer);stopTimer=null;tickTimer=null;}
  function filename(){return `youtube-${locale.value}-take-${String(take.valueAsNumber).padStart(2,'0')}.webm`;}
  function validName(){return ['en','zh-CN'].includes(locale.value)&&Number.isInteger(take.valueAsNumber)&&take.valueAsNumber>=1&&take.valueAsNumber<=99;}
  function tick(){
    elapsed=(performance.now()-startedAt)/1000;
    progress.value=Math.min(requestedSeconds,elapsed);
    element('timer').textContent=`${Math.min(requestedSeconds,elapsed).toFixed(1)} / ${requestedSeconds} ${text.seconds}`;
    if(elapsed>=requestedSeconds)finish();
  }
  function finish(reason=''){
    if(!recording())return;
    stopReason=reason;elapsed=(performance.now()-startedAt)/1000;clearTimers();busy=true;update();message(text.saving);
    recorder.stop();
    // MediaRecorder's final dataavailable/stop events still deliver after tracks
    // are released. Release immediately; never capture during the local upload.
    stopTracks();
  }
  async function upload(){
    if(!blob||busy)return;
    if(!validName()){message('Invalid filename language/take.',true);return;}
    busy=true;update();message(text.saving);
    const query=new URLSearchParams({lang:locale.value,take:String(take.valueAsNumber),seconds:String(elapsed.toFixed(3)),width:String(selectedSettings?.width??0),height:String(selectedSettings?.height??0),fps:String(selectedSettings?.frameRate??0),audio:String(recordingAudio)});
    try{
      const response=await fetch('/upload?'+query,{method:'POST',headers:{'Content-Type':'video/webm'},body:blob});
      const answer=await response.json();if(!response.ok)throw new Error(answer.error||`HTTP ${response.status}`);
      saved=true;message(`${text.saved}: ${answer.file}${stopReason?' · '+stopReason:''}`);
      result.textContent=`${answer.file}\n${(blob.size/1024/1024).toFixed(1)} MiB · ${text.durationActual}: ${elapsed.toFixed(2)} ${text.seconds}`;
      const link=document.createElement('a');link.href='/recording?lang='+locale.value+'&take='+take.value;link.textContent=text.download;link.download=filename();result.append(document.createElement('br'),link);
    }catch(error){message(`${text.saveFailed}\n${error.message}`,true);}finally{busy=false;update();}
  }
  choose.addEventListener('click',async()=>{
    if(!navigator.mediaDevices?.getDisplayMedia||!window.MediaRecorder){message(text.unsupported,true);return;}
    if(!document.hasFocus()){message(text.focus,true);return;}
    if(!validName()){message('Invalid filename language/take.',true);return;}
    stopTracks();selecting=true;update();message(text.picking);
    try{
      // Must remain in this real click handler: no automated selection, hidden
      // chooser, persistent permission or remote browser-control workaround.
      const options={video:{displaySurface:'browser',width:{ideal:1920,max:1920},height:{ideal:1080,max:1080},frameRate:{ideal:30,max:30}},audio:audio.checked?{suppressLocalAudioPlayback:false}:false,selfBrowserSurface:'exclude',preferCurrentTab:false,monitorTypeSurfaces:'exclude',systemAudio:'exclude',surfaceSwitching:'exclude'};
      if(window.CaptureController){options.controller=new CaptureController();options.controller.setFocusBehavior('no-focus-change');}
      stream=await navigator.mediaDevices.getDisplayMedia(options);
      const video=stream.getVideoTracks()[0];
      if(!video||video.readyState!=='live')throw new Error(text.noVideo);
      selectedSettings=video.getSettings();
      if(selectedSettings.displaySurface!=='browser')throw new Error(text.wrongSurface);
      if(audio.checked&&!stream.getAudioTracks().some(track=>track.readyState==='live'))throw new Error(text.noAudio);
      const surface=language==='en'?'Chrome tab':'Chrome 标签页';
      details.textContent=`${text.surface}: ${surface}\n${text.resolution}: ${selectedSettings.width??'?'} × ${selectedSettings.height??'?'}\n${text.fps}: ${selectedSettings.frameRate??'?'} fps\n${text.tracks}: ${stream.getAudioTracks().length}`;
      video.addEventListener('ended',()=>{if(recording())finish(text.ended);else{stopTracks();message(text.ended);}});
      message(text.ready);element('timer').textContent='0.0';progress.value=0;
    }catch(error){stopTracks();message(error.name==='NotAllowedError'?text.denied:error.message,true);}finally{selecting=false;update();}
  });
  start.addEventListener('click',()=>{
    if(!stream||busy||recording())return;
    if(audio.checked&&!stream.getAudioTracks().some(track=>track.readyState==='live')){message(text.noAudio,true);return;}
    try{
      const withAudio=stream.getAudioTracks().length>0;
      const candidates=withAudio?['video/webm;codecs=vp8,opus','video/webm;codecs=vp9,opus','video/webm']:['video/webm;codecs=vp8','video/webm;codecs=vp9','video/webm'];
      const mimeType=candidates.find(value=>MediaRecorder.isTypeSupported(value));if(!mimeType)throw new Error('WebM recording is unavailable in this browser.');
      if(objectUrl)URL.revokeObjectURL(objectUrl);objectUrl=null;blob=null;preview.removeAttribute('src');download.hidden=true;result.textContent='';
      chunks=[];bytes=0;elapsed=0;stopReason='';requestedSeconds=Number(duration.value);recordingAudio=withAudio;
      recorder=new MediaRecorder(stream,{mimeType,videoBitsPerSecond:8_000_000,...(withAudio?{audioBitsPerSecond:128_000}:{})});
      recorder.addEventListener('dataavailable',event=>{if(!event.data.size)return;chunks.push(event.data);bytes+=event.data.size;if(bytes>maxBytes-2*1024*1024)finish(text.limit);});
      recorder.addEventListener('error',event=>{
        const reason=event.error?.message??'Recorder error';
        if(recording())finish(reason);
        else{clearTimers();stopTracks();message(reason,true);busy=false;update();}
      });
      recorder.addEventListener('stop',()=>{
        clearTimers();busy=false;
        if(!chunks.length){message('No recording data was produced.',true);update();return;}
        blob=new Blob(chunks,{type:'video/webm'});chunks=[];saved=false;objectUrl=URL.createObjectURL(blob);
        preview.src=objectUrl;preview.hidden=false;download.href=objectUrl;download.download=filename();download.hidden=false;
        if(blob.size>maxBytes){message(text.limit+' '+text.saveFailed,true);update();return;}
        void upload();
      });
      recorder.start(1000);startedAt=performance.now();progress.max=requestedSeconds;
      stopTimer=setTimeout(()=>finish(),requestedSeconds*1000);tickTimer=setInterval(tick,200);
      message(`${text.recording} · ${requestedSeconds} ${text.seconds}`);update();
    }catch(error){clearTimers();stopTracks();message(error.message,true);update();}
  });
  stop.addEventListener('click',()=>finish());
  release.addEventListener('click',()=>{stopTracks();message(text.idle);});
  retry.addEventListener('click',()=>void upload());
  discard.addEventListener('click',()=>{if(objectUrl)URL.revokeObjectURL(objectUrl);objectUrl=null;blob=null;saved=true;preview.removeAttribute('src');preview.hidden=true;download.hidden=true;result.textContent='';message(text.idle);update();});
  download.addEventListener('click',()=>{saved=true;update();});
  addEventListener('beforeunload',event=>{if(recording()||selecting||busy||(blob&&!saved)){event.preventDefault();event.returnValue='';}});
  addEventListener('pagehide',()=>{clearTimers();for(const track of stream?.getTracks()??[])track.stop();});
  // Deliberately no visibilitychange stop: the operator switches to YouTube.
  message(text.idle);update();
}

const escape=value=>String(value).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
function page(language){
  const t=words[language];
  return `<!doctype html><html lang="${language}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${escape(t.title)} · StreamLingo</title><style>:root{color-scheme:light;font:16px/1.55 system-ui,'Segoe UI','Microsoft YaHei',sans-serif;color:#132642;background:#eef4fb}*{box-sizing:border-box}body{max-width:1040px;margin:28px auto;padding:0 24px}header{display:flex;justify-content:space-between;align-items:start;gap:20px}h1{font-size:30px;line-height:1.25;margin:0}h2{font-size:18px}p{color:#405d7b}a{color:#1754a9}header a{display:inline-block;padding:10px;min-height:44px}main{background:white;border:1px solid #cfdded;border-radius:14px;padding:24px;margin-top:20px}.fields{display:flex;flex-wrap:wrap;gap:20px}label{display:flex;flex-direction:column;gap:6px;font-weight:600}.check{flex-direction:row;align-items:center;margin:18px 0;font-weight:400}input,select,button{font:inherit;min-height:44px;border:1px solid #90a8c5;border-radius:7px;padding:8px 12px;background:white;color:inherit}input[type=checkbox]{width:20px;min-height:20px;height:20px}input[type=number]{width:110px}button{cursor:pointer;font-weight:650}button:disabled{opacity:.5;cursor:default}button:hover:not(:disabled){background:#eef4fb}.primary{background:#2563eb;color:white;border-color:#2563eb}.primary:hover:not(:disabled){background:#174baf}.buttons{display:flex;flex-wrap:wrap;gap:10px;margin-top:16px}button:focus-visible,a:focus-visible,input:focus-visible,select:focus-visible{outline:3px solid #d97706;outline-offset:3px}#status{white-space:pre-wrap;font-weight:650;color:#193f70;min-height:50px}#status[data-error=true]{color:#991b1b}#details,#result{white-space:pre-wrap;overflow-wrap:anywhere;color:#334c68;background:#f4f7fb;padding:14px;border-radius:8px}#details:empty,#result:empty{display:none}progress{width:100%;height:14px;accent-color:#2563eb}#timer{font-variant-numeric:tabular-nums;font-size:24px}video{display:block;max-width:100%;width:800px;background:#0f172a;margin-top:12px}video[hidden],[hidden]{display:none!important}.hint{font-size:14px}.privacy{font-size:13px}footer{margin:20px 0 32px}</style><script src="/recorder.js?lang=${language}" defer></script></head><body><header><div><h1>${escape(t.title)}</h1><p>${escape(t.subtitle)}</p></div><nav><a href="/?lang=en">English</a><a href="/?lang=zh-CN">中文</a></nav></header><main><p>${escape(t.instructions)}</p><p class="hint">${escape(t.scope)}</p><div class="fields"><label>${escape(t.duration)}<select id="duration"><option value="30">30 ${escape(t.seconds)}</option><option value="45">45 ${escape(t.seconds)}</option></select></label><label>${escape(t.locale)}<select id="locale"><option value="en"${language==='en'?' selected':''}>en</option><option value="zh-CN"${language==='zh-CN'?' selected':''}>zh-CN</option></select></label><label>${escape(t.take)}<input id="take" type="number" value="1" min="1" max="99" step="1"></label></div><label class="check"><input id="audio" type="checkbox" checked>${escape(t.audio)}</label><div class="buttons"><button id="choose" class="primary">${escape(t.choose)}</button><button id="start" class="primary" disabled>${escape(t.start)}</button><button id="stop" disabled>${escape(t.stop)}</button><button id="release" disabled>${escape(t.release)}</button></div><p class="hint">${escape(t.hint)}</p><p class="hint">${escape(t.target)}</p><p id="status" role="status" aria-live="polite"></p><pre id="details"></pre><div id="timer">0.0</div><progress id="progress" value="0" max="30" aria-label="${escape(t.duration)}"></progress><pre id="result"></pre><div class="buttons"><button id="retry" hidden>${escape(t.retry)}</button><button id="discard" hidden>${escape(t.discard)}</button><a id="download" hidden>${escape(t.download)}</a></div><h2>${escape(t.preview)}</h2><video id="preview" controls muted playsinline hidden></video><p class="hint">${escape(t.localPath)}</p></main><footer class="privacy">${escape(t.privacy)}</footer></body></html>`;
}

export function recordingName(search){
  const query=new URLSearchParams(search),language=query.get('lang'),take=query.get('take');
  if(!['en','zh-CN'].includes(language)||! /^(?:[1-9]|[1-9]\d|0[1-9])$/.test(take??''))return null;
  return `youtube-${language}-take-${String(Number(take)).padStart(2,'0')}.webm`;
}

export function createRecordingServer(){
  return createServer(async(req,res)=>{
    const json=(status,value)=>{res.writeHead(status,{'Content-Type':'application/json; charset=utf-8'});res.end(JSON.stringify(value));};
    try{
      res.setHeader('Cache-Control','no-store');res.setHeader('X-Content-Type-Options','nosniff');
      res.setHeader('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'unsafe-inline'; media-src 'self' blob:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; connect-src 'self'");
      if(req.headers.host!=='127.0.0.1:8901'){json(403,{error:'Use the loopback recorder at http://127.0.0.1:8901'});return;}
      const url=new URL(req.url,ORIGIN),name=recordingName(url.search);
      if(req.method==='POST'&&url.pathname==='/upload'){
        if(req.headers.origin!==ORIGIN){json(403,{error:'Same-origin upload required'});return;}
        if(!name){json(400,{error:'Expected lang=en|zh-CN and take=1..99'});return;}
        if(req.headers['content-type']!==MIME){json(415,{error:'Only video/webm recordings are accepted'});return;}
        if(Number(req.headers['content-length'])>MAX_BYTES){json(413,{error:'Maximum recording size is 96 MiB'});return;}
        await mkdir(DIRECTORY,{recursive:true});const path=resolve(DIRECTORY,name);
        let file;try{file=await open(path,'wx');}catch(error){if(error.code==='EEXIST'){json(409,{error:'Take already exists. Choose another take number; existing footage is never overwritten.'});return;}throw error;}
        let total=0,header=Buffer.alloc(0),valid=false;
        try{
          for await(const chunk of req){
            total+=chunk.length;if(total>MAX_BYTES){const error=new Error('Maximum recording size is 96 MiB');error.status=413;throw error;}
            if(header.length<4)header=Buffer.concat([header,chunk]).subarray(0,4);
            if(header.length===4&&!header.equals(Buffer.from([0x1a,0x45,0xdf,0xa3]))){const error=new Error('Expected a WebM/EBML header');error.status=400;throw error;}
            await file.writeFile(chunk);
          }
          if(total<4){const error=new Error('Empty or incomplete recording');error.status=400;throw error;}
          await file.close();valid=true;
          json(200,{file:`output/social-video/capture/${name}`,bytes:total});
        }catch(error){await file.close().catch(()=>{});await unlink(path).catch(()=>{});if(!res.headersSent)json(error.status??500,{error:error.message});}
        finally{if(!valid)await file.close().catch(()=>{});}
        return;
      }
      if(req.method!=='GET'){json(405,{error:'Method not allowed'});return;}
      const language=url.searchParams.get('lang')==='en'?'en':'zh-CN';
      if(url.pathname==='/'){res.setHeader('Content-Type','text/html; charset=utf-8');res.end(page(language));return;}
      if(url.pathname==='/recorder.js'){res.setHeader('Content-Type','text/javascript; charset=utf-8');res.end(`(${recorderPageClient.toString()})(${JSON.stringify({text:words[language],language,maxBytes:MAX_BYTES})});`);return;}
      if(url.pathname==='/recording'&&name){
        const path=resolve(DIRECTORY,name);let information;
        try{information=await stat(path);}catch(error){if(error.code==='ENOENT'){json(404,{error:'Recording not found'});return;}throw error;}
        res.setHeader('Content-Type',MIME);res.setHeader('Content-Length',information.size);res.setHeader('Content-Disposition',`attachment; filename="${name}"`);
        await pipeline(createReadStream(path),res);return;
      }
      json(404,{error:'Not found'});
    }catch(error){console.error(error);if(!res.headersSent)json(500,{error:'Local recorder operation failed'});else res.end();}
  });
}

if(process.argv[1]&&resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  createRecordingServer().listen(8901,'127.0.0.1',()=>console.log(`Native tab recorder: ${ORIGIN}/?lang=zh-CN\nEnglish: ${ORIGIN}/?lang=en\nChoose a YouTube tab using Chrome's native picker, then start a 30/45-second take. No browser is launched by this server.`));
}
