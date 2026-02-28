import * as THREE from "three";

const TAU = Math.PI * 2;

function createRingGeometry(innerR, outerR, segments = 64) {
  const geo = new THREE.RingGeometry(innerR, outerR, segments);
  return geo;
}

function createCircleLine(radius, segments = 64) {
  const pts = [];
  for (let i = 0; i <= segments; i++) {
    const a = (i / segments) * TAU;
    pts.push(new THREE.Vector3(Math.cos(a) * radius, Math.sin(a) * radius, 0));
  }
  return new THREE.BufferGeometry().setFromPoints(pts);
}

function createPetalRosetteGeo(baseR, tipR, petals, innerPull = 0.76) {
  const pts = [];
  const seg = TAU / petals;
  const curveRes = 10;
  for (let i = 0; i < petals; i++) {
    const a = i * seg;
    const centerA = a + seg * 0.5;
    const left = centerA - seg * 0.28;
    const right = centerA + seg * 0.28;
    const p0 = new THREE.Vector2(Math.cos(left) * baseR, Math.sin(left) * baseR);
    const cp1 = new THREE.Vector2(Math.cos(centerA) * tipR, Math.sin(centerA) * tipR);
    const p1 = new THREE.Vector2(Math.cos(right) * baseR, Math.sin(right) * baseR);
    const cp2 = new THREE.Vector2(Math.cos(centerA) * baseR * innerPull, Math.sin(centerA) * baseR * innerPull);

    const outer = new THREE.QuadraticBezierCurve(p0, cp1, p1);
    const inner = new THREE.QuadraticBezierCurve(p1, cp2, p0);
    const outerPts = outer.getPoints(curveRes);
    const innerPts = inner.getPoints(curveRes);
    for (let j = 0; j < outerPts.length - 1; j++) {
      pts.push(new THREE.Vector3(outerPts[j].x, outerPts[j].y, 0));
      pts.push(new THREE.Vector3(outerPts[j + 1].x, outerPts[j + 1].y, 0));
    }
    for (let j = 0; j < innerPts.length - 1; j++) {
      pts.push(new THREE.Vector3(innerPts[j].x, innerPts[j].y, 0));
      pts.push(new THREE.Vector3(innerPts[j + 1].x, innerPts[j + 1].y, 0));
    }
  }
  return new THREE.BufferGeometry().setFromPoints(pts);
}

function createStarGeo(points, r0, r1) {
  const pts = [];
  for (let i = 0; i < points; i++) {
    const a = (i / points) * TAU;
    const b = ((i + 1) / points) * TAU;
    pts.push(new THREE.Vector3(Math.cos(a) * r0, Math.sin(a) * r0, 0));
    pts.push(new THREE.Vector3(Math.cos(b) * r1, Math.sin(b) * r1, 0));
  }
  return new THREE.BufferGeometry().setFromPoints(pts);
}

function createSpokesGeo(count, r0, r1) {
  const pts = [];
  for (let i = 0; i < count; i++) {
    const a = (i / count) * TAU;
    pts.push(new THREE.Vector3(Math.cos(a) * r0, Math.sin(a) * r0, 0));
    pts.push(new THREE.Vector3(Math.cos(a) * r1, Math.sin(a) * r1, 0));
  }
  return new THREE.BufferGeometry().setFromPoints(pts);
}

