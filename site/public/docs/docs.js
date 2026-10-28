const root = document.documentElement;
const theme = document.querySelector("#docs-theme");
if (theme) {
  theme.value = root.dataset.theme;
  theme.addEventListener("change", () => {
    root.dataset.theme = theme.value;
    try {
      localStorage.setItem("orion-site-theme", theme.value);
    } catch {}
  });
}
const motionButton = document.querySelector("#docs-motion-toggle");
let paused = root.dataset.motion === "paused";
function syncMotion() {
  if (!motionButton) return;
  root.dataset.motion = paused ? "paused" : "running";
  motionButton.setAttribute(
    "aria-label",
    paused ? "Resume animations" : "Pause animations",
  );
  motionButton.setAttribute("aria-pressed", String(paused));
  motionButton.querySelector("span").textContent = paused ? "▷" : "Ⅱ";
}
motionButton?.addEventListener("click", () => {
  paused = !paused;
  try {
    localStorage.setItem("orion-site-motion", paused ? "paused" : "running");
  } catch {}
  syncMotion();
});
syncMotion();
const guidesMenu = document.querySelector(".guides-menu");
const narrow = matchMedia("(max-width:680px)");
function syncMenu() {
  if (guidesMenu) guidesMenu.open = !narrow.matches;
}
syncMenu();
narrow.addEventListener("change", syncMenu);

const searchStatus = document.getElementById("search-results");
const escapeText = (value) => String(value ?? "");

async function showSearch(query) {
  if (!searchStatus || !query.trim()) return;
  searchStatus.hidden = false;
  searchStatus.replaceChildren();
  const heading = document.createElement("h2");
  heading.textContent = `Search results for “${query.trim()}”`;
  searchStatus.append(heading);
  try {
    const response = await fetch("/Orion/docs/search-index.json");
    if (!response.ok) throw new Error("Search index unavailable");
    const entries = await response.json();
    const words = query.toLocaleLowerCase().split(/\s+/).filter(Boolean);
    const matches = entries
      .map((entry) => ({
        entry,
        score: words.reduce(
          (sum, word) =>
            sum +
            `${entry.title} ${entry.description} ${entry.text}`
              .toLocaleLowerCase()
              .split(word).length -
            1,
          0,
        ),
      }))
      .filter(({ score }) => score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, 8);
    if (!matches.length) {
      const empty = document.createElement("p");
      empty.textContent = "No guides matched. Try a broader term.";
      searchStatus.append(empty);
      return;
    }
    const list = document.createElement("ul");
    list.setAttribute("aria-label", "Matching documentation pages");
    for (const { entry } of matches) {
      const item = document.createElement("li");
      const link = document.createElement("a");
      link.href = entry.url;
      link.textContent = escapeText(entry.title);
      const description = document.createElement("p");
      description.textContent = escapeText(entry.description);
      item.append(link, description);
      list.append(item);
    }
    searchStatus.append(list);
  } catch {
    const failure = document.createElement("p");
    failure.textContent =
      "Search could not load. The guides are still available from the navigation.";
    searchStatus.append(failure);
  }
}

const query = new URLSearchParams(location.search).get("q");
const searchInput = document.getElementById("doc-search");
if (query && searchInput) {
  searchInput.value = query;
  showSearch(query);
}

for (const pre of document.querySelectorAll(".article pre")) {
  const code = pre.querySelector("code");
  if (!code) continue;
  const button = document.createElement("button");
  button.type = "button";
  button.className = "copy-code";
  button.textContent = "Copy code";
  button.setAttribute("aria-label", "Copy code");
  const status = document.createElement("span");
  status.className = "copy-status";
  status.setAttribute("aria-live", "polite");
  button.addEventListener("click", async () => {
    try {
      if (!navigator.clipboard?.writeText)
        throw new Error("Clipboard API unavailable");
      await navigator.clipboard.writeText(code.innerText);
      button.textContent = "Copied";
      status.textContent = "Code copied to clipboard.";
      button.dataset.state = "success";
    } catch {
      button.textContent = "Copy failed";
      status.textContent =
        "Could not copy code. Select the code block and copy it manually.";
      button.dataset.state = "failure";
    }
    window.setTimeout(() => {
      button.textContent = "Copy code";
      button.dataset.state = "";
      status.textContent = "";
    }, 2600);
  });
  pre.append(button, status);
}
