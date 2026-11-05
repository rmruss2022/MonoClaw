/**
 * Browser remote — the phone's TV tab, as a web page, so the whole cast flow is
 * testable with zero native app. Signs in with the openhome account (proxied
 * server-side through the control-plane to dodge CORS), searches, and casts a
 * title to a paired stick (e.g. the /mock browser stick with code 000000).
 */
export function remotePage(): string {
  return `<!doctype html><html lang="en"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>openhome TV · Remote</title>
<style>
  :root{--bg:#0e1014;--panel:#171a21;--line:#272c37;--text:#e7ebf3;--muted:#8b93a7;--accent:#3ddc97;--dim:#1f7a56}
  *{box-sizing:border-box}html,body{margin:0;min-height:100%}
  body{background:radial-gradient(1000px 700px at 50% -10%,#141821,var(--bg));color:var(--text);
    font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;padding:22px;max-width:620px;margin:0 auto}
  .brand{display:flex;align-items:center;gap:10px;font-weight:800;font-size:20px;margin-bottom:18px}
  .dot{width:10px;height:10px;border-radius:50%;background:var(--accent);box-shadow:0 0 10px var(--accent)}
  input{width:100%;padding:13px 14px;border-radius:12px;border:1px solid var(--line);background:#0e1014;color:var(--text);font-size:16px;margin-bottom:10px}
  .btn{background:var(--accent);color:#05251a;font-weight:800;border:0;border-radius:12px;padding:12px 18px;font-size:15px;cursor:pointer}
  .card{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:18px;margin-bottom:16px}
  .sticks{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px}
  .chip{padding:7px 12px;border:1px solid var(--line);border-radius:999px;font-size:13px;font-weight:700;color:var(--muted);cursor:pointer;background:var(--panel)}
  .chip.on{color:var(--accent);border-color:var(--dim);background:rgba(61,220,151,.1)}
  .row{display:flex;gap:12px;align-items:center;background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:10px;margin-bottom:8px}
  .row img{width:46px;height:68px;border-radius:8px;object-fit:cover;background:#0f1216;border:1px solid var(--line)}
  .row .nm{font-weight:600}.row .mt{font-size:12px;color:var(--muted)}
  .cast{margin-left:auto;background:rgba(61,220,151,.1);border:1px solid var(--dim);color:var(--accent);font-weight:800;border-radius:999px;padding:8px 16px;cursor:pointer}
  .toast{position:fixed;left:50%;bottom:24px;transform:translateX(-50%);background:var(--panel);border:1px solid var(--dim);border-radius:999px;padding:12px 18px;font-weight:700;opacity:0;transition:.2s}
  .toast.show{opacity:1}
  .muted{color:var(--muted);font-size:13px}
  #app{display:none}
</style></head>
<body>
  <div class="brand"><span class="dot"></span>openhome TV · Remote</div>

  <div class="card" id="login">
    <p class="muted" style="margin-top:0">Sign in with your openhome account to cast.</p>
    <input id="email" type="email" placeholder="you@email.com" autocapitalize="off"/>
    <input id="pw" type="password" placeholder="password"/>
    <button class="btn" onclick="signin()">Sign in</button>
    <div class="muted" id="lerr" style="color:#ff6b6b;margin-top:8px"></div>
  </div>

  <div id="app">
    <div class="card">
      <div class="muted" style="margin-bottom:8px">Cast to</div>
      <div class="sticks" id="sticks"></div>
      <div class="muted" id="nostick" style="display:none">No stick paired yet. Open <b>/mock</b> in another tab and it pairs with code <b>000000</b> automatically.</div>
    </div>
    <input id="q" placeholder="Search movies, shows…" onkeydown="if(event.key==='Enter')doSearch()"/>
    <div id="results"></div>
  </div>
  <div class="toast" id="toast"></div>

<script>
const BASE=location.origin; let TOKEN=null, STICK=null;
const $=id=>document.getElementById(id);
function toast(m){const t=$("toast");t.textContent=m;t.classList.add("show");setTimeout(()=>t.classList.remove("show"),2200);}
async function signin(){
  $("lerr").textContent="";
  const r=await fetch(BASE+"/remote/login",{method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({email:$("email").value.trim(),password:$("pw").value})}).then(r=>r.json()).catch(()=>({ok:false}));
  if(!r.ok){$("lerr").textContent=r.error==="bad_login"?"Wrong email or password.":r.error==="no_home"?"No home paired to this account.":"Couldn't sign in.";return;}
  TOKEN=r.homeToken; $("login").style.display="none"; $("app").style.display="block";
  loadSticks(); doSearch();
}
async function loadSticks(){
  const d=await fetch(BASE+"/sticks",{headers:{Authorization:"Bearer "+TOKEN}}).then(r=>r.json()).catch(()=>({sticks:[]}));
  const list=d.sticks||[];
  if(!list.length){$("nostick").style.display="block";$("sticks").innerHTML="";return;}
  $("nostick").style.display="none";
  STICK=STICK||(list.find(s=>s.online)||list[0]).id;
  $("sticks").innerHTML=list.map(s=>\`<span class="chip \${s.id===STICK?'on':''}" onclick="pick('\${s.id}')">\${s.online?'● ':'○ '}\${esc(s.name)}</span>\`).join('');
}
function pick(id){STICK=id;loadSticks();}
async function doSearch(){
  const q=$("q").value.trim();
  const d=await fetch(BASE+"/"+(q?"search?q="+encodeURIComponent(q):"trending")).then(r=>r.json()).catch(()=>({results:[]}));
  $("results").innerHTML=(d.results||[]).map(t=>\`<div class="row">
    <img src="\${t.poster||''}" onerror="this.style.visibility='hidden'"/>
    <div><div class="nm">\${esc(t.name)}</div><div class="mt">\${t.year||''} · \${(t.sources||[]).map(s=>s.serviceName).slice(0,3).join(', ')||'—'}</div></div>
    <button class="cast" onclick='cast(\${JSON.stringify(t.id)},\${JSON.stringify(t.name)})'>Cast</button></div>\`).join('');
}
async function cast(id,name){
  if(!STICK){toast("Pair a stick first");loadSticks();return;}
  const r=await fetch(BASE+"/route",{method:"POST",headers:{"Content-Type":"application/json",Authorization:"Bearer "+TOKEN},
    body:JSON.stringify({titleId:id,stickId:STICK})}).then(r=>r.json()).catch(()=>({ok:false}));
  toast(r.ok?("▶ "+name+" → "+(r.castTo||'TV')):(r.reason||"Couldn't cast"));
  loadSticks();
}
function esc(s){return (s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
</script></body></html>`;
}
