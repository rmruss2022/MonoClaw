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
import os, json, math, urllib.request, urllib.parse
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
  #sheet{position:absolute;left:0;right:0;bottom:0;z-index:1000;background:var(--panel);border-top:1px solid var(--line);border-radius:20px 20px 0 0;box-shadow:0 -10px 40px rgba(0,0,0,.5);transform:translateY(calc(100% - 128px));transition:transform .28s cubic-bezier(.2,.8,.2,1);max-height:80vh;display:flex;flex-direction:column;padding-bottom:env(safe-area-inset-bottom);touch-action:none}
  #sheet.open{transform:translateY(0)}
  #grip{padding:14px 0 8px;display:flex;justify-content:center;cursor:grab}
  #grip .bar{width:48px;height:6px;border-radius:6px;background:#3a4c5e}
  #sheetHead{cursor:grab}
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
    <div class="tab" data-tab="ask">Ask AI</div>
    <div class="tab" data-tab="route">Directions</div>
  </div>
  <div id="body"></div>
</div>

<div id="toast"></div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
/* ---------- tiny helpers ---------- */
const API="__BASE__";
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
// Keyless dark basemap (Esri dark-gray canvas) — CARTO's no-key tiles now demand an API key.
L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}',{maxZoom:19}).addTo(map);
L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}',{maxZoom:19}).addTo(map);
L.control.attribution({position:'bottomleft',prefix:false}).addAttribution('© Esri · OpenStreetMap · OSRM · Wikipedia').addTo(map);

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
  let b='';
  if(me){
    // Keep short/bare-number searches (e.g. "123") local instead of matching another country.
    const bounded=(/^\d{1,5}$/.test(q.trim())||q.trim().length<4)?1:0;
    b=`&viewbox=${me.lon-.5},${me.lat+.35},${me.lon+.5},${me.lat-.35}&bounded=${bounded}`;
  }
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
  switchTab('route');collapseSheet();
  if(me){follow=true;setFollowUI();map.setView([me.lat,me.lon],16);}   // Waze-style: track the driver, map stays visible
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
async function fetchBrief(lat,lon){
  try{const r=await fetch(API+'/api/brief',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({lat,lon})});return await r.json();}catch(_){return null;}
}
async function showArea(narrate){
  switchTab('area');openSheet();
  const body=$('#body');
  const at=me||{lat:map.getCenter().lat,lon:map.getCenter().lng};
  body.innerHTML='<div class="empty">Asking your AI guide about this area…</div>';
  const d=await fetchBrief(at.lat,at.lon);
  body.innerHTML='';
  const where=(d&&d.place)||'';
  const guideText=(d&&d.text)||'';
  $('#sheetTitle').textContent=where||'About the area';
  $('#sheetBadge').style.display='none';
  const guide=el('div','card',`<h3>🧭 Local guide${where?` · ${where}`:''}</h3><p>${guideText||'Couldn\'t load a briefing right now — check your connection.'}</p>`+(guideText?`<div class="row"><button id="briefSay">🔊 Read aloud</button></div>`:''));
  body.appendChild(guide);
  const sb=guide.querySelector('#briefSay');if(sb)sb.onclick=()=>speak(guideText);
  const arts=(d&&d.articles)||[];
  arts.forEach(x=>{
    const c=el('div','card',
      `<h3>${x.thumb?`<img src="${x.thumb}" style="width:34px;height:34px;border-radius:8px;object-fit:cover"/>`:''}${x.title}</h3>`+
      `<div class="meta">${x.dist!=null?fmtDist(x.dist)+' away':''}</div>`+
      `<p>${x.extract||'No summary available.'}</p>`+
      `<div class="row"><button data-say="1">🔊 Read aloud</button><button data-wiki="1">Open article</button></div>`);
    c.querySelector('[data-say]').onclick=()=>speak(`${x.title}. ${x.extract}`);
    c.querySelector('[data-wiki]').onclick=()=>window.open('https://en.wikipedia.org/wiki/'+encodeURIComponent(x.title.replace(/ /g,'_')),'_blank');
    body.appendChild(c);
  });
  lastAreaAt={lat:at.lat,lon:at.lon};
  if(narrate&&guideText)speak(guideText);
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
    const at=me;
    const d=await fetchBrief(at.lat,at.lon);
    lastAreaAt={lat:at.lat,lon:at.lon};
    if(d&&(d.place||d.text)){
      toast('📍 '+(d.place||'New area'));
      if(d.text)speak(d.text);
      if(activeTab==='area')showArea(false);
    }
  }finally{setTimeout(()=>autoBusy=false,20000);}
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

