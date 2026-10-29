import "./gallery.css";
import { collections } from "./collections";
import { mediaArtwork } from "./media-art";

function featuredMarkup(index) {
  const item = collections[index];
  const artwork = mediaArtwork(index);
  const fileName = item.source.split("/").at(-1);
  return `<div class="gallery-feature" data-gallery-feature data-index="${index}">
    <div class="gallery-artwork" role="img" aria-label="Original illustrated cover for ${item.title}">${artwork}<span class="gallery-artwork-index" aria-hidden="true">${item.glyph} / 07</span></div>
    <div class="gallery-feature-copy"><div class="gallery-title-line"><div><span class="gallery-eyebrow">${item.kind.toUpperCase()} · FICTIONAL SAMPLE</span><h3 data-gallery-title>${item.title}</h3><p class="gallery-description" data-gallery-description>${item.detail}</p></div><span class="gallery-year">${item.year}</span></div>
      <div class="gallery-file-journey"><div><span>FROM YOUR FILES</span><strong data-gallery-source>${fileName}</strong></div><span class="gallery-journey-arrow" aria-hidden="true">⟶</span><div><span>TO YOUR LIBRARY</span><strong data-gallery-destination>${item.destination}</strong></div></div>
      <p class="gallery-disclosure"><i aria-hidden="true"></i> FICTIONAL SAMPLE · No files are moved.</p>
      <a class="gallery-open-link" href="#demo" data-demo-select="${index}">Explore ${item.name}<span aria-hidden="true">↗</span></a>
    </div>
  </div>`;
}

export function galleryMarkup() {
  return `<section class="collection-gallery reveal" aria-labelledby="gallery-heading" data-gallery-index="0">
    <div class="gallery-heading-block"><p class="gallery-kicker"><span></span> A PLACE FOR EVERY PASSION</p><h2 id="gallery-heading">For every<br><em>obsession.</em></h2><p class="gallery-intro">Seven collections, each with its own character. Pick a shelf and see where a file finds its place.</p>
      <div class="gallery-collection-list" role="group" aria-label="Explore collections">${collections
        .map(
          (item, index) =>
            `<button type="button" data-gallery-select="${index}" aria-label="${item.name}" aria-pressed="${index === 0}"><span aria-hidden="true">${item.glyph}</span><strong>${item.name}</strong><span class="gallery-select-arrow" aria-hidden="true">↗</span></button>`,
        )
        .join("")}</div>
    </div>
    <div class="gallery-stage" aria-live="polite" aria-atomic="true">${featuredMarkup(0)}</div>
  </section>`;
}

export function mountGallery(rootElement) {
  const root = rootElement.matches?.(".collection-gallery")
    ? rootElement
    : rootElement.querySelector(".collection-gallery");
  if (!root) return () => {};

  function select(index) {
    if (!Number.isInteger(index) || index < 0 || index >= collections.length)
      return;
    root.dataset.galleryIndex = String(index);
    root.querySelectorAll("[data-gallery-select]").forEach((button) => {
      button.setAttribute(
        "aria-pressed",
        String(Number(button.dataset.gallerySelect) === index),
      );
    });
    root.querySelector("[data-gallery-feature]").outerHTML =
      featuredMarkup(index);
  }

  function onClick(event) {
    const button = event.target.closest("[data-gallery-select]");
    if (button && root.contains(button))
      select(Number(button.dataset.gallerySelect));
  }

  root.addEventListener("click", onClick);
  return () => root.removeEventListener("click", onClick);
}
