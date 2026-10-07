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

# ---- logging: request lines + a client-side diagnostic beacon land in data/croppa.log ----
LOGFILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "croppa.log")
def log_event(kind, data=None, ip=""):
    try:
        os.makedirs(os.path.dirname(LOGFILE), exist_ok=True)
        rec = {"t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "kind": kind}
        if ip: rec["ip"] = ip
        if data is not None: rec["data"] = data
        with open(LOGFILE, "a") as f:
            f.write(json.dumps(rec, default=str)[:4000] + "\n")
    except Exception:
        pass

# ---- optional email/password gate (enabled with CROPPA_AUTH=1 on the public instance) ----
AUTH = os.environ.get("CROPPA_AUTH") == "1"
USERS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "users.json")
SESS = {}; TTL = 60*60*24*30
def _users():
    try: return json.load(open(USERS))
    except Exception: return {}
def _save_users(u):
    os.makedirs(os.path.dirname(USERS), exist_ok=True)
    json.dump(u, open(USERS, "w")); os.chmod(USERS, 0o600)
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
<button type="button" onclick="sub('login')">Sign in</button>
<button type="button" onclick="sub('signup')" style="margin-top:9px;background:transparent;border:1px solid var(--line);color:var(--text)">Create account</button>
<div class="err" id="err"></div></form>
<script>
function go(ev){ev.preventDefault();sub('login');return false;}
async function sub(mode){const e=document.getElementById('e').value,p=document.getElementById('p').value,err=document.getElementById('err');err.textContent='';
 if(!e||!p){err.textContent='Enter your email and password.';return;}
 let r;try{r=await fetch('api/'+mode,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:e,password:p})});}catch(_){err.textContent='Network error.';return;}
 if(r.ok){location.reload();return;}
 let m=mode==='signup'?'Could not create account.':'Wrong email or password.';try{const j=await r.json();if(j.error)m=j.error;}catch(_){}
 err.textContent=m;}</script></body></html>'''

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
  /* ---- library / tray ---- */
  #traybar{display:none;margin-bottom:8px}
  .trayhead{display:flex;align-items:center;gap:8px;padding:0 2px 8px;font-size:12px;color:var(--dim)}
  .trayhead button{background:var(--panel2);border:1px solid var(--line);color:#cfe0ee;border-radius:9px;padding:6px 10px;font-size:12px;font-weight:700}
  #exportall{border-color:var(--accent)!important;color:#fff!important;background:rgba(99,102,241,.2)!important}
  #autoall{border-color:var(--accent2)!important;color:#fff!important;background:rgba(139,92,246,.26)!important}
  .trayhead button:disabled{opacity:.5}
  #drop.drag{border-color:var(--accent);background:rgba(99,102,241,.1);color:var(--text)}
  #tray{gap:8px}
  .thumb{position:relative;flex:0 0 auto;width:54px;height:54px;border-radius:9px;background:#0e1118 center/cover no-repeat;border:2px solid var(--line);overflow:hidden}
  .thumb.on{border-color:var(--accent);box-shadow:0 0 0 2px rgba(99,102,241,.35)}
  .thumb .dot{position:absolute;left:3px;bottom:3px;width:9px;height:9px;border-radius:50%;background:#64748b;box-shadow:0 0 0 2px rgba(0,0,0,.55)}
  .thumb.done .dot{background:#22c55e}
  .thumb .x{position:absolute;right:1px;top:1px;width:17px;height:17px;border-radius:50%;background:rgba(3,5,9,.72);color:#fff;font-size:12px;line-height:16px;text-align:center;font-weight:700}
  .thumb.add{display:flex;align-items:center;justify-content:center;color:var(--dim);font-size:26px;border-style:dashed;background:var(--panel2)}
  #save{background:var(--panel2);border:1px solid var(--accent2);color:#fff}
</style></head>
<body>
<header>
  <div class="logo"><svg viewBox="0 0 24 24"><path d="M6 2v14a2 2 0 0 0 2 2h14"/><path d="M2 6h14a2 2 0 0 1 2 2v14"/></svg></div>
  <h1>Croppa</h1><div id="status">loading AI…</div>
</header>

<div id="stage">
  <canvas id="cv"></canvas>
  <div id="drop"><div style="font-size:30px">🖼️</div><div><b>Add photos</b><br/>tap to pick, or drag a batch here — AI frames each</div><span class="pill">Choose photos</span></div>
</div>

<div class="panel">
  <div id="traybar">
    <div class="trayhead">
      <span id="traycount">0 photos</span>
      <span style="flex:1"></span>
      <button id="autoall" style="display:none">⚡ Auto-crop all</button>
      <button id="exportall" style="display:none">⬇︎ Export all</button>
      <button id="clearall">Clear</button>
    </div>
    <div class="row" id="tray"></div>
  </div>
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
    <button id="auto">✨ Auto</button>
    <button id="save">✓ Save</button>
    <button id="dl">⬇︎ Export</button>
  </div>
  <div class="hint">Drag to reposition · tap a subject to frame · <b>Save</b> adds to your library, <b>Export</b> sends to your device</div>
</div>
<input type="file" id="file" accept="image/*" multiple/>

<script src="https://cdn.jsdelivr.net/npm/@tensorflow/tfjs@4.20.0/dist/tf.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/@tensorflow-models/coco-ssd@2.2.3/dist/coco-ssd.min.js"></script>
<script>
const $=s=>document.querySelector(s);
const cv=$('#cv'), ctx=cv.getContext('2d');
let img=null, nat={w:0,h:0}, disp={w:0,h:0}, S=1;
let crop=null, ar=0, dets=[], target=null, model=null;

// ---- diagnostics: mirror key events to the server log (data/croppa.log) ----
const isIOS=/iP(hone|ad|od)/.test(navigator.userAgent)||(/Macintosh/.test(navigator.userAgent)&&'ontouchend'in document);
const standalone=(window.navigator.standalone===true)||(window.matchMedia&&matchMedia('(display-mode: standalone)').matches);
function clog(ev,data){ try{ console.log('[croppa]',ev,data||''); fetch('api/log',{method:'POST',keepalive:true,headers:{'Content-Type':'application/json'},body:JSON.stringify({ev,data:data||null,ios:isIOS,standalone})}); }catch(_){ } }
window.addEventListener('error',e=>clog('jserror',{m:String(e.message),src:e.filename,ln:e.lineno}));
window.addEventListener('unhandledrejection',e=>clog('reject',{m:String((e.reason&&e.reason.message)||e.reason)}));
clog('load',{tf:typeof tf,coco:typeof cocoSsd,w:innerWidth,h:innerHeight,share:!!(navigator.canShare)});

function status(t){ $('#status').textContent=t; }
(async()=>{ try{ model=await cocoSsd.load(); status('AI ready'); clog('model_ready'); }
  catch(e){ status('manual mode'); clog('model_fail',{m:String(e&&e.message||e)}); } })();

$('#drop').onclick=()=>$('#file').click();
$('#file').onchange=e=>{ addFiles(e.target.files); e.target.value=''; };

// ---------- Library / tray: multi-photo file management (client-side, persisted in IndexedDB) ----------
let tray=[], activeId=null, db=null, busy=false;
const CAP = isIOS?80:400;   // bound in-browser storage; desktop photographers get the bigger batch
const uid=()=> Date.now().toString(36)+Math.random().toString(36).slice(2,7);

function idb(){ return new Promise(res=>{ try{
    const r=indexedDB.open('croppa',1);
    r.onupgradeneeded=()=>{ try{ r.result.createObjectStore('items',{keyPath:'id'}); }catch(_){ } };
    r.onsuccess=()=>res(r.result); r.onerror=()=>res(null);
  }catch(_){ res(null); } }); }
function dbPut(it){ if(!db) return Promise.resolve(false);
  const rec={id:it.id,name:it.name,ts:it.ts,orig:it.orig,out:it.out,thumb:it.thumb,st:it.st,done:it.done};
  return new Promise(res=>{ try{
    const rq=db.transaction('items','readwrite').objectStore('items').put(rec);
    rq.onsuccess=()=>res(true);
    rq.onerror=()=>{ // likely quota — retry without the heavy original (keep the crop + thumb)
      try{ const rq2=db.transaction('items','readwrite').objectStore('items').put({...rec,orig:null});
        rq2.onsuccess=()=>res(true); rq2.onerror=()=>res(false); }catch(_){ res(false); } };
  }catch(_){ res(false); } }); }
function dbDel(id){ if(!db)return; try{ db.transaction('items','readwrite').objectStore('items').delete(id); }catch(_){ } }
function dbAll(){ return new Promise(res=>{ if(!db)return res([]);
  try{ const rq=db.transaction('items').objectStore('items').getAll(); rq.onsuccess=()=>res(rq.result||[]); rq.onerror=()=>res([]); }catch(_){ res([]); } }); }

function makeThumb(imEl){ try{
    const s=Math.min(120/imEl.naturalWidth,120/imEl.naturalHeight,1);
    const c=document.createElement('canvas'); c.width=Math.max(1,Math.round(imEl.naturalWidth*s)); c.height=Math.max(1,Math.round(imEl.naturalHeight*s));
    c.getContext('2d').drawImage(imEl,0,0,c.width,c.height); return c.toDataURL('image/jpeg',0.7);
  }catch(_){ return ''; } }

async function addFiles(files){
  const list=[...(files||[])].filter(f=>/^image\//.test(f.type||'')||/\.(jpe?g|png|webp|gif|heic|heif|bmp|tiff?)$/i.test(f.name||''));
  if(!list.length){ clog('pick_none'); return; }
  let firstNew=null;
  for(const f of list){
    if(tray.length>=CAP){ status('library full ('+CAP+') — export or clear'); break; }
    const it={id:uid(),name:f.name||'photo.jpg',ts:Date.now(),orig:f,out:null,thumb:'',st:null,done:false};
    try{ await new Promise(done=>{ const im=new Image(); im.onload=()=>{ it.thumb=makeThumb(im); done(); }; im.onerror=done; im.src=URL.createObjectURL(f); }); }catch(_){ }
    tray.push(it); dbPut(it); if(!firstNew) firstNew=it.id;
  }
  clog('tray_add',{added:list.length,total:tray.length});
  renderTray();
  if(firstNew && (!activeId || !img)) openItem(firstNew);
}

function renderTray(){
  const strip=$('#tray'); strip.innerHTML='';
  tray.forEach(it=>{
    const d=document.createElement('div'); d.className='thumb'+(it.done?' done':'')+(it.id===activeId?' on':'');
    if(it.thumb) d.style.backgroundImage='url('+it.thumb+')';
    d.innerHTML='<span class="dot"></span><span class="x">×</span>';
    d.addEventListener('click',e=>{ if(e.target.classList.contains('x')){ e.stopPropagation(); removeItem(it.id); } else openItem(it.id); });
    strip.appendChild(d);
  });
  const add=document.createElement('div'); add.className='thumb add'; add.textContent='+';
  add.onclick=()=>$('#file').click(); strip.appendChild(add);
  const done=tray.filter(t=>t.done).length, pend=tray.length-done;
  $('#traycount').textContent=tray.length+' photo'+(tray.length!=1?'s':'')+' · '+done+' saved';
  $('#exportall').style.display=done? '':'none';
  $('#autoall').style.display=(pend>0)? '':'none';
  $('#autoall').textContent='⚡ Auto-crop all'+(pend?(' ('+pend+')'):'');
  $('#traybar').style.display=tray.length? '':'none';
}

function removeItem(id){
  const i=tray.findIndex(t=>t.id===id); if(i<0)return;
  tray.splice(i,1); dbDel(id); clog('tray_remove',{total:tray.length});
  if(activeId===id){ activeId=null; img=null;
    const nx=tray[i]||tray[i-1]||tray[0];
    if(nx) openItem(nx.id);
    else { ctx.clearRect(0,0,cv.width,cv.height); cv.width=cv.height=0; $('#drop').style.display=''; dets=[]; $('#subjects').innerHTML=''; status(model?'AI ready':'manual mode'); }
  }
  renderTray();
}

function setARchip(a){ document.querySelectorAll('.chip').forEach(x=>x.classList.toggle('on', parseFloat(x.dataset.ar)===a)); }

function openItem(id){
  const it=tray.find(t=>t.id===id); if(!it)return; activeId=id;
  const haveOrig=!!it.orig; const blob=it.orig||it.out; const src=blob?URL.createObjectURL(blob):(it.thumb||'');
  if(!src){ renderTray(); return; }
  const im=new Image();
  im.onload=()=>{ img=im; nat={w:im.naturalWidth,h:im.naturalHeight}; $('#drop').style.display='none'; layout();
    if(!nat.w||!nat.h){ status('could not read image'); clog('image_zero',{name:it.name}); }
    if(haveOrig && it.st){ ar=it.st.ar||0; setARchip(ar); $('#zoom').value=(it.st.zoom!=null?it.st.zoom:60);
      crop={x:it.st.x,y:it.st.y,w:it.st.w,h:it.st.h}; clampCrop(crop); redraw(); detect(false); status('saved — edit & re-save'); }
    else { crop=fullCrop(); applyAR(ar,true); detect(true); }
    redraw(); clog('tray_open',{nw:nat.w,nh:nat.h,done:it.done,orig:haveOrig}); };
  im.onerror=()=>{ status('could not open that photo'); clog('image_error',{name:it.name}); };
  im.src=src;
  renderTray();
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
async function detect(autoframe){
  if(autoframe===undefined) autoframe=true;
  $('#subjects').innerHTML=''; dets=[]; target=null;
  if(!model) return;
  status('detecting…');
  try{ dets=await model.detect(img); }catch(e){ dets=[]; clog('detect_err',{m:String(e&&e.message||e)}); }
  status(dets.length? (dets.length+' found'):'no subjects — manual');
  clog('detect',{n:dets.length,classes:dets.slice(0,8).map(d=>d.class)});
  dets.sort((a,b)=> (b.bbox[2]*b.bbox[3])-(a.bbox[2]*a.bbox[3]));
  dets.forEach((d,i)=>{
    const b=document.createElement('div'); b.className='sub'; b.textContent=d.class+' '+Math.round(d.score*100)+'%';
    b.onclick=()=>{ document.querySelectorAll('.sub').forEach(x=>x.classList.remove('on')); b.classList.add('on'); target=d; frame(d.bbox); };
    $('#subjects').appendChild(b);
  });
  if(dets.length){ target=dets[0]; $('#subjects').firstChild.classList.add('on'); if(autoframe) frame(dets[0].bbox); }
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
$('#auto').onclick=()=>{ clog('auto',{dets:dets.length}); if(dets.length){ target=dets[0]; frame(dets[0].bbox);} else applyAR(ar,true); $('#zoom').value=62; applyZoom(); };

// a cropped-result overlay — the reliable "save" path on iOS (press-and-hold / share sheet)
function showResult(url,ow,oh){
  const m=document.createElement('div'); m.id='result';
  m.style.cssText='position:fixed;inset:0;background:rgba(3,5,9,.94);z-index:60;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:14px;padding:24px';
  m.innerHTML='<div style="color:#eaf0f7;font-weight:800;font-size:16px">Your crop is ready</div>'
   +'<img src="'+url+'" style="max-width:100%;max-height:60vh;border-radius:12px;border:1px solid #222b38">'
   +'<div style="color:#90a0b4;font-size:13px;text-align:center;line-height:1.5">Press &amp; hold the image to save it to Photos,<br>or tap Share.</div>'
   +'<div style="display:flex;gap:10px"><button id="rshare" style="background:linear-gradient(135deg,#6366f1,#8b5cf6);color:#fff;border:0;border-radius:11px;padding:12px 20px;font-weight:700;font-size:15px">Share / Save</button>'
   +'<button id="rclose" style="background:#141922;color:#fff;border:1px solid #222b38;border-radius:11px;padding:12px 20px;font-weight:700;font-size:15px">Close</button></div>';
  document.body.appendChild(m);
  m.querySelector('#rclose').onclick=()=>m.remove();
  m.querySelector('#rshare').onclick=async()=>{ try{
      const r=await fetch(url); const b=await r.blob(); const f=new File([b],'croppa.jpg',{type:'image/jpeg'});
      if(navigator.canShare&&navigator.canShare({files:[f]})){ await navigator.share({files:[f],title:'Croppa'}); clog('result_share_ok'); }
      else { const a=document.createElement('a'); a.href=url; a.download='croppa.jpg'; document.body.appendChild(a); a.click(); a.remove(); clog('result_anchor'); }
    }catch(err){ clog('result_share_err',{m:String(err&&err.message||err)}); } };
}

function nameFor(it){ const base=((it&&it.name)||'photo').replace(/\.[^.]+$/,'').slice(0,40); return 'croppa-'+base+'.jpg'; }
function renderCropCanvas(){
  const ow=Math.round(crop.w), oh=Math.round(crop.h);
  if(!img||!ow||!oh) return null;
  const o=document.createElement('canvas'); o.width=ow; o.height=oh;
  o.getContext('2d').drawImage(img, crop.x,crop.y,crop.w,crop.h, 0,0,ow,oh);
  return {canvas:o,ow,oh};
}
async function saveCurrent(advance){
  const it=tray.find(t=>t.id===activeId); if(!it){ clog('save_noitem'); return null; }
  const r=renderCropCanvas(); if(!r){ clog('save_badcrop'); status('nothing to save'); return null; }
  let blob=null; try{ blob=await new Promise(res=>r.canvas.toBlob(res,'image/jpeg',0.95)); }catch(_){ }
  if(!blob){ try{ blob=await (await fetch(r.canvas.toDataURL('image/jpeg',0.95))).blob(); }catch(_){ } }
  it.out=blob; it.done=true; it.st={x:crop.x,y:crop.y,w:crop.w,h:crop.h,ar,zoom:+$('#zoom').value};
  if(!it.thumb){ try{ it.thumb=r.canvas.toDataURL('image/jpeg',0.6); }catch(_){ } }
  dbPut(it); clog('save',{ow:r.ow,oh:r.oh}); renderTray();
  if(advance){ const next=tray.find(t=>!t.done); if(next&&next.id!==activeId){ openItem(next.id); status('saved ✓ · next photo'); } else status('all saved ✓'); }
  else status('saved ✓');
  return it;
}
async function exportBlob(blob,name){
  const url=URL.createObjectURL(blob); const file=new File([blob],name||'croppa.jpg',{type:'image/jpeg'});
  if(navigator.canShare&&navigator.canShare({files:[file]})){
    try{ await navigator.share({files:[file],title:'Croppa'}); clog('export_share_ok'); setTimeout(()=>URL.revokeObjectURL(url),9000); return; }
    catch(err){ clog('export_share_fail',{m:String(err&&err.message||err)}); }
  }
  if(!isIOS&&!standalone){
    try{ const a=document.createElement('a'); a.href=url; a.download=name||'croppa.jpg'; document.body.appendChild(a); a.click(); a.remove(); clog('export_anchor'); setTimeout(()=>URL.revokeObjectURL(url),9000); return; }
    catch(err){ clog('export_anchor_fail',{m:String(err&&err.message||err)}); }
  }
  showResult(url,0,0); clog('export_modal');
}

$('#save').onclick=()=>saveCurrent(true);
$('#dl').onclick=async()=>{
  if(!img){ clog('dl_noimg'); return; }
  const it=await saveCurrent(false);   // keep the library in sync with what we export
  const blob=it&&it.out; if(!blob){ return; }
  exportBlob(blob, nameFor(it));
};
$('#exportall').onclick=async()=>{
  const outs=tray.filter(t=>t.done&&t.out); if(!outs.length) return;
  clog('export_all',{n:outs.length});
  const files=outs.map(t=>new File([t.out],nameFor(t),{type:'image/jpeg'}));
  if(navigator.canShare&&navigator.canShare({files})){
    try{ await navigator.share({files,title:'Croppa'}); clog('export_all_ok',{n:files.length}); return; }
    catch(err){ clog('export_all_fail',{m:String(err&&err.message||err)}); }
  }
  for(const t of outs){ await exportBlob(t.out,nameFor(t)); await new Promise(r=>setTimeout(r,450)); }
};
$('#clearall').onclick=()=>{
  if(!tray.length) return;
  if(!confirm('Remove all '+tray.length+' photos from the library?')) return;
  tray.forEach(t=>dbDel(t.id)); tray=[]; activeId=null; img=null;
  ctx.clearRect(0,0,cv.width,cv.height); cv.width=cv.height=0; $('#drop').style.display=''; dets=[]; $('#subjects').innerHTML='';
  renderTray(); status(model?'AI ready':'manual mode'); clog('tray_clear');
};

// ---------- batch: AI auto-crop every photo in one pass (the photographer workflow) ----------
function loadImg(src){ return new Promise(res=>{ const im=new Image(); im.onload=()=>res(im); im.onerror=()=>res(null); im.src=src; }); }
function computeCrop(nw,nh,a,box,z){
  const ca = a ? a : nw/nh;                                   // target aspect
  let maxW,maxH; if(nw/nh>ca){ maxH=nh; maxW=maxH*ca; } else { maxW=nw; maxH=maxW/ca; }
  const w=maxW-(maxW-maxW*0.35)*z, h=maxH-(maxH-maxH*0.35)*z; // same zoom curve as the editor
  let cx=nw/2, cy=nh/2;
  if(box){ const pad=0.18; cx=box[0]+box[2]/2; cy=box[1]+box[3]/2; }  // centre on the detected subject
  let x=cx-w/2, y=cy-h/2;
  x=Math.max(0,Math.min(x,nw-w)); y=Math.max(0,Math.min(y,nh-h));
  return {x,y,w,h};
}
async function processOne(it,a,z){
  const blob=it.orig||it.out; if(!blob) return false;
  const im=await loadImg(URL.createObjectURL(blob)); if(!im||!im.naturalWidth) return false;
  const nw=im.naturalWidth, nh=im.naturalHeight;
  let box=null;
  if(model){ try{ let ds=await model.detect(im); if(ds&&ds.length){ ds.sort((p,q)=>q.bbox[2]*q.bbox[3]-p.bbox[2]*p.bbox[3]); box=ds[0].bbox; } }catch(_){ } }
  const c=computeCrop(nw,nh,a,box,z); const ow=Math.round(c.w), oh=Math.round(c.h); if(!ow||!oh) return false;
  const o=document.createElement('canvas'); o.width=ow; o.height=oh;
  o.getContext('2d').drawImage(im,c.x,c.y,c.w,c.h,0,0,ow,oh);
  let out=null; try{ out=await new Promise(r=>o.toBlob(r,'image/jpeg',0.95)); }catch(_){ }
  if(!out){ try{ out=await (await fetch(o.toDataURL('image/jpeg',0.95))).blob(); }catch(_){ } }
  it.out=out; it.done=true; it.st={x:c.x,y:c.y,w:c.w,h:c.h,ar:a,zoom:Math.round(z*100)};
  if(!it.thumb){ try{ it.thumb=o.toDataURL('image/jpeg',0.6); }catch(_){ } }
  dbPut(it); return true;
}
function setBusy(b){ busy=b; ['#autoall','#exportall','#clearall','#save','#dl','#auto'].forEach(s=>{ const el=$(s); if(el) el.disabled=b; }); }
$('#autoall').onclick=async()=>{
  if(busy) return;
  const pend=tray.filter(t=>!t.done); if(!pend.length) return;
  const a=ar, z=+$('#zoom').value/100;     // apply the currently-selected aspect + zoom to the whole batch
  clog('autoall_start',{n:pend.length,ar:a,model:!!model});
  setBusy(true); let ok=0;
  for(let i=0;i<pend.length;i++){ status('auto-cropping '+(i+1)+'/'+pend.length+'…'); if(await processOne(pend[i],a,z)) ok++; renderTray(); }
  setBusy(false);
  if(activeId){ openItem(activeId); }       // refresh the editor to reflect the active item's new crop
  status('auto-cropped '+ok+' ✓ — tap Export all'); clog('autoall_done',{ok,total:pend.length});
};

// ---------- desktop drag-and-drop: drop a whole shoot onto the window ----------
const dz=$('#drop');
['dragenter','dragover'].forEach(ev=>window.addEventListener(ev,e=>{ if(e.dataTransfer&&[...e.dataTransfer.types].includes('Files')){ e.preventDefault(); dz.classList.add('drag'); } }));
['dragleave','dragend'].forEach(ev=>window.addEventListener(ev,e=>{ if(e.relatedTarget===null) dz.classList.remove('drag'); }));
window.addEventListener('drop',e=>{ dz.classList.remove('drag'); if(e.dataTransfer&&e.dataTransfer.files&&e.dataTransfer.files.length){ e.preventDefault(); clog('drop',{n:e.dataTransfer.files.length}); addFiles(e.dataTransfer.files); } });

// restore the library from a previous session
(async()=>{ db=await idb(); let saved=[]; try{ saved=await dbAll(); }catch(_){ }
  if(saved&&saved.length){ tray=saved.sort((a,b)=>(a.ts||0)-(b.ts||0)); renderTray(); openItem(tray[0].id); clog('tray_restore',{n:tray.length}); } })();

window.addEventListener('resize',()=>{ if(img){ layout(); redraw(); } });
</script>
</body></html>'''

