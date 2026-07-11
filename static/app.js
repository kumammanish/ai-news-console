const TABS = ["news", "microsoft", "repos", "use_cases"];

const TAB_ENDPOINTS = {
  news: "/api/news",
  microsoft: "/api/microsoft",
  repos: "/api/repos",
  use_cases: "/api/use-cases",
};

const state = {
  tab: "news",
  itemsByTab: Object.fromEntries(TABS.map((t) => [t, []])),
  activeSources: Object.fromEntries(TABS.map((t) => [t, new Set()])),
  search: "",
  lastVisit: localStorage.getItem("lastVisit"),
};

const el = {
  tabs: document.getElementById("tabs"),
  chips: document.getElementById("chips"),
  cards: document.getElementById("cards"),
  emptyState: document.getElementById("empty-state"),
  search: document.getElementById("search"),
  refreshBtn: document.getElementById("refresh-btn"),
  refreshIcon: document.getElementById("refresh-icon"),
  lastUpdated: document.getElementById("last-updated"),
};

function relativeTime(iso) {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const diffSec = Math.round((Date.now() - then) / 1000);
  if (diffSec < 60) return "just now";
  const diffMin = Math.round(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.round(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.round(diffHr / 24);
  if (diffDay < 7) return `${diffDay}d ago`;
  return new Date(iso).toLocaleDateString();
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

async function fetchJSON(url, opts) {
  const resp = await fetch(url, opts);
  if (!resp.ok) throw new Error(`${url} -> ${resp.status}`);
  return resp.json();
}

async function loadTab(tab) {
  const items = await fetchJSON(TAB_ENDPOINTS[tab]);
  state.itemsByTab[tab] = items;
  if (state.activeSources[tab].size === 0) {
    for (const it of items) state.activeSources[tab].add(it.source);
  } else {
    // keep only sources still present, add any newly seen sources as active
    const present = new Set(items.map((i) => i.source));
    for (const s of present) {
      if (!state.activeSources[tab].has(s) && !wasSourceKnown(tab, s)) {
        state.activeSources[tab].add(s);
      }
    }
  }
  return items;
}

const knownSources = Object.fromEntries(TABS.map((t) => [t, new Set()]));
function wasSourceKnown(tab, source) {
  const known = knownSources[tab].has(source);
  knownSources[tab].add(source);
  return known;
}

async function loadAll() {
  await Promise.all(Object.keys(TAB_ENDPOINTS).map(loadTab));
  render();
}

function updateLastUpdated() {
  const items = state.itemsByTab[state.tab];
  if (!items.length) {
    el.lastUpdated.textContent = "";
    return;
  }
  const latest = items.reduce((max, it) => {
    const t = new Date(it.last_seen_at).getTime();
    return t > max ? t : max;
  }, 0);
  el.lastUpdated.textContent = latest ? `Updated ${relativeTime(new Date(latest).toISOString())}` : "";
}

function renderChips() {
  const items = state.itemsByTab[state.tab];
  const sources = [...new Set(items.map((i) => i.source))].sort();
  el.chips.innerHTML = "";
  for (const source of sources) {
    const chip = document.createElement("button");
    const active = state.activeSources[state.tab].has(source);
    chip.className = `chip ${active ? "active" : ""}`;
    chip.textContent = source;
    chip.addEventListener("click", () => {
      const set = state.activeSources[state.tab];
      if (set.has(source)) set.delete(source);
      else set.add(source);
      render();
    });
    el.chips.appendChild(chip);
  }
}

function handleImageError(img) {
  const fallback = document.createElement("div");
  fallback.className = "card-image--fallback";
  fallback.style.setProperty("--ping-delay", img.dataset.pingDelay || "0s");
  img.replaceWith(fallback);
}

function cardHtml(item) {
  const isNew = state.lastVisit && item.first_seen_at > state.lastVisit;
  const badges = [];
  if (isNew) badges.push('<span class="new-badge text-[10px] font-semibold px-1.5 py-0.5 rounded-full meta-mono">NEW</span>');

  let repoMeta = "";
  if (item.category === "repos") {
    const deltaText =
      item.star_delta === null || item.star_delta === undefined
        ? ""
        : item.star_delta > 0
        ? ` (+${item.star_delta} this week)`
        : "";
    repoMeta = `<div class="meta-mono text-xs text-zinc-400 flex items-center gap-3 mt-1">
      <span>⭐ ${item.stars ?? "?"}${deltaText}</span>
      ${item.language ? `<span>${escapeHtml(item.language)}</span>` : ""}
    </div>`;
  }

  // Stagger the fallback corner-ping per card so a grid of no-image items
  // doesn't pulse in visual unison.
  const pingDelay = `${(item.id % 5) * 0.3}s`;
  const imageBand = item.image
    ? `<img class="card-image" src="${escapeHtml(item.image)}" alt="" loading="lazy" data-ping-delay="${pingDelay}" onerror="handleImageError(this)">`
    : `<div class="card-image--fallback" style="--ping-delay:${pingDelay}"></div>`;

  return `
    <article class="card ${item.read ? "is-read" : ""}" data-id="${item.id}">
      ${imageBand}
      <div class="card-body">
        <a href="${item.url}" target="_blank" rel="noopener" class="card-title text-[0.95rem]">${escapeHtml(item.title)}</a>
        <p class="text-sm text-zinc-400 leading-relaxed line-clamp-3">${escapeHtml(item.gist || "")}</p>
        ${repoMeta}
        <div class="mt-auto pt-2 flex items-center justify-between">
          <span class="source-badge"><span class="source-dot"></span>${escapeHtml(item.source || "")}</span>
          <div class="flex items-center gap-2">
            ${badges.join("")}
            <span class="meta-mono text-xs text-zinc-500">${relativeTime(item.published_at || item.first_seen_at)}</span>
          </div>
        </div>
      </div>
    </article>
  `;
}

function render() {
  document.body.dataset.activeTab = state.tab;
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === state.tab);
  });

  renderChips();

  const search = state.search.trim().toLowerCase();
  const activeSources = state.activeSources[state.tab];
  const items = state.itemsByTab[state.tab].filter((it) => {
    if (activeSources.size && !activeSources.has(it.source)) return false;
    if (!search) return true;
    return (
      it.title.toLowerCase().includes(search) || (it.gist || "").toLowerCase().includes(search)
    );
  });

  el.cards.innerHTML = items.map(cardHtml).join("");
  el.emptyState.classList.toggle("hidden", items.length > 0);
  updateLastUpdated();

  el.cards.querySelectorAll(".card a").forEach((link) => {
    link.addEventListener("click", () => {
      const card = link.closest(".card");
      const id = Number(card.dataset.id);
      markRead(id);
    });
  });
}

