// Klubbhuset – appen. Enkel router med en vy per adress (#/, #/story/12, #/sparat …).

import { createApi } from "./api.js";
import { local } from "./local.js";

const SECTIONS = [
  { slug: "touren", name: "Touren" },
  { slug: "utrustning", name: "Utrustning" },
  { slug: "teknik", name: "Teknik" },
  { slug: "spelare", name: "Spelare" },
  { slug: "historia", name: "Historia" },
  { slug: "youtube-poddar", name: "YouTube & Poddar" },
];

const app = document.getElementById("app");
const state = { api: null, currentStory: null };

// --- Hjälpfunktioner ---------------------------------------------------------

const esc = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

const ICON = {
  search: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/></svg>',
  back: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15 5l-7 7 7 7"/></svg>',
  bookmark: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 4h10v16l-5-3.5L7 20z"/></svg>',
  external: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14 5h5v5"/><path d="M19 5l-8 8"/><path d="M17 14v4a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V8a1 1 0 0 1 1-1h4"/></svg>',
  play: '<svg class="play" viewBox="0 0 24 24" aria-hidden="true"><path d="M9 7l8 5-8 5z"/></svg>',
  gear: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M12 3v2.2M12 18.8V21M3 12h2.2M18.8 12H21M5.6 5.6l1.6 1.6M16.8 16.8l1.6 1.6M5.6 18.4l1.6-1.6M16.8 7.2l1.6-1.6"/></svg>',
  headphones: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 15v-3a8 8 0 0 1 16 0v3"/><rect x="3.5" y="14" width="4" height="6" rx="1.5"/><rect x="16.5" y="14" width="4" height="6" rx="1.5"/></svg>',
};

// Bara riktiga bilder – saknas bilden blir det en ren textnyhet, som i en tidning.
function photo(story, caption = "") {
  if (!story.image_url) return "";
  const tint = `ph-${(Number(story.id) % 3) + 1}`;
  return `<figure class="photo-wrap"><div class="photo ${tint}"><img src="${esc(story.image_url)}" alt=""
    loading="lazy" referrerpolicy="no-referrer" onerror="this.closest('figure').remove()"></div>${
    caption ? `<figcaption class="caption">${esc(caption)}</figcaption>` : ""}</figure>`;
}

// --- Tema ---------------------------------------------------------------------

const darkQuery = window.matchMedia("(prefers-color-scheme: dark)");

function applyTheme(choice) {
  if (choice === "light" || choice === "dark") document.documentElement.dataset.theme = choice;
  else delete document.documentElement.dataset.theme;
  // Statusraden ska ha samma färg som appen, även när temat är valt i appen
  const forced = choice === "light" ? "#ffffff" : choice === "dark" ? "#121212" : null;
  document.querySelectorAll('meta[name="theme-color"]').forEach((meta) => {
    const own = meta.media.includes("dark") ? "#121212" : "#ffffff";
    meta.setAttribute("content", forced || own);
  });
}

const GENERIC_WORDS = new Set(["golf", "the", "on", "msn", "com", "www"]);

function initials(name) {
  const all = String(name || "?").split(/[^\p{L}\p{N}]+/u).filter(Boolean);
  const specific = all.filter((w) => !GENERIC_WORDS.has(w.toLowerCase()));
  const words = specific.length ? specific : all;
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return (words[0][0] + words[1][0]).toUpperCase();
}

function badgeClass(name) {
  let hash = 0;
  for (const ch of String(name)) hash = (hash * 31 + ch.codePointAt(0)) >>> 0;
  return `c${hash % 6}`;
}

const badge = (name) => `<span class="badge ${badgeClass(name)}" aria-hidden="true">${esc(initials(name))}</span>`;

function paragraphs(text) {
  return String(text || "")
    .split(/\n\s*\n/)
    .map((p) => p.trim())
    .filter(Boolean)
    .map((p) => `<p>${esc(p)}</p>`)
    .join("");
}

