#!/usr/bin/env python3
"""Sestavení webu Nová cesta.

Použití:
  python3 build.py            ostrý web do _site/ (bez konceptů)
  python3 build.py --nahled   testovací verze: pruh nahoře, noindex, i koncepty

Obsah: content/clanky/*.md, content/stranky/*.md, content/fotky/*, nastavení web.json.
"""
import datetime as dt
import hashlib
import html
import json
import re
import shutil
import sys
from pathlib import Path

import markdown
from PIL import Image, ImageOps

KOREN = Path(__file__).resolve().parent
OBSAH = KOREN / "content"
VYSTUP = KOREN / "_site"
NAHLED = "--nahled" in sys.argv or json.loads((KOREN / "web.json").read_text(encoding="utf-8")).get("testovaci_verze", False)

MESICE = ["ledna", "února", "března", "dubna", "května", "června", "července",
          "srpna", "září", "října", "listopadu", "prosince"]


# ---------- pomocné funkce ----------

def nacti_md(cesta):
    """Načte soubor s hlavičkou mezi --- (klíč: hodnota) a tělem v Markdownu."""
    text = cesta.read_text(encoding="utf-8")
    meta, telo = {}, text
    if text.startswith("---"):
        _, hlava, telo = text.split("---", 2)
        for radek in hlava.strip().splitlines():
            if ":" in radek:
                k, v = radek.split(":", 1)
                v = v.strip()
                if len(v) >= 2 and v[0] == v[-1] == '"':
                    v = v[1:-1]
                meta[k.strip()] = v
    meta["telo"] = telo.strip()
    return meta


def datum_cesky(iso):
    d = dt.date.fromisoformat(iso)
    return f"{d.day}. {MESICE[d.month - 1]} {d.year}"


def e(text):
    return html.escape(text, quote=True)


def spojky(fragment):
    """Nezlomitelná mezera za jednopísmennými předložkami a spojkami (jen v textu, ne ve značkách)."""
    casti = re.split(r"(<[^>]+>)", fragment)
    for i, c in enumerate(casti):
        if c.startswith("<"):
            continue
        casti[i] = re.sub(r"(^|[\s(„])([vkszouaiVKSZOUAI]) ", "\\1\\2 ", c)
    return "".join(casti)


def otisk(cesta):
    return hashlib.sha1(cesta.read_bytes()).hexdigest()[:8]


# ---------- fotky ----------

ROZMERY = {}


def zpracuj_fotky():
    cil = VYSTUP / "fotky"
    cil.mkdir(parents=True, exist_ok=True)
    for f in sorted((OBSAH / "fotky").iterdir()):
        if f.suffix.lower() not in (".jpg", ".jpeg", ".png", ".heic"):
            continue
        if f.suffix.lower() == ".heic":
            from pillow_heif import register_heif_opener
            register_heif_opener()
        im = ImageOps.exif_transpose(Image.open(f)).convert("RGB")
        im.thumbnail((1300, 1300))
        jmeno = f.stem + ".jpg"
        im.save(cil / jmeno, "JPEG", quality=80, optimize=True, progressive=True)
        ROZMERY[f.name] = ROZMERY[jmeno] = im.size


def og_obrazek(zdroj, slug):
    """Náhled pro sdílení 1200 × 630 (ořez na střed)."""
    im = Image.open(VYSTUP / "fotky" / (Path(zdroj).stem + ".jpg"))
    im = ImageOps.fit(im, (1200, 630), centering=(0.5, 0.4))
    jmeno = f"og-{slug}.jpg"
    im.save(VYSTUP / "fotky" / jmeno, "JPEG", quality=82, optimize=True)
    return f"fotky/{jmeno}"


def obrazek_html(zdroj, alt, popisek, pre, lazy=True, popisek_html=False):
    jmeno = Path(zdroj).stem + ".jpg"
    w, h = ROZMERY[jmeno]
    nacitani = ' loading="lazy" decoding="async"' if lazy else ""
    text = spojky(popisek) if popisek_html else e(popisek)
    cap = f"\n  <figcaption>{text}</figcaption>" if popisek else ""
    return (f'<figure>\n  <img src="{pre}fotky/{jmeno}" width="{w}" height="{h}" alt="{e(alt)}"{nacitani}>'
            f"{cap}\n</figure>")


