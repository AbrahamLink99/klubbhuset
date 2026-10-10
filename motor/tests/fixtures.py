"""Små exempelflöden som efterliknar de verkliga källornas egenheter."""

GOLFCOM_LIKE = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:media="http://search.yahoo.com/mrss/">
<channel><title>GOLF</title>
<item>
  <title>Ryder Cup 2027: Everything you need to know</title>
  <link>https://golf.com/news/ryder-cup-2027-guide/?utm_source=rss</link>
  <pubDate>Thu, 08 Oct 2026 14:00:00 +0000</pubDate>
  <description><![CDATA[Short teaser.]]></description>
  <content:encoded><![CDATA[<p>Teaser only.</p>]]></content:encoded>
  <content:encoded><![CDATA[<p>Still short.</p>]]></content:encoded>
  <content:encoded><![CDATA[<!DOCTYPE html><html><head><title>Wrapper</title></head><body>
    <p>The 2027 Ryder Cup will be played at Adare Manor in County Limerick.</p>
    <p>It is the first time Ireland hosts since The K Club in 2006.</p>
    <img src="https://golf.com/img/adare.jpg"/></body></html>]]></content:encoded>
</item>
</channel></rss>"""

DUPLICATE_NAMESPACE = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/" xmlns:media="http://search.yahoo.com/mrss/">
<channel><title>Plugged In Golf</title>
<item>
  <title>Review: A new putter</title>
  <link>https://www.pluggedingolf.com/review-a-new-putter/</link>
  <pubDate>Thu, 08 Oct 2026 10:00:00 +0000</pubDate>
  <description>The putter is reviewed in full here.</description>
</item>
</channel></rss>"""

YOUTUBE_ATOM = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns:media="http://search.yahoo.com/mrss/" xmlns="http://www.w3.org/2005/Atom">
 <title>Rick Shiels Golf</title>
 <entry>
  <id>yt:video:abc123</id>
  <yt:videoId>abc123</yt:videoId>
  <title>Testing every new driver</title>
  <link rel="alternate" href="https://www.youtube.com/watch?v=abc123"/>
  <published>2026-10-08T17:00:00+00:00</published>
  <media:group>
   <media:title>Testing every new driver</media:title>
   <media:thumbnail url="https://i2.ytimg.com/vi/abc123/hqdefault.jpg" width="480" height="360"/>
   <media:description>We test the drivers on the course.</media:description>
  </media:group>
 </entry>
</feed>"""

PODCAST_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
<channel><title>Klubbans fel</title>
<item>
  <title>Avsnitt 120: Hösten på touren</title>
  <pubDate>Wed, 07 Oct 2026 06:00:00 +0000</pubDate>
  <enclosure url="https://cdn.example.com/ep120.mp3" type="audio/mpeg" length="1"/>
  <itunes:duration>01:04:12</itunes:duration>
  <description>Vi pratar höst.</description>
</item>
</channel></rss>""".encode("utf-8")

BING_NEWS = """<?xml version="1.0" encoding="utf-8" ?>
<rss version="2.0" xmlns:News="https://www.bing.com/news/search?q=golf+%c3%85berg&amp;format=rss">
<channel><title>golf Åberg - BingNyheter</title>
<item>
  <title>Åberg klar för finalen</title>
  <link>http://www.bing.com/news/apiclick.aspx?ref=FexRss&amp;aid=&amp;tid=x&amp;url=https%3a%2f%2fwww.svt.se%2fsport%2fgolf%2faberg-klar&amp;c=1</link>
  <description>Ludvig Åberg är klar för säsongsfinalen.</description>
  <pubDate>Thu, 08 Oct 2026 12:00:00 GMT</pubDate>
  <News:Source>SVT Sport</News:Source>
  <News:Image>https://www.bing.com/th?id=OVFT.abc&amp;pid=News</News:Image>
</item>
</channel></rss>""".encode("utf-8")