function ago(iso) {
  if (!iso) return "";
  const minutes = Math.max(0, Math.round((Date.now() - new Date(iso)) / 60000));
  if (minutes < 60) return `för ${Math.max(1, minutes)} min sedan`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `för ${hours} tim sedan`;
  return new Date(iso).toLocaleDateString("sv-SE", { day: "numeric", month: "short" });
}

const shortDate = (iso) =>
  iso ? new Date(iso).toLocaleDateString("sv-SE", { day: "numeric", month: "short" }) : "";

function todayLine() {
  const text = new Date().toLocaleDateString("sv-SE", {
    weekday: "long", day: "numeric", month: "long", year: "numeric",
  });
  return text.charAt(0).toUpperCase() + text.slice(1);
}

const readMinutes = (words) => Math.max(1, Math.round((words || 0) / 220));

function formatDuration(value) {
  if (!value) return "";
  const parts = String(value).split(":").map(Number);
  if (parts.some(Number.isNaN)) return "";
  const seconds = parts.reduce((total, part) => total * 60 + part, 0);
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.round((seconds % 3600) / 60);
  return hours ? `${hours} tim ${minutes} min` : `${Math.max(1, minutes)} min`;
}
const sectionBySlug = (slug) => SECTIONS.find((s) => s.slug === slug);
const slugFor = (name) => (SECTIONS.find((s) => s.name === name) || SECTIONS[0]).slug;

function sourcesLine(story) {
  const outlets = story.outlets || [];
  const count = story.outlet_count || outlets.length || 1;
  return `<div class="sources"><span class="badges">${outlets.slice(0, 4).map(badge).join("")}</span>
    <span><b>${count} ${count === 1 ? "källa" : "källor"}</b> · ${esc(ago(story.last_published_at))}</span></div>`;
}

// --- Gemensamma delar --------------------------------------------------------

function masthead(active) {
  const nav = [`<a href="#/" class="${active === "idag" ? "active" : ""}">Idag</a>`]
    .concat(SECTIONS.map((s) =>
      `<a href="#/sektion/${s.slug}" class="${active === s.slug ? "active" : ""}">${esc(s.name)}</a>`))
    .join("");
  return `
    <header class="masthead">
      <div class="date">${esc(todayLine())}</div>
      <h1>Klubbhuset</h1>
      <div class="tagline">Golf · Touren · Teknik · Historia</div>
    </header>
    <div class="compactbar" aria-hidden="true"><button data-action="top" tabindex="-1">Klubbhuset</button></div>
    <div class="navwrap"><nav class="sectionnav" aria-label="Sektioner">${nav}</nav></div>
    ${demoNotice()}`;
}

function minihead({ right = '<span class="spacer"></span>' } = {}) {
  return `<header class="minihead">
    <button class="icon-btn" data-action="back" aria-label="Tillbaka">${ICON.back}</button>
    <a class="logo" href="#/">Klubbhuset</a>
    ${right}
  </header>`;
}

function demoNotice() {
  return state.api.mode === "demo"
    ? `<p class="notice"><b>Demoläge.</b> Motorn har inte publicerat några nyheter ännu, så det här är exempel.</p>`
    : "";
}

function storyRow(story, read) {
  return `<a class="row ${read.has(story.id) ? "read" : ""}" href="#/story/${story.id}">
    <div class="text">
      <div class="kicker">${esc(story.section)}</div>
      <h3 class="title">${esc(story.title_sv)}</h3>
      <p>${esc(story.ingress)}</p>
      <div class="meta">${story.outlet_count || 1} ${story.outlet_count > 1 ? "källor" : "källa"} · ${esc(ago(story.last_published_at))}</div>
    </div>
    ${photo(story)}
  </a>`;
}

