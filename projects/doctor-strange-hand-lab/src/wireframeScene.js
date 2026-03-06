import * as THREE from "three";

const TAU = Math.PI * 2;
const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
const lerp = (a, b, t) => a + (b - a) * t;
const dist = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);

const wireState = {
  time: 0,
  speed: 0.35,
  morph: 0.25,
  glow: 0.45,
  scale: 1,
  anchorX: 0.5,
  anchorY: 0.5,
  targetAnchorX: 0.5,
  targetAnchorY: 0.5
};

const sphereVertexShader = `
  uniform float uTime;
  uniform float uMorph;
  uniform float uSpeed;
  varying float vDepth;

  void main() {
    vec3 pos = position;
    float r = length(pos);
    if (r > 0.001) {
      vec3 n = pos / r;
      float theta = acos(clamp(n.y, -1.0, 1.0));
      float phi = atan(n.z, n.x);

      float wave = sin(theta * 5.0 + uTime * 0.25) * cos(phi * 4.0 - uTime * 0.2)
                 + sin(phi * 7.0 + theta * 3.0 + uTime * 0.35) * 0.35;
      float radial = r + wave * (0.11 + uMorph * 0.19) * r;

      float torsion = uMorph * 0.4 * sin(theta * 2.0 + uTime * 0.12);
      float ct = cos(torsion);
      float st = sin(torsion);
      vec3 deformed = vec3(
        n.x * ct - n.z * st,
        n.y,
        n.x * st + n.z * ct
      ) * radial;
      pos = deformed;
    }

    vec4 mvPos = modelViewMatrix * vec4(pos, 1.0);
    vDepth = -mvPos.z;
    gl_Position = projectionMatrix * mvPos;
  }
`;

const sphereFragmentShader = `
  uniform float uGlow;
  uniform vec3 uColor;
  varying float vDepth;

  void main() {
    float depthFade = clamp(1.0 - (vDepth - 2.0) / 5.0, 0.15, 1.0);
    float alpha = (0.22 + uGlow * 0.28) * depthFade;
    gl_FragColor = vec4(uColor * (0.7 + uGlow * 0.5), alpha);
  }
`;

const FINGER_OFFSET_X = 0.025;
const FINGER_OFFSET_Y = -0.045;

function applyGestureControls(hands, width, height) {
  if (!hands.length) {
    wireState.targetAnchorX = lerp(wireState.targetAnchorX, 0.5, 0.06);
    wireState.targetAnchorY = lerp(wireState.targetAnchorY, 0.5, 0.06);
    wireState.speed = lerp(wireState.speed, 0.35, 0.03);
    wireState.morph = lerp(wireState.morph, 0.25, 0.04);
    wireState.glow = lerp(wireState.glow, 0.45, 0.04);
    wireState.scale = lerp(wireState.scale, 1, 0.05);
    return;
  }

  const primary = hands[0];
  const followX = clamp(primary.indexTip.x / width + FINGER_OFFSET_X, 0, 1);
  const followY = clamp(primary.indexTip.y / height + FINGER_OFFSET_Y, 0, 1);
  wireState.targetAnchorX = followX;
  wireState.targetAnchorY = followY;

  const morphTarget = 0.15 + Math.abs(primary.rotation % TAU) * 0.12;
  const glowTarget = 0.4 + primary.pinchFactor * 0.35;
  const scaleTarget = 1.0;

  let speedTarget = 0.35;
  if (hands.length > 1) {
    const secondary = hands[1];
    speedTarget = 0.08 + secondary.pinchFactor * 1.4;
    wireState.glow = lerp(wireState.glow, clamp(glowTarget + secondary.pinchFactor * 0.2, 0.15, 1), 0.08);
  } else {
    wireState.glow = lerp(wireState.glow, clamp(glowTarget, 0.15, 1), 0.08);
  }

  wireState.speed = lerp(wireState.speed, clamp(speedTarget, 0.08, 1.5), 0.04);
  wireState.morph = lerp(wireState.morph, clamp(morphTarget, 0.05, 0.85), 0.08);
  wireState.scale = lerp(wireState.scale, scaleTarget, 0.08);
}

