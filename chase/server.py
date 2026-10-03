#!/usr/bin/env python3
"""
Chase — AI video object tracker + follow-cam. Pick an object (e.g. a car) and it
keeps it centered/zoomed as it moves (COCO-SSD, in-browser, no keys). Great for
race footage like cars in a sand-dune race.

Env: CHASE_PORT (default 18833), CHASE_BASE (e.g. "/track")
"""
import os, json, hashlib, hmac, secrets, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("CHASE_PORT", "18833"))
BASE = (os.environ.get("CHASE_BASE", "").rstrip("/"))

# ---- optional email/password gate (enabled with CHASE_AUTH=1 on the public instance) ----
AUTH = os.environ.get("CHASE_AUTH") == "1"
USERS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "users.json")
SESS = {}; TTL = 60*60*24*30
def _users():
    try: return json.load(open(USERS))
    except Exception: return {}
def _verify(e, p):
    u = _users().get((e or "").strip().lower())
    if not u: return False
    try: return hmac.compare_digest(hashlib.pbkdf2_hmac("sha256",(p or "").encode(),bytes.fromhex(u["salt"]),200000).hex(), u["hash"])
    except Exception: return False
def _newsess(e):
    t = secrets.token_urlsafe(32); SESS[t] = (e, time.time()+TTL); return t
def _sessok(t):
    v = SESS.get(t)
    if not v: return False
    if v[1] < time.time(): SESS.pop(t, None); return False
    return True
LOGIN_PAGE = r'''<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><title>Chase · sign in</title>
<style>:root{--bg:#0b0e14;--panel:#141922;--line:#222b38;--text:#eaf0f7;--muted:#90a0b4;--accent:#f59e0b}
*{box-sizing:border-box}html,body{height:100%}body{margin:0;background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;display:flex;align-items:center;justify-content:center;padding:24px}
.card{width:100%;max-width:340px;background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:26px}
h1{margin:0 0 4px;font-size:22px;font-weight:800}.sub{color:var(--muted);font-size:13px;margin-bottom:18px}
label{display:block;font-size:12px;color:var(--muted);margin:12px 0 5px;font-weight:700;text-transform:uppercase;letter-spacing:.04em}
input{width:100%;background:#0e1118;border:1px solid var(--line);border-radius:11px;color:var(--text);padding:12px;font-size:16px}
button{width:100%;margin-top:18px;background:var(--accent);color:#1c1200;border:0;border-radius:11px;padding:13px;font-size:15px;font-weight:800}
.err{color:#f0768a;font-size:13px;margin-top:12px;min-height:16px;text-align:center}</style></head><body>
<form class="card" onsubmit="return go(event)"><h1>Chase</h1><div class="sub">Sign in to continue.</div>
<label>Email</label><input id="e" type="email" autocomplete="username" autofocus>
<label>Password</label><input id="p" type="password" autocomplete="current-password">
<button type="submit">Sign in</button><div class="err" id="err"></div></form>
<script>async function go(ev){ev.preventDefault();document.getElementById('err').textContent='';
const r=await fetch('api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:document.getElementById('e').value,password:document.getElementById('p').value})});
if(r.ok)location.reload();else document.getElementById('err').textContent='Wrong email or password.';return false;}</script></body></html>'''

