/**
 * Browser mock stick — a Roku-style "TV" you open in a tab. Pairs with the fixed
 * code 000000 (stick id "stick-mock"), reports its app inventory, and listens on
 * the SSE control channel. It presents an app home screen (tiles you "sign into"
 * and launch) plus a trending rail. When a title is cast from the phone/remote it
 * either plays INLINE (YouTube, and self-hosted Plex/Jellyfin — the sources that
 * permit embedding) or, for the DRM services (Netflix, Prime, Disney+, Max, …)
 * which block web embedding, it shows a launch screen and hands off to the app —
 * exactly how a real streaming stick behaves.
 */
export function mockStickPage(): string {
  return `<!doctype html><html lang="en"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>openhome TV · Mock Stick</title>
<style>
  :root{--bg:#0e1014;--panel:#171a21;--line:#272c37;--text:#e7ebf3;--muted:#8b93a7;--accent:#3ddc97}
  *{box-sizing:border-box}html,body{margin:0;height:100%}
  body{background:radial-gradient(1200px 800px at 50% -10%,#141821,var(--bg));color:var(--text);
    font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;padding:28px}
  .brand{display:flex;align-items:center;gap:10px;font-weight:800;font-size:22px;letter-spacing:-.5px}
  .dot{width:11px;height:11px;border-radius:50%;background:var(--accent);box-shadow:0 0 12px var(--accent)}
  .status{color:var(--accent);font-weight:600;margin-left:auto;font-size:14px}
  .top{display:flex;align-items:center;gap:12px;margin-bottom:22px}
  .pairbox{background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:20px 24px;max-width:560px;margin-bottom:26px}
  .pairbox h2{margin:0 0 8px;font-size:18px}
  .pairbox p{color:var(--muted);margin:0 0 12px;font-size:14px;line-height:1.5}
  .code{font-size:56px;font-weight:900;letter-spacing:12px;color:var(--accent);text-align:center;margin:4px 0}
  .rail-title{color:var(--muted);text-transform:uppercase;letter-spacing:1px;font-size:13px;font-weight:700;margin:22px 0 12px}
  /* app grid (Roku home) */
  .apps{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:14px;max-width:1100px}
  .app{position:relative;border-radius:14px;height:94px;display:flex;align-items:center;justify-content:center;
    font-weight:800;font-size:18px;color:#fff;cursor:pointer;border:1px solid rgba(255,255,255,.08);
    text-shadow:0 1px 3px rgba(0,0,0,.4);transition:transform .08s ease,box-shadow .12s ease;overflow:hidden}
  .app:hover{transform:translateY(-2px);box-shadow:0 10px 30px rgba(0,0,0,.45)}
  .app .signin{position:absolute;bottom:6px;left:0;right:0;text-align:center;font-size:10.5px;font-weight:700;
    text-transform:uppercase;letter-spacing:.6px}
  .app .signin.yes{color:rgba(255,255,255,.92)}
  .app .signin.no{color:rgba(255,255,255,.72);text-decoration:underline}
  .rail{display:flex;gap:14px;overflow-x:auto;padding-bottom:10px}
  .card{width:140px;flex:0 0 auto;cursor:pointer}
  .poster{width:140px;height:206px;border-radius:12px;background:var(--panel);border:1px solid var(--line);object-fit:cover;display:block}
  .cname{font-size:13px;font-weight:600;margin-top:8px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .cmeta{font-size:11px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  /* launch / player overlay */
  .ov{position:fixed;inset:0;background:rgba(5,6,8,.96);display:none;z-index:50}
  .ov.show{display:flex;align-items:center;justify-content:center;padding:24px}
  .nowcard{display:flex;gap:26px;align-items:center;max-width:820px;width:100%}
  .nowcard img{width:220px;height:326px;border-radius:16px;object-fit:cover;border:1px solid var(--line);box-shadow:0 20px 60px rgba(0,0,0,.6)}
  .nowmeta h1{margin:0 0 6px;font-size:32px;letter-spacing:-.5px}
  .nowmeta .svc{display:inline-block;color:#fff;font-weight:800;border-radius:999px;padding:6px 14px;margin:10px 0}
  .nowmeta p{color:var(--muted);margin:6px 0 18px;max-width:420px}
  .btn{display:inline-block;background:var(--accent);color:#05251a;font-weight:800;border:0;border-radius:12px;padding:13px 20px;font-size:15px;cursor:pointer;text-decoration:none}
  .btn.ghost{background:transparent;border:1px solid var(--line);color:var(--text);margin-left:10px}
  .player{position:fixed;inset:0;background:#000;display:none;z-index:60}
  .player.show{display:block}
  .player iframe{width:100%;height:100%;border:0}
  .player .x{position:absolute;top:16px;right:18px;z-index:61;background:rgba(0,0,0,.6);border:1px solid #333;color:#fff;border-radius:10px;padding:8px 14px;cursor:pointer;font-weight:700}
</style></head>
<body>
  <div class="top">
    <div class="brand"><span class="dot"></span>openhome TV <span style="color:var(--muted);font-weight:600;font-size:14px">· Mock Stick</span></div>
    <div class="status" id="status">starting…</div>
  </div>

  <div class="pairbox" id="pairbox">
    <h2>Pair this TV</h2>
    <p>In the openhome app → <b>TV</b> tab, enter this code to pair, then <b>Cast</b> a title — or tap an app below.</p>
    <div class="code" id="code">000000</div>
  </div>

  <p class="rail-title">Your apps</p>
  <div class="apps" id="apps"></div>

  <p class="rail-title">Trending</p>
  <div class="rail" id="rail"></div>

  <div class="ov" id="ov">
    <div class="nowcard">
      <img id="np_poster" alt=""/>
      <div class="nowmeta">
        <h1 id="np_title">—</h1>
        <div class="svc" id="np_svc">—</div>
        <p id="np_sub">Casting from your phone…</p>
        <a class="btn" id="np_open" target="_blank" rel="noopener">▶ Play</a>
        <button class="btn ghost" onclick="hideOv()">Back to TV</button>
      </div>
    </div>
  </div>

  <div class="player" id="player">
    <button class="x" onclick="closePlayer()">✕ Close</button>
    <iframe id="pframe" allow="autoplay; encrypted-media; fullscreen" allowfullscreen></iframe>
  </div>

<script>
const BASE=location.origin, STICK="stick-mock";
// id -> {name, color, home}. "home" is where "open app"/"sign in" sends you.
const APPS={
  netflix:{name:"Netflix",color:"#E50914",home:"https://www.netflix.com"},
  prime:{name:"Prime Video",color:"#00A8E1",home:"https://www.primevideo.com"},
  disney:{name:"Disney+",color:"#113CCF",home:"https://www.disneyplus.com"},
  hbomax:{name:"Max",color:"#0046FF",home:"https://www.max.com"},
  hulu:{name:"Hulu",color:"#1CE783",home:"https://www.hulu.com"},
  appletv:{name:"Apple TV",color:"#333",home:"https://tv.apple.com"},
  youtube:{name:"YouTube",color:"#FF0000",home:"https://www.youtube.com",embed:true},
  peacock:{name:"Peacock",color:"#111",home:"https://www.peacocktv.com"},
  paramount:{name:"Paramount+",color:"#0064FF",home:"https://www.paramountplus.com"},
  tubi:{name:"Tubi",color:"#FA382F",home:"https://tubitv.com"},
  plex:{name:"Plex",color:"#E5A00D",home:"https://app.plex.tv",embed:true},
  jellyfin:{name:"Jellyfin",color:"#00A4DC",home:"https://jellyfin.org",embed:true},
  spotify:{name:"Spotify",color:"#1DB954",home:"https://open.spotify.com",embed:true},
};
const INSTALLED=Object.keys(APPS);
const OWNED=["netflix","hbomax","disney","prime","spotify","youtube"];
let TOKEN=null;
const $=id=>document.getElementById(id);
const esc=s=>(s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));

// Which apps you've "signed into" on this TV. We can't read a streaming
// service's cross-origin session, so sign-in is tracked here and the actual
// auth lives in your browser's session with that service (just like signing in
// on a real stick, per app).
function signedIn(){try{return JSON.parse(localStorage.getItem("oh_tv_signedin")||"[]");}catch(_){return[];}}
function setSignedIn(list){localStorage.setItem("oh_tv_signedin",JSON.stringify(list));}
function isIn(id){return signedIn().includes(id);}
function toggleSignIn(id,ev){
  ev.stopPropagation();
  const s=signedIn(); const i=s.indexOf(id);
  if(i>=0){s.splice(i,1);} else {s.push(id); window.open(APPS[id].home,"_blank","noopener");}
  setSignedIn(s); renderApps();
}
function openApp(id){
  // Launch the app (its web home) where your session lives — the stick hands off.
  window.open(APPS[id].home,"_blank","noopener");
}
function renderApps(){
  $("apps").innerHTML=INSTALLED.map(id=>{
    const a=APPS[id]; const yes=isIn(id);
    return \`<div class="app" style="background:linear-gradient(145deg,\${a.color},\${a.color}cc)" onclick="openApp('\${id}')">
      <span>\${esc(a.name)}</span>
      <span class="signin \${yes?'yes':'no'}" onclick="toggleSignIn('\${id}',event)">\${yes?'✓ signed in':'sign in'}</span>
    </div>\`;
  }).join('');
}
async function boot(){
  try{
    const pr=await fetch(BASE+"/sticks/pair/begin",{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({stickId:STICK,name:"Mock TV (browser)",code:"000000"})}).then(r=>r.json());
    TOKEN=pr.stickToken; $("code").textContent=pr.code||"000000";
    await fetch(BASE+"/stick/"+STICK+"/apps",{method:"POST",
      headers:{"Content-Type":"application/json","Authorization":"Bearer "+TOKEN},
      body:JSON.stringify({installed:INSTALLED,owned:OWNED})});
    renderApps();
    const tr=await fetch(BASE+"/trending").then(r=>r.json());
    $("rail").innerHTML=(tr.results||[]).map(t=>\`<div class="card">
      <img class="poster" src="\${t.poster||''}" onerror="this.style.visibility='hidden'"/>
      <div class="cname">\${esc(t.name)}</div><div class="cmeta">\${t.year||''} · \${(t.sources||[]).map(s=>s.serviceName).slice(0,2).join(', ')}</div></div>\`).join('');
    connect();
  }catch(e){ $("status").textContent="error: "+(e&&e.message||e); }
}
function connect(){
  const es=new EventSource(BASE+"/stick/"+STICK+"/stream?token="+encodeURIComponent(TOKEN));
  es.addEventListener("ready",()=>{ $("status").textContent="● connected — ready to cast"; $("pairbox").style.opacity=.6; });
  es.addEventListener("launch",ev=>launch(JSON.parse(ev.data)));
  es.addEventListener("error",()=>{ $("status").textContent="reconnecting…"; });
}
function ytId(url){const m=/[?&]v=([^&]+)/.exec(url||'')||/youtu\\.be\\/([^?&]+)/.exec(url||'');return m?m[1]:null;}
function hideOv(){$("ov").classList.remove("show");}
function closePlayer(){$("player").classList.remove("show");$("pframe").src="about:blank";}
function playInline(src){$("pframe").src=src;$("player").classList.add("show");}
function launch(cmd){
  const svc=cmd.service||''; const a=APPS[svc]||{name:svc,color:"#3ddc97"};
  // report now-playing back up so the phone sees it
  fetch(BASE+"/stick/"+STICK+"/event",{method:"POST",headers:{"Content-Type":"application/json","Authorization":"Bearer "+TOKEN},
    body:JSON.stringify({title:cmd.title.name,service:svc,playing:true,ts:Date.now()})}).catch(()=>{});
  // INLINE playback where the platform allows embedding.
  if(svc==="youtube"){ const id=ytId(cmd.deepLink); if(id){ playInline("https://www.youtube.com/embed/"+id+"?autoplay=1"); return; } }
  if((svc==="plex"||svc==="jellyfin") && cmd.deepLink){ playInline(cmd.deepLink); return; }
  // Otherwise (DRM services) show the launch screen and hand off to the app.
  $("np_title").textContent=cmd.title.name;
  $("np_poster").src=cmd.title.poster||'';
  $("np_svc").textContent="▶ "+(a.name||svc).toUpperCase(); $("np_svc").style.background=a.color;
  $("np_sub").textContent=a.name+" uses DRM and can't play inside a browser — opening the app to this title, where you're signed in.";
  const o=$("np_open"); o.href=cmd.deepLink||a.home||'#'; o.textContent="▶ Play in "+(a.name||'app'); o.style.background=a.color; o.style.color="#fff";
  $("ov").classList.add("show");
  try{ window.open(cmd.deepLink||a.home, "_blank", "noopener"); }catch(_){}
}
boot();
</script></body></html>`;
}
