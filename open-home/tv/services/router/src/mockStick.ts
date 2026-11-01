/**
 * Browser mock stick — a test "TV" you open in a tab. Pairs with the fixed code
 * 000000 (stick id "stick-mock"), reports a full app inventory, listens on the
 * SSE control channel, and when you Cast a title from the app it pops a
 * full-screen "now playing" card and opens the service's deep link. Lets you test
 * the whole search → cast → launch flow with no hardware.
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
  .pairbox{background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:24px;max-width:560px;margin-bottom:28px}
  .pairbox h2{margin:0 0 8px;font-size:18px}
  .pairbox p{color:var(--muted);margin:0 0 14px;font-size:14px;line-height:1.5}
  .code{font-size:64px;font-weight:900;letter-spacing:14px;color:var(--accent);text-align:center;margin:6px 0}
  .rail-title{color:var(--muted);text-transform:uppercase;letter-spacing:1px;font-size:13px;font-weight:700;margin:0 0 12px}
  .rail{display:flex;gap:14px;overflow-x:auto;padding-bottom:10px}
  .card{width:150px;flex:0 0 auto}
  .poster{width:150px;height:220px;border-radius:12px;background:var(--panel);border:1px solid var(--line);object-fit:cover;display:block}
  .cname{font-size:13px;font-weight:600;margin-top:8px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .cmeta{font-size:11px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  /* launch overlay */
  .ov{position:fixed;inset:0;background:rgba(5,6,8,.92);display:none;align-items:center;justify-content:center;z-index:50;padding:24px}
  .ov.show{display:flex}
  .nowcard{display:flex;gap:26px;align-items:center;max-width:820px;width:100%}
  .nowcard img{width:240px;height:356px;border-radius:16px;object-fit:cover;border:1px solid var(--line);box-shadow:0 20px 60px rgba(0,0,0,.6)}
  .nowmeta h1{margin:0 0 6px;font-size:34px;letter-spacing:-.5px}
  .nowmeta .svc{display:inline-block;background:var(--accent);color:#05251a;font-weight:800;border-radius:999px;padding:6px 14px;margin:10px 0}
  .nowmeta p{color:var(--muted);margin:6px 0 18px}
  .btn{display:inline-block;background:var(--accent);color:#05251a;font-weight:800;border:0;border-radius:12px;padding:14px 22px;font-size:16px;cursor:pointer;text-decoration:none}
  .btn.ghost{background:transparent;border:1px solid var(--line);color:var(--text);margin-left:10px}
</style></head>
<body>
  <div class="top">
    <div class="brand"><span class="dot"></span>openhome TV <span style="color:var(--muted);font-weight:600;font-size:14px">· Mock Stick</span></div>
    <div class="status" id="status">starting…</div>
  </div>

  <div class="pairbox" id="pairbox">
    <h2>Pair this TV</h2>
    <p>In the openhome app → <b>TV</b> tab, enter this code to pair, then <b>Cast</b> a title — it'll pop up here.</p>
    <div class="code" id="code">000000</div>
  </div>

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
        <button class="btn ghost" onclick="document.getElementById('ov').classList.remove('show')">Back to TV</button>
      </div>
    </div>
  </div>

<script>
const BASE=location.origin, STICK="stick-mock";
const INSTALLED=["netflix","prime","hbomax","disney","hulu","appletv","youtube","peacock","paramount","tubi","plex","spotify"];
const OWNED=["netflix","hbomax","disney","prime","spotify"];
let TOKEN=null;
const $=id=>document.getElementById(id);
async function boot(){
  try{
    // pair with the fixed code 000000
    const pr=await fetch(BASE+"/sticks/pair/begin",{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({stickId:STICK,name:"Mock TV (browser)",code:"000000"})}).then(r=>r.json());
    TOKEN=pr.stickToken; $("code").textContent=pr.code||"000000";
    // report installed apps / subscriptions so routing works
    await fetch(BASE+"/stick/"+STICK+"/apps",{method:"POST",
      headers:{"Content-Type":"application/json","Authorization":"Bearer "+TOKEN},
      body:JSON.stringify({installed:INSTALLED,owned:OWNED})});
    // trending rail
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
function launch(cmd){
  $("np_title").textContent=cmd.title.name;
  $("np_poster").src=cmd.title.poster||'';
  $("np_svc").textContent="▶ "+(cmd.service||'').toUpperCase();
  $("np_sub").textContent="Opening "+(cmd.service||'the app')+" to this title…";
  const a=$("np_open"); a.href=cmd.deepLink||'#'; a.textContent="▶ Play on "+(cmd.service||'app');
  $("ov").classList.add("show");
  // report now-playing back up so the phone sees it
  fetch(BASE+"/stick/"+STICK+"/event",{method:"POST",headers:{"Content-Type":"application/json","Authorization":"Bearer "+TOKEN},
    body:JSON.stringify({title:cmd.title.name,service:cmd.service,playing:true,ts:Date.now()})}).catch(()=>{});
  // try to actually open it (real services open their web player)
  try{ window.open(cmd.deepLink, "_blank", "noopener"); }catch(_){}
}
function esc(s){return (s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
boot();
</script></body></html>`;
}
