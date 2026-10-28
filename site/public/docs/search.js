(() => {
  const root = document.documentElement;
  const controls = document.querySelector(".header-controls, .docs-controls");
  if (!controls) return;

  const trigger = document.createElement("button");
  trigger.type = "button";
  trigger.className = "command-search-trigger";
  trigger.setAttribute("aria-haspopup", "dialog");
  trigger.setAttribute("aria-label", "Search documentation");
  const triggerText = document.createElement("span");
  triggerText.textContent = "Search";
  const shortcut = document.createElement("kbd");
  shortcut.setAttribute("aria-hidden", "true");
  shortcut.textContent = "⌘ K";
  trigger.append(triggerText, shortcut);
  controls.prepend(trigger);

  const dialog = document.createElement("dialog");
  dialog.className = "command-search";
  dialog.setAttribute("aria-labelledby", "command-search-title");
  dialog.innerHTML = `
    <section class="command-search-panel">
      <header class="command-search-heading">
        <div><span class="command-search-eyebrow">ORION FIELD GUIDE</span><h2 id="command-search-title">Search documentation</h2></div>
        <button class="command-search-close" type="button" aria-label="Close search"><span aria-hidden="true">×</span></button>
      </header>
      <label class="visually-hidden" for="command-search-input">Search guides</label>
      <div class="command-search-input-wrap"><span aria-hidden="true">⌕</span><input id="command-search-input" type="search" role="searchbox" autocomplete="off" spellcheck="false" placeholder="Search guides, topics, and commands…"><kbd aria-hidden="true">ESC</kbd></div>
      <p class="command-search-hint">Type a few words. Every word must match.</p>
      <div class="command-search-results" role="status" aria-live="polite"></div>
      <footer class="command-search-footer"><span>LOCAL DOCUMENTATION</span><span><kbd>↑</kbd><kbd>↓</kbd> navigate <kbd>↵</kbd> open</span></footer>
    </section>`;
  document.body.append(dialog);

  const input = dialog.querySelector("#command-search-input");
  const results = dialog.querySelector(".command-search-results");
  const close = dialog.querySelector(".command-search-close");
  let returnFocus = null;
  let entriesPromise = null;
  let selectedIndex = 0;

  const setMessage = (message, state = "") => {
    results.replaceChildren();
    results.dataset.state = state;
    const note = document.createElement("p");
    note.className = "command-search-message";
    note.textContent = message;
    results.append(note);
    if (state === "error" || state === "empty") {
      const browse = document.createElement("a");
      browse.className = "command-search-browse";
      browse.href = "/Orion/docs/";
      browse.textContent = "Browse all guides →";
      results.append(browse);
    }
  };

  const readEntries = () => {
    if (!entriesPromise) {
      entriesPromise = fetch("/Orion/docs/search-index.json", {
        headers: { Accept: "application/json" },
      })
        .then((response) => {
          if (!response.ok) throw new Error("Search index unavailable");
          return response.json();
        })
        .then((entries) => {
          if (!Array.isArray(entries)) throw new Error("Invalid search index");
          return entries;
        })
        .catch((error) => {
          entriesPromise = null;
          throw error;
        });
    }
    return entriesPromise;
  };

  const safeLocalUrl = (value) => {
    try {
      const url = new URL(value, location.origin);
      if (
        url.origin !== location.origin ||
        !/^\/Orion\/docs\/[\w-]+\.html$/.test(url.pathname)
      )
        return null;
      return `${url.pathname}${url.search}${url.hash}`;
    } catch {
      return null;
    }
  };

  const render = async () => {
    const query = input.value.trim().toLocaleLowerCase();
    if (!query) {
      setMessage("Start typing to search the guides.");
      return;
    }
    setMessage("Searching the local guide index…", "loading");
    try {
      const entries = await readEntries();
      if (!dialog.open || query !== input.value.trim().toLocaleLowerCase())
        return;
      const terms = [...new Set(query.split(/\s+/u).filter(Boolean))];
      const matches = entries
        .map((entry) => {
          const title = String(entry.title ?? "").toLocaleLowerCase();
          const description = String(
            entry.description ?? "",
          ).toLocaleLowerCase();
          const text = String(entry.text ?? "").toLocaleLowerCase();
          const fields = [title, description, text];
          const allMatch = terms.every((term) =>
            fields.some((field) => field.includes(term)),
          );
          const score = terms.reduce(
            (total, term) =>
              total +
              (title.includes(term) ? 12 : 0) +
              (description.includes(term) ? 4 : 0) +
              (text.includes(term) ? 1 : 0),
            0,
          );
          return { entry, score, allMatch, url: safeLocalUrl(entry.url) };
        })
        .filter((result) => result.allMatch && result.url)
        .sort(
          (a, b) =>
            b.score - a.score ||
            String(a.entry.title).localeCompare(String(b.entry.title)),
        )
        .slice(0, 8);
      results.replaceChildren();
      if (!matches.length) {
        setMessage("No guides matched. Try a broader term.", "empty");
        return;
      }
      selectedIndex = 0;
      const list = document.createElement("ul");
      list.className = "command-search-list";
      list.setAttribute("aria-label", "Matching documentation pages");
      for (const [index, match] of matches.entries()) {
        const item = document.createElement("li");
        const link = document.createElement("a");
        link.className = "command-search-result";
        link.href = match.url;
        link.setAttribute("data-result-index", String(index));
        link.setAttribute(
          "aria-current",
          index === selectedIndex ? "true" : "false",
        );
        const title = document.createElement("span");
        title.className = "command-search-result-title";
        title.textContent = String(match.entry.title ?? "Untitled guide");
        const description = document.createElement("span");
        description.className = "command-search-result-description";
        description.textContent = String(match.entry.description ?? "");
        const arrow = document.createElement("span");
        arrow.className = "command-search-result-arrow";
        arrow.setAttribute("aria-hidden", "true");
        arrow.textContent = "↗";
        link.append(title, description, arrow);
        item.append(link);
        list.append(item);
      }
      results.dataset.state = "results";
      results.append(list);
    } catch {
      if (!dialog.open || query !== input.value.trim().toLocaleLowerCase())
        return;
      entriesPromise = null;
      setMessage(
        "Search could not load. Check your connection or try again.",
        "error",
      );
    }
  };

  const open = () => {
    returnFocus = document.activeElement;
    if (!dialog.open) dialog.showModal();
    input.value = "";
    setMessage("Start typing to search the guides.");
    input.focus();
  };

  trigger.addEventListener("click", open);
  close.addEventListener("click", () => dialog.close());
  dialog.addEventListener("close", () => {
    if (returnFocus?.isConnected && typeof returnFocus.focus === "function")
      returnFocus.focus();
  });
  input.addEventListener("input", render);
  input.addEventListener("keydown", (event) => {
    const links = [...results.querySelectorAll("a[data-result-index]")];
    if (!links.length) return;
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      selectedIndex =
        (selectedIndex + (event.key === "ArrowDown" ? 1 : -1) + links.length) %
        links.length;
      links.forEach((link, index) =>
        link.setAttribute(
          "aria-current",
          index === selectedIndex ? "true" : "false",
        ),
      );
      links[selectedIndex]?.scrollIntoView({ block: "nearest" });
    } else if (event.key === "Enter") {
      event.preventDefault();
      links[selectedIndex]?.click();
    }
  });
  document.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      if (dialog.open) {
        input.focus();
        input.select();
      } else {
        open();
      }
    }
  });

  // Keep the generated button labels concise on narrow layouts.
  if (root.dataset.motion === "paused") dialog.dataset.motion = "paused";
})();
