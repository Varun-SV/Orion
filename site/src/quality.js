// Frame-time governor. Steps quality down quickly when frames are slow and back up
// slowly when they are comfortably fast, and stops trying once it has proven that a
// higher tier does not hold.
export const TIERS = [
  { name: "high", scale: 1, particles: 1, nebula: 1 },
  { name: "medium", scale: 0.75, particles: 0.6, nebula: 0.7 },
  { name: "low", scale: 0.5, particles: 0.3, nebula: 0.4 },
];

export function initialTier({
  coarsePointer = false,
  saveData = false,
  cores = 8,
  memory = 8,
} = {}) {
  if (saveData || cores <= 2 || memory <= 2) return 2;
  if (coarsePointer || cores <= 4 || memory <= 4) return 1;
  return 0;
}

export function createGovernor({
  start = 0,
  windowSize = 45,
  slowMs = 26,
  fastMs = 18,
  upAfterFrames = 240,
  upBlockMs = 6000,
  maxUpAttempts = 2,
} = {}) {
  let tier = start;
  const samples = new Float32Array(windowSize);
  let count = 0,
    head = 0,
    sum = 0,
    fastRun = 0,
    now = 0,
    lastDown = -Infinity,
    upAttempts = 0,
    lastUp = -Infinity;
  const reset = () => {
    count = 0;
    head = 0;
    sum = 0;
    fastRun = 0;
  };
  return {
    get tier() {
      return tier;
    },
    // Returns the new tier when it changes, otherwise null.
    sample(dt) {
      // A hidden tab or a long stall is not evidence about rendering speed.
      if (!(dt > 0) || dt > 250) {
        reset();
        return null;
      }
      now += dt;
      if (count === windowSize) sum -= samples[head];
      else count++;
      samples[head] = dt;
      sum += dt;
      head = (head + 1) % windowSize;
      if (count < windowSize) return null;
      const avg = sum / count;
      if (avg > slowMs && tier < TIERS.length - 1 && now - lastDown > 1200) {
        if (now - lastUp < upBlockMs) upAttempts++;
        tier++;
        lastDown = now;
        reset();
        return tier;
      }
      fastRun = avg < fastMs ? fastRun + 1 : 0;
      if (fastRun >= upAfterFrames && tier > 0 && upAttempts < maxUpAttempts) {
        tier--;
        lastUp = now;
        reset();
        return tier;
      }
      return null;
    },
  };
}
