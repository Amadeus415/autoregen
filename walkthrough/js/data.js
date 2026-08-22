/** Teaching data for the walkthrough. Numbers from runs/grok-4.5/results.tsv. */

export const RUN = {
  researcher: "Grok 4.5",
  effort: "high",
  harness: "grok CLI",
  gens: 20,
  keeps: 14,
  discards: 6,
  start: 0.25771421,
  final: 0,
  solvedAt: 15,
};

export const FAMILIES = [
  {
    id: "box",
    key: "A",
    taskId: "t_1c598275",
    name: "Box",
    hint: "width · depth · height",
    names: ["width", "depth", "height"],
    step: "A 40×20×10 rectangular solid. Six planar faces. No holes, no blends. That is the whole file.",
    observedBB: { x: 40, y: 20, z: 10 },
    observed: { width: 40, depth: 20, height: 10 },
    heldout: [
      { width: 70, depth: 25, height: 12 },
      { width: 35, depth: 35, height: 20 },
      { width: 22, depth: 55, height: 14 },
    ],
    recover: { partial: null, at: 1 },
  },
  {
    id: "plateHole",
    key: "B",
    taskId: "t_22a5cbf9",
    name: "Plate + hole",
    hint: "thick · hole_d",
    names: ["width", "depth", "thick", "hole_d"],
    step: "A 50×30×6 plate with one centered through-hole, diameter 8. Faces and a cylindrical bore. No recipe.",
    observedBB: { x: 50, y: 30, z: 6 },
    observed: { width: 50, depth: 30, thick: 6, hole_d: 8 },
    heldout: [
      { width: 80, depth: 40, thick: 8, hole_d: 12 },
      { width: 40, depth: 40, thick: 5, hole_d: 6 },
      { width: 60, depth: 25, thick: 10, hole_d: 10 },
    ],
    recover: { partial: null, at: 2 },
  },
  {
    id: "cylinder",
    key: "C",
    taskId: "t_9e830a67",
    name: "Cylinder",
    hint: "radius · height",
    names: ["radius", "height"],
    step: "A solid cylinder, radius 10, height 30. One lateral face, two planar ends. The file does not say “circle then extrude.”",
    observedBB: { x: 20, y: 20, z: 30 },
    observed: { radius: 10, height: 30 },
    heldout: [
      { radius: 16, height: 20 },
      { radius: 8, height: 40 },
      { radius: 12, height: 12 },
    ],
    recover: { partial: null, at: 4 },
  },
  {
    id: "tube",
    key: "D",
    taskId: "t_4485028d",
    name: "Tube",
    hint: "outer_r · inner_r",
    names: ["outer_r", "inner_r", "height"],
    step: "An annular solid: outer radius 12, inner radius 6, height 25. Two cylinders and two washers. No inner/outer names inside the file.",
    observedBB: { x: 24, y: 24, z: 25 },
    observed: { outer_r: 12, inner_r: 6, height: 25 },
    heldout: [
      { outer_r: 18, inner_r: 8, height: 20 },
      { outer_r: 10, inner_r: 5, height: 30 },
      { outer_r: 15, inner_r: 4, height: 15 },
    ],
    recover: { partial: null, at: 5 },
  },
  {
    id: "boss",
    key: "E",
    taskId: "t_8357ae7f",
    name: "Boss",
    hint: "boss_d · boss_h",
    names: ["width", "depth", "plate_t", "boss_d", "boss_h"],
    step: "A 40×30×5 plate with a centered cylindrical boss, diameter 12, height 8. The STEP is the fused solid, not “plate then extrude.”",
    observedBB: { x: 40, y: 30, z: 13 },
    observed: { width: 40, depth: 30, plate_t: 5, boss_d: 12, boss_h: 8 },
    heldout: [
      { width: 60, depth: 40, plate_t: 6, boss_d: 16, boss_h: 12 },
      { width: 35, depth: 35, plate_t: 4, boss_d: 10, boss_h: 6 },
      { width: 50, depth: 20, plate_t: 8, boss_d: 8, boss_h: 10 },
    ],
    recover: { partial: null, at: 7 },
  },
  {
    id: "offsetHole",
    key: "F",
    taskId: "t_ae3e162d",
    name: "Offset hole",
    hint: "hole_x · hole_y",
    names: ["width", "depth", "thick", "hole_d", "hole_x", "hole_y"],
    step: "A 56×34×6 plate. Through-hole diameter 8, center at (12, 6) from the plate origin — not in the middle. Volume and bounding box look like a centered hole. The centroid does not.",
    observedBB: { x: 56, y: 34, z: 6 },
    observed: { width: 56, depth: 34, thick: 6, hole_d: 8, hole_x: 12, hole_y: 6 },
    heldout: [
      { width: 80, depth: 44, thick: 8, hole_d: 10, hole_x: 18, hole_y: -8 },
      { width: 48, depth: 36, thick: 5, hole_d: 6, hole_x: -14, hole_y: 9 },
      { width: 64, depth: 28, thick: 7, hole_d: 9, hole_x: 8, hole_y: -5 },
    ],
    recover: { partial: 2, at: 3 },
  },
  {
    id: "offsetBoss",
    key: "G",
    taskId: "t_b0ed1c5f",
    name: "Offset boss",
    hint: "boss_x · boss_y",
    names: ["width", "depth", "plate_t", "boss_d", "boss_h", "boss_x", "boss_y"],
    step: "A 52×36×5 plate with a boss at (10, −6), not centered. Same lesson as the offset hole: placement lives in the centroid.",
    observedBB: { x: 52, y: 36, z: 13 },
    observed: {
      width: 52,
      depth: 36,
      plate_t: 5,
      boss_d: 12,
      boss_h: 8,
      boss_x: 10,
      boss_y: -6,
    },
    heldout: [
      { width: 70, depth: 42, plate_t: 6, boss_d: 14, boss_h: 10, boss_x: 16, boss_y: 8 },
      { width: 46, depth: 32, plate_t: 4, boss_d: 10, boss_h: 6, boss_x: -12, boss_y: 7 },
      { width: 58, depth: 30, plate_t: 7, boss_d: 11, boss_h: 9, boss_x: 8, boss_y: -8 },
    ],
    recover: { partial: 7, at: 8 },
  },
  {
    id: "fillet",
    key: "H",
    taskId: "t_5a31d16a",
    name: "Fillet",
    hint: "fillet_r",
    names: ["width", "depth", "height", "fillet_r"],
    step: "A 32×20×12 box with every edge filleted at 1.5. The spherical corners are in the B-rep. The file does not say “fillet all edges.”",
    observedBB: { x: 32, y: 20, z: 12 },
    observed: { width: 32, depth: 20, height: 12, fillet_r: 1.5 },
    heldout: [
      { width: 48, depth: 28, height: 16, fillet_r: 2.0 },
      { width: 24, depth: 18, height: 14, fillet_r: 1.2 },
      { width: 40, depth: 22, height: 18, fillet_r: 2.4 },
    ],
    recover: { partial: 9, at: 13 },
  },
  {
    id: "chamfer",
    key: "I",
    taskId: "t_aef89436",
    name: "Chamfer",
    hint: "chamfer",
    names: ["width", "depth", "height", "chamfer"],
    step: "A 30×22×14 box with only the top-face edges chamfered at 1.2. Not every edge. That distinction is visible in the solid and hidden from the names.",
    observedBB: { x: 30, y: 22, z: 14 },
    observed: { width: 30, depth: 22, height: 14, chamfer: 1.2 },
    heldout: [
      { width: 46, depth: 26, height: 16, chamfer: 1.8 },
      { width: 24, depth: 18, height: 12, chamfer: 0.8 },
      { width: 38, depth: 20, height: 18, chamfer: 1.5 },
    ],
    recover: { partial: 10, at: 15 },
  },
  {
    id: "counterbore",
    key: "J",
    taskId: "t_52cd28e5",
    name: "Counterbore",
    hint: "cbore_d · cbore_h",
    names: ["width", "depth", "thick", "hole_d", "cbore_d", "cbore_h"],
    step: "A 48×32×8 plate. Through-hole 6, plus a shallow 12-diameter counterbore 2.5 deep. Two coaxial cylinders, not one.",
    observedBB: { x: 48, y: 32, z: 8 },
    observed: { width: 48, depth: 32, thick: 8, hole_d: 6, cbore_d: 12, cbore_h: 2.5 },
    heldout: [
      { width: 70, depth: 40, thick: 10, hole_d: 8, cbore_d: 16, cbore_h: 3.0 },
      { width: 40, depth: 28, thick: 7, hole_d: 5, cbore_d: 10, cbore_h: 2.0 },
      { width: 56, depth: 36, thick: 12, hole_d: 7, cbore_d: 14, cbore_h: 3.5 },
    ],
    recover: { partial: 2, at: 6 },
  },
  {
    id: "slot",
    key: "K",
    taskId: "t_ff5c1459",
    name: "Slot",
    hint: "slot_l · slot_w",
    names: ["width", "depth", "thick", "slot_l", "slot_w"],
    step: "A 60×32×6 plate with a centered stadium slot, 24 long and 6 wide, cut all the way through. No slot_x / slot_y in the names.",
    observedBB: { x: 60, y: 32, z: 6 },
    observed: { width: 60, depth: 32, thick: 6, slot_l: 24, slot_w: 6 },
    heldout: [
      { width: 80, depth: 40, thick: 8, slot_l: 32, slot_w: 8 },
      { width: 50, depth: 28, thick: 5, slot_l: 20, slot_w: 5 },
      { width: 70, depth: 36, thick: 7, slot_l: 28, slot_w: 7 },
    ],
    recover: { partial: null, at: 11 },
  },
  {
    id: "holePair",
    key: "L",
    taskId: "t_c82e39ac",
    name: "Hole pair",
    hint: "pitch · hole_d",
    names: ["width", "depth", "thick", "hole_d", "pitch"],
    step: "A 64×30×6 plate with two through-holes, diameter 6, centers 24 apart on the X axis. A pair, not a grid.",
    observedBB: { x: 64, y: 30, z: 6 },
    observed: { width: 64, depth: 30, thick: 6, hole_d: 6, pitch: 24 },
    heldout: [
      { width: 88, depth: 40, thick: 8, hole_d: 8, pitch: 32 },
      { width: 56, depth: 28, thick: 5, hole_d: 5, pitch: 20 },
      { width: 76, depth: 34, thick: 7, hole_d: 7, pitch: 28 },
    ],
    recover: { partial: 2, at: 12 },
  },
];

