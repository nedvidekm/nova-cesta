#!/usr/bin/env python3
"""Sestavení webu Na nové cestě.

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
# koncepty na ostrém webu: vidět s označením „koncept“ (pro známé a testery), ale noindex a bez rozesílky, RSS a mapy webu
KONCEPTY = NAHLED or json.loads((KOREN / "web.json").read_text(encoding="utf-8")).get("ukazat_koncepty", False)
# testovací verze, kterou už smějí číst vyhledávače (koncepty zůstávají noindex)
ROBOTI = json.loads((KOREN / "web.json").read_text(encoding="utf-8")).get("povolit_roboty", False) and "--nahled" not in sys.argv

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


def og_obrazek(zdroj, slug, centering=(0.5, 0.4)):
    """Náhled pro sdílení 1200 × 630 (ořez na střed)."""
    im = Image.open(VYSTUP / "fotky" / (Path(zdroj).stem + ".jpg"))
    im = ImageOps.fit(im, (1200, 630), centering=centering)
    jmeno = f"og-{slug}.jpg"
    im.save(VYSTUP / "fotky" / jmeno, "JPEG", quality=82, optimize=True)
    return f"fotky/{jmeno}"


def obrazek_html(zdroj, alt, popisek, pre, lazy=True, popisek_html=False):
    jmeno = Path(zdroj).stem + ".jpg"
    w, h = ROZMERY[jmeno]
    nacitani = ' loading="lazy" decoding="async"' if lazy else ""
    text = spojky(popisek) if popisek_html else e(popisek)
    cap = f"\n  <figcaption>{text}</figcaption>" if popisek else ""
    trida = ' class="nastojato"' if h > w else ""   # fotka na výšku: na širokém displeji užší
    return (f'<figure{trida}>\n  <img src="{pre}fotky/{jmeno}" width="{w}" height="{h}" alt="{e(alt)}"{nacitani}>'
            f"{cap}\n</figure>")


def kontakt_md(telo, cfg):
    k = cfg.get("kontakt_email", "")
    return telo.replace("{{kontakt}}", f"[{k}](mailto:{k})")


def md_na_html(telo, pre):
    # ![alt](foto.jpg "popisek") na samostatném řádku -> figure s popiskem
    def nahrad(m):
        popisek = m.group(3) or m.group(4) or ""
        html_pop = markdown.markdown(popisek)[3:-4] if popisek else ""
        return obrazek_html(m.group(2), m.group(1), html_pop, pre, popisek_html=True)
    telo = re.sub(r'^!\[([^\]]*)\]\(([^)\s]+)(?:\s+"([^"]*)")?\)[ \t]*(?:\n\*(.+)\*[ \t]*)?$', nahrad, telo, flags=re.M)
    vysledek = markdown.markdown(telo, extensions=["sane_lists", "tables"], output_format="html")
    vysledek = vysledek.replace("<blockquote>\n<p>", "<blockquote>").replace("</p>\n</blockquote>", "</blockquote>")
    # fotka na výšku stojí vedle textu jen tehdy, když po ní text opravdu následuje; jinak zůstane uprostřed
    casti = re.split(r'(<figure class="nastojato">.*?</figure>)', vysledek, flags=re.S)
    for i in range(1, len(casti), 2):
        if not casti[i + 1].lstrip().startswith("<p>"):
            casti[i] = casti[i].replace('class="nastojato"', 'class="nastojato sama"', 1)
    vysledek = "".join(casti)
    return spojky(vysledek)


# ---------- šablona ----------

def stranka(cfg, *, pre, titulek, popis, cesta, obsah, og=None, ld=None, aktivni="", typ="website", koncept=False, noindex=False, odber=True):
    url = cfg["zakladni_url"].rstrip("/") + "/" + cesta
    og_url = cfg["zakladni_url"].rstrip("/") + "/" + (og or "fotky/og-web.jpg")
    nav = [("clanky", "Články", f"{pre}#clanky"), ("o-mne", "O mně", f"{pre}o-mne/"),
           ("odber", "Odebírat", f"{pre}podporit/#odber"), ("podporit", "Podpořit", f"{pre}podporit/")]
    nav_html = "\n      ".join(
        f'<a href="{h}"{" aria-current=\"page\"" if k == aktivni else ""}>{t}</a>' for k, t, h in nav)
    robots = '<meta name="robots" content="noindex, nofollow">\n' if (noindex or koncept or (NAHLED and not ROBOTI)) else ""
    pruh = '<aside class="preview" aria-label="Upozornění">Testovací verze, zatím nezveřejněno</aside>\n' if NAHLED else ""
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
<script>try{{document.documentElement.dataset.theme=localStorage.getItem("rezim")==="dark"?"dark":"light"}}catch(x){{document.documentElement.dataset.theme="light"}}</script>
{ld_html}</head>
<body>
{pruh}<a class="skip" href="#obsah">Přeskočit na obsah</a>
<header class="site">
  <div class="wrap">
    <a class="brand" href="{pre or './'}" aria-label="{e(cfg['nazev'])}, úvodní stránka">
      <span class="znacka" aria-hidden="true"><span></span><span></span><span></span></span>
      <span><b>{e(cfg['nazev'])}</b><small>{e(cfg['podtitul_dlouhy'])}</small></span>
    </a>
  </div>
</header>
<nav class="menu" aria-label="Hlavní menu">
  <div class="wrap">
    {nav_html}
    <button type="button" class="rezim" hidden aria-label="Přepnout na tmavý režim" title="Světlý / tmavý režim"><span aria-hidden="true"></span></button>
  </div>
</nav>

<main id="obsah">
{obsah}
{odber_html(cfg) if odber else ""}
</main>

<footer>
  <div class="wrap">
    <div class="paticka-ja">
      <h2>{e(cfg['nazev'])}</h2>
      <span>{e(cfg['podtitul'])}</span>{kontakt_html}
    </div>
    <nav class="paticka-odkazy" aria-labelledby="paticka-sledujte">
      <h2 id="paticka-sledujte">Sledujte a podpořte</h2>
      <a href="{pre}podporit/">Podpořit cestu</a><a href="{pre}podporit/#odber">Odebírat novinky e-mailem</a>{socialni_html(cfg)}
    </nav>
    <div class="podporuji">
      <h2>Podporují mě</h2>
      <a class="zamek" href="https://www.zivyzamektouzim.cz/" rel="noopener"><img src="{pre}zamek-logo.png" width="320" height="241" alt="Živý zámek Toužim" loading="lazy"></a>
    </div>
    <p class="paticka-spodek"><a href="{pre}osobni-udaje/">Ochrana osobních údajů</a><span aria-hidden="true"> · </span><span>Web vytvořil {e(cfg['autor'])}</span></p>
  </div>
</footer>
<script src="{pre}odber.js?v={OTISK_JS}" defer></script>
</body>
</html>
"""


