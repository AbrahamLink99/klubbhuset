// Datalagret. Läser nyheterna som motorn har publicerat i api/, eller visar demodata
// om motorn inte har publicerat något ännu.

import { local } from "./local.js";

const SLUGS = {
  Touren: "touren", Utrustning: "utrustning", Teknik: "teknik", Spelare: "spelare", Historia: "historia",
};

async function getJson(path) {
  const response = await fetch(`api/${path}`, { cache: "no-cache" });
  if (!response.ok) throw new Error(`${path}: ${response.status}`);
  return response.json();
}

function matches(story, terms) {
  const haystack = [story.title_sv, story.ingress, ...(story.tags || []), ...(story.players || [])]
    .join(" ")
    .toLowerCase();
  return terms.every((t) => haystack.includes(t));
}

function liveApi() {
  let searchIndex = null;
  return {
    mode: "live",
    async frontPage() {
      const front = await getJson("front.json");
      return {
        stories: front.stories,
        historia: front.historia,
        media: front.media,
        lastRun: front.last_run,
      };
    },
    async section(name) {
      return getJson(`sections/${SLUGS[name]}.json`);
    },
    async media(kind) {
      const items = await getJson("media.json");
      return kind ? items.filter((m) => m.kind === kind) : items;
    },
    async story(id) {
      try {
        return await getJson(`stories/${Number(id)}.json`);
      } catch {
        return { story: null, items: [] };
      }
    },
    async related(story) {
      return story.related || [];
    },
    async search(text) {
      const terms = text.toLowerCase().split(/\s+/).filter(Boolean);
      if (!terms.length) return [];
      searchIndex = searchIndex || (await getJson("search.json"));
      return searchIndex.filter((s) => matches(s, terms)).slice(0, 40);
    },
    async health() {
      return getJson("health.json");
    },
  };
}

async function demoApi() {
  const { DEMO } = await import("./demo.js");
  const byId = (id) => DEMO.stories.find((s) => s.id === Number(id));
  const recent = (a, b) => b.last_published_at.localeCompare(a.last_published_at);
  return {
    mode: "demo",
    async frontPage() {
      return {
        stories: [...DEMO.stories].sort((a, b) => b.score - a.score),
        historia: DEMO.stories.filter((s) => s.section === "Historia").slice(0, 2),
        media: DEMO.media.slice(0, 4),
        lastRun: null,
      };
    },
    async section(name) {
      return DEMO.stories.filter((s) => s.section === name).sort(recent);
    },
    async media(kind) {
      return DEMO.media.filter((m) => !kind || m.kind === kind);
    },
    async story(id) {
      const story = byId(id);
      return { story, items: DEMO.items.filter((i) => i.story_id === Number(id)) };
    },
    async related(story) {
      return DEMO.stories
        .filter((s) => s.id !== story.id && s.tags.some((t) => story.tags.includes(t)))
        .slice(0, 3);
    },
    async search(text) {
      const terms = text.toLowerCase().split(/\s+/).filter(Boolean);
      return DEMO.stories.filter((s) => matches(s, terms));
    },
    async health() {
      return { last_run: null, sources: DEMO.health };
    },
  };
}

export async function createApi() {
  const base = await (async () => {
    try {
      await getJson("front.json");
      return liveApi();
    } catch {
      return demoApi();
    }
  })();
  return {
    ...base,
    saved: async () => local.saved(),
    isSaved: async (id) => local.isSaved(id),
    setSaved: async (story, on) => local.setSaved(story, on),
    readIds: async () => local.readIds(),
    markRead: async (id) => local.markRead(id),
  };
}