function createGlyphBandGeo(count, radius, size) {
  const pts = [];
  for (let i = 0; i < count; i++) {
    const a = (i / count) * TAU;
    const gx = Math.cos(a) * radius;
    const gy = Math.sin(a) * radius;
    const tangent = a + Math.PI / 2;
    const ct = Math.cos(tangent);
    const st = Math.sin(tangent);
    const dx = (x, y) => gx + ct * x - st * y;
    const dy = (x, y) => gy + st * x + ct * y;
    pts.push(new THREE.Vector3(dx(-size * 0.5, -size * 0.6), dy(-size * 0.5, -size * 0.6), 0));
    pts.push(new THREE.Vector3(dx(size * 0.5, -size * 0.6), dy(size * 0.5, -size * 0.6), 0));
    pts.push(new THREE.Vector3(dx(size * 0.5, -size * 0.6), dy(size * 0.5, -size * 0.6), 0));
    pts.push(new THREE.Vector3(dx(size * 0.23, size * 0.65), dy(size * 0.23, size * 0.65), 0));
    if (i % 4 === 0) {
      pts.push(new THREE.Vector3(dx(size * 0.23, size * 0.65), dy(size * 0.23, size * 0.65), 0));
      pts.push(new THREE.Vector3(dx(-size * 0.23, size * 0.65), dy(-size * 0.23, size * 0.65), 0));
    }
    pts.push(new THREE.Vector3(dx(-size * 0.5, -size * 0.6), dy(-size * 0.5, -size * 0.6), 0));
    pts.push(new THREE.Vector3(dx(size * 0.23, size * 0.65), dy(size * 0.23, size * 0.65), 0));
    if (i % 3 === 0) {
      pts.push(new THREE.Vector3(dx(-size * 0.8, size * 1.3), dy(-size * 0.8, size * 1.3), 0));
      pts.push(new THREE.Vector3(dx(size * 0.8, size * 1.3), dy(size * 0.8, size * 1.3), 0));
    }
  }
  return new THREE.BufferGeometry().setFromPoints(pts);
}

function createSegmentedRingGeo(segments, radius, arcFractionA, arcFractionB) {
  const pts = [];
  for (let i = 0; i < segments; i++) {
    const start = (i / segments) * TAU;
    const frac = i % 3 === 0 ? arcFractionA : arcFractionB;
    const end = start + (TAU / segments) * frac;
    const steps = 8;
    for (let j = 0; j < steps; j++) {
      const a1 = start + ((end - start) * j) / steps;
      const a2 = start + ((end - start) * (j + 1)) / steps;
      pts.push(new THREE.Vector3(Math.cos(a1) * radius, Math.sin(a1) * radius, 0));
      pts.push(new THREE.Vector3(Math.cos(a2) * radius, Math.sin(a2) * radius, 0));
    }
  }
  return new THREE.BufferGeometry().setFromPoints(pts);
}

function createShardGeo(count, innerR, wingR, tipR) {
  const pts = [];
  for (let i = 0; i < count; i++) {
    const a = (i / count) * TAU;
    const c = Math.cos(a);
    const s = Math.sin(a);
    const cl = Math.cos(a - 0.03);
    const sl = Math.sin(a - 0.03);
    const cr = Math.cos(a + 0.03);
    const sr = Math.sin(a + 0.03);
    pts.push(new THREE.Vector3(c * innerR, s * innerR, 0));
    pts.push(new THREE.Vector3(cl * wingR, sl * wingR, 0));
    pts.push(new THREE.Vector3(cl * wingR, sl * wingR, 0));
    pts.push(new THREE.Vector3(c * tipR, s * tipR, 0));
    pts.push(new THREE.Vector3(c * tipR, s * tipR, 0));
    pts.push(new THREE.Vector3(cr * wingR, sr * wingR, 0));
    pts.push(new THREE.Vector3(cr * wingR, sr * wingR, 0));
    pts.push(new THREE.Vector3(c * innerR, s * innerR, 0));
  }
  return new THREE.BufferGeometry().setFromPoints(pts);
}

function createSeedOfLifeGeo(seedR, orbitR) {
  const pts = [];
  const circPts = 32;
  const addCircle = (cx, cy) => {
    for (let i = 0; i < circPts; i++) {
      const a1 = (i / circPts) * TAU;
      const a2 = ((i + 1) / circPts) * TAU;
      pts.push(new THREE.Vector3(cx + Math.cos(a1) * seedR, cy + Math.sin(a1) * seedR, 0));
      pts.push(new THREE.Vector3(cx + Math.cos(a2) * seedR, cy + Math.sin(a2) * seedR, 0));
    }
  };
  addCircle(0, 0);
  for (let i = 0; i < 6; i++) {
    const a = (i / 6) * TAU;
    addCircle(Math.cos(a) * orbitR, Math.sin(a) * orbitR);
  }
  return new THREE.BufferGeometry().setFromPoints(pts);
}

