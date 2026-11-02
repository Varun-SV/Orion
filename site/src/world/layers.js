import {
  AdditiveBlending,
  BufferAttribute,
  BufferGeometry,
  Color,
  LineSegments,
  Points,
  ShaderMaterial,
} from "three";
import { rng } from "./random.js";
import { EDGES, starPositions, nebulaPosition } from "../stars-data.js";

const additive = {
  transparent: true,
  depthWrite: false,
  depthTest: false,
  blending: AdditiveBlending,
};
const attr = (array, size) => new BufferAttribute(array, size);
const shared = (pr) => ({
  uTime: { value: 0 },
  uPR: { value: pr },
  uDim: { value: 0 },
});

// Soft hash used by several fragment shaders.
const NOISE = `
float hash(vec2 p){ p = fract(p*vec2(123.34, 456.21)); p += dot(p, p+45.32); return fract(p.x*p.y); }
float vnoise(vec2 p){ vec2 i = floor(p), f = fract(p); f = f*f*(3.-2.*f);
  return mix(mix(hash(i), hash(i+vec2(1,0)), f.x), mix(hash(i+vec2(0,1)), hash(i+vec2(1,1)), f.x), f.y); }`;

/* ---- distant stars and the faint band of the galaxy ---- */
export function createBackdrop(count, pr) {
  const r = rng(11);
  const pos = new Float32Array(count * 3),
    size = new Float32Array(count),
    tint = new Float32Array(count * 3),
    phase = new Float32Array(count);
  for (let i = 0; i < count; i++) {
    const band = i < count * 0.38;
    let x = r.gauss(),
      y = band ? r.gauss() * 0.16 : r.gauss(),
      z = r.gauss();
    if (!band) {
      x = r() * 2 - 1;
      y = r() * 2 - 1;
      z = r() * 2 - 1;
    }
    // Tilt the band so it crosses behind the constellation.
    if (band) {
      const c = Math.cos(0.5),
        s = Math.sin(0.5);
      const ny = y * c - z * s;
      z = y * s + z * c;
      y = ny;
    }
    const len = Math.hypot(x, y, z) || 1;
    const dist = 420 + r() * 120;
    pos.set([(x / len) * dist, (y / len) * dist, (z / len) * dist - 60], i * 3);
    const bright = r() ** 6;
    size[i] = 0.7 + bright * 2.6 + (band ? 0 : 0.2);
    const warm = r();
    tint.set(
      warm < 0.2
        ? [1, 0.82, 0.62]
        : warm < 0.55
          ? [0.82, 0.88, 1]
          : [0.66, 0.78, 1],
      i * 3,
    );
    phase[i] = r() * 6.283;
  }
  const g = new BufferGeometry();
  g.setAttribute("position", attr(pos, 3));
  g.setAttribute("aSize", attr(size, 1));
  g.setAttribute("aTint", attr(tint, 3));
  g.setAttribute("aPhase", attr(phase, 1));
  const m = new ShaderMaterial({
    ...additive,
    uniforms: { ...shared(pr), uIntro: { value: 0 } },
    vertexShader: `attribute float aSize, aPhase; attribute vec3 aTint; uniform float uTime, uPR, uIntro; varying vec3 vC; varying float vA;
      void main(){ vC = aTint; float tw = .72 + .28*sin(uTime*(.6+aPhase*.15) + aPhase*9.);
        vA = tw * (.25 + .75*smoothstep(0., 1., uIntro));
        gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.); gl_PointSize = aSize*uPR*(.85+.15*tw); }`,
    fragmentShader: `varying vec3 vC; varying float vA; uniform float uDim;
      void main(){ float d = length(gl_PointCoord-.5); if(d>.5) discard; float k = pow(smoothstep(.5, 0., d), 1.8);
        gl_FragColor = vec4(vC, k*vA*(1.-uDim*.35)*.8); }`,
  });
  const points = new Points(g, m);
  points.frustumCulled = false;
  return points;
}

