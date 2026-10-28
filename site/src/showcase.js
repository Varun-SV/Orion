import { collections } from "./collections";

const arrow =
  '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M4 10h12m-5-5 5 5-5 5"/></svg>';
const file =
  '<svg viewBox="0 0 24 28" aria-hidden="true"><path d="M4 1h10l6 6v20H4zM14 1v7h6M8 15h8M8 19h6"/></svg>';
const check =
  '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="m3 8 3 3 7-7"/></svg>';

export function showcaseMarkup() {
  return `<section class="showcase" aria-label="Interactive organising sample">
    <div class="showcase-top"><span class="workspace-brand"><span class="orbit-mark" aria-hidden="true">✦</span> ORION <span class="workspace-caption">/ THE WORKSPACE</span></span><span class="live-label"><i></i> LOCAL</span></div>
    <div class="sample-tabs" role="group" aria-label="Sample collection">${[0, 5, 6].map((i) => `<button type="button" data-sample="${i}" aria-label="Sample ${collections[i].name}" aria-pressed="${i === 0}">${collections[i].name}</button>`).join("")}<span>↗</span></div>
    <div class="showcase-body" data-showcase-body></div>
    <div class="showcase-footer"><span class="sample-disclosure">FICTIONAL SAMPLE <span>· browser only</span></span><span class="sample-footer-symbol" aria-hidden="true">⊕</span></div>
  </section>`;
}

export function mountShowcase(root) {
  let selected = 0,
    phase = 0;
  const body = root.querySelector("[data-showcase-body]");
  function draw() {
    const item = collections[selected];
    root.dataset.phase = String(phase);
    root
      .querySelectorAll("[data-sample]")
      .forEach((button) =>
        button.setAttribute(
          "aria-pressed",
          String(Number(button.dataset.sample) === selected),
        ),
      );
    const parts = item.source.split("/");
    const sourceName = parts.at(-1);
    body.innerHTML = `<div class="sample-section-head"><div><span class="overline">${phase === 0 ? "01 / INCOMING" : phase === 1 ? "02 / YOUR PREVIEW" : "03 / IN ORBIT"}</span><h3>${phase === 0 ? "A little scattered." : phase === 1 ? "A place for everything." : "Beautifully in order."}</h3></div><span class="sample-count">${phase === 2 ? "✓" : "01"} <span>FILE</span></span></div>
      <div class="sample-file ${phase === 2 ? "is-organised" : ""}"><span class="file-icon">${phase === 2 ? check : file}</span><div><span class="file-eyebrow">${phase === 0 ? "SOURCE FILE" : phase === 1 ? "CONFIRMED SAMPLE MATCH" : "ORGANISED SAMPLE"}</span><strong>${phase === 0 ? sourceName : item.title + (item.year ? " (" + item.year + ")" : "")}</strong><span class="file-metadata">${phase === 0 ? "Waiting for a clearer home" : item.detail}</span></div><span class="file-status">${phase === 0 ? "···" : check}</span></div>
      <div class="transfer-visual" aria-hidden="true"><span class="transfer-thread"></span><span class="transfer-particle"></span><span class="transfer-copy">${phase === 0 ? "IDENTIFY · REVIEW · PREVIEW" : phase === 1 ? "YOU SEE EVERY PATH FIRST" : "SIMULATED IN YOUR BROWSER"}</span></div>
      <div class="sample-destination ${phase === 0 ? "is-awaiting" : ""}" ${phase > 0 ? 'data-testid="hero-plan"' : ""}><span class="folder-symbol" aria-hidden="true">${phase === 0 ? "⊞" : "▱"}</span><div><span class="file-eyebrow">${phase === 0 ? "THE DESTINATION" : "SAMPLE DESTINATION"}</span><strong>${phase === 0 ? "Your library, considered." : item.destination.split("/").slice(0, -1).join(" / ")}</strong><span class="destination-path">${phase === 0 ? "Preview the path. Then make it happen." : item.destination}</span></div></div>
      <div class="showcase-action">${phase === 2 ? `<p role="status"><span>${check}</span> Sample complete. No files were moved.</p><button type="button" class="sample-reset" data-action="reset">Reset sample ↻</button>` : `<span class="sample-safety"><span aria-hidden="true">◇</span> ${phase === 0 ? "You approve every move." : "A preview. Never a surprise."}</span><button type="button" class="button primary sample-action" data-action="${phase === 0 ? "preview" : "organise"}">${phase === 0 ? "Preview sample plan" : "Simulate organisation"} ${arrow}</button>`}</div>`;
  }
  function click(event) {
    const collection = event.target.closest("[data-sample]");
    if (collection) {
      selected = Number(collection.dataset.sample);
      phase = 0;
      draw();
      return;
    }
    const action = event.target.closest("[data-action]")?.dataset.action;
    if (action) {
      phase = action === "preview" ? 1 : action === "organise" ? 2 : 0;
      draw();
      const next =
        phase === 2
          ? body.querySelector('[role="status"]')
          : body.querySelector("[data-action]");
      if (phase === 2) next.setAttribute("tabindex", "-1");
      next?.focus({ preventScroll: true });
    }
  }
  root.addEventListener("click", click);
  draw();
  return () => root.removeEventListener("click", click);
}