/* ---------- draggable bottom sheet (Google Maps / Waze style) ---------- */
const sheetEl=$('#sheet');
const PEEK=128;
function openSheet(){sheetEl.style.transition='';sheetEl.style.transform='';sheetEl.classList.add('open');}
function collapseSheet(){sheetEl.style.transition='';sheetEl.style.transform='';sheetEl.classList.remove('open');}
function toggleSheet(){sheetEl.classList.contains('open')?collapseSheet():openSheet();}
let sdrag=null;
function sheetStart(y){sdrag={y0:y,moved:0,open:sheetEl.classList.contains('open'),h:sheetEl.offsetHeight};sheetEl.style.transition='none';}
function sheetMove(y){
  if(!sdrag)return;
  const peekOff=sdrag.h-PEEK;
  const dy=y-sdrag.y0;sdrag.moved=Math.max(sdrag.moved,Math.abs(dy));
  const base=sdrag.open?0:peekOff;
  const t=Math.min(peekOff,Math.max(0,base+dy));
  sheetEl.style.transform=`translateY(${t}px)`;
}
function sheetEnd(){
  if(!sdrag)return;
  const peekOff=sdrag.h-PEEK;
  const m=/translateY\(([-0-9.]+)px\)/.exec(sheetEl.style.transform||'');
  const t=m?parseFloat(m[1]):(sdrag.open?0:peekOff);
  sheetEl.style.transition='';sheetEl.style.transform='';
  if(sdrag.moved<6){toggleSheet();}
  else if(t<peekOff*0.5){sheetEl.classList.add('open');}
  else{sheetEl.classList.remove('open');}
  sdrag=null;
}
['#grip','#sheetHead'].forEach(sel=>{
  const e=$(sel);if(!e)return;
  e.addEventListener('touchstart',ev=>sheetStart(ev.touches[0].clientY),{passive:true});
  e.addEventListener('touchmove',ev=>{sheetMove(ev.touches[0].clientY);ev.preventDefault();},{passive:false});
  e.addEventListener('touchend',sheetEnd);
  e.addEventListener('touchcancel',sheetEnd);
  e.addEventListener('mousedown',ev=>{sheetStart(ev.clientY);
    const mm=e2=>sheetMove(e2.clientY);
    const mu=()=>{sheetEnd();document.removeEventListener('mousemove',mm);document.removeEventListener('mouseup',mu);};
    document.addEventListener('mousemove',mm);document.addEventListener('mouseup',mu);});
});
document.querySelectorAll('.tab').forEach(t=>t.onclick=()=>{switchTab(t.dataset.tab);openSheet();});
function switchTab(name){
  activeTab=name;
  document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('active',t.dataset.tab===name));
  if(name==='route')renderRoute();
  else if(name==='ask')renderAsk();
  else showAreaCached();
}

