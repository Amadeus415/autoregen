import {
  LESSONS,
  GENS,
  familyById,
  capsAt,
  lastKeepErr,
  formatErr,
  formatSize,
  paramsCard,
} from "./data.js";
import { makePart, SCALE, bboxCage, centroidPin, approxCentroid } from "./parts.js";
import { placeRow } from "./studio.js";

const REDUCED = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const none = new Set();

export const STEPS = [
  ...LESSONS.map((s) => ({ ...s, kind: "lesson" })),
  ...GENS.map((g) => ({
    ...g,
    kind: "gen",
    id: `g${g.gen}`,
    duration: g.status === "discard" ? 5600 : 4800,
  })),
];

const FIRST_GEN = STEPS.findIndex((s) => s.kind === "gen");

export class Tour {
  constructor(studio, ui) {
    this.studio = studio;
    this.ui = ui;
    this.index = 0;
    this.playing = false;
    this.timer = 0;
    this.view = "auto";
    this.focusFamily = null;
    this.studio.onPick = (id) => this.inspectFamily(id);
  }

  get step() {
    return STEPS[this.index];
  }

  go(i, { fromUser = false, silentHash = false } = {}) {
    this.index = Math.max(0, Math.min(STEPS.length - 1, i));
    if (fromUser) this.pause();
    this.view = "auto";
    if (this.step.kind === "lesson") this.focusFamily = null;
    this.apply();
    if (!silentHash) {
      const step = this.step;
      const hash = step.kind === "lesson" ? `#${step.id}` : `#gen=${step.gen}`;
      if (location.hash !== hash) history.replaceState(null, "", hash);
    }
    if (this.playing) this.#arm();
  }

  startFromHash() {
    const raw = (location.hash || "").replace(/^#/, "");
    if (!raw) return this.go(0, { silentHash: true });
    if (raw.startsWith("gen=")) {
      const gen = Number(raw.slice(4));
      if (Number.isFinite(gen)) return this.jumpGen(gen, false);
    }
    const lesson = STEPS.findIndex((s) => s.kind === "lesson" && (s.id === raw || s.sheet === raw));
    if (lesson >= 0) return this.go(lesson, { silentHash: true });
    this.go(0, { silentHash: true });
  }

  next(fromUser = false) {
    if (this.index >= STEPS.length - 1) {
      this.pause();
      return;
    }
    this.go(this.index + 1, { fromUser });
  }

  prev(fromUser = false) {
    this.go(this.index - 1, { fromUser });
  }

  jumpGen(gen, fromUser = true) {
    const i = STEPS.findIndex((s) => s.kind === "gen" && s.gen === gen);
    if (i >= 0) this.go(i, { fromUser });
  }

  jumpLesson(id, fromUser = true) {
    const i = STEPS.findIndex((s) => s.kind === "lesson" && s.id === id);
    if (i >= 0) this.go(i, { fromUser });
  }

  skipToRun() {
    this.go(FIRST_GEN, { fromUser: true });
  }

  toIntro() {
    this.go(0, { fromUser: true });
  }

  play() {
    if (this.index >= STEPS.length - 1) this.index = 0;
    this.playing = true;
    this.ui.setPlaying(true);
    this.apply();
    this.#arm();
  }

  pause() {
    this.playing = false;
    this.ui.setPlaying(false);
    clearTimeout(this.timer);
  }

  toggle() {
    if (this.playing) this.pause();
    else this.play();
  }

  #arm() {
    clearTimeout(this.timer);
    this.timer = setTimeout(() => this.next(false), this.step.duration || 5000);
  }

  setView(view) {
    this.pause();
    this.view = view;
    this.apply();
  }

  inspectFamily(id) {
    this.pause();
    this.focusFamily = id;
    if (this.step.kind === "lesson") {
      const scene = this.step.scene;
      if (scene === "task" || scene === "steptext" || scene === "contract" || scene === "onegen") {
        this.apply();
        return;
      }
      this.jumpLesson("task");
      this.focusFamily = id;
      this.apply();
      return;
    }
    this.view = "hero";
    this.apply();
  }

  apply() {
    const step = this.step;
    this.studio.clearStage();
    this.studio.stage.rotation.y = 0;
    this.studio.setRotate(false);
    if (step.kind === "lesson") this.#lesson(step);
    else this.#gen(step);
    this.ui.render(this);
  }

