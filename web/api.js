// Datalagret. Pratar med Supabase, eller visar demodata om config.js är tom.

import { SUPABASE_URL, SUPABASE_ANON_KEY } from "./config.js";

const STORY_FIELDS =
  "id, section, title_sv, ingress, image_url, outlets, outlet_count, tags, last_published_at";
const MEDIA_FIELDS = "id, kind, outlet, original_title, url, image_url, duration, published_at";
const hoursAgo = (h) => new Date(Date.now() - h * 3600 * 1000).toISOString();

function liveApi(sb) {
  const must = ({ data, error }) => {
    if (error) throw error;
    return data;
  };

  return {
    mode: "live",

    async frontPage() {
      const [stories, historia, media, runs] = await Promise.all([
        sb.from("stories").select(STORY_FIELDS).gte("last_published_at", hoursAgo(72))
          .order("score", { ascending: false }).limit(40),
        sb.from("stories").select(STORY_FIELDS).eq("section", "Historia")
          .order("last_published_at", { ascending: false }).limit(2),
        sb.from("items").select(MEDIA_FIELDS).in("kind", ["video", "podcast"])
          .order("published_at", { ascending: false }).limit(4),
        sb.from("runs").select("finished_at, new_items").not("finished_at", "is", null)
          .order("finished_at", { ascending: false }).limit(1),
      ]);
      return {
        stories: must(stories),
        historia: must(historia),
        media: must(media),
        lastRun: must(runs)[0] || null,
      };
    },

    async section(name) {
      return must(await sb.from("stories").select(STORY_FIELDS).eq("section", name)
        .order("last_published_at", { ascending: false }).limit(40));
    },

    async media(kind) {
      let q = sb.from("items").select(MEDIA_FIELDS)
        .order("published_at", { ascending: false }).limit(50);
      q = kind ? q.eq("kind", kind) : q.in("kind", ["video", "podcast"]);
      return must(await q);
    },

    async story(id) {
      const [story, items] = await Promise.all([
        sb.from("stories").select("*").eq("id", id).maybeSingle(),
        sb.from("items").select("id, outlet, original_title, url, published_at, source_words")
          .eq("story_id", id).eq("status", "ready").order("published_at", { ascending: true }),
      ]);
      return { story: must(story), items: must(items) };
    },

    async related(story) {
      if (!story.tags || !story.tags.length) return [];
      return must(await sb.from("stories").select(STORY_FIELDS).overlaps("tags", story.tags)
        .neq("id", story.id).order("last_published_at", { ascending: false }).limit(3));
    },

    async search(text) {
      const term = text.replace(/[%,()]/g, " ").trim();
      if (!term) return [];
      return must(await sb.from("stories").select(STORY_FIELDS)
        .or(`title_sv.ilike.%${term}%,ingress.ilike.%${term}%,summary.ilike.%${term}%`)
        .order("last_published_at", { ascending: false }).limit(30));
    },

    async user() {
      const { data } = await sb.auth.getSession();
      return data.session ? data.session.user : null;
    },
    onAuthChange(callback) {
      sb.auth.onAuthStateChange((_event, session) => callback(session ? session.user : null));
    },
    async signIn(email) {
      must(await sb.auth.signInWithOtp({
        email,
        options: { emailRedirectTo: location.origin + location.pathname },
      }));
    },
    async signOut() {
      await sb.auth.signOut();
    },

    async saved() {
      const rows = must(await sb.from("saved").select(`saved_at, stories(${STORY_FIELDS})`)
        .order("saved_at", { ascending: false }));
      return rows.map((r) => r.stories).filter(Boolean);
    },
    async isSaved(id) {
      const rows = must(await sb.from("saved").select("story_id").eq("story_id", id));
      return rows.length > 0;
    },
    async setSaved(id, on) {
      if (on) must(await sb.from("saved").upsert({ story_id: id }, { onConflict: "user_id,story_id", ignoreDuplicates: true }));
      else must(await sb.from("saved").delete().eq("story_id", id));
    },
    async readIds() {
      const rows = must(await sb.from("read_state").select("story_id").gte("read_at", hoursAgo(24 * 7)));
      return new Set(rows.map((r) => r.story_id));
    },
    async markRead(id) {
      await sb.from("read_state").upsert({ story_id: id }, { onConflict: "user_id,story_id", ignoreDuplicates: true });
    },

    async health() {
      return must(await sb.from("sources")
        .select("id, name, kind, active, last_checked_at, last_ok_at, last_new_item_at, last_error")
        .eq("active", true).order("kind").order("name"));
    },
  };
}

async function demoApi() {
  const { DEMO } = await import("./demo.js");
  const saved = new Set();
  const read = new Set();
  let user = null;
  const listeners = [];
  const byId = (id) => DEMO.stories.find((s) => s.id === Number(id));
  const recent = (a, b) => b.last_published_at.localeCompare(a.last_published_at);

  return {
    mode: "demo",
    async frontPage() {
      return {
        stories: [...DEMO.stories].sort((a, b) => b.score - a.score),
        historia: DEMO.stories.filter((s) => s.section === "Historia").slice(0, 2),
        media: DEMO.media.slice(0, 4),
        lastRun: { finished_at: hoursAgo(0.4), new_items: 38 },
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
      const t = text.toLowerCase();
      return DEMO.stories.filter((s) =>
        [s.title_sv, s.ingress, s.summary].join(" ").toLowerCase().includes(t));
    },
    async user() { return user; },
    onAuthChange(cb) { listeners.push(cb); },
    async signIn(email) {
      user = { email };
      listeners.forEach((cb) => cb(user));
    },
    async signOut() {
      user = null;
      listeners.forEach((cb) => cb(null));
    },
    async saved() { return DEMO.stories.filter((s) => saved.has(s.id)); },
    async isSaved(id) { return saved.has(Number(id)); },
    async setSaved(id, on) { on ? saved.add(Number(id)) : saved.delete(Number(id)); },
    async readIds() { return read; },
    async markRead(id) { read.add(Number(id)); },
    async health() { return DEMO.health; },
  };
}

export async function createApi() {
  if (SUPABASE_URL && SUPABASE_ANON_KEY) {
    const { createClient } = await import(
      "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.45.4/+esm"
    );
    return liveApi(createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
      auth: { persistSession: true, detectSessionInUrl: true },
    }));
  }
  return demoApi();
}