export const FAMILY_BY_ID = Object.fromEntries(FAMILIES.map((f) => [f.id, f]));

export const GENS = [
  {
    gen: 0,
    status: "keep",
    err: 0.25771421,
    unlock: null,
    family: "box",
    names: [],
    title: "Baseline: measure the STEP, ignore the names",
    why: "Same twelve STEP files for the whole run. The starting solver imports each one, reads its bounding box, and emits a hardcoded box of those extents. Parameters are in the function signature and never used. That is mediocre on purpose.",
    code: `def build(width, depth, height):
    return cq.Workplane('XY').box(40, 20, 10)`,
  },
  {
    gen: 1,
    status: "keep",
    err: 0.07671038,
    unlock: "bindBox",
    family: "box",
    names: ["width", "depth", "height"],
    title: "Bind the box names to the axes",
    why: "One edit to the shared solver. If params.json contains width / depth / height (or thick, plate_t), those arguments now drive the box. All twelve tasks are re-scored. Rectangular families start tracking held-out sizes. Circular ones are still boxes.",
    code: `x = width if 'width' in names else dx
y = depth if 'depth' in names else dy
z = height or thick or plate_t or dz
return cq.Workplane('XY').box(x, y, z)`,
  },
  {
    gen: 2,
    status: "keep",
    err: 0.07406043,
    unlock: "hole",
    family: "plateHole",
    names: ["hole_d"],
    title: "When hole_d is present, cut a centered hole",
    why: "Still one solver. A new if-branch: families whose names include hole_d get a through-hole. Four families mention hole_d. Offset, pitch, and counterbore can wait — the centroid term will say so.",
    code: `.box(width, depth, thick)
.faces('>Z').workplane()
.hole(hole_d)`,
  },
  {
    gen: 3,
    status: "keep",
    err: 0.07392169,
    unlock: "offsetHole",
    family: "offsetHole",
    names: ["hole_x", "hole_y"],
    title: "When hole_x / hole_y exist, move the hole",
    why: "The STEP files did not change. This generation added one condition: if those names are in params.json, place the hole there. A centered hole and an offset hole share volume and bounding box. Only the mass centroid moves.",
    code: `.faces('>Z').workplane()
.center(hole_x, hole_y)
.hole(hole_d)`,
  },
  {
    gen: 4,
    status: "keep",
    err: 0.04908365,
    unlock: "cylinder",
    family: "cylinder",
    names: ["radius"],
    title: "When radius is present, emit a cylinder",
    why: "The cylinder task’s STEP is a round solid, but the solver was still emitting the observed square envelope. One branch: names include radius → circle(radius).extrude(height). The other eleven families are untouched.",
    code: `return cq.Workplane('XY').circle(radius).extrude(height)`,
  },
  {
    gen: 5,
    status: "keep",
    err: 0.02089932,
    unlock: "tube",
    family: "tube",
    names: ["outer_r", "inner_r"],
    title: "When outer_r / inner_r exist, emit a tube",
    why: "Same pattern. The tube STEP is an annulus; the solver was still a solid box. Two circles, one extrude. Volume now drops by the inner bore on every held-out vector.",
    code: `return (
    cq.Workplane('XY')
    .circle(outer_r)
    .circle(inner_r)
    .extrude(height)
)`,
  },
  {
    gen: 6,
    status: "keep",
    err: 0.02040682,
    unlock: "cbore",
    family: "counterbore",
    names: ["cbore_d", "cbore_h"],
    title: "When cbore_* exist, use a counterbore",
    why: "A plain through-hole misses the shallow wide cavity in that one family’s STEP. The branch is keyed off the names, not off a family verb — the path is still t_52cd28e5.",
    code: `.faces('>Z').workplane()
.cboreHole(hole_d, cbore_d, cbore_h)`,
  },
  {
    gen: 7,
    status: "keep",
    err: 0.00372274,
    unlock: "boss",
    family: "boss",
    names: ["boss_d", "boss_h"],
    title: "When boss_d / boss_h exist, extrude a boss",
    why: "Two families still emitted a bare plate because nothing in the solver looked at boss_*. One capability: a centered cylinder on the top face. Placement comes next.",
    code: `.box(width, depth, plate_t)
.faces('>Z').workplane()
.circle(boss_d / 2)
.extrude(boss_h)`,
  },
  {
    gen: 8,
    status: "keep",
    err: 0.00329005,
    unlock: "offsetBoss",
    family: "offsetBoss",
    names: ["boss_x", "boss_y"],
    title: "When boss_x / boss_y exist, offset the boss",
    why: "Same lesson as the hole, same twelve files. Centered and offset bosses share volume. boss_x / boss_y have to drive placement or the centroid term stays on the table.",
    code: `.faces('>Z').workplane()
.center(boss_x, boss_y)
.circle(boss_d / 2)
.extrude(boss_h)`,
  },
  {
    gen: 9,
    status: "keep",
    err: 0.0031907,
    unlock: "vFillet",
    family: "fillet",
    names: ["fillet_r"],
    title: "When fillet_r is present, fillet vertical edges",
    why: "Close, not done. Vertical |Z fillets miss the spherical corners that are actually in the STEP. Volume and extents are still a little short on held-out radii.",
    code: `.box(width, depth, height)
.edges('|Z')
.fillet(fillet_r)`,
  },
  {
    gen: 10,
    status: "keep",
    err: 0.00305991,
    unlock: "vChamfer",
    family: "chamfer",
    names: ["chamfer"],
    title: "When chamfer is present, chamfer vertical edges",
    why: "Mirrors the fillet step — and inherits its mistake. The STEP only bevels the top face, which also shifts the centroid downward. The names do not say which edges.",
    code: `.box(width, depth, height)
.edges('|Z')
.chamfer(chamfer)`,
  },
  {
    gen: 11,
    status: "keep",
    err: 0.00090534,
    unlock: "slot",
    family: "slot",
    names: ["slot_l", "slot_w"],
    title: "When slot_l / slot_w exist, cut a slot",
    why: "The slot STEP is a plate with a stadium cut-through. Until this branch existed, that task was still a solid plate. Offset placement is not in the names, so it is not on the hill.",
    code: `.faces('>Z').workplane()
.slot2D(slot_l, slot_w)
.cutThruAll()`,
  },
  {
    gen: 12,
    status: "keep",
    err: 0.00050209,
    unlock: "pitch",
    family: "holePair",
    names: ["pitch"],
    title: "When pitch is present, cut two holes",
    why: "A single centered hole ignores pitch. rarray(pitch, 1, 2, 1) puts centers at ±pitch/2. The STEP already has two holes; the program now reproduces that pattern at any pitch.",
    code: `.faces('>Z').workplane()
.rarray(pitch, 1, 2, 1)
.hole(hole_d)`,
  },
  {
    gen: 13,
    status: "keep",
    err: 0.00014507,
    unlock: "allFillet",
    family: "fillet",
    names: ["fillet_r"],
    title: "Fillet every edge, not only the vertical ones",
    why: "A repair, not a new family. The leftover error on the fillet task was the spherical corners already present in the observed STEP. edges().fillet(fillet_r) matches held-out volume and extents.",
    code: `.box(width, depth, height)
.edges()
.fillet(fillet_r)`,
  },
  {
    gen: 14,
    status: "discard",
    err: 0.00039102,
    attempt: "allChamfer",
    family: "chamfer",
    names: ["chamfer"],
    title: "Chamfer every edge — discarded",
    why: "The same move that fixed fillets. Wrong family. The ground truth only bevels the top face, so all-edge chamfers add volume error. Git resets solver.py. The twelve STEP files are unchanged.",
    code: `.box(width, depth, height)
.edges()
.chamfer(chamfer)   # discarded`,
  },
  {
    gen: 15,
    status: "keep",
    err: 0,
    unlock: "topChamfer",
    family: "chamfer",
    names: ["chamfer"],
    title: "Chamfer the top face only",
    why: "faces('>Z').edges() is the design that is actually in the STEP. Volume, extents, and centroid all land. intent_err hits 0.000. The twelve families are recovered. The files were the same ones as generation 0.",
    code: `.box(width, depth, height)
.faces('>Z').edges()
.chamfer(chamfer)`,
  },
  {
    gen: 16,
    status: "discard",
    err: 0,
    attempt: "offsetSlot",
    family: "slot",
    names: ["slot_x", "slot_y"],
    title: "Offset the slot — discarded",
    why: "There is no slot_x / slot_y on any of the twelve tasks. The score cannot improve past zero, so the edit is thrown away. Rejects stay in the log.",
    code: `.center(slot_x, slot_y)
.slot2D(slot_l, slot_w)   # discarded`,
  },
  {
    gen: 17,
    status: "discard",
    err: 0,
    attempt: "aliases",
    family: "box",
    names: ["length", "breadth"],
    title: "Bind length / breadth — discarded",
    why: "No public family uses those names. Equal score is not a keep. The ratchet is strict: only a lower number stays.",
    code: `x = length or width
y = breadth or depth   # discarded`,
  },
  {
    gen: 18,
    status: "discard",
    err: 0,
    attempt: "countersink",
    family: "plateHole",
    names: ["csink_d"],
    title: "Add a countersink — discarded",
    why: "csink_d / csink_angle are not in any params.json. Inventing a family the evaluator does not have cannot drop the score.",
    code: `.cskHole(hole_d, csink_d, csink_angle)   # discarded`,
  },
  {
    gen: 19,
    status: "discard",
    err: 0,
    attempt: "grid",
    family: "holePair",
    names: ["pitch_x", "pitch_y"],
    title: "A 2×2 hole grid — discarded",
    why: "The family is a pair on one axis, not a rectangular pattern. Extra holes change volume. Discarded, frontier unchanged.",
    code: `.rarray(pitch_x, pitch_y, 2, 2)   # discarded`,
  },
  {
    gen: 20,
    status: "discard",
    err: 0,
    attempt: "blind",
    family: "plateHole",
    names: ["hole_depth"],
    title: "A blind hole — discarded",
    why: "Every hole family is through. A depth parameter that does not exist cannot help. The run ends. The honest part of the log is the cloud of discards.",
    code: `.hole(hole_d, hole_depth)   # discarded`,
  },
];

