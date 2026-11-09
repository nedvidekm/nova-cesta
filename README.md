# Nová cesta

Blog Michala Nedvídka z přípravy a roku dobrovolnictví se salesiány Dona Boska.

## Jak web funguje

- Obsah: `content/clanky/*.md` (články), `content/stranky/*.md` (O mně, Podpořit, Ochrana osobních údajů), fotky v `content/fotky/`, nastavení v `web.json` (adresa webu, kontakt, ukazatel kurzu, „Připravuji“).
- Článek s `koncept: ano` se na ostrý web nedostane, jen do testovací verze.
- Sestavení: `python3 build.py` (ostrý web do `_site/`), `python3 build.py --nahled` (testovací verze s pruhem a noindex). Fotky se samy zmenší na 1 300 px.
- Kontrola před nasazením: `node kontrola.js` (všechny stránky, šířky 320–1440 px, světlý i tmavý režim, odkazy, přetékání, kontrast). `--rychla` jen pro 3 šířky.
- Zveřejnění: po sloučení do větve `main` web sestaví a zveřejní GitHub Actions (`.github/workflows/web.yml`) na GitHub Pages.

## Odběr e-mailem (Google)

Skript `apps-script/odber.gs` běží v Gmailu určeném pro blog. Ukládá odběratele do Google tabulky, posílá potvrzovací e-mail, odhlašuje a po zveřejnění nového článku ho rozešle. Odpovědi čtenářů jdou na `michal@nanoveceste.cz`. Běžný Google účet pošle 100 e-mailů denně, co se nestihne, skript dopošle další den.

Jednorázové nastavení:
1. V Gmailu pro blog otevřít script.google.com → Nový projekt, vložit obsah `apps-script/odber.gs`, uložit.
2. Vybrat funkci `nastavit` → Spustit → povolit oprávnění. V protokolu se objeví odkaz na tabulku a klíč.
3. Nasadit → Nové nasazení → typ Webová aplikace, Spustit jako: Já, Kdo má přístup: Kdokoli → Nasadit. Zkopírovat adresu webové aplikace.
4. Adresu vložit do `web.json` jako `odber_url`.
5. Na GitHubu v repozitáři: Settings → Secrets and variables → Actions → New repository secret: `ODBER_URL` (adresa webové aplikace) a `ODBER_KLIC` (klíč z kroku 2).

## Doména

Až bude koupená `nanoveceste.cz`: do `web.json` doplnit `"domena": "nanoveceste.cz"` a změnit `zakladni_url` na `https://nanoveceste.cz`, u registrátora nastavit DNS na GitHub Pages a v Settings → Pages zapnout Enforce HTTPS. Totéž upravit v `apps-script/odber.gs` (`webUrl`).