/* ---------- Ask AI (agentic) ---------- */
function renderAsk(){
  $('#sheetTitle').textContent='Ask Waypoint';$('#sheetBadge').style.display='none';
  const body=$('#body');body.innerHTML='';
  const wrap=el('div','card',
    `<h3>🤖 Ask anything</h3>`+
    `<p style="margin-bottom:10px">“Find good coffee near me”, “take me to a park”, “what's interesting around here?”</p>`+
    `<div style="display:flex;gap:8px">`+
      `<input id="askIn" placeholder="Ask…" autocomplete="off" enterkeyhint="send" style="flex:1;background:#0b1118;border:1px solid var(--line);color:var(--text);border-radius:11px;padding:12px;font-size:15px"/>`+
      `<button id="askMic" class="iconbtn" style="width:46px;height:46px"><svg viewBox="0 0 24 24"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M6 11a6 6 0 0 0 12 0M12 17v4"/></svg></button>`+
      `<button id="askSend" style="background:var(--accent);color:#04120a;border:0;font-weight:700;border-radius:11px;padding:0 16px;font-size:15px">Go</button>`+
    `</div>`);
  body.appendChild(wrap);
  const out=el('div','',''); out.id='askOut'; body.appendChild(out);
  $('#askSend').onclick=()=>doAsk($('#askIn').value.trim());
  $('#askIn').addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();doAsk($('#askIn').value.trim());}});
  $('#askMic').onclick=startDictation;
}
async function doAsk(q){
  if(!q)return;
  const out=$('#askOut');out.innerHTML='<div class="empty">Thinking…</div>';
  const at=me||{lat:map.getCenter().lat,lon:map.getCenter().lng};
  let d=null;
  try{const r=await fetch(API+'/api/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({lat:at.lat,lon:at.lon,query:q})});d=await r.json();}catch(_){}
  if(!d){out.innerHTML='<div class="empty">Couldn\'t reach the assistant (network).</div>';return;}
  out.innerHTML='';
  const c=el('div','card',`<h3>🤖 Waypoint</h3><p>${d.say||'—'}</p>`);
  if(d.destination&&d.destination.name){
    const row=el('div','row');
    const go=el('button',null,`🧭 Route to ${d.destination.name}`);
    go.onclick=()=>navigateTo(d.destination.lat,d.destination.lon,d.destination.name);
    row.appendChild(go);c.appendChild(row);
  }
  out.appendChild(c);
  speak(d.say||'');
}
function startDictation(){
  const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
  if(!SR){toast('Voice input not supported here — just type it');return;}
  try{const r=new SR();r.lang='en-US';r.interimResults=false;r.maxAlternatives=1;
    r.onresult=e=>{const t=e.results[0][0].transcript;if($('#askIn'))$('#askIn').value=t;doAsk(t);};
    r.onerror=()=>toast('Didn\'t catch that');
    r.start();toast('🎙️ Listening…');}catch(_){toast('Voice input unavailable');}
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

# ---- AI + geo backend (agentic layer) --------------------------------------
UA = {"User-Agent": "Waypoint/1.0 (personal navigation app; contact: matthew)"}

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

def get_json(url, timeout=12):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))

def gemini(prompt, want_json=False, timeout=16):
    if not GEMINI_KEY:
        return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={GEMINI_KEY}"
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    if want_json:
        body["generationConfig"] = {"response_mime_type": "application/json"}
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            j = json.loads(r.read().decode("utf-8", "replace"))
        return j["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        return None

def reverse_geocode(lat, lon):
    return get_json(f"https://nominatim.openstreetmap.org/reverse?format=jsonv2&zoom=14&addressdetails=1&lat={lat}&lon={lon}")

def nominatim_search(q, lat, lon, limit=8):
    vb = f"&viewbox={lon-0.15},{lat+0.12},{lon+0.15},{lat-0.12}&bounded=0"
    return get_json(f"https://nominatim.openstreetmap.org/search?format=jsonv2&limit={limit}&addressdetails=1&q={urllib.parse.quote(q)}{vb}")

def wiki_nearby(lat, lon, limit=6):
    j = get_json(f"https://en.wikipedia.org/w/api.php?action=query&list=geosearch&gscoord={lat}%7C{lon}&gsradius=3000&gslimit={limit}&format=json")
    lst = (j.get("query", {}) or {}).get("geosearch", []) or []
    if not lst:
        return []
    ids = "|".join(str(x["pageid"]) for x in lst)
    j2 = get_json(f"https://en.wikipedia.org/w/api.php?action=query&prop=extracts%7Cpageimages&exintro&explaintext&exsentences=3&piprop=thumbnail&pithumbsize=90&pilimit={limit}&pageids={urllib.parse.quote(ids)}&format=json")
    pages = (j2.get("query", {}) or {}).get("pages", {}) or {}
    out = []
    for x in lst:
        pg = pages.get(str(x["pageid"]), {}) or {}
        out.append({"title": x["title"], "dist": x.get("dist"),
                    "extract": pg.get("extract", ""),
                    "thumb": (pg.get("thumbnail", {}) or {}).get("source", "")})
    return out

def hav(lat1, lon1, lat2, lon2):
    R = 6371000.0
    dlat = math.radians(lat2 - lat1); dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2
    return 2*R*math.asin(math.sqrt(a))

OVERPASS_HOSTS = ["https://overpass-api.de/api/interpreter",
                  "https://overpass.kumi.systems/api/interpreter"]

def overpass_nearby(tag, lat, lon, radius=2500, limit=8):
    q = (f"[out:json][timeout:12];("
         f"node(around:{radius},{lat},{lon})[{tag}];"
         f"way(around:{radius},{lat},{lon})[{tag}];);out center {limit*3};")
    for host in OVERPASS_HOSTS:
        try:
            j = get_json(host + "?data=" + urllib.parse.quote(q), timeout=14)
        except Exception:
            continue
        out = []
        for e in j.get("elements", []):
            tags = e.get("tags", {}) or {}
            name = tags.get("name")
            if not name:
                continue
            la = e.get("lat") if e.get("lat") is not None else (e.get("center", {}) or {}).get("lat")
            lo = e.get("lon") if e.get("lon") is not None else (e.get("center", {}) or {}).get("lon")
            if la is None or lo is None:
                continue
            out.append({"name": name, "lat": la, "lon": lo, "dist": hav(lat, lon, la, lo),
                        "kind": tags.get("amenity") or tags.get("shop") or tags.get("leisure") or tags.get("tourism")})
        if out:
            out.sort(key=lambda x: x["dist"])
            return out[:limit]
    return []

def photon_search(term, lat, lon, key=None, value=None, limit=8, maxkm=25):
    url = f"https://photon.komoot.io/api/?q={urllib.parse.quote(term)}&lat={lat}&lon={lon}&limit=20"
    j = get_json(url, timeout=14)
    prim, sec = [], []
    for f in j.get("features", []):
        p = f.get("properties", {}) or {}
        name = p.get("name")
        c = (f.get("geometry", {}) or {}).get("coordinates", [None, None])
        if not name or c[0] is None:
            continue
        lo, la = c[0], c[1]
        d = hav(lat, lon, la, lo)
        if d > maxkm * 1000:
            continue
        rec = {"name": name, "lat": la, "lon": lo, "dist": d, "kind": p.get("osm_value")}
        if (value and p.get("osm_value") == value) or (key and p.get("osm_key") == key):
            prim.append(rec)
        else:
            sec.append(rec)
    res = prim if prim else sec
    res.sort(key=lambda x: x["dist"])
    return res[:limit]

def find_places(tag, label, lat, lon):
    key = value = None
    if tag and "=" in tag:
        key, value = tag.split("=", 1)
    cands = []
    # Photon first — fast and reliable, filtered to the intended category.
    for term in [t for t in (label, value) if t]:
        try:
            cands = photon_search(term, lat, lon, key, value)
        except Exception:
            cands = []
        if cands:
            break
    # Overpass as a category-accurate upgrade when Photon is weak (but it's flaky/slow).
    if len(cands) < 2 and tag:
        try:
            ov = overpass_nearby(tag, lat, lon)
            if ov:
                cands = ov
        except Exception:
            pass
    if not cands:  # last resort: bounded freeform name search
        try:
            for r in nominatim_search(label, lat, lon, 8):
                d = hav(lat, lon, float(r["lat"]), float(r["lon"]))
                if d < 60000:
                    cands.append({"name": r.get("display_name", "").split(",")[0],
                                  "lat": float(r["lat"]), "lon": float(r["lon"]), "dist": d})
        except Exception: pass
    cands.sort(key=lambda x: x.get("dist") if x.get("dist") is not None else 9e9)
    return cands[:8]

def _where_str(place, short=False):
    a = (place or {}).get("address", {}) if place else {}
    parts = [a.get("neighbourhood") or a.get("suburb") or a.get("hamlet"),
             a.get("city") or a.get("town") or a.get("village") or a.get("county")]
    if not short:
        parts.append(a.get("state"))
    return ", ".join([x for x in parts if x])


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
  "const C='waypoint-v5';"
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

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        p = self._route()
        try:
            n = int(self.headers.get('Content-Length', '0') or 0)
        except ValueError:
            n = 0
        raw = self.rfile.read(n) if n else b'{}'
        try:
            req = json.loads(raw or b'{}')
        except Exception:
            req = {}
        if p == '/api/brief':
            self._brief(req)
        elif p == '/api/ask':
            self._ask(req)
        else:
            self.send_response(404); self.end_headers(); self.wfile.write(b'not found')

    def _brief(self, req):
        lat, lon = req.get('lat'), req.get('lon')
        if lat is None or lon is None:
            return self._json({'error': 'no location'}, 400)
        place = None
        try: place = reverse_geocode(lat, lon)
        except Exception: pass
        where = _where_str(place)
        arts = []
        try: arts = wiki_nearby(lat, lon, 6)
        except Exception: pass
        landmarks = '; '.join(f"{x['title']}: {x['extract'][:180]}" for x in arts[:5] if x.get('extract'))
        prompt = ("You are a warm, knowledgeable local guide riding shotgun with a driver. "
                  "In 2-3 short spoken sentences (no markdown, no lists, no emoji), tell them what's "
                  f"interesting about where they are: {where or 'this area'}. "
                  f"Ground it in these nearby landmarks when relevant: {landmarks or 'none found'}. "
                  "Be vivid but brief; it will be read aloud while driving.")
        text = gemini(prompt)
        if not text:
            text = ((f"You're in {where}. " if where else "") +
                    (f"Nearby: {arts[0]['title']}. {arts[0]['extract']}" if arts else
                     "No notable landmarks right around here."))
        self._json({'text': text.strip(), 'place': where, 'articles': arts})

    def _ask(self, req):
        lat, lon = req.get('lat'), req.get('lon')
        q = (req.get('query') or '').strip()
        if lat is None or lon is None or not q:
            return self._json({'say': "Tell me where you'd like to go.", 'destination': None})
        place = None
        try: place = reverse_geocode(lat, lon)
        except Exception: pass
        where = _where_str(place, short=True)

        # Step 1 — the agent decides: is this "find a place" or a general question?
        cls = gemini(
            f"A driver near {where or 'here'} said: \"{q}\".\n"
            'If they want to find or be taken to a TYPE of place, reply JSON '
            '{"mode":"find","osm":"<one valid OpenStreetMap tag filter, e.g. amenity=cafe, shop=supermarket, '
            'leisure=park, amenity=fuel, amenity=restaurant, amenity=bar, amenity=pharmacy>","label":"<short plural noun>"}. '
            'If it is a general question about the area, reply JSON {"mode":"chat","say":"<one friendly spoken sentence, no markdown/emoji>"}. '
            'Reply ONLY JSON.', want_json=True)
        spec = {}
        if cls:
            try: spec = json.loads(cls)
            except Exception: spec = {}
        if spec.get('mode') == 'chat' and spec.get('say'):
            return self._json({'say': spec['say'], 'destination': None})

        tag = spec.get('osm'); label = spec.get('label') or q
        cands = find_places(tag, label, lat, lon)
        if not cands:
            return self._json({'say': f"I couldn't find {label} near you right now.", 'destination': None})

        # Step 2 — the agent picks the best and pitches it
        slim = [{'name': c['name'], 'lat': c['lat'], 'lon': c['lon'],
                 'meters': (round(c['dist']) if c.get('dist') is not None else None)} for c in cands[:8]]
        pick = gemini(
            f"Driver near {where or 'here'} asked: \"{q}\". Candidate places (JSON, nearest first): {json.dumps(slim)}. "
            'Pick the single best one and reply ONLY JSON '
            '{"say":"<one friendly spoken sentence naming it and how far>","name":"..","lat":..,"lon":..} '
            'using values copied from a candidate.', want_json=True)
        say, dest = None, None
        if pick:
            try:
                j = json.loads(pick); say = j.get('say')
                if j.get('name') and j.get('lat') is not None and j.get('lon') is not None:
                    dest = {'name': j['name'], 'lat': float(j['lat']), 'lon': float(j['lon'])}
            except Exception: pass
        if not dest:
            c = cands[0]; dest = {'name': c['name'], 'lat': c['lat'], 'lon': c['lon']}
            if not say:
                say = f"Closest is {c['name']}" + (f", about {round(c['dist'])} meters away." if c.get('dist') is not None else ".")
        self._json({'say': say, 'destination': dest})

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