def socialni_html(cfg):
    return "".join(f'<a href="{e(x["url"])}" rel="me noopener">{e(x["nazev"])}</a>' for x in cfg.get("socialni", []))


def kc(n):
    return f"{int(n):,}".replace(",", "\u00a0") + "\u00a0Kč"


def stav_sbirky_html(cfg):
    """Teploměr sbírky: kolik je na transparentním účtu z cíle (ručně ve web.json → podpora)."""
    p = cfg.get("podpora") or {}
    cil, vyb = int(p.get("cil", 0)), int(p.get("vybrano", 0))
    if not cil:
        return ""
    pct = min(100, round(vyb * 100 / cil))
    presne = vyb * 100 / cil
    pct_text = f"{presne:.1f}".replace(".", ",") if 0 < presne < 10 and presne != int(presne) else str(pct)
    kdy = f" · stav k {datum_cesky(p['aktualizovano'])}" if p.get("aktualizovano") else ""
    return f"""<div class="sbirka">
  <p class="sbirka-cisla"><b>{kc(vyb)}</b> <span>z cíle {kc(cil)}</span></p>
  <div class="sbirka-pruh" role="img" aria-label="Vybráno {pct_text} % z cíle {kc(cil)}"><span style="width:{max(pct, 1) if vyb else 0}%"></span></div>
  <p class="sbirka-pozn">Vybráno {pct_text} %{kdy}</p>
</div>"""


