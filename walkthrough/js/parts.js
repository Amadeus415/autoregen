import * as THREE from "three";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";
import { ConvexGeometry } from "three/addons/geometries/ConvexGeometry.js";

const SCALE = 0.058;

export const MATERIALS = {
  solid: () =>
    new THREE.MeshPhysicalMaterial({
      color: 0xe9e9eb,
      roughness: 0.36,
      metalness: 0.14,
      clearcoat: 0.5,
      clearcoatRoughness: 0.3,
      envMapIntensity: 1.05,
    }),
  pending: () =>
    new THREE.MeshPhysicalMaterial({
      color: 0xdcdce0,
      roughness: 0.64,
      metalness: 0.02,
      envMapIntensity: 0.55,
    }),
  ghost: () =>
    new THREE.MeshPhysicalMaterial({
      color: 0x0e7490,
      roughness: 0.18,
      metalness: 0.05,
      transparent: true,
      opacity: 0.2,
      depthWrite: false,
      side: THREE.DoubleSide,
      envMapIntensity: 0.8,
    }),
  discard: () =>
    new THREE.MeshPhysicalMaterial({
      color: 0xe5484d,
      roughness: 0.38,
      metalness: 0.08,
      transparent: true,
      opacity: 0.42,
      depthWrite: false,
      envMapIntensity: 0.7,
    }),
};

const EDGE = new THREE.LineBasicMaterial({
  color: 0x111111,
  transparent: true,
  opacity: 0.28,
});

const GHOST_EDGE = new THREE.LineBasicMaterial({
  color: 0x0e7490,
  transparent: true,
  opacity: 0.5,
});

const DISCARD_EDGE = new THREE.LineBasicMaterial({
  color: 0xe5484d,
  transparent: true,
  opacity: 0.55,
});

/** Small blends are 1–2 mm. Boost so they read at studio scale. */
function boost(v, min = 2.1, k = 2.3) {
  return Math.max(min, v * k);
}

function sit(geo) {
  geo.computeBoundingBox();
  const bb = geo.boundingBox;
  const cx = (bb.min.x + bb.max.x) / 2;
  const cz = (bb.min.z + bb.max.z) / 2;
  geo.translate(-cx, -bb.min.y, -cz);
  geo.computeVertexNormals();
  return geo;
}

function roundedRect(w, d, r) {
  const hw = w / 2;
  const hd = d / 2;
  const rr = Math.max(0.05, Math.min(r, hw - 0.05, hd - 0.05));
  const s = new THREE.Shape();
  s.moveTo(-hw + rr, -hd);
  s.lineTo(hw - rr, -hd);
  s.absarc(hw - rr, -hd + rr, rr, -Math.PI / 2, 0, false);
  s.lineTo(hw, hd - rr);
  s.absarc(hw - rr, hd - rr, rr, 0, Math.PI / 2, false);
  s.lineTo(-hw + rr, hd);
  s.absarc(-hw + rr, hd - rr, rr, Math.PI / 2, Math.PI, false);
  s.lineTo(-hw, -hd + rr);
  s.absarc(-hw + rr, -hd + rr, rr, Math.PI, Math.PI * 1.5, false);
  return s;
}

function rect(w, d) {
  const s = new THREE.Shape();
  const hw = w / 2;
  const hd = d / 2;
  s.moveTo(-hw, -hd);
  s.lineTo(hw, -hd);
  s.lineTo(hw, hd);
  s.lineTo(-hw, hd);
  s.closePath();
  return s;
}

function chamferedRect(w, d, c) {
  const hw = w / 2;
  const hd = d / 2;
  const cc = Math.max(0.04, Math.min(c, hw - 0.05, hd - 0.05));
  const s = new THREE.Shape();
  s.moveTo(-hw + cc, -hd);
  s.lineTo(hw - cc, -hd);
  s.lineTo(hw, -hd + cc);
  s.lineTo(hw, hd - cc);
  s.lineTo(hw - cc, hd);
  s.lineTo(-hw + cc, hd);
  s.lineTo(-hw, hd - cc);
  s.lineTo(-hw, -hd + cc);
  s.closePath();
  return s;
}