def md_na_html(telo, pre):
    # ![alt](foto.jpg "popisek") na samostatném řádku -> figure s popiskem
    def nahrad(m):
        popisek = m.group(3) or m.group(4) or ""
        html_pop = markdown.markdown(popisek)[3:-4] if popisek else ""
        return obrazek_html(m.group(2), m.group(1), html_pop, pre, popisek_html=True)
    telo = re.sub(r'^!\[([^\]]*)\]\(([^)\s]+)(?:\s+"([^"]*)")?\)[ \t]*(?:\n\*(.+)\*[ \t]*)?$', nahrad, telo, flags=re.M)
    vysledek = markdown.markdown(telo, extensions=["sane_lists"], output_format="html")
    vysledek = vysledek.replace("<blockquote>\n<p>", "<blockquote>").replace("</p>\n</blockquote>", "</blockquote>")
    return spojky(vysledek)


# ---------- šablona ----------

def stranka(cfg, *, pre, titulek, popis, cesta, obsah, og=None, ld=None, aktivni="", typ="website"):
    url = cfg["zakladni_url"].rstrip("/") + "/" + cesta
    og_url = cfg["zakladni_url"].rstrip("/") + "/" + (og or "fotky/og-web.jpg")
    nav = [("clanky", "Články", f"{pre}#clanky"), ("o-mne", "O mně", f"{pre}o-mne/"),
           ("odber", "Odebírat", "#odber"), ("podporit", "Podpořit", f"{pre}podporit/")]
    nav_html = "\n      ".join(
        f'<a href="{h}"{" aria-current=\"page\"" if k == aktivni else ""}>{t}</a>' for k, t, h in nav)
    robots = '<meta name="robots" content="noindex, nofollow">\n' if NAHLED else ""
    pruh = ('<aside class="preview" aria-label="Upozornění">Testovací verze, zatím nezveřejněno '
            '<button type="button" class="rezim" onclick="var r=document.documentElement,t=r.dataset.theme===\'dark\'||(!r.dataset.theme&&matchMedia(\'(prefers-color-scheme: dark)\').matches)?\'light\':\'dark\';r.dataset.theme=t;this.textContent=t===\'dark\'?\'Zobrazit světlý režim\':\'Zobrazit tmavý režim\'">Přepnout světlý / tmavý</button></aside>\n') if NAHLED else ""
    ld_html = ""
    if ld:
        ld_html = '<script type="application/ld+json">' + json.dumps(ld, ensure_ascii=False) + "</script>\n"
    kontakt = cfg.get("kontakt_email", "")
    kontakt_html = f'<a href="mailto:{e(kontakt)}">{e(kontakt)}</a>' if kontakt else ""
    return f"""<!doctype html>
<html lang="cs">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(titulek)}</title>
<meta name="description" content="{e(popis)}">
{robots}<link rel="canonical" href="{e(url)}">
<meta property="og:type" content="{typ}">
<meta property="og:locale" content="cs_CZ">
<meta property="og:site_name" content="{e(cfg['nazev'])}">
<meta property="og:title" content="{e(titulek)}">
<meta property="og:description" content="{e(popis)}">
<meta property="og:url" content="{e(url)}">
<meta property="og:image" content="{e(og_url)}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="{pre}favicon.svg" type="image/svg+xml">
<link rel="alternate" type="application/rss+xml" title="{e(cfg['nazev'])}" href="{pre}rss.xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Zilla+Slab:wght@500;700&family=Literata:ital,opsz,wght@0,7..72,400;0,7..72,600;1,7..72,400&family=IBM+Plex+Sans+Condensed:wght@500;600&display=swap">
<link rel="stylesheet" href="{pre}styl.css?v={OTISK_CSS}">
{ld_html}</head>
<body>
{pruh}<a class="skip" href="#obsah">Přeskočit na obsah</a>
<header class="site">
  <div class="wrap">
    <a class="brand" href="{pre or './'}" aria-label="{e(cfg['nazev'])}, úvodní stránka">
      <span class="znacka" aria-hidden="true"><span></span><span></span><span></span></span>
      <span><b>{e(cfg['nazev'])}</b><small>{e(cfg['podtitul_dlouhy'])}</small></span>
    </a>
    <nav aria-label="Hlavní menu">
      {nav_html}
    </nav>
  </div>
</header>

<main id="obsah">
{obsah}
{odber_html(cfg)}
</main>

<footer>
  <div class="wrap"><span>{e(cfg['nazev'])} · {e(cfg['podtitul'])}</span>{kontakt_html}<a href="{pre}osobni-udaje/">Ochrana osobních údajů</a><span>Web vytvořil {e(cfg['autor'])}</span></div>
</footer>
<script src="{pre}odber.js?v={OTISK_JS}" defer></script>
</body>
</html>
"""