def ucet_html(cfg):
    p = cfg.get("podpora") or {}
    if not p.get("ucet"):
        return """<div class="ucet ucet-brzy">
  <p class="ucet-nazev">Osobní transparentní účet – podpora dobrovolnické mise</p>
  <p><b>Účet právě zakládám.</b> Číslo účtu a QR kód pro platbu z mobilu sem doplním hned, jak ho banka zřídí. Kdo nechce nic propást, může se <a href="#odber">přihlásit k odběru</a> a dám mu vědět.</p>
</div>"""
    radky = [("Číslo účtu", f'<span class="ucet-cislo">{e(p["ucet"])}</span> <button type="button" class="kopirovat" data-text="{e(p["ucet"])}">Zkopírovat</button>')]
    if p.get("majitel"):
        radky.append(("Majitel", e(p["majitel"])))
    if p.get("zprava"):
        radky.append(("Zpráva pro příjemce", e(p["zprava"])))
    dl = "".join(f"<dt>{a}</dt><dd>{b}</dd>" for a, b in radky)
    qr = ""
    if p.get("qr"):
        castky = p.get("qr_castky") or []
        vychozi = p.get("qr_vychozi")
        src = f"platba-qr-{vychozi}.svg" if vychozi in castky else p["qr"]
        tlacitka = ""
        if castky:
            volby = [(str(c), kc(c)) for c in castky] + [("", "Jiná částka")]
            tlacitka = ('<div class="qr-castky" role="group" aria-label="Částka v QR kódu">' + "".join(
                f'<button type="button" data-qr="{{PRE}}{"platba-qr-" + k + ".svg" if k else e(p["qr"])}" aria-pressed="{"true" if k == str(vychozi) else "false"}">{t}</button>'
                for k, t in volby) + '</div>')
        qr = (f'<figure class="ucet-qr">{tlacitka}<img src="{{PRE}}{src}" width="220" height="220" alt="QR kód pro platbu na účet {e(p["ucet"])}">'
              f'<figcaption>Naskenujte v aplikaci své banky. Částku tam můžete ještě změnit.</figcaption></figure>')
    vypis = f'<p><a href="{e(p["vypis_url"])}" rel="noopener">Veřejný výpis z účtu →</a></p>' if p.get("vypis_url") else ""
    return f'<div class="ucet"><p class="ucet-nazev">Osobní transparentní účet – podpora dobrovolnické mise</p><dl>{dl}</dl>{qr}{vypis}<p class="ucet-ok" role="status" hidden></p></div>'



def odber_html(cfg, pre=None):
    """Box s odběrem. Pod článkem a zápiskem (pre zadané) v něm je i prosba o podporu, aby byl jen jeden."""
    stav = "nahled" if NAHLED else ("ok" if cfg.get("odber_url") else "pripravuji")
    podpora = ""
    if pre is not None:
        podpora = f"""<p>Tenhle blog píšu, abych na cestě nebyl sám. Pomůže mi, když budete číst dál, pošlete článek někomu, koho by mohl zajímat, nebo když na cestu přispějete. Stovka udělá radost stejně jako tisícovka.</p>
    {stav_sbirky_html(cfg)}
    <p class="vyzva-akce"><a class="tlacitko" href="{pre}podporit/">Podpořit cestu</a></p>
    <h3 class="odber-mezi">Nový článek e-mailem</h3>
"""
    nadpis = "Jdete se mnou?" if pre is not None else "Chcete jít se mnou?"
    return f"""<section class="wrap" aria-labelledby="odber-nadpis">
  <div class="box" id="odber" data-url="{e(cfg.get('odber_url', ''))}" data-stav="{stav}">
    <h2 id="odber-nadpis">{nadpis}</h2>
    {podpora}<p>Pošlu vám e-mail pokaždé, když tu přibude nový článek nebo krátký zápisek. Nic jiného, žádná reklama.</p>
    <form id="f-odber" novalidate>
      <label for="email" class="sr-only">Váš e-mail</label>
      <input type="email" id="email" name="email" placeholder="vas@email.cz" autocomplete="email" required>
      <input type="text" name="web" tabindex="-1" autocomplete="off" class="sr-only" aria-hidden="true">
      <label class="souhlas"><input type="checkbox" id="souhlas" name="souhlas" required><span>Souhlasím, aby mi Michal posílal e-mailem nové články a zápisky. Odhlásit se můžu kdykoli. <a href="{{PRE}}osobni-udaje/">Jak s adresou zacházím</a></span></label>
      <button type="submit">Odebírat</button>
    </form>
    <div class="ok" id="odber-ok" role="status" hidden></div>
    <div class="chyba" id="odber-chyba" role="alert" hidden></div>
  </div>
</section>"""