export const LESSONS = [
  {
    id: "goal",
    sheet: "01",
    kicker: "What we are testing",
    title: "Did you recover the design, or just copy one part?",
    body: "Autoregen is an exam for a coding agent. Twelve parametric CAD families sit under opaque ids. For each family the agent is shown one finished solid and the names of the driving parameters. The official score rebuilds every family at that observed size and at three sizes the agent never saw. Matching the one STEP file is not the task.",
    scene: "gallery",
    family: "box",
    duration: 9000,
    legend: "twelve families · one observed member each",
    artifact: {
      kind: "kv",
      title: "The exam",
      rows: [
        ["Test", "Recover design intent of 12 parametric families"],
        ["Not the test", "Shape-match this one STEP file"],
        ["Score", "Mean error · 12 families × 4 members"],
        ["Pass", "intent_err → 0.000"],
      ],
    },
  },
  {
    id: "prompt",
    sheet: "02",
    kicker: "What the model is given",
    title: "A brief, a solver, and twelve folders. Not a chat about one part.",
    body: "Each generation the harness sends the same instruction: read program.md, read the current solver.py, make exactly one hypothesized improvement, stop. The model is a coding agent editing Python. It is not asked to “look at a STEP and generate CAD.” The STEP files sit in the workspace so solver.py can import them.",
    scene: "workspace",
    family: "box",
    duration: 10000,
    legend: "shown to the agent every generation",
    artifact: {
      kind: "code",
      title: "turn_prompt() · sent every generation",
      text: `Read program.md, solver.py,
and the last 40 lines of results.tsv.

Make exactly one hypothesized
improvement to solver.py.
One capability only.

Write one line to .hypothesis.txt.
Do not edit any other file.
Do not score yourself.
You will be invoked again after
the harness scores this change.`,
    },
  },
  {
    id: "task",
    sheet: "03",
    kicker: "What's in a folder",
    title: "One STEP file is one size of one family.",
    body: "Open any task. target.step is a B-rep solid — faces and edges of one specific part. It is the finished member, not the recipe. params.json lists the names. The actual numbers are withheld. The family verb (“offset hole”) is not in the path. Click another family on the right to open its folder.",
    scene: "task",
    family: "offsetHole",
    duration: 11000,
    legend: "shown · one observed member",
    artifact: {
      kind: "files",
      title: "data/tasks/<id>/",
    },
  },
  {
    id: "stepfile",
    sheet: "03",
    kicker: "What's in the STEP file",
    title: "Vertices and faces. No box(width, depth, height).",
    body: "STEP (ISO 10303) is a text dump of geometry: points, edges, faces. The baseline solver imports it, measures the bounding box (the wire cage), and emits a hardcoded box of those extents. That is why it can look right on this member and still have no idea how the family works.",
    scene: "steptext",
    family: "offsetHole",
    duration: 11000,
    legend: "the file is the finished part, not the program",
    artifact: {
      kind: "code",
      title: "target.step · excerpt",
      text: `ISO-10303-21;
HEADER;
FILE_SCHEMA(('AUTOMOTIVE_DESIGN'));
ENDSEC;
DATA;
#15 = MANIFOLD_SOLID_BREP('',#16);
#23 = CARTESIAN_POINT('',(-28.,-17.,-3.));
#32 = PLANE('',#33);
#16 = CLOSED_SHELL('',(#17, …));
… faces, edges, vertices …
ENDSEC;`,
    },
  },
  {
    id: "emit",
    sheet: "04",
    kicker: "What the model must write",
    title: "A program that rebuilds the family at any size.",
    body: "solve(task_dir) looks at the STEP and the names, then returns Python source defining build(**params). The evaluator will call that function with the sealed numbers — including sizes that were never in the folder. If build() ignores its arguments, the held-out members fail. The first solid is what the agent saw. The other three are the exam.",
    scene: "contract",
    family: "offsetHole",
    duration: 11000,
    legend: "shown · sealed · sealed · sealed",
    artifact: {
      kind: "code",
      title: "solver.py must emit",
      text: `def solve(task_dir):
    names = read("params.json")["names"]
    solid = importStep("target.step")
    # inspect names + topology
    return """
def build(width, depth, thick,
          hole_d, hole_x, hole_y):
    return (cq.Workplane('XY')
        .box(width, depth, thick)
        .faces('>Z').workplane()
        .center(hole_x, hole_y)
        .hole(hole_d))
"""`,
    },
  },
  {
    id: "trap",
    sheet: "05",
    kicker: "Why copying loses",
    title: "The next size is the test.",
    body: "Same family, four members. Aluminum is the baseline: it always emits the observed 40×20×10 box. Cyan is the truth. The first one matches. The other three are sizes the agent was never shown. A solver that hard-codes the STEP it saw looks fine on the part you were shown and falls over on the next order.",
    scene: "trap",
    family: "box",
    duration: 11000,
    legend: "aluminum = baseline copy · cyan = sealed truth",
    artifact: {
      kind: "kv",
      title: "Box family · t_1c598275",
      rows: [
        ["Shown", "width=40  depth=20  height=10"],
        ["Sealed", "70×25×12"],
        ["Sealed", "35×35×20"],
        ["Sealed", "22×55×14"],
        ["Baseline", "always emits box(40, 20, 10)"],
      ],
    },
  },
  {
    id: "score",
    sheet: "06",
    kicker: "How we know",
    title: "Volume, box, and centroid. One number.",
    body: "shape_err mixes three signals. A centered hole and an offset hole have the same volume and the same bounding box. Only the mass centroid (the pin) moves. intent_err is the mean of shape_err over twelve families times four members. A crash scores 1.0. Keep only if the mean is strictly lower.",
    scene: "centroid",
    family: "offsetHole",
    duration: 11000,
    legend: "same volume · same bbox · different centroid",
    artifact: {
      kind: "code",
      title: "prepare.py",
      text: `shape_err  = ⅓ |Δvolume| / volume
           + ⅓ mean |Δextent| / extent
           + ⅓ |Δcentroid| / bbox_diag

intent_err = mean over
  12 families × 4 members

keep if new < best
else git checkout -- solver.py`,
    },
  },
  {
    id: "loop",
    sheet: "07",
    kicker: "What iterates",
    title: "The STEP files stay put. The solver is what changes.",
    body: "There are twelve observed STEP files for the whole run. They do not cycle. They do not get replaced. Each generation edits one shared solver.py. Then the evaluator scores all twelve families at four members each — 48 solids — and keeps the edit only if the mean dropped. The next start is the last accepted solver, not a discarded guess, and not “the next STEP file.”",
    scene: "loop",
    family: "box",
    duration: 12000,
    legend: "12 files · fixed · scored together every generation",
    artifact: {
      kind: "kv",
      title: "One generation",
      rows: [
        ["1", "Agent edits solver.py once"],
        ["2", "Evaluator calls solve() on all 12 tasks"],
        ["3", "For each task: build(observed) + build(3 held-outs)"],
        ["4", "48 solids → one mean, intent_err"],
        ["5", "Strictly lower → git keep. Else reset."],
      ],
    },
  },
  {
    id: "generation",
    sheet: "08",
    kicker: "How a step actually works",
    title: "One hypothesis. Then the whole exam is re-graded.",
    body: "Generation 3, as a close-up. Grok saw hole_x and hole_y in one params.json and added a branch to the shared solver: when those names appear, place the hole there. After the edit, every family is scored again. The offset-hole family improves; the others stay as they were. Mean 0.07406 → 0.07392. Keep. The twelve STEP files were not touched.",
    scene: "onegen",
    family: "offsetHole",
    duration: 12000,
    legend: "before → after, on the family this edit names",
    artifact: {
      kind: "code",
      title: "generation 3 · keep",
      text: `.hypothesis.txt
When hole_x and hole_y are present
with hole_d, place the through-hole
at (hole_x, hole_y) instead of center.

intent_err  0.07406 → 0.07392  keep
12 families re-scored
STEP files unchanged`,
    },
  },
  {
    id: "handoff",
    sheet: "09",
    kicker: "Then a real run",
    title: "Grok 4.5 did this twenty times.",
    body: "Same starting solver. Same twelve STEP files. One capability per generation. Fourteen keeps, six discards, zero at generation 15. The next section is that log, replayed on the solids. Remember: you are watching one program get better at an exam that does not change.",
    scene: "gallery-done",
    family: "box",
    duration: 8000,
    legend: "recovered · the files were the same ones as sheet 01",
    artifact: {
      kind: "kv",
      title: "Grok 4.5 · high · 20 gens",
      rows: [
        ["Start", "0.258"],
        ["Keeps", "14"],
        ["Discards", "6"],
        ["Solved at", "generation 15"],
        ["Final", "0.000"],
      ],
    },
  },
];