def odber_html(cfg):
    stav = "nahled" if NAHLED else ("ok" if cfg.get("odber_url") else "pripravuji")
    return f"""<section class="wrap" aria-labelledby="odber-nadpis">
  <div class="box" id="odber" data-url="{e(cfg.get('odber_url', ''))}" data-stav="{stav}">
    <h2 id="odber-nadpis">Chcete jít se mnou?</h2>
    <p>Pošlu vám e-mail, kdykoli tu přibude nový článek. Zhruba jednou za měsíc, po každém víkendu kurzu.</p>
    <form id="f-odber" novalidate>
      <label for="email" class="sr-only">Váš e-mail</label>
      <input type="email" id="email" name="email" placeholder="vas@email.cz" autocomplete="email" required>
      <input type="text" name="web" tabindex="-1" autocomplete="off" class="sr-only" aria-hidden="true">
      <label class="souhlas"><input type="checkbox" id="souhlas" name="souhlas" required><span>Souhlasím, aby mi Michal posílal e-mailem nové články. Odhlásit se můžu kdykoli. <a href="{{PRE}}osobni-udaje/">Jak s adresou zacházím</a></span></label>
      <button type="submit">Odebírat</button>
    </form>
    <div class="ok" id="odber-ok" role="status" hidden></div>
    <div class="chyba" id="odber-chyba" role="alert" hidden></div>
  </div>
</section>"""


def kurz_html(cfg):
    k = cfg["kurz"]
    hotovo = sum(1 for v in k["vikendy"] if v.get("hotovo"))
    posledni = [v for v in k["vikendy"] if v.get("hotovo")]
    polozky = []
    for v in k["vikendy"]:
        tridy = " ".join(t for t, ano in (("hotovo", v.get("hotovo")), ("rozhodnuti", v.get("rozhodnuti"))) if ano)
        pozn = f": {v['poznamka']}" if v.get("poznamka") else ""
        polozky.append(f'<li{f" class=\"{tridy}\"" if tridy else ""} title="{e(v["misto"])}, {e(v["termin"])}{e(pozn)}"></li>')
    kde = f" ({e(posledni[-1]['misto'])})" if posledni else ""
    return f"""<section class="kurz wrap" aria-label="Kde právě jsem">
  <h2>Kde právě jsem: {e(k['nazev'])}</h2>
  <ol class="trasa" aria-label="Osm víkendů kurzu, za mnou {hotovo}">
    {''.join(polozky)}
  </ol>
  <div class="trasa-pop"><span><strong>{hotovo}&nbsp;z&nbsp;{len(k['vikendy'])} víkendů</strong> za mnou{kde}</span><span>{e(k['dalsi_krok'])}</span></div>
</section>"""


def osoba_ld(cfg):
    return {"@type": "Person", "name": cfg["autor"], "url": cfg["zakladni_url"].rstrip("/") + "/o-mne/"}


# ---------- sestavení ----------

