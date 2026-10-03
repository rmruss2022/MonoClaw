#!/usr/bin/env python3
"""
Inkling — a voice-first writing room where an AI librarian (the Keeper) writes books with you.

Speak your intent; the Keeper listens (browser speech recognition), talks back, and co-writes
your manuscript in YOUR voice. It tends your ideas like a librarian in a labyrinth of books:
Library -> Books -> Chapters, plus Marginalia (idea cards) and Loose Leaves (unfiled sparks).

Hard anti-slop contract baked into every prompt: your voice, concrete detail, no filler or
clichés, never invents facts (asks instead), offers rather than overwrites.

Zero third-party deps — stdlib http.server + sqlite3. Gemini for the Keeper (key from
/root/.openclaw/.env). Voice is 100% browser-side (Web Speech API), so there's no audio cost.
"""
import os, json, re, sqlite3, hashlib, secrets, urllib.request, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime, timezone

PORT = int(os.environ.get("INKLING_PORT", "18826"))
BASE = (os.environ.get("INKLING_BASE", "").rstrip("/"))   # "" = served at root (public tunnel)
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DB = os.path.join(DATA, "inkling.db")
os.makedirs(DATA, exist_ok=True)
MODEL = os.environ.get("INKLING_MODEL", "gemini-flash-latest")

# ---- storage ---------------------------------------------------------------

def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    return c

