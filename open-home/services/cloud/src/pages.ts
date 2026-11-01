/** Minimal themed sign-in page for the web entrypoint (matches openhome tokens). */
export function signinPage(): string {
  return `<!doctype html><html lang="en"><head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"/>
<title>openhome · sign in</title>
<meta name="theme-color" content="#0e1014"/>
<style>
  :root{--bg:#0e1014;--panel:#171a21;--line:#272c37;--text:#e7ebf3;--muted:#8b93a7;--accent:#3ddc97}
  *{box-sizing:border-box}html,body{height:100%}
  body{margin:0;background:radial-gradient(1200px 900px at 50% -5%,#141821,var(--bg));color:var(--text);
    font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    display:flex;align-items:center;justify-content:center;padding:24px}
  .card{width:100%;max-width:360px;background:var(--panel);border:1px solid var(--line);
    border-radius:18px;padding:28px 24px}
  .brand{display:flex;align-items:center;gap:10px;margin-bottom:6px;font-weight:700;font-size:18px}
  .dot{width:11px;height:11px;border-radius:50%;background:var(--accent);box-shadow:0 0 12px var(--accent)}
  p.sub{margin:0 0 20px;color:var(--muted);font-size:13px}
  label{display:block;font-size:12px;color:var(--muted);margin:12px 0 6px}
  input{width:100%;padding:13px 14px;border-radius:12px;border:1px solid var(--line);
    background:#0e1014;color:var(--text);font-size:16px;outline:none}
  input:focus{border-color:var(--accent)}
  button{margin-top:18px;width:100%;padding:13px;border:0;border-radius:12px;background:var(--accent);
    color:#05251a;font-weight:700;font-size:15px;cursor:pointer}
  .ghost{margin-top:9px;background:transparent;border:1px solid var(--line);color:var(--text)}
  .err{color:#ff6b6b;font-size:13px;margin:12px 0 0;min-height:16px}
  .foot{margin-top:18px;color:var(--muted);font-size:11px;text-align:center}
</style></head>
<body>
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
</script>
</body></html>`;
}
