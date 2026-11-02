// The principal stars of Orion. Right ascension (hours) and declination (degrees)
// are astronomical facts; each of the seven brightest stars stands for one collection.
export const STARS = [
  {
    name: "Betelgeuse",
    ra: 5.9195,
    dec: 7.4071,
    mag: 0.42,
    collection: 0,
    tint: [1, 0.56, 0.36],
  },
  {
    name: "Bellatrix",
    ra: 5.4189,
    dec: 6.3497,
    mag: 1.64,
    collection: 1,
    tint: [0.7, 0.82, 1],
  },
  {
    name: "Mintaka",
    ra: 5.5334,
    dec: -0.2991,
    mag: 2.23,
    collection: 2,
    tint: [0.7, 0.82, 1],
  },
  {
    name: "Alnilam",
    ra: 5.6036,
    dec: -1.2019,
    mag: 1.69,
    collection: 3,
    tint: [0.72, 0.84, 1],
  },
  {
    name: "Alnitak",
    ra: 5.6793,
    dec: -1.9426,
    mag: 1.77,
    collection: 4,
    tint: [0.7, 0.82, 1],
  },
  {
    name: "Saiph",
    ra: 5.7959,
    dec: -9.6697,
    mag: 2.09,
    collection: 5,
    tint: [0.68, 0.8, 1],
  },
  {
    name: "Rigel",
    ra: 5.2423,
    dec: -8.2016,
    mag: 0.13,
    collection: 6,
    tint: [0.62, 0.78, 1],
  },
  {
    name: "Meissa",
    ra: 5.5855,
    dec: 9.9342,
    mag: 3.3,
    collection: -1,
    tint: [0.75, 0.85, 1],
  },
];

// Messier 42, the Orion Nebula.
export const NEBULA = { ra: 5.588, dec: -5.39 };

// Indices into STARS: the classic figure of the hunter.
export const EDGES = [
  [7, 0],
  [7, 1],
  [0, 4],
  [1, 2],
  [2, 3],
  [3, 4],
  [4, 5],
  [2, 6],
  [6, 5],
];

const CENTER_RA = 5.5833;
export const SKY_SCALE = 100;

// Gnomonic projection about the centre of the constellation, east to the left as on a sky chart.
export function projectSky(raHours, decDeg) {
  const d = (decDeg * Math.PI) / 180;
  const a = ((raHours - CENTER_RA) * 15 * Math.PI) / 180;
  const cosc = Math.cos(d) * Math.cos(a);
  return {
    x: -((Math.cos(d) * Math.sin(a)) / cosc) * SKY_SCALE,
    y: (Math.sin(d) / cosc) * SKY_SCALE,
  };
}

export function starPositions() {
  return STARS.map((star) => ({ ...star, ...projectSky(star.ra, star.dec) }));
}
export function nebulaPosition() {
  return projectSky(NEBULA.ra, NEBULA.dec);
}