export const SHEETS = [
  { id: "01", label: "The exam", lesson: "goal" },
  { id: "02", label: "The input", lesson: "prompt" },
  { id: "03", label: "A task", lesson: "task" },
  { id: "04", label: "The output", lesson: "emit" },
  { id: "05", label: "The trap", lesson: "trap" },
  { id: "06", label: "The score", lesson: "score" },
  { id: "07", label: "The loop", lesson: "loop" },
  { id: "08", label: "One step", lesson: "generation" },
  { id: "09", label: "The run", lesson: "handoff" },
];

export const UNLOCK_ORDER = [
  "bindBox",
  "hole",
  "offsetHole",
  "cylinder",
  "tube",
  "cbore",
  "boss",
  "offsetBoss",
  "vFillet",
  "vChamfer",
  "slot",
  "pitch",
  "allFillet",
  "topChamfer",
];

export function familyById(id) {
  return FAMILY_BY_ID[id];
}

export function capsAt(gen) {
  const caps = new Set();
  for (const g of GENS) {
    if (g.gen > gen) break;
    if (g.status === "keep" && g.unlock) caps.add(g.unlock);
  }
  return caps;
}

export function lastKeepErr(gen) {
  let err = GENS[0].err;
  for (const g of GENS) {
    if (g.gen > gen) break;
    if (g.status === "keep") err = g.err;
  }
  return err;
}