/* ---- the principal stars: halo, core and diffraction spikes ---- */
export function createStars(pr) {
  const stars = starPositions();
  const pos = new Float32Array(stars.length * 3),
    size = new Float32Array(stars.length),
    tint = new Float32Array(stars.length * 3),
    idx = new Float32Array(stars.length),
    delay = new Float32Array(stars.length);
  stars.forEach((s, i) => {
    pos.set([s.x, s.y, 0], i * 3);
    size[i] = 22 + (3.6 - s.mag) * 12;
    tint.set(s.tint, i * 3);
    idx[i] = s.collection;
    delay[i] = 0.1 + (i / stars.length) * 0.45;
  });
  const g = new BufferGeometry();
  g.setAttribute("position", attr(pos, 3));
  g.setAttribute("aSize", attr(size, 1));
  g.setAttribute("aTint", attr(tint, 3));
  g.setAttribute("aIdx", attr(idx, 1));
  g.setAttribute("aDelay", attr(delay, 1));
  const m = new ShaderMaterial({
    ...additive,
    uniforms: {
      ...shared(pr),
      uIntro: { value: 0 },
      uFocus: { value: -1 },
      uFocusAmt: { value: 0 },
      uHover: { value: -1 },
    },
    vertexShader: `attribute float aSize, aIdx, aDelay; attribute vec3 aTint; uniform float uTime, uPR, uIntro, uFocus, uFocusAmt, uHover;
      varying vec3 vC; varying float vA, vBoost;
      void main(){ vec4 mv = modelViewMatrix*vec4(position,1.); gl_Position = projectionMatrix*mv;
        float on = smoothstep(aDelay, aDelay+.22, uIntro);
        float f = (aIdx>-.5 && abs(aIdx-uFocus)<.5) ? uFocusAmt : 0.;
        float h = (aIdx>-.5 && abs(aIdx-uHover)<.5) ? 1. : 0.;
        float pulse = .5+.5*sin(uTime*2.2+aIdx);
        vBoost = max(f*(.7+.3*pulse), h*.8);
        vC = aTint; vA = on*(.8+.2*sin(uTime*1.1+aDelay*20.));
        gl_PointSize = aSize*uPR*(70./-mv.z)*(1.+vBoost*.9)*(.35+.65*on); }`,
    fragmentShader: `varying vec3 vC; varying float vA, vBoost; uniform float uDim;
      void main(){ vec2 p = gl_PointCoord-.5; float d = length(p)*2.;
        float core = exp(-d*d*38.); float halo = exp(-d*5.5)*.55*(1.-smoothstep(.85,1.,d));
        float spike = (exp(-abs(p.x)*95.)*exp(-abs(p.y)*5.5) + exp(-abs(p.y)*95.)*exp(-abs(p.x)*5.5))*.5*(1.-smoothstep(.3,1.,d));
        float a = (core*1.6 + halo + spike*(.7+vBoost)) * vA;
        vec3 c = mix(vC, vec3(1.), core*.85);
        gl_FragColor = vec4(c*(1.+vBoost*.7), a*(1.-uDim*.2)); }`,
  });
  const points = new Points(g, m);
  points.frustumCulled = false;
  return { points, stars };
}

/* ---- the constellation figure, drawn on by uDraw ---- */
export function createLines(pr) {
  const stars = starPositions();
  const pos = new Float32Array(EDGES.length * 6),
    t = new Float32Array(EDGES.length * 2);
  EDGES.forEach(([a, b], k) => {
    pos.set([stars[a].x, stars[a].y, 0, stars[b].x, stars[b].y, 0], k * 6);
    t[k * 2] = k / EDGES.length;
    t[k * 2 + 1] = (k + 1) / EDGES.length;
  });
  const g = new BufferGeometry();
  g.setAttribute("position", attr(pos, 3));
  g.setAttribute("aT", attr(t, 1));
  const m = new ShaderMaterial({
    ...additive,
    uniforms: {
      ...shared(pr),
      uDraw: { value: 0 },
      uColor: { value: new Color("#8fd3ff") },
    },
    vertexShader: `attribute float aT; varying float vT; void main(){ vT = aT; gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.); }`,
    fragmentShader: `uniform float uDraw, uTime, uDim; uniform vec3 uColor; varying float vT;
      void main(){ float shown = smoothstep(vT-.002, vT+.03, uDraw*1.04);
        float pulse = pow(.5+.5*sin(vT*55.-uTime*1.6), 10.);
        gl_FragColor = vec4(uColor, shown*(.34+.5*pulse)*(1.-uDim*.4)); }`,
  });
  const lines = new LineSegments(g, m);
  lines.frustumCulled = false;
  return lines;
}

