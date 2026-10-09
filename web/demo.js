// Demodata som visas tills motorn har publicerat riktiga nyheter. Rubriker, källor och avsnitt är exempel.

const ago = (h) => new Date(Date.now() - h * 3600 * 1000).toISOString();

export const DEMO = {
  stories: [
    {
      id: 1, section: "Touren", score: 3.1, last_published_at: ago(1),
      title_sv: "Elva månader kvar till Adare Manor – så ser vägen till Ryder Cup ut",
      ingress: "Irland står värd för första gången sedan 2006. Fyra källor om hur lagen tas ut, vilka tävlingar som väger tyngst och vad banan i Limerick kräver.",
      summary: "Ryder Cup spelas på Adare Manor i grevskapet Limerick hösten 2027. Det är första gången tävlingen avgörs på irländsk mark sedan The K Club 2006.\n\nBanan byggdes om helt inför tävlingen, och floden som rinner genom anläggningen är i spel på flera av hålen. Europa går in som regerande mästare efter segern på Bethpage Black 2025.\n\nKvalificeringen till båda lagen pågår redan. Källorna går igenom hur poängen räknas och vilka tävlingar som väger tyngst fram till nästa höst.",
      angles: [
        { outlet: "Ryder Cup", angle: "Beskriver banan och förberedelserna på plats." },
        { outlet: "Svensk Golf", angle: "Följer de svenska spelarna och deras chanser till en plats i laget." },
        { outlet: "Golf Monthly", angle: "Samlar det praktiska: datum, format och biljetter." },
      ],
      outlets: ["Ryder Cup", "Golf Monthly", "Golf Digest", "Svensk Golf"], outlet_count: 4,
      tags: ["Ryder Cup 2027", "Adare Manor"], image_url: null,
    },
    {
      id: 2, section: "Utrustning", score: 1.4, last_published_at: ago(3),
      title_sv: "Tvåårscykeln: därför byts Pro V1 ut vartannat år",
      ingress: "Vad förändras egentligen mellan generationerna – och märks det för en amatör?",
      summary: "Titleist uppdaterar Pro V1 och Pro V1x i en fast rytm, och nästa generation väntas enligt källorna under 2027.\n\nTesterna visar att skillnaderna mellan två generationer oftast handlar om spinn i närspelet och känsla, snarare än längd från tee.",
      angles: [], outlets: ["MyGolfSpy", "GOLF.com", "Golf Monthly"], outlet_count: 3,
      tags: ["Titleist", "Pro V1", "Golfbollar"], image_url: null,
    },
    {
      id: 3, section: "Teknik", score: 1.2, last_published_at: ago(5),
      title_sv: "Därför fastnar bunkerslaget – fyra fel som de flesta amatörer gör",
      ingress: "Bladet, bollpositionen och var klubban tar sanden. Coacherna är förvånansvärt överens.",
      summary: "Det vanligaste felet är att bladet stängs genom träffen, så att klubbans studs inte kommer till användning.\n\nDärefter kommer bollen för långt bak i stansen, vikten på bakre foten och för lite fart genom sanden.",
      angles: [], outlets: ["Golf Monthly"], outlet_count: 1,
      tags: ["Bunkerspel", "Närspel"], image_url: null,
    },
    {
      id: 4, section: "Spelare", score: 1.0, last_published_at: ago(7),
      title_sv: "Så läser du en WITB-lista – och vad den inte säger om din egen bag",
      ingress: "Proffsens klubbor är byggda för deras svinghastighet. Här är vad som går att låna.",
      summary: "En WITB-lista visar vilka klubbor, skaft och bollar ett proffs använder, men sällan varför.\n\nLoft, lie och skaft är anpassade till en svinghastighet som få amatörer har.",
      angles: [], outlets: ["GolfWRX"], outlet_count: 1, tags: ["Utrustning", "Proffsens bagar"], image_url: null,
    },
    {
      id: 5, section: "Touren", score: 0.9, last_published_at: ago(9),
      title_sv: "Säsongsfinalen närmar sig – så ser läget ut för svenskarna",
      ingress: "Flera svenskar slåss om spelrätten inför nästa säsong.",
      summary: "Med några tävlingar kvar av säsongen avgörs vilka som behåller spelrätten.\n\nKällorna går igenom poängläget och vilka tävlingar som återstår.",
      angles: [], outlets: ["Svensk Golf", "SVT Sport"], outlet_count: 2, tags: ["DP World Tour"], image_url: null,
    },
    {
      id: 6, section: "Historia", score: 0.6, last_published_at: ago(20),
      title_sv: "Nicklaus, 46 år, och nio hål på 30 slag",
      ingress: "Fyrtio år senare är söndagen på Augusta fortfarande måttstocken.",
      summary: "Jack Nicklaus vann Masters 1986 som 46-åring efter en sista runda på 65 slag, med 30 slag på de nio sista hålen.",
      angles: [], outlets: ["Golf Digest"], outlet_count: 1, tags: ["Masters", "Jack Nicklaus"], image_url: null,
    },
    {
      id: 7, section: "Historia", score: 0.5, last_published_at: ago(26),
      title_sv: "Två-bollsputtern fyller 25 år",
      ingress: "Siktidén från 2001 som förändrade hur amatörer ställer upp sina puttar.",
      summary: "Två vita cirklar i bollens storlek gjorde siktet till en geometrisk fråga.",
      angles: [], outlets: ["Golf Monthly"], outlet_count: 1, tags: ["Puttrar", "Odyssey"], image_url: null,
    },
  ],
  items: [
    { story_id: 1, outlet: "Ryder Cup", original_title: "Adare Manor: the road to 2027", url: "https://www.rydercup.com", published_at: ago(26), source_words: 1300 },
    { story_id: 1, outlet: "Golf Monthly", original_title: "Ryder Cup 2027: Everything you need to know", url: "https://www.golfmonthly.com", published_at: ago(5), source_words: 1800 },
    { story_id: 1, outlet: "Golf Digest", original_title: "Why Adare Manor will be a Ryder Cup unlike any other", url: "https://www.golfdigest.com", published_at: ago(30), source_words: 1100 },
    { story_id: 1, outlet: "Svensk Golf", original_title: "Så tar sig svenskarna till Adare Manor", url: "https://www.svenskgolf.se", published_at: ago(1), source_words: 900 },
    { story_id: 2, outlet: "MyGolfSpy", original_title: "Why Titleist updates the Pro V1 every two years", url: "https://mygolfspy.com", published_at: ago(3), source_words: 1500 },
    { story_id: 3, outlet: "Golf Monthly", original_title: "4 bunker mistakes golfers make", url: "https://www.golfmonthly.com", published_at: ago(5), source_words: 1200 },
  ],
  media: [
    { id: 101, kind: "video", outlet: "Rick Shiels Golf", original_title: "Testing every new driver on the course", url: "https://www.youtube.com", published_at: ago(2), duration: null },
    { id: 102, kind: "podcast", outlet: "No Laying Up", original_title: "Weekly tour roundup", url: "https://nolayingup.com", published_at: ago(6), duration: "01:14:00" },
    { id: 103, kind: "podcast", outlet: "Klubbans fel", original_title: "Avsnitt 120: Hösten på touren", url: "https://feed.pod.space/klubbansfel", published_at: ago(10), duration: "58:00" },
    { id: 104, kind: "video", outlet: "Carl Déman", original_title: "Kan jag bryta 75 på en ny bana?", url: "https://www.youtube.com", published_at: ago(14), duration: null },
  ],
  health: [
    { id: "golfcom", name: "GOLF.com", kind: "article", last_ok_at: ago(0.4), last_new_item_at: ago(1), last_error: null },
    { id: "svt-golf", name: "SVT Sport Golf", kind: "article", last_ok_at: ago(0.4), last_new_item_at: ago(3), last_error: null },
    { id: "bing-liv", name: "LIV Golf (andra medier)", kind: "news_search", last_ok_at: ago(30), last_new_item_at: ago(30), last_error: "HTTPStatusError: 429" },
  ],
};
