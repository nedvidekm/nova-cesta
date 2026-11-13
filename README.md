# Nová cesta

Blog Michala Nedvídka z přípravy a roku dobrovolnictví v zahraničí.

## Jak web funguje

- Obsah: `content/clanky/*.md` (články), `content/stranky/*.md` (O mně, Podpořit, Ochrana osobních údajů), fotky v `content/fotky/`, nastavení v `web.json` (adresa webu, kontakt, ukazatel kurzu, „Připravuji“).
- `"testovaci_verze": true` ve `web.json`: zveřejněný web je testovací (pruh nahoře, noindex, koncepty viditelné, odběr nic neodesílá). Před spuštěním přepnout na `false`.
- Článek s `koncept: ano` se na ostrý web nedostane, jen do testovací verze.
- Sestavení: `python3 build.py` (ostrý web do `_site/`), `python3 build.py --nahled` (testovací verze s pruhem a noindex). Fotky se samy zmenší na 1 300 px.
- Kontrola před nasazením: `node kontrola.js` (všechny stránky, šířky 320–1440 px, světlý i tmavý režim, odkazy, přetékání, kontrast). `--rychla` jen pro 3 šířky.
- Zveřejnění: po sloučení do větve `main` web sestaví a zveřejní GitHub Actions (`.github/workflows/web.yml`) na GitHub Pages.

## Odběr e-mailem (Google)

Skript `apps-script/odber.gs` běží v Google účtu s Gmailem. Ukládá odběratele do Google tabulky, posílá potvrzovací e-mail, odhlašuje a po zveřejnění nového článku ho rozešle. Běžný Google účet pošle 100 e-mailů denně, co se nestihne, skript dopošle další den.

Odesílatel: když je v Gmailu adresa `michal@nanoveceste.cz` přidaná jako „Odesílat poštu jako“ (Nastavení → Účty a import, přes SMTP poštovní služby domény), odcházejí e-maily z ní. Když tam není, odejdou z gmailové adresy účtu a odpovědi míří na `michal@nanoveceste.cz`. Google podle své nápovědy (support.google.com/mail/answer/22370) od ledna 2027 „Odesílat poštu jako“ pro adresy mimo Google ruší; skript pak sám přejde na druhou variantu.

Jednorázové nastavení:
1. V Gmailu pro blog otevřít script.google.com → Nový projekt, vložit obsah `apps-script/odber.gs`, uložit.
2. Vybrat funkci `nastavit` → Spustit → povolit oprávnění. V protokolu se objeví odkaz na tabulku, klíč a adresa, ze které e-maily odejdou.
3. Nasadit → Nové nasazení → typ Webová aplikace, Spustit jako: Já, Kdo má přístup: Kdokoli → Nasadit. Zkopírovat adresu webové aplikace.
4. Adresu vložit do `web.json` jako `odber_url`.
5. Na GitHubu v repozitáři: Settings → Secrets and variables → Actions → New repository secret: `ODBER_URL` (adresa webové aplikace) a `ODBER_KLIC` (klíč z kroku 2).

## Doména

Až bude koupená `nanoveceste.cz`: do `web.json` doplnit `"domena": "nanoveceste.cz"` a změnit `zakladni_url` na `https://nanoveceste.cz`, u registrátora nastavit DNS na GitHub Pages a v Settings → Pages zapnout Enforce HTTPS. Totéž upravit v `apps-script/odber.gs` (`webUrl`).