function nodesMesh(count, ringRadius, nodeRadius) {
  const geo = new THREE.CircleGeometry(nodeRadius, 8);
  const mat = new THREE.MeshBasicMaterial({
    color: 0xffc580,
    transparent: true,
    opacity: 0.4,
    blending: THREE.AdditiveBlending,
    depthWrite: false
  });
  const mesh = new THREE.InstancedMesh(geo, mat, count);
  const dummy = new THREE.Object3D();
  for (let i = 0; i < count; i++) {
    const a = (i / count) * TAU;
    dummy.position.set(Math.cos(a) * ringRadius, Math.sin(a) * ringRadius, 0);
    dummy.updateMatrix();
    mesh.setMatrixAt(i, dummy.matrix);
  }
  mesh.instanceMatrix.needsUpdate = true;
  return mesh;
}

const PARTICLE_COUNT = 400;

function createParticleSystem() {
  const positions = new Float32Array(PARTICLE_COUNT * 3);
  const velocities = new Float32Array(PARTICLE_COUNT * 3);
  const lifetimes = new Float32Array(PARTICLE_COUNT);
  const sizes = new Float32Array(PARTICLE_COUNT);

  for (let i = 0; i < PARTICLE_COUNT; i++) {
    positions[i * 3] = positions[i * 3 + 1] = positions[i * 3 + 2] = 0;
    lifetimes[i] = 0;
    sizes[i] = 0;
  }

  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geo.setAttribute("aLife", new THREE.BufferAttribute(lifetimes, 1));
  geo.setAttribute("aSize", new THREE.BufferAttribute(sizes, 1));

  const mat = new THREE.ShaderMaterial({
    uniforms: {},
    vertexShader: `
      attribute float aLife;
      attribute float aSize;
      varying float vAlpha;
      void main() {
        vAlpha = clamp(aLife, 0.0, 1.0);
        vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
        gl_PointSize = aSize * vAlpha * (300.0 / -mvPosition.z);
        gl_Position = projectionMatrix * mvPosition;
      }
    `,
    fragmentShader: `
      varying float vAlpha;
      void main() {
        float d = length(gl_PointCoord - vec2(0.5));
        if (d > 0.5) discard;
        float falloff = 1.0 - smoothstep(0.0, 0.5, d);
        gl_FragColor = vec4(1.0, 0.72, 0.35, vAlpha * falloff * 0.85);
      }
    `,
    transparent: true,
    blending: THREE.AdditiveBlending,
    depthWrite: false
  });

  const points = new THREE.Points(geo, mat);
  let nextIdx = 0;

  function emit(x, y, count, spread, speedMul = 1) {
    for (let i = 0; i < count; i++) {
      const angle = Math.random() * TAU;
      const spd = (0.5 + Math.random() * 2.5) * speedMul;
      const idx = nextIdx % PARTICLE_COUNT;
      nextIdx++;
      positions[idx * 3] = x;
      positions[idx * 3 + 1] = y;
      positions[idx * 3 + 2] = 0;
      velocities[idx * 3] = Math.cos(angle) * spd * spread;
      velocities[idx * 3 + 1] = Math.sin(angle) * spd * spread;
      velocities[idx * 3 + 2] = 0;
      lifetimes[idx] = 0.4 + Math.random() * 0.8;
      sizes[idx] = 1.5 + Math.random() * 4;
    }
  }

  function update(dt) {
    const dtScaled = dt * 60;
    for (let i = 0; i < PARTICLE_COUNT; i++) {
      if (lifetimes[i] <= 0) continue;
      positions[i * 3] += velocities[i * 3] * dtScaled;
      positions[i * 3 + 1] += velocities[i * 3 + 1] * dtScaled;
      velocities[i * 3 + 1] += 0.25 * dt;
      lifetimes[i] -= 0.016 * dtScaled;
    }
    geo.attributes.position.needsUpdate = true;
    geo.attributes.aLife.needsUpdate = true;
  }

  return { points, emit, update };
}