function addCircleHole(shape, x, y, r) {
  const hole = new THREE.Path();
  hole.absarc(x, y, Math.max(0.08, r), 0, Math.PI * 2, true);
  shape.holes.push(hole);
}

function addSlotHole(shape, x, y, length, width) {
  const hole = new THREE.Path();
  const rr = width / 2;
  const hx = Math.max(0.05, length / 2 - rr);
  hole.absarc(x - hx, y, rr, Math.PI / 2, -Math.PI / 2, true);
  hole.absarc(x + hx, y, rr, -Math.PI / 2, Math.PI / 2, true);
  shape.holes.push(hole);
}

function extrude(shape, depth, segments = 48) {
  const geo = new THREE.ExtrudeGeometry(shape, {
    depth,
    bevelEnabled: false,
    curveSegments: segments,
  });
  geo.rotateX(-Math.PI / 2);
  return sit(geo);
}

function boxGeo(w, d, h) {
  return sit(new THREE.BoxGeometry(w, h, d));
}

function cylinderGeo(r, h, seg = 64) {
  return sit(new THREE.CylinderGeometry(r, r, h, seg));
}

function tubeGeo(outerR, innerR, h) {
  const shape = new THREE.Shape();
  shape.absarc(0, 0, outerR, 0, Math.PI * 2, false);
  const hole = new THREE.Path();
  hole.absarc(0, 0, Math.max(0.08, innerR), 0, Math.PI * 2, true);
  shape.holes.push(hole);
  return extrude(shape, h, 72);
}

function plateHoles(w, d, t, holes) {
  const shape = rect(w, d);
  for (const hole of holes) addCircleHole(shape, hole.x, hole.y, hole.r);
  return extrude(shape, t, 48);
}

function plateSlot(w, d, t, sx, sy, sl, sw) {
  const shape = rect(w, d);
  addSlotHole(shape, sx, sy, sl, sw);
  return extrude(shape, t, 48);
}

function counterboreGeo(w, d, t, holeD, cboreD, cboreH, hx, hy) {
  const group = new THREE.Group();
  const rest = Math.max(0.2, t - cboreH);
  const bottom = plateHoles(w, d, rest, [{ x: hx, y: hy, r: holeD / 2 }]);
  const top = plateHoles(w, d, cboreH, [{ x: hx, y: hy, r: cboreD / 2 }]);
  const bottomMesh = new THREE.Mesh(bottom);
  const topMesh = new THREE.Mesh(top);
  topMesh.position.y = rest;
  group.add(bottomMesh, topMesh);
  return group;
}

function bossGeo(w, d, plateT, bossD, bossH, bx, by) {
  const group = new THREE.Group();
  const plate = new THREE.Mesh(boxGeo(w, d, plateT));
  const cyl = new THREE.Mesh(cylinderGeo(bossD / 2, bossH, 56));
  cyl.position.set(bx, plateT, by);
  group.add(plate, cyl);
  return group;
}

function verticalFilletGeo(w, d, h, r) {
  return extrude(roundedRect(w, d, r), h, 24);
}

function verticalChamferGeo(w, d, h, c) {
  return extrude(chamferedRect(w, d, c), h, 8);
}

function topChamferGeo(w, d, h, c) {
  const hw = w / 2;
  const hd = d / 2;
  const hh = h / 2;
  const cc = Math.max(0.05, Math.min(c, w / 2 - 0.2, d / 2 - 0.2, h - 0.2));
  const y0 = -hh;
  const y1 = hh - cc;
  const y2 = hh;
  const pts = [
    [-hw, y0, -hd],
    [hw, y0, -hd],
    [hw, y0, hd],
    [-hw, y0, hd],
    [-hw, y1, -hd],
    [hw, y1, -hd],
    [hw, y1, hd],
    [-hw, y1, hd],
    [-hw + cc, y2, -hd + cc],
    [hw - cc, y2, -hd + cc],
    [hw - cc, y2, hd - cc],
    [-hw + cc, y2, hd - cc],
  ].map(([x, y, z]) => new THREE.Vector3(x, y, z));
  return sit(new ConvexGeometry(pts));
}