class H(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        try: log_event("http", {"msg": (fmt % args)}, self.client_address[0])
        except Exception: pass
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
        if p=='/api/signup':
            n=int(self.headers.get('Content-Length',0) or 0); raw=self.rfile.read(n) if n else b'{}'
            try: d=json.loads(raw or b'{}')
            except Exception: d={}
            email=(d.get('email') or '').strip().lower(); pw=d.get('password') or ''
            if '@' not in email or '.' not in email.split('@')[-1] or len(pw)<6:
                self.send_response(400); self.end_headers(); self.wfile.write(b'{"error":"Enter a valid email and a password of at least 6 characters."}'); return
            users=_users()
            if email in users:
                self.send_response(400); self.end_headers(); self.wfile.write(b'{"error":"That email already has an account \\u2014 sign in instead."}'); return
            salt=secrets.token_hex(16); users[email]={"salt":salt,"hash":hashlib.pbkdf2_hmac("sha256",pw.encode(),bytes.fromhex(salt),200000).hex()}; _save_users(users)
            t=_newsess(email); body=b'{"ok":true}'
            self.send_response(200); self.send_header('Content-Type','application/json')
            self.send_header('Set-Cookie', f"sess={t}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age={TTL}")
            self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body); return
        if p=='/api/logout':
            t=self._cookie('sess');
            if t: SESS.pop(t,None)
            self.send_response(200); self.end_headers(); self.wfile.write(b'{"ok":true}'); return
        if p=='/api/log':
            n=int(self.headers.get('Content-Length',0) or 0); raw=self.rfile.read(n) if n else b'{}'
            try: d=json.loads(raw or b'{}')
            except Exception: d={}
            log_event("client", d, self.client_address[0])
            self.send_response(204); self.end_headers(); return
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
