import { GENS, FAMILIES, SHEETS, RUN, familyState, formatErr, formatSize } from "./data.js";
import { STEPS } from "./tour.js";

export class UI {
  constructor() {
    this.root = document.getElementById("ui");
    this.playing = false;
    this.handlers = {};
  }

  on(name, fn) {
    this.handlers[name] = fn;
  }

  emit(name, ...args) {
    this.handlers[name]?.(...args);
  }

  setPlaying(on) {
    this.playing = on;
    const btn = document.getElementById("btn-play");
    if (btn) {
      btn.textContent = on ? "Pause" : "Play";
      btn.setAttribute("aria-pressed", on ? "true" : "false");
    }
  }

  mount() {
    this.#bind();
    this.#sheets();
    this.#rail();
    this.#families();
  }

  #bind() {
    document.getElementById("btn-prev").addEventListener("click", () => this.emit("prev"));
    document.getElementById("btn-next").addEventListener("click", () => this.emit("next"));
    document.getElementById("btn-play").addEventListener("click", () => this.emit("toggle"));
    document.getElementById("btn-intro").addEventListener("click", () => this.emit("intro"));
    document.getElementById("btn-run").addEventListener("click", () => this.emit("run"));
    document.querySelectorAll("[data-view]").forEach((el) => {
      el.addEventListener("click", () => this.emit("view", el.dataset.view));
    });