function allChamferGeo(w, d, h, c) {
  const cc = Math.max(0.05, Math.min(c, w / 4, d / 4, h / 4));
  const shape = rect(w - 2 * cc, d - 2 * cc);
  const geo = new THREE.ExtrudeGeometry(shape, {
    depth: h - 2 * cc,
    bevelEnabled: true,
    bevelThickness: cc,
    bevelSize: cc,
    bevelSegments: 1,
  });
  geo.rotateX(-Math.PI / 2);
  return sit(geo);
}

function allFilletGeo(w, d, h, r) {
  const rr = Math.max(0.08, Math.min(r, w / 2 - 0.15, d / 2 - 0.15, h / 2 - 0.15));
  const geo = new RoundedBoxGeometry(w, h, d, 5, rr);
  return sit(geo);
}

function countersinkGeo(w, d, t, holeD, csinkD) {
  const group = new THREE.Group();
  const plate = new THREE.Mesh(plateHoles(w, d, t, [{ x: 0, y: 0, r: holeD / 2 }]));
  const coneH = Math.min(t * 0.55, (csinkD - holeD) / 2);
  const cone = new THREE.Mesh(sit(new THREE.CylinderGeometry(csinkD / 2, holeD / 2, coneH, 48)));
  cone.position.y = t - coneH;
  group.add(plate, cone);
  return group;
}

function blindHoleGeo(w, d, t, holeD, depth) {
  const group = new THREE.Group();
  const plate = new THREE.Mesh(boxGeo(w, d, t));
  const bore = new THREE.Mesh(cylinderGeo(holeD / 2, depth, 40));
  bore.position.y = t - depth;
  group.add(plate, bore);
  return group;
}

function truthGeo(family, params) {
  switch (family.id) {
    case "box":
      return boxGeo(params.width, params.depth, params.height);
    case "cylinder":
      return cylinderGeo(params.radius, params.height);
    case "tube":
      return tubeGeo(params.outer_r, params.inner_r, params.height);
    case "plateHole":
      return plateHoles(params.width, params.depth, params.thick, [
        { x: 0, y: 0, r: params.hole_d / 2 },
      ]);
    case "offsetHole":
      return plateHoles(params.width, params.depth, params.thick, [
        { x: params.hole_x, y: params.hole_y, r: params.hole_d / 2 },
      ]);
    case "boss":
      return bossGeo(params.width, params.depth, params.plate_t, params.boss_d, params.boss_h, 0, 0);
    case "offsetBoss":
      return bossGeo(
        params.width,
        params.depth,
        params.plate_t,
        params.boss_d,
        params.boss_h,
        params.boss_x,
        params.boss_y,
      );
    case "fillet":
      return allFilletGeo(params.width, params.depth, params.height, boost(params.fillet_r));
    case "chamfer":
      return topChamferGeo(params.width, params.depth, params.height, boost(params.chamfer));
    case "counterbore":
      return counterboreGeo(
        params.width,
        params.depth,
        params.thick,
        params.hole_d,
        params.cbore_d,
        boost(params.cbore_h, 2.4, 1.6),
        0,
        0,
      );
    case "slot":
      return plateSlot(params.width, params.depth, params.thick, 0, 0, params.slot_l, params.slot_w);
    case "holePair": {
      const half = params.pitch / 2;
      return plateHoles(params.width, params.depth, params.thick, [
        { x: -half, y: 0, r: params.hole_d / 2 },
        { x: half, y: 0, r: params.hole_d / 2 },
      ]);
    }
    default:
      return boxGeo(params.width || 20, params.depth || 20, params.height || 10);
  }
}

