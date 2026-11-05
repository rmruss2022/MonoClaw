/** Minimal themed sign-in page for the web entrypoint (matches openhome tokens). */
export function signinPage(): string {
  return `<!doctype html><html lang="en"><head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"/>
<title>openhome · sign in</title>
<meta name="theme-color" content="#0b0a12"/>
<style>
  :root{--bg:#0b0a12;--panel:#181527;--line:#2a2540;--text:#ece9f5;--muted:#9a93b8;--accent:#f5c977;--purple:#a855f7;
    --serif:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,"Times New Roman",serif}
  *{box-sizing:border-box}html,body{height:100%}
  body{margin:0;background:radial-gradient(1200px 900px at 50% -5%,#140f22,var(--bg));color:var(--text);
    font:15px/1.5 ui-rounded,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,system-ui,sans-serif;
    display:flex;align-items:center;justify-content:center;padding:24px}
  .stars{position:fixed;inset:0;z-index:-1;pointer-events:none}
  .card{width:100%;max-width:360px;background:rgba(24,21,39,.78);backdrop-filter:blur(8px);border:1px solid var(--line);
    border-radius:20px;padding:28px 24px;box-shadow:0 24px 70px rgba(0,0,0,.5),0 0 0 1px rgba(168,85,247,.08)}
  .brand{display:flex;align-items:center;gap:10px;margin-bottom:6px;font-weight:600;font-size:22px;font-family:var(--serif);letter-spacing:.2px}
  .dot{width:11px;height:11px;border-radius:50%;background:var(--accent);box-shadow:0 0 14px var(--accent)}
  p.sub{margin:0 0 20px;color:var(--muted);font-size:13px}
  label{display:block;font-size:12px;color:var(--muted);margin:12px 0 6px}
  input{width:100%;padding:13px 14px;border-radius:12px;border:1px solid var(--line);
    background:#0b0a12;color:var(--text);font-size:16px;outline:none}
  input:focus{border-color:var(--accent);box-shadow:0 0 0 3px rgba(245,201,119,.15)}
  button{margin-top:18px;width:100%;padding:13px;border:0;border-radius:12px;
    background:linear-gradient(180deg,#f7d58c,var(--accent));color:#2a1e05;font-weight:800;font-size:15px;cursor:pointer;
    box-shadow:0 10px 30px rgba(245,201,119,.22)}
  .ghost{margin-top:9px;background:transparent;border:1px solid var(--line);color:var(--text);box-shadow:none}
  .err{color:#ff6b6b;font-size:13px;margin:12px 0 0;min-height:16px}
  .foot{margin-top:18px;color:var(--muted);font-size:11px;text-align:center;letter-spacing:.3px}
</style></head>
<body>
  <canvas class="stars"></canvas>
  <div class="card">
    <div class="brand"><span class="dot"></span>openhome</div>
    <p class="sub" id="sub">Sign in to your home.</p>
    <label for="email">Email</label>
    <input id="email" type="email" autocomplete="username" autocapitalize="none"/>
    <label for="password">Password</label>
    <input id="password" type="password" autocomplete="current-password"/>
    <button onclick="go('login')">Sign in</button>
    <button class="ghost" onclick="go('signup')">Create account</button>
    <div class="err" id="err"></div>
    <div class="foot">Your home. Your keys.</div>
  </div>
<script>
async function go(mode){
  const email=document.getElementById('email').value.trim();
  const password=document.getElementById('password').value;
  const err=document.getElementById('err'); err.textContent='';
  try{
    const r=await fetch('/api/'+mode,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email,password})});
    const j=await r.json();
    if(!r.ok||!j.ok){err.textContent=j.error||'Something went wrong.';return;}
    // Fetch the routing grant, then hand off to the hub's /sso so the user lands
    // straight in their house — no second passphrase prompt.
    const hr=await fetch('/api/home',{headers:{'Authorization':'Bearer '+j.token}});
    const hj=await hr.json();
    if(hj.ok&&hj.homeToken){
      const base='https://'+String(hj.endpoint).replace(/^https?:\\/\\//,'').replace(/\\/+$/,'');
      const f=document.createElement('form');
      f.method='POST'; f.action=base+'/sso';
      const i=document.createElement('input');
      i.type='hidden'; i.name='token'; i.value=hj.homeToken;
      f.appendChild(i); document.body.appendChild(f); f.submit();
    } else {
      document.getElementById('sub').textContent='Signed in. No home paired yet — pair your hub to continue.';
    }
  }catch(e){err.textContent='Could not reach the server.';}
}
(function(){var c=document.querySelector('.stars');if(!c)return;var x=c.getContext('2d');
function rs(){c.width=innerWidth;c.height=innerHeight;}rs();addEventListener('resize',rs);
var st=Array.from({length:60},function(){return{x:Math.random()*c.width,y:Math.random()*c.height,r:Math.random()*1.2+.2,a:Math.random()*6};});
(function loop(){x.clearRect(0,0,c.width,c.height);for(var i=0;i<st.length;i++){var s=st[i];s.a+=0.015;var o=.22+.33*Math.sin(s.a);x.fillStyle='rgba(220,210,255,'+o+')';x.beginPath();x.arc(s.x,s.y,s.r,0,7);x.fill();}requestAnimationFrame(loop);})();})();
</script>
</body></html>`;
}