    window.addEventListener("keydown", (e) => {
      const tag = document.activeElement?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      if (e.key === "ArrowRight" || e.key === "j") {
        e.preventDefault();
        this.emit("next");
      } else if (e.key === "ArrowLeft" || e.key === "k") {
        e.preventDefault();
        this.emit("prev");
      } else if (e.key === " ") {
        e.preventDefault();
        this.emit("toggle");
      } else if (e.key === "Home") {
        e.preventDefault();
        this.emit("intro");
      } else if (e.key === "g") {
        this.emit("view", "gallery");
      } else if (e.key === "m") {
        this.emit("view", "members");
      } else if (e.key === "h") {
        this.emit("view", "hero");
      }
    });
  }

  #sheets() {
    const nav = document.getElementById("sheets");
    nav.innerHTML = SHEETS.map(
      (s) => `<button class="sheet" data-lesson="${s.lesson}" type="button">
        <span class="sn">${s.id}</span>
        <span class="sl">${s.label}</span>
      </button>`,
    ).join("");
    nav.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-lesson]");
      if (btn) this.emit("lesson", btn.dataset.lesson);
    });
  }

  #rail() {
    const rail = document.getElementById("rail");
    rail.innerHTML = GENS.map((g) => {
      return `<button class="tick" data-gen="${g.gen}" type="button">
        <i class="dot ${g.status}"></i>
        <span class="n">${g.gen}</span>
        <span class="e">${formatErr(g.err)}</span>
      </button>`;
    }).join("");
    rail.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-gen]");
      if (btn) this.emit("gen", Number(btn.dataset.gen));
    });

    const scrub = document.getElementById("scrub");
    scrub.innerHTML = STEPS.map((s, i) => {
      const cls = s.kind === "gen" ? s.status : "lesson";
      const label = s.kind === "gen" ? `Generation ${s.gen}` : s.title;
      return `<button class="scrub-dot ${cls}" data-step="${i}" type="button" aria-label="${label}"></button>`;
    }).join("");
    scrub.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-step]");
      if (btn) this.emit("step", Number(btn.dataset.step));
    });
  }

  #families() {
    const el = document.getElementById("families");
    el.innerHTML = FAMILIES.map(
      (f) => `<button class="fam" data-fam="${f.id}" type="button">
        <i class="dot pending"></i>
        <span class="fn">${f.name}</span>
        <span class="fh">${f.taskId}</span>
      </button>`,
    ).join("");
    el.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-fam]");
      if (btn) this.emit("family", btn.dataset.fam);
    });
  }

  render(tour) {
    const hud = tour.hud();
    const step = tour.step;
    const isLesson = step.kind === "lesson";
    const gen = step.kind === "gen" ? step.gen : null;

    document.body.dataset.mode = isLesson ? "lesson" : "run";
    document.getElementById("kicker").textContent = hud.kicker;
    document.getElementById("title").textContent = hud.title;
    document.getElementById("body").textContent = hud.body;
    document.getElementById("sheet-no").textContent = isLesson ? step.sheet : String(step.gen).padStart(2, "0");
    document.getElementById("sheet-of").textContent = isLesson ? "09" : "20";
    document.getElementById("sheet-name").textContent = isLesson ? step.kicker : `Generation ${step.gen}`;
    const tbLabel = document.querySelector(".tb-label");
    if (tbLabel) tbLabel.textContent = isLesson ? "Sheet" : "Gen";
    document.getElementById("stage-legend").textContent = hud.legend || "";

    this.#artifact(hud, tour);

    const score = document.getElementById("score");
    const scoreLabel = document.getElementById("score-caption");
    const fill = document.getElementById("score-fill");
    const scorebox = document.getElementById("scorebox");
    if (hud.err == null) {
      score.textContent = formatErr(RUN.start);
      scoreLabel.textContent = "baseline intent_err";
      fill.style.width = "100%";
      score.dataset.status = "";
      scorebox.hidden = isLesson;
    } else {
      scorebox.hidden = false;
      score.textContent = hud.status === "discard" ? hud.errLabel : hud.frontierLabel;
      scoreLabel.textContent =
        hud.status === "discard"
          ? `would be ${hud.errLabel} · frontier ${hud.frontierLabel}`
          : "intent_err · mean of 48 solids";
      const v = hud.status === "discard" ? hud.displayErr : hud.err;
      fill.style.width = `${Math.max(2, (v / RUN.start) * 100)}%`;
      score.dataset.status = hud.status;
    }

    document.getElementById("progress").style.width = `${((tour.index + 1) / STEPS.length) * 100}%`;
    document.getElementById("step-count").textContent = `${tour.index + 1} / ${STEPS.length}`;

    document.querySelectorAll(".sheet").forEach((el) => {
      const sheet = SHEETS.find((s) => s.lesson === el.dataset.lesson);
      el.classList.toggle("is-on", isLesson && sheet && sheet.id === step.sheet);
      el.classList.toggle("is-past", isLesson && sheet && sheet.id < step.sheet);
    });

    document.querySelectorAll(".tick, .scrub-dot").forEach((el) => {
      if (el.dataset.gen != null) {
        const g = Number(el.dataset.gen);
        el.classList.toggle("is-on", gen === g);
        el.classList.toggle("is-past", gen != null && g < gen);
      }
      if (el.dataset.step != null) {
        const i = Number(el.dataset.step);
        el.classList.toggle("is-on", tour.index === i);
        el.classList.toggle("is-past", i < tour.index);
      }
    });

    const frontierGen = gen == null ? (isLesson && step.scene === "gallery-done" ? 20 : isLesson && step.scene === "loop" ? 3 : -1) : step.status === "keep" ? gen : gen - 1;
    document.querySelectorAll(".fam").forEach((el) => {
      const id = el.dataset.fam;
      const fam = FAMILIES.find((f) => f.id === id);
      const state = frontierGen < 0 ? "pending" : familyState(fam, frontierGen);
      el.dataset.state = state;
      const focused = ["task", "steptext", "contract", "onegen", "centroid", "trap"].includes(step.scene || "") || step.kind === "gen";
      el.classList.toggle("is-on", focused && hud.family === id);
      el.querySelector(".dot").className = `dot ${state}`;
    });

    document.querySelector(".views").hidden = isLesson;
    document.querySelectorAll("[data-view]").forEach((el) => {
      el.classList.toggle("is-on", el.dataset.view === hud.view);
    });

    document.getElementById("btn-intro").classList.toggle("is-on", isLesson);
    document.getElementById("btn-run").classList.toggle("is-on", !isLesson);

    const rail = document.getElementById("rail");
    const on = rail.querySelector(".tick.is-on");
    if (on) on.scrollIntoView({ block: "nearest" });

    document.getElementById("btn-prev").disabled = tour.index === 0;
    document.getElementById("btn-next").disabled = tour.index === STEPS.length - 1;
  }

  #artifact(hud, tour) {
    const el = document.getElementById("artifact");
    const art = hud.artifact;
    if (!art) {
      el.hidden = true;
      el.innerHTML = "";
      return;
    }
    el.hidden = false;
    if (art.kind === "files") {
      const f = art.family;
      const names = f.names
        .map((n) => `<tr><td>${n}</td><td class="blank">withheld</td></tr>`)
        .join("");
      el.innerHTML = `
        <div class="art-kicker">${art.title}</div>
        <div class="filecard">
          <div class="file">
            <div class="file-name">target.step</div>
            <p>${f.step}</p>
            <div class="file-meta">observed member · ${formatSize(f.observed)}</div>
          </div>
          <div class="file">
            <div class="file-name">params.json</div>
            <table class="params">${names}</table>
          </div>
        </div>`;
      return;
    }
    if (art.kind === "kv") {
      const rows = art.rows
        .map(([k, v]) => `<tr><th>${escapeHtml(k)}</th><td>${escapeHtml(v)}</td></tr>`)
        .join("");
      el.innerHTML = `<div class="art-kicker">${escapeHtml(art.title)}</div><table class="kv">${rows}</table>`;
      return;
    }
    el.innerHTML = `<div class="art-kicker">${escapeHtml(art.title)}</div><pre class="code">${escapeHtml(art.text || "")}</pre>`;
  }
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}