export function reconstruct(family, params, caps) {
  const n = new Set(family.names);
  const bb = family.observedBB;
  const bind = caps.has("bindBox");
  const x = n.has("width") && bind ? params.width : bb.x;
  const y = n.has("depth") && bind ? params.depth : bb.y;
  let z = bb.z;
  if (bind) {
    if (n.has("height")) z = params.height;
    else if (n.has("thick")) z = params.thick;
    else if (n.has("plate_t")) z = params.plate_t;
  }

  if (n.has("outer_r") && n.has("inner_r") && caps.has("tube")) {
    const h = n.has("height") ? params.height : bb.z;
    return tubeGeo(params.outer_r, params.inner_r, h);
  }
  if (n.has("radius") && caps.has("cylinder")) {
    const h = n.has("height") ? params.height : bb.z;
    return cylinderGeo(params.radius, h);
  }
  if (n.has("hole_d") && n.has("pitch") && caps.has("pitch")) {
    const half = params.pitch / 2;
    return plateHoles(x, y, z, [
      { x: -half, y: 0, r: params.hole_d / 2 },
      { x: half, y: 0, r: params.hole_d / 2 },
    ]);
  }
  if (n.has("hole_d") && caps.has("hole")) {
    const ox = n.has("hole_x") && n.has("hole_y") && caps.has("offsetHole") ? params.hole_x : 0;
    const oy = n.has("hole_x") && n.has("hole_y") && caps.has("offsetHole") ? params.hole_y : 0;
    if (n.has("cbore_d") && n.has("cbore_h") && caps.has("cbore")) {
      return counterboreGeo(
        x,
        y,
        z,
        params.hole_d,
        params.cbore_d,
        boost(params.cbore_h, 2.4, 1.6),
        ox,
        oy,
      );
    }
    return plateHoles(x, y, z, [{ x: ox, y: oy, r: params.hole_d / 2 }]);
  }
  if (n.has("boss_d") && n.has("boss_h") && caps.has("boss")) {
    const bx = n.has("boss_x") && n.has("boss_y") && caps.has("offsetBoss") ? params.boss_x : 0;
    const by = n.has("boss_x") && n.has("boss_y") && caps.has("offsetBoss") ? params.boss_y : 0;
    return bossGeo(x, y, z, params.boss_d, params.boss_h, bx, by);
  }
  if (n.has("slot_l") && n.has("slot_w") && caps.has("slot")) {
    return plateSlot(x, y, z, 0, 0, params.slot_l, params.slot_w);
  }
  if (n.has("fillet_r") && caps.has("allFillet")) {
    return allFilletGeo(x, y, z, boost(params.fillet_r));
  }
  if (n.has("fillet_r") && caps.has("vFillet")) {
    return verticalFilletGeo(x, y, z, boost(params.fillet_r));
  }
  if (n.has("chamfer") && caps.has("topChamfer")) {
    return topChamferGeo(x, y, z, boost(params.chamfer));
  }
  if (n.has("chamfer") && caps.has("vChamfer")) {
    return verticalChamferGeo(x, y, z, boost(params.chamfer));
  }
  return boxGeo(x, y, z);
}

export function attemptGeo(attempt, family, params) {
  switch (attempt) {
    case "allChamfer":
      return allChamferGeo(params.width, params.depth, params.height, boost(params.chamfer));
    case "offsetSlot":
      return plateSlot(
        params.width,
        params.depth,
        params.thick,
        10,
        -5,
        params.slot_l,
        params.slot_w,
      );
    case "aliases":
      return boxGeo(params.width, params.depth, params.height);
    case "countersink":
      return countersinkGeo(params.width, params.depth, params.thick, params.hole_d, params.hole_d * 1.9);
    case "grid": {
      const px = (params.pitch || 24) / 2;
      const py = 8;
      return plateHoles(params.width, params.depth, params.thick, [
        { x: -px, y: -py, r: params.hole_d / 2 },
        { x: px, y: -py, r: params.hole_d / 2 },
        { x: -px, y: py, r: params.hole_d / 2 },
        { x: px, y: py, r: params.hole_d / 2 },
      ]);
    }
    case "blind":
      return blindHoleGeo(params.width, params.depth, params.thick, params.hole_d, params.thick * 0.55);
    default:
      return truthGeo(family, params);
  }
}

function edgeMaterial(kind) {
  if (kind === "ghost") return GHOST_EDGE;
  if (kind === "discard") return DISCARD_EDGE;
  return EDGE;
}

function addEdges(mesh, geo, kind) {
  if (!geo || !geo.attributes?.position) return;
  const count = geo.attributes.position.count;
  if (count > 1800) return;
  const eg = new THREE.EdgesGeometry(geo, 28);
  const lines = new THREE.LineSegments(eg, edgeMaterial(kind));
  lines.position.copy(mesh.position);
  lines.rotation.copy(mesh.rotation);
  lines.scale.copy(mesh.scale);
  mesh.add(lines);
}

