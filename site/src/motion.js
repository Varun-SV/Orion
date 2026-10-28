export function setupMotion() {
  const html = document.documentElement;
  const reduced = matchMedia("(prefers-reduced-motion: reduce)");
  const button = document.querySelector("#motion-toggle");
  let paused = false,
    observer,
    ambientObserver,
    frame = 0,
    transition;
  try {
    paused = localStorage.getItem("orion-site-motion") === "paused";
  } catch {}
  const allowed = () => !paused && !reduced.matches;
  function sync() {
    if (!allowed()) transition?.skipTransition?.();
    html.dataset.motion = paused
      ? "paused"
      : reduced.matches
        ? "reduced"
        : "running";
    button.setAttribute(
      "aria-label",
      paused ? "Resume animations" : "Pause animations",
    );
    button.setAttribute("aria-pressed", String(paused));
    button.querySelector("[data-motion-icon]").textContent = paused ? "▷" : "Ⅱ";
    button.title = reduced.matches
      ? "Motion follows your device preference"
      : paused
        ? "Resume animations"
        : "Pause animations";
    refresh();
  }
  function update() {
    frame = 0;
    const total = document.documentElement.scrollHeight - innerHeight;
    html.style.setProperty(
      "--scroll-progress",
      String(total > 0 ? scrollY / total : 0),
    );
    const parallax =
      allowed() && innerWidth > 760 ? Math.min(scrollY * 0.11, 80) : 0;
    html.style.setProperty("--parallax", `${parallax}px`);
  }
  function onScroll() {
    if (!frame) frame = requestAnimationFrame(update);
  }
  function refresh() {
    observer?.disconnect();
    ambientObserver?.disconnect();
    const nodes = document.querySelectorAll("main .reveal");
    if (allowed() && "IntersectionObserver" in window) {
      observer = new IntersectionObserver(
        (entries) =>
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              entry.target.classList.add("is-visible");
              observer.unobserve(entry.target);
            }
          }),
        { threshold: 0.07, rootMargin: "0px 0px -24px 0px" },
      );
      nodes.forEach((node) => {
        node.classList.add("will-reveal");
        if (node.getBoundingClientRect().top < innerHeight * 0.95)
          node.classList.add("is-visible");
        else observer.observe(node);
      });
      ambientObserver = new IntersectionObserver((entries) =>
        entries.forEach((entry) =>
          entry.target.classList.toggle("is-offscreen", !entry.isIntersecting),
        ),
      );
      document
        .querySelectorAll(
          ".orbit-decoration, .headline-star, .transfer-visual, .scroll-invitation",
        )
        .forEach((node) => ambientObserver.observe(node));
    } else nodes.forEach((node) => node.classList.add("is-visible"));
    update();
  }
  button.addEventListener("click", () => {
    paused = !paused;
    try {
      localStorage.setItem("orion-site-motion", paused ? "paused" : "running");
    } catch {}
    sync();
  });
  reduced.addEventListener("change", sync);
  addEventListener("scroll", onScroll, { passive: true });
  addEventListener("resize", onScroll, { passive: true });
  document.addEventListener("visibilitychange", () => {
    html.dataset.visibility = document.hidden ? "hidden" : "visible";
  });
  sync();
  return {
    refresh,
    transition(draw) {
      transition?.skipTransition?.();
      if (allowed() && document.startViewTransition) {
        transition = document.startViewTransition(draw);
        transition.ready.catch(() => {});
        transition.finished.catch(() => {});
      } else draw();
    },
  };
}