/* ---- the Orion Nebula: layered, softly noisy sprites ---- */
export function createNebula(count, pr) {
  const r = rng(42);
  const c = nebulaPosition();
  const lobes = [
    [0, 0, 0, 1],
    [-5, 3, -3, 0.8],
    [6, -2, 2, 0.7],
    [-2, -6, -2, 0.7],
    [4, 6, -6, 0.6],
  ];
  const pos = new Float32Array(count * 3),
    size = new Float32Array(count),
    col = new Float32Array(count * 3),
    seed = new Float32Array(count),
    hot = new Float32Array(count);
  const palette = [
    [0.1, 0.62, 0.74],
    [0.25, 0.4, 0.95],
    [0.9, 0.28, 0.55],
    [0.98, 0.62, 0.3],
    [0.45, 0.25, 0.8],
  ];
  for (let i = 0; i < count; i++) {
    const lobe = lobes[Math.floor(r() * lobes.length)];
    const spread = 6.5 * lobe[3];
    const x = c.x + lobe[0] + r.gauss() * spread,
      y = c.y + lobe[1] + r.gauss() * spread * 0.8,
      z = lobe[2] + r.gauss() * spread * 0.6;
    pos.set([x, y, z], i * 3);
    const dist = Math.hypot(x - c.x, y - c.y) / 14;
    const pick = palette[Math.floor(r() * (dist < 0.35 ? 3 : palette.length))];
    const core = 1 - Math.min(1, dist);
    const k = 0.8 + core * 0.25;
    col.set([pick[0] * k, pick[1] * k, pick[2] * k], i * 3);
    size[i] = 26 + r() * 70 + core * 12;
    seed[i] = r() * 100;
    hot[i] = i % 23 === 0 ? 1 : 0;
  }
  const g = new BufferGeometry();
  g.setAttribute("position", attr(pos, 3));
  g.setAttribute("aSize", attr(size, 1));
  g.setAttribute("aColor", attr(col, 3));
  g.setAttribute("aSeed", attr(seed, 1));
  g.setAttribute("aHot", attr(hot, 1));
  const m = new ShaderMaterial({
    ...additive,
    uniforms: {
      ...shared(pr),
      uAmount: { value: 0.4 },
      uCenter: { value: [c.x, c.y] },
    },
    vertexShader: `attribute float aSize, aSeed, aHot; attribute vec3 aColor; uniform float uTime, uPR, uAmount; uniform vec2 uCenter;
      varying vec3 vC; varying float vSeed, vHot, vA;
      void main(){ vec3 p = position; vec2 q = p.xy-uCenter; float a = uTime*.025*(1.+aSeed*.004); float s = sin(a), c = cos(a);
        p.xy = uCenter + vec2(q.x*c-q.y*s, q.x*s+q.y*c);
        vec4 mv = modelViewMatrix*vec4(p,1.); gl_Position = projectionMatrix*mv;
        vC = aColor; vSeed = aSeed; vHot = aHot; vA = uAmount;
        float sz = aHot>.5 ? 7. : aSize*(70./-mv.z)*3.2;
        gl_PointSize = min(sz*uPR, 190.*uPR); }`,
    fragmentShader: `${NOISE}
      varying vec3 vC; varying float vSeed, vHot, vA; uniform float uDim, uTime;
      void main(){ vec2 p = gl_PointCoord-.5; float d = length(p)*2.; if(d>1.) discard;
        if(vHot>.5){ float k = exp(-d*d*9.); gl_FragColor = vec4(vec3(.85,.92,1.)*k, k*vA*.9); return; }
        float n = vnoise(p*5.+vSeed) *.65 + vnoise(p*11.-vSeed*1.3+uTime*.015)*.35;
        float fall = pow(1.-d, 1.7);
        float a = fall*(.35+.65*n)*.085*vA*(1.-uDim*.25);
        gl_FragColor = vec4(vC, a); }`,
  });
  const pts = new Points(g, m);
  pts.frustumCulled = false;
  return pts;
}

