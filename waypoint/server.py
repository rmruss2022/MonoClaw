#!/usr/bin/env python3
"""
Waypoint — Matthew's driving GPS + "tell me about the area" companion.

Standalone app: Python stdlib http.server, zero third-party deps, reboot-safe.
All the smarts run client-side against free public APIs (no keys):
  - Map tiles:      CARTO dark basemap + OpenStreetMap
  - Geocoding:      Nominatim (search + reverse)
  - Driving routes: OSRM (turn-by-turn, ETA, distance)
  - Area briefings: Wikipedia geosearch (nearby articles, spoken aloud)

Env:
  WAYPOINT_PORT   (default 18822)
  WAYPOINT_BASE   base path when mounted under the command hub, e.g. "/waypoint"
"""
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("WAYPOINT_PORT", "18822"))
BASE = (os.environ.get("WAYPOINT_BASE", "").rstrip("/"))  # e.g. "/waypoint" or ""

PAGE = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover"/>
<meta name="theme-color" content="#0b0f14"/>
<link rel="manifest" href="__BASE__/manifest.webmanifest"/>
<link rel="apple-touch-icon" href="__BASE__/icon.png"/>
<meta name="apple-mobile-web-app-capable" content="yes"/>
<meta name="mobile-web-app-capable" content="yes"/>
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent"/>
<meta name="apple-mobile-web-app-title" content="Waypoint"/>
<title>Waypoint</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<style>
  :root{ --bg:#0b0f14; --panel:#121820; --panel2:#0e141b; --line:#1e2833; --text:#e8eef5; --dim:#8aa0b4; --accent:#22c55e; --accent2:#38bdf8; --danger:#ef4444; }
  *{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
  html,body{margin:0;height:100%;background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;overflow:hidden}
  #map{position:absolute;inset:0;background:var(--bg);z-index:1}
  .leaflet-container{background:var(--bg)}
  /* Top search bar */
  #topbar{position:absolute;top:0;left:0;right:0;z-index:1000;padding:calc(env(safe-area-inset-top) + 10px) 10px 10px;display:flex;gap:8px;align-items:center}
  #searchWrap{flex:1;display:flex;background:var(--panel);border:1px solid var(--line);border-radius:14px;box-shadow:0 6px 24px rgba(0,0,0,.45);overflow:hidden}
  #q{flex:1;background:transparent;border:0;outline:0;color:var(--text);font-size:16px;padding:13px 14px}
  #q::placeholder{color:var(--dim)}
  #go{background:var(--accent);color:#04120a;border:0;font-weight:700;padding:0 16px;font-size:15px}
  #go:active{filter:brightness(.9)}
  .iconbtn{width:46px;height:46px;flex:0 0 auto;border-radius:13px;background:var(--panel);border:1px solid var(--line);color:var(--text);display:flex;align-items:center;justify-content:center;box-shadow:0 6px 24px rgba(0,0,0,.45)}
  .iconbtn svg{width:22px;height:22px;stroke:currentColor;fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
  .iconbtn.on{color:var(--accent)}
  /* suggestions */
  #sugg{position:absolute;top:calc(env(safe-area-inset-top) + 64px);left:10px;right:10px;z-index:1001;background:var(--panel);border:1px solid var(--line);border-radius:14px;overflow:hidden;box-shadow:0 12px 32px rgba(0,0,0,.5);display:none}
  #sugg div{padding:12px 14px;border-bottom:1px solid var(--line);font-size:15px}
  #sugg div:last-child{border-bottom:0}
  #sugg .s2{color:var(--dim);font-size:12px;margin-top:2px}
  /* right side controls */
  #side{position:absolute;right:10px;top:calc(env(safe-area-inset-top) + 68px);z-index:1000;display:flex;flex-direction:column;gap:8px}
  /* Nav banner (active turn) */
  #nav{position:absolute;top:calc(env(safe-area-inset-top) + 62px);left:10px;right:66px;z-index:999;background:linear-gradient(135deg,#0f2a1a,#123);border:1px solid #1f6f3f;border-radius:16px;padding:12px 14px;display:none;box-shadow:0 10px 30px rgba(0,0,0,.5)}
  #nav .man{font-size:18px;font-weight:700;line-height:1.25}
  #nav .sub{color:var(--dim);font-size:13px;margin-top:3px}
  /* Bottom sheet */
  #sheet{position:absolute;left:0;right:0;bottom:0;z-index:1000;background:var(--panel);border-top:1px solid var(--line);border-radius:20px 20px 0 0;box-shadow:0 -10px 40px rgba(0,0,0,.5);transform:translateY(calc(100% - 92px));transition:transform .28s cubic-bezier(.2,.8,.2,1);max-height:78vh;display:flex;flex-direction:column;padding-bottom:env(safe-area-inset-bottom)}
  #sheet.open{transform:translateY(0)}
  #grip{padding:10px 0 6px;display:flex;justify-content:center}
  #grip .bar{width:44px;height:5px;border-radius:5px;background:#2b3a49}
  #sheetHead{padding:0 16px 10px;display:flex;align-items:center;gap:10px}
  #sheetHead .tt{font-weight:700;font-size:16px;flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  #sheetHead .badge{font-size:12px;color:var(--accent);border:1px solid #1f6f3f;background:#0f2a1a;border-radius:999px;padding:3px 9px}
  #tabs{display:flex;gap:6px;padding:0 12px 8px}
  .tab{flex:1;text-align:center;padding:9px;border-radius:11px;background:var(--panel2);border:1px solid var(--line);color:var(--dim);font-size:13px;font-weight:600}
  .tab.active{color:var(--text);border-color:#2b6cb0;background:#0d2233}
  #body{overflow:auto;padding:4px 14px 18px;-webkit-overflow-scrolling:touch}
  .route-sum{display:flex;gap:14px;align-items:baseline;padding:6px 2px 12px}
  .route-sum .eta{font-size:26px;font-weight:800;color:var(--accent)}
  .route-sum .dist{font-size:15px;color:var(--dim)}
  .route-sum .clear{margin-left:auto;color:var(--danger);font-size:13px;border:1px solid #4c1d1d;background:#1a0f10;border-radius:10px;padding:7px 11px}
  .step{display:flex;gap:12px;padding:11px 4px;border-bottom:1px solid var(--line)}
  .step .n{width:26px;height:26px;flex:0 0 auto;border-radius:8px;background:#0d2233;border:1px solid #24425a;color:var(--accent2);display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700}
  .step .m{font-size:15px}
  .step .d{color:var(--dim);font-size:12px;margin-top:2px}
  .card{background:var(--panel2);border:1px solid var(--line);border-radius:14px;padding:13px;margin:10px 0}
  .card h3{margin:0 0 6px;font-size:16px;display:flex;align-items:center;gap:8px}
  .card .meta{color:var(--dim);font-size:12px;margin-bottom:6px}
  .card p{margin:0;font-size:14px;line-height:1.5;color:#cfe0ee}
  .card .row{display:flex;gap:8px;margin-top:10px}
  .card .row button{flex:1;background:#0d2233;border:1px solid #24425a;color:var(--accent2);border-radius:10px;padding:9px;font-size:13px;font-weight:600}
  .empty{color:var(--dim);text-align:center;padding:26px 10px;font-size:14px;line-height:1.5}
  #toast{position:absolute;bottom:104px;left:50%;transform:translateX(-50%);z-index:2000;background:#0d2233;border:1px solid #24425a;color:var(--text);padding:10px 14px;border-radius:12px;font-size:13px;box-shadow:0 8px 24px rgba(0,0,0,.5);display:none;max-width:82vw;text-align:center}
  .pulse{position:relative}
  .gpsdot{width:18px;height:18px;border-radius:50%;background:var(--accent2);border:3px solid #fff;box-shadow:0 0 0 6px rgba(56,189,248,.25)}
  .leaflet-routeline{filter:drop-shadow(0 0 6px rgba(34,197,94,.5))}
</style>
</head>
<body>
<div id="map"></div>

<div id="topbar">
  <div id="searchWrap">
    <input id="q" placeholder="Where to?" autocomplete="off" enterkeyhint="search"/>
    <button id="go">Go</button>
  </div>
  <button class="iconbtn on" id="voiceBtn" title="Voice on/off" aria-label="Voice">
    <svg viewBox="0 0 24 24"><path d="M3 10v4h4l5 5V5L7 10H3z"/><path d="M16 8a5 5 0 0 1 0 8"/></svg>
  </button>
</div>
<div id="sugg"></div>

<div id="nav"><div class="man" id="navMan">—</div><div class="sub" id="navSub"></div></div>

<div id="side">
  <button class="iconbtn on" id="followBtn" title="Recenter / follow" aria-label="Recenter">
    <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3.2"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/><circle cx="12" cy="12" r="8.5"/></svg>
  </button>
  <button class="iconbtn" id="areaBtn" title="About this area" aria-label="About this area">
    <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 8h.01M11 12h1v4h1"/></svg>
  </button>
</div>

<div id="sheet">
  <div id="grip"><div class="bar"></div></div>
  <div id="sheetHead"><div class="tt" id="sheetTitle">Waypoint</div><div class="badge" id="sheetBadge" style="display:none"></div></div>
  <div id="tabs">
    <div class="tab active" data-tab="area">About the area</div>
    <div class="tab" data-tab="route">Directions</div>
  </div>
  <div id="body"></div>
</div>

<div id="toast"></div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
/* ---------- tiny helpers ---------- */
const $=s=>document.querySelector(s);
const el=(t,c,h)=>{const e=document.createElement(t);if(c)e.className=c;if(h!=null)e.innerHTML=h;return e;};
function toast(m,ms=2600){const t=$('#toast');t.textContent=m;t.style.display='block';clearTimeout(t._t);t._t=setTimeout(()=>t.style.display='none',ms);}
function fmtDist(m){return m>=1609?(m/1609.34).toFixed(m<16093?1:0)+' mi':Math.round(m/0.3048/10)*10+' ft';}
function fmtDur(s){s=Math.round(s);const h=Math.floor(s/3600),m=Math.round((s%3600)/60);return h?`${h} hr ${m} min`:`${m} min`;}
function etaClock(s){const d=new Date(Date.now()+s*1000);let h=d.getHours(),mi=d.getMinutes();const ap=h>=12?'PM':'AM';h=h%12||12;return `${h}:${String(mi).padStart(2,'0')} ${ap}`;}

/* ---------- speech ---------- */
let voiceOn=true;
function speak(text){
  if(!voiceOn||!('speechSynthesis'in window)||!text)return;
  try{const u=new SpeechSynthesisUtterance(text);u.rate=1.0;u.pitch=1.0;u.lang='en-US';speechSynthesis.cancel();speechSynthesis.speak(u);}catch(e){}
}

/* ---------- map ---------- */
const map=L.map('map',{zoomControl:false,attributionControl:false}).setView([40.7128,-74.006],13);
L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',{maxZoom:20,subdomains:'abcd'}).addTo(map);
L.control.attribution({position:'bottomleft',prefix:false}).addAttribution('© OpenStreetMap · CARTO · OSRM · Wikipedia').addTo(map);

const meIcon=L.divIcon({className:'',html:'<div class="gpsdot"></div>',iconSize:[18,18],iconAnchor:[9,9]});
let meMarker=null, destMarker=null, routeLine=null;
let me=null;            // {lat,lon,acc,heading,speed}
let follow=true;
let routeData=null;     // OSRM route
let steps=[];           // flattened maneuvers
let stepIdx=0;
let routeReq=0;         // guards against overlapping/stale route requests
let lastAreaAt=null;    // {lat,lon}
let activeTab='area';

/* ---------- geolocation ---------- */
function startGeo(){
  if(!('geolocation'in navigator)){toast('No geolocation on this device');return;}
  navigator.geolocation.watchPosition(onPos,onGeoErr,{enableHighAccuracy:true,maximumAge:1000,timeout:15000});
}
function onGeoErr(e){toast('Location: '+(e.message||'blocked. Enable location for this site.'),4000);}
function onPos(p){
  const c=p.coords;
  me={lat:c.latitude,lon:c.longitude,acc:c.accuracy,heading:c.heading,speed:c.speed};
  if(!meMarker){meMarker=L.marker([me.lat,me.lon],{icon:meIcon,zIndexOffset:1000}).addTo(map);map.setView([me.lat,me.lon],16);maybeArea(true);}
  else meMarker.setLatLng([me.lat,me.lon]);
  if(follow)map.panTo([me.lat,me.lon],{animate:true,duration:.5});
  if(steps.length)updateNav();
  maybeArea(false);
}

/* ---------- geocoding (Nominatim) ---------- */
async function geocode(q){
  const b=me?`&viewbox=${me.lon-.6},${me.lat+.4},${me.lon+.6},${me.lat-.4}&bounded=0`:'';
  const url=`https://nominatim.openstreetmap.org/search?format=jsonv2&limit=6&addressdetails=1&q=${encodeURIComponent(q)}${b}`;
  const r=await fetch(url,{headers:{'Accept':'application/json'}});
  return r.ok?await r.json():[];
}
async function reverse(lat,lon){
  const url=`https://nominatim.openstreetmap.org/reverse?format=jsonv2&zoom=14&addressdetails=1&lat=${lat}&lon=${lon}`;
  const r=await fetch(url,{headers:{'Accept':'application/json'}});
  return r.ok?await r.json():null;
}

/* ---------- search UI ---------- */
let suggTimer=null;
$('#q').addEventListener('input',e=>{
  const v=e.target.value.trim();clearTimeout(suggTimer);
  if(v.length<3){$('#sugg').style.display='none';return;}
  suggTimer=setTimeout(async()=>{
    try{const res=await geocode(v);renderSugg(res);}catch(_){}
  },350);
});
function renderSugg(res){
  const s=$('#sugg');s.innerHTML='';
  if(!res.length){s.style.display='none';return;}
  res.slice(0,6).forEach(r=>{
    const name=(r.display_name||'').split(',')[0];
    const d=el('div','',`<div>${name}</div><div class="s2">${(r.display_name||'').split(',').slice(1,4).join(', ')}</div>`);
    d.onclick=()=>{$('#q').value=name;s.style.display='none';navigateTo(+r.lat,+r.lon,name);};
    s.appendChild(d);
  });
  s.style.display='block';
}
$('#go').onclick=async()=>{
  const v=$('#q').value.trim();if(!v)return;
  $('#sugg').style.display='none';toast('Finding “'+v+'”…');
  try{const res=await geocode(v);if(!res.length){toast('No match for “'+v+'”');return;}
    const r=res[0];navigateTo(+r.lat,+r.lon,(r.display_name||v).split(',')[0]);}
  catch(e){toast('Search failed');}
};
$('#q').addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();$('#go').click();}});

/* ---------- routing (OSRM) ---------- */
// Reliable public OSRM instances (FOSSGIS first — far less rate-limited than the demo server).
const OSRM_HOSTS=['https://routing.openstreetmap.de/routed-car','https://router.project-osrm.org'];
async function osrmRoute(from,to){
  const path=`/route/v1/driving/${from.lon},${from.lat};${to.lon},${to.lat}?overview=full&geometries=geojson&steps=true`;
  for(let attempt=0;attempt<2;attempt++){
    for(const h of OSRM_HOSTS){
      try{
        const r=await fetch(h+path);
        if(!r.ok)continue;
        const j=await r.json();
        if(j.code==='Ok'&&j.routes&&j.routes.length)return j.routes[0];
      }catch(_){/* try next host */}
    }
    if(attempt===0)await new Promise(res=>setTimeout(res,600));
  }
  return null;
}
async function navigateTo(lat,lon,label){
  const myReq=++routeReq;              // only the newest request may render or error
  if(!me)toast('Waiting for your GPS fix…');
  if(destMarker)map.removeLayer(destMarker);
  destMarker=L.marker([lat,lon]).addTo(map);
  const from=me||{lat:map.getCenter().lat,lon:map.getCenter().lng};
  toast('Routing…');
  const rt=await osrmRoute(from,{lat,lon});
  if(myReq!==routeReq)return;          // a newer search superseded this one — stay silent
  if(!rt){toast('No route found — try adding a street name or city');return;}
  routeData=rt;drawRoute(routeData);buildSteps(routeData);
  switchTab('route');openSheet();
  const sum=`${fmtDur(routeData.duration)} · ${fmtDist(routeData.distance)}`;
  $('#sheetTitle').textContent=label||'Destination';
  $('#sheetBadge').style.display='inline-block';$('#sheetBadge').textContent=sum;
  speak(`Starting drive to ${label||'your destination'}. ${fmtDur(routeData.duration)}, ${fmtDist(routeData.distance)}.`);
  stepIdx=0;updateNav();
}
function drawRoute(rt){
  if(routeLine)map.removeLayer(routeLine);
  const pts=rt.geometry.coordinates.map(c=>[c[1],c[0]]);
  routeLine=L.polyline(pts,{color:'#22c55e',weight:6,opacity:.9,className:'leaflet-routeline'}).addTo(map);
  try{map.fitBounds(routeLine.getBounds().pad(.18));}catch(_){}
  follow=false;setFollowUI();
}
function buildSteps(rt){
  steps=[];
  (rt.legs||[]).forEach(leg=>(leg.steps||[]).forEach(s=>{
    const m=s.maneuver||{};const road=s.name||'';
    steps.push({text:manText(m,road,s),dist:s.distance,loc:m.location?[m.location[1],m.location[0]]:null});
  }));
  renderRoute();
}
function manText(m,road,s){
  const t=m.type||'', mod=m.modifier||'';
  const on=road?` onto ${road}`:'';
  if(t==='depart')return `Head ${mod||m.bearing_after? dirWord(m.bearing_after):''}`.trim()+(road?` on ${road}`:'');
  if(t==='arrive')return `Arrive at your destination`;
  if(t==='roundabout'||t==='rotary')return `Take the roundabout${s&&s.name?` to ${s.name}`:''}`;
  if(t==='merge')return `Merge ${mod||''}${on}`.trim();
  if(t==='on ramp'||t==='ramp')return `Take the ramp ${mod||''}`.trim();
  if(t==='off ramp')return `Take the exit ${mod||''}`.trim();
  if(t==='fork')return `Keep ${mod||'straight'}${on}`;
  if(t==='continue')return `Continue ${mod||'straight'}${road?` on ${road}`:''}`;
  if(t==='new name')return `Continue${road?` on ${road}`:''}`;
  if(t==='turn')return `Turn ${mod||''}${on}`.trim();
  if(t==='end of road')return `At the end of the road, turn ${mod||''}${on}`.trim();
  return `${(t||'Continue')} ${mod||''}${on}`.trim();
}
function dirWord(b){const dirs=['north','northeast','east','southeast','south','southwest','west','northwest'];return dirs[Math.round(((b||0)%360)/45)%8];}

/* ---------- live nav updates ---------- */
function haversine(a,b){const R=6371000,dLat=(b[0]-a[0])*Math.PI/180,dLon=(b[1]-a[1])*Math.PI/180,la1=a[0]*Math.PI/180,la2=b[0]*Math.PI/180;const x=Math.sin(dLat/2)**2+Math.cos(la1)*Math.cos(la2)*Math.sin(dLon/2)**2;return 2*R*Math.asin(Math.sqrt(x));}
let lastSpokenStep=-1;
function updateNav(){
  if(!steps.length||!me){$('#nav').style.display='none';return;}
  // advance to nearest upcoming maneuver
  while(stepIdx<steps.length-1 && steps[stepIdx].loc && haversine([me.lat,me.lon],steps[stepIdx].loc)<28){stepIdx++;}
  const st=steps[stepIdx];if(!st){$('#nav').style.display='none';return;}
  const d=st.loc?haversine([me.lat,me.lon],st.loc):null;
  $('#nav').style.display='block';
  $('#navMan').textContent=st.text;
  $('#navSub').textContent=(d!=null?`in ${fmtDist(d)}`:'')+ (routeData?` · ETA ${etaClock(routeData.duration)}`:'');
  // speak once when within ~140m, and again on arrival step
  if(d!=null && d<150 && lastSpokenStep!==stepIdx){lastSpokenStep=stepIdx;speak(st.text);}
  if(stepIdx===steps.length-1 && d!=null && d<40){speak('You have arrived.');}
}

/* ---------- "About the area" (Wikipedia geosearch) ---------- */
async function wikiNearby(lat,lon){
  const u=`https://en.wikipedia.org/w/api.php?action=query&list=geosearch&gscoord=${lat}%7C${lon}&gsradius=3000&gslimit=8&format=json&origin=*`;
  const r=await fetch(u);const j=await r.json();
  const list=(j.query&&j.query.geosearch)||[];
  if(!list.length)return[];
  const ids=list.map(x=>x.pageid).join('|');
  const u2=`https://en.wikipedia.org/w/api.php?action=query&prop=extracts%7Cpageimages%7Ccoordinates&exintro&explaintext&exsentences=3&piprop=thumbnail&pithumbsize=90&pilimit=8&pageids=${ids}&format=json&origin=*`;
  const r2=await fetch(u2);const j2=await r2.json();
  const pages=(j2.query&&j2.query.pages)||{};
  return list.map(x=>({title:x.title,dist:x.dist,extract:(pages[x.pageid]||{}).extract||'',thumb:((pages[x.pageid]||{}).thumbnail||{}).source||''}));
}
async function showArea(narrate){
  switchTab('area');openSheet();
  const body=$('#body');
  const at=me||{lat:map.getCenter().lat,lon:map.getCenter().lng};
  body.innerHTML='<div class="empty">Reading the area around you…</div>';
  let place=null;try{place=await reverse(at.lat,at.lon);}catch(_){}
  const a=(place&&place.address)||{};
  const where=[a.neighbourhood||a.suburb||a.hamlet, a.city||a.town||a.village||a.county, a.state].filter(Boolean).join(', ');
  $('#sheetTitle').textContent=where||'About the area';
  $('#sheetBadge').style.display='none';
  let arts=[];try{arts=await wikiNearby(at.lat,at.lon);}catch(_){}
  body.innerHTML='';
  const intro=el('div','card',`<h3>📍 ${where||'Right here'}</h3>${place?`<div class="meta">${place.display_name}</div>`:''}<p>${arts.length?`${arts.length} notable spots within ~2 miles. Tap any to hear it.`:'No Wikipedia landmarks nearby — you are off the beaten path.'}</p>`);
  body.appendChild(intro);
  arts.forEach(x=>{
    const c=el('div','card',
      `<h3>${x.thumb?`<img src="${x.thumb}" style="width:34px;height:34px;border-radius:8px;object-fit:cover"/>`:''}${x.title}</h3>`+
      `<div class="meta">${fmtDist(x.dist)} away</div>`+
      `<p>${x.extract||'No summary available.'}</p>`+
      `<div class="row"><button data-say="1">🔊 Read aloud</button><button data-wiki="${encodeURIComponent(x.title)}">Open article</button></div>`);
    c.querySelector('[data-say]').onclick=()=>speak(`${x.title}. ${x.extract}`);
    c.querySelector('[data-wiki]').onclick=()=>window.open('https://en.wikipedia.org/wiki/'+encodeURIComponent(x.title.replace(/ /g,'_')),'_blank');
    body.appendChild(c);
  });
  lastAreaAt={lat:at.lat,lon:at.lon};
  if(narrate&&(where||arts.length)){
    const lead=arts[0];
    speak(`You're in ${where||'this area'}.`+(lead?` Nearby: ${lead.title}. ${lead.extract}`:''));
  }
}
// auto-briefing when you move into a meaningfully new area (~700m) and not actively turning
function maybeArea(force){
  if(!me)return;
  if(!lastAreaAt){ if(force) autoArea(); return; }
  const moved=haversine([me.lat,me.lon],[lastAreaAt.lat,lastAreaAt.lon]);
  if(moved>700 && !steps.length){ autoArea(); }
}
let autoBusy=false;
async function autoArea(){
  if(autoBusy)return;autoBusy=true;
  try{
    const at=me;let place=null;try{place=await reverse(at.lat,at.lon);}catch(_){}
    const a=(place&&place.address)||{};
    const where=[a.neighbourhood||a.suburb||a.hamlet,a.city||a.town||a.village].filter(Boolean).join(', ');
    let arts=[];try{arts=await wikiNearby(at.lat,at.lon);}catch(_){}
    lastAreaAt={lat:at.lat,lon:at.lon};
    if(where||arts.length){
      toast('📍 '+(where||'New area'));
      const lead=arts[0];
      speak(`Now entering ${where||'a new area'}.`+(lead?` ${lead.title}: ${lead.extract}`:''));
      if(activeTab==='area')showArea(false);
    }
  }finally{setTimeout(()=>autoBusy=false,15000);}
}

/* ---------- route render ---------- */
function renderRoute(){
  const body=$('#body');body.innerHTML='';
  if(!routeData){body.innerHTML='<div class="empty">Search a destination above to get driving directions.<br/>Turn-by-turn is spoken aloud as you drive.</div>';return;}
  const sum=el('div','route-sum',`<div class="eta">${fmtDur(routeData.duration)}</div><div class="dist">${fmtDist(routeData.distance)} · ETA ${etaClock(routeData.duration)}</div><div class="clear" id="clearRoute">End</div>`);
  body.appendChild(sum);
  sum.querySelector('#clearRoute').onclick=clearRoute;
  steps.forEach((s,i)=>{
    const d=el('div','step',`<div class="n">${i+1}</div><div><div class="m">${s.text}</div><div class="d">${fmtDist(s.dist)}</div></div>`);
    d.onclick=()=>{if(s.loc)map.panTo(s.loc);};
    body.appendChild(d);
  });
}
function clearRoute(){
  routeData=null;steps=[];stepIdx=0;lastSpokenStep=-1;
  if(routeLine){map.removeLayer(routeLine);routeLine=null;}
  if(destMarker){map.removeLayer(destMarker);destMarker=null;}
  $('#nav').style.display='none';$('#sheetBadge').style.display='none';$('#sheetTitle').textContent='Waypoint';
  follow=true;setFollowUI();if(me)map.setView([me.lat,me.lon],16);
  switchTab('area');renderRoute();
}

/* ---------- sheet / tabs ---------- */
function openSheet(){$('#sheet').classList.add('open');}
function closeSheet(){$('#sheet').classList.remove('open');}
$('#grip').onclick=()=>$('#sheet').classList.toggle('open');
$('#sheetHead').onclick=()=>$('#sheet').classList.toggle('open');
document.querySelectorAll('.tab').forEach(t=>t.onclick=()=>switchTab(t.dataset.tab));
function switchTab(name){
  activeTab=name;
  document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('active',t.dataset.tab===name));
  if(name==='route')renderRoute();else showAreaCached();
  openSheet();
}
let areaRendered=false;
function showAreaCached(){ if(!areaRendered){areaRendered=true;showArea(false);} }

/* ---------- controls ---------- */
function setFollowUI(){$('#followBtn').classList.toggle('on',follow);}
$('#followBtn').onclick=()=>{follow=!follow;setFollowUI();if(follow&&me)map.setView([me.lat,me.lon],16);};
map.on('dragstart',()=>{follow=false;setFollowUI();});
$('#areaBtn').onclick=()=>{areaRendered=true;showArea(true);};
$('#voiceBtn').onclick=()=>{voiceOn=!voiceOn;$('#voiceBtn').classList.toggle('on',voiceOn);toast(voiceOn?'Voice on':'Voice muted');if(voiceOn)speak('Voice on.');else speechSynthesis.cancel();};

/* ---------- boot ---------- */
if('serviceWorker'in navigator){navigator.serviceWorker.register('__BASE__/sw.js',{scope:'__BASE__/'}).catch(()=>{});}
renderRoute();
startGeo();
// iOS: speechSynthesis needs a user gesture to unlock — prime it on first tap
document.body.addEventListener('touchend',function prime(){try{speechSynthesis.speak(new SpeechSynthesisUtterance(''));}catch(_){}document.body.removeEventListener('touchend',prime);},{once:true});
</script>
</body>
</html>'''

HERE = os.path.dirname(os.path.abspath(__file__))

MANIFEST = ('{'
  '"name":"Waypoint","short_name":"Waypoint",'
  f'"start_url":"{BASE}/","scope":"{BASE}/","display":"standalone",'
  '"orientation":"portrait","background_color":"#0b0f14","theme_color":"#0b0f14",'
  '"description":"Driving GPS with spoken area briefings.",'
  '"icons":['
    f'{{"src":"{BASE}/icon-192.png","sizes":"192x192","type":"image/png","purpose":"any"}},'
    f'{{"src":"{BASE}/icon-512.png","sizes":"512x512","type":"image/png","purpose":"any"}},'
    f'{{"src":"{BASE}/icon-512.png","sizes":"512x512","type":"image/png","purpose":"maskable"}}'
  ']}'
)

SW = (
  "const C='waypoint-v2';"
  f"const SHELL=['{BASE}/','{BASE}/icon.png','{BASE}/icon-192.png','{BASE}/icon-512.png','{BASE}/manifest.webmanifest'];"
  "self.addEventListener('install',e=>{e.waitUntil(caches.open(C).then(c=>c.addAll(SHELL)).then(()=>self.skipWaiting()).catch(()=>self.skipWaiting()));});"
  "self.addEventListener('activate',e=>{e.waitUntil(caches.keys().then(k=>Promise.all(k.filter(x=>x!==C).map(x=>caches.delete(x)))).then(()=>self.clients.claim()));});"
  "self.addEventListener('fetch',e=>{const u=new URL(e.request.url);"
  "if(e.request.method!=='GET'||u.origin!==location.origin){return;}"
  "if(e.request.mode==='navigate'){e.respondWith(fetch(e.request).catch(()=>caches.match(SHELL[0])));return;}"
  "e.respondWith(caches.match(e.request).then(r=>r||fetch(e.request)));});"
)


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet
        pass

    def _route(self):
        p = self.path.split('?', 1)[0]
        if BASE and p.startswith(BASE):
            p = p[len(BASE):] or '/'
        return p

    def _send(self, body, ctype, cache='no-cache'):
        if isinstance(body, str):
            body = body.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', cache)
        self.end_headers()
        self.wfile.write(body)

    def _file(self, name, ctype):
        try:
            with open(os.path.join(HERE, name), 'rb') as f:
                self._send(f.read(), ctype, cache='public, max-age=86400')
        except OSError:
            self.send_response(404); self.end_headers(); self.wfile.write(b'not found')

    def do_GET(self):
        p = self._route()
        if p in ('/', '/index.html'):
            self._send(PAGE.replace('__BASE__', BASE), 'text/html; charset=utf-8')
        elif p == '/manifest.webmanifest':
            self._send(MANIFEST, 'application/manifest+json')
        elif p == '/sw.js':
            self._send(SW, 'application/javascript; charset=utf-8')
        elif p in ('/icon.png', '/icon-192.png', '/icon-512.png'):
            self._file(p.lstrip('/'), 'image/png')
        elif p in ('/health', '/healthz'):
            self._send('ok', 'text/plain')
        else:
            self.send_response(404); self.end_headers(); self.wfile.write(b'not found')

if __name__ == '__main__':
    print(f"Waypoint on :{PORT} base='{BASE or '/'}'")
    ThreadingHTTPServer(('127.0.0.1', PORT), H).serve_forever()
