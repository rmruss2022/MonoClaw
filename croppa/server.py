#!/usr/bin/env python3
"""
Croppa — AI auto-cropping for photos. Detects subjects (TensorFlow.js COCO-SSD,
in-browser, no keys) and frames them; full manual control on top.

Env: CROPPA_PORT (default 18832), CROPPA_BASE (e.g. "/crop")
"""
import os, json, hashlib, hmac, secrets, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("CROPPA_PORT", "18832"))
BASE = (os.environ.get("CROPPA_BASE", "").rstrip("/"))

# ---- optional email/password gate (enabled with CROPPA_AUTH=1 on the public instance) ----
AUTH = os.environ.get("CROPPA_AUTH") == "1"
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
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><title>Croppa · sign in</title>
<style>:root{--bg:#0b0e14;--panel:#141922;--line:#222b38;--text:#eaf0f7;--muted:#90a0b4;--accent:#6366f1}
*{box-sizing:border-box}html,body{height:100%}body{margin:0;background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;display:flex;align-items:center;justify-content:center;padding:24px}
.card{width:100%;max-width:340px;background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:26px}
h1{margin:0 0 4px;font-size:22px;font-weight:800}.sub{color:var(--muted);font-size:13px;margin-bottom:18px}
label{display:block;font-size:12px;color:var(--muted);margin:12px 0 5px;font-weight:700;text-transform:uppercase;letter-spacing:.04em}
input{width:100%;background:#0e1118;border:1px solid var(--line);border-radius:11px;color:var(--text);padding:12px;font-size:16px}
button{width:100%;margin-top:18px;background:var(--accent);color:#fff;border:0;border-radius:11px;padding:13px;font-size:15px;font-weight:700}
.err{color:#f0768a;font-size:13px;margin-top:12px;min-height:16px;text-align:center}</style></head><body>
<form class="card" onsubmit="return go(event)"><h1>Croppa</h1><div class="sub">Sign in to continue.</div>
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
<meta name="apple-mobile-web-app-title" content="Croppa"/>
<title>Croppa — AI crop</title>
<style>
  :root{--bg:#0b0e14;--panel:#141922;--panel2:#0f141c;--line:#222b38;--text:#eaf0f7;--dim:#90a0b4;--accent:#6366f1;--accent2:#8b5cf6}
  *{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
  html,body{margin:0;height:100%;background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,sans-serif}
  body{display:flex;flex-direction:column;overflow:hidden}
  header{padding:calc(env(safe-area-inset-top) + 12px) 16px 10px;display:flex;align-items:center;gap:10px}
  .logo{width:30px;height:30px;border-radius:9px;background:linear-gradient(135deg,var(--accent),var(--accent2));display:flex;align-items:center;justify-content:center}
  .logo svg{width:18px;height:18px;stroke:#fff;fill:none;stroke-width:2.2}
  h1{font-size:18px;margin:0;font-weight:700;letter-spacing:-.01em}
  #status{margin-left:auto;font-size:12px;color:var(--dim)}
  #stage{flex:1;position:relative;display:flex;align-items:center;justify-content:center;overflow:hidden;background:#07090d}
  #cv{touch-action:none;max-width:100%;max-height:100%;border-radius:8px}
  #drop{position:absolute;inset:18px;border:2px dashed var(--line);border-radius:16px;display:flex;flex-direction:column;align-items:center;justify-content:center;color:var(--dim);gap:10px;text-align:center;padding:20px}
  #drop b{color:var(--text)}
  .pill{display:inline-block;background:var(--accent);color:#fff;border-radius:11px;padding:11px 18px;font-weight:700;font-size:15px}
  .panel{background:var(--panel);border-top:1px solid var(--line);padding:10px 12px calc(env(safe-area-inset-bottom) + 12px)}
  .row{display:flex;gap:7px;overflow-x:auto;padding-bottom:8px}
  .chip{flex:0 0 auto;background:var(--panel2);border:1px solid var(--line);color:var(--dim);border-radius:10px;padding:8px 12px;font-size:13px;font-weight:600;white-space:nowrap}
  .chip.on{color:#fff;border-color:var(--accent);background:rgba(99,102,241,.18)}
  .sub{flex:0 0 auto;background:var(--panel2);border:1px solid var(--line);color:#cfe0ee;border-radius:10px;padding:8px 12px;font-size:13px;font-weight:600;white-space:nowrap}
  .sub.on{color:#fff;border-color:var(--accent2);background:rgba(139,92,246,.2)}
  .ctl{display:flex;align-items:center;gap:12px;margin-top:6px}
  .ctl label{font-size:12px;color:var(--dim);width:46px}
  input[type=range]{flex:1;accent-color:var(--accent)}
  .actions{display:flex;gap:9px;margin-top:10px}
  .actions button{flex:1;border:0;border-radius:12px;padding:13px;font-size:15px;font-weight:700}
  #auto{background:var(--panel2);border:1px solid var(--line);color:#fff}
  #dl{background:linear-gradient(135deg,var(--accent),var(--accent2));color:#fff}
  .hint{color:var(--dim);font-size:11.5px;margin-top:8px;text-align:center}
  input[type=file]{display:none}
</style></head>
<body>
<header>
  <div class="logo"><svg viewBox="0 0 24 24"><path d="M6 2v14a2 2 0 0 0 2 2h14"/><path d="M2 6h14a2 2 0 0 1 2 2v14"/></svg></div>
  <h1>Croppa</h1><div id="status">loading AI…</div>
</header>

<div id="stage">
  <canvas id="cv"></canvas>
  <div id="drop"><div style="font-size:30px">🖼️</div><div><b>Add a photo</b><br/>tap to choose — AI frames the subject</div><span class="pill">Choose photo</span></div>
</div>

<div class="panel">
  <div class="row" id="subjects"></div>
  <div class="row">
    <div class="chip on" data-ar="0">Original</div>
    <div class="chip" data-ar="1">1:1</div>
    <div class="chip" data-ar="0.8">4:5</div>
    <div class="chip" data-ar="0.75">3:4</div>
    <div class="chip" data-ar="1.7778">16:9</div>
    <div class="chip" data-ar="0.5625">9:16</div>
  </div>
  <div class="ctl"><label>Zoom</label><input type="range" id="zoom" min="0" max="100" value="60"/></div>
  <div class="actions">
    <button id="auto">✨ Auto-frame</button>
    <button id="dl">Download</button>
  </div>
  <div class="hint">Drag the photo to reposition the crop · tap a detected subject to frame it</div>
</div>
<input type="file" id="file" accept="image/*"/>

<script src="https://cdn.jsdelivr.net/npm/@tensorflow/tfjs@4.20.0/dist/tf.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/@tensorflow-models/coco-ssd@2.2.3/dist/coco-ssd.min.js"></script>
<script>
const $=s=>document.querySelector(s);
const cv=$('#cv'), ctx=cv.getContext('2d');
let img=null, nat={w:0,h:0}, disp={w:0,h:0}, S=1;
let crop=null, ar=0, dets=[], target=null, model=null;

function status(t){ $('#status').textContent=t; }
(async()=>{ try{ model=await cocoSsd.load(); status('AI ready'); }catch(e){ status('manual mode'); } })();

$('#drop').onclick=()=>$('#file').click();
$('#file').onchange=e=>{ const f=e.target.files[0]; if(f) loadImage(f); };

function loadImage(file){
  const im=new Image();
  im.onload=()=>{ img=im; nat={w:im.naturalWidth,h:im.naturalHeight}; $('#drop').style.display='none'; layout(); crop=fullCrop(); applyAR(ar,true); detect(); redraw(); };
  im.src=URL.createObjectURL(file);
}
function layout(){
  const stage=$('#stage'); const maxW=stage.clientWidth, maxH=stage.clientHeight;
  const s=Math.min(maxW/nat.w, maxH/nat.h); disp={w:Math.round(nat.w*s), h:Math.round(nat.h*s)}; S=disp.w/nat.w;
  cv.width=disp.w; cv.height=disp.h;
}
function fullCrop(){ return {x:0,y:0,w:nat.w,h:nat.h}; }
function clampCrop(c){
  c.w=Math.min(c.w,nat.w); c.h=Math.min(c.h,nat.h);
  c.x=Math.max(0,Math.min(c.x,nat.w-c.w)); c.y=Math.max(0,Math.min(c.y,nat.h-c.h));
  return c;
}
function applyAR(a, keepFull){
  ar=a;
  const cx=crop?crop.x+crop.w/2:nat.w/2, cy=crop?crop.y+crop.h/2:nat.h/2;
  let w,h;
  if(!a){ w=nat.w; h=nat.h; }            // original ratio = whole image, zoom shrinks it
  else {
    // largest rect of aspect a (=w/h) fitting in image
    if(nat.w/nat.h > a){ h=nat.h; w=h*a; } else { w=nat.w; h=w/a; }
  }
  if(keepFull){ crop={x:(nat.w-w)/2,y:(nat.h-h)/2,w,h}; }
  else { crop={x:cx-w/2,y:cy-h/2,w,h}; }
  clampCrop(crop); applyZoom();
}
function curAR(){ return ar ? ar : nat.w/nat.h; }
function applyZoom(){
  const z=+$('#zoom').value/100;                 // 0=max crop(zoom out) .. 1=tight
  const a=curAR();
  // max rect of ratio a inside image
  let maxW,maxH; if(nat.w/nat.h>a){ maxH=nat.h; maxW=maxH*a; } else { maxW=nat.w; maxH=maxW/a; }
  const minW=maxW*0.35, minH=maxH*0.35;
  const cx=crop.x+crop.w/2, cy=crop.y+crop.h/2;
  crop.w=maxW-(maxW-minW)*z; crop.h=maxH-(maxH-minH)*z;
  crop.x=cx-crop.w/2; crop.y=cy-crop.h/2; clampCrop(crop); redraw();
}
async function detect(){
  $('#subjects').innerHTML=''; dets=[]; target=null;
  if(!model) return;
  status('detecting…');
  try{ dets=await model.detect(img); }catch(e){ dets=[]; }
  status(dets.length? (dets.length+' found'):'no subjects — manual');
  dets.sort((a,b)=> (b.bbox[2]*b.bbox[3])-(a.bbox[2]*a.bbox[3]));
  dets.forEach((d,i)=>{
    const b=document.createElement('div'); b.className='sub'; b.textContent=d.class+' '+Math.round(d.score*100)+'%';
    b.onclick=()=>{ document.querySelectorAll('.sub').forEach(x=>x.classList.remove('on')); b.classList.add('on'); target=d; frame(d.bbox); };
    $('#subjects').appendChild(b);
  });
  if(dets.length){ target=dets[0]; $('#subjects').firstChild.classList.add('on'); frame(dets[0].bbox); }
}
function frame(bbox){
  // bbox=[x,y,w,h] in natural px. pad, then fit to current AR, then set zoom to a sensible tight value.
  const pad=0.18; let [x,y,w,h]=bbox;
  x-=w*pad; y-=h*pad; w*=(1+2*pad); h*=(1+2*pad);
  const a=curAR(); let cw=w, ch=h;
  if(cw/ch>a){ ch=cw/a; } else { cw=ch*a; }   // expand to AR
  let cx=x+w/2, cy=y+h/2;
  crop={x:cx-cw/2,y:cy-ch/2,w:cw,h:ch}; clampCrop(crop); redraw();
}
function redraw(){
  if(!img) return;
  ctx.clearRect(0,0,cv.width,cv.height);
  ctx.drawImage(img,0,0,disp.w,disp.h);
  const cx=crop.x*S, cy=crop.y*S, cw=crop.w*S, ch=crop.h*S;
  ctx.fillStyle='rgba(6,8,12,.62)';
  ctx.fillRect(0,0,disp.w,cy); ctx.fillRect(0,cy+ch,disp.w,disp.h-(cy+ch));
  ctx.fillRect(0,cy,cx,ch); ctx.fillRect(cx+cw,cy,disp.w-(cx+cw),ch);
  // thirds
  ctx.strokeStyle='rgba(255,255,255,.28)'; ctx.lineWidth=1;
  for(let i=1;i<3;i++){ ctx.beginPath(); ctx.moveTo(cx+cw*i/3,cy); ctx.lineTo(cx+cw*i/3,cy+ch); ctx.moveTo(cx,cy+ch*i/3); ctx.lineTo(cx+cw,cy+ch*i/3); ctx.stroke(); }
  ctx.strokeStyle='#8b5cf6'; ctx.lineWidth=2.5; ctx.strokeRect(cx,cy,cw,ch);
  // corner ticks
  ctx.strokeStyle='#fff'; ctx.lineWidth=3; const t=14;
  [[cx,cy,1,1],[cx+cw,cy,-1,1],[cx,cy+ch,1,-1],[cx+cw,cy+ch,-1,-1]].forEach(([px,py,sx,sy])=>{
    ctx.beginPath(); ctx.moveTo(px,py+sy*t); ctx.lineTo(px,py); ctx.lineTo(px+sx*t,py); ctx.stroke(); });
}
// drag to reposition
let drag=null;
cv.addEventListener('pointerdown',e=>{ drag={x:e.clientX,y:e.clientY,cx:crop.x,cy:crop.y}; cv.setPointerCapture(e.pointerId); });
cv.addEventListener('pointermove',e=>{ if(!drag)return; const dx=(e.clientX-drag.x)/S, dy=(e.clientY-drag.y)/S; crop.x=drag.cx-dx; crop.y=drag.cy-dy; clampCrop(crop); redraw(); });
cv.addEventListener('pointerup',()=>drag=null); cv.addEventListener('pointercancel',()=>drag=null);

document.querySelectorAll('.chip').forEach(c=>c.onclick=()=>{
  document.querySelectorAll('.chip').forEach(x=>x.classList.remove('on')); c.classList.add('on');
  const a=parseFloat(c.dataset.ar); if(target) { ar=a; frame(target.bbox); } else applyAR(a,false);
});
$('#zoom').oninput=applyZoom;
$('#auto').onclick=()=>{ if(dets.length){ target=dets[0]; frame(dets[0].bbox);} else applyAR(ar,true); $('#zoom').value=62; applyZoom(); };
$('#dl').onclick=()=>{
  if(!img) return;
  const ow=Math.round(crop.w), oh=Math.round(crop.h);
  const o=document.createElement('canvas'); o.width=ow; o.height=oh;
  o.getContext('2d').drawImage(img, crop.x,crop.y,crop.w,crop.h, 0,0,ow,oh);
  o.toBlob(b=>{ const a=document.createElement('a'); a.href=URL.createObjectURL(b); a.download='croppa.jpg'; a.click(); }, 'image/jpeg', 0.95);
};
window.addEventListener('resize',()=>{ if(img){ layout(); redraw(); } });
</script>
</body></html>'''

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _route(self):
        p = self.path.split('?',1)[0]
        if BASE and p.startswith(BASE): p = p[len(BASE):] or '/'
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
    print(f"Croppa on :{PORT} base='{BASE or '/'}'")
    ThreadingHTTPServer(('127.0.0.1',PORT),H).serve_forever()