def kurz_html(cfg, pre="", clanky=()):
    """Osa kurzu. Víkend, který je za mnou, odkazuje na svůj článek (pole "clanek" ve web.json),
    a dokud článek není venku, na výpis článků."""
    k = cfg["kurz"]
    venku = {c["slug"] for c in clanky}
    # Víkend je „za mnou“ až ve chvíli, kdy je venku jeho článek (pokud nějaký má).
    def je_hotovo(v):
        return bool(v.get("hotovo")) and (not v.get("clanek") or v["clanek"] in venku)
    posledni = [v for v in k["vikendy"] if je_hotovo(v)]
    hotovo = len(posledni)
    polozky = []
    for i, v in enumerate(k["vikendy"], 1):
        tridy = " ".join(t for t, ano in (("hotovo", je_hotovo(v)), ("rozhodnuti", v.get("rozhodnuti"))) if ano)
        pozn = f": {v['poznamka']}" if v.get("poznamka") else ""
        popis = f"Víkend {i}: {v['misto']}, {v['termin']}{pozn}"
        if je_hotovo(v):
            cil = f"{pre}clanky/{v['clanek']}/" if v.get("clanek") else f"{pre}#clanky"
            vnitrek = f'<a href="{cil}" title="{e(popis)}"><span class="sr-only">{e(popis)}, číst</span></a>'
        else:
            vnitrek = f'<span title="{e(popis)}"><span class="sr-only">{e(popis)}, teprve mě čeká</span></span>'
        polozky.append(f'<li{f" class=\"{tridy}\"" if tridy else ""}>{vnitrek}</li>')
    kde = f" ({e(posledni[-1]['misto'])})" if posledni else ""
    return f"""<section class="kurz wrap" aria-label="Kde právě jsem">
  <h2>Kde právě jsem: {e(k['nazev'])}</h2>
  <ol class="trasa" aria-label="Osm víkendů kurzu, za mnou {hotovo}">
    {''.join(polozky)}
  </ol>
  <div class="trasa-pop"><span><strong>{hotovo}&nbsp;z&nbsp;{len(k['vikendy'])} víkendů</strong> za mnou{kde}</span><span>{e(k['dalsi_krok'])}</span></div>
</section>"""


