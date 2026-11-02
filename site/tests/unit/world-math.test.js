import test from "node:test";
import assert from "node:assert/strict";
import {
  STARS,
  EDGES,
  projectSky,
  starPositions,
  nebulaPosition,
} from "../../src/stars-data.js";
import { TIERS, createGovernor, initialTier } from "../../src/quality.js";
import {
  CHAPTERS,
  ANCHORS,
  locate,
  activeCollection,
  cameraPose,
  damp,
  framing,
  worldState,
} from "../../src/director.js";

test("seven principal stars map one-to-one onto the seven collections", () => {
  const mapped = STARS.filter((s) => s.collection >= 0)
    .map((s) => s.collection)
    .sort();
  assert.deepEqual(mapped, [0, 1, 2, 3, 4, 5, 6]);
  assert.equal(STARS.length, 8);
  for (const [a, b] of EDGES) assert.ok(STARS[a] && STARS[b] && a !== b);
});

test("projection reproduces the shape of Orion as seen on a sky chart", () => {
  const p = Object.fromEntries(starPositions().map((s) => [s.name, s]));
  assert.ok(
    p.Betelgeuse.y > 0 && p.Rigel.y < 0,
    "Betelgeuse north, Rigel south",
  );
  assert.ok(
    p.Betelgeuse.x < 0 && p.Rigel.x > 0,
    "east (Betelgeuse) is on the left",
  );
  assert.ok(
    p.Alnitak.x < p.Alnilam.x && p.Alnilam.x < p.Mintaka.x,
    "the belt runs east to west",
  );
  const spread = Math.abs(p.Alnitak.y - p.Mintaka.y);
  assert.ok(spread < 3, "belt stars are nearly level");
  assert.ok(
    nebulaPosition().y < p.Alnilam.y,
    "the nebula hangs below the belt",
  );
  assert.deepEqual(Object.keys(projectSky(5.5833, 0)).sort(), ["x", "y"]);
  assert.ok(Math.abs(projectSky(5.5833, 0).x) < 1e-9);
});

test("locate gives a continuous flight coordinate across chapter boundaries", () => {
  const vh = 800;
  const tops = [0, 1500, 3300, 5100, 6900, 8700, 9900, 11000];
  assert.equal(tops.length, CHAPTERS.length + 1);
  let previous = locate(tops, 0, vh).u;
  for (let y = 1; y <= 11000; y += 1) {
    const { u } = locate(tops, y, vh);
    assert.ok(u + 1e-9 >= previous, `u never goes backwards at ${y}`);
    assert.ok(u - previous < 0.02, `u jumps by ${u - previous} at ${y}`);
    previous = u;
  }
  assert.equal(locate(tops, 0, vh).index, 0);
  assert.equal(locate(tops, 99999, vh).index, 6);
  assert.equal(locate(tops, 1800, vh).index, 1);
  assert.equal(locate(tops, 1499, vh).index, 0);
});

test("camera and world are finite and continuous along the whole flight", () => {
  const pose = { p: [0, 0, 0], l: [0, 0, 0] };
  const state = {};
  let last = null;
  for (let u = 0; u <= 6.0001; u += 0.002) {
    cameraPose(u, pose);
    worldState(u, state);
    for (const v of [...pose.p, ...pose.l, pose.fov, ...Object.values(state)])
      assert.ok(Number.isFinite(v));
    const now = [...pose.p, ...pose.l, pose.fov];
    if (last)
      now.forEach((v, i) =>
        assert.ok(Math.abs(v - last[i]) < 1.2, "no camera jump"),
      );
    last = now;
    for (const key of ["focus", "nebula", "order", "rewind", "verify"])
      assert.ok(state[key] >= 0 && state[key] <= 1.0001, `${key} in range`);
    assert.ok(state.dim >= -0.2 && state.dim <= 0.6);
  }
  cameraPose(0, pose);
  assert.deepEqual(pose.p, ANCHORS[0].p);
  cameraPose(6, pose);
  assert.deepEqual(pose.p.map(Math.round), ANCHORS[6].p);
  cameraPose(-3, pose);
  assert.deepEqual(pose.p, ANCHORS[0].p);
  cameraPose(99, pose);
  assert.deepEqual(pose.p.map(Math.round), ANCHORS[6].p);
});