function mediaRow(item) {
  const isVideo = item.kind === "video";
  const what = `${isVideo ? "Video" : "Podd"} · ${item.outlet}`;
  const where = isVideo ? "Öppnas i YouTube" : "Öppnas i poddappen";
  const when = [formatDuration(item.duration), ago(item.published_at)].filter(Boolean).join(" · ");
  return `<a class="media" href="${esc(item.url)}" target="_blank" rel="noopener">
    <span class="circle">${isVideo ? ICON.play : ICON.headphones}</span>
    <span class="text">
      <span class="what">${esc(what)}</span>
      <span class="name title">${esc(item.original_title)}</span>
      <span class="meta">${esc(when)} · ${where}</span>
    </span>
    <span class="ext">${ICON.external}</span>
  </a>`;
}

const loading = () => { app.innerHTML = `<div class="loading">Hämtar …</div>`; };

// --- Vyer ------------------------------------------------------------------

async function viewFront() {
  const [{ stories, historia, media, lastRun }, read] = await Promise.all([
    state.api.frontPage(),
    state.api.readIds(),
  ]);
  const main = stories.filter((s) => s.section !== "Historia");
  const [lead, ...rest] = main;

  const leadHtml = lead
    ? `<a class="lead ${read.has(lead.id) ? "read" : ""}" href="#/story/${lead.id}">
        <div class="kicker">${esc(lead.section)}${lead.tags && lead.tags[0] ? " · " + esc(lead.tags[0]) : ""}</div>
        <h2 class="title">${esc(lead.title_sv)}</h2>
        <p class="dek">${esc(lead.ingress)}</p>
        ${photo(lead, `Bild från ${(lead.outlets || [])[0] || "källan"}`)}
        ${sourcesLine(lead)}
      </a>`
    : `<div class="empty">Inga nyheter ännu. Motorn fyller på varje timme.</div>`;

  const historiaHtml = historia.length
    ? `<section class="block">
        <div class="block-head"><h2>Historia</h2><a href="#/sektion/historia">Mer historia</a></div>
        <div class="grid2">${historia.map((s) => `
          <a href="#/story/${s.id}" class="${read.has(s.id) ? "read" : ""}">
            <div class="kicker">${esc((s.tags && s.tags[0]) || "Historia")}</div>
            <h3 class="title">${esc(s.title_sv)}</h3>
            <p>${esc(s.ingress)}</p>
            <div class="meta">${s.outlet_count || 1} ${s.outlet_count > 1 ? "källor" : "källa"}</div>
          </a>`).join("")}</div>
      </section>`
    : "";

  const mediaHtml = media.length
    ? `<section class="block">
        <div class="block-head"><h2>YouTube &amp; Poddar</h2><a href="#/sektion/youtube-poddar">Alla avsnitt</a></div>
        ${media.map(mediaRow).join("")}
      </section>`
    : "";

  app.innerHTML = `${masthead("idag")}
    ${leadHtml}
    ${rest.slice(0, 14).map((s) => storyRow(s, read)).join("")}
    ${historiaHtml}
    ${mediaHtml}
    <div class="caught-up"><em>Du är ikapp.</em>
      ${lastRun ? `Senast uppdaterad ${esc(ago(lastRun.finished_at))}` : "Motorn har inte kört än"}
    </div>`;
}

async function viewSection(slug) {
  const section = sectionBySlug(slug);
  if (!section) return viewNotFound();
  if (slug === "youtube-poddar") return viewMedia(new URLSearchParams(location.hash.split("?")[1]).get("typ"));
  const [stories, read] = await Promise.all([
    state.api.section(section.name),
    state.api.readIds(),
  ]);
  app.innerHTML = `${masthead(slug)}
    <div class="page-title"><h1>${esc(section.name)}</h1></div>
    ${stories.length ? stories.map((s) => storyRow(s, read)).join("") : `<div class="empty">Inget här ännu.</div>`}`;
}

