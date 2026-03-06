import * as THREE from "three";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import { initHandTracking, isReady, detectHands, resetState } from "./handTracking.js";
import { createShieldScene } from "./shieldScene.js";
import { createWireframeScene } from "./wireframeScene.js";

const video = document.getElementById("inputVideo");
const statusEl = document.getElementById("status");
const toggleLandmarks = document.getElementById("toggleLandmarks");
const toggleMirror = document.getElementById("toggleMirror");
const animationMode = document.getElementById("animationMode");
const shieldControls = document.getElementById("shieldControls");
const stageShell = document.getElementById("stageShell");

let isMirror = true;
let lastFrameMs = -1;

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

function status(text) {
  statusEl.textContent = text;
}

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(window.devicePixelRatio);
renderer.setClearColor(0x000000, 1);
renderer.domElement.style.position = "absolute";
renderer.domElement.style.inset = "0";
renderer.domElement.style.width = "100%";
renderer.domElement.style.height = "100%";
renderer.domElement.style.pointerEvents = "none";
renderer.domElement.style.mixBlendMode = "screen";
stageShell.appendChild(renderer.domElement);

const oldCanvas = document.getElementById("fxCanvas");
if (oldCanvas) oldCanvas.remove();

const shield = createShieldScene();
const wire = createWireframeScene();

let activeComposer = null;
let shieldComposer = null;
let wireComposer = null;

function buildComposers(w, h) {
  renderer.setSize(w, h);

  shieldComposer = new EffectComposer(renderer);
  shieldComposer.addPass(new RenderPass(shield.scene, shield.camera));
  shieldComposer.addPass(new UnrealBloomPass(new THREE.Vector2(w, h), 1.3, 0.65, 0.12));

  wireComposer = new EffectComposer(renderer);
  wireComposer.addPass(new RenderPass(wire.scene, wire.camera));
  wireComposer.addPass(new UnrealBloomPass(new THREE.Vector2(w, h), 1.6, 0.7, 0.08));

  shield.resize(w, h);
  wire.resize(w, h);

  activeComposer = animationMode.value === "wireframe" ? wireComposer : shieldComposer;
}

function onResize() {
  const rect = stageShell.getBoundingClientRect();
  const w = Math.floor(rect.width);
  const h = Math.floor(rect.height);
  if (w > 0 && h > 0) {
    buildComposers(w, h);
  }
}

function setModeUI() {
  const isWire = animationMode.value === "wireframe";
  shieldControls.classList.toggle("hidden", isWire);
  video.style.opacity = "1";
  video.style.filter = "saturate(1.1) contrast(1.05) brightness(0.82)";
  activeComposer = isWire ? wireComposer : shieldComposer;
}

const landmarkCanvas = document.createElement("canvas");
landmarkCanvas.style.cssText = "position:absolute;inset:0;width:100%;height:100%;pointer-events:none";
stageShell.appendChild(landmarkCanvas);
const landmarkCtx = landmarkCanvas.getContext("2d");

function resizeLandmarkCanvas() {
  const rect = stageShell.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  landmarkCanvas.width = Math.floor(rect.width * dpr);
  landmarkCanvas.height = Math.floor(rect.height * dpr);
  landmarkCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
}

function drawLandmarks2D(hands) {
  const rect = stageShell.getBoundingClientRect();
  if (landmarkCanvas.width !== Math.floor(rect.width * (window.devicePixelRatio || 1))) {
    resizeLandmarkCanvas();
  }
  landmarkCtx.clearRect(0, 0, rect.width, rect.height);
  if (!toggleLandmarks.checked) return;
  landmarkCtx.fillStyle = "rgba(183, 226, 255, 0.9)";
  for (const hand of hands) {
    if (!hand.points) continue;
    for (const p of hand.points) {
      landmarkCtx.beginPath();
      landmarkCtx.arc(p.x, p.y, 2.2, 0, Math.PI * 2);
      landmarkCtx.fill();
    }
  }
}

function processFrame(now) {
  if (!isReady() || video.readyState < 2) {
    requestAnimationFrame(processFrame);
    return;
  }

  if (lastFrameMs === -1) lastFrameMs = now;
  const elapsed = clamp((now - lastFrameMs) / 1000, 0.001, 0.05);
  lastFrameMs = now;

  const rect = stageShell.getBoundingClientRect();
  const width = rect.width;
  const height = rect.height;

  const inWireMode = animationMode.value === "wireframe";
  const detectInterval = inWireMode ? 24 : 20;
  const hands = detectHands(video, now, width, height, isMirror, detectInterval);

  if (inWireMode) {
    wire.update(hands, elapsed, width, height);
    status(wire.getStatusText(hands));
  } else {
    shield.update(hands, elapsed);
    status(
      hands.length
        ? `Tracking ${hands.length} hand${hands.length > 1 ? "s" : ""} | pinch to charge`
        : "Show your hand(s) in frame to summon sigils"
    );
  }

  if (activeComposer) {
    activeComposer.render();
  }

  drawLandmarks2D(hands);

  requestAnimationFrame(processFrame);
}

async function initCamera() {
  const stream = await navigator.mediaDevices.getUserMedia({
    video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: "user" },
    audio: false
  });
  video.srcObject = stream;
  await video.play();
  video.style.transform = "scaleX(-1)";
}

async function init() {
  try {
    onResize();
    await initCamera();
    status("Loading hand tracker...");
    await initHandTracking();
    status("Hand tracker ready. Begin casting.");
    requestAnimationFrame(processFrame);
  } catch (err) {
    console.error(err);
    status("Failed to initialize camera or model. Check permissions and refresh.");
  }
}

toggleMirror.addEventListener("change", (event) => {
  isMirror = event.target.checked;
  video.style.transform = isMirror ? "scaleX(-1)" : "none";
});

animationMode.addEventListener("change", () => {
  setModeUI();
  resetState();
});

window.addEventListener("resize", () => {
  onResize();
  resizeLandmarkCanvas();
});
setModeUI();
init();
