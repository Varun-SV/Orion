// Original artwork for the fictional sample library. No external images or fonts.
let instance = 0;
export function mediaArtwork(index) {
  const id = `media-art-${++instance}`;
  const palettes = [
    ["#102a30", "#8cb5a0", "#f2edbf"],
    ["#182336", "#789aac", "#dae4dc"],
    ["#403962", "#c0a0bc", "#f8d6a9"],
    ["#193f45", "#7eb4ad", "#f3d3b2"],
    ["#442f38", "#ba7f69", "#f2c18d"],
    ["#a44229", "#d79166", "#f7d7a6"],
    ["#253b30", "#779075", "#e7d8b4"],
  ];
  const [dark, mid, light] = palettes[index];
  const titles = [
    ["THE", "LANTERN"],
    ["NORTH", "BOUND"],
    ["CLOUD ATLAS", "ACADEMY"],
    ["PAPER MOON", "GARDEN"],
    ["SMALL", "HOURS"],
    ["QUIET", "LINES"],
    ["THE FIELD", "NOTEBOOK"],
  ];
  const isMusic = index === 5,
    isBook = index === 6;
  const shape = isMusic
    ? `<g transform="translate(120 139)"><circle r="81" fill="${dark}"/>${[75, 66, 57, 48, 39, 30].map((r) => `<circle r="${r}" stroke="${light}" stroke-opacity=".3" fill="none"/>`).join("")}<circle r="20" fill="${light}"/><circle r="4" fill="${dark}"/></g><path d="M29 90V23h51M211 190v67h-51" fill="none" stroke="${light}" stroke-width="2"/>`
    : isBook
      ? `<g stroke="${light}" fill="none" stroke-width="1.2"><path d="M120 246V86M120 119Q61 126 63 80Q115 78 120 119M120 152Q182 147 178 104Q127 114 120 152M120 182Q63 186 58 141Q111 140 120 182M120 217Q179 215 187 171Q134 174 120 217"/><path d="m64 82 56 37m58-14-58 47m-61-10 61 40m66-10-66 45" stroke-opacity=".45"/></g><rect x="10" y="10" width="220" height="300" rx="1" fill="none" stroke="${light}" stroke-opacity=".35"/><path d="M17 0V320" stroke="#000" stroke-opacity=".3"/>`
      : `<circle cx="${index === 2 ? 165 : 125}" cy="${index === 2 ? 99 : 127}" r="${index === 2 ? 51 : 64}" fill="url(#${id}-sun)"/>${Array.from({ length: 6 }, (_, i) => `<path d="M-20 ${202 + i * 21}Q${40 + i * 18} ${90 + i * 18} ${112 + i * 10} ${183 + i * 17}T270 ${153 + i * 23}V330H-20Z" fill="${i % 2 ? dark : mid}" opacity="${0.4 + i * 0.1}"/>`).join("")}${index === 0 ? `<path d="m118 216 4-25 4 25 9 20h-26Z" fill="#061516"/><path d="M132 210v12" stroke="${light}" stroke-width="2"/><circle cx="132" cy="211" r="3" fill="${light}"/>` : ""}`;
  return `<svg class="media-artwork" viewBox="0 0 240 320" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" focusable="false"><defs><linearGradient id="${id}-bg" x2=".7" y2="1"><stop stop-color="${dark}"/><stop offset="1" stop-color="${mid}"/></linearGradient><radialGradient id="${id}-sun"><stop stop-color="${light}"/><stop offset=".8" stop-color="${light}" stop-opacity=".9"/><stop offset="1" stop-color="${light}" stop-opacity=".1"/></radialGradient></defs><rect width="240" height="320" fill="url(#${id}-bg)"/>${Array.from({ length: 28 }, (_, i) => `<circle cx="${(i * 79 + 13) % 240}" cy="${(i * 31 + 21) % 260}" r="${i % 5 === 0 ? 1 : 0.45}" fill="${light}" opacity=".45"/>`).join("")}${shape}<g fill="${light}" text-anchor="middle"><text x="120" y="${isBook ? 42 : 32}" font-family="Georgia,serif" font-size="${index === 2 || index === 3 ? 17 : 23}" letter-spacing="${index === 2 || index === 3 ? 1 : 3}">${titles[index][0]}</text><text x="120" y="${isBook ? 64 : 57}" font-family="Georgia,serif" font-size="${index === 2 || index === 3 ? 18 : 25}" letter-spacing="2">${titles[index][1]}</text><text x="120" y="293" font-family="sans-serif" font-size="6" letter-spacing="2.3">${isMusic ? "AN ALBUM BY SAMPLE ARTIST" : isBook ? "OBSERVATIONS FROM THE EVERYDAY" : "AN ORIGINAL FICTIONAL STORY"}</text><path d="M107 306h26" stroke="${light}" stroke-opacity=".6"/></g></svg>`;
}

export function universeMarkup() {
  return `<div class="media-universe" aria-hidden="true">
    <div class="universe-wordmark">ORION</div>
    <div class="universe-orbit-label"><span class="small-dot"></span> A UNIVERSE, CONNECTED.</div>
    <div class="universe-covers">
      ${[0, 5, 6, 2].map((index, i) => `<div class="universe-cover universe-cover--${i}"><div class="universe-cover-face">${mediaArtwork(index)}</div><span>${["01 / CINEMA", "02 / SOUND", "03 / WORDS", "04 / IMAGINATION"][i]}</span></div>`).join("")}
    </div>
    <div class="universe-coordinate"><i></i><span>07 collections<br><b>One place to belong.</b></span></div>
  </div>`;
}
