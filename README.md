# Klubbhuset

Din personliga golftidning. En motor hämtar ett hundratal golfkällor varje timme, låter AI skriva svenska sammanfattningar och väver ihop nyheter som flera sajter skriver om. Appen visar allt i Dagstidningens design, och för hela texten går du till källan.

```
sources.yaml, players.yaml   Källorna och spelarna du följer
motor/                       Motorn (Python) – körs av GitHub Actions
supabase/schema.sql          Databasen
web/                         Appen (HTML/JS) – publiceras av Netlify
.github/workflows/           Motorn varje timme, flödestest och tester
```

---

## Kom igång – steg för steg

Räkna med ungefär 30 minuter. Klistra aldrig in nycklar i chattar eller i koden, utom de två värdena i `web/config.js` som är gjorda för att vara publika.

### 1. Supabase – databasen

1. Skapa ett projekt på [supabase.com](https://supabase.com). Välj en region i Europa och spara databaslösenordet du väljer.
2. Gå till **SQL Editor → New query**, klistra in hela `supabase/schema.sql` och klicka **Run**.
3. Hämta tre saker:
   - **Project URL** och **anon public key**: *Project Settings → API*. De ska till appen (steg 5).
   - **Anslutningssträngen** till motorn: klicka **Connect** högst upp och välj **Session pooler**. Den ser ut ungefär så här: `postgresql://postgres.abcxyz:[DITT-LÖSENORD]@aws-0-eu-north-1.pooler.supabase.com:5432/postgres`. Byt ut `[DITT-LÖSENORD]` mot lösenordet.
     > Välj *Session pooler*, inte *Direct connection*. GitHub Actions når bara IPv4, och den direkta anslutningen är IPv6 på gratisplanen.

### 2. Anthropic – AI:n

1. Logga in på [platform.claude.com](https://platform.claude.com), fyll på med till exempel 10 dollar under *Billing*.
2. Skapa en nyckel under *API keys*. Den börjar med `sk-ant-`.

### 3. GitHub – motorn

1. I repot: **Settings → Secrets and variables → Actions → New repository secret**. Lägg till två hemligheter:
   - `DATABASE_URL` – anslutningssträngen från steg 1.3
   - `ANTHROPIC_API_KEY` – nyckeln från steg 2
2. Gå till fliken **Actions**. Om GitHub frågar, klicka för att aktivera arbetsflödena.
3. Kör **Testa flöden → Run workflow**. Efter någon minut visar loggen vilka av källorna som svarar. Inga nycklar behövs för det.
4. Kör **Motorn → Run workflow**. Första körningen sammanfattar upp till 40 artiklar. Därefter går motorn av sig själv varje timme kl. 06–23 och två gånger på natten.

### 4. Netlify – appen

1. På [netlify.com](https://netlify.com): **Add new site → Import an existing project → GitHub → klubbhuset**.
2. Inställningarna läses från `netlify.toml` – klicka bara **Deploy**. Du får en adress som `https://något-namn.netlify.app`. Du kan byta namn under *Site configuration → Change site name*, till exempel `klubbhuset-linus`.

### 5. Koppla ihop appen med databasen

1. Öppna `web/config.js` och fyll i `SUPABASE_URL` och `SUPABASE_ANON_KEY` från steg 1.3. Spara och pusha – Netlify publicerar automatiskt.
2. I Supabase: **Authentication → URL Configuration**. Sätt *Site URL* till din Netlify-adress och lägg till samma adress under *Redirect URLs*.

### 6. På telefonen

1. Öppna Netlify-adressen i Safari.
2. Tryck **Dela → Lägg till på hemskärmen**.
3. Gå till **Sparat**, skriv din e-post och tryck på länken du får. Nu sparas det du bokmärker och appen minns vad du har läst.
4. Stäng sedan dörren för andra: i Supabase, **Authentication → Sign In / Providers**, slå av *Allow new users to sign up*.

---

## Ändra saker

| Vad | Var |
| --- | --- |
| Lägga till eller ta bort en källa | `sources.yaml`. `weight: 1.0` = Ja, `0.5` = Kanske, `active: false` = Nej |
| Spelare du följer | `players.yaml` |
| Hur ofta motorn kör | `cron` i `.github/workflows/motorn.yml` (tiderna är i UTC) |
| Sammanfattningarnas längd | `SUMMARY_MAX_SHARE` (andel av originalet, standard 0.25) och `SUMMARY_MAX_WORDS` (tak, standard 450). Lägg till under `env:` i `motorn.yml` |
| Antal artiklar per körning | `MAX_ARTICLES_PER_RUN` (standard 40) |
| AI-modell | `KLUBBHUSET_MODEL` (standard `claude-haiku-5-5`) |

Ändringar i `sources.yaml` och `players.yaml` gäller från nästa körning.

## Om något inte fungerar

- **Källornas hälsa** i appen (*Sektioner → Källornas hälsa*) visar vilka flöden som felar eller inte gett något nytt på en vecka.
- **Actions → Motorn** visar loggen från varje körning, med antal nya artiklar, sammanfattningar och fel.
- **Inga nyheter i appen:** kontrollera att `web/config.js` är ifylld och att Motorn har kört minst en gång utan fel.
- **Inloggningslänken leder fel:** kontrollera *Site URL* och *Redirect URLs* i steg 5.2.

## Kostnader

- GitHub Actions: gratis och obegränsat så länge repot är publikt. Görs repot privat ryms cirka 20 körningar om dagen à ett par minuter i gratisminuterna (2 000 i månaden).
  > I publika repon stänger GitHub av schemalagda körningar om ingenting har hänt i repot på 60 dagar. Du får ett mejl innan. Det räcker att göra en ändring, till exempel i `sources.yaml`, eller att slå på arbetsflödet igen under Actions.
- Supabase och Netlify: gratisplanerna räcker.
- Anthropic: runt 5 dollar i månaden för sammanfattningarna med nuvarande inställningar.

## Utveckling

```bash
cd motor
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt pytest
python -m pytest                              # databastesterna kräver KH_TEST_DATABASE_URL
python -m klubbhuset_motor.run --check-feeds  # testa flödena lokalt
```

Appen kan provas lokalt med `python -m http.server` i mappen `web/`. Utan ifylld `config.js` visas demodata.

## Principer

- Appen visar sammanfattningar och länkar till källan, aldrig hela artiklar. Brödtext läses bara för att AI ska kunna sammanfatta och sparas inte.
- Sammanfattningen får bli högst en fjärdedel av originalets längd (max 450 ord) och längre för stories med flera källor.
- Originalrubriken och källan visas alltid.