/* ---- files: scattered dust that settles into a tidy lattice ---- */
const LANES = 7;
export function createFiles(count, pr) {
  const r = rng(77);
  const c = nebulaPosition();
  const COLS = 96;
  const per = LANES * COLS;
  const pos = new Float32Array(count * 3), // lattice target
    swirl = new Float32Array(count * 4), // radius, angle, z, speed
    meta = new Float32Array(count * 3), // lane, delay, size
    col = new Float32Array(count * 3);
  const hues = [
    [0.4, 0.85, 0.95],
    [0.55, 0.65, 1],
    [0.95, 0.55, 0.75],
    [0.98, 0.78, 0.45],
    [0.6, 0.95, 0.7],
    [0.95, 0.5, 0.45],
    [0.8, 0.7, 1],
  ];
  for (let i = 0; i < count; i++) {
    const lane = i % LANES;
    const slot = Math.floor(i / LANES);
    const column = slot % COLS;
    const layer = Math.floor(slot / COLS);
    pos.set(
      [
        c.x - 16 + (column / (COLS - 1)) * 32,
        c.y + 2.5 - lane * 1.5 + (layer % 2) * 0.12,
        -layer * 0.42 + 1.5,
      ],
      i * 3,
    );
    const rad = 1.5 + r() ** 0.7 * 15;
    swirl.set(
      [rad, r() * 6.283, (r() - 0.5) * 9, 0.18 + 1.6 / (rad + 1.5)],
      i * 4,
    );
    meta.set([lane, r() * 0.6, 0.6 + r() * 1.1], i * 3);
    col.set(hues[lane], i * 3);
  }
  void per;
  const g = new BufferGeometry();
  g.setAttribute("position", attr(pos, 3));
  g.setAttribute("aSwirl", attr(swirl, 4));
  g.setAttribute("aMeta", attr(meta, 3));
  g.setAttribute("aColor", attr(col, 3));
  const m = new ShaderMaterial({
    ...additive,
    uniforms: {
      ...shared(pr),
      uOrder: { value: 0 },
      uRewind: { value: 0 },
      uCenter: { value: [c.x, c.y] },
    },
    vertexShader: `attribute vec4 aSwirl; attribute vec3 aMeta; attribute vec3 aColor; uniform float uTime, uPR, uOrder, uRewind; uniform vec2 uCenter;
      varying vec3 vC; varying float vK, vA;
      void main(){ float ang = aSwirl.y + uTime*aSwirl.w; float rad = aSwirl.x*(1.+.06*sin(uTime*.5+aSwirl.y*3.));
        vec3 free = vec3(uCenter.x + cos(ang)*rad, uCenter.y + sin(ang)*rad*.62, aSwirl.z + sin(ang*2.+uTime*.3)*.8);
        float k = smoothstep(aMeta.y, aMeta.y+.4, uOrder*1.4);
        k = k*k*(3.-2.*k);
        vec3 p = mix(free, position, k);
        p.z += sin(k*3.14159)*(2.+aMeta.y*6.);
        vec4 mv = modelViewMatrix*vec4(p,1.); gl_Position = projectionMatrix*mv;
        vK = k; vC = mix(vec3(.62,.8,.95), aColor, k); vA = mix(.5, .95, k);
        gl_PointSize = clamp(aMeta.z*uPR*(55./-mv.z)*(1.+k*.4), 1., 5.5*uPR); }`,
    fragmentShader: `varying vec3 vC; varying float vK, vA; uniform float uDim;
      void main(){ vec2 p = gl_PointCoord-.5; float d = length(p)*2.; if(d>1.) discard;
        float a = (1.-d)*(1.-d); gl_FragColor = vec4(vC, a*vA*.9*(1.-uDim*.5)); }`,
  });
  const pts = new Points(g, m);
  pts.frustumCulled = false;
  return pts;
}

/* ---- the verification ring that sweeps the lattice during "recoverable" ---- */
export function createRing(pr) {
  const n = 220;
  const c = nebulaPosition();
  const pos = new Float32Array(n * 3),
    ph = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const a = (i / n) * Math.PI * 2;
    pos.set([c.x + Math.cos(a) * 9, c.y - 1.5 + Math.sin(a) * 9, 1.2], i * 3);
    ph[i] = a;
  }
  const g = new BufferGeometry();
  g.setAttribute("position", attr(pos, 3));
  g.setAttribute("aPhase", attr(ph, 1));
  const m = new ShaderMaterial({
    ...additive,
    uniforms: { ...shared(pr), uVerify: { value: 0 } },
    vertexShader: `attribute float aPhase; uniform float uTime, uPR, uVerify; varying float vA;
      void main(){ float head = mod(uTime*1.3, 6.2832); float dd = mod(head-aPhase+6.2832, 6.2832);
        vA = uVerify*(.18+.82*exp(-dd*1.3));
        vec4 mv = modelViewMatrix*vec4(position,1.); gl_Position = projectionMatrix*mv; gl_PointSize = (2.+vA*3.)*uPR; }`,
    fragmentShader: `varying float vA; void main(){ float d = length(gl_PointCoord-.5)*2.; if(d>1.) discard; gl_FragColor = vec4(.55,.95,.8, (1.-d)*vA); }`,
  });
  const pts = new Points(g, m);
  pts.frustumCulled = false;
  return pts;
}