const FRAG_COUNT = 320;
const SHARD_PARTICLE_COUNT = 1600;

const fragmentVertexShader = `
  attribute vec3 aOffset;
  attribute vec3 aVelocity;
  attribute vec4 aRotation;
  attribute float aLife;
  attribute float aScale;
  varying float vAlpha;
  varying float vHeat;

  vec3 applyQuat(vec4 q, vec3 v) {
    vec3 t = 2.0 * cross(q.xyz, v);
    return v + q.w * t + cross(q.xyz, t);
  }

  void main() {
    vAlpha = aLife;
    vHeat = clamp(aLife * 1.5, 0.0, 1.0);
    float speed = length(aVelocity);
    float stretch = 1.0 + speed * 0.12;
    vec3 pos = position * aScale;
    pos.y *= stretch;
    pos = applyQuat(aRotation, pos);
    pos += aOffset;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(pos, 1.0);
  }
`;

const fragmentFragmentShader = `
  varying float vAlpha;
  varying float vHeat;

  void main() {
    vec3 hot = vec3(1.0, 1.0, 1.0);
    vec3 mid = vec3(0.4, 0.8, 1.0);
    vec3 cool = vec3(0.3, 0.35, 0.9);
    vec3 col = mix(cool, mix(mid, hot, vHeat), vHeat);
    float edge = 0.85 + vHeat * 0.5;
    gl_FragColor = vec4(col * edge, vAlpha * 0.9);
  }
`;

function buildTriangleGeo() {
  const verts = new Float32Array([
    -0.02, -0.015, 0,
     0.02, -0.015, 0,
     0.0,   0.022, 0
  ]);
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(verts, 3));
  return geo;
}

function extractFaceCentroids(geo) {
  const pos = geo.attributes.position;
  const idx = geo.index;
  const centroids = [];
  const normals = [];
  const faceCount = idx ? idx.count / 3 : pos.count / 3;
  const v = [new THREE.Vector3(), new THREE.Vector3(), new THREE.Vector3()];

  for (let f = 0; f < faceCount; f++) {
    for (let k = 0; k < 3; k++) {
      const i = idx ? idx.getX(f * 3 + k) : f * 3 + k;
      v[k].set(pos.getX(i), pos.getY(i), pos.getZ(i));
    }
    const cx = (v[0].x + v[1].x + v[2].x) / 3;
    const cy = (v[0].y + v[1].y + v[2].y) / 3;
    const cz = (v[0].z + v[1].z + v[2].z) / 3;
    centroids.push(new THREE.Vector3(cx, cy, cz));
    const edge1 = new THREE.Vector3().subVectors(v[1], v[0]);
    const edge2 = new THREE.Vector3().subVectors(v[2], v[0]);
    normals.push(new THREE.Vector3().crossVectors(edge1, edge2).normalize());
  }
  return { centroids, normals };
}