async function viewMedia(kind) {
  const items = await state.api.media(kind || null);
  const chip = (value, label) =>
    `<a class="chip ${(kind || "") === value ? "on" : ""}" href="#/sektion/youtube-poddar${value ? "?typ=" + value : ""}">${label}</a>`;
  app.innerHTML = `${masthead("youtube-poddar")}
    <div class="page-title"><h1>YouTube &amp; Poddar</h1><p>Nya videor och avsnitt från dina kanaler. Öppnas i YouTube eller poddappen.</p></div>
    <div class="chips">${chip("", "Alla")}${chip("video", "Video")}${chip("podcast", "Poddar")}</div>
    <div class="px">${items.length ? items.map(mediaRow).join("") : `<div class="empty">Inget här ännu.</div>`}</div>`;
}

async function viewStory(id) {
  const { story, items } = await state.api.story(id);
  if (!story) return viewNotFound();
  const [saved, related] = await Promise.all([state.api.isSaved(story.id), state.api.related(story)]);
  state.api.markRead(story.id);
  state.currentStory = story;

  const outlets = story.outlets || [];
  const angles = (story.angles || []).filter((a) => a.outlet && a.angle);
  const saveBtn = `<button class="icon-btn ${saved ? "on" : ""}" data-action="save" data-id="${story.id}"
      aria-pressed="${saved}" aria-label="${saved ? "Ta bort från Sparat" : "Spara"}">${ICON.bookmark}</button>`;

  app.innerHTML = `${minihead({ right: saveBtn })}
    <article class="story">
      <div class="kicker">${esc(story.section)}${story.tags && story.tags[0] ? " · " + esc(story.tags[0]) : ""}</div>
      <h1>${esc(story.title_sv)}</h1>
      <div class="sources" style="margin-top:0"><span class="badges">${outlets.slice(0, 4).map(badge).join("")}</span>
        <span>${story.summary ? "Sammanfattad ur" : "Från"} <b>${story.outlet_count || 1} ${story.outlet_count > 1 ? "källor" : "källa"}</b> · ${esc(ago(story.last_published_at))}</span></div>
      ${photo(story, `Bild från ${outlets[0] || "källan"}`)}

      ${story.summary
        ? `<div class="label">Sammanfattning</div><div class="summary">${paragraphs(story.summary)}</div>`
        : `<div class="label">Kort notis</div><div class="summary"><p>${esc(story.ingress)}</p></div>
           <p class="notis-note">Källan har bara publicerat en kort text här. Hela nyheten finns hos källan nedan.</p>`}

      ${angles.length >= 2 ? `<section class="angles section-rule"><h2>Så skiljer sig källorna</h2>
        <ul>${angles.map((a) => `<li><b>${esc(a.outlet)}</b> – ${esc(a.angle)}</li>`).join("")}</ul></section>` : ""}

      <section class="section-rule">
        <h2>Läs hela texten hos källan</h2>
        ${items.map((i) => `
          <a class="source-link" href="${esc(i.url)}" target="_blank" rel="noopener">
            ${badge(i.outlet)}
            <span class="text">
              <span class="who">${esc(i.outlet)} · ${esc(shortDate(i.published_at))}</span>
              <span class="orig">”${esc(i.original_title)}”</span>
              <span class="meta">${i.source_words ? readMinutes(i.source_words) + " min hos källan" : "Öppnas hos källan"}</span>
            </span>
            <span class="ext">${ICON.external}</span>
          </a>`).join("")}
      </section>

      ${related.length ? `<section class="related section-rule"><h2>Mer om ${esc(story.tags[0])}</h2>
        ${related.map((r) => `<a href="#/story/${r.id}">
          <span class="kicker">${esc(r.section)} · ${esc(shortDate(r.last_published_at))}</span>
          <h3 class="title">${esc(r.title_sv)}</h3>
          <span class="meta">${r.outlet_count || 1} ${r.outlet_count > 1 ? "källor" : "källa"}</span></a>`).join("")}
      </section>` : ""}

      <p class="ai-note">Sammanfattningen är skriven av AI utifrån källorna ovan. Läs alltid originalet innan du citerar något.</p>
    </article>`;
}

function storyList(stories, emptyText) {
  return stories.length
    ? stories.map((s) => storyRow(s, new Set())).join("")
    : `<div class="empty">${emptyText}</div>`;
}