async function markRead(id) {
  try {
    await fetch(`/api/item/${id}/read`, { method: "POST" });
  } catch (e) {
    console.warn("Failed to mark item read", e);
  }
  for (const tab of Object.keys(state.itemsByTab)) {
    const item = state.itemsByTab[tab].find((i) => i.id === id);
    if (item) item.read = true;
  }
  const card = el.cards.querySelector(`.card[data-id="${id}"]`);
  if (card) card.classList.add("is-read");
}

async function doRefresh(force) {
  el.refreshBtn.disabled = true;
  el.refreshIcon.classList.add("spinning");
  try {
    await fetch(`/api/refresh?force=${force ? "true" : "false"}`, { method: "POST" });
    await loadAll();
  } catch (e) {
    console.error("Refresh failed", e);
    alert("Refresh failed — check the server logs (data/app.log).");
  } finally {
    el.refreshIcon.classList.remove("spinning");
    el.refreshBtn.disabled = false;
  }
}

el.tabs.addEventListener("click", (e) => {
  const btn = e.target.closest(".tab-btn");
  if (!btn) return;
  state.tab = btn.dataset.tab;
  render();
});

el.search.addEventListener("input", (e) => {
  state.search = e.target.value;
  render();
});

el.refreshBtn.addEventListener("click", () => doRefresh(true));

(async function init() {
  const visitStart = new Date().toISOString();
  await loadAll();
  localStorage.setItem("lastVisit", visitStart);
})();
