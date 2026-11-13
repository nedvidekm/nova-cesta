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

Skript `apps-script/odber.gs` běží v Google účtu. Ukládá odběratele do Google tabulky, posílá potvrzovací e-mail, odhlašuje a po zveřejnění nového článku ho rozešle. Co se nepodaří odeslat, dopošle další hodinu.

Odesílání: přes službu SMTP2GO (rozhraní `POST /v3/email/send`) z adresy `michal@nanoveceste.cz`, odpovědi čtenářů jdou na stejnou adresu. Tarif zdarma má 1 000 e-mailů měsíčně. Klíč služby je uložený jen ve vlastnostech skriptu (`SMTP2GO_KLIC`), v repozitáři není. Bez klíče skript odesílá přes Gmail účtu.

Nastavení SMTP2GO (jednou):
1. V SMTP2GO: Sending → Verified Senders → přidat doménu a u registrátora vytvořit CNAME záznamy, které SMTP2GO vypíše.
2. Sending → API Keys → Add API Key, oprávnění jen pro odesílání e-mailů. Klíč zkopírovat.
3. V Apps Script: Nastavení projektu → Vlastnosti skriptu → přidat vlastnost `SMTP2GO_KLIC` s klíčem.

Jednorázové nastavení:
1. V Gmailu pro blog otevřít script.google.com → Nový projekt, vložit obsah `apps-script/odber.gs`, uložit.
2. Vybrat funkci `nastavit` → Spustit → povolit oprávnění. V protokolu se objeví odkaz na tabulku, klíč a adresa, ze které e-maily odejdou.
3. Nasadit → Nové nasazení → typ Webová aplikace, Spustit jako: Já, Kdo má přístup: Kdokoli → Nasadit. Zkopírovat adresu webové aplikace.
4. Adresu vložit do `web.json` jako `odber_url`.
5. Na GitHubu v repozitáři: Settings → Secrets and variables → Actions → New repository secret: `ODBER_URL` (adresa webové aplikace) a `ODBER_KLIC` (klíč z kroku 2).

## Doména

Web běží na `nanoveceste.cz` (registrátor WEDOS, DNS u WEDOSu). Ve `web.json` je `"domena": "nanoveceste.cz"` a `zakladni_url` `https://nanoveceste.cz`, stejná adresa je v `apps-script/odber.gs` (`webUrl`). V DNS: čtyři záznamy A a čtyři AAAA na GitHub Pages, `www` jako CNAME na `nedvidekm.github.io`; na GitHubu Settings → Pages → Custom domain a Enforce HTTPS. Pošta: schránka `michal@nanoveceste.cz` u Email Profi (MX, SPF, DKIM, DMARC), rozesílka přes SMTP2GO (tři CNAME z jeho administrace).