async function viewSearch(query) {
  const results = query ? await state.api.search(query) : [];
  app.innerHTML = `${minihead()}
    <form class="searchbar" data-form="search" role="search">
      <div class="field" style="margin:0;flex:1">
        <label for="q">Sök i arkivet</label>
        <input id="q" name="q" type="search" value="${esc(query)}" placeholder="Till exempel bunkerslag" autocomplete="off">
      </div>
    </form>
    <p class="notice">Sökningen letar i allt Klubbhuset har samlat. Sökning på hela webben, med uppslag som i skissen, kommer i nästa steg.</p>
    ${query ? storyList(results, `Inget i arkivet om ”${esc(query)}” ännu.`) : ""}`;
  if (!query) document.getElementById("q").focus();
}

async function viewSaved() {
  const [stories, read] = await Promise.all([state.api.saved(), state.api.readIds()]);
  app.innerHTML = `${minihead({ right: `<a class="icon-btn" href="#/installningar" aria-label="Inställningar">${ICON.gear}</a>` })}
    <div class="page-title"><h1>Sparat</h1><p>Det du sparar ligger på den här enheten.</p></div>
    ${stories.length ? stories.map((s) => storyRow(s, read)).join("")
      : `<div class="empty">Inget sparat ännu. Tryck på bokmärket i en nyhet för att spara den.</div>`}`;
}

async function viewSettings() {
  app.innerHTML = `${minihead()}
    <div class="page-title"><h1>Inställningar</h1></div>
    <section class="settings">
      <div class="block-head"><h2>Utseende</h2></div>
      <div class="chips" role="group" aria-label="Tema">
        ${[["auto", "Som telefonen"], ["light", "Ljust"], ["dark", "Mörkt"]].map(([value, label]) =>
          `<button class="chip ${local.theme() === value ? "on" : ""}" data-action="theme" data-value="${value}"
            aria-pressed="${local.theme() === value}">${label}</button>`).join("")}
      </div>
    </section>
    <section class="settings">
      <div class="block-head"><h2>Drift</h2></div>
    </section>
    <a class="row" href="#/halsa"><div class="text"><h3 class="title">Källornas hälsa</h3>
      <p>Vilka flöden som svarar och när de senast gav något nytt.</p></div></a>`;
}

async function viewHealth() {
  const { sources, last_run: lastRun } = await state.api.health();
  const weekAgo = Date.now() - 7 * 24 * 3600 * 1000;
  const rows = sources.map((s) => {
    const quiet = !s.last_new_item_at || new Date(s.last_new_item_at) < weekAgo;
    return `<tr>
      <td>${esc(s.name)}<div class="meta">${esc(s.kind)}</div></td>
      <td class="${s.last_error ? "bad" : ""}">${s.last_error ? esc(s.last_error) : s.last_ok_at ? "OK " + esc(ago(s.last_ok_at)) : "Inte kontrollerad"}</td>
      <td class="${quiet ? "bad" : ""}">${s.last_new_item_at ? esc(ago(s.last_new_item_at)) : "Aldrig"}</td>
    </tr>`;
  }).join("");
  app.innerHTML = `${minihead()}
    <div class="page-title"><h1>Källornas hälsa</h1><p>${lastRun ? `Motorn körde senast ${esc(ago(lastRun.finished_at))}. ` : ""}Rött betyder fel vid senaste hämtningen, eller inget nytt på en vecka.</p></div>
    <div class="px"><table class="health"><thead><tr><th>Källa</th><th>Senaste hämtning</th><th>Senast nytt</th></tr></thead>
    <tbody>${rows}</tbody></table></div>`;
}

function viewNotFound() {
  app.innerHTML = `${minihead()}<div class="empty">Den här sidan finns inte.</div>`;
}

// --- Router och händelser ----------------------------------------------------

function activeTab(route) {
  const tab = route.startsWith("sok") ? "sok"
    : route.startsWith("sparat") ? "sparat"
    : /^(installningar|sektioner|halsa)/.test(route) ? "sparat"
    : "idag";
  document.querySelectorAll(".tabbar a").forEach((a) =>
    a.classList.toggle("active", a.dataset.tab === tab));
}