  #family(step) {
    return familyById(this.focusFamily || step.family);
  }

  #lesson(step) {
    const family = this.#family(step);
    const done = capsAt(20);

    if (step.scene === "gallery") {
      this.studio.setGrid(done, 20, { labels: "name", truth: true });
      this.studio.setRotate(true);
      this.studio.frame("workspace", 1100);
      return;
    }

    if (step.scene === "workspace") {
      this.studio.setGrid(done, 20, { labels: "task", truth: true });
      this.studio.frame("workspace", 1100);
      return;
    }

    if (step.scene === "task" || step.scene === "steptext") {
      const part = makePart({
        family,
        params: family.observed,
        caps: done,
        kind: "truth",
        scale: SCALE * 1.02,
      });
      this.studio.addHero(part, `${family.taskId} / target.step`, "anno");
      const bb = family.observedBB;
      const cage = bboxCage(bb.x, bb.y, bb.z);
      cage.scale.setScalar(SCALE * 1.02);
      this.studio.hero.add(cage);
      this.studio.annotate(this.studio.hero, formatSize(family.observed), -0.52, "anno anno-faint");
      this.studio.setRotate(true);
      this.studio.frame("task", 1000);
      return;
    }

    if (step.scene === "contract") {
      this.#members(family, done, 20, {
        labels: ["shown to the agent", "sealed · held-out 1", "sealed · held-out 2", "sealed · held-out 3"],
        recovered: true,
      });
      return;
    }

    if (step.scene === "trap") {
      const box = familyById("box");
      const members = [box.observed, ...box.heldout];
      const parts = members.map((params, i) => {
        const guess = makePart({
          family: box,
          params,
          caps: none,
          kind: "pending",
          scale: SCALE * 0.82,
        });
        const truth = makePart({
          family: box,
          params,
          caps: done,
          kind: "ghost",
          scale: 1,
        });
        guess.add(truth);
        this.studio.annotate(guess, i === 0 ? "shown" : `sealed ${i}`, -0.22, i === 0 ? "anno" : "anno anno-truth");
        this.studio.annotate(guess, formatSize(params), -0.48, "anno anno-faint");
        return guess;
      });
      placeRow(parts, 3.45);
      this.studio.setExtras(parts);
      this.studio.frame("trap", 1100);
      return;
    }

    if (step.scene === "centroid") {
      const centered = familyById("plateHole");
      const offset = familyById("offsetHole");
      const left = makePart({
        family: centered,
        params: centered.observed,
        caps: done,
        kind: "solid",
        scale: SCALE * 1.05,
      });
      const right = makePart({
        family: offset,
        params: offset.observed,
        caps: done,
        kind: "solid",
        scale: SCALE * 1.05,
      });
      const lc = approxCentroid(centered, centered.observed);
      const rc = approxCentroid(offset, offset.observed);
      left.add(centroidPin(lc.x, lc.y, lc.z, 0x161c20));
      right.add(centroidPin(rc.x, rc.y, rc.z, 0x0e7490));
      left.position.set(-2.35, 0, 0);
      right.position.set(2.35, 0, 0);
      this.studio.annotate(left, "centered hole", -0.3);
      this.studio.annotate(right, "offset hole", -0.3, "anno anno-truth");
      this.studio.setExtras([left, right]);
      this.studio.frame("centroid", 1100);
      return;
    }

    if (step.scene === "loop") {
      this.studio.setGrid(done, 20, { labels: "task", locked: true, truth: true, highlightId: "offsetHole" });
      this.studio.frame("loop", 1100);
      return;
    }

    if (step.scene === "onegen") {
      const before = capsAt(2);
      const after = capsAt(3);
      const members = [family.observed, ...family.heldout];
      const parts = members.map((params, i) => {
        const guess = makePart({
          family,
          params,
          caps: after,
          kind: "solid",
          scale: SCALE * 0.78,
        });
        const prev = makePart({
          family,
          params,
          caps: before,
          kind: "ghost",
          scale: 1,
        });
        guess.add(prev);
        this.studio.annotate(guess, i === 0 ? "observed" : `held-out ${i}`, -0.28, i === 0 ? "anno" : "anno anno-truth");
        return guess;
      });
      placeRow(parts, 3.45);
      this.studio.setExtras(parts);
      this.studio.frame("onegen", 1100);
      return;
    }

    this.studio.setGrid(done, 20, { labels: "name", truth: true });
    this.studio.setRotate(true);
    this.studio.frame("workspace", 1100);
  }

  #gen(step) {
    const family = familyById(this.focusFamily || step.family);
    const afterCaps = capsAt(step.gen);
    const beforeCaps = capsAt(step.gen - 1);
    const frontier = step.status === "keep" ? afterCaps : beforeCaps;
    const frontierGen = step.status === "keep" ? step.gen : Math.max(0, step.gen - 1);
    const view = this.view === "auto" ? defaultView(step) : this.view;

    this.studio.setShelf(frontier, family.id, frontierGen, { focus: view === "gallery" });
    this.studio.showShelf(view === "gallery");

    if (view === "gallery") {
      this.studio.setGrid(frontier, frontierGen, { labels: "name", highlightId: family.id });
      this.studio.frame("gallery", REDUCED ? 0 : 800);
      return;
    }

    if (view === "members") {
      this.#members(family, frontier, frontierGen);
      return;
    }

    const params = family.observed;
    const recovered = family.recover.at <= frontierGen;

    if (step.status === "discard" && step.attempt && !this.focusFamily) {
      this.studio.addHero(
        makePart({
          family,
          params,
          caps: beforeCaps,
          kind: "discard",
          attempt: step.attempt,
          scale: SCALE * 1.12,
        }),
        "discarded hypothesis",
        "anno anno-miss",
      );
      this.studio.addGhost(
        makePart({
          family,
          params,
          caps: frontier,
          kind: recovered ? "solid" : "pending",
          scale: SCALE * 1.12,
        }),
        "kept frontier",
      );
      this.studio.hero.position.x = -2.15;
      this.studio.ghost.position.x = 2.15;
      this.studio.frame("compare", REDUCED ? 0 : 850);
      return;
    }

    this.studio.addHero(
      makePart({
        family,
        params,
        caps: frontier,
        kind: recovered ? "solid" : "pending",
        scale: SCALE * 1.14,
      }),
      family.name.toLowerCase(),
    );

    if (!recovered) {
      this.studio.addGhost(
        makePart({ family, params, caps: frontier, kind: "ghost", scale: SCALE * 1.14 }),
        "sealed truth",
      );
    }

    this.studio.setRotate(true);
    this.studio.frame("hero", REDUCED ? 0 : 800);
  }

  #members(family, caps, frontierGen, { labels, recovered } = {}) {
    this.studio.showShelf(false);
    const isRec = recovered ?? family.recover.at <= frontierGen;
    const parts = [family.observed, ...family.heldout].map((params, i) => {
      const guess = makePart({
        family,
        params,
        caps,
        kind: isRec ? "solid" : "pending",
        scale: SCALE * 0.82,
      });
      if (!isRec) {
        guess.add(makePart({ family, params, caps, kind: "ghost", scale: 1 }));
      }
      const caption = labels ? labels[i] : i === 0 ? "observed · shown" : `held-out ${i} · sealed`;
      this.studio.annotate(guess, caption, -0.22, i === 0 ? "anno" : "anno anno-truth");
      this.studio.annotate(guess, formatSize(params), -0.46, "anno anno-faint");
      return guess;
    });
    placeRow(parts, 2.95);
    this.studio.setExtras(parts);
    this.studio.frame("members", REDUCED ? 0 : 900);
  }

  hud() {
    const step = this.step;
    if (step.kind === "lesson") {
      const family = this.#family(step);
      return {
        mode: "lesson",
        kicker: step.kicker,
        title: step.title,
        body: step.body,
        sheet: step.sheet,
        scene: step.scene,
        legend: step.legend,
        artifact: artifactFor(step, family),
        status: "",
        genLabel: `Sheet ${step.sheet}`,
        err: null,
        displayErr: null,
        family: family.id,
        view: "auto",
      };
    }
    const displayErr = step.status === "keep" ? step.err : lastKeepErr(step.gen - 1);
    const focused = this.focusFamily && this.focusFamily !== step.family;
    const fam = focused ? familyById(this.focusFamily) : familyById(step.family);
    return {
      mode: "run",
      kicker: focused
        ? `Generation ${step.gen} · ${fam.name}`
        : `Generation ${step.gen} · ${step.status} · same 12 files`,
      title: focused ? fam.name : step.title,
      body: focused
        ? `${fam.taskId} at generation ${step.gen}. The STEP file has not changed. You are seeing what the shared solver now emits for this family.`
        : step.why,
      code: step.code,
      status: step.status,
      gen: step.gen,
      genLabel: `Gen ${step.gen}`,
      err: step.err,
      displayErr,
      errLabel: formatErr(step.err),
      frontierLabel: formatErr(displayErr),
      family: this.focusFamily || step.family,
      names: step.names || [],
      view: this.view === "auto" ? defaultView(step) : this.view,
      legend:
        step.status === "discard"
          ? "red = discarded guess · the frontier did not move"
          : "same 12 STEP files · one edit to solver.py",
      artifact: {
        kind: "code",
        title: focused ? `${fam.taskId} · solver at gen ${step.gen}` : `solver.py · generation ${step.gen}`,
        text: step.code,
      },
    };
  }
}

function defaultView(step) {
  if (step.gen <= 1) return "members";
  if (step.status === "discard") return "hero";
  return "hero";
}

function artifactFor(step, family) {
  const base = step.artifact || { kind: "kv", title: "", rows: [] };
  if (step.scene === "task" || step.scene === "steptext" || base.kind === "files") {
    const card = paramsCard(family);
    return {
      kind: "files",
      title: `data/tasks/${family.taskId}/`,
      family,
      card,
    };
  }
  return base;
}