def osoba_ld(cfg):
    osoba = {"@type": "Person", "name": cfg["autor"], "url": cfg["zakladni_url"].rstrip("/") + "/o-mne/"}
    if cfg.get("socialni"):
        osoba["sameAs"] = [x["url"] for x in cfg["socialni"]]
    return osoba


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
    shutil.copy(KOREN / "web" / "zamek-logo.png", VYSTUP / "zamek-logo.png")
    for f in (KOREN / "web").glob("platba-qr*.svg"):
        shutil.copy(f, VYSTUP / f.name)
    OTISK_CSS, OTISK_JS = otisk(VYSTUP / "styl.css"), otisk(VYSTUP / "odber.js")
    zaklad = cfg["zakladni_url"].rstrip("/")

    clanky = [nacti_md(p) for p in sorted((OBSAH / "clanky").glob("*.md"))]
    vsechny_koncepty = [c for c in clanky if c.get("koncept") == "ano"]
    clanky = [c for c in clanky if KONCEPTY or c.get("koncept") != "ano"]
    clanky.sort(key=lambda c: (c["datum"], int(c.get("cislo", 0))), reverse=True)
    # koncept má v testovací verzi vlastní stránku k pročtení, ale do výpisů se nedostane (je v „Připravuji“)
    vydane = [c for c in clanky if c.get("koncept") != "ano"]

    # náhled při sdílení webu: portrét ve vínovém svetru (neořezaná verze fotky z úvodu), hlava celá
    og_web = og_obrazek("michal-portret.jpg", "uvod", centering=(0.5, 0.0))
    mapa = [f"{zaklad}/"]

    # krátké zápisky (koncepty jen v testovací verzi)
    zapisky = [nacti_md(p) for p in sorted((OBSAH / "zapisky").glob("*.md"))] if (OBSAH / "zapisky").exists() else []
    vsechny_koncepty += [dict(z, je_zapisek=True) for z in zapisky if z.get("koncept") == "ano"]
    zapisky = [z for z in zapisky if KONCEPTY or z.get("koncept") != "ano"]
    for c in clanky:
        c["druh"] = "clanky"
    for z in zapisky:
        z["druh"] = "zapisky"
    # v testovací verzi se koncepty ukazují všude tak, jako by už vyšly (s označením koncept)
    ukazat = clanky if KONCEPTY else vydane
    venku = sorted(ukazat + [z for z in zapisky if KONCEPTY or z.get("koncept") != "ano"],
                   key=lambda d: (d["datum"], int(d.get("cislo", 0))), reverse=True)

    def stitek(d):
        if d["druh"] == "zapisky":
            t = f"Krátký zápisek · {datum_cesky(d['datum'])}"
        else:
            t = f"Článek {e(d.get('cislo', ''))} · {datum_cesky(d['datum'])}"
        return t + (" · koncept" if d.get("koncept") == "ano" else "")

    def prehled_html(c, pre):
        """Pod článkem i zápiskem stejný výpis všeho vydaného, aby se dalo rovnou pokračovat jinam."""
        radky = []
        for d in venku if c in venku else [c] + venku:
            if d is c:
                radky.append(f'<li class="tady" aria-current="page"><small>{stitek(d)} · právě čtete</small><span>{spojky(e(d["nazev"]))}</span></li>')
            else:
                radky.append(f'<li><a href="{pre}{d["druh"]}/{d["slug"]}/"><small>{stitek(d)}</small><span>{spojky(e(d["nazev"]))}</span></a></li>')
        nadpis = "Všechny články a zápisky" if zapisky else "Všechny články"
        return (f'<section class="prehled wrap" aria-labelledby="prehled-nadpis"><h2 id="prehled-nadpis">{nadpis}</h2>'
                f'<ol>{"".join(radky)}</ol></section>') if len(radky) > 1 else ""

    def cist_dal_html(c, pre):
        """Hned pod textem: předchozí a další článek a odkaz dolů na celý seznam."""
        rada = venku if c in venku else sorted(venku + [c], key=lambda d: (d["datum"], int(d.get("cislo", 0))), reverse=True)
        i = rada.index(c)
        novejsi = rada[i - 1] if i > 0 else None
        starsi = rada[i + 1] if i + 1 < len(rada) else None
        def karta(d, smer, trida):
            return (f'<a class="{trida}" href="{pre}{d["druh"]}/{d["slug"]}/"><small>{smer}</small>'
                    f'<span>{spojky(e(d["nazev"]))}</span></a>')
        karty = (karta(starsi, "← Předchozí", "cist-pred") if starsi else "") + (karta(novejsi, "Další →", "cist-dal") if novejsi else "")
        if not karty:
            return ""
        return (f'<nav class="cist wrap" aria-label="Další čtení"><div class="cist-karty">{karty}</div>'
                f'<a class="dal cist-vse" href="#prehled-nadpis">Všechny články a zápisky ↓</a></nav>')

    # články
    for i, c in enumerate(clanky):
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
        prehled = prehled_html(c, pre)
        obsah = f"""{kurz_html(cfg, pre, ukazat)}

<article class="wrap">
  <div class="meta">Článek {e(c.get('cislo', ''))} · <time datetime="{c['datum']}">{datum_cesky(c['datum'])}</time>{koncept}</div>
  <h1>{spojky(e(c['nazev']))}</h1>
  <p class="perex">{spojky(e(c['perex']))}</p>
  {foto}
  {md_na_html(kontakt_md(c['telo'], cfg), pre)}
</article>
{cist_dal_html(c, pre)}
{odber_html(cfg, pre)}
{prehled}"""
        ld = {"@context": "https://schema.org", "@type": "BlogPosting", "headline": c["nazev"],
              "description": c["popis"], "datePublished": c["datum"], "inLanguage": "cs",
              "url": f"{zaklad}/{cesta}", "image": f"{zaklad}/{og}", "author": osoba_ld(cfg),
              "publisher": osoba_ld(cfg), "mainEntityOfPage": f"{zaklad}/{cesta}"}
        html_out = stranka(cfg, pre=pre, titulek=f"{c['nazev']} | {cfg['nazev']}", popis=c["popis"],
                           cesta=cesta, obsah=obsah, og=og, ld=ld, aktivni="clanky", typ="article", koncept=c.get("koncept") == "ano", odber=False)
        uloz(cesta, html_out.replace("{PRE}", pre))
        c["url"] = f"{zaklad}/{cesta}"
        if c.get("koncept") != "ano":
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
  {md_na_html(telo, pre).replace("<p>{{stav_sbirky}}</p>", stav_sbirky_html(cfg)).replace("<p>{{ucet}}</p>", ucet_html(cfg))}
