// Pure scroll director. No DOM and no three.js: it turns scroll position into a chapter,
// a camera pose and the state of the world, so the whole flight can be unit-tested.
export const CHAPTERS = [
  "landing",
  "collections",
  "scan",
  "preview",
  "recover",
  "try",
  "connect",
];
const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
const smooth = (a, b, v) => {
  const t = clamp((v - a) / (b - a));
  return t * t * (3 - 2 * t);
};
const smoother = (t) => t * t * t * (t * (t * 6 - 15) + 10);

// Frame-rate independent exponential follower: the same blend per second at any frame rate.
export const damp = (current, target, dt, rate) =>
  current + (target - current) * (1 - Math.exp(-Math.max(0, dt) * rate));

// Camera holds on the chapter for its first third, then travels to the next anchor.
export const holdEase = (local) => smoother(clamp((local - 0.3) / 0.7));

// tops has one entry per chapter plus the document end. Returns the chapter, progress through
// its scrollable travel (height minus one viewport) and the continuous flight coordinate u.
export function locate(tops, scrollY, viewportH) {
  const n = tops.length - 1;
  let index = 0;
  for (let i = 0; i < n; i++) if (tops[i] <= scrollY + 0.5) index = i;
  const travel = Math.max(1, tops[index + 1] - tops[index] - viewportH);
  const local = index === n - 1 ? 0 : clamp((scrollY - tops[index]) / travel);
  return { index, local, u: index + holdEase(local) };
}

// Collection under the camera during the "collections" chapter, else -1.
export function activeCollection(index, local, count = 7) {
  return index === 1
    ? Math.min(count - 1, Math.floor(clamp(local) * count))
    : -1;
}

// Camera anchors, one per chapter. Orion's stars span about 18 x 38 world units around the origin.
export const ANCHORS = [
  { p: [0, 2, 84], l: [0, 0, 0], fov: 46 },
  { p: [0, 1, 50], l: [0, 0, 0], fov: 50 },
  { p: [5, -11, 24], l: [1, -10, -6], fov: 58 },
  { p: [0, -9, 30], l: [0, -9, 0], fov: 52 },
  { p: [-7, -8, 25], l: [0, -9, 0], fov: 54 },
  { p: [0, 0, 96], l: [0, 0, 0], fov: 46 },
  { p: [0, 3, 74], l: [0, 0, 0], fov: 48 },
];

function catmull(p0, p1, p2, p3, t) {
  const t2 = t * t,
    t3 = t2 * t;
  return (
    0.5 *
    (2 * p1 +
      (p2 - p0) * t +
      (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 +
      (3 * p1 - p0 - 3 * p2 + p3) * t3)
  );
}

export function cameraPose(u, out = {}) {
  const last = ANCHORS.length - 1;
  const x = clamp(u, 0, last);
  const i = Math.min(last - 1, Math.floor(x));
  const t = x - i;
  const a0 = ANCHORS[Math.max(0, i - 1)],
    a1 = ANCHORS[i],
    a2 = ANCHORS[i + 1],
    a3 = ANCHORS[Math.min(last, i + 2)];
  out.p = out.p || [0, 0, 0];
  out.l = out.l || [0, 0, 0];
  for (let k = 0; k < 3; k++) {
    out.p[k] = catmull(a0.p[k], a1.p[k], a2.p[k], a3.p[k], t);
    out.l[k] = catmull(a0.l[k], a1.l[k], a2.l[k], a3.l[k], t);
  }
  out.fov = catmull(a0.fov, a1.fov, a2.fov, a3.fov, t);
  return out;
}

// Keeps the subject comfortably framed on any screen: pulls back on portrait screens and, on
// wide screens in the opening, slides the constellation right so the headline has room.
export function framing(aspect, u) {
  const portrait = aspect < 1;
  const back = portrait ? Math.min(1.9, Math.pow(1 / aspect, 0.65)) : 1;
  const opening = 1 - smooth(0, 0.85, u);
  return {
    back,
    shiftX: portrait ? 0 : -20 * opening * clamp((aspect - 1) / 0.8),
    // On a portrait screen the text sits in the lower half, so the scene stays in the upper half
    // all the way through the text chapters, and relaxes only for the sample and install pages.
    shiftY: portrait
      ? -(14 + 26 * (1 - aspect)) *
        (opening + (1 - opening) * 0.62 * (1 - smooth(4.8, 5.4, u)))
      : 0,
  };
}

// State of the world for the flight coordinate u. Every value is continuous in u.
export function worldState(u, out = {}) {
  out.focus = smooth(0.55, 0.95, u) * (1 - smooth(1.9, 2.2, u));
  out.nebula = 0.35 + 0.65 * smooth(1.2, 2.1, u) * (1 - 0.35 * smooth(5, 6, u));
  const settle = smooth(2.45, 3.45, u);
  out.rewind = smooth(3.9, 4.4, u) * (1 - smooth(4.6, 5.0, u));
  out.order = clamp(settle - 0.9 * out.rewind, 0, 1);
  out.verify = smooth(4.1, 4.5, u) * (1 - smooth(4.7, 5.0, u));
  out.dim = 0.5 * smooth(4.7, 5.2, u) - 0.15 * smooth(5.6, 6, u);
  return out;
}