def init_db():
    c = db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users(
      id INTEGER PRIMARY KEY, email TEXT UNIQUE, pw_hash TEXT, pw_salt TEXT, created TEXT);
    CREATE TABLE IF NOT EXISTS sessions(
      token TEXT PRIMARY KEY, user_id INTEGER, created TEXT);
    CREATE TABLE IF NOT EXISTS books(
      id INTEGER PRIMARY KEY, user_id INTEGER, title TEXT, premise TEXT, voice_sample TEXT, created TEXT);
    CREATE TABLE IF NOT EXISTS chapters(
      id INTEGER PRIMARY KEY, book_id INTEGER, idx INTEGER, title TEXT, body TEXT, created TEXT);
    CREATE TABLE IF NOT EXISTS cards(
      id INTEGER PRIMARY KEY, user_id INTEGER, book_id INTEGER, kind TEXT, text TEXT, created TEXT);
    CREATE TABLE IF NOT EXISTS messages(
      id INTEGER PRIMARY KEY, book_id INTEGER, chapter_id INTEGER, role TEXT, mode TEXT, text TEXT, created TEXT);
    """)
    # migrate pre-auth DBs: add user_id ownership columns if missing
    for tbl in ("books", "cards"):
        cols = [r[1] for r in c.execute(f"PRAGMA table_info({tbl})").fetchall()]
        if "user_id" not in cols:
            c.execute(f"ALTER TABLE {tbl} ADD COLUMN user_id INTEGER")
    c.commit(); c.close()

def hash_pw(pw, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 200_000).hex()
    return salt, h

def verify_pw(pw, salt, h):
    try:
        return secrets.compare_digest(hash_pw(pw, salt)[1], h)
    except Exception:
        return False

def now():
    return datetime.now(timezone.utc).isoformat()

# ---- the Keeper (Gemini) ---------------------------------------------------

def _load_key():
    k = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if k:
        return k
    try:
        with open("/root/.openclaw/.env") as f:
            for line in f:
                line = line.strip()
                for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
                    if line.startswith(name + "="):
                        v = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if v:
                            return v
    except OSError:
        pass
    return ""

GEMINI_KEY = _load_key()

def gemini(prompt, want_json=False, timeout=45, temperature=0.9):
    if not GEMINI_KEY:
        return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={GEMINI_KEY}"
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temperature}}
    if want_json:
        body["generationConfig"]["response_mime_type"] = "application/json"
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            j = json.loads(r.read().decode("utf-8", "replace"))
        return j["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        return None

# The soul of the Keeper — the anti-slop contract, prepended to every call.
KEEPER = (
"You are the Keeper: a warm, exacting librarian and co-author who tends a writer's ideas like "
"rare books in a labyrinth of stacks. You care for their ideas; you never flatten them.\n"
"Rules you never break:\n"
"- Write in the WRITER'S voice, not a generic assistant voice. Mirror the diction, rhythm and "
"vocabulary in their voice-sample and existing prose.\n"
"- Be concrete and sensory. The specific noun, the real detail — never the abstract summary.\n"
"- No filler, no hedging, no 'it's worth noting', no inspirational wrap-ups, no clichés, no "
"purple prose, no emoji, no corporate AI tone.\n"
"- Never invent facts about the writer's world. If a needed detail is genuinely unknown, ask ONE "
"precise question instead of making it up.\n"
"- Offer, don't overwrite. Serve the writer's intent; never make their ideas safer or blander.\n"
"- Keep it tight. Short by default; go long only when explicitly asked to draft.\n")

def ctx_for(c, book_id, chapter_id=None, tail=1600):
    """Assemble compact context: book, voice, current chapter tail, cards, recent turns."""
    b = c.execute("SELECT * FROM books WHERE id=?", (book_id,)).fetchone()
    out = []
    if b:
        out.append(f"BOOK: {b['title']}\nPREMISE: {b['premise'] or '(none yet)'}")
        if b["voice_sample"]:
            out.append("THE WRITER'S VOICE (sample of their own writing — match this):\n\"\"\"\n"
                       + b["voice_sample"][:1200] + "\n\"\"\"")
    cards = c.execute("SELECT text FROM cards WHERE book_id=? ORDER BY id DESC LIMIT 12", (book_id,)).fetchall()
    if cards:
        out.append("MARGINALIA (the writer's idea-cards for this book):\n" +
                   "\n".join("- " + r["text"][:200] for r in cards))
    if chapter_id:
        ch = c.execute("SELECT * FROM chapters WHERE id=?", (chapter_id,)).fetchone()
        if ch and ch["body"]:
            body = ch["body"]
            out.append(f"CURRENT CHAPTER ({ch['title'] or 'untitled'}) — the end of it so far:\n"
                       + ("…" + body[-tail:] if len(body) > tail else body))
    msgs = c.execute("SELECT role,text FROM messages WHERE book_id=? ORDER BY id DESC LIMIT 6",
                     (book_id,)).fetchall()
    if msgs:
        turns = list(reversed([f"{m['role']}: {m['text'][:300]}" for m in msgs]))
        out.append("RECENT CONVERSATION:\n" + "\n".join(turns))
    return "\n\n".join(out)

# ---- front end -------------------------------------------------------------

PAGE = r'''<!doctype html><html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#201a14">
<link rel="manifest" href="__BASE__/manifest.webmanifest">
<link rel="apple-touch-icon" href="__BASE__/icon-192.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="Inkling">
<title>Inkling — write by voice</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,600;1,9..144,400&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root{--bg:#201a14;--bg2:#271f17;--panel:#2d2419;--panel2:#352a1d;--line:#453726;--text:#f3ebdd;
--muted:#b2a088;--ink:#e9dcc4;--accent:#c89b53;--accent2:#e0b063;--good:#8bbf8a;--bad:#d98a6a;--r:16px;
--serif:"Fraunces",Georgia,serif;--sans:"Inter",-apple-system,system-ui,sans-serif}
*{box-sizing:border-box}
body{margin:0;background:radial-gradient(1200px 600px at 50% -10%,#2a2116,var(--bg));color:var(--text);
font:15px/1.6 var(--sans);-webkit-font-smoothing:antialiased}
a{color:var(--accent2)}
header{padding:calc(env(safe-area-inset-top,0) + 15px) 18px 12px;border-bottom:1px solid var(--line);
display:flex;align-items:center;gap:11px;position:sticky;top:0;z-index:20;
background:linear-gradient(180deg,#241c14,rgba(32,26,20,.85));backdrop-filter:blur(8px)}
.brand{font-family:var(--serif);font-size:21px;font-weight:600;letter-spacing:-.01em;flex:1}
.brand .q{color:var(--accent)}
.sub{font-size:11.5px;color:var(--muted);margin-top:-2px}
.back{background:var(--panel2);border:1px solid var(--line);color:var(--text);border-radius:10px;
padding:7px 11px;font-size:13px;font-weight:600;cursor:pointer}
.vtoggle{background:var(--panel2);border:1px solid var(--line);color:var(--muted);border-radius:999px;
padding:6px 11px;font-size:12px;font-weight:600;cursor:pointer}
.vtoggle.on{color:var(--accent2);border-color:var(--accent)}
main{max-width:820px;margin:0 auto;padding:18px 15px 160px}
.btn{background:linear-gradient(180deg,var(--accent2),var(--accent));color:#2a1e0a;border:0;border-radius:12px;
padding:12px 16px;font-weight:700;font-size:14px;cursor:pointer;width:100%;font-family:var(--sans)}
.btn.ghost{background:var(--panel2);color:var(--text);border:1px solid var(--line)}
.btn.sm{padding:8px 12px;font-size:13px;width:auto}
.btn:disabled{opacity:.5}
label{display:block;font-size:11px;color:var(--muted);font-weight:700;margin:12px 0 5px;text-transform:uppercase;letter-spacing:.05em}
input,textarea,select{width:100%;background:var(--bg2);border:1px solid var(--line);color:var(--text);
border-radius:11px;padding:11px 12px;font:inherit;outline:none}
input:focus,textarea:focus{border-color:var(--accent)}
textarea{resize:vertical}
.card{background:var(--panel);border:1px solid var(--line);border-radius:var(--r);padding:16px;margin-bottom:13px}
.muted{color:var(--muted)}.sm{font-size:12.5px}
.empty{color:var(--muted);text-align:center;padding:44px 14px;font-family:var(--serif);font-size:17px;line-height:1.5}
.book{cursor:pointer;display:flex;gap:13px;align-items:flex-start}
.spine{width:10px;align-self:stretch;border-radius:4px;background:linear-gradient(180deg,var(--accent2),var(--accent));flex-shrink:0}
.book .t{font-family:var(--serif);font-size:18px;font-weight:600}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}
.chip{background:var(--panel2);border:1px solid var(--line);border-radius:999px;padding:3px 10px;font-size:11.5px;color:var(--muted)}
.ch{display:flex;align-items:center;gap:10px;padding:11px 12px;border:1px solid var(--line);border-radius:12px;
background:var(--panel2);margin-bottom:8px;cursor:pointer}
.ch .n{width:24px;height:24px;border-radius:7px;background:var(--bg);display:flex;align-items:center;justify-content:center;
font-size:12px;color:var(--accent2);font-weight:700;flex-shrink:0}
.ch .t{flex:1;font-family:var(--serif);font-size:15.5px}
.ch .w{font-size:11px;color:var(--muted)}
.manu{width:100%;min-height:44vh;background:var(--bg2);border:1px solid var(--line);border-radius:12px;
padding:16px 17px;font-family:var(--serif);font-size:17px;line-height:1.75;color:var(--ink)}
.row{display:flex;gap:9px}.row>*{flex:1}
.section-t{font-family:var(--serif);font-size:15px;color:var(--muted);margin:4px 0 8px;font-weight:600}
.cardlist .m{background:var(--panel2);border:1px solid var(--line);border-left:3px solid var(--accent);
border-radius:10px;padding:10px 12px;margin-bottom:8px;position:relative}
.cardlist .m .x{position:absolute;top:7px;right:9px;color:var(--muted);cursor:pointer;font-size:14px}
.keeper{background:var(--panel2);border:1px solid var(--line);border-radius:12px;padding:13px 14px;margin-top:10px;
font-family:var(--serif);font-size:15.5px;line-height:1.6;white-space:pre-wrap}
.keeper .who{font-family:var(--sans);font-size:11px;color:var(--accent);font-weight:700;text-transform:uppercase;
letter-spacing:.06em;margin-bottom:5px}
.draft{border-left:3px solid var(--accent)}
/* composer dock */
.dock{position:fixed;left:0;right:0;bottom:0;z-index:30;padding:10px 12px calc(12px + env(safe-area-inset-bottom,0));
background:linear-gradient(180deg,rgba(32,26,20,0),#201a14 26%);}
.dockin{max-width:820px;margin:0 auto;background:var(--panel);border:1px solid var(--line);border-radius:18px;
padding:9px 10px;box-shadow:0 10px 40px rgba(0,0,0,.45)}
.modes{display:flex;gap:6px;margin-bottom:8px}
.mode{flex:1;text-align:center;padding:7px;border:1px solid var(--line);border-radius:10px;background:var(--panel2);
font-size:12.5px;font-weight:700;color:var(--muted);cursor:pointer}
.mode.on{color:#2a1e0a;background:linear-gradient(180deg,var(--accent2),var(--accent));border-color:var(--accent)}
.composer{display:flex;gap:9px;align-items:flex-end}
.composer textarea{flex:1;min-height:44px;max-height:140px;border-radius:12px;font-family:var(--sans);font-size:15px}
.mic{width:50px;height:50px;border-radius:50%;border:0;flex-shrink:0;cursor:pointer;
background:linear-gradient(180deg,var(--accent2),var(--accent));color:#2a1e0a;font-size:21px;display:flex;align-items:center;justify-content:center}
.mic.rec{background:linear-gradient(180deg,#e06a4a,#c2492b);color:#fff;animation:pulse 1.2s infinite}
@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(224,106,74,.6)}70%{box-shadow:0 0 0 14px rgba(224,106,74,0)}100%{box-shadow:0 0 0 0 rgba(224,106,74,0)}}
.send{width:50px;height:50px;border-radius:14px;border:0;flex-shrink:0;cursor:pointer;background:var(--panel2);
border:1px solid var(--line);color:var(--accent2);font-size:20px}
.hint{font-size:11px;color:var(--muted);margin-top:6px;text-align:center}
.spinner{display:inline-block;width:14px;height:14px;border:2px solid rgba(255,255,255,.3);border-top-color:#fff;
border-radius:50%;animation:sp .7s linear infinite;vertical-align:-2px;margin-right:6px}
@keyframes sp{to{transform:rotate(360deg)}}
.toolbar{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
.modal{position:fixed;inset:0;background:rgba(0,0,0,.72);z-index:50;display:flex;align-items:flex-end;justify-content:center}
.sheet{background:var(--panel);border-top-left-radius:20px;border-top-right-radius:20px;width:100%;max-width:560px;
max-height:92vh;overflow:auto;padding:18px 16px calc(24px + env(safe-area-inset-bottom,0));border:1px solid var(--line)}
.sheet h2{font-family:var(--serif);font-weight:600;margin:2px 0 4px}
.toast{position:fixed;left:50%;bottom:150px;transform:translateX(-50%);background:#352a1d;border:1px solid var(--line);
color:var(--text);padding:10px 15px;border-radius:12px;z-index:80;font-size:13.5px;box-shadow:0 8px 30px rgba(0,0,0,.5);max-width:90%}
.bad{color:var(--bad)}
</style></head><body>
<header>
  <div>
    <div class="brand">Ink<span class="q">ling</span></div>
    <div class="sub" id="crumb">your writing room</div>
  </div>
  <button class="vtoggle on" id="vbtn" onclick="toggleVoice()" style="display:none">🔊 Voice</button>
  <button class="back" id="backBtn" style="display:none" onclick="goLib()">← Library</button>
  <button class="vtoggle" id="logout" style="display:none" onclick="doLogout()" title="Log out">⎋</button>
</header>
<main id="app"></main>
<div class="dock" id="dock" style="display:none">
 <div class="dockin">
  <div class="modes">
   <div class="mode on" data-m="muse" onclick="setMode('muse')">💬 Talk</div>
   <div class="mode" data-m="draft" onclick="setMode('draft')">✒️ Write</div>
   <div class="mode" data-m="revise" onclick="setMode('revise')">✎ Revise</div>
  </div>
  <div class="composer">
   <button class="mic" id="mic" onclick="toggleRec()" title="Hold a thought and speak">🎙️</button>
   <textarea id="say" rows="1" placeholder="Speak, or type to the Keeper…"></textarea>
   <button class="send" id="send" onclick="sendSay()" title="Send">➤</button>
  </div>
  <div class="hint" id="hint">Talk through an idea. The Keeper listens and nurtures it.</div>
 </div>
</div>
<script>
const BASE="__BASE__";
const api=(p,o)=>fetch(BASE+p,o).then(async r=>{
  if(r.status===401){USER=null;renderAuth();throw new Error('auth');}
  return r.json();});
const el=id=>document.getElementById(id);
const esc=s=>(s||"").replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
let BOOK=null, CH=null, MODE="muse", VOICE=true, REC=null, recOn=false, USER=null, authMode="login";

function toast(m){let t=document.createElement('div');t.className='toast';t.textContent=m;
 document.body.appendChild(t);setTimeout(()=>t.remove(),2800);}
function speak(t){if(!VOICE||!t||!window.speechSynthesis)return;try{speechSynthesis.cancel();
 const u=new SpeechSynthesisUtterance(t.replace(/[*_#>`]/g,''));u.rate=1.0;u.pitch=1.0;speechSynthesis.speak(u);}catch(e){}}
function toggleVoice(){VOICE=!VOICE;el('vbtn').classList.toggle('on',VOICE);el('vbtn').textContent=VOICE?'🔊 Voice':'🔇 Voice';
 if(!VOICE&&window.speechSynthesis)speechSynthesis.cancel();}

// ---- speech recognition (Web Speech API) ----
function recSupported(){return 'webkitSpeechRecognition' in window||'SpeechRecognition' in window;}
function toggleRec(){
 if(!recSupported())return toast('This browser has no speech recognition — try Chrome. You can still type.');
 if(recOn){REC&&REC.stop();return;}
 const SR=window.SpeechRecognition||window.webkitSpeechRecognition;REC=new SR();
 REC.lang='en-US';REC.interimResults=true;REC.continuous=true;
 let base=el('say').value?el('say').value+' ':'';
 REC.onstart=()=>{recOn=true;el('mic').classList.add('rec');el('hint').textContent='Listening… tap the mic again when you pause.';};
 REC.onerror=e=>{toast('Mic: '+e.error);};
 REC.onend=()=>{recOn=false;el('mic').classList.remove('rec');el('hint').textContent=hintFor(MODE);};
 REC.onresult=ev=>{let fin='',interim='';for(let i=ev.resultIndex;i<ev.results.length;i++){
   const tr=ev.results[i][0].transcript;if(ev.results[i].isFinal)fin+=tr;else interim+=tr;}
   if(fin)base+=fin+' ';el('say').value=(base+interim).replace(/\s+/g,' ').trimStart();autosize();};
 REC.start();
}
function autosize(){const t=el('say');t.style.height='auto';t.style.height=Math.min(t.scrollHeight,140)+'px';}
el('say').addEventListener('input',autosize);
el('say').addEventListener('keydown',e=>{if(e.key==='Enter'&&(e.metaKey||e.ctrlKey)){e.preventDefault();sendSay();}});

function hintFor(m){return m==='draft'?'Say what happens next — the Keeper drafts it in your voice.'
 :m==='revise'?'Select text in the manuscript, then say how to change it.'
 :'Talk through an idea. The Keeper listens and nurtures it.';}
function setMode(m){MODE=m;document.querySelectorAll('.mode').forEach(x=>x.classList.toggle('on',x.dataset.m===m));
 el('hint').textContent=hintFor(m);}

// ---- library ----
// ---- auth ----
async function boot(){let me;try{me=await api('/api/auth/me');}catch(e){return;}
 USER=me.user;if(USER){enterApp();}else{renderAuth();}}
function enterApp(){el('vbtn').style.display='';el('logout').style.display='';goLib();}
function renderAuth(){USER=null;
 el('backBtn').style.display='none';el('dock').style.display='none';
 el('vbtn').style.display='none';el('logout').style.display='none';
 el('crumb').textContent='your writing room';
 el('app').innerHTML=`<div class="card" style="max-width:390px;margin:32px auto 0">
  <h2 style="font-family:var(--serif);font-size:22px;margin:0 0 2px">Welcome to Inkling</h2>
  <p class="muted sm" style="margin:0 0 6px">A quiet room where the Keeper writes with you. Your books are private to your account.</p>
  <label>Email</label><input id="au_email" type="email" autocomplete="username" placeholder="you@example.com">
  <label>Password</label><input id="au_pw" type="password" autocomplete="current-password" placeholder="at least 6 characters">
  <div id="au_err" class="bad sm" style="margin-top:8px"></div>
  <div style="margin-top:14px"><button class="btn" id="au_go" onclick="doAuth()">Log in</button>
  <button class="btn ghost" style="margin-top:8px" onclick="toggleAuthMode()" id="au_tog">New here? Create an account</button></div></div>`;
 el('au_pw').addEventListener('keydown',e=>{if(e.key==='Enter')doAuth();});
}
function toggleAuthMode(){authMode=authMode==='login'?'signup':'login';
 el('au_go').textContent=authMode==='login'?'Log in':'Create account';
 el('au_tog').textContent=authMode==='login'?'New here? Create an account':'Have an account? Log in';
 el('au_pw').setAttribute('autocomplete',authMode==='login'?'current-password':'new-password');el('au_err').textContent='';}
async function doAuth(){const email=(el('au_email').value||'').trim();const pw=el('au_pw').value||'';
 if(!email||!pw)return el('au_err').textContent='Enter your email and password.';
 el('au_go').disabled=true;el('au_err').textContent='';let r;
 try{r=await fetch(BASE+'/api/auth/'+(authMode==='signup'?'signup':'login'),
   {method:'POST',body:JSON.stringify({email,password:pw})}).then(x=>x.json());}catch(e){r={error:'Network error'};}
 el('au_go').disabled=false;
 if(r.error){el('au_err').textContent=r.error;return;}
 USER=r.user;enterApp();}
async function doLogout(){try{await fetch(BASE+'/api/auth/logout',{method:'POST'});}catch(e){}
 if(window.speechSynthesis)speechSynthesis.cancel();BOOK=null;CH=null;renderAuth();}

async function goLib(){BOOK=null;CH=null;el('backBtn').style.display='none';el('dock').style.display='none';
 el('crumb').textContent='your writing room';
 const d=await api('/api/library');renderLib(d);}
function renderLib(d){
 let h=`<button class="btn" onclick="newBook()">+ Begin a new book</button>`;
 const loose=d.loose||[];
 if(!d.books.length){h+=`<div class="empty">The stacks are empty.<br>Begin a book, and the Keeper will<br>write it with you — one idea at a time.</div>`;}
 else{h+=`<div style="margin-top:14px"></div>`;
  for(const b of d.books){h+=`<div class="card book" onclick="openBook(${b.id})"><div class="spine"></div>
   <div style="flex:1;min-width:0"><div class="t">${esc(b.title)}</div>
   <div class="muted sm">${esc(b.premise||'')}</div>
   <div class="chips"><span class="chip">📖 ${b.chapters} ch</span><span class="chip">🗒️ ${b.cards} cards</span>
   <span class="chip">${b.words.toLocaleString()} words</span></div></div></div>`;}
 }
 // loose leaves shelf
 h+=`<div class="card"><div class="section-t">🍃 Loose Leaves — unfiled sparks</div>`;
 if(!loose.length)h+=`<div class="muted sm">Catch a stray idea anytime with the spark button.</div>`;
 else{h+=`<div class="cardlist">`;for(const l of loose)h+=`<div class="m"><span class="x" onclick="delCard(${l.id},event)">✕</span>${esc(l.text)}</div>`;h+=`</div>`;}
 h+=`<div class="toolbar"><button class="btn sm ghost" onclick="spark()">✨ Capture a spark</button></div></div>`;
 el('app').innerHTML=h;
}
function newBook(){sheet(`<h2>Begin a new book</h2>
 <label>Title</label><input id="b_title" placeholder="The Cartographer's Daughter">
 <label>What's it about? (a premise, however rough)</label><textarea id="b_prem" rows="3" placeholder="A mapmaker's daughter inherits a map of places that don't exist yet."></textarea>
 <label>A paragraph in your voice (optional — teaches the Keeper how you write)</label>
 <textarea id="b_voice" rows="4" placeholder="Paste something you've written. The Keeper will match your rhythm and diction."></textarea>
 <div style="margin-top:16px"><button class="btn" onclick="createBook()">Open the book</button></div>`);}
async function createBook(){const title=el('b_title').value.trim();if(!title)return toast('Give it a title');
 const r=await api('/api/books',{method:'POST',body:JSON.stringify({title,premise:el('b_prem').value.trim(),voice_sample:el('b_voice').value.trim()})});
 closeSheet();openBook(r.id);}

// ---- book view ----
async function openBook(id){const b=await api('/api/books/'+id);BOOK=b;CH=null;
 el('backBtn').style.display='';el('dock').style.display='';el('crumb').textContent=b.title;
 setMode('muse');renderBook();}
function renderBook(){const b=BOOK;
 let h=`<div class="card"><div class="t" style="font-family:var(--serif);font-size:22px">${esc(b.title)}</div>
  <div class="muted sm" style="margin-top:3px">${esc(b.premise||'')}</div>
  <div class="toolbar">
   <button class="btn sm" onclick="newChapter()">+ New chapter</button>
   <button class="btn sm ghost" onclick="tend()">🕯️ Tend the stacks</button>
   <button class="btn sm ghost" onclick="spark()">✨ Spark</button>
   <button class="btn sm ghost" onclick="exportBook()">⬇︎ Export</button>
   <button class="btn sm ghost bad" onclick="delBook()">Delete</button>
  </div><div id="tendbox"></div></div>`;
 h+=`<div class="section-t">📖 Chapters</div>`;
 if(!b.chapters.length)h+=`<div class="muted sm" style="margin-bottom:10px">No chapters yet. Start one, then switch to ✒️ Write and speak.</div>`;
 b.chapters.forEach((ch,i)=>{const w=(ch.body||'').trim().split(/\s+/).filter(Boolean).length;
  h+=`<div class="ch" onclick="openCh(${ch.id})"><div class="n">${i+1}</div>
   <div class="t">${esc(ch.title||'Untitled')}</div><div class="w">${w} w</div></div>`;});
 // marginalia
 h+=`<div class="card" style="margin-top:14px"><div class="section-t">🗒️ Marginalia — this book's ideas</div>`;
 if(!b.cards.length)h+=`<div class="muted sm">Sparks you file here become the Keeper's memory for this book.</div>`;
 else{h+=`<div class="cardlist">`;for(const cd of b.cards)h+=`<div class="m"><span class="x" onclick="delCard(${cd.id},event)">✕</span>${esc(cd.text)}</div>`;h+=`</div>`;}
 h+=`</div><div id="keeperbox"></div>`;
 el('app').innerHTML=h;el('keeperbox').innerHTML='';
}

async function newChapter(){const r=await api('/api/chapters',{method:'POST',
  body:JSON.stringify({book_id:BOOK.id,title:'Chapter '+(BOOK.chapters.length+1),body:''})});
 const b=await api('/api/books/'+BOOK.id);BOOK=b;openCh(r.id);}

// ---- chapter (manuscript) view ----
let saveT=null;
function openCh(id){CH=BOOK.chapters.find(c=>c.id===id);setMode('draft');
 el('crumb').textContent=BOOK.title+' · '+(CH.title||'chapter');
 let h=`<div class="card"><input id="ch_title" value="${esc(CH.title||'')}" style="font-family:var(--serif);font-size:18px;border:0;background:transparent;padding:0 0 8px" oninput="queueSave()">
  <textarea id="manu" class="manu" oninput="queueSave()" placeholder="Your manuscript grows here. Switch to ✒️ Write below and speak what happens next.">${esc(CH.body||'')}</textarea>
  <div class="toolbar"><button class="btn sm ghost" onclick="renderBook()">← Back to book</button>
   <span class="muted sm" id="savest" style="align-self:center">saved</span></div>
  </div><div id="keeperbox"></div>`;
 el('app').innerHTML=h;}
function queueSave(){el('savest')&&(el('savest').textContent='…');clearTimeout(saveT);saveT=setTimeout(saveCh,700);}
async function saveCh(){if(!CH)return;CH.title=el('ch_title').value;CH.body=el('manu').value;
 await api('/api/chapters',{method:'POST',body:JSON.stringify({id:CH.id,book_id:BOOK.id,title:CH.title,body:CH.body})});
 const bi=BOOK.chapters.findIndex(c=>c.id===CH.id);if(bi>=0)BOOK.chapters[bi]=CH;el('savest')&&(el('savest').textContent='saved');}

// ---- the core voice turn ----
async function sendSay(){const text=el('say').value.trim();if(!text)return;
 if(!BOOK)return toast('Open a book first');
 if(MODE==='revise'&&!CH)return toast('Open a chapter and select the text to revise');
 let selection=null;
 if(MODE==='revise'){const t=el('manu');if(t&&t.selectionStart!==t.selectionEnd)
   selection=t.value.substring(t.selectionStart,t.selectionEnd);
   if(!selection)return toast('Select the passage to revise first');}
 el('say').value='';autosize();
 const kb=el('keeperbox')||document.getElementById('app');
 const box=document.createElement('div');box.className='keeper';
 box.innerHTML=`<div class="who">The Keeper</div><span class="spinner"></span>thinking…`;
 kb.prepend?kb.prepend(box):kb.appendChild(box);box.scrollIntoView({behavior:'smooth',block:'center'});
 const r=await api('/api/say',{method:'POST',body:JSON.stringify({book_id:BOOK.id,
   chapter_id:CH?CH.id:null,mode:MODE,text,selection})});
 if(r.error){box.innerHTML=`<div class="who">The Keeper</div><span class="bad">${esc(r.error)}</span>`;return;}
 if(MODE==='draft'&&r.draft){
   box.classList.add('draft');
   box.innerHTML=`<div class="who">The Keeper · a draft</div>${esc(r.draft)}
    <div class="toolbar"><button class="btn sm" onclick='applyDraft(this)'>＋ Add to chapter</button>
    <button class="btn sm ghost" onclick="this.closest('.keeper').remove()">Discard</button></div>`;
   box._draft=r.draft;speak(r.note||"Here's a draft.");
 } else if(MODE==='revise'&&r.draft){
   box.classList.add('draft');
   box.innerHTML=`<div class="who">The Keeper · revised</div>${esc(r.draft)}
    <div class="toolbar"><button class="btn sm" onclick='applyRevise(this)'>Replace selection</button>
    <button class="btn sm ghost" onclick="this.closest('.keeper').remove()">Keep mine</button></div>`;
   box._draft=r.draft;box._sel=selection;speak("Here's a revision.");
 } else {
   box.innerHTML=`<div class="who">The Keeper</div>${esc(r.reply||'…')}`;speak(r.reply);
 }
}
async function applyDraft(btn){const box=btn.closest('.keeper');const d=box._draft;
 if(!CH){toast('Open a chapter first');return;}
 const t=el('manu');if(t){t.value=(t.value.trim()?t.value.replace(/\s*$/,'')+'\n\n':'')+d;queueSave();}
 box.classList.remove('draft');box.innerHTML=`<div class="who">The Keeper</div>Added to the chapter. Keep going — what happens next?`;
}
async function applyRevise(btn){const box=btn.closest('.keeper');const t=el('manu');
 if(t&&box._sel){t.value=t.value.replace(box._sel,box._draft);queueSave();}
 box.classList.remove('draft');box.innerHTML=`<div class="who">The Keeper</div>Done — your passage is revised.`;
}

// ---- marginalia / sparks ----
function spark(){sheet(`<h2>✨ Capture a spark</h2>
 <p class="muted sm">A stray idea, a line of dialogue, an image. ${recSupported()?'Tap the mic and speak, or type.':'Type it below.'}</p>
 <textarea id="sp_text" rows="4" placeholder="What just occurred to you?"></textarea>
 <div class="toolbar">${recSupported()?'<button class="btn sm ghost" id="sp_mic" onclick="sparkMic()">🎙️ Speak</button>':''}</div>
 <label>File it under</label>
 <select id="sp_dest"><option value="loose">🍃 Loose Leaves (unfiled)</option>${BOOK?`<option value="book" selected>🗒️ ${esc(BOOK.title)}</option>`:''}</select>
 <div style="margin-top:14px"><button class="btn" onclick="saveSpark()">Shelve it</button></div>`);}
let sparkRec=null;
function sparkMic(){if(!recSupported())return;const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
 const r=new SR();r.lang='en-US';r.interimResults=true;r.continuous=true;let base=el('sp_text').value?el('sp_text').value+' ':'';
 const btn=el('sp_mic');r.onstart=()=>btn.textContent='● Listening…';r.onend=()=>btn.textContent='🎙️ Speak';
 r.onresult=ev=>{let f='',i='';for(let k=ev.resultIndex;k<ev.results.length;k++){const tr=ev.results[k][0].transcript;
  ev.results[k].isFinal?f+=tr:i+=tr;}if(f)base+=f+' ';el('sp_text').value=(base+i).trimStart();};
 if(btn.textContent.indexOf('Listening')>=0){sparkRec&&sparkRec.stop();sparkRec=null;}else{sparkRec=r;r.start();}}
async function saveSpark(){const text=el('sp_text').value.trim();if(!text)return toast('Nothing to shelve');
 const dest=el('sp_dest').value;sparkRec&&sparkRec.stop();
 await api('/api/cards',{method:'POST',body:JSON.stringify({book_id:dest==='book'&&BOOK?BOOK.id:null,kind:'spark',text})});
 closeSheet();toast('Shelved ✨');if(BOOK)openBook(BOOK.id);else goLib();}
async function delCard(id,ev){ev.stopPropagation();await api('/api/cards/'+id,{method:'DELETE'});
 if(BOOK)openBook(BOOK.id);else goLib();}

async function tend(){const box=el('tendbox');box.innerHTML=`<div class="keeper"><div class="who">The Keeper · tending</div><span class="spinner"></span>walking the stacks…</div>`;
 const r=await api('/api/tend',{method:'POST',body:JSON.stringify({book_id:BOOK.id})});
 box.innerHTML=`<div class="keeper"><div class="who">The Keeper · tending the stacks</div>${esc(r.text||r.error||'Nothing yet.')}</div>`;
 speak(r.text);}

async function exportBook(){window.open(BASE+'/api/export/'+BOOK.id,'_blank');}
async function delBook(){if(!confirm('Delete this book and everything in it?'))return;
 await api('/api/books/'+BOOK.id,{method:'DELETE'});goLib();}

// ---- bottom sheet ----
function sheet(html){closeSheet();const m=document.createElement('div');m.className='modal';m.id='modal';
 m.onclick=e=>{if(e.target===m)closeSheet();};m.innerHTML=`<div class="sheet">${html}</div>`;document.body.appendChild(m);}
function closeSheet(){const m=el('modal');if(m)m.remove();}

if('serviceWorker' in navigator)navigator.serviceWorker.register(BASE+'/sw.js').catch(()=>{});
if(!recSupported())el('mic').style.opacity=.5;
boot();
</script></body></html>'''

MANIFEST = json.dumps({
    "name": "Inkling", "short_name": "Inkling",
    "start_url": (BASE + "/") or "/", "scope": (BASE + "/") or "/",
    "display": "standalone", "background_color": "#201a14", "theme_color": "#201a14",
    "description": "A voice-first writing room where an AI librarian writes books with you.",
    "icons": [
        {"src": (BASE + "/icon-192.png"), "sizes": "192x192", "type": "image/png"},
        {"src": (BASE + "/icon-512.png"), "sizes": "512x512", "type": "image/png", "purpose": "any maskable"},
    ],
})

SW = ("const C='inkling-v3';const SHELL=['__B__/','__B__/manifest.webmanifest','__B__/icon-192.png'];"
      "self.addEventListener('install',e=>{self.skipWaiting();e.waitUntil(caches.open(C).then(c=>c.addAll(SHELL).catch(()=>{})))});"
      "self.addEventListener('activate',e=>{self.clients.claim();e.waitUntil(caches.keys().then(ks=>Promise.all(ks.filter(k=>k!==C).map(k=>caches.delete(k)))))});"
      "self.addEventListener('fetch',e=>{const u=new URL(e.request.url);if(u.pathname.indexOf('/api/')>=0)return;"
      # network-first for the page/navigation so a stale shell can never persist
      "if(e.request.mode==='navigate'){e.respondWith(fetch(e.request).then(res=>{"
      "const cp=res.clone();caches.open(C).then(c=>c.put(e.request,cp));return res;}).catch(()=>caches.match(e.request).then(r=>r||caches.match('__B__/'))));return;}"
      # cache-first for static assets
      "e.respondWith(caches.match(e.request).then(r=>r||fetch(e.request).then(res=>{"
      "if(e.request.method==='GET'&&res.ok){const cp=res.clone();caches.open(C).then(c=>c.put(e.request,cp));}return res;}).catch(()=>r)))});"
      ).replace("__B__", BASE)

ICON_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">'
            '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
            '<stop offset="0" stop-color="#e0b063"/><stop offset="1" stop-color="#c89b53"/></linearGradient></defs>'
            '<rect width="512" height="512" rx="112" fill="#201a14"/>'
            '<rect x="150" y="96" width="212" height="300" rx="14" fill="none" stroke="url(#g)" stroke-width="16"/>'
            '<line x1="256" y1="110" x2="256" y2="382" stroke="url(#g)" stroke-width="12"/>'
            '<path d="M330 150 l44 -20 -10 46 -150 150 -40 8 8 -40z" fill="url(#g)"/>'
            '<circle cx="256" cy="430" r="16" fill="url(#g)"/></svg>')

# ---- server ----------------------------------------------------------------

def book_words(c, bid):
    rows = c.execute("SELECT body FROM chapters WHERE book_id=?", (bid,)).fetchall()
    return sum(len((r["body"] or "").split()) for r in rows)

class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ct="application/json", extra=None):
        if isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code, obj):
        self._send(code, json.dumps(obj))

    def _body(self):
        n = int(self.headers.get("Content-Length", 0))
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return {}

    def _p(self):
        p = urllib.parse.urlparse(self.path).path
        if BASE and p.startswith(BASE):
            p = p[len(BASE):] or "/"
        return p

    def _user(self, c):
        tok = None
        for part in (self.headers.get("Cookie", "") or "").split(";"):
            if "=" in part:
                k, v = part.strip().split("=", 1)
                if k == "ink_sess":
                    tok = v
        if not tok:
            return None
        return c.execute("SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=?",
                         (tok,)).fetchone()

    def _own_book(self, c, uid, bid):
        return c.execute("SELECT * FROM books WHERE id=? AND user_id=?", (bid, uid)).fetchone()

    def _set_cookie(self, tok, clear=False):
        path = (BASE or "") + "/"
        if clear:
            return f"ink_sess=; Path={path}; HttpOnly; SameSite=Lax; Max-Age=0"
        return f"ink_sess={tok}; Path={path}; HttpOnly; SameSite=Lax; Max-Age=31536000"

    def do_GET(self):
        p = self._p()
        if p in ("/", "/index.html"):
            return self._send(200, PAGE.replace("__BASE__", BASE), "text/html; charset=utf-8")
        if p == "/manifest.webmanifest":
            return self._send(200, MANIFEST, "application/manifest+json")
        if p == "/sw.js":
            return self._send(200, SW, "application/javascript")
        if p in ("/icon.svg", "/icon.png", "/icon-192.png", "/icon-512.png"):
            fp = os.path.join(HERE, p.lstrip("/"))
            if p.endswith(".png") and os.path.isfile(fp):
                with open(fp, "rb") as f:
                    return self._send(200, f.read(), "image/png")
            return self._send(200, ICON_SVG, "image/svg+xml")

        c = db()
        try:
            u = self._user(c)
            if p == "/api/auth/me":
                return self._json(200, {"user": {"email": u["email"]} if u else None})
            if not u:
                return self._json(401, {"error": "Please log in."})
            uid = u["id"]
            if p == "/api/library":
                books = []
                for b in c.execute("SELECT * FROM books WHERE user_id=? ORDER BY id DESC", (uid,)).fetchall():
                    books.append({"id": b["id"], "title": b["title"], "premise": b["premise"],
                                  "chapters": c.execute("SELECT COUNT(*) FROM chapters WHERE book_id=?", (b["id"],)).fetchone()[0],
                                  "cards": c.execute("SELECT COUNT(*) FROM cards WHERE book_id=?", (b["id"],)).fetchone()[0],
                                  "words": book_words(c, b["id"])})
                loose = [dict(r) for r in c.execute("SELECT * FROM cards WHERE book_id IS NULL AND user_id=? ORDER BY id DESC", (uid,)).fetchall()]
                return self._json(200, {"books": books, "loose": loose})
            m = re.match(r"/api/books/(\d+)$", p)
            if m:
                bid = int(m.group(1))
                b = self._own_book(c, uid, bid)
                if not b:
                    return self._json(404, {"error": "not found"})
                d = dict(b)
                d["chapters"] = [dict(r) for r in c.execute("SELECT * FROM chapters WHERE book_id=? ORDER BY idx,id", (bid,)).fetchall()]
                d["cards"] = [dict(r) for r in c.execute("SELECT * FROM cards WHERE book_id=? ORDER BY id DESC", (bid,)).fetchall()]
                return self._json(200, d)
            m = re.match(r"/api/export/(\d+)$", p)
            if m:
                bid = int(m.group(1))
                b = self._own_book(c, uid, bid)
                if not b:
                    return self._send(404, b"not found", "text/plain")
                md = [f"# {b['title']}\n"]
                if b["premise"]:
                    md.append(f"> {b['premise']}\n")
                for ch in c.execute("SELECT * FROM chapters WHERE book_id=? ORDER BY idx,id", (bid,)).fetchall():
                    md.append(f"\n## {ch['title'] or 'Untitled'}\n\n{ch['body'] or ''}\n")
                fn = re.sub(r"[^0-9A-Za-z]+", "-", b["title"]).strip("-") or "book"
                return self._send(200, "\n".join(md), "text/markdown; charset=utf-8",
                                  {"Content-Disposition": f'attachment; filename="{fn}.md"'})
            return self._send(404, b"not found", "text/plain")
        finally:
            c.close()

    def do_POST(self):
        p = self._p()
        b = self._body()
        c = db()
        try:
            # ---- auth (no session required) ----
            if p == "/api/auth/signup":
                email = (b.get("email") or "").strip().lower()
                pw = b.get("password") or ""
                if "@" not in email or "." not in email or len(pw) < 6:
                    return self._json(400, {"error": "Enter a valid email and a password of at least 6 characters."})
                if c.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
                    return self._json(409, {"error": "That email already has an account — try logging in."})
                salt, h = hash_pw(pw)
                uid = c.execute("INSERT INTO users(email,pw_hash,pw_salt,created) VALUES(?,?,?,?)",
                                (email, h, salt, now())).lastrowid
                # the very first account adopts any pre-auth (orphan) books/sparks
                if c.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1:
                    c.execute("UPDATE books SET user_id=? WHERE user_id IS NULL", (uid,))
                    c.execute("UPDATE cards SET user_id=? WHERE user_id IS NULL", (uid,))
                tok = secrets.token_urlsafe(32)
                c.execute("INSERT INTO sessions(token,user_id,created) VALUES(?,?,?)", (tok, uid, now()))
                c.commit()
                return self._send(200, json.dumps({"user": {"email": email}}),
                                  "application/json", {"Set-Cookie": self._set_cookie(tok)})

            if p == "/api/auth/login":
                email = (b.get("email") or "").strip().lower()
                pw = b.get("password") or ""
                row = c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
                if not row or not verify_pw(pw, row["pw_salt"], row["pw_hash"]):
                    return self._json(400, {"error": "Wrong email or password."})
                tok = secrets.token_urlsafe(32)
                c.execute("INSERT INTO sessions(token,user_id,created) VALUES(?,?,?)", (tok, row["id"], now()))
                c.commit()
                return self._send(200, json.dumps({"user": {"email": email}}),
                                  "application/json", {"Set-Cookie": self._set_cookie(tok)})

            if p == "/api/auth/logout":
                for part in (self.headers.get("Cookie", "") or "").split(";"):
                    if "=" in part:
                        k, v = part.strip().split("=", 1)
                        if k == "ink_sess":
                            c.execute("DELETE FROM sessions WHERE token=?", (v,)); c.commit()
                return self._send(200, json.dumps({"ok": True}),
                                  "application/json", {"Set-Cookie": self._set_cookie("", clear=True)})

            # ---- everything below needs a session ----
            u = self._user(c)
            if not u:
                return self._json(401, {"error": "Please log in."})
            uid = u["id"]

            if p == "/api/books":
                cur = c.execute("INSERT INTO books(user_id,title,premise,voice_sample,created) VALUES(?,?,?,?,?)",
                                (uid, b.get("title", "Untitled"), b.get("premise", ""), b.get("voice_sample", ""), now()))
                c.commit()
                return self._json(200, {"id": cur.lastrowid})

            if p == "/api/chapters":
                cid = b.get("id")
                if cid:
                    ch = c.execute("SELECT book_id FROM chapters WHERE id=?", (cid,)).fetchone()
                    if not ch or not self._own_book(c, uid, ch["book_id"]):
                        return self._json(403, {"error": "not yours"})
                    c.execute("UPDATE chapters SET title=?,body=? WHERE id=?",
                              (b.get("title", ""), b.get("body", ""), cid))
                else:
                    if not self._own_book(c, uid, b.get("book_id")):
                        return self._json(403, {"error": "not yours"})
                    idx = c.execute("SELECT COALESCE(MAX(idx),-1)+1 FROM chapters WHERE book_id=?", (b.get("book_id"),)).fetchone()[0]
                    cur = c.execute("INSERT INTO chapters(book_id,idx,title,body,created) VALUES(?,?,?,?,?)",
                                    (b.get("book_id"), idx, b.get("title", ""), b.get("body", ""), now()))
                    cid = cur.lastrowid
                c.commit()
                return self._json(200, {"id": cid})

            if p == "/api/cards":
                if b.get("book_id") and not self._own_book(c, uid, b.get("book_id")):
                    return self._json(403, {"error": "not yours"})
                cur = c.execute("INSERT INTO cards(user_id,book_id,kind,text,created) VALUES(?,?,?,?,?)",
                                (uid, b.get("book_id"), b.get("kind", "spark"), b.get("text", ""), now()))
                c.commit()
                return self._json(200, {"id": cur.lastrowid})

            if p == "/api/say":
                if not self._own_book(c, uid, b.get("book_id")):
                    return self._json(403, {"error": "not yours"})
                return self._say(c, b)

            if p == "/api/tend":
                if not self._own_book(c, uid, b.get("book_id")):
                    return self._json(403, {"error": "not yours"})
                return self._tend(c, b)

            return self._send(404, b"not found", "text/plain")
        finally:
            c.close()

    def do_DELETE(self):
        p = self._p()
        c = db()
        try:
            u = self._user(c)
            if not u:
                return self._json(401, {"error": "Please log in."})
            uid = u["id"]
            m = re.match(r"/api/books/(\d+)$", p)
            if m:
                bid = int(m.group(1))
                if not self._own_book(c, uid, bid):
                    return self._json(403, {"error": "not yours"})
                for t in ("chapters", "cards", "messages"):
                    c.execute(f"DELETE FROM {t} WHERE book_id=?", (bid,))
                c.execute("DELETE FROM books WHERE id=?", (bid,))
                c.commit()
                return self._json(200, {"ok": True})
            m = re.match(r"/api/cards/(\d+)$", p)
            if m:
                c.execute("DELETE FROM cards WHERE id=? AND user_id=?", (int(m.group(1)), uid))
                c.commit()
                return self._json(200, {"ok": True})
            m = re.match(r"/api/chapters/(\d+)$", p)
            if m:
                ch = c.execute("SELECT book_id FROM chapters WHERE id=?", (int(m.group(1)),)).fetchone()
                if ch and self._own_book(c, uid, ch["book_id"]):
                    c.execute("DELETE FROM chapters WHERE id=?", (int(m.group(1)),))
                    c.commit()
                return self._json(200, {"ok": True})
            return self._send(404, b"not found", "text/plain")
        finally:
            c.close()

    # ---- the Keeper turns ----
    def _log(self, c, bid, cid, role, mode, text):
        c.execute("INSERT INTO messages(book_id,chapter_id,role,mode,text,created) VALUES(?,?,?,?,?,?)",
                  (bid, cid, role, mode, text, now()))

    def _say(self, c, b):
        bid, cid, mode = b.get("book_id"), b.get("chapter_id"), b.get("mode", "muse")
        text = (b.get("text") or "").strip()
        if not text:
            return self._json(400, {"error": "say something"})
        if not GEMINI_KEY:
            return self._json(200, {"error": "The Keeper is offline (no AI key configured)."})
        self._log(c, bid, cid, "writer", mode, text)
        context = ctx_for(c, bid, cid)

        if mode == "draft":
            prompt = (KEEPER + "\n\nCONTEXT:\n" + context +
                      "\n\nTHE WRITER JUST SAID (their direction for what to write next):\n\"" + text + "\"\n\n"
                      "Write that next passage of the manuscript — prose only, ready to drop straight into the "
                      "chapter, continuing naturally from where it left off, in the writer's voice. Roughly one to "
                      "three paragraphs unless they asked for more or less. Output ONLY the prose: no preamble, no "
                      "quotation marks around it, no notes.")
            draft = gemini(prompt, temperature=0.95)
            if not draft:
                return self._json(200, {"error": "The Keeper couldn't draft that — try again."})
            draft = draft.strip().strip('"')
            self._log(c, bid, cid, "keeper", "draft", draft); c.commit()
            return self._json(200, {"draft": draft, "note": "Here's a draft — add it or discard it."})

        if mode == "revise":
            sel = (b.get("selection") or "").strip()
            if not sel:
                return self._json(200, {"error": "Select the passage to revise first."})
            prompt = (KEEPER + "\n\nCONTEXT:\n" + context +
                      "\n\nThe writer selected this passage:\n\"\"\"\n" + sel + "\n\"\"\"\n\n"
                      "Their instruction: \"" + text + "\"\n\n"
                      "Rewrite the selected passage accordingly, in their voice. Output ONLY the revised passage.")
            draft = gemini(prompt, temperature=0.85)
            if not draft:
                return self._json(200, {"error": "The Keeper couldn't revise that — try again."})
            draft = draft.strip().strip('"')
            self._log(c, bid, cid, "keeper", "revise", draft); c.commit()
            return self._json(200, {"draft": draft})

        # muse (default)
        prompt = (KEEPER + "\n\nCONTEXT:\n" + context +
                  "\n\nTHE WRITER JUST SAID:\n\"" + text + "\"\n\n"
                  "Respond as the Keeper in 2-4 sentences. Think WITH them about the idea; nurture it; where it "
                  "genuinely helps, ask one sharp, specific question that opens the idea further. Reference their "
                  "earlier notes when relevant. Prose only, no lists.")
        reply = gemini(prompt, temperature=0.9)
        if not reply:
            return self._json(200, {"error": "The Keeper went quiet — try again."})
        reply = reply.strip()
        self._log(c, bid, cid, "keeper", "muse", reply); c.commit()
        return self._json(200, {"reply": reply})

    def _tend(self, c, b):
        bid = b.get("book_id")
        if not GEMINI_KEY:
            return self._json(200, {"error": "The Keeper is offline (no AI key configured)."})
        cards = c.execute("SELECT text FROM cards WHERE book_id=? ORDER BY id", (bid,)).fetchall()
        chaps = c.execute("SELECT title,body FROM chapters WHERE book_id=? ORDER BY idx,id", (bid,)).fetchall()
        bk = c.execute("SELECT * FROM books WHERE id=?", (bid,)).fetchone()
        if not bk:
            return self._json(404, {"error": "not found"})
        summary = [f"BOOK: {bk['title']}\nPREMISE: {bk['premise'] or '(none)'}"]
        if cards:
            summary.append("IDEA-CARDS:\n" + "\n".join("- " + r["text"][:240] for r in cards))
        if chaps:
            summary.append("CHAPTERS (openings):\n" + "\n".join(
                f"- {ch['title'] or 'untitled'}: {(ch['body'] or '')[:220]}" for ch in chaps))
        if not cards and not chaps:
            return self._json(200, {"text": "There's little in the stacks yet. Capture a few sparks or draft a scene, and I'll find the threads between them."})
        prompt = (KEEPER + "\n\nYou are tending the stacks for this book:\n\n" + "\n\n".join(summary) +
                  "\n\nIn your warm, specific voice (a short paragraph, no lists, no headings): surface the genuine "
                  "connections and threads running between these ideas, name the one gap or unanswered question most "
                  "worth pursuing, and suggest the single most promising next move. Reference the actual ideas by name. "
                  "No generic writing advice.")
        text = gemini(prompt, temperature=0.85)
        return self._json(200, {"text": (text or "").strip()} if text else {"error": "The Keeper couldn't tend just now."})

    def log_message(self, *a):
        pass

if __name__ == "__main__":
    init_db()
    print(f"inkling on :{PORT}  base={BASE or '/'}  keeper={'on' if GEMINI_KEY else 'OFF'}  db={DB}")
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