</article>"""
        ld = None
        if s["slug"] == "o-mne":
            ld = {"@context": "https://schema.org", "@type": "ProfilePage", "mainEntity": osoba_ld(cfg)}
        html_out = stranka(cfg, pre=pre, titulek=f"{s['nazev']} | {cfg['nazev']}", popis=s["popis"],
                           cesta=cesta, obsah=obsah, og=og_web, ld=ld, aktivni=s["slug"])
        uloz(cesta, html_out.replace("{PRE}", pre))
        mapa.append(f"{zaklad}/{cesta}")

    # krátké zápisky: vlastní stránka stejně jako článek (kvůli odkazu z Facebooku), celé znění i na úvodní stránce
    for z in zapisky:
        pre = "../../"
        cesta = f"zapisky/{z['slug']}/"
        og = og_obrazek(z["foto"], "z-" + z["slug"]) if z.get("foto") else og_web
        foto = obrazek_html(z["foto"], z.get("foto_alt", ""), z.get("foto_popisek", ""), pre, lazy=False) if z.get("foto") else ""
        koncept = '<span class="koncept">koncept</span>' if z.get("koncept") == "ano" else ""
        obsah = f"""{kurz_html(cfg, pre, ukazat)}

<article class="wrap zapisek-stranka">
  <div class="meta">Krátký zápisek · <time datetime="{z['datum']}">{datum_cesky(z['datum'])}</time>{koncept}</div>
  <h1>{spojky(e(z['nazev']))}</h1>
  {foto}
  {md_na_html(kontakt_md(z['telo'], cfg), pre)}