def main():
    global OTISK_CSS, OTISK_JS
    cfg = json.loads((KOREN / "web.json").read_text(encoding="utf-8"))
    if VYSTUP.exists():
        shutil.rmtree(VYSTUP)
    VYSTUP.mkdir()
    zpracuj_fotky()
    shutil.copy(KOREN / "web" / "styl.css", VYSTUP / "styl.css")
    shutil.copy(KOREN / "web" / "odber.js", VYSTUP / "odber.js")
    shutil.copy(KOREN / "web" / "favicon.svg", VYSTUP / "favicon.svg")
    OTISK_CSS, OTISK_JS = otisk(VYSTUP / "styl.css"), otisk(VYSTUP / "odber.js")
    zaklad = cfg["zakladni_url"].rstrip("/")

    clanky = [nacti_md(p) for p in sorted((OBSAH / "clanky").glob("*.md"))]
    clanky = [c for c in clanky if NAHLED or c.get("koncept") != "ano"]
    clanky.sort(key=lambda c: (c["datum"], int(c.get("cislo", 0))), reverse=True)

    og_web = og_obrazek("michal-s-talirem.jpg", "web")
    mapa = [f"{zaklad}/"]

    # články
    for c in clanky:
        pre = "../../"
        cesta = f"clanky/{c['slug']}/"
        foto = ""
        og = og_web
        if c.get("foto"):
            foto = obrazek_html(c["foto"], c.get("foto_alt", ""), c.get("foto_popisek", ""), pre, lazy=False)
            og = og_obrazek(c["foto"], c["slug"])
        else:
            m = re.search(r"\]\(([^)\s]+\.jpe?g)", c["telo"])
            if m:
                og = og_obrazek(m.group(1), c["slug"])
        koncept = '<span class="koncept">koncept</span>' if c.get("koncept") == "ano" else ""
        obsah = f"""{kurz_html(cfg)}

<article class="wrap">
  <div class="meta">Článek {e(c.get('cislo', ''))} · <time datetime="{c['datum']}">{datum_cesky(c['datum'])}</time>{koncept}</div>
  <h1>{spojky(e(c['nazev']))}</h1>
  <p class="perex">{spojky(e(c['perex']))}</p>
  {foto}
  {md_na_html(c['telo'], pre)}
  <p><a class="zpet" href="{pre}#clanky">← Všechny články</a></p>
</article>"""
        ld = {"@context": "https://schema.org", "@type": "BlogPosting", "headline": c["nazev"],
              "description": c["popis"], "datePublished": c["datum"], "inLanguage": "cs",
              "url": f"{zaklad}/{cesta}", "image": f"{zaklad}/{og}", "author": osoba_ld(cfg),
              "publisher": osoba_ld(cfg), "mainEntityOfPage": f"{zaklad}/{cesta}"}
        html_out = stranka(cfg, pre=pre, titulek=f"{c['nazev']} | {cfg['nazev']}", popis=c["popis"],
                           cesta=cesta, obsah=obsah, og=og, ld=ld, aktivni="clanky", typ="article")
        uloz(cesta, html_out.replace("{PRE}", pre))
        c["url"] = f"{zaklad}/{cesta}"
        mapa.append(c["url"])

    # stránky
    for p in sorted((OBSAH / "stranky").glob("*.md")):
        s = nacti_md(p)
        pre = "../"
        cesta = f"{s['slug']}/"
        telo = s["telo"].replace("{{kontakt}}", cfg.get("kontakt_email", ""))
        foto = obrazek_html(s["foto"], s.get("foto_alt", ""), "", pre, lazy=False) if s.get("foto") else ""
        obsah = f"""<article class="wrap">
  <h1>{spojky(e(s['nazev']))}</h1>
  {foto}
  {md_na_html(telo, pre)}
</article>"""
        ld = None
        if s["slug"] == "o-mne":
            ld = {"@context": "https://schema.org", "@type": "ProfilePage", "mainEntity": osoba_ld(cfg)}
        html_out = stranka(cfg, pre=pre, titulek=f"{s['nazev']} | {cfg['nazev']}", popis=s["popis"],
                           cesta=cesta, obsah=obsah, og=og_web, ld=ld, aktivni=s["slug"])
        uloz(cesta, html_out.replace("{PRE}", pre))
        mapa.append(f"{zaklad}/{cesta}")

    # úvodní stránka
    pre = ""
    karty = []
    for c in clanky:
        koncept = '<span class="koncept">koncept</span>' if c.get("koncept") == "ano" else ""
        karty.append(f"""<li class="karta">
    <div class="meta">Článek {e(c.get('cislo', ''))} · <time datetime="{c['datum']}">{datum_cesky(c['datum'])}</time>{koncept}</div>
    <a class="nadpis" href="clanky/{c['slug']}/">{spojky(e(c['nazev']))}</a>
    <p>{spojky(e(c['perex']))}</p>
    <a class="dal" href="clanky/{c['slug']}/" aria-label="Číst článek {e(c['nazev'])}">Číst dál →</a>
  </li>""")
    pripravuji = "".join(f"<li><span>{e(x['nazev'])}</span><span>{e(x['kdy'])}</span></li>" for x in cfg["pripravuji"])
    obsah = f"""<section class="uvod wrap">
  <h1 class="sr-only">{e(cfg['nazev'])}: {e(cfg['podtitul'])}</h1>
  <p>{spojky(e(cfg['uvod']))}</p>
</section>
{kurz_html(cfg)}
<section class="vypis wrap" id="clanky" aria-labelledby="clanky-nadpis">
  <h2 id="clanky-nadpis">Články</h2>
  <ol>
  {''.join(karty)}
  </ol>
</section>
<section class="dalsi wrap" aria-label="Připravované články">
  <h2>Připravuji</h2>
  <ul>{pripravuji}</ul>
</section>"""
    ld = {"@context": "https://schema.org", "@graph": [
        {"@type": "WebSite", "name": cfg["nazev"], "alternateName": cfg["podtitul"], "url": f"{zaklad}/",
         "inLanguage": "cs", "description": cfg["uvod"], "author": osoba_ld(cfg)},
        osoba_ld(cfg)]}
    popis = cfg["uvod"]
    if len(popis) > 155:
        popis = popis[:popis.rfind(" ", 0, 152)] + "…"
    html_out = stranka(cfg, pre=pre, titulek=f"{cfg['nazev']}: {cfg['podtitul']}", popis=popis, cesta="",
                       obsah=obsah, og=og_web, ld=ld, aktivni="")
    uloz("", html_out.replace("{PRE}", pre))

    # 404, sitemap, robots, RSS, seznam článků pro rozesílku
    html404 = stranka(cfg, pre=zaklad + "/", titulek=f"Stránka nenalezena | {cfg['nazev']}",
                      popis="Stránka nenalezena.", cesta="404.html",
                      obsah=f'<article class="wrap"><h1>Tahle stránka tu není</h1><p>Možná se změnila adresa. Zkuste <a href="{zaklad}/">úvodní stránku</a>.</p></article>')
    (VYSTUP / "404.html").write_text(html404.replace("{PRE}", zaklad + "/"), encoding="utf-8")
    if NAHLED:
        (VYSTUP / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
    else:
        (VYSTUP / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {zaklad}/sitemap.xml\n", encoding="utf-8")
    (VYSTUP / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{e(u)}</loc></url>\n" for u in mapa) + "</urlset>\n", encoding="utf-8")
    polozky = "".join(
        f"<item><title>{e(c['nazev'])}</title><link>{e(c['url'])}</link><guid>{e(c['url'])}</guid>"
        f"<pubDate>{dt.datetime.fromisoformat(c['datum']).strftime('%a, %d %b %Y 08:00:00 +0100')}</pubDate>"
        f"<description>{e(c['perex'])}</description></item>\n" for c in clanky)
    (VYSTUP / "rss.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel><title>{e(cfg["nazev"])}</title>'
        f'<link>{zaklad}/</link><description>{e(cfg["uvod"])}</description><language>cs</language>\n{polozky}</channel></rss>\n',
        encoding="utf-8")
    (VYSTUP / "clanky.json").write_text(json.dumps(
        [{"slug": c["slug"], "nazev": c["nazev"], "perex": c["perex"], "url": c["url"], "datum": c["datum"]}
         for c in clanky if c.get("koncept") != "ano"], ensure_ascii=False, indent=1), encoding="utf-8")
    if cfg.get("domena") and not NAHLED:
        (VYSTUP / "CNAME").write_text(cfg["domena"] + "\n", encoding="utf-8")
    (VYSTUP / ".nojekyll").write_text("", encoding="utf-8")
    print(f"Hotovo: {len(clanky)} článků, {len(mapa)} stránek v mapě, režim {'NÁHLED' if NAHLED else 'OSTRÝ'}.")


def uloz(cesta, obsah):
    cil = VYSTUP / cesta / "index.html"
    cil.parent.mkdir(parents=True, exist_ok=True)
    cil.write_text(obsah, encoding="utf-8")


if __name__ == "__main__":
    main()
