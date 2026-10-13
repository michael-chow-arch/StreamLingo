// README cover composition from a reviewed real recording frame. No fake UI.
// Source: output/social-video/capture/hero-source.png; see docs/video-production.md.
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

const root = new URL('../', import.meta.url);
const escape = value => value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('"', '&quot;');
const copy = {
  en: {
    label: 'LIVE CAPTIONS · LOCAL AI',
    headline: 'Live streams. Now in your language.',
    detail: 'AI-translated captions for YouTube. Works with your local Ollama model.',
    easy: 'Setup once. Choose a direction. Start captions.',
    modes: 'English ↔ Chinese · Auto detect',
    proof: 'REAL CHROME RECORDING',
    context: 'English → Chinese · YouTube playback demo',
    action: 'Watch the 32-second demo →',
  },
  'zh-CN': {
    label: '直播字幕 · 本地 AI',
    headline: '直播听不懂？让 AI 字幕帮你跟上。',
    detail: '直接翻译 YouTube 直播原声。支持已有的 Ollama 本地模型。',
    easy: '首次配置后，选方向，开始字幕。',
    modes: '英 ↔ 中 · 自动识别语言',
    proof: '真实 CHROME 录制',
    context: '英语 → 中文 · YouTube 回放实录',
    action: '观看 32 秒实际效果 →',
  },
};

function page(locale) {
  const t = copy[locale];
  return `<!doctype html><html lang="${locale}"><meta charset="utf-8"><title>StreamLingo · ${locale} cover</title>
<style>
*{box-sizing:border-box}html,body{margin:0;background:#091323;color:#f8fafc;font-family:'Segoe UI','Microsoft YaHei',sans-serif}#cover{position:relative;width:1600px;height:1000px;overflow:hidden;background:linear-gradient(125deg,#102445 0%,#091323 60%)}
.brand{position:absolute;left:64px;top:42px;display:flex;align-items:center;gap:16px;font-size:35px;font-weight:750}.brand img{width:52px;height:52px}.eyebrow{position:absolute;right:64px;top:60px;color:#93c5fd;font-size:20px;font-weight:650;letter-spacing:2px}
h1{position:absolute;left:64px;top:132px;margin:0;font-size:70px;line-height:1.16;font-weight:750;letter-spacing:-1.6px;white-space:nowrap}html[lang=zh-CN] h1{font-size:66px;letter-spacing:0}.detail{position:absolute;left:68px;top:230px;margin:0;font-size:28px;color:#c2d2ea}
.benefits{position:absolute;left:64px;top:290px;display:flex;gap:18px;align-items:center;font-size:23px}.easy{color:#eff6ff;background:#1d4ed8;border:1px solid #3b82f6;border-radius:10px;padding:12px 18px}.modes{padding:12px 18px;color:#c2d2ea}
.visual{position:absolute;left:64px;top:368px;width:1472px;height:520px;overflow:hidden;border:2px solid #506386;border-radius:16px;background:#101827;box-shadow:0 22px 55px #0005}.visual img{position:absolute;left:0;top:0;width:2078.12px;height:auto;max-width:none}
.proof{position:absolute;left:84px;top:916px;font-size:16px;color:#93c5fd;font-weight:700;letter-spacing:1px}.context{position:absolute;left:84px;top:944px;font-size:17px;color:#bdcbe0}.action{position:absolute;right:68px;top:916px;font-size:25px;font-weight:650;color:#eff6ff}.credit{position:absolute;right:68px;top:955px;color:#a9bbd5;font-size:15px}
</style><main id="cover" aria-label="StreamLingo ${locale} cover"><div class="brand"><img src="/logo.png" alt="">StreamLingo</div><div class="eyebrow">${escape(t.label)}</div><h1>${escape(t.headline)}</h1><p class="detail">${escape(t.detail)}</p><div class="benefits"><span class="easy">${escape(t.easy)}</span><span class="modes">${escape(t.modes)}</span></div><div class="visual"><img src="/frame.png" alt="Actual Chrome recording of StreamLingo translating English dialogue into Chinese"></div><span class="proof">${escape(t.proof)}</span><span class="context">${escape(t.context)}</span><span class="action">${escape(t.action)}</span><span class="credit">Tears of Steel / Blender Foundation / CC BY 3.0</span></main></html>`;
}

createServer(async (req, res) => {
  if (req.headers.host !== '127.0.0.1:8902') { res.writeHead(403); res.end(); return; }
  const url = new URL(req.url, 'http://127.0.0.1:8902');
  res.setHeader('Cache-Control', 'no-store');
  res.setHeader('Content-Security-Policy', "default-src 'none'; style-src 'unsafe-inline'; img-src 'self'; base-uri 'none'; frame-ancestors 'none'");
  try {
    const asset = { '/frame.png': 'output/social-video/capture/hero-source.png', '/logo.png': 'extension/icons/icon128.png' }[url.pathname];
    if (asset) { res.setHeader('Content-Type', 'image/png'); res.end(await readFile(new URL(asset, root))); return; }
    if (url.pathname !== '/') { res.writeHead(404); res.end(); return; }
    res.setHeader('Content-Type', 'text/html; charset=utf-8');
    res.end(page(url.searchParams.get('lang') === 'en' ? 'en' : 'zh-CN'));
  } catch { res.writeHead(404); res.end('Reviewed local recording frame is missing. See docs/video-production.md.'); }
}).listen(8902, '127.0.0.1', () => console.log(`Cover preview: http://127.0.0.1:8902/?lang=en\nWorkspace: ${fileURLToPath(root)}`));