</article>
{cist_dal_html(z, pre)}
{odber_html(cfg, pre)}
{prehled_html(z, pre)}"""
        popis = re.sub(r"\s+", " ", re.sub(r"[*_\[\]{}]|\(mailto:[^)]*\)", "", z["telo"])).strip()
        if len(popis) > 155:
            popis = popis[:popis.rfind(" ", 0, 152)] + "…"
        z["perex"], z["url"] = popis, f"{zaklad}/{cesta}"
        ld = {"@context": "https://schema.org", "@type": "BlogPosting", "headline": z["nazev"], "description": popis,
              "datePublished": z["datum"], "inLanguage": "cs", "url": f"{zaklad}/{cesta}", "image": f"{zaklad}/{og}",
              "author": osoba_ld(cfg), "publisher": osoba_ld(cfg), "mainEntityOfPage": f"{zaklad}/{cesta}"}
        html_out = stranka(cfg, pre=pre, titulek=f"{z['nazev']} | {cfg['nazev']}", popis=popis, cesta=cesta,
                           obsah=obsah, og=og, ld=ld, aktivni="clanky", typ="article", koncept=z.get("koncept") == "ano", odber=False)
        uloz(cesta, html_out.replace("{PRE}", pre))
        if z.get("koncept") != "ano":
            mapa.append(f"{zaklad}/{cesta}")

    # úvodní stránka
    pre = ""
    polozky = [("clanek", c) for c in ukazat] + [("zapisek", z) for z in zapisky]
    polozky.sort(key=lambda x: x[1]["datum"], reverse=True)
    karty = []
    for druh, c in polozky:
        if druh == "zapisek":
            koncept = '<span class="koncept">koncept</span>' if c.get("koncept") == "ano" else ""
            foto = obrazek_html(c["foto"], c.get("foto_alt", ""), c.get("foto_popisek", ""), pre) if c.get("foto") else ""
            karty.append(f"""<li class="karta zapisek" id="zapisek-{e(c['slug'])}">
    <div class="meta">Krátký zápisek · <time datetime="{c['datum']}">{datum_cesky(c['datum'])}</time>{koncept}</div>
    <h3><a href="zapisky/{e(c['slug'])}/">{spojky(e(c['nazev']))}</a></h3>
    {foto}
    {md_na_html(kontakt_md(c['telo'], cfg), pre)}
  </li>""")
            continue
        koncept = '<span class="koncept">koncept</span>' if c.get("koncept") == "ano" else ""
        karty.append(f"""<li class="karta">
    <div class="meta">Článek {e(c.get('cislo', ''))} · <time datetime="{c['datum']}">{datum_cesky(c['datum'])}</time>{koncept}</div>
    <a class="nadpis" href="clanky/{c['slug']}/">{spojky(e(c['nazev']))}</a>
    <p>{spojky(e(c['perex']))}</p>
    <a class="dal" href="clanky/{c['slug']}/" aria-label="Číst článek {e(c['nazev'])}">Číst dál →</a>
  </li>""")
    # Připravuji: naplánované koncepty (článek i zápisek) s přesným datem + větší plány z web.json bez textu, podle data, max. 5
    def bez_roku(iso):
        d = dt.date.fromisoformat(iso)
        return f"{d.day}. {MESICE[d.month - 1]}"
    hotove = {k["nazev"] for k in vsechny_koncepty}
    plan = [{"nazev": k["nazev"], "datum": k["datum"], "kdy": bez_roku(k["datum"]),
             "druh": "krátký zápisek" if k.get("je_zapisek") else "článek"} for k in vsechny_koncepty]
    plan += [dict(x, druh="článek") for x in cfg["pripravuji"] if x["nazev"] not in hotove]
    plan.sort(key=lambda x: x["datum"])
    pripravuji = "".join(f'<li class="plan"><span class="nazev">{e(x["nazev"])}</span><small>{e(x["kdy"])} · {x["druh"]}</small></li>'
                         for x in plan[:5])
    hero = cfg.get("hero", {})
    hero_foto = ""
    if hero.get("foto"):
        jm = Path(hero["foto"]).stem + ".jpg"
        w, h = ROZMERY[jm]
        hero_foto = (f'<figure class="hero-foto"><img src="fotky/{jm}" width="{w}" height="{h}" '
                     f'alt="{e(hero.get("foto_alt", ""))}" fetchpriority="high"></figure>')
    nadpis = hero.get("nadpis") or f"{cfg['nazev']}: {cfg['podtitul']}"
    postaveno = {c["slug"] for c in clanky}   # stránky, které v tomhle sestavení existují
    resim = []
    for x in cfg.get("prave_resim", []):
        if x.get("clanek") in postaveno:
            resim.append(f'<li><a href="clanky/{x["clanek"]}/">{spojky(e(x["text"]))}</a></li>')
        elif x.get("stranka"):
            resim.append(f'<li><a href="{x["stranka"]}/">{spojky(e(x["text"]))}</a></li>')
        else:
            resim.append(f"<li><span>{spojky(e(x['text']))}</span></li>")
    resim_html = (f'<section class="resim wrap" aria-labelledby="resim-nadpis"><div class="resim-box">'
                  f'<h2 id="resim-nadpis">Právě řeším</h2><ul>{"".join(resim)}</ul></div></section>') if resim else ""
    obsah = f"""<section class="uvod wrap">
  <div class="uvod-text">
    <p class="meta">{e(hero.get('stitek', cfg['podtitul']))}</p>
    <h1>{spojky(e(nadpis))}</h1>
    <p class="uvod-perex">{spojky(e(cfg['uvod']))}</p>
    <p class="uvod-akce"><a class="tlacitko" href="#clanky">Číst články</a><a class="dal" href="podporit/">Jak mě podpořit →</a></p>
  </div>
  {hero_foto}