test("the narrative runs in order: scattered, tidy, rewound, tidy again", () => {
  const at = (u) => worldState(u, {});
  assert.equal(at(1).order, 0);
  assert.ok(at(3.5).order > 0.95);
  assert.ok(at(4.4).rewind > 0.9 && at(4.4).order < 0.2);
  assert.ok(at(5.1).order > 0.95 && at(5.1).rewind === 0);
  assert.ok(at(1.0).focus > 0.9 && at(0).focus === 0 && at(3).focus === 0);
});

test("collection selection covers all seven evenly and only in its chapter", () => {
  const seen = new Set();
  for (let l = 0; l <= 1; l += 0.001) seen.add(activeCollection(1, l));
  assert.deepEqual([...seen].sort(), [0, 1, 2, 3, 4, 5, 6]);
  assert.equal(activeCollection(0, 0.5), -1);
  assert.equal(activeCollection(2, 0.5), -1);
});

test("framing pulls back on portrait screens and clears space for the headline on wide ones", () => {
  assert.ok(framing(0.5, 0).back > framing(1.6, 0).back);
  assert.equal(framing(1.6, 0).back, 1);
  assert.ok(framing(1.8, 0).shiftX < 0);
  assert.ok(framing(1.8, 3).shiftX === 0);
  assert.ok(framing(0.5, 0).shiftY < 0);
  // The scene stays in the upper half through the text chapters, a little less than at the opening.
  assert.ok(framing(0.5, 3).shiftY < 0);
  assert.ok(
    Math.abs(framing(0.5, 3).shiftY) < Math.abs(framing(0.5, 0).shiftY),
  );
  assert.ok(
    Math.abs(framing(0.5, 6).shiftY) < Math.abs(framing(0.5, 3).shiftY),
  );
});

test("quality governor steps down fast, up slowly, and stops oscillating", () => {
  assert.equal(initialTier({}), 0);
  assert.equal(initialTier({ coarsePointer: true }), 1);
  assert.equal(initialTier({ saveData: true }), 2);
  const g = createGovernor({ start: 0 });
  const feed = (ms, frames) => {
    let changed = null;
    for (let i = 0; i < frames; i++) changed = g.sample(ms) ?? changed;
    return changed;
  };
  feed(16, 100);
  assert.equal(g.tier, 0, "good frames keep the top tier");
  assert.equal(feed(40, 60), 1, "slow frames drop one tier");
  assert.equal(g.sample(500), null, "a stall is ignored");
  assert.equal(g.tier, 1);
  // Recovery: needs a long sustained fast run.
  assert.equal(feed(10, 100), null);
  assert.equal(feed(10, 400), 0, "sustained speed earns the tier back");
  // Fail twice after moving up: the governor then stays down.
  feed(40, 60);
  feed(10, 400);
  feed(40, 60);
  const tierAfter = g.tier;
  feed(10, 2000);
  assert.equal(
    g.tier,
    tierAfter,
    "no oscillation after repeated failed attempts",
  );
  assert.ok(g.tier <= TIERS.length - 1);
});

test("damping glides toward a target without overshoot and is frame-rate independent", () => {
  let a = 0;
  for (let i = 0; i < 40; i++) {
    const next = damp(a, 10, 1 / 60, 6);
    assert.ok(
      next > a && next < 10,
      "moves toward the target and never passes it",
    );
    a = next;
  }
  // One 20 ms step equals two 10 ms steps.
  const once = damp(0, 8, 0.02, 6);
  const twice = damp(damp(0, 8, 0.01, 6), 8, 0.01, 6);
  assert.ok(Math.abs(once - twice) < 1e-9);
  assert.equal(damp(3, 9, 0, 6), 3);
  assert.equal(damp(3, 9, -1, 6), 3);
  // A jump of a selected star (about 6 world units) is spread over many frames, not one.
  const first = damp(0, 6, 1 / 60, 6);
  assert.ok(first < 0.7);
});