function decorate(root, kind, matFactory) {
  const mat = matFactory();
  root.traverse((o) => {
    if (!o.isMesh) return;
    o.material = mat;
    o.castShadow = kind !== "ghost";
    o.receiveShadow = true;
    if (kind !== "ghost") addEdges(o, o.geometry, kind);
  });
  return root;
}

function asGroup(obj) {
  if (obj.isGroup) return obj;
  const g = new THREE.Group();
  const mesh = new THREE.Mesh(obj);
  g.add(mesh);
  return g;
}

export function makePart({ family, params, caps, kind = "solid", attempt = null, scale = SCALE }) {
  let obj;
  if (kind === "ghost") obj = truthGeo(family, params);
  else if (kind === "discard" && attempt) obj = attemptGeo(attempt, family, params);
  else if (kind === "truth") obj = truthGeo(family, params);
  else obj = reconstruct(family, params, caps);

  const group = asGroup(obj);
  const factory =
    kind === "ghost"
      ? MATERIALS.ghost
      : kind === "discard"
        ? MATERIALS.discard
        : kind === "pending"
          ? MATERIALS.pending
          : MATERIALS.solid;
  decorate(group, kind === "truth" ? "solid" : kind, factory);
  group.scale.setScalar(scale);
  group.userData.familyId = family.id;
  group.userData.kind = kind;
  return group;
}

export function bboxCage(w, d, h, color = 0x161c20) {
  const geo = sit(new THREE.BoxGeometry(w, h, d));
  const edges = new THREE.EdgesGeometry(geo);
  const lines = new THREE.LineSegments(
    edges,
    new THREE.LineDashedMaterial({
      color,
      dashSize: 1.2,
      gapSize: 0.7,
      transparent: true,
      opacity: 0.55,
    }),
  );
  lines.computeLineDistances();
  geo.dispose();
  return lines;
}

/** Teaching pin. Offset is exaggerated so the centroid shift reads at studio scale. */
export function approxCentroid(family, params) {
  const z = (params.height ?? params.thick ?? params.plate_t ?? family.observedBB.z) / 2;
  let x = 0;
  let zAxis = 0;
  if (family.id === "offsetHole") {
    x = -params.hole_x * 0.45;
    zAxis = -params.hole_y * 0.45;
  } else if (family.id === "offsetBoss") {
    const plate = params.width * params.depth * params.plate_t;
    const boss = Math.PI * (params.boss_d / 2) ** 2 * params.boss_h;
    const total = plate + boss;
    x = (params.boss_x * boss) / total;
    zAxis = (params.boss_y * boss) / total;
    return { x, y: (params.plate_t * plate + (params.plate_t + params.boss_h / 2) * boss) / total, z: zAxis };
  } else if (family.id === "plateHole" || family.id === "counterbore" || family.id === "slot" || family.id === "holePair") {
    return { x: 0, y: z, z: 0 };
  }
  return { x, y: z, z: zAxis };
}

export function centroidPin(x, y, z, color = 0x0e7490) {
  const g = new THREE.Group();
  const top = y + 14;
  const stem = new THREE.Mesh(
    new THREE.CylinderGeometry(0.55, 0.55, top, 10),
    new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.9 }),
  );
  stem.position.set(x, top / 2, z);
  const ball = new THREE.Mesh(
    new THREE.SphereGeometry(4.4, 20, 16),
    new THREE.MeshPhysicalMaterial({
      color,
      emissive: color,
      emissiveIntensity: 0.55,
      roughness: 0.28,
      metalness: 0.1,
    }),
  );
  ball.position.set(x, top, z);
  g.add(stem, ball);
  g.userData.kind = "pin";
  return g;
}

export function disposeObject(obj) {
  if (!obj) return;
  obj.traverse((o) => {
    o.geometry?.dispose();
    if (o.material) {
      if (Array.isArray(o.material)) o.material.forEach((m) => m.dispose());
      else if (o.material !== EDGE && o.material !== GHOST_EDGE && o.material !== DISCARD_EDGE) {
        o.material.dispose();
      }
    }
  });
}

export { SCALE };