export function createShieldScene() {
  const scene = new THREE.Scene();
  const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0.1, 10);
  camera.position.z = 5;

  const lineMat = (color, opacity = 0.5) =>
    new THREE.LineBasicMaterial({
      color,
      transparent: true,
      opacity,
      blending: THREE.AdditiveBlending,
      depthWrite: false
    });

  const ember = 0xffa040;
  const emberHot = 0xffb860;
  const emberSoft = 0xffb860;
  const lotusBright = 0xffba60;

  const mandalaGroup = new THREE.Group();
  scene.add(mandalaGroup);

  const coreGlowTex = (() => {
    const c = document.createElement("canvas");
    c.width = c.height = 128;
    const cx = c.getContext("2d");
    const g = cx.createRadialGradient(64, 64, 0, 64, 64, 64);
    g.addColorStop(0, "rgba(255, 200, 120, 0.9)");
    g.addColorStop(0.45, "rgba(255, 160, 60, 0.35)");
    g.addColorStop(1, "rgba(255, 140, 40, 0)");
    cx.fillStyle = g;
    cx.fillRect(0, 0, 128, 128);
    const tex = new THREE.CanvasTexture(c);
    return tex;
  })();

  const auraGlowTex = (() => {
    const c = document.createElement("canvas");
    c.width = c.height = 256;
    const cx = c.getContext("2d");
    const g = cx.createRadialGradient(128, 128, 10, 128, 128, 128);
    g.addColorStop(0, "rgba(255, 180, 80, 0.35)");
    g.addColorStop(0.5, "rgba(255, 145, 30, 0.1)");
    g.addColorStop(1, "rgba(255, 145, 30, 0)");
    cx.fillStyle = g;
    cx.fillRect(0, 0, 256, 256);
    return new THREE.CanvasTexture(c);
  })();

  const auraSprite = new THREE.Sprite(
    new THREE.SpriteMaterial({
      map: auraGlowTex,
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false
    })
  );
  auraSprite.scale.set(1, 1, 1);
  mandalaGroup.add(auraSprite);

  const rings = [];
  for (let i = 0; i < 5; i++) {
    const r = 0.46 + i * 0.2;
    const geo = createCircleLine(r);
    const mat = lineMat(i === 1 || i === 3 ? emberHot : emberSoft, 0.45);
    const line = new THREE.Line(geo, mat);
    rings.push(line);
    mandalaGroup.add(line);
  }

  const petalLayers = [];
  const petalConfigs = [
    { base: 0.25, tip: 0.49, count: 12, pull: 0.68 },
    { base: 0.5, tip: 0.74, count: 18, pull: 0.73 },
    { base: 0.78, tip: 1.03, count: 24, pull: 0.8 }
  ];
  for (const cfg of petalConfigs) {
    const geo = createPetalRosetteGeo(cfg.base, cfg.tip, cfg.count, cfg.pull);
    const mat = lineMat(lotusBright, 0.38);
    const seg = new THREE.LineSegments(geo, mat);
    petalLayers.push(seg);
    mandalaGroup.add(seg);
  }

  const starConfigs = [
    { points: 6, r0: 0.44, r1: 0.9 },
    { points: 8, r0: 0.54, r1: 0.8 },
    { points: 12, r0: 0.33, r1: 0.62 }
  ];
  const starLayers = [];
  for (const cfg of starConfigs) {
    const geo = createStarGeo(cfg.points, cfg.r0, cfg.r1);
    const seg = new THREE.LineSegments(geo, lineMat(emberSoft, 0.35));
    starLayers.push(seg);
    mandalaGroup.add(seg);
  }

  const seedGeo = createSeedOfLifeGeo(0.18, 0.24);
  const seedMesh = new THREE.LineSegments(seedGeo, lineMat(emberSoft, 0.32));
  mandalaGroup.add(seedMesh);

  const spokesGeo = createSpokesGeo(24, 0.22, 0.96);
  const spokesMesh = new THREE.LineSegments(spokesGeo, lineMat(emberHot, 0.45));
  mandalaGroup.add(spokesMesh);

  const nodes1 = nodesMesh(24, 0.98, 0.016);
  mandalaGroup.add(nodes1);
  const nodes2 = nodesMesh(36, 1.2, 0.01);
  mandalaGroup.add(nodes2);

  const glyphGeo = createGlyphBandGeo(42, 1.2, 0.045);
  const glyphMesh = new THREE.LineSegments(glyphGeo, lineMat(0xffd090, 0.38));
  mandalaGroup.add(glyphMesh);

  const outerSegs = createSegmentedRingGeo(30, 1.4, 0.68, 0.48);
  const outerSegsMesh = new THREE.LineSegments(outerSegs, lineMat(emberHot, 0.42));
  mandalaGroup.add(outerSegsMesh);

  const shardGeo = createShardGeo(20, 1.34, 1.48, 1.58);
  const shardMesh = new THREE.LineSegments(shardGeo, lineMat(emberSoft, 0.3));
  mandalaGroup.add(shardMesh);

  const coreSprite = new THREE.Sprite(
    new THREE.SpriteMaterial({
      map: coreGlowTex,
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false
    })
  );
  coreSprite.scale.set(0.6, 0.6, 1);
  mandalaGroup.add(coreSprite);

  const particles = createParticleSystem();
  scene.add(particles.points);

  const arcLineMat = new THREE.LineBasicMaterial({
    color: 0xffa640,
    transparent: true,
    opacity: 0.5,
    blending: THREE.AdditiveBlending,
    depthWrite: false
  });
  const arcGeo = new THREE.BufferGeometry();
  const arcPositions = new Float32Array(12 * 3);
  arcGeo.setAttribute("position", new THREE.BufferAttribute(arcPositions, 3));
  const arcLine = new THREE.Line(arcGeo, arcLineMat);
  arcLine.visible = false;
  scene.add(arcLine);

  const shieldGroups = [mandalaGroup];
  const extraMandalas = [];

  function resize(w, h) {
    camera.left = 0;
    camera.right = w;
    camera.top = 0;
    camera.bottom = h;
    camera.updateProjectionMatrix();
  }

  function updateMandala(group, cx, cy, radius, rotation, energy, hueShift) {
    group.position.set(cx, cy, 0);

    const baseScale = radius / 100;
    group.scale.set(baseScale * 100, baseScale * 100, 1);

    const t = rotation;

    auraSprite.scale.set(
      baseScale * 100 * (1.78 + energy * 0.3) * 2,
      baseScale * 100 * (1.78 + energy * 0.3) * 2,
      1
    );
    auraSprite.material.opacity = 0.2 + energy * 0.15;

    for (let i = 0; i < rings.length; i++) {
      const dir = i % 2 === 0 ? 1 : -1;
      rings[i].rotation.z = t * dir * (0.65 + i * 0.32);
      rings[i].material.opacity = 0.35 + energy * 0.25;
    }

    const petalSpins = [0.95, -0.68, 0.35];
    for (let i = 0; i < petalLayers.length; i++) {
      petalLayers[i].rotation.z = t * petalSpins[i];
      petalLayers[i].material.opacity = 0.25 + energy * 0.2;
    }

    const starSpins = [0.78, -1.22, 1.6];
    for (let i = 0; i < starLayers.length; i++) {
      starLayers[i].rotation.z = t * starSpins[i];
    }

    seedMesh.rotation.z = t * 0.24;
    spokesMesh.rotation.z = t * 0.34;
    nodes1.rotation.z = -t * 0.74;
    nodes2.rotation.z = t * 0.9;
    glyphMesh.rotation.z = -t * 1.5;
    outerSegsMesh.rotation.z = t * 0.85;
    shardMesh.rotation.z = -t * 0.42;

    const brightness = 0.5 + energy * 0.4;
    coreSprite.material.opacity = brightness;
    coreSprite.scale.set(
      baseScale * 100 * 0.42 * 2 * (1 + energy * 0.3),
      baseScale * 100 * 0.42 * 2 * (1 + energy * 0.3),
      1
    );
  }

  function updateArc(a, b, power) {
    if (power < 0.08) {
      arcLine.visible = false;
      return;
    }
    arcLine.visible = true;
    arcLineMat.opacity = 0.3 + power * 0.4;
    const pos = arcGeo.attributes.position.array;
    const lerp = (v1, v2, t) => v1 + (v2 - v1) * t;
    const segCount = 12;
    for (let i = 0; i < segCount; i++) {
      const t = i / (segCount - 1);
      pos[i * 3] = lerp(a.x, b.x, t) + (i > 0 && i < segCount - 1 ? (Math.random() - 0.5) * (14 + power * 32) : 0);
      pos[i * 3 + 1] = lerp(a.y, b.y, t) + (i > 0 && i < segCount - 1 ? (Math.random() - 0.5) * (14 + power * 32) : 0);
      pos[i * 3 + 2] = 0;
    }
    arcGeo.attributes.position.needsUpdate = true;
  }

  function update(hands, dt) {
    for (let i = 0; i < hands.length; i++) {
      const hand = hands[i];
      if (i === 0) {
        updateMandala(
          mandalaGroup,
          hand.center.x,
          hand.center.y,
          hand.radius,
          hand.rotation,
          hand.pinchFactor,
          hand.handedness === "Left" ? 0 : 8
        );
        mandalaGroup.visible = true;

        if (Math.random() < 0.28 + hand.pinchFactor * 0.5) {
          const angle = Math.random() * TAU;
          const rr = hand.radius * (0.7 + Math.random() * 0.45);
          particles.emit(
            hand.center.x + Math.cos(angle) * rr,
            hand.center.y + Math.sin(angle) * rr,
            Math.floor(2 + hand.pinchFactor * 6),
            0.4,
            0.6 + hand.pinchFactor * 0.6
          );
        }
      }

      if (i >= 1 && i - 1 < extraMandalas.length) {
        const g = extraMandalas[i - 1];
        g.visible = true;
        updateMandala(
          g, hand.center.x, hand.center.y, hand.radius,
          hand.rotation, hand.pinchFactor, hand.handedness === "Left" ? 0 : 8
        );
      }
    }

    for (let i = hands.length; i <= extraMandalas.length; i++) {
      if (i === 0) mandalaGroup.visible = false;
      else if (extraMandalas[i - 1]) extraMandalas[i - 1].visible = false;
    }

    if (hands.length === 2) {
      const d = Math.hypot(hands[0].center.x - hands[1].center.x, hands[0].center.y - hands[1].center.y);
      const pairPower = Math.min(1, Math.max(0, (260 - d) / 220)) * ((hands[0].pinchFactor + hands[1].pinchFactor) / 2);
      updateArc(hands[0].center, hands[1].center, pairPower);
      if (d < 200 && Math.random() < 0.12 + pairPower * 0.25) {
        particles.emit(
          (hands[0].center.x + hands[1].center.x) / 2,
          (hands[0].center.y + hands[1].center.y) / 2,
          Math.floor(10 + pairPower * 40),
          1 + pairPower * 1.6,
          1 + pairPower * 1.2
        );
      }
    } else {
      arcLine.visible = false;
    }

    if (hands.length === 0) {
      mandalaGroup.visible = false;
    }

    particles.update(dt);
  }

  return { scene, camera, resize, update };
}