async function render() {
  const route = location.hash.replace(/^#\/?/, "");
  const [path, query = ""] = route.split("?");
  const parts = path.split("/").filter(Boolean);
  activeTab(path);
  loading();
  try {
    if (!parts.length) await viewFront();
    else if (parts[0] === "story" && parts[1]) await viewStory(Number(parts[1]));
    else if (parts[0] === "sektion" && parts[1]) await viewSection(parts[1]);
    else if (parts[0] === "installningar" || parts[0] === "sektioner") await viewSettings();
    else if (parts[0] === "sok") await viewSearch(new URLSearchParams(query).get("q") || "");
    else if (parts[0] === "sparat") await viewSaved();
    else if (parts[0] === "halsa") await viewHealth();
    else viewNotFound();
  } catch (error) {
    console.error(error);
    app.innerHTML = `${minihead()}<div class="empty">Kunde inte hämta nyheterna just nu.<br>
      <button class="btn" style="margin-top:16px" data-action="retry">Försök igen</button></div>`;
  }
  const activeSection = document.querySelector(".sectionnav a.active");
  if (activeSection) {
    const nav = activeSection.parentElement;
    nav.scrollLeft = activeSection.offsetLeft - nav.clientWidth / 2 + activeSection.clientWidth / 2;
  }
  const nav = document.querySelector(".sectionnav");
  if (nav) nav.addEventListener("scroll", updateNavFade, { passive: true });
  window.scrollTo(0, 0);
  updateNavFade();
  updateCompact();
}

// Tidningshuvudet krymper till en smal rad när sektionsraden har fastnat i toppen
function updateCompact() {
  const wrap = document.querySelector(".navwrap");
  const stuck = !!wrap && wrap.getBoundingClientRect().top <= 1 && window.scrollY > 0;
  document.body.classList.toggle("compact", stuck);
}

// Tona ut högerkanten så länge det finns fler sektioner att svepa fram
function updateNavFade() {
  const nav = document.querySelector(".sectionnav");
  if (!nav) return;
  const more = nav.scrollLeft + nav.clientWidth < nav.scrollWidth - 4;
  nav.parentElement.classList.toggle("more", more);
}

window.addEventListener("scroll", updateCompact, { passive: true });
window.addEventListener("resize", updateNavFade);

document.addEventListener("click", async (event) => {
  const target = event.target.closest("[data-action]");
  if (!target) return;
  const action = target.dataset.action;
  if (action === "back") {
    if (history.length > 1) history.back();
    else location.hash = "#/";
  } else if (action === "retry") {
    render();
  } else if (action === "top") {
    window.scrollTo({ top: 0, behavior: "smooth" });
  } else if (action === "theme") {
    local.setTheme(target.dataset.value);
    applyTheme(target.dataset.value);
    render();
  } else if (action === "save") {
    const on = target.getAttribute("aria-pressed") !== "true";
    target.setAttribute("aria-pressed", String(on));
    target.classList.toggle("on", on);
    target.setAttribute("aria-label", on ? "Ta bort från Sparat" : "Spara");
    await state.api.setSaved(state.currentStory, on);
  }
});

document.addEventListener("submit", async (event) => {
  const form = event.target.closest("[data-form]");
  if (!form) return;
  event.preventDefault();
  if (form.dataset.form === "search") {
    const q = new FormData(form).get("q").toString().trim();
    location.hash = `#/sok?q=${encodeURIComponent(q)}`;
  }
});

window.addEventListener("hashchange", render);

(async function start() {
  applyTheme(local.theme());
  darkQuery.addEventListener("change", () => { if (local.theme() === "auto") render(); });
  state.api = await createApi();
  await render();
  if ("serviceWorker" in navigator && location.protocol === "https:") {
    navigator.serviceWorker.register("sw.js").catch(() => {});
  }
})();
