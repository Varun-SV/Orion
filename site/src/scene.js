// A decorative orbital field. The organiser never depends on Canvas support.
export const sceneMarkup = () => `<div class="orbital-scene" aria-hidden="true">
  <svg class="orbital-fallback" viewBox="0 0 1200 800" preserveAspectRatio="xMidYMid slice"><defs><radialGradient id="orbit-glow"><stop stop-color="currentColor" stop-opacity=".14"/><stop offset="1" stop-color="currentColor" stop-opacity="0"/></radialGradient></defs><ellipse cx="830" cy="310" rx="440" ry="310" fill="url(#orbit-glow)"/><g transform="rotate(-24 830 310)" fill="none" stroke="currentColor"><ellipse cx="830" cy="310" rx="360" ry="130"/><ellipse cx="830" cy="310" rx="290" ry="104"/><ellipse cx="830" cy="310" rx="220" ry="79"/></g><g fill="currentColor"><circle cx="615" cy="230" r="3"/><circle cx="950" cy="150" r="4"/><circle cx="1050" cy="390" r="3"/><circle cx="830" cy="310" r="5"/></g></svg>
  <canvas class="orbital-canvas"></canvas>
</div>`;

export function mountScene(hero) {
  const canvas = hero.querySelector(".orbital-canvas");
  let ctx;
  try {
    ctx = canvas.getContext("2d");
  } catch {
    return () => {};
  }
  if (!ctx) return () => {};
  hero.querySelector(".orbital-scene").classList.add("has-canvas");
  const html = document.documentElement;
  const reduce = matchMedia("(prefers-reduced-motion: reduce)");
  const fine = matchMedia("(pointer: fine)");
  let width = 0,
    height = 0,
    frame = 0,
    time = 0,
    last = 0,
    visible = true;
  let pointerX = 0,
    pointerY = 0,
    accent,
    ink,
    dark;
  // Deterministic positions: stable through refreshes, no stored user data.
  const particles = Array.from({ length: 540 }, (_, i) => ({
    angle: i * 2.399963,
    radius: 0.34 + ((i * 97) % 541) / 780,
    depth: ((i * 53) % 107) / 107,
    size: i % 37 === 0 ? 2 : i % 7 === 0 ? 1.1 : 0.55,
  }));
  const allowed = () =>
    visible &&
    !document.hidden &&
    !reduce.matches &&
    html.dataset.motion === "running";
  const rgb = (color, alpha) => `rgb(${color} / ${alpha})`;
  function colors() {
    const style = getComputedStyle(html);
    const toRGB = (name) => {
      const value = style.getPropertyValue(name).trim();
      return [1, 3, 5]
        .map((index) => parseInt(value.slice(index, index + 2), 16))
        .join(" ");
    };
    accent = toRGB("--accent");
    ink = toRGB("--ink");
    dark = html.dataset.theme === "night";
  }
  function paint() {
    if (!width || !height) return;
    ctx.clearRect(0, 0, width, height);
    const mobile = width < 701;
    const cx = width * (mobile ? 0.66 : 0.72) + pointerX * 12;
    const cy = height * (mobile ? 0.24 : 0.32) + pointerY * 9;
    const radius = Math.min(width * (mobile ? 0.85 : 0.36), 510);
    const angle = -0.4,
      cosine = Math.cos(angle),
      sine = Math.sin(angle);
    const project = (theta, r, depth = 0) => {
      const x = Math.cos(theta) * r;
      const y = Math.sin(theta) * r * 0.38 + depth;
      return [cx + x * cosine - y * sine, cy + x * sine + y * cosine];
    };
    const glow = ctx.createRadialGradient(cx, cy, 0, cx, cy, radius * 1.3);
    glow.addColorStop(0, rgb(accent, dark ? 0.085 : 0.045));
    glow.addColorStop(0.6, rgb(accent, 0.025));
    glow.addColorStop(1, rgb(accent, 0));
    ctx.fillStyle = glow;
    ctx.fillRect(0, 0, width, height);
    // Faint stars outside the orbital disk.
    for (let i = 0; i < 75; i++) {
      const x = (((i * 137.5 + 17) % 1000) / 1000) * width;
      const y = (((i * 193 + 43) % 1100) / 1100) * height;
      ctx.fillStyle = rgb(ink, 0.12 + (i % 4) * 0.05);
      ctx.beginPath();
      ctx.arc(x, y, i % 9 === 0 ? 1.2 : 0.6, 0, Math.PI * 2);
      ctx.fill();
    }
    for (const scale of [0.48, 0.69, 0.9, 1.08]) {
      ctx.beginPath();
      for (let j = 0; j <= 180; j++) {
        const [x, y] = project((j / 180) * Math.PI * 2, radius * scale);
        if (j === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.strokeStyle = rgb(accent, scale === 0.69 ? 0.25 : 0.12);
      ctx.lineWidth = 0.65;
      ctx.stroke();
    }
    for (const p of particles) {
      const [x, y] = project(
        p.angle + time * (0.018 + p.depth * 0.015),
        radius * p.radius,
        (p.depth - 0.5) * 30,
      );
      const alpha = 0.12 + p.depth * (dark ? 0.55 : 0.4);
      ctx.fillStyle = rgb(p.size > 1.5 ? ink : accent, alpha);
      ctx.beginPath();
      ctx.arc(x, y, p.size, 0, Math.PI * 2);
      ctx.fill();
    }
    // Bright satellite packets and their orbital trails.
    for (let i = 0; i < 4; i++) {
      const theta = i * 1.65 + time * (0.11 + i * 0.013);
      const orbit = radius * [0.48, 0.69, 0.9, 1.08][i];
      const [x, y] = project(theta, orbit);
      ctx.beginPath();
      for (let j = 0; j < 18; j++) {
        const point = project(theta - j * 0.012, orbit);
        if (!j) ctx.moveTo(...point);
        else ctx.lineTo(...point);
      }
      ctx.strokeStyle = rgb(accent, 0.5);
      ctx.lineWidth = 1.2;
      ctx.stroke();
      const halo = ctx.createRadialGradient(x, y, 0, x, y, 13);
      halo.addColorStop(0, rgb(accent, 0.7));
      halo.addColorStop(1, rgb(accent, 0));
      ctx.fillStyle = halo;
      ctx.fillRect(x - 13, y - 13, 26, 26);
      ctx.fillStyle = rgb(ink, 0.95);
      ctx.beginPath();
      ctx.arc(x, y, 2, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.strokeStyle = rgb(accent, 0.6);
    ctx.lineWidth = 0.8;
    ctx.beginPath();
    ctx.moveTo(cx - 8, cy);
    ctx.lineTo(cx + 8, cy);
    ctx.moveTo(cx, cy - 8);
    ctx.lineTo(cx, cy + 8);
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(cx, cy, 19, 0, Math.PI * 2);
    ctx.strokeStyle = rgb(accent, 0.22);
    ctx.stroke();
  }
  function tick(timestamp) {
    frame = 0;
    if (!allowed()) return;
    if (timestamp - last >= 32) {
      time += Math.min((timestamp - last) / 1000, 0.05);
      last = timestamp;
      paint();
    }
    frame = requestAnimationFrame(tick);
  }
  function sync() {
    cancelAnimationFrame(frame);
    frame = 0;
    colors();
    paint();
    last = performance.now();
    if (allowed()) frame = requestAnimationFrame(tick);
  }
  function resize() {
    const box = hero.getBoundingClientRect();
    width = box.width;
    height = box.height;
    const ratio = Math.min(devicePixelRatio || 1, 1.75);
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    sync();
  }
  function pointer(event) {
    if (!fine.matches || !allowed()) return;
    const box = hero.getBoundingClientRect();
    pointerX = (event.clientX - box.left) / width - 0.5;
    pointerY = (event.clientY - box.top) / height - 0.5;
  }
  function leave() {
    pointerX = 0;
    pointerY = 0;
  }
  const observer = new MutationObserver(sync);
  observer.observe(html, {
    attributes: true,
    attributeFilter: ["data-theme", "data-motion"],
  });
  const visibility = new IntersectionObserver(([entry]) => {
    visible = entry.isIntersecting;
    sync();
  });
  visibility.observe(hero);
  const sizing = new ResizeObserver(resize);
  sizing.observe(hero);
  hero.addEventListener("pointermove", pointer, { passive: true });
  hero.addEventListener("pointerleave", leave, { passive: true });
  document.addEventListener("visibilitychange", sync);
  reduce.addEventListener("change", sync);
  resize();
  return () => {
    cancelAnimationFrame(frame);
    observer.disconnect();
    visibility.disconnect();
    sizing.disconnect();
    hero.removeEventListener("pointermove", pointer);
    hero.removeEventListener("pointerleave", leave);
    document.removeEventListener("visibilitychange", sync);
    reduce.removeEventListener("change", sync);
  };
}
