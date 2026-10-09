# Klubbhuset

Din personliga golftidning. En motor hämtar ett hundratal golfkällor varje timme, låter AI skriva svenska sammanfattningar och väver ihop nyheter som flera sajter skriver om. Appen visar allt i Dagstidningens design, och för hela texten går du till källan.

Allt körs på GitHub – inga andra konton eller databaser behövs.

**Appens adress:** https://abrahamlink99.github.io/klubbhuset/

---

## Kom igång – två steg

### 1. Lägg in AI-nyckeln

1. Skapa en nyckel på [platform.claude.com](https://platform.claude.com) under *API keys* (fyll på några dollar under *Billing* om du inte redan har gjort det). Nyckeln börjar med `sk-ant-`.
2. Här i repot: **Settings → Secrets and variables → Actions → New repository secret**.
3. Name: `ANTHROPIC_API_KEY`. Secret: klistra in nyckeln. Klicka **Add secret**.

### 2. Slå på GitHub Pages

1. **Settings → Pages**.
2. Under *Build and deployment*, välj **Source: GitHub Actions**.

Klart. Motorn kör nästa hel timme (klockan :07). Vill du inte vänta: **Actions → Motorn → Run workflow**.

### På telefonen

Öppna appens adress i Safari, tryck **Dela → Lägg till på hemskärmen**.

---

## Så fungerar det

```
sources.yaml, players.yaml   Källorna och spelarna du följer
motor/                       Motorn (Python)
web/                         Appen (HTML/JS)
.github/workflows/motorn.yml Kör motorn och publicerar appen
grenen "arkiv"               Arkivet: alla sammanfattningar, i en komprimerad fil
```

Varje körning:
1. hämtar arkivet från grenen `arkiv`,
2. hämtar nya artiklar, videor och poddavsnitt,
3. låter Claude skriva svensk rubrik, ingress och sammanfattning och grupperar stories,
4. sparar arkivet tillbaka till `arkiv`,
5. bygger appen med nyheterna som JSON-filer och publicerar den på GitHub Pages.

Utan AI-nyckel hämtas och sparas artiklarna ändå, och sammanfattas när nyckeln finns på plats. YouTube och poddar syns direkt.

**Sparat** och vilka nyheter du har läst sparas i telefonens webbläsare – de följer inte med till andra enheter.

## Ändra saker

| Vad | Var |
| --- | --- |
| Lägga till eller ta bort en källa | `sources.yaml`. `weight: 1.0` = Ja, `0.5` = Kanske, `active: false` = Nej |
| Spelare du följer | `players.yaml` |
| Hur ofta motorn kör | `cron` i `.github/workflows/motorn.yml` (tiderna är i UTC) |
| Sammanfattningarnas längd | `SUMMARY_MAX_SHARE` (andel av originalet, standard 0.25) och `SUMMARY_MAX_WORDS` (tak, standard 450) under `env:` i `motorn.yml` |
| Antal artiklar per körning | `MAX_ARTICLES_PER_RUN` (standard 40) |

När `sources.yaml` eller `players.yaml` ändras körs **Testa flöden** automatiskt och visar vilka källor som svarar.

## Om något inte fungerar

- **Sektioner → Källornas hälsa** i appen visar vilka flöden som felar eller inte gett något nytt på en vecka.
- **Actions → Motorn** visar loggen från varje körning. En gul varning där säger om AI-nyckeln saknas eller om GitHub Pages inte är påslaget.
- Radera aldrig grenen `arkiv` – där ligger alla sammanfattningar.

## Bra att veta

- Repot och appen är publika: den som har adressen kan läsa sammanfattningarna. AI-nyckeln är hemlig och syns aldrig.
- GitHub Actions är gratis för publika repon. Motorn sparar arkivet varje körning, så repot räknas som aktivt.
- AI-kostnaden är runt 5 dollar i månaden med nuvarande inställningar.

## Principer

- Appen visar sammanfattningar och länkar till källan, aldrig hela artiklar. Brödtext läses bara för att AI ska kunna sammanfatta och sparas inte.
- Sammanfattningen får bli högst en fjärdedel av originalets längd (max 450 ord) och längre för stories med flera källor.
- Originalrubriken och källan visas alltid.

## Utveckling

```bash
cd motor
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt pytest
python -m pytest                              # testerna
python -m klubbhuset_motor.run --check-feeds  # testa flödena
python -m klubbhuset_motor.run                # en körning (arkiv/ och site/ skapas i repot)
```

Appen kan provas med `python -m http.server` i `site/` efter en körning, eller i `web/` för demodata.
