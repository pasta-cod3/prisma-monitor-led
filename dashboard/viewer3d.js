import * as THREE from "three";
import { OrbitControls } from "three/OrbitControls";
import { RoomEnvironment } from "three/RoomEnvironment";

const W = 10, H = 5.6, CURVE_R = 34;

async function loadExtras() {
  try {
    const [{ EffectComposer }, { RenderPass }, { UnrealBloomPass }, { OutputPass }, { Reflector }] = await Promise.all([
      import("three/EffectComposer"), import("three/RenderPass"), import("three/UnrealBloomPass"),
      import("three/OutputPass"), import("three/Reflector"),
    ]);
    return { EffectComposer, RenderPass, UnrealBloomPass, OutputPass, Reflector };
  } catch {
    return null;
  }
}

function bend(geom, radius) {
  const p = geom.attributes.position;
  for (let i = 0; i < p.count; i++) {
    const x = p.getX(i);
    p.setZ(i, p.getZ(i) + (x * x) / (2 * radius));
  }
  p.needsUpdate = true;
  geom.computeVertexNormals();
}

function pillowFall(x, y, w, h) {
  const nx = x / (w / 2), ny = (y / (h / 2)) + 0.32;
  const d2 = nx * nx * 2.6 + ny * ny * 2.6;
  return Math.max(0, 1 - d2);
}

function pillowBackZ(x, y, w, h, baseDepth, bulge) {
  return -baseDepth / 2 - bulge * Math.pow(pillowFall(x, y, w, h), 1.4);
}

function pillowShell(w, h, baseDepth, bulge, segX, segY, curveR) {
  const geo = new THREE.BoxGeometry(w, h, baseDepth, segX, segY, 1);
  const p = geo.attributes.position;
  for (let i = 0; i < p.count; i++) {
    const x = p.getX(i), y = p.getY(i), z = p.getZ(i);
    let nz = z < 0 ? pillowBackZ(x, y, w, h, baseDepth, bulge) : z;
    if (curveR) nz += (x * x) / (2 * curveR);
    p.setZ(i, nz);
  }
  p.needsUpdate = true;
  geo.computeVertexNormals();
  return geo;
}

function tripodFoot(material) {
  const group = new THREE.Group();
  const hub = new THREE.Mesh(new THREE.CylinderGeometry(0.85, 0.95, 0.42, 40), material);
  hub.position.y = 0.21;
  group.add(hub);
  const legAngles = [180, 55, -55];
  for (const deg of legAngles) {
    const leg = new THREE.Mesh(new THREE.CapsuleGeometry(0.46, 2.1, 10, 20), material);
    leg.scale.x = 0.55;
    leg.scale.z = 0.88;
    leg.rotation.z = Math.PI / 2;
    const rad = (deg * Math.PI) / 180;
    leg.position.set(Math.cos(rad) * 1.55, 0.17, Math.sin(rad) * 1.55);
    leg.rotation.y = -rad;
    group.add(leg);
  }
  group.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
  return group;
}

function shadowTexture() {
  const c = document.createElement("canvas");
  c.width = c.height = 256;
  const g = c.getContext("2d").createRadialGradient(128, 128, 10, 128, 128, 128);
  g.addColorStop(0, "rgba(0,0,0,0.55)");
  g.addColorStop(1, "rgba(0,0,0,0)");
  const ctx = c.getContext("2d");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 256, 256);
  return new THREE.CanvasTexture(c);
}

