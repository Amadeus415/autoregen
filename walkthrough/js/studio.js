import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { CSS2DRenderer, CSS2DObject } from "three/addons/renderers/CSS2DRenderer.js";
import { FAMILIES } from "./data.js";
import { makePart, disposeObject, SCALE, bboxCage, centroidPin, approxCentroid } from "./parts.js";

const REDUCED = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

export const CAM = {
  tight: { pos: [5.2, 4.6, 6.4], target: [0, 0.15, 0] },
  hero: { pos: [6.2, 5.2, 7.4], target: [0, 0.15, 0] },
  compare: { pos: [0.2, 6.4, 11.2], target: [0, 0.1, 0] },
  members: { pos: [0.2, 7.4, 12.2], target: [0, 0.05, 0] },
  gallery: { pos: [0, 9.2, 11.4], target: [0, 0, 0] },
  workspace: { pos: [0.2, 9.4, 10.6], target: [0, 0, 0] },
  task: { pos: [6.4, 5.6, 7.6], target: [0, 0.15, 0] },
  contract: { pos: [0.2, 7.6, 12.4], target: [0, 0.05, 0] },
  trap: { pos: [0.2, 7.6, 12.4], target: [0, 0.05, 0] },
  centroid: { pos: [0.2, 6.2, 10.6], target: [0, 0.1, 0] },
  loop: { pos: [0.2, 9.4, 10.6], target: [0, 0, 0] },
  ratchet: { pos: [0.2, 6.0, 10.2], target: [0, 0.1, 0] },
};

function easeInOut(t) {
  return t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2;
}

export class Studio {
  constructor(canvas) {
    this.canvas = canvas;
    this.clock = new THREE.Clock();
    this.camTween = null;
    this.autoRotate = false;
    this.userOrbiting = false;
    this._orbitTimeout = 0;

    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0xd4d9dd);
    this.scene.fog = new THREE.Fog(0xd4d9dd, 24, 46);

    this.camera = new THREE.PerspectiveCamera(38, 1, 0.1, 80);
    this.camera.position.set(5.1, 3.4, 6.2);

    this.renderer = new THREE.WebGLRenderer({
      canvas,
      antialias: true,
      alpha: false,
      powerPreference: "high-performance",
    });
    this.renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.08;
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;

    this.labels = new CSS2DRenderer();
    this.labels.domElement.className = "label-layer";
    canvas.parentElement.appendChild(this.labels.domElement);

    this.controls = new OrbitControls(this.camera, this.labels.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.08;
    this.controls.enablePan = false;
    this.controls.minDistance = 2.2;
    this.controls.maxDistance = 28;
    this.controls.maxPolarAngle = Math.PI * 0.48;
    this.controls.target.set(0, 0.7, 0);
    this.controls.addEventListener("start", () => {
      this.userOrbiting = true;
      this.autoRotate = false;
    });
    this.controls.addEventListener("end", () => {
      clearTimeout(this._orbitTimeout);
      this._orbitTimeout = setTimeout(() => {
        this.userOrbiting = false;
      }, 1800);
    });

    const pmrem = new THREE.PMREMGenerator(this.renderer);
    this.scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    pmrem.dispose();

    this.#lights();
    this.#ground();

    this.stage = new THREE.Group();
    this.scene.add(this.stage);
    this.hero = new THREE.Group();
    this.ghost = new THREE.Group();
    this.extras = new THREE.Group();
    this.shelf = new THREE.Group();
    this.stage.add(this.hero, this.ghost, this.extras, this.shelf);

    this.raycaster = new THREE.Raycaster();
    this.pointer = new THREE.Vector2();
    this.onPick = null;
    this.labels.domElement.addEventListener("pointerdown", (e) => this.#onPointer(e));

    this.resize();
    window.addEventListener("resize", () => this.resize());
  }

  #lights() {
    const hemi = new THREE.HemisphereLight(0xf4f6f7, 0xb7bdc2, 0.85);
    this.scene.add(hemi);

    const key = new THREE.DirectionalLight(0xffffff, 1.15);
    key.position.set(7, 12, 5);
    key.castShadow = true;
    key.shadow.mapSize.set(2048, 2048);
    key.shadow.camera.near = 1;
    key.shadow.camera.far = 36;
    key.shadow.camera.left = -14;
    key.shadow.camera.right = 14;
    key.shadow.camera.top = 14;
    key.shadow.camera.bottom = -14;
    key.shadow.radius = 3;
    key.shadow.bias = -0.00025;
    this.scene.add(key);

    const fill = new THREE.DirectionalLight(0xe8eef2, 0.36);
    fill.position.set(-8, 4, -3);
    this.scene.add(fill);

    const rim = new THREE.DirectionalLight(0xffffff, 0.38);
    rim.position.set(-1, 6, -9);
    this.scene.add(rim);
  }