</section>
{kurz_html(cfg, pre, ukazat)}
{resim_html}
<section class="vypis wrap" id="clanky" aria-labelledby="clanky-nadpis">
  <h2 id="clanky-nadpis">{"Články a zápisky" if zapisky else "Články"}</h2>
  <ol>
  {''.join(karty)}
  </ol>
</section>
<section class="pomoc wrap" aria-labelledby="pomoc-nadpis">
  <h2 id="pomoc-nadpis">Jak můžete pomoct</h2>
  <p>Na cestu se připravuji už teď a peníze na ni začínám skládat taky už teď. Cíl je 100 000 Kč na letenky, očkování, pojištění a další výdaje. Na transparentním účtu bude vidět každá koruna, která přijde i odejde.</p>
  {stav_sbirky_html(cfg)}
  <ol class="pomoc-kroky">
    <li><b>Sledujte mě.</b> <a href="#odber">Přihlaste se k odběru</a> a nový článek vám přijde e-mailem.</li>
    <li><b>Pošlete blog dál.</b> Komukoli, koho by mohl zajímat.</li>
    <li><b>Přispějte na cestu.</b> Jakoukoli částkou, <a href="podporit/">jak a na co</a> najdete na stránce Podpořit.</li>
  </ol>
</section>
<section class="dalsi wrap" aria-label="Připravované články">
  <h2>Připravuji</h2>
  <ul>{pripravuji}</ul>
</section>"""
    koncepty = [c for c in clanky if c.get("koncept") == "ano"]
    if False and koncepty:  # koncepty jsou v testovací verzi přímo ve výpisu článků
        odkazy = "".join(f'<li><a href="clanky/{c["slug"]}/">{spojky(e(c["nazev"]))}</a><span>koncept</span></li>' for c in koncepty)
        obsah += f"""
<section class="dalsi koncepty wrap" aria-label="Koncepty k pročtení">
  <h2>Koncepty k pročtení (jen v testovací verzi)</h2>
  <ul>{odkazy}</ul>
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
                      popis="Stránka nenalezena.", cesta="404.html", noindex=True,
                      obsah=f'<article class="wrap"><h1>Tahle stránka tu není</h1><p>Možná se změnila adresa. Zkuste <a href="{zaklad}/">úvodní stránku</a>.</p></article>')
    (VYSTUP / "404.html").write_text(html404.replace("{PRE}", zaklad + "/"), encoding="utf-8")
    if NAHLED and not ROBOTI:
        (VYSTUP / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
    else:
        (VYSTUP / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {zaklad}/sitemap.xml\n", encoding="utf-8")
    (VYSTUP / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{e(u)}</loc></url>\n" for u in mapa) + "</urlset>\n", encoding="utf-8")
    polozky = "".join(
        f"<item><title>{e(c['nazev'])}</title><link>{e(c['url'])}</link><guid>{e(c['url'])}</guid>"
        f"<pubDate>{dt.datetime.fromisoformat(c['datum']).strftime('%a, %d %b %Y 08:00:00 +0100')}</pubDate>"
        f"<description>{e(c['perex'])}</description></item>\n" for c in vydane)
    (VYSTUP / "rss.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel><title>{e(cfg["nazev"])}</title>'
        f'<link>{zaklad}/</link><description>{e(cfg["uvod"])}</description><language>cs</language>\n{polozky}</channel></rss>\n',
        encoding="utf-8")
    # pro rozesílku: všechno vydané (články i zápisky), nejnovější první; ohlašuje se to první
    (VYSTUP / "clanky.json").write_text(json.dumps(
        [{"slug": c["slug"], "nazev": c["nazev"], "perex": c["perex"], "url": c["url"], "datum": c["datum"], "druh": c["druh"]}
         for c in venku if c.get("koncept") != "ano"], ensure_ascii=False, indent=1), encoding="utf-8")
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
