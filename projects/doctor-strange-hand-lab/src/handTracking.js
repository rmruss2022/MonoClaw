import { FilesetResolver, HandLandmarker } from "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/+esm";

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
const dist = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
const lerp = (a, b, t) => a + (b - a) * t;
const smoothstep = (x) => x * x * (3 - 2 * x);

let handLandmarker = null;
let previousHands = new Map();
let cachedResults = { landmarks: [], handedness: [] };
let lastDetectMs = -Infinity;

export async function initHandTracking() {
  const vision = await FilesetResolver.forVisionTasks(
    "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm"
  );
  handLandmarker = await HandLandmarker.createFromOptions(vision, {
    baseOptions: {
      modelAssetPath:
        "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task",
      delegate: "GPU"
    },
    numHands: 2,
    runningMode: "VIDEO"
  });
}

export function isReady() {
  return handLandmarker !== null;
}

export function resetState() {
  previousHands.clear();
  cachedResults = { landmarks: [], handedness: [] };
  lastDetectMs = -Infinity;
}

function normToPx(point, width, height, mirror) {
  return {
    x: (mirror ? 1 - point.x : point.x) * width,
    y: point.y * height
  };
}

function getPalmCenter(points) {
  const palmIndices = [0, 5, 9, 13, 17];
  let x = 0;
  let y = 0;
  for (const idx of palmIndices) {
    x += points[idx].x;
    y += points[idx].y;
  }
  return { x: x / palmIndices.length, y: y / palmIndices.length };
}

export function detectHands(video, now, width, height, mirror, detectIntervalMs = 20) {
  if (!handLandmarker || video.readyState < 2) return [];

  if (now - lastDetectMs >= detectIntervalMs) {
    cachedResults = handLandmarker.detectForVideo(video, now);
    lastDetectMs = now;
  }

  const results = cachedResults;
  const hands = [];

  for (let i = 0; i < results.landmarks.length; i += 1) {
    const landmarks = results.landmarks[i];
    const handedness = results.handedness[i]?.[0]?.categoryName || "Unknown";
    const points = landmarks.map((p) => normToPx(p, width, height, mirror));

    const wrist = points[0];
    const indexTip = points[8];
    const thumbTip = points[4];
    const middleMcp = points[9];
    const pinkyMcp = points[17];
    const palmCenterRaw = getPalmCenter(points);
    const wristToPalm = { x: middleMcp.x - wrist.x, y: middleMcp.y - wrist.y };
    const anchor = {
      x: palmCenterRaw.x + wristToPalm.x * 0.15,
      y: palmCenterRaw.y + wristToPalm.y * 0.15
    };

    const pinch = dist(indexTip, thumbTip);
    const palm = dist(middleMcp, wrist) + dist(middleMcp, pinkyMcp) * 0.35;
    const pinchRatio = pinch / Math.max(10, palm);
    const angle = Math.atan2(indexTip.y - anchor.y, indexTip.x - anchor.x);

    const prev = previousHands.get(handedness);
    const pinchMin = prev ? Math.min(prev.pinchMin * 0.985 + pinchRatio * 0.015, pinchRatio) : pinchRatio;
    const pinchMax = prev ? Math.max(prev.pinchMax * 0.985 + pinchRatio * 0.015, pinchRatio) : pinchRatio + 0.25;
    const pinchRange = Math.max(0.06, pinchMax - pinchMin);
    let pinchFactor = clamp((pinchMax - pinchRatio) / pinchRange, 0, 1);
    pinchFactor = smoothstep(pinchFactor);
    const smoothedPinch = prev ? lerp(prev.pinchFactor, pinchFactor, 0.22) : pinchFactor;

    const center = prev
      ? { x: lerp(prev.center.x, anchor.x, 0.35), y: lerp(prev.center.y, anchor.y, 0.35) }
      : anchor;

    const radiusRaw = clamp(palm * (1.05 + smoothedPinch * 1.05), 40, 230);
    const radius = prev ? lerp(prev.radius, radiusRaw, 0.28) : radiusRaw;

    let angleDelta = 0;
    if (prev) {
      angleDelta = angle - prev.angle;
      if (angleDelta > Math.PI) angleDelta -= Math.PI * 2;
      if (angleDelta < -Math.PI) angleDelta += Math.PI * 2;
    }
    const spin = prev ? prev.spin + angleDelta * 3.8 : 0;
    const smoothedSpin = prev ? lerp(prev.spin, spin, 0.18) : 0;
    const elapsed = prev ? clamp((now - (prev.lastMs || now)) / 1000, 0.001, 0.05) : 0;
    const rotation = (prev?.rotation || 0) + smoothedSpin * elapsed;

    previousHands.set(handedness, {
      angle,
      spin: smoothedSpin,
      rotation,
      pinchMin,
      pinchMax,
      pinchFactor: smoothedPinch,
      center,
      radius,
      lastMs: now
    });

    hands.push({
      handedness,
      center,
      indexTip,
      points,
      radius,
      pinchFactor: smoothedPinch,
      rotation,
      spin: smoothedSpin
    });
  }

  return hands;
}