export class Monitor3D {
  constructor(canvas) {
    this.canvas = canvas;
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: "high-performance" });
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.0;
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;

    this.scene = new THREE.Scene();
    this.scene.fog = new THREE.Fog(0x0b0c10, 28, 64);
    const pmrem = new THREE.PMREMGenerator(this.renderer);
    this.scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.045).texture;

    this.camera = new THREE.PerspectiveCamera(30, 1, 0.1, 200);
    this.camera.position.set(0, 0.6, 27);

    this.controls = new OrbitControls(this.camera, canvas);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.08;
    this.controls.enablePan = false;
    this.controls.minDistance = 15;
    this.controls.maxDistance = 46;
    this.controls.minPolarAngle = Math.PI * 0.2;
    this.controls.maxPolarAngle = Math.PI * 0.64;
    this.controls.target.set(0, -0.4, 0);

    this.monitor = new THREE.Group();
    this.scene.add(this.monitor);

    this.lights = {
      front: new THREE.PointLight(0xffffff, 0, 42, 2),
      left: new THREE.PointLight(0xffffff, 0, 42, 2),
      right: new THREE.PointLight(0xffffff, 0, 42, 2),
    };
    this.lights.front.position.set(0, -H / 2 - 1, 5);
    this.lights.left.position.set(-W / 2, 0, -3);
    this.lights.right.position.set(W / 2, 0, -3);
    Object.values(this.lights).forEach((l) => this.scene.add(l));

    const key = new THREE.DirectionalLight(0xfff4e8, 1.35);
    key.position.set(9, 13, 11);
    key.castShadow = true;
    key.shadow.mapSize.set(1536, 1536);
    key.shadow.camera.near = 4;
    key.shadow.camera.far = 40;
    key.shadow.camera.left = -9;
    key.shadow.camera.right = 9;
    key.shadow.camera.top = 9;
    key.shadow.camera.bottom = -7;
    key.shadow.bias = -0.0015;
    key.shadow.radius = 3;
    this.scene.add(key);
    const fill = new THREE.DirectionalLight(0xbcd4ff, 0.3);
    fill.position.set(-10, 4, 6);
    this.scene.add(fill);
    const rim = new THREE.DirectionalLight(0xffffff, 0.55);
    rim.position.set(-2, 6, -12);
    this.scene.add(rim);

    const floorGeo = new THREE.PlaneGeometry(80, 80);
    const floorFallback = new THREE.Mesh(floorGeo, new THREE.MeshStandardMaterial({
      color: 0x050608, roughness: 0.3, metalness: 0.4, envMapIntensity: 0.14,
    }));
    floorFallback.rotation.x = -Math.PI / 2;
    floorFallback.position.y = -H / 2 - 3.12;
    floorFallback.receiveShadow = true;
    this.scene.add(floorFallback);
    this.floor = floorFallback;

    const shadow = new THREE.Mesh(
      new THREE.PlaneGeometry(22, 16),
      new THREE.MeshBasicMaterial({ map: shadowTexture(), transparent: true, opacity: 0.7, depthWrite: false }),
    );
    shadow.rotation.x = -Math.PI / 2;
    shadow.position.y = this.floor.position.y + 0.02;
    shadow.position.z = -0.5;
    this.scene.add(shadow);

    this.zoneMeshes = {};
    this.raycaster = new THREE.Raycaster();
    this.pickCb = null;
    this._bindPick();
    this.ready = this._initExtras();
  }

  async _initExtras() {
    const extras = await loadExtras();
    if (!extras) return;
    const { EffectComposer, RenderPass, UnrealBloomPass, OutputPass, Reflector } = extras;

    const reflector = new Reflector(this.floor.geometry.clone(), {
      textureWidth: 1024, textureHeight: 1024, color: 0x18191d, clipBias: 0.003,
    });
    reflector.rotation.copy(this.floor.rotation);
    reflector.position.copy(this.floor.position);
    reflector.material.transparent = true;
    reflector.material.opacity = 0.32;
    this.scene.remove(this.floor);
    this.scene.add(reflector);
    this.floor = reflector;

    this.composer = new EffectComposer(this.renderer);
    this.composer.addPass(new RenderPass(this.scene, this.camera));
    this.bloom = new UnrealBloomPass(new THREE.Vector2(1, 1), 0.55, 0.4, 0.68);
    this.composer.addPass(this.bloom);
    this.composer.addPass(new OutputPass());
    this.resize();
  }


  build(model) {
    this.monitor.rotation.y = 0;
    this.tween = null;
    this.monitor.clear();
    this.zoneMeshes = {};
    const curved = model.id === "MPG27CQ" || /curv|cq/i.test(model.id);
    const R = curved ? CURVE_R : 1e6;
    const curveZ = (x) => (x * x) / (2 * R);
    const SEG = 96;

    const topM = 0.16, sideM = 0.16, chinM = 0.6;
    const scrW = W - sideM * 2, scrH = H - topM - chinM;
    const scrCY = -(chinM - topM) / 2;

    const panelMat = new THREE.MeshPhysicalMaterial({
      color: 0x24272e, metalness: 0.9, roughness: 0.33, envMapIntensity: 1.4, clearcoat: 0.55, clearcoatRoughness: 0.28,
    });
    const panelGeo = new THREE.BoxGeometry(W, H, 0.32, SEG, 24, 1);
    bend(panelGeo, R);
    const bezel = new THREE.Mesh(panelGeo, panelMat);
    bezel.castShadow = true;
    bezel.receiveShadow = true;
    this.monitor.add(bezel);

    const rimGeo = new THREE.BoxGeometry(scrW + 0.22, scrH + 0.22, 0.38, SEG, 20, 1);
    bend(rimGeo, R);
    const rim = new THREE.Mesh(rimGeo, new THREE.MeshStandardMaterial({ color: 0x08090c, metalness: 0.5, roughness: 0.65 }));
    rim.position.set(0, scrCY, 0.03);
    this.monitor.add(rim);

    const screenGeo = new THREE.BoxGeometry(scrW, scrH, 0.14, SEG, 24, 1);
    bend(screenGeo, R);
    const screen = new THREE.Mesh(screenGeo, new THREE.MeshPhysicalMaterial({
      color: 0x050506, metalness: 0.0, roughness: 0.05, clearcoat: 1, clearcoatRoughness: 0.04, envMapIntensity: 1.7,
    }));
    screen.position.set(0, scrCY, 0.18);
    this.monitor.add(screen);

    const logo = new THREE.Mesh(new THREE.CylinderGeometry(0.17, 0.17, 0.05, 28),
      new THREE.MeshStandardMaterial({ color: 0xb5121b, metalness: 0.4, roughness: 0.4, emissive: 0x4a0609, emissiveIntensity: 0.3 }));
    logo.rotation.x = Math.PI / 2;
    logo.position.set(0, -H / 2 + 0.26, 0.22 + curveZ(0));
    this.monitor.add(logo);

    const shellDepth = 0.34, shellGap = 0.01, shellBulge = 0.42;
    const shellW = W * 0.97, shellH = H * 0.95;
    const shellZ = -0.16 - shellDepth / 2 - shellGap;
    const shellGeo = pillowShell(shellW, shellH, shellDepth, shellBulge, 72, 40, R);
    const shell = new THREE.Mesh(shellGeo, new THREE.MeshPhysicalMaterial({
      color: 0x1b1d23, metalness: 0.55, roughness: 0.46, envMapIntensity: 1, clearcoat: 0.2, clearcoatRoughness: 0.5,
    }));
    shell.position.z = shellZ;
    shell.castShadow = true;
    shell.receiveShadow = true;
    this.monitor.add(shell);

    const standZ = shellZ - 0.46;
    const hinge = new THREE.Mesh(new THREE.BoxGeometry(1.3, 1.0, 0.38, 6, 6, 4),
      new THREE.MeshStandardMaterial({ color: 0x15171c, metalness: 0.8, roughness: 0.4, envMapIntensity: 1 }));
    hinge.position.set(0, -H * 0.2, standZ - 0.1);
    hinge.castShadow = true;
    this.monitor.add(hinge);

    const standMat = new THREE.MeshStandardMaterial({ color: 0x111319, metalness: 0.82, roughness: 0.38, envMapIntensity: 1.1 });
    const neckTopY = -H / 2 - 0.3, neckBotY = -H / 2 - 2.5;
    const neck = new THREE.Mesh(new THREE.CylinderGeometry(0.42, 0.5, neckTopY - neckBotY, 32, 6), standMat);
    neck.position.set(0, (neckTopY + neckBotY) / 2, standZ);
    neck.castShadow = true;
    this.monitor.add(neck);

    const ring = new THREE.Mesh(new THREE.TorusGeometry(0.46, 0.05, 16, 40),
      new THREE.MeshStandardMaterial({ color: 0xcf2130, metalness: 0.5, roughness: 0.35, emissive: 0x4a0609, emissiveIntensity: 0.25 }));
    ring.rotation.x = Math.PI / 2;
    ring.position.set(0, neckTopY - 0.55, standZ);
    this.monitor.add(ring);

    const foot = tripodFoot(standMat);
    foot.position.set(0, neckBotY, standZ + 0.3);
    foot.scale.setScalar(1.35);
    this.monitor.add(foot);

    const front = model.zones.filter((z) => z.view === "front");
    const back = model.zones.filter((z) => z.view === "back");

    const span = (W - 1.4) / Math.max(front.length, 1);
    front.forEach((z, i) => {
      const cx = -W / 2 + 0.7 + span * (i + 0.5);
      this._addZone(z, cx, -H / 2 - 0.08, 0.2 + curveZ(cx), span - 0.25, 0.22, 0.9, Math.min(z.leds, 8), false);
    });
    back.forEach((z, i) => {
      const n = back.length;
      const cx = n === 1 ? 0 : (-W / 2 + 1.6 + (i / (n - 1)) * (W - 3.2));
      const proud = 0.1;
      const ledZ = shellZ + pillowBackZ(cx, 0, shellW, shellH, shellDepth, shellBulge) + proud;
      this._addZone(z, cx, 0, ledZ, 0.5, H - 2.4, 0.55, 1, true);
    });
  }

  _addZone(z, x, y, zPos, w, h, intensity, segCount, back) {
    const segs = [];
    const sw = w / segCount;
    for (let k = 0; k < segCount; k++) {
      const led = new THREE.Mesh(
        new THREE.BoxGeometry(sw * 0.86, h, 0.18),
        new THREE.MeshStandardMaterial({ color: 0x000000, emissive: 0x000000, emissiveIntensity: intensity, roughness: 0.5, toneMapped: false }),
      );
      led.position.set(x - w / 2 + sw * (k + 0.5), y, zPos);
      led.userData.zone = z.id;
      led.userData.base = intensity;
      this.monitor.add(led);
      segs.push(led);
    }
    const glow = new THREE.Mesh(
      new THREE.PlaneGeometry(w * 1.5, h * (back ? 1.6 : 2.6)),
      new THREE.MeshBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.25, blending: THREE.AdditiveBlending, depthWrite: false, toneMapped: false }),
    );
    glow.position.set(x, y, zPos + (back ? -0.25 : 0.3));
    if (back) glow.rotation.y = Math.PI;
    this.monitor.add(glow);
    this.zoneMeshes[z.id] = { segs, glow, back };
  }


  setLeds(id, colors) {
    const m = this.zoneMeshes[id];
    if (!m) return;
    const n = colors.length;
    m.cols = m.segs.map((_, k) => colors[Math.min(Math.floor((k * n) / m.segs.length), n - 1)].map((v) => v / 255));
  }

  setBrightness(k) { this._bright = k; }

  spin() {
    const from = this.monitor.rotation.y;
    this.tween = { from, to: from + Math.PI * 2, start: performance.now(), dur: 2600 };
  }

  snapTo(view) {
    const from = this.monitor.rotation.y;
    const base = view === "back" ? Math.PI : 0;
    const to = base + Math.round((from - base) / (Math.PI * 2)) * Math.PI * 2;
    this.tween = { from, to, start: performance.now(), dur: 700 };
  }

  update(now) {
    const zoneAvg = {};
    for (const [id, m] of Object.entries(this.zoneMeshes)) {
      const cols = m.cols || m.segs.map(() => [0, 0, 0]);
      m.segs.forEach((led, k) => led.material.emissive.setRGB(...cols[k]));
      const a = [0, 1, 2].map((j) => cols.reduce((s, c) => s + c[j], 0) / cols.length);
      zoneAvg[id] = a;
      m.glow.material.color.setRGB(...a);
      m.glow.material.opacity = 0.06 + 0.3 * Math.max(...a);
    }
    const ids = Object.keys(this.zoneMeshes);
    const fronts = ids.filter((i) => !this.zoneMeshes[i].back);
    const backs = ids.filter((i) => this.zoneMeshes[i].back);
    const avg = (list) => {
      if (!list.length) return [0, 0, 0];
      return [0, 1, 2].map((k) => list.reduce((s, i) => s + zoneAvg[i][k], 0) / list.length);
    };
    const bk = (this._bright != null ? this._bright : 1);
    const setL = (light, col) => { light.color.setRGB(...col); light.intensity = 3.2 * bk * Math.max(...col, 0.0001); };
    setL(this.lights.front, avg(fronts.length ? fronts : ids));
    setL(this.lights.left, avg(backs.length ? [backs[0]] : ids));
    setL(this.lights.right, avg(backs.length ? [backs[backs.length - 1]] : ids));

    if (this.tween) {
      const p = Math.min(1, (now - this.tween.start) / this.tween.dur);
      this.monitor.rotation.y = this.tween.from + (this.tween.to - this.tween.from) * easeTurn(p);
      if (p >= 1) { this.monitor.rotation.y %= Math.PI * 2; this.tween = null; }
    }
    this.controls.update();
    if (this.composer) this.composer.render();
    else this.renderer.render(this.scene, this.camera);
  }

  resize() {
    const r = this.canvas.getBoundingClientRect();
    const w = Math.max(1, r.width), h = Math.max(1, r.height);
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    if (this.composer) this.composer.setSize(w, h);
  }

  _bindPick() {
    this.canvas.addEventListener("click", (e) => {
      if (!this.pickCb) return;
      const r = this.canvas.getBoundingClientRect();
      const pt = new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
      this.raycaster.setFromCamera(pt, this.camera);
      const meshes = Object.values(this.zoneMeshes).flatMap((m) => m.segs);
      const hit = this.raycaster.intersectObjects(meshes, false)[0];
      if (hit) this.pickCb(hit.object.userData.zone, e);
    });
  }

  onPick(cb) { this.pickCb = cb; }

  highlight(ids) {
    for (const [id, m] of Object.entries(this.zoneMeshes)) {
      const k = ids.has(id) ? 1.35 : 1;
      m.segs.forEach((led) => { led.material.emissiveIntensity = led.userData.base * k; });
    }
  }
}

function easeTurn(p) {
  return p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2;
}

export function webglAvailable() {
  try {
    const c = document.createElement("canvas");
    return !!(c.getContext("webgl2") || c.getContext("webgl"));
  } catch {
    return false;
  }
}
