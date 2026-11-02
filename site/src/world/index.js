import { PerspectiveCamera, Scene, Vector3, WebGLRenderer } from "three";
import { cameraPose, damp, framing, worldState } from "../director.js";
import { TIERS, createGovernor, initialTier } from "../quality.js";
import {
  createBackdrop,
  createFiles,
  createLines,
  createNebula,
  createRing,
  createStars,
} from "./layers.js";

const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
const smooth = (a, b, v) => {
  const t = clamp((v - a) / (b - a));
  return t * t * (3 - 2 * t);
};
const INTRO_SECONDS = 4.6;

// Creates the 3D world, or returns null when WebGL is unavailable so the page keeps its static form.
export function createWorld(canvas, options = {}) {
  const {
    onProject = () => {},
    onTier = () => {},
    onLost = () => {},
    onRestored = () => {},
  } = options;
  const nav = navigator;
  const coarse = matchMedia("(pointer: coarse)").matches;
  const start = initialTier({
    coarsePointer: coarse,
    saveData: Boolean(nav.connection?.saveData),
    cores: nav.hardwareConcurrency || 8,
    memory: nav.deviceMemory || 8,
  });

  // Ask for the context ourselves so an unsupported browser falls back quietly, without
  // three.js writing an error to the console.
  let gl = null;
  try {
    gl = canvas.getContext("webgl2", {
      antialias: false,
      alpha: false,
      powerPreference: "high-performance",
    });
  } catch {
    gl = null;
  }
  if (!gl) return null;
  let renderer;
  try {
    renderer = new WebGLRenderer({
      canvas,
      context: gl,
      antialias: false,
      alpha: false,
    });
  } catch {
    return null;
  }
  renderer.setClearColor(0x02040a, 1);

  const governor = createGovernor({ start });
  let tier = TIERS[start];
  const maxRatio = () => Math.min(devicePixelRatio || 1, coarse ? 1.5 : 2);
  const pixelRatio = () => Math.max(0.5, maxRatio() * tier.scale);

  const scene = new Scene();
  const camera = new PerspectiveCamera(46, 1, 0.5, 1400);
  const pr = pixelRatio();
  const backdrop = createBackdrop(7000, pr);
  const { points: starPoints, stars } = createStars(pr);
  const lines = createLines(pr);
  const nebula = createNebula(1100, pr);
  const files = createFiles(12000, pr);
  const ring = createRing(pr);
  scene.add(backdrop, nebula, files, ring, lines, starPoints);
  const materials = [backdrop, starPoints, lines, nebula, files, ring].map(
    (o) => o.material,
  );
  const total = { backdrop: 7000, nebula: 1100, files: 12000 };

  const byCollection = [];
  for (const s of stars) if (s.collection >= 0) byCollection[s.collection] = s;
  const state = {};
  const pose = { p: [0, 0, 0], l: [0, 0, 0], fov: 46 };
  const look = new Vector3();
  const tmp = new Vector3();
  const projected = new Float32Array(stars.length * 3);
  let target = { u: 0, collection: -1, index: 0 };
  let u = 0,
    time = 0,
    intro = 0,
    hover = -1,
    last = 0,
    raf = 0,
    running = false,
    visible = !document.hidden,
    frames = 0,
    msSum = 0,
    width = 0,
    height = 0,
    pointerX = 0,
    pointerY = 0,
    smoothX = 0,
    smoothY = 0,
    focusX = byCollection[0].x,
    focusY = byCollection[0].y,
    focusIndex = 0,
    lostFlag = false;
  let motion = "running"; // running | paused | reduced

  const setUniform = (name, value) => {
    for (const m of materials)
      if (m.uniforms[name]) m.uniforms[name].value = value;
  };

  function applyTier() {
    renderer.setPixelRatio(pixelRatio());
    backdrop.geometry.setDrawRange(
      0,
      Math.floor(total.backdrop * (tier.scale >= 1 ? 1 : 0.7)),
    );
    nebula.geometry.setDrawRange(0, Math.floor(total.nebula * tier.nebula));
    files.geometry.setDrawRange(0, Math.floor(total.files * tier.particles));
    resize(true);
  }

  function resize(force) {
    const w = canvas.clientWidth || innerWidth,
      h = canvas.clientHeight || innerHeight;
    if (!force && w === width && h === height) return;
    width = w;
    height = h;
    renderer.setSize(w, h, false);
    // Point sizes follow the screen height, so a short landscape view is not over-exposed.
    setUniform("uPR", renderer.getPixelRatio() * clamp(h / 900, 0.5, 1.3));
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    invalidate();
  }

  function frame(now) {
    raf = 0;
    if (lostFlag) return;
    const dt = last ? Math.min((now - last) / 1000, 0.1) : 0;
    const rawDt = last ? now - last : 0;
    last = now;
    const live = motion === "running";
    if (live) {
      time += dt;
      // The opening runs on the wall clock so slow frames cannot stretch it.
      intro = clamp(intro + Math.min(rawDt / 1000, 0.5) / INTRO_SECONDS);
    } else if (motion === "reduced") {
      intro = 1;
    }
    // Camera follower: damped with the wheel, cut straight to the chapter for reduced motion.
    const goal = motion === "reduced" ? target.index : target.u;
    u = live && frames > 0 ? damp(u, goal, dt, 5.5) : goal;
    if (Math.abs(goal - u) < 0.0005) u = goal;
    smoothX += (pointerX - smoothX) * (1 - Math.exp(-dt * 4));
    smoothY += (pointerY - smoothY) * (1 - Math.exp(-dt * 4));

    worldState(u, state);
    cameraPose(u, pose);
    const aspect = camera.aspect;
    const f = framing(aspect, u);
    // The focus follows the chosen star smoothly, so changing collection glides rather than cuts.
    const chosen =
      target.collection >= 0 ? byCollection[target.collection] : null;
    if (chosen) {
      const follow = live && frames > 0;
      focusX = follow ? damp(focusX, chosen.x, dt, 6) : chosen.x;
      focusY = follow ? damp(focusY, chosen.y, dt, 6) : chosen.y;
      focusIndex = target.collection;
    }
    const fa = state.focus;
    look.set(
      pose.l[0] + (focusX - pose.l[0]) * 0.55 * fa,
      pose.l[1] + (focusY - pose.l[1]) * 0.55 * fa,
      pose.l[2],
    );
    tmp.set(
      pose.p[0] + focusX * 0.45 * fa,
      pose.p[1] + focusY * 0.45 * fa,
      pose.p[2],
    );
    tmp.sub(look).multiplyScalar(f.back).add(look);
    const parallax = live && !coarse ? 1.4 : 0;
    camera.position.set(
      tmp.x + f.shiftX + smoothX * parallax,
      tmp.y + f.shiftY - smoothY * parallax * 0.7,
      tmp.z,
    );
    look.x += f.shiftX;
    look.y += f.shiftY;
    camera.lookAt(look);
    if (Math.abs(camera.fov - pose.fov) > 0.01) {
      camera.fov = pose.fov;
      camera.updateProjectionMatrix();
    }

    const draw = smooth(0.32, 0.92, intro);
    setUniform("uTime", time);
    setUniform("uIntro", intro);
    setUniform("uDraw", draw);
    setUniform("uDim", clamp(state.dim, 0, 1));
    setUniform("uFocus", focusIndex);
    setUniform("uFocusAmt", state.focus);
    setUniform("uHover", hover);
    setUniform("uAmount", state.nebula * smooth(0.05, 0.7, intro));
    setUniform("uOrder", state.order);
    setUniform("uRewind", state.rewind);
    setUniform("uVerify", state.verify);

    camera.updateMatrixWorld();
    for (let i = 0; i < stars.length; i++) {
      tmp.set(stars[i].x, stars[i].y, 0).project(camera);
      projected[i * 3] = (tmp.x * 0.5 + 0.5) * width;
      projected[i * 3 + 1] = (-tmp.y * 0.5 + 0.5) * height;
      projected[i * 3 + 2] = tmp.z < 1 ? 1 : 0;
    }
    const shown = smooth(0.75, 1, intro);
    onProject(
      projected,
      shown * (1 - smooth(1.45, 1.8, u)),
      shown * (1 - smooth(1.85, 2.1, u)),
      stars,
    );

    renderer.render(scene, camera);
    frames++;
    if (live && rawDt > 0) {
      msSum += rawDt;
      const next = governor.sample(rawDt);
      if (next !== null) {
        tier = TIERS[next];
        applyTier();
        onTier(tier, next);
      }
      if (frames % 10 === 0) {
        options.onStats?.({ frames, ms: msSum / 10, tier: governor.tier });
        msSum = 0;
      }
    }
    if (running && live && visible) schedule();
    else if (Math.abs(goal - u) > 0.0005) schedule();
  }

  function schedule() {
    if (!raf && !lostFlag) raf = requestAnimationFrame(frame);
  }
  // Render a single frame (scroll, resize, hover, motion change) when the loop is not running.
  function invalidate() {
    schedule();
  }

  const onVisibility = () => {
    visible = !document.hidden;
    last = 0;
    if (visible) schedule();
  };
  const onResize = () => resize(false);
  const onPointer = (event) => {
    pointerX = (event.clientX / innerWidth) * 2 - 1;
    pointerY = (event.clientY / innerHeight) * 2 - 1;
  };
  const onLostEvent = (event) => {
    event.preventDefault();
    lostFlag = true;
    cancelAnimationFrame(raf);
    raf = 0;
    onLost();
  };
  const onRestoredEvent = () => {
    lostFlag = false;
    last = 0;
    applyTier();
    onRestored();
    schedule();
  };
  document.addEventListener("visibilitychange", onVisibility);
  addEventListener("resize", onResize, { passive: true });
  addEventListener("pointermove", onPointer, { passive: true });
  canvas.addEventListener("webglcontextlost", onLostEvent);
  canvas.addEventListener("webglcontextrestored", onRestoredEvent);

  applyTier();
  return {
    tier: () => governor.tier,
    // info = { u, index, collection } from the page's scroll handler.
    setScroll(info) {
      target = info;
      invalidate();
    },
    setHover(index) {
      hover = index;
      invalidate();
    },
    setMotion(mode) {
      if (mode === motion) return;
      motion = mode;
      last = 0;
      if (mode === "reduced") intro = 1;
      invalidate();
    },
    start() {
      running = true;
      schedule();
    },
    stop() {
      running = false;
    },
    resize: () => resize(true),
    dispose() {
      running = false;
      cancelAnimationFrame(raf);
      document.removeEventListener("visibilitychange", onVisibility);
      removeEventListener("resize", onResize);
      removeEventListener("pointermove", onPointer);
      canvas.removeEventListener("webglcontextlost", onLostEvent);
      canvas.removeEventListener("webglcontextrestored", onRestoredEvent);
      for (const o of [backdrop, starPoints, lines, nebula, files, ring]) {
        o.geometry.dispose();
        o.material.dispose();
      }
      renderer.dispose();
    },
  };
}