export function familyState(family, gen) {
  if (family.recover.at <= gen) return "recovered";
  if (family.recover.partial != null && family.recover.partial <= gen) return "partial";
  return "pending";
}

export function formatErr(n) {
  if (n === 0) return "0.000";
  if (n < 0.001) return n.toFixed(6).replace(/0+$/, "").replace(/\.$/, "");
  return n.toFixed(3);
}

export function formatParams(params) {
  return Object.entries(params)
    .map(([k, v]) => `${k}=${v}`)
    .join("  ");
}

export function formatSize(params) {
  if (params.width != null && params.depth != null) {
    const z = params.height ?? params.thick ?? params.plate_t;
    return z != null ? `${params.width}×${params.depth}×${z}` : `${params.width}×${params.depth}`;
  }
  if (params.radius != null) return `r${params.radius} × ${params.height}`;
  if (params.outer_r != null) return `ø${params.outer_r * 2} / ${params.inner_r * 2} × ${params.height}`;
  return formatParams(params);
}

export function paramsCard(family) {
  const names = family.names.map((n) => n.padEnd(10)).join("\n");
  const blanks = family.names.map(() => "—").join("\n");
  return {
    names: family.names,
    withheld: family.names.map(() => "—"),
    block: family.names.map((n) => `${n.padEnd(10)} —`).join("\n"),
    header: names,
    values: blanks,
  };
}
