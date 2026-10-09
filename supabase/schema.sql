-- Klubbhuset – databasschema för Supabase
-- Kör hela filen en gång i Supabase: SQL Editor → New query → klistra in → Run.
-- Filen går att köra igen utan att något förstörs.

-- ---------------------------------------------------------------------------
-- Källor (fylls och uppdateras av motorn från sources.yaml och players.yaml)
-- ---------------------------------------------------------------------------
create table if not exists public.sources (
  id                text primary key,
  name              text not null,
  outlet            text,
  kind              text not null check (kind in ('article', 'youtube', 'podcast', 'news_search')),
  site              text,
  feed              text not null,
  language          text,
  weight            real not null default 1.0,
  paywall           boolean not null default false,
  active            boolean not null default true,
  player            text,
  last_checked_at   timestamptz,
  last_ok_at        timestamptz,
  last_new_item_at  timestamptz,
  last_error        text,
  updated_at        timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Stories: en nyhet, sammanställd ur en eller flera artiklar
-- ---------------------------------------------------------------------------
create table if not exists public.stories (
  id                  bigint generated always as identity primary key,
  section             text not null,
  title_sv            text not null,
  ingress             text not null,
  summary             text not null,
  angles              jsonb not null default '[]'::jsonb,
  tags                text[] not null default '{}',
  players             text[] not null default '{}',
  outlets             text[] not null default '{}',
  outlet_count        int not null default 1,
  weight              real not null default 1.0,
  image_url           text,
  score               real not null default 0,
  first_published_at  timestamptz not null default now(),
  last_published_at   timestamptz not null default now(),
  needs_synthesis     boolean not null default false,
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now()
);

create index if not exists stories_last_published_idx on public.stories (last_published_at desc);
create index if not exists stories_score_idx on public.stories (score desc);
create index if not exists stories_section_idx on public.stories (section, last_published_at desc);
create index if not exists stories_tags_idx on public.stories using gin (tags);

-- ---------------------------------------------------------------------------
-- Items: varje artikel, video eller poddavsnitt som motorn har hittat.
-- Hela artiklar sparas aldrig – bara rubrik, kort utdrag och AI-sammanfattning.
-- ---------------------------------------------------------------------------
create table if not exists public.items (
  id              bigint generated always as identity primary key,
  source_id       text not null references public.sources (id) on update cascade on delete cascade,
  kind            text not null check (kind in ('article', 'video', 'podcast')),
  url             text not null unique,
  outlet          text not null,
  original_title  text not null,
  excerpt         text,
  image_url       text,
  duration        text,
  published_at    timestamptz,
  fetched_at      timestamptz not null default now(),
  source_words    int,
  pending_text    text,  -- flödets text i väntan på sammanfattning; töms direkt efteråt
  status          text not null default 'new' check (status in ('new', 'ready', 'skipped', 'failed')),
  attempts        int not null default 0,
  last_error      text,
  title_sv        text,
  ingress         text,
  summary         text,
  section         text,
  tags            text[] not null default '{}',
  players         text[] not null default '{}',
  story_id        bigint references public.stories (id) on delete set null
);

create index if not exists items_status_idx on public.items (status, published_at desc);
create index if not exists items_kind_idx on public.items (kind, published_at desc);
create index if not exists items_story_idx on public.items (story_id);

-- ---------------------------------------------------------------------------
-- Körningar: en rad per gång motorn har kört (för hälsovyn)
-- ---------------------------------------------------------------------------
create table if not exists public.runs (
  id               bigint generated always as identity primary key,
  started_at       timestamptz not null default now(),
  finished_at      timestamptz,
  feeds_ok         int not null default 0,
  feeds_failed     int not null default 0,
  new_items        int not null default 0,
  summarized       int not null default 0,
  stories_created  int not null default 0,
  stories_updated  int not null default 0,
  errors           jsonb not null default '[]'::jsonb
);

-- ---------------------------------------------------------------------------
-- Personligt: sparat och läst. Kopplat till inloggad användare.
-- ---------------------------------------------------------------------------
create table if not exists public.saved (
  user_id   uuid not null default auth.uid() references auth.users (id) on delete cascade,
  story_id  bigint not null references public.stories (id) on delete cascade,
  saved_at  timestamptz not null default now(),
  primary key (user_id, story_id)
);

create table if not exists public.read_state (
  user_id   uuid not null default auth.uid() references auth.users (id) on delete cascade,
  story_id  bigint not null references public.stories (id) on delete cascade,
  read_at   timestamptz not null default now(),
  primary key (user_id, story_id)
);

-- ---------------------------------------------------------------------------
-- Behörigheter (Row Level Security)
-- Appen får läsa allt innehåll. Sparat och läst syns bara för den som är inloggad.
-- Motorn skriver via databasanslutningen och påverkas inte av reglerna.
-- ---------------------------------------------------------------------------
alter table public.sources    enable row level security;
alter table public.stories    enable row level security;
alter table public.items      enable row level security;
alter table public.runs       enable row level security;
alter table public.saved      enable row level security;
alter table public.read_state enable row level security;

drop policy if exists "Innehåll är läsbart" on public.sources;
create policy "Innehåll är läsbart" on public.sources for select to anon, authenticated using (true);

drop policy if exists "Innehåll är läsbart" on public.stories;
create policy "Innehåll är läsbart" on public.stories for select to anon, authenticated using (true);

drop policy if exists "Innehåll är läsbart" on public.items;
create policy "Innehåll är läsbart" on public.items for select to anon, authenticated using (true);

drop policy if exists "Innehåll är läsbart" on public.runs;
create policy "Innehåll är läsbart" on public.runs for select to anon, authenticated using (true);

drop policy if exists "Egna sparade" on public.saved;
create policy "Egna sparade" on public.saved for all to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());

drop policy if exists "Egen läsning" on public.read_state;
create policy "Egen läsning" on public.read_state for all to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());

grant select on public.sources, public.stories, public.items, public.runs to anon, authenticated;
grant select, insert, update, delete on public.saved, public.read_state to authenticated;
