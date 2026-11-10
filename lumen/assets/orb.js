(function(){
var VS="#version 300 es\nin vec2 a; out vec2 vUv;\nvoid main(){ vUv = a; gl_Position = vec4(a,0.,1.); }";
var FS="#version 300 es\nprecision highp float;\nin vec2 vUv; out vec4 o;\nuniform vec2 uRes; uniform float uTime, uFlow, uBreath, uFlare, uPress, uSession, uEvo;\nuniform vec2 uPtr; uniform vec2 uSpin; uniform int uMotes, uMotesPrev; uniform vec3 uBg;\nuniform float uExtras;\nuniform vec3 uPal[5]; uniform vec3 uHalo, uRim, uMote, uFlareC;\n\nfloat hash(vec3 p){ p = fract(p*0.3183099 + .1); p *= 17.0; return fract(p.x*p.y*p.z*(p.x+p.y+p.z)); }\nfloat noise(vec3 x){\n  vec3 i = floor(x), f = fract(x); f = f*f*f*(f*(f*6.-15.)+10.);\n  return mix(mix(mix(hash(i),hash(i+vec3(1,0,0)),f.x), mix(hash(i+vec3(0,1,0)),hash(i+vec3(1,1,0)),f.x),f.y),\n             mix(mix(hash(i+vec3(0,0,1)),hash(i+vec3(1,0,1)),f.x), mix(hash(i+vec3(0,1,1)),hash(i+vec3(1,1,1)),f.x),f.y), f.z);\n}\nfloat fbm(vec3 p){ float a=.5, s=0.; for(int i=0;i<4;i++){ s += a*noise(p); p = p*2.03 + vec3(1.7,9.2,3.1); a *= .5; } return s; }\nfloat fbm3(vec3 p){ float a=.5, s=0.; for(int i=0;i<3;i++){ s += a*noise(p); p = p*2.03 + vec3(1.7,9.2,3.1); a *= .5; } return s; }\n\nmat3 rotY(float a){ float c=cos(a), s=sin(a); return mat3(c,0,-s, 0,1,0, s,0,c); }\nmat3 rotX(float a){ float c=cos(a), s=sin(a); return mat3(1,0,0, 0,c,s, 0,-s,c); }\nmat3 rotZ(float a){ float c=cos(a), s=sin(a); return mat3(c,s,0, -s,c,0, 0,0,1); }\n\n// domain-warped plasma field\nvec3 motePos(float th, float a, float h1, float h2){\n  return rotZ((h1-.5)*.9) * rotX(.35 + (h2-.5)*.7) * vec3(cos(th)*a, 0., sin(th)*a);\n}\n\n// glittering dust disk, inclined like a planetary ring. returns intensity; front = near half\nfloat dustDisk(vec2 p, out bool front){\n  float tilt = -.30, ci = .27;\n  vec2 q = mat2(cos(tilt), sin(tilt), -sin(tilt), cos(tilt)) * p;\n  vec2 dp = vec2(q.x, q.y/ci);\n  float rr = length(dp);\n  front = q.y < 0.;\n  if(rr < 1.3 || rr > 2.25) return 0.;\n  float ang = atan(dp.y, dp.x) - uTime*.06/pow(rr, 1.5);      // keplerian shear: inner dust moves faster\n  vec3 s3 = vec3(cos(ang), sin(ang), 0.) * rr;\n  float clump = fbm3(s3*2.4 + vec3(0., 0., uTime*.02));\n  float bands = .7 + .3*sin(rr*26. + clump*2.);\n  float prof = smoothstep(1.32, 1.55, rr) * smoothstep(2.22, 1.85, rr);\n  vec2 cell = vec2(ang*150./rr, rr*95.);\n  float gh = hash(vec3(floor(cell), 3.7));\n  float spark = step(.94, gh) * smoothstep(.35, .0, length(fract(cell) - .5)) * (.5 + .5*sin(uTime*(1.5 + gh*3.) + gh*40.));\n  float v = prof * (bands*smoothstep(.2, .85, clump)*.42 + .07) + prof*spark*1.1;\n  return v * 2.2/(rr*rr);\n}\n\nfloat field(vec3 p, float t){\n  vec3 q = p*1.55 + vec3(0., t*.05, t*.03);\n  vec2 w = vec2(fbm3(q + vec3(0,0,t*.045)), fbm3(q + vec3(5.2,1.3,-t*.035)));\n  float turb = 1.6 + uEvo*0.6;\n  return fbm(q + turb*vec3(w, w.x*w.y));\n}\n\n// heat -> linear HDR color: ember -> orange -> amber -> hot white\nvec3 ramp(float h){\n  vec3 c = uPal[0];\n  c = mix(c, uPal[1], smoothstep(.0,.25,h));\n  c = mix(c, uPal[2], smoothstep(.2,.55,h));\n  c = mix(c, uPal[3], smoothstep(.5,.85,h));\n  c = mix(c, uPal[4], smoothstep(.85,1.3,h));\n  return c;\n}\n\nvec3 aces(vec3 x){ return clamp((x*(2.51*x+.03))/(x*(2.43*x+.59)+.14), 0., 1.); }\n\nvoid main(){\n  vec2 uv = vUv;                       // -1..1\n  float px = 2.0 / uRes.x;             // one pixel in uv units\n  float t = uFlow;\n  mat3 Msp = rotY(uSpin.x) * rotX(uSpin.y);\n\n  float R = (0.355 + 0.03*uEvo) * (1. + uBreath*0.035 + uSession*0.02) * (1. - uPress*0.02);\n  float flareA = uFlare >= 0. ? 1. - uFlare : 0.;\n  float flareI = uFlare >= 0. ? sin(clamp(uFlare,0.,1.)*3.14159) : 0.;\n  vec2 p = uv / R;\n  float r = length(p);\n  float lum = 1. + uBreath*.08 + uPress*.10 + flareI*.9;\n\n  vec3 col = vec3(0.);\n\n  // ---- halo (outside + behind) ----\n  float dOut = max(r - 1., 0.);\n  float haloW = 1. + uSession*.6 + uPress*1.1;\n  vec3 haloC = uHalo;\n  float halo = .40*exp(-dOut*6.0/haloW) + .10*exp(-dOut*2.2/haloW) + .015*exp(-dOut*1.0);\n  halo *= (.75 + .45*uEvo + uPress*.6) * lum;\n  col += haloC * halo * smoothstep(.0, .02, r - .98 + .02);\n\n  // ---- level-up ripple ----\n  if(uFlare >= 0.){\n    float rr = 1.0 + uFlare*1.9;\n    float ring = exp(-pow((r - rr)*9., 2.)) * flareA*flareA;\n    col += uFlareC * ring * .9;\n  }\n\n  // ---- dust disk (back half, drawn before the sphere so the orb hides it) ----\n  bool dFront = false; float dust = uExtras > .5 ? dustDisk(p, dFront) * (.35 + .75*uEvo) * lum : 0.;\n  vec3 dustC = mix(uHalo, uMote, .55);\n  if(!dFront) col += dustC * dust;\n\n  // ---- sphere body ----\n  float edge = smoothstep(1. + px/R*1.2, 1. - px/R*1.2, r);\n  if(r < 1.04){\n    float r2 = min(r*r, 1.);\n    float zMax = sqrt(1. - r2);\n    vec3 n = vec3(p, zMax);\n    // slow rotation of the inner volume + pointer parallax\n    mat3 M = rotY(t*.035) * Msp * rotX(.25);\n    vec2 coreOff = uPtr*.07;\n\n    vec3 emit = vec3(0.);\n    float coreK = mix(2.6, 1.7, uEvo);\n    float coreS = mix(.72, .98, uEvo);\n    float heatS = mix(.80, .96, uEvo);\n    const int STEPS = 4;\n    for(int i=0;i<STEPS;i++){\n      float fz = mix(zMax, -zMax, (float(i)+.5)/float(STEPS));\n      vec3 pos = vec3(p - coreOff, fz);\n      float d = length(pos);\n      float f = field(M*pos, t);\n      float fil = smoothstep(.38, .78, f);              // filaments\n      float core = exp(-d*d*coreK) * coreS;              // hot center\n      float h = (core*1.0 + fil*.55*(1.1 - d*.7) + f*.16) * heatS * lum;\n      h = h / (1. + max(h - 1.05, 0.)*1.4);   // soft shoulder so the core never blobs out\n      emit += ramp(h) * (.55 + h*.9);\n    }\n    emit /= float(STEPS);\n\n    // frosted shell: slight absorption toward the limb\n    emit *= mix(1., .45, pow(r, 3.5));\n\n    // second inner turbulence layer at higher evolution\n    if(uEvo > .35){\n      float f2 = fbm3(M*vec3(p*2.6, zMax*2.6) + vec3(0., -t*.08, t*.05));\n      emit += uPal[3] * smoothstep(.55,.85,f2) * (uEvo - .35) * .55 * (1. - r*.6) * lum;\n    }\n\n    // fresnel rim light\n    float fres = pow(1. - zMax, 3.0);\n    vec3 rimC = uRim;\n    emit += rimC * fres * mix(.55, 1.05, uEvo) * (1. + uSession*.25);\n\n    // drifting soft specular highlight (glass)\n    vec3 L = normalize(Msp * vec3(-.55 + .06*sin(uTime*.11) + uPtr.x*.25, .62 + .05*cos(uTime*.083) - uPtr.y*.25, .75));\n    vec3 H = normalize(L + vec3(0,0,1));\n    float spec = pow(max(dot(n, H), 0.), 140.) * .45 + pow(max(dot(n, H), 0.), 18.) * .035;\n    emit += vec3(1.0,.93,.85) * spec;\n\n    col = mix(col, emit, edge);\n    // light bleeding just outside the silhouette\n    col += haloC * .25 * smoothstep(1.06, 1.0, r) * (1. - edge) * lum;\n  }\n\n  // ---- corona: flame tendrils curling off the limb ----\n  if(uExtras > .5 && r > .96 && r < 1.9){\n    vec2 dir = p / max(r, 1e-3);\n    float fl  = fbm(vec3(dir*2.2, r*1.7 - uFlow*.22));\n    float fl2 = fbm3(vec3(dir*5.5 + fl, r*3.2 - uFlow*.38));\n    float tend = pow(smoothstep(.42, .9, fl*.75 + fl2*.45), 2.);\n    float fall = exp(-(r - 1.)*mix(7.5, 5.5, uEvo)) * smoothstep(1.85, 1.45, r);\n    col += mix(uHalo, uRim, .45) * tend * fall * (.6 + .45*uEvo) * lum * (1. - edge) * 1.2;\n  }\n\n  // ---- dust disk (front half, over the sphere) ----\n  if(dFront) col += dustC * dust;\n\n  // ---- motes ----\n  for(int i=0;i<24;i++){\n    if(i >= uMotes) break;\n    float fi = float(i);\n    float h1 = fract(sin(fi*12.9898+1.1)*43758.5453), h2 = fract(sin(fi*78.233+4.7)*24634.6345), h3 = fract(sin(fi*39.425+9.3)*31415.9265);\n    float a = 1.28 + h1*.62;                         // orbit radius (in R units)\n    float sp = (.05 + h2*.07) * (h3 > .5 ? 1. : -1.);\n    float th = h3*6.2831 + uTime*sp;\n    // newborn motes travel out from the core during the flare\n    if(i >= uMotesPrev && uFlare >= 0.) a *= smoothstep(0., 1., uFlare);\n    vec3 m = Msp * motePos(th, a, h1, h2);\n    float bob = sin(uTime*.4 + fi)*.02;\n    m.y += bob;\n    float depth = m.z / a;                            // -1 back .. 1 front\n    vec2 mp = m.xy * R;\n    float occl = (m.z < 0. && length(m.xy) < 1.) ? .06 : 1.;\n    float sz = (.010 + .006*h2) * (1. + .35*depth);\n    float dd = length(uv - mp);\n    float tw = .65 + .35*sin(uTime*(.6 + h1) + fi*2.);\n    float g = exp(-dd*dd/(sz*sz)) * 1.4 + exp(-dd/(sz*3.)) * .08;\n    float birth = (i >= uMotesPrev && uFlare >= 0.) ? smoothstep(.0,.4,uFlare) : 1.;\n    col += uMote * g * tw * occl * (.55 + .45*depth) * birth;\n    // comet trail along the orbit (skip pixels far from this mote)\n    if(uExtras > .5 && dd < .17){\n      float sgn = sp > 0. ? 1. : -1.;\n      for(int j=1;j<7;j++){\n        float fj = float(j);\n        vec3 mt = Msp * motePos(th - sgn*fj*.04, a, h1, h2); mt.y += bob;\n        float td = length(uv - mt.xy*R);\n        float ts = sz*(1. - fj*.1);\n        float oc = (mt.z < 0. && length(mt.xy) < 1.) ? .06 : 1.;\n        col += uMote * exp(-td*td/(ts*ts)) * .28*(1. - fj/7.) * oc * birth * (.55 + .45*mt.z/a);\n      }\n    }\n  }\n\n  col = aces(col * 1.05);\n  col = pow(col, vec3(1./2.2));\n  // dither against banding\n  col += (hash(vec3(gl_FragCoord.xy, fract(uTime))) - .5) / 255.;\n  col *= smoothstep(1.0, .78, length(uv));   // fade light to zero well before the canvas edge\n  col = max(col, 0.);\n  o = vec4(col, max(max(col.r, col.g), col.b));   // premultiplied: light adds over whatever card is behind\n}";
const PALETTES = {
  Ember:     { ramp:[[.05,.006,.001],[.32,.035,.004],[1,.2,.02],[1.15,.45,.09],[1.6,1.25,.85]], halo:[1,.30,.045], rim:[1,.70,.38], mote:[1,.78,.48], flare:[1.2,.62,.22], ring:['#ff6a13','#ff9a3a','#ffe2b0'], swatch:'#ff7a1a', tint:'rgba(255,120,30,.07)' },
  Aurora:    { ramp:[[.002,.03,.03],[.005,.16,.14],[.03,.75,.55],[.25,1.05,.8],[1,1.5,1.3]], halo:[.05,.6,.45], rim:[.55,1,.85], mote:[.7,1,.9], flare:[.4,1.2,.9], ring:['#0fb894','#3fe0b8','#c8fff0'], swatch:'#2fd6a8', tint:'rgba(40,220,170,.06)' },
  Violet:    { ramp:[[.02,.004,.05],[.12,.02,.3],[.45,.12,1],[.75,.4,1.2],[1.35,1.15,1.6]], halo:[.35,.12,1], rim:[.8,.65,1], mote:[.85,.78,1], flare:[.7,.5,1.3], ring:['#7b3fff','#a77bff','#eadcff'], swatch:'#8b5cff', tint:'rgba(130,80,255,.07)' },
  Rose:      { ramp:[[.05,.004,.01],[.3,.02,.06],[1,.12,.25],[1.15,.42,.5],[1.6,1.15,1.15]], halo:[1,.15,.3], rim:[1,.65,.7], mote:[1,.8,.82], flare:[1.2,.5,.6], ring:['#ff2d6a','#ff6f95','#ffd6e0'], swatch:'#ff4f80', tint:'rgba(255,60,110,.06)' },
  Moonlight: { ramp:[[.003,.01,.04],[.02,.07,.25],[.12,.4,1],[.45,.75,1.2],[1.3,1.4,1.6]], halo:[.15,.4,1], rim:[.7,.85,1], mote:[.85,.92,1], flare:[.6,.8,1.3], ring:['#2f7bff','#6fa8ff','#dce9ff'], swatch:'#5b95ff', tint:'rgba(80,140,255,.06)' },
};

var UNAMES=["uRes","uTime","uFlow","uBreath","uFlare","uPress","uSession","uEvo","uPtr","uSpin","uMotes","uMotesPrev","uBg","uPal","uHalo","uRim","uMote","uFlareC","uExtras"];
var TUNE={ bg:[0x0b/255,0x0a/255,0x12/255], breath:{idle:[4,6],session:[5,7]}, maxLevel:20, motes:[6,24], flareDur:1.8 };
var LEAGUE_PAL={Ember:"Ember",Spark:"Ember",Glow:"Rose",Flare:"Rose",Beacon:"Aurora",Nova:"Violet",Supernova:"Violet"};
function flat(p){return p.ramp.flat().concat(p.halo,p.rim,p.mote,p.flare);}
function mountLumenOrb(opts){
  opts=opts||{};
  if(window.__lumOrb){ try{window.__lumOrb.destroy();}catch(e){} window.__lumOrb=null; }
  var stage=document.getElementById("lumStage"); if(!stage) return;
  var canvas=document.getElementById("lumOrbCanvas"), fallback=document.getElementById("lumFallback");
  var level=opts.level||1, into=opts.into||0, need=opts.need||100;
  var progress=Math.max(0,Math.min(1,into/((into+need)||1)));
  var pal=PALETTES[opts.palette]||PALETTES.Ember;
  function qs(id){return stage.querySelector(id);}
  var g0=qs("#g0"),g1=qs("#g1"),g2=qs("#g2"),h1=qs("#h1"),h2=qs("#h2");
  if(g0)g0.setAttribute("stop-color",pal.ring[0]); if(g1)g1.setAttribute("stop-color",pal.ring[1]); if(g2)g2.setAttribute("stop-color",pal.ring[2]);
  if(h1)h1.setAttribute("stop-color",pal.ring[2]); if(h2)h2.setAttribute("stop-color",pal.ring[0]);
  var GLOPTS={antialias:false,alpha:true,premultipliedAlpha:true,powerPreference:"high-performance"};
  var gl=canvas&&canvas.getContext("webgl2",GLOPTS);
  function showFallback(){ if(canvas)canvas.style.display="none"; if(fallback){fallback.style.display="block";fallback.style.inset="24%";fallback.style.background="radial-gradient(circle at 46% 44%, "+pal.ring[2]+" 0, "+pal.swatch+" 24%, "+pal.ring[0]+" 52%, rgba(0,0,0,0) 72%)";fallback.style.boxShadow="0 0 60px 20px "+pal.tint;} }
  if(!gl){ showFallback(); return; }
  function compile(type,src){var sh=gl.createShader(type);gl.shaderSource(sh,src);gl.compileShader(sh);if(!gl.getShaderParameter(sh,gl.COMPILE_STATUS)){console.error(gl.getShaderInfoLog(sh));return null;}return sh;}
  var vs=compile(gl.VERTEX_SHADER,VS), fsh=compile(gl.FRAGMENT_SHADER,FS);
  if(!vs||!fsh){ showFallback(); return; }
  var pr=gl.createProgram();gl.attachShader(pr,vs);gl.attachShader(pr,fsh);gl.linkProgram(pr);gl.useProgram(pr);
  var buf=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buf);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,1,-1,-1,1,1,1]),gl.STATIC_DRAW);
  var loc=gl.getAttribLocation(pr,"a");gl.enableVertexAttribArray(loc);gl.vertexAttribPointer(loc,2,gl.FLOAT,false,0,0);
  var U={}; UNAMES.forEach(function(k){U[k]=gl.getUniformLocation(pr,k);});
  var S={level:level,progress:progress,session:false,reduced:matchMedia("(prefers-reduced-motion: reduce)").matches,press:0,pressT:0,ptr:[0,0],ptrT:[0,0],flare:-1,flareStart:0,levelVis:level,sessionVis:0,progVis:progress,motesPrev:99,
    spin:[0,0],spinV:[0,0],drag:false,lastX:0,lastY:0};
  function motesFor(l){return Math.round(TUNE.motes[0]+(TUNE.motes[1]-TUNE.motes[0])*Math.min((l-1)/(TUNE.maxLevel-1),1));}
  var palCur=flat(pal), palTgt=palCur.slice();
  var arcs=stage.querySelectorAll(".arc,.arcGlow"), heads=stage.querySelectorAll(".headDot");
  function drawRing(){ S.progVis+=(S.progress-S.progVis)*.08; var v=Math.max(S.progVis,.002)*1000; arcs.forEach(function(e){e.setAttribute("stroke-dasharray",v+" 1000");}); var a=S.progVis*Math.PI*2-Math.PI/2; heads.forEach(function(h){h.setAttribute("transform","translate("+(50+46*Math.cos(a))+" "+(50+46*Math.sin(a))+")");}); }
  var ease=function(x){return x<.5?4*x*x*x:1-Math.pow(-2*x+2,3)/2;};
  function breath(t){var a=S.session?TUNE.breath.session:TUNE.breath.idle;var inh=a[0],exh=a[1],c=inh+exh,x=t%c;return x<inh?ease(x/inh):1-ease((x-inh)/exh);}
  function resize(){var dpr=Math.min(window.devicePixelRatio||1,2);
    var side=Math.min(stage.clientWidth||0,stage.clientHeight||0)||stage.clientWidth||stage.offsetWidth||272;
    var w=Math.max(1,Math.round(side*dpr));
    if(canvas.width!==w){canvas.width=canvas.height=w;canvas.style.width=canvas.style.height="100%";gl.viewport(0,0,w,w);}}
  resize();
  var _ro=null;try{_ro=new ResizeObserver(function(){resize();});_ro.observe(stage);}catch(e){}
  window.addEventListener("resize",resize);
  function onMove(e){
    if(S.drag){
      var dx=e.clientX-S.lastX, dy=e.clientY-S.lastY; S.lastX=e.clientX; S.lastY=e.clientY;
      var k=0.012;
      S.spin[0]+=dx*k;
      S.spin[1]=Math.max(-1.3,Math.min(1.3,S.spin[1]+dy*k));
      S.spinV=[dx*k, dy*k];
      if(e.cancelable)e.preventDefault();
    } else {
      var r=stage.getBoundingClientRect();S.ptrT=[((e.clientX-r.left)/r.width-.5)*2,((e.clientY-r.top)/r.height-.5)*2];
    }
  }
  function onLeave(){if(!S.drag){S.ptrT=[0,0];S.pressT=0;}}
  function onDown(e){S.pressT=1;S.drag=true;S.spinV=[0,0];S.lastX=e.clientX;S.lastY=e.clientY;start();try{stage.setPointerCapture(e.pointerId);}catch(_){}}
  function onUp(e){S.pressT=0;if(S.drag){S.drag=false;try{stage.releasePointerCapture(e.pointerId);}catch(_){}}}
  function onGyro(e){if(e.gamma==null)return;S.ptrT=[Math.max(-1,Math.min(1,e.gamma/30)),Math.max(-1,Math.min(1,(e.beta-45)/30))];}
  stage.addEventListener("pointermove",onMove);stage.addEventListener("pointerleave",onLeave);stage.addEventListener("pointerdown",onDown);
  window.addEventListener("pointerup",onUp);window.addEventListener("deviceorientation",onGyro);
  var visible=true,raf=0,last=performance.now()/1000,clock=0,flow=0,dead=false;
  var io=new IntersectionObserver(function(es){es.forEach(function(e){visible=e.isIntersecting;});if(visible)start();});
  io.observe(stage);
  function onVis(){if(!document.hidden)start();}
  document.addEventListener("visibilitychange",onVis);
  function start(){if(!raf&&!dead){last=performance.now()/1000;raf=requestAnimationFrame(frame);}}
  function frame(nowMs){ raf=0; if(dead||!visible||document.hidden)return;
    var now=nowMs/1000, dt=Math.min(now-last,.05); last=now;
    var motion=S.reduced?0:1; clock+=dt*motion; flow+=dt*motion*(S.session?.75:1)*(.75+.25*Math.min((S.level-1)/10,1));
    S.press+=(S.pressT-S.press)*(1-Math.exp(-dt*(S.pressT?14:5)));
    var pt=S.reduced?[0,0]:S.ptrT; var k=1-Math.exp(-dt*6);
    S.ptr[0]+=(pt[0]-S.ptr[0])*k*.6; S.ptr[1]+=(pt[1]-S.ptr[1])*k*.6;
    // drag-to-spin with inertia: flick it and it keeps turning, then eases to rest
    if(!S.drag){ S.spin[0]+=S.spinV[0]; S.spin[1]=Math.max(-1.3,Math.min(1.3,S.spin[1]+S.spinV[1]));
      var dc=Math.pow(0.92,dt*60); S.spinV[0]*=dc; S.spinV[1]*=dc;
      if(Math.abs(S.spinV[0])<1e-4)S.spinV[0]=0; if(Math.abs(S.spinV[1])<1e-4)S.spinV[1]=0; }
    S.levelVis+=(S.level-S.levelVis)*(1-Math.exp(-dt*1.5));
    S.sessionVis+=((S.session?1:0)-S.sessionVis)*(1-Math.exp(-dt*1.2));
    var flare=-1; if(S.flare>=0){flare=(now-S.flareStart)/TUNE.flareDur;if(flare>=1){S.flare=-1;flare=-1;S.motesPrev=motesFor(S.level);}}
    var b=S.reduced?(Math.sin(now*2*Math.PI/10)*.5+.5)*.5:breath(now);
    var evo=Math.min((S.levelVis-1)/(TUNE.maxLevel-1),1);
    drawRing();
    var kp=1-Math.exp(-dt*3); for(var i=0;i<palCur.length;i++)palCur[i]+=(palTgt[i]-palCur[i])*kp;
    resize();
    gl.uniform2f(U.uRes,canvas.width,canvas.height);
    gl.uniform1f(U.uTime,clock); gl.uniform1f(U.uFlow,flow); gl.uniform1f(U.uBreath,b);
    gl.uniform1f(U.uFlare,flare); gl.uniform1f(U.uPress,Math.min(1.4,S.press+Math.min(.9,Math.hypot(S.spinV[0],S.spinV[1])*1.4))); gl.uniform1f(U.uSession,S.sessionVis);
    gl.uniform1f(U.uEvo,evo); gl.uniform2f(U.uPtr,S.ptr[0]*.5,S.ptr[1]*.5); gl.uniform2f(U.uSpin,S.spin[0],S.spin[1]);
    gl.uniform1i(U.uMotes,motesFor(S.level)); gl.uniform1i(U.uMotesPrev,S.flare>=0?S.motesPrev:99);
    gl.uniform3f(U.uBg,TUNE.bg[0],TUNE.bg[1],TUNE.bg[2]); gl.uniform1f(U.uExtras,1);
    gl.uniform3fv(U.uPal,palCur.slice(0,15)); gl.uniform3fv(U.uHalo,palCur.slice(15,18));
    gl.uniform3fv(U.uRim,palCur.slice(18,21)); gl.uniform3fv(U.uMote,palCur.slice(21,24)); gl.uniform3fv(U.uFlareC,palCur.slice(24,27));
    gl.drawArrays(gl.TRIANGLE_STRIP,0,4);
    raf=requestAnimationFrame(frame);
  }
  start();
  window.__lumOrb={ S:S, setProgress:function(p){S.progress=Math.max(0,Math.min(1,p));}, destroy:function(){ dead=true; if(raf)cancelAnimationFrame(raf); try{io.disconnect();}catch(e){} try{if(_ro)_ro.disconnect();}catch(e){} window.removeEventListener("resize",resize); document.removeEventListener("visibilitychange",onVis); window.removeEventListener("pointerup",onUp); window.removeEventListener("deviceorientation",onGyro); stage.removeEventListener("pointermove",onMove); stage.removeEventListener("pointerleave",onLeave); stage.removeEventListener("pointerdown",onDown); var lc=gl.getExtension("WEBGL_lose_context"); if(lc)lc.loseContext(); } };
}
window.mountLumenOrb=mountLumenOrb;
window.LUM_LEAGUE_PAL=LEAGUE_PAL;

})();