export function createWireframeScene() {
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(50, 1, 0.1, 100);
  camera.position.z = 5;

  const sphereGeo = new THREE.IcosahedronGeometry(1, 5);

  const sphereMat = new THREE.ShaderMaterial({
    uniforms: {
      uTime: { value: 0 },
      uMorph: { value: wireState.morph },
      uSpeed: { value: wireState.speed },
      uGlow: { value: wireState.glow },
      uColor: { value: new THREE.Color(0.4, 0.75, 1.0) }
    },
    vertexShader: sphereVertexShader,
    fragmentShader: sphereFragmentShader,
    transparent: true,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
    wireframe: true
  });

  const wireMesh = new THREE.Mesh(sphereGeo, sphereMat);
  scene.add(wireMesh);

  const ringMeshes = [];
  for (let k = 0; k < 2; k++) {
    const torusGeo = new THREE.TorusGeometry(0.56 + k * 0.17, 0.008, 8, 48);
    const torusMat = new THREE.MeshBasicMaterial({
      color: k === 0 ? 0x60c8ff : 0x80d8ff,
      transparent: true,
      opacity: 0.3,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      wireframe: true
    });
    const ring = new THREE.Mesh(torusGeo, torusMat);
    ring.rotation.x = 0.25 + k * 0.35;
    ring.rotation.z = 0.2 + k * 0.5;
    ringMeshes.push(ring);
    scene.add(ring);
  }

  const coreGlowTex = (() => {
    const c = document.createElement("canvas");
    c.width = c.height = 128;
    const cx = c.getContext("2d");
    const g = cx.createRadialGradient(64, 64, 0, 64, 64, 64);
    g.addColorStop(0, "rgba(128, 220, 255, 0.9)");
    g.addColorStop(0.5, "rgba(80, 180, 255, 0.3)");
    g.addColorStop(1, "rgba(80, 200, 255, 0)");
    cx.fillStyle = g;
    cx.fillRect(0, 0, 128, 128);
    return new THREE.CanvasTexture(c);
  })();

  const coreSprite = new THREE.Sprite(
    new THREE.SpriteMaterial({
      map: coreGlowTex,
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false
    })
  );
  coreSprite.scale.set(0.8, 0.8, 1);
  scene.add(coreSprite);

  const shockGeo = new THREE.RingGeometry(0.9, 1.0, 48);
  const shockMat = new THREE.MeshBasicMaterial({
    color: 0x80d8ff,
    transparent: true,
    opacity: 0,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
    side: THREE.DoubleSide
  });
  const shockwave = new THREE.Mesh(shockGeo, shockMat);
  shockwave.visible = false;
  scene.add(shockwave);

  const flashSpriteTex = (() => {
    const c = document.createElement("canvas");
    c.width = c.height = 64;
    const cx = c.getContext("2d");
    const g = cx.createRadialGradient(32, 32, 0, 32, 32, 32);
    g.addColorStop(0, "rgba(200, 240, 255, 1)");
    g.addColorStop(0.3, "rgba(120, 200, 255, 0.6)");
    g.addColorStop(1, "rgba(80, 180, 255, 0)");
    cx.fillStyle = g;
    cx.fillRect(0, 0, 64, 64);
    return new THREE.CanvasTexture(c);
  })();
  const flashSprite = new THREE.Sprite(
    new THREE.SpriteMaterial({
      map: flashSpriteTex,
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      opacity: 0
    })
  );
  flashSprite.visible = false;
  scene.add(flashSprite);

  const fragSourceGeo = new THREE.IcosahedronGeometry(1, 2);
  const { centroids: fragCentroids, normals: fragNormals } = extractFaceCentroids(fragSourceGeo);
  const triGeo = buildTriangleGeo();
  const fragMat = new THREE.ShaderMaterial({
    uniforms: { uColor: { value: new THREE.Color(0.5, 0.85, 1.0) } },
    vertexShader: fragmentVertexShader,
    fragmentShader: fragmentFragmentShader,
    transparent: true,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
    side: THREE.DoubleSide
  });

  const fragOffsets = new Float32Array(FRAG_COUNT * 3);
  const fragRotations = new Float32Array(FRAG_COUNT * 4);
  const fragLifes = new Float32Array(FRAG_COUNT);
  const fragScales = new Float32Array(FRAG_COUNT);
  const fragVelocities = new Float32Array(FRAG_COUNT * 3);
  const fragAngVel = new Float32Array(FRAG_COUNT * 3);

  const fragInstanceGeo = triGeo.clone();
  fragInstanceGeo.setAttribute("aOffset", new THREE.InstancedBufferAttribute(fragOffsets, 3));
  fragInstanceGeo.setAttribute("aVelocity", new THREE.InstancedBufferAttribute(fragVelocities, 3));
  fragInstanceGeo.setAttribute("aRotation", new THREE.InstancedBufferAttribute(fragRotations, 4));
  fragInstanceGeo.setAttribute("aLife", new THREE.InstancedBufferAttribute(fragLifes, 1));
  fragInstanceGeo.setAttribute("aScale", new THREE.InstancedBufferAttribute(fragScales, 1));

  const fragMesh = new THREE.InstancedMesh(fragInstanceGeo, fragMat, FRAG_COUNT);
  fragMesh.visible = false;
  scene.add(fragMesh);

  const shardPositions = new Float32Array(SHARD_PARTICLE_COUNT * 3);
  const shardVelocities = new Float32Array(SHARD_PARTICLE_COUNT * 3);
  const shardLifes = new Float32Array(SHARD_PARTICLE_COUNT);
  const shardSizes = new Float32Array(SHARD_PARTICLE_COUNT);
  const shardGeo = new THREE.BufferGeometry();
  shardGeo.setAttribute("position", new THREE.BufferAttribute(shardPositions, 3));
  shardGeo.setAttribute("aLife", new THREE.BufferAttribute(shardLifes, 1));
  shardGeo.setAttribute("aSize", new THREE.BufferAttribute(shardSizes, 1));
  const shardMat = new THREE.ShaderMaterial({
    vertexShader: `
      attribute float aLife;
      attribute float aSize;
      varying float vAlpha;
      varying float vHeat;
      void main() {
        vAlpha = clamp(aLife, 0.0, 1.0);
        vHeat = vAlpha;
        vec4 mvPos = modelViewMatrix * vec4(position, 1.0);
        gl_PointSize = aSize * (0.4 + vAlpha * 0.6) * (250.0 / -mvPos.z);
        gl_Position = projectionMatrix * mvPos;
      }
    `,
    fragmentShader: `
      varying float vAlpha;
      varying float vHeat;
      void main() {
        float d = length(gl_PointCoord - vec2(0.5));
        if (d > 0.5) discard;
        float falloff = 1.0 - smoothstep(0.0, 0.5, d);
        vec3 hot = vec3(1.0, 1.0, 1.0);
        vec3 mid = vec3(0.45, 0.82, 1.0);
        vec3 cool = vec3(0.25, 0.3, 0.85);
        vec3 col = mix(cool, mix(mid, hot, vHeat), vHeat);
        gl_FragColor = vec4(col, vAlpha * falloff * 0.8);
      }
    `,
    transparent: true,
    blending: THREE.AdditiveBlending,
    depthWrite: false
  });
  const shardPoints = new THREE.Points(shardGeo, shardMat);
  shardPoints.visible = false;
  scene.add(shardPoints);

  let shardNextIdx = 0;

  const shockwave2 = shockwave.clone();
  shockwave2.material = shockMat.clone();
  shockwave2.visible = false;
  scene.add(shockwave2);
  const shockwave3 = shockwave.clone();
  shockwave3.material = shockMat.clone();
  shockwave3.visible = false;
  scene.add(shockwave3);

  const TENDRIL_COUNT = 12;
  const TENDRIL_SEGS = 8;
  const tendrilLines = [];
  for (let i = 0; i < TENDRIL_COUNT; i++) {
    const pts = new Float32Array(TENDRIL_SEGS * 3);
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(pts, 3));
    const mat = new THREE.LineBasicMaterial({
      color: 0x80d8ff,
      transparent: true,
      opacity: 0,
      blending: THREE.AdditiveBlending,
      depthWrite: false
    });
    const line = new THREE.Line(geo, mat);
    line.visible = false;
    scene.add(line);
    const angle = (i / TENDRIL_COUNT) * TAU;
    const elevate = (Math.random() - 0.5) * 1.2;
    tendrilLines.push({
      line, geo, mat, pts,
      dir: new THREE.Vector3(Math.cos(angle), elevate, Math.sin(angle)).normalize(),
      speed: 2.5 + Math.random() * 3.5,
      curl: (Math.random() - 0.5) * 2.5
    });
  }

  const explosion = {
    phase: "idle",
    timer: 0,
    origin: new THREE.Vector3(),
    recentPeakPinch: 0,
    cooldown: 0
  };

  const EXPLODE_DURATION = 3.2;
  const REFORM_DURATION = 1.8;

  function triggerExplosion(worldPos) {
    explosion.phase = "exploding";
    explosion.timer = 0;
    explosion.origin.copy(worldPos);
    explosion.cooldown = EXPLODE_DURATION + REFORM_DURATION + 1.0;

    wireMesh.visible = false;
    ringMeshes.forEach((r) => (r.visible = false));
    fragMesh.visible = true;
    shardPoints.visible = true;
    shockwave.visible = true;
    shockwave2.visible = true;
    shockwave3.visible = true;
    flashSprite.visible = true;
    tendrilLines.forEach((t) => (t.line.visible = true));

    const usedCentroids = Math.min(FRAG_COUNT, fragCentroids.length);
    for (let i = 0; i < FRAG_COUNT; i++) {
      const src = i % usedCentroids;
      const c = fragCentroids[src];
      const n = fragNormals[src];

      fragOffsets[i * 3] = worldPos.x + c.x * wireState.scale;
      fragOffsets[i * 3 + 1] = worldPos.y + c.y * wireState.scale;
      fragOffsets[i * 3 + 2] = worldPos.z + c.z * wireState.scale;

      const speed = 2.2 + Math.random() * 4.0;
      fragVelocities[i * 3] = n.x * speed + (Math.random() - 0.5) * 1.6;
      fragVelocities[i * 3 + 1] = n.y * speed + (Math.random() - 0.5) * 1.6;
      fragVelocities[i * 3 + 2] = n.z * speed + (Math.random() - 0.5) * 0.8;

      fragAngVel[i * 3] = (Math.random() - 0.5) * 10;
      fragAngVel[i * 3 + 1] = (Math.random() - 0.5) * 10;
      fragAngVel[i * 3 + 2] = (Math.random() - 0.5) * 10;

      const axis = new THREE.Vector3(Math.random() - 0.5, Math.random() - 0.5, Math.random() - 0.5).normalize();
      const q = new THREE.Quaternion().setFromAxisAngle(axis, Math.random() * TAU);
      fragRotations[i * 4] = q.x;
      fragRotations[i * 4 + 1] = q.y;
      fragRotations[i * 4 + 2] = q.z;
      fragRotations[i * 4 + 3] = q.w;

      fragLifes[i] = 1.0;
      fragScales[i] = 5 + Math.random() * 12;
    }

    for (let i = 0; i < Math.min(180, SHARD_PARTICLE_COUNT); i++) {
      const si = shardNextIdx % SHARD_PARTICLE_COUNT;
      shardNextIdx++;
      const a = Math.random() * TAU;
      const el = (Math.random() - 0.5) * Math.PI;
      const spd = 1.5 + Math.random() * 4;
      shardPositions[si * 3] = worldPos.x;
      shardPositions[si * 3 + 1] = worldPos.y;
      shardPositions[si * 3 + 2] = worldPos.z;
      shardVelocities[si * 3] = Math.cos(a) * Math.cos(el) * spd;
      shardVelocities[si * 3 + 1] = Math.sin(el) * spd;
      shardVelocities[si * 3 + 2] = Math.sin(a) * Math.cos(el) * spd * 0.4;
      shardLifes[si] = 0.6 + Math.random() * 0.9;
      shardSizes[si] = 3 + Math.random() * 6;
    }
  }

  function updateExplosion(dt) {
    if (explosion.cooldown > 0) explosion.cooldown -= dt;

    if (explosion.phase === "exploding") {
      explosion.timer += dt;
      const p = clamp(explosion.timer / EXPLODE_DURATION, 0, 1);
      const easeOut = 1 - (1 - p) * (1 - p);

      const drag = 0.965;
      for (let i = 0; i < FRAG_COUNT; i++) {
        fragVelocities[i * 3] *= drag;
        fragVelocities[i * 3 + 1] *= drag;
        fragVelocities[i * 3 + 2] *= drag;
        fragVelocities[i * 3 + 1] -= 0.2 * dt;

        fragOffsets[i * 3] += fragVelocities[i * 3] * dt;
        fragOffsets[i * 3 + 1] += fragVelocities[i * 3 + 1] * dt;
        fragOffsets[i * 3 + 2] += fragVelocities[i * 3 + 2] * dt;

        const q = new THREE.Quaternion(
          fragRotations[i * 4], fragRotations[i * 4 + 1],
          fragRotations[i * 4 + 2], fragRotations[i * 4 + 3]
        );
        const dq = new THREE.Quaternion().setFromEuler(
          new THREE.Euler(
            fragAngVel[i * 3] * dt,
            fragAngVel[i * 3 + 1] * dt,
            fragAngVel[i * 3 + 2] * dt
          )
        );
        q.multiply(dq).normalize();
        fragRotations[i * 4] = q.x;
        fragRotations[i * 4 + 1] = q.y;
        fragRotations[i * 4 + 2] = q.z;
        fragRotations[i * 4 + 3] = q.w;

        const fadeStart = 0.4;
        fragLifes[i] = p < fadeStart ? 1.0 : clamp(1 - (p - fadeStart) / (1 - fadeStart), 0, 1);
        fragScales[i] *= (1 - 0.2 * dt);
        fragAngVel[i * 3] *= 0.995;
        fragAngVel[i * 3 + 1] *= 0.995;
        fragAngVel[i * 3 + 2] *= 0.995;

        const trailChance = p < 0.5 ? 0.35 : 0.12;
        if (Math.random() < trailChance && fragLifes[i] > 0.1) {
          const si = shardNextIdx % SHARD_PARTICLE_COUNT;
          shardNextIdx++;
          shardPositions[si * 3] = fragOffsets[i * 3];
          shardPositions[si * 3 + 1] = fragOffsets[i * 3 + 1];
          shardPositions[si * 3 + 2] = fragOffsets[i * 3 + 2];
          shardVelocities[si * 3] = fragVelocities[i * 3] * 0.15 + (Math.random() - 0.5) * 0.3;
          shardVelocities[si * 3 + 1] = fragVelocities[i * 3 + 1] * 0.15 + (Math.random() - 0.5) * 0.3;
          shardVelocities[si * 3 + 2] = fragVelocities[i * 3 + 2] * 0.15;
          shardLifes[si] = 0.3 + Math.random() * 0.7;
          shardSizes[si] = 1.5 + Math.random() * 3.5;
        }

        if (p > 0.35 && fragLifes[i] > 0 && fragLifes[i] < 0.35 && Math.random() < 0.08) {
          for (let k = 0; k < 3; k++) {
            const si = shardNextIdx % SHARD_PARTICLE_COUNT;
            shardNextIdx++;
            shardPositions[si * 3] = fragOffsets[i * 3];
            shardPositions[si * 3 + 1] = fragOffsets[i * 3 + 1];
            shardPositions[si * 3 + 2] = fragOffsets[i * 3 + 2];
            const a = Math.random() * TAU;
            const spd = 0.3 + Math.random() * 0.8;
            shardVelocities[si * 3] = Math.cos(a) * spd;
            shardVelocities[si * 3 + 1] = Math.sin(a) * spd;
            shardVelocities[si * 3 + 2] = (Math.random() - 0.5) * 0.3;
            shardLifes[si] = 0.2 + Math.random() * 0.4;
            shardSizes[si] = 1 + Math.random() * 2;
          }
        }
      }

      const updateShock = (mesh, mat, delay, maxScale, fadeSpeed) => {
        const st = clamp((explosion.timer - delay) / (EXPLODE_DURATION - delay), 0, 1);
        if (st <= 0) { mat.opacity = 0; return; }
        const se = 1 - (1 - st) * (1 - st);
        const sc = 0.3 + se * maxScale;
        mesh.position.copy(explosion.origin);
        mesh.scale.set(sc, sc, 1);
        mesh.lookAt(camera.position);
        mat.opacity = clamp(fadeSpeed * (1 - se), 0, 1);
      };
      updateShock(shockwave, shockMat, 0, 10, 0.65);
      updateShock(shockwave2, shockwave2.material, 0.12, 7, 0.45);
      updateShock(shockwave3, shockwave3.material, 0.28, 13, 0.3);

      flashSprite.position.copy(explosion.origin);
      const flashP = clamp(explosion.timer / 0.5, 0, 1);
      const flashScale = 1.5 + flashP * 8;
      flashSprite.scale.set(flashScale, flashScale, 1);
      flashSprite.material.opacity = clamp((1 - flashP) * (1 - flashP), 0, 1);

      for (const t of tendrilLines) {
        const tp = clamp(explosion.timer / (EXPLODE_DURATION * 0.6), 0, 1);
        const tFade = clamp(1 - (tp - 0.4) / 0.6, 0, 1);
        t.mat.opacity = tFade * 0.55;
        for (let s = 0; s < TENDRIL_SEGS; s++) {
          const segP = (s / (TENDRIL_SEGS - 1)) * tp * t.speed;
          const curl = Math.sin(segP * 3 + explosion.timer * 2) * t.curl * 0.08;
          t.pts[s * 3] = explosion.origin.x + t.dir.x * segP + curl;
          t.pts[s * 3 + 1] = explosion.origin.y + t.dir.y * segP + Math.cos(segP * 2 + explosion.timer) * t.curl * 0.06;
          t.pts[s * 3 + 2] = explosion.origin.z + t.dir.z * segP;
        }
        t.geo.attributes.position.needsUpdate = true;
      }

      fragInstanceGeo.attributes.aOffset.needsUpdate = true;
      fragInstanceGeo.attributes.aVelocity.needsUpdate = true;
      fragInstanceGeo.attributes.aRotation.needsUpdate = true;
      fragInstanceGeo.attributes.aLife.needsUpdate = true;
      fragInstanceGeo.attributes.aScale.needsUpdate = true;

      if (p >= 1) {
        explosion.phase = "reforming";
        explosion.timer = 0;
        fragMesh.visible = false;
        shockwave.visible = false;
        shockwave2.visible = false;
        shockwave3.visible = false;
        flashSprite.visible = false;
        tendrilLines.forEach((t) => (t.line.visible = false));
      }
    }

    if (explosion.phase === "reforming") {
      explosion.timer += dt;
      const p = clamp(explosion.timer / REFORM_DURATION, 0, 1);
      const easeIn = p * p * (3 - 2 * p);

      wireMesh.visible = true;
      ringMeshes.forEach((r) => (r.visible = true));
      wireMesh.scale.set(easeIn * wireState.scale, easeIn * wireState.scale, easeIn * wireState.scale);
      sphereMat.uniforms.uGlow.value = wireState.glow * easeIn + (1 - easeIn) * 1.2;

      for (let k = 0; k < ringMeshes.length; k++) {
        ringMeshes[k].scale.set(easeIn * wireState.scale, easeIn * wireState.scale, easeIn * wireState.scale);
        ringMeshes[k].material.opacity = easeIn * (0.2 + wireState.glow * 0.25);
      }

      coreSprite.material.opacity = (0.3 + wireState.glow * 0.3) * easeIn + (1 - easeIn) * 0.8;
      const coreScale = 0.6 * wireState.scale * (easeIn + (1 - easeIn) * 2.5);
      coreSprite.scale.set(coreScale, coreScale, 1);

      if (p >= 1) {
        explosion.phase = "idle";
        shardPoints.visible = false;
      }
    }

    for (let i = 0; i < SHARD_PARTICLE_COUNT; i++) {
      if (shardLifes[i] <= 0) continue;
      shardPositions[i * 3] += shardVelocities[i * 3] * dt;
      shardPositions[i * 3 + 1] += shardVelocities[i * 3 + 1] * dt;
      shardPositions[i * 3 + 2] += shardVelocities[i * 3 + 2] * dt;
      shardVelocities[i * 3] *= 0.992;
      shardVelocities[i * 3 + 1] *= 0.992;
      shardVelocities[i * 3 + 1] -= 0.1 * dt;
      shardLifes[i] -= dt * 0.75;
    }
    shardGeo.attributes.position.needsUpdate = true;
    shardGeo.attributes.aLife.needsUpdate = true;
  }

  const anchorGeo = new THREE.RingGeometry(0.04, 0.06, 16);
  const anchorMat = new THREE.MeshBasicMaterial({
    color: 0x60c8ff,
    transparent: true,
    opacity: 0.5,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
    side: THREE.DoubleSide
  });
  const anchorMeshes = [
    new THREE.Mesh(anchorGeo, anchorMat.clone()),
    new THREE.Mesh(anchorGeo, anchorMat.clone())
  ];
  anchorMeshes.forEach((m) => {
    m.visible = false;
    scene.add(m);
  });

  function resize(w, h) {
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }

  function screenToWorld(sx, sy, w, h) {
    const nx = (sx / w) * 2 - 1;
    const ny = -(sy / h) * 2 + 1;
    const vec = new THREE.Vector3(nx, ny, 0.5);
    vec.unproject(camera);
    const dir = vec.sub(camera.position).normalize();
    const t = -camera.position.z / dir.z;
    return camera.position.clone().add(dir.multiplyScalar(t));
  }

  function update(hands, dt, width, height) {
    applyGestureControls(hands, width, height);

    wireState.time += dt;
    wireState.anchorX = lerp(wireState.anchorX, wireState.targetAnchorX, 0.16);
    wireState.anchorY = lerp(wireState.anchorY, wireState.targetAnchorY, 0.16);

    const t = wireState.time;
    const worldPos = screenToWorld(wireState.anchorX * width, wireState.anchorY * height, width, height);

    if (hands.length > 0) {
      const currentPinch = hands[0].pinchFactor;
      explosion.recentPeakPinch = Math.max(currentPinch, explosion.recentPeakPinch * 0.98);
      const wasPinching = explosion.recentPeakPinch > 0.45;
      const nowOpen = currentPinch < 0.12;
      if (wasPinching && nowOpen && explosion.cooldown <= 0 && explosion.phase === "idle") {
        triggerExplosion(worldPos);
        explosion.recentPeakPinch = 0;
      }
    } else {
      explosion.recentPeakPinch *= 0.9;
    }

    updateExplosion(dt);

    if (explosion.phase === "idle") {
      wireMesh.position.copy(worldPos);
      coreSprite.position.copy(worldPos);
      ringMeshes.forEach((r) => r.position.copy(worldPos));

      const s = wireState.scale;
      wireMesh.scale.set(s, s, s);

      const spin = t * wireState.speed;
      wireMesh.rotation.x = 0.6;
      wireMesh.rotation.y = spin;
      wireMesh.rotation.z = 0;

      sphereMat.uniforms.uTime.value = t;
      sphereMat.uniforms.uMorph.value = wireState.morph;
      sphereMat.uniforms.uSpeed.value = wireState.speed;
      sphereMat.uniforms.uGlow.value = wireState.glow;

      for (let k = 0; k < ringMeshes.length; k++) {
        const ring = ringMeshes[k];
        const ringSpin = t * wireState.speed * (0.35 + k * 0.15) * (k % 2 ? -1 : 1);
        ring.rotation.y = ringSpin;
        ring.scale.set(s, s, s);
        ring.material.opacity = 0.2 + wireState.glow * 0.25;
      }

      coreSprite.material.opacity = 0.3 + wireState.glow * 0.3;
      coreSprite.scale.set(0.6 * s, 0.6 * s, 1);
    } else if (explosion.phase === "reforming") {
      wireMesh.position.copy(worldPos);
      coreSprite.position.copy(worldPos);
      ringMeshes.forEach((r) => r.position.copy(worldPos));

      const spin = t * wireState.speed;
      wireMesh.rotation.x = 0.6;
      wireMesh.rotation.y = spin;
      wireMesh.rotation.z = 0;

      sphereMat.uniforms.uTime.value = t;
      sphereMat.uniforms.uMorph.value = wireState.morph;
      sphereMat.uniforms.uGlow.value = wireState.glow;
    }

    for (let i = 0; i < anchorMeshes.length; i++) {
      if (i < hands.length) {
        anchorMeshes[i].visible = true;
        const wp = screenToWorld(hands[i].indexTip.x, hands[i].indexTip.y, width, height);
        anchorMeshes[i].position.set(wp.x, wp.y, wp.z + 0.1);
        const aScale = 0.5 + hands[i].pinchFactor * 1.2;
        anchorMeshes[i].scale.set(aScale, aScale, 1);
        anchorMeshes[i].material.opacity = 0.3 + hands[i].pinchFactor * 0.4;
      } else {
        anchorMeshes[i].visible = false;
      }
    }
  }

  function getStatusText(hands) {
    if (explosion.phase === "exploding") return "...";
    if (explosion.phase === "reforming") return "Reforming...";
    if (!hands.length) return "Show your hand to summon the artifact";
    if (hands.length === 1) return "Pinch then open palm to detonate | rotate palm to morph | 2nd hand pinch = speed";
    return "Open palm = detonate | 2nd hand pinch = speed | rotate palm to morph";
  }

  return { scene, camera, resize, update, getStatusText };
}
