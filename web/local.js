// Det som är personligt – sparat och läst – ligger i telefonens webbläsare.
// Allt är inlindat så att appen fungerar även om lagringen är avstängd (t.ex. privat läge).

const SAVED_KEY = "klubbhuset.saved.v1";
const READ_KEY = "klubbhuset.read.v1";
const READ_MAX = 2000;

function load(key, fallback) {
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}

function store(key, value) {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* lagringen är full eller avstängd – appen fungerar ändå */
  }
}

const SNAPSHOT_FIELDS = [
  "id", "section", "title_sv", "ingress", "image_url", "outlets", "outlet_count", "tags", "last_published_at",
];

export const local = {
  saved() {
    return load(SAVED_KEY, []);
  },
  isSaved(id) {
    return this.saved().some((s) => s.id === Number(id));
  },
  setSaved(story, on) {
    const others = this.saved().filter((s) => s.id !== Number(story.id));
    if (on) {
      const snapshot = Object.fromEntries(SNAPSHOT_FIELDS.map((k) => [k, story[k]]));
      others.unshift({ ...snapshot, saved_at: new Date().toISOString() });
    }
    store(SAVED_KEY, others);
  },
  readIds() {
    return new Set(load(READ_KEY, []));
  },
  markRead(id) {
    const ids = load(READ_KEY, []).filter((x) => x !== Number(id));
    ids.unshift(Number(id));
    store(READ_KEY, ids.slice(0, READ_MAX));
  },
};