PAGE = r'''<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover"/>
<meta name="theme-color" content="#0b0e14"/>
<meta name="apple-mobile-web-app-capable" content="yes"/>
<meta name="apple-mobile-web-app-title" content="Chase"/>
<title>Chase — AI follow-cam</title>
<style>
  :root{--bg:#0b0e14;--panel:#141922;--panel2:#0f141c;--line:#222b38;--text:#eaf0f7;--dim:#90a0b4;--accent:#f59e0b;--accent2:#ef4444}
  *{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
  html,body{margin:0;height:100%;background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,sans-serif}
  body{display:flex;flex-direction:column;overflow:hidden}
  header{padding:calc(env(safe-area-inset-top) + 12px) 16px 10px;display:flex;align-items:center;gap:10px}
  .logo{width:30px;height:30px;border-radius:9px;background:linear-gradient(135deg,var(--accent),var(--accent2));display:flex;align-items:center;justify-content:center}
  .logo svg{width:18px;height:18px;stroke:#fff;fill:none;stroke-width:2.2}
  h1{font-size:18px;margin:0;font-weight:700;letter-spacing:-.01em}
  #status{margin-left:auto;font-size:12px;color:var(--dim);max-width:52%;text-align:right}
  #stage{flex:1;position:relative;display:flex;align-items:center;justify-content:center;overflow:hidden;background:#07090d}
  #out{max-width:100%;max-height:100%;border-radius:8px;touch-action:none}
  #drop{position:absolute;inset:18px;border:2px dashed var(--line);border-radius:16px;display:flex;flex-direction:column;align-items:center;justify-content:center;color:var(--dim);gap:10px;text-align:center;padding:20px}
  #drop b{color:var(--text)}
  .pill{display:inline-block;background:var(--accent);color:#1c1200;border-radius:11px;padding:11px 18px;font-weight:800;font-size:15px}
  #prog{position:absolute;left:0;bottom:0;height:3px;background:var(--accent);width:0}
  .panel{background:var(--panel);border-top:1px solid var(--line);padding:10px 12px calc(env(safe-area-inset-bottom) + 12px)}
  .row{display:flex;gap:7px;overflow-x:auto;padding-bottom:8px}
  .chip{flex:0 0 auto;background:var(--panel2);border:1px solid var(--line);color:var(--dim);border-radius:10px;padding:8px 12px;font-size:13px;font-weight:600;white-space:nowrap}
  .chip.on{color:#fff;border-color:var(--accent);background:rgba(245,158,11,.18)}
  .actions{display:flex;gap:9px;margin-top:4px}
  .actions button{flex:1;border:0;border-radius:12px;padding:13px;font-size:15px;font-weight:700}
  #detect{background:var(--panel2);border:1px solid var(--line);color:#fff}
  #go{background:linear-gradient(135deg,var(--accent),var(--accent2));color:#1c1200}
  #go[disabled]{opacity:.5}
  .hint{color:var(--dim);font-size:11.5px;margin-top:8px;text-align:center}
  input[type=file]{display:none}
  video{display:none}
</style></head>
<body>
<header>
  <div class="logo"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="2.4"/><path d="M12 1v3M12 20v3M1 12h3M20 12h3"/></svg></div>
  <h1>Chase</h1><div id="status">loading AI…</div>
</header>

<div id="stage">
  <canvas id="out"></canvas>
  <div id="drop"><div style="font-size:30px">🏎️</div><div><b>Add a video</b><br/>pick an object and AI follows it</div><span class="pill">Choose video</span></div>
  <div id="prog"></div>
</div>

<div class="panel">
  <div class="row">
    <div class="chip on" data-mode="follow">🎯 Follow-cam</div>
    <div class="chip" data-mode="overlay">▢ Track box</div>
    <div style="flex:1"></div>
    <div class="chip" data-ar="0.5625">9:16</div>
    <div class="chip on" data-ar="1">1:1</div>
    <div class="chip" data-ar="1.7778">16:9</div>
  </div>
  <div class="actions">
    <button id="detect">① Detect &amp; pick</button>
    <button id="go" disabled>② Track &amp; play</button>
  </div>
  <div class="hint">Step 1: tap <b>Detect</b>, then tap the car (or object) to lock on. Step 2: <b>Track &amp; play</b> — screen-record to save.</div>
</div>
<input type="file" id="file" accept="video/*"/>
<video id="vid" muted playsinline></video>

<script src="https://cdn.jsdelivr.net/npm/@tensorflow/tfjs@4.20.0/dist/tf.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/@tensorflow-models/coco-ssd@2.2.3/dist/coco-ssd.min.js"></script>
<script>
const $=s=>document.querySelector(s);
const vid=$('#vid'), out=$('#out'), octx=out.getContext('2d');
const work=document.createElement('canvas'), wctx=work.getContext('2d');
let model=null, dets=[], target=null, mode='follow', ar=1, running=false;
let smooth=null; // smoothed follow box {cx,cy,w,h}
const CO={w:720}; // output width baseline

function status(t){ $('#status').textContent=t; }
(async()=>{ try{ model=await cocoSsd.load(); status('AI ready — add a video'); }catch(e){ status('AI failed to load'); } })();

$('#drop').onclick=()=>$('#file').click();
$('#file').onchange=e=>{ const f=e.target.files[0]; if(f) loadVideo(f); };

function loadVideo(f){
  vid.src=URL.createObjectURL(f);
  vid.onloadedmetadata=()=>{
    work.width=vid.videoWidth; work.height=vid.videoHeight;
    sizeOut(); $('#drop').style.display='none';
    vid.currentTime=Math.min(0.1, (vid.duration||1)/2);
  };
  vid.onseeked=()=>{ drawFrameToWork(); renderPreviewFull(); status('tap ① Detect & pick'); };
}
function sizeOut(){
  let w,h;
  if(mode==='follow'){ w=CO.w; h=Math.round(CO.w/ar); }
  else { const vr=vid.videoWidth/vid.videoHeight; w=Math.min(1280,vid.videoWidth); h=Math.round(w/vr); }
  out.width=w; out.height=h;
}
function drawFrameToWork(){ wctx.drawImage(vid,0,0,work.width,work.height); }
function renderPreviewFull(){
  // show the current work frame (fit) with any detection boxes
  sizeOutOverlay();
  const vr=vid.videoWidth/vid.videoHeight; octx.fillStyle='#07090d'; octx.fillRect(0,0,out.width,out.height);
  octx.drawImage(work,0,0,out.width,out.height);
  const sx=out.width/vid.videoWidth, sy=out.height/vid.videoHeight;
  dets.forEach(d=>{ const [x,y,w,h]=d.bbox;
    octx.strokeStyle=(d===target)?'#f59e0b':'rgba(255,255,255,.65)'; octx.lineWidth=(d===target)?4:2;
    octx.strokeRect(x*sx,y*sy,w*sx,h*sy);
    octx.fillStyle=octx.strokeStyle; octx.font='bold 14px -apple-system'; octx.fillText(d.class, x*sx+4, y*sy+16);
  });
}
function sizeOutOverlay(){ const vr=vid.videoWidth/vid.videoHeight; const w=Math.min(1280,vid.videoWidth); out.width=w; out.height=Math.round(w/vr); }

$('#detect').onclick=async()=>{
  if(!model){ status('AI not ready'); return; }
  vid.pause(); drawFrameToWork(); status('detecting…');
  try{ dets=await model.detect(work); }catch(e){ dets=[]; }
  target=null;
  // auto-pick the biggest vehicle if present
  const veh=dets.filter(d=>['car','truck','motorcycle','bus','bicycle'].includes(d.class)).sort((a,b)=>b.bbox[2]*b.bbox[3]-a.bbox[2]*a.bbox[3]);
  if(veh.length){ target=veh[0]; }
  status(dets.length? 'tap the object to lock on ('+dets.length+' found)':'nothing detected — try another frame');
  renderPreviewFull();
  $('#go').disabled=!target && !dets.length;
};
// tap to select a detection on the preview
out.addEventListener('pointerdown',e=>{
  if(running || !dets.length) return;
  const r=out.getBoundingClientRect(); const px=(e.clientX-r.left)/r.width*vid.videoWidth, py=(e.clientY-r.top)/r.height*vid.videoHeight;
  let best=null,ba=1e18;
  dets.forEach(d=>{ const [x,y,w,h]=d.bbox; if(px>=x&&px<=x+w&&py>=y&&py<=y+h){ const a=w*h; if(a<ba){ba=a;best=d;} } });
  if(best){ target=best; renderPreviewFull(); $('#go').disabled=false; status('locked: '+best.class+' — tap ② Track & play'); }
});

document.querySelectorAll('.chip[data-mode]').forEach(c=>c.onclick=()=>{ document.querySelectorAll('.chip[data-mode]').forEach(x=>x.classList.remove('on')); c.classList.add('on'); mode=c.dataset.mode; });
document.querySelectorAll('.chip[data-ar]').forEach(c=>c.onclick=()=>{ document.querySelectorAll('.chip[data-ar]').forEach(x=>x.classList.remove('on')); c.classList.add('on'); ar=parseFloat(c.dataset.ar); });

function iou(a,b){ const ax2=a[0]+a[2],ay2=a[1]+a[3],bx2=b[0]+b[2],by2=b[1]+b[3];
  const ix=Math.max(0,Math.min(ax2,bx2)-Math.max(a[0],b[0])), iy=Math.max(0,Math.min(ay2,by2)-Math.max(a[1],b[1]));
  const inter=ix*iy, uni=a[2]*a[3]+b[2]*b[3]-inter; return uni>0?inter/uni:0; }

$('#go').onclick=async()=>{
  if(!target){ status('pick an object first'); return; }
  running=true; $('#go').disabled=true; $('#detect').disabled=true; smooth=null;
  const cls=target.class; let last=target.bbox.slice();
  sizeOut();
  // optional recording (best-effort; iOS Safari may not support)
  let rec=null, chunks=[];
  try{ const st=out.captureStream(30); rec=new MediaRecorder(st,{mimeType:MediaRecorder.isTypeSupported('video/mp4')?'video/mp4':'video/webm'}); rec.ondataavailable=e=>e.data.size&&chunks.push(e.data); rec.start(); }catch(e){ rec=null; }
  vid.currentTime=0; await new Promise(r=>vid.onseeked=r);
  vid.onseeked=null;
  await vid.play().catch(()=>{});
  const useRVFC = 'requestVideoFrameCallback' in HTMLVideoElement.prototype;

  async function step(){
    if(vid.paused||vid.ended||!running){ finish(); return; }
    drawFrameToWork();
    let d=[]; try{ d=await model.detect(work); }catch(_){}
    // associate: same class, best by IoU then nearest center to last
    const cand=d.filter(x=>x.class===cls);
    let pick=null,score=-1;
    const lc=[last[0]+last[2]/2,last[1]+last[3]/2];
    cand.forEach(x=>{ const i=iou(last,x.bbox); const cx=x.bbox[0]+x.bbox[2]/2,cy=x.bbox[1]+x.bbox[3]/2;
      const dist=Math.hypot(cx-lc[0],cy-lc[1]); const s=i*2 - dist/ (work.width); if(s>score){score=s;pick=x;} });
    if(pick && (iou(last,pick.bbox)>0.02 || score>-0.4)) last=pick.bbox.slice();
    renderOutput(last);
    $('#prog').style.width=((vid.currentTime/vid.duration)*100)+'%';
    if(useRVFC) vid.requestVideoFrameCallback(()=>step()); else setTimeout(step,0);
  }
  function finish(){
    running=false; $('#go').disabled=false; $('#detect').disabled=false; $('#prog').style.width='0';
    if(rec){ rec.stop(); rec.onstop=()=>{ const b=new Blob(chunks,{type:chunks[0]?.type||'video/webm'});
      const a=document.createElement('a'); a.href=URL.createObjectURL(b); a.download='chase.'+(b.type.includes('mp4')?'mp4':'webm'); a.click();
      status('done — saved clip (or screen-record next time if it didn’t download)'); }; }
    else status('done — screen-record to save (your browser can’t export video)');
  }
  if(useRVFC) vid.requestVideoFrameCallback(()=>step()); else step();
  status('tracking '+cls+'…');
};

function renderOutput(box){
  if(mode==='overlay'){
    sizeOutOverlay();
    octx.drawImage(vid,0,0,out.width,out.height);
    const sx=out.width/vid.videoWidth, sy=out.height/vid.videoHeight; const [x,y,w,h]=box;
    octx.strokeStyle='#f59e0b'; octx.lineWidth=4; octx.strokeRect(x*sx,y*sy,w*sx,h*sy);
    octx.fillStyle='#f59e0b'; octx.font='bold 16px -apple-system'; octx.fillText('🎯 '+target.class, x*sx+5, Math.max(16,y*sy-6));
    return;
  }
  // follow-cam: crop window around box, chosen AR, smoothed
  const [x,y,w,h]=box; const ocx=x+w/2, ocy=y+h/2;
  let cw=Math.max(w,h)*3.2; let ch=cw/ar; // zoom factor around object
  cw=Math.min(cw, vid.videoWidth); ch=Math.min(ch, vid.videoHeight); cw=ch*ar<=vid.videoWidth?ch*ar:cw; // keep ar, clamp
  if(ch>vid.videoHeight){ ch=vid.videoHeight; cw=ch*ar; }
  if(cw>vid.videoWidth){ cw=vid.videoWidth; ch=cw/ar; }
  let t={cx:ocx,cy:ocy,w:cw,h:ch};
  if(!smooth) smooth=t; else { const k=0.18; smooth={cx:smooth.cx+(t.cx-smooth.cx)*k, cy:smooth.cy+(t.cy-smooth.cy)*k, w:smooth.w+(t.w-smooth.w)*k, h:smooth.h+(t.h-smooth.h)*k}; }
  let sx=smooth.cx-smooth.w/2, sy=smooth.cy-smooth.h/2;
  sx=Math.max(0,Math.min(sx,vid.videoWidth-smooth.w)); sy=Math.max(0,Math.min(sy,vid.videoHeight-smooth.h));
  octx.fillStyle='#000'; octx.fillRect(0,0,out.width,out.height);
  octx.drawImage(vid, sx,sy,smooth.w,smooth.h, 0,0,out.width,out.height);
}
</script>
</body></html>'''

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _route(self):
        p=self.path.split('?',1)[0]
        if BASE and p.startswith(BASE): p=p[len(BASE):] or '/'
        return p
    def _cookie(self, name):
        for part in (self.headers.get("Cookie","") or "").split(";"):
            k,_,v = part.strip().partition("=")
            if k==name: return v
        return None
    def _authed(self):
        if not AUTH: return True
        t=self._cookie("sess"); return bool(t and _sessok(t))
    def do_POST(self):
        p=self._route()
        if p=='/api/login':
            n=int(self.headers.get('Content-Length',0) or 0); raw=self.rfile.read(n) if n else b'{}'
            try: d=json.loads(raw or b'{}')
            except Exception: d={}
            if _verify(d.get('email',''), d.get('password','')):
                t=_newsess((d.get('email','') or '').strip().lower()); body=b'{"ok":true}'
                self.send_response(200); self.send_header('Content-Type','application/json')
                self.send_header('Set-Cookie', f"sess={t}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age={TTL}")
                self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body); return
            self.send_response(401); self.end_headers(); self.wfile.write(b'{"error":"invalid"}'); return
        if p=='/api/logout':
            t=self._cookie('sess');
            if t: SESS.pop(t,None)
            self.send_response(200); self.end_headers(); self.wfile.write(b'{"ok":true}'); return
        self.send_response(404); self.end_headers(); self.wfile.write(b'not found')
    def do_GET(self):
        p=self._route()
        if AUTH and not self._authed():
            if p in ('/','/index.html'):
                b=LOGIN_PAGE.encode(); self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8')
                self.send_header('Content-Length',str(len(b))); self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(b); return
            self.send_response(401); self.end_headers(); self.wfile.write(b'auth'); return
        if p in ('/','/index.html'):
            b=PAGE.encode(); self.send_response(200)
            self.send_header('Content-Type','text/html; charset=utf-8'); self.send_header('Content-Length',str(len(b)))
            self.send_header('Cache-Control','no-cache'); self.end_headers(); self.wfile.write(b)
        elif p in ('/health','/healthz'):
            self.send_response(200); self.end_headers(); self.wfile.write(b'ok')
        else:
            self.send_response(404); self.end_headers(); self.wfile.write(b'not found')

if __name__=='__main__':
    print(f"Chase on :{PORT} base='{BASE or '/'}'")
    ThreadingHTTPServer(('127.0.0.1',PORT),H).serve_forever()
