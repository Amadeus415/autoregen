import { Studio } from "./studio.js";
import { UI } from "./ui.js";
import { Tour } from "./tour.js";

window.addEventListener("error", (event) => {
  const el = document.getElementById("boot-error") || document.createElement("pre");
  el.id = "boot-error";
  el.textContent = String(event.error?.stack || event.message || event);
  document.body.appendChild(el);
});
window.addEventListener("unhandledrejection", (event) => {
  const el = document.getElementById("boot-error") || document.createElement("pre");
  el.id = "boot-error";
  el.textContent = String(event.reason?.stack || event.reason || event);
  document.body.appendChild(el);
});

const canvas = document.getElementById("stage");
let studio;
try {
  studio = new Studio(canvas);
} catch (err) {
  const el = document.getElementById("boot-error") || document.createElement("pre");
  el.id = "boot-error";
  el.textContent = String(err?.stack || err);
  document.body.appendChild(el);
  throw err;
}
const ui = new UI();
const tour = new Tour(studio, ui);

ui.mount();
ui.on("prev", () => tour.prev(true));
ui.on("next", () => tour.next(true));
ui.on("toggle", () => tour.toggle());
ui.on("intro", () => tour.toIntro());
ui.on("run", () => tour.skipToRun());
ui.on("gen", (g) => tour.jumpGen(g));
ui.on("lesson", (id) => tour.jumpLesson(id));
ui.on("step", (i) => tour.go(i, { fromUser: true }));
ui.on("family", (id) => tour.inspectFamily(id));
ui.on("view", (v) => tour.setView(v));

tour.startFromHash();
window.addEventListener("hashchange", () => tour.startFromHash());

function frame() {
  studio.tick();
  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);