  #ground() {
    const floor = new THREE.Mesh(
      new THREE.PlaneGeometry(32, 32),
      new THREE.MeshStandardMaterial({
        color: 0xc9ced3,
        roughness: 0.94,
        metalness: 0.06,
      }),
    );
    floor.rotation.x = -Math.PI / 2;
    floor.receiveShadow = true;
    this.scene.add(floor);

    const grid = new THREE.GridHelper(24, 24, 0xb0b6bb, 0xc2c7cc);
    grid.position.y = 0.01;
    grid.material.transparent = true;
    grid.material.opacity = 0.55;
    this.scene.add(grid);

    const shadow = new THREE.Mesh(
      new THREE.CircleGeometry(8.2, 64),
      new THREE.ShadowMaterial({ opacity: 0.12 }),
    );
    shadow.rotation.x = -Math.PI / 2;
    shadow.position.y = 0.012;
    shadow.receiveShadow = true;
    this.scene.add(shadow);
  }

  resize() {
    const wrap = this.canvas.parentElement;
    const w = wrap.clientWidth;
    const h = wrap.clientHeight;
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(w, h, false);
    this.labels.setSize(w, h);
  }

  frame(preset, duration = 900) {
    const cam = CAM[preset] || CAM.hero;
    this.tweenCamera(cam.pos, cam.target, REDUCED ? 0 : duration);
  }

  tweenCamera(pos, target, duration) {
    const fromP = this.camera.position.clone();
    const fromT = this.controls.target.clone();
    const toP = new THREE.Vector3(...pos);
    const toT = new THREE.Vector3(...target);
    if (duration <= 1) {
      this.camera.position.copy(toP);
      this.controls.target.copy(toT);
      this.camTween = null;
      return;
    }
    const t0 = performance.now();
    this.camTween = { fromP, fromT, toP, toT, t0, duration };
  }

  setRotate(on) {
    this.autoRotate = on && !REDUCED;
  }

  #clear(group) {
    [...group.children].forEach((ch) => {
      ch.traverse((o) => {
        if (o.isCSS2DObject && o.element) o.element.remove();
      });
      group.remove(ch);
      disposeObject(ch);
    });
  }

  clearStage() {
    this.#clear(this.hero);
    this.#clear(this.ghost);
    this.#clear(this.extras);
    this.#clear(this.shelf);
    this.hero.position.set(0, 0, 0);
    this.ghost.position.set(0, 0, 0);
    this.extras.position.set(0, 0, 0);
    this.shelf.position.set(0, 0, 0);
  }

  #label(text, position, cls = "anno") {
    const el = document.createElement("div");
    el.className = cls;
    el.textContent = text;
    const obj = new CSS2DObject(el);
    obj.position.copy(position);
    return obj;
  }

  annotate(parent, text, y = -0.28, cls = "anno") {
    parent.add(this.#label(text, new THREE.Vector3(0, y, 0), cls));
  }

  addHero(part, label, cls = "anno") {
    this.#clear(this.hero);
    this.hero.add(part);
    if (label) this.hero.add(this.#label(label, new THREE.Vector3(0, -0.28, 0), cls));
  }

  addGhost(part, label) {
    this.#clear(this.ghost);
    this.ghost.add(part);
    if (label) this.ghost.add(this.#label(label, new THREE.Vector3(0, -0.28, 0), "anno anno-truth"));
  }

  setExtras(parts) {
    this.#clear(this.extras);
    for (const p of parts) this.extras.add(p);
  }

  addCage(family, params, scale = SCALE * 1.14) {
    const cage = bboxCage(params.width ?? family.observedBB.x, params.depth ?? family.observedBB.y, params.height ?? params.thick ?? params.plate_t ?? family.observedBB.z);
    cage.scale.setScalar(scale);
    this.hero.add(cage);
  }

  addCentroid(family, params, scale = SCALE, color = 0x0e7490) {
    const c = approxCentroid(family, params);
    const pin = centroidPin(c.x * scale, c.y * scale, c.z * scale, color);
    this.extras.add(pin);
    return pin;
  }

  setShelf(caps, highlightId, gen, { focus = false } = {}) {
    this.#clear(this.shelf);
    const n = FAMILIES.length;
    const span = focus ? 13.8 : 13.6;
    const z = focus ? 0 : -6.2;
    const scale = SCALE * (focus ? 0.56 : 0.38);
    FAMILIES.forEach((family, i) => {
      const x = -span / 2 + (i + 0.5) * (span / n);
      const recovered = family.recover.at <= gen;
      const part = makePart({
        family,
        params: family.observed,
        caps,
        kind: recovered ? "solid" : "pending",
        scale,
      });
      part.position.set(x + (focus ? 0.45 : 0), 0, z);
      part.userData.pickable = true;
      part.userData.familyId = family.id;
      if (focus) {
        const cls = ["anno", "anno-shelf", family.id === highlightId ? "is-on" : ""]
          .filter(Boolean)
          .join(" ");
        part.add(this.#label(family.name, new THREE.Vector3(0, -0.22, 0), cls));
      }
      this.shelf.add(part);
    });
  }

  setGrid(caps, gen, { labels = "name", locked = false, highlightId = null, scale = SCALE * 0.5, truth = false } = {}) {
    this.#clear(this.shelf);
    const cols = 6;
    const gapX = 2.28;
    const gapZ = 3.2;
    FAMILIES.forEach((family, i) => {
      const col = i % cols;
      const row = Math.floor(i / cols);
      const x = (col - 2.5) * gapX;
      const z = (row - 0.45) * gapZ;
      const recovered = gen == null ? true : family.recover.at <= gen;
      const part = makePart({
        family,
        params: family.observed,
        caps: caps || new Set(),
        kind: truth ? "truth" : recovered ? "solid" : "pending",
        scale,
      });
      part.position.set(x, 0, z);
      part.userData.pickable = true;
      part.userData.familyId = family.id;
      const title = labels === "task" ? family.taskId : family.name;
      const cls = ["anno", "anno-shelf", family.id === highlightId ? "is-on" : ""].filter(Boolean).join(" ");
      part.add(this.#label(title, new THREE.Vector3(0, -0.2, 0), cls));
      if (labels === "task") {
        part.add(this.#label("target.step", new THREE.Vector3(0, -0.42, 0), "anno anno-faint"));
      }
      this.shelf.add(part);
    });
    this.shelf.visible = true;
  }

  showShelf(on) {
    this.shelf.visible = on;
  }

  #onPointer(e) {
    if (!this.onPick) return;
    const rect = this.renderer.domElement.getBoundingClientRect();
    this.pointer.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    this.pointer.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
    this.raycaster.setFromCamera(this.pointer, this.camera);
    const pool = [...this.shelf.children, ...this.extras.children, ...this.hero.children];
    const hits = this.raycaster.intersectObjects(pool, true);
    for (const hit of hits) {
      let o = hit.object;
      while (o && !o.userData.familyId) o = o.parent;
      if (o?.userData.familyId) {
        this.onPick(o.userData.familyId);
        return;
      }
    }
  }

  tick() {
    const dt = this.clock.getDelta();
    if (this.camTween) {
      const { fromP, fromT, toP, toT, t0, duration } = this.camTween;
      const u = Math.min(1, (performance.now() - t0) / duration);
      const k = easeInOut(u);
      this.camera.position.lerpVectors(fromP, toP, k);
      this.controls.target.lerpVectors(fromT, toT, k);
      if (u >= 1) this.camTween = null;
    } else if (this.autoRotate && !REDUCED && !this.userOrbiting) {
      this.stage.rotation.y += dt * 0.07;
    }
    this.controls.update();
    this.renderer.render(this.scene, this.camera);
    this.labels.render(this.scene, this.camera);
  }
}

export function placeSideBySide(left, right, gap = 2.6) {
  left.position.set(-gap / 2, 0, 0);
  right.position.set(gap / 2, 0, 0);
}

export function placeRow(items, gap = 2.3) {
  const n = items.length;
  const width = (n - 1) * gap;
  items.forEach((item, i) => {
    item.position.set(-width / 2 + i * gap, 0, 0);
  });
}
