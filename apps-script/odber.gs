/**
 * Odběr nových článků blogu Nová cesta (Google Apps Script).
 *
 * Co dělá:
 *  - přihlášení z formuláře na webu (doPost, akce=prihlasit) a potvrzovací e-mail,
 *  - potvrzení a odhlášení odkazem z e-mailu (doGet, akce=potvrdit / odhlasit),
 *  - rozeslání nového článku, když ho web ohlásí po zveřejnění (doPost, akce=novy-clanek + klíč),
 *  - hlídá denní limit e-mailů Googlu; co se nestihne, dopošle každou hodinu funkce rozeslat().
 *
 * Nastavení (jednou): vložit do projektu Apps Script v Gmailu pro blog, spustit funkci nastavit(),
 * povolit oprávnění, pak Nasadit → Nové nasazení → Webová aplikace (Spustit jako: Já, Přístup: Kdokoli).
 * Postup krok za krokem je v README.md.
 */

var NASTAVENI = {
  nazevWebu: 'Nová cesta',
  odesilatel: 'Michal Nedvídek | Nová cesta',
  odpovediNa: 'michal@nanoveceste.cz',
  odeslatZ: 'michal@nanoveceste.cz',   // adresa na doméně, přidaná v Gmailu jako „Odesílat poštu jako“
  webUrl: 'https://nedvidekm.github.io/nova-cesta/'
};

var LIST_ODBERATELE = 'Odběratelé';
var LIST_CLANKY = 'Články';

// ---------- jednorázové nastavení ----------

function nastavit() {
  var ss = tabulka_();
  var o = ss.getSheetByName(LIST_ODBERATELE) || ss.insertSheet(LIST_ODBERATELE);
  if (o.getLastRow() === 0) o.appendRow(['E-mail', 'Stav', 'Token', 'Přihlášen', 'Potvrzen', 'Poslední rozeslaný článek']);
  var c = ss.getSheetByName(LIST_CLANKY) || ss.insertSheet(LIST_CLANKY);
  if (c.getLastRow() === 0) c.appendRow(['Slug', 'Název', 'Adresa', 'Perex', 'Ohlášeno']);
  var vychozi = ss.getSheetByName('List1') || ss.getSheetByName('Sheet1');
  if (vychozi && ss.getSheets().length > 2) ss.deleteSheet(vychozi);

  var vlastnosti = PropertiesService.getScriptProperties();
  if (!vlastnosti.getProperty('KLIC')) vlastnosti.setProperty('KLIC', Utilities.getUuid());

  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'rozeslat') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('rozeslat').timeBased().everyHours(1).create();

  Logger.log('Tabulka: ' + ss.getUrl());
  Logger.log('Klíč pro GitHub (secret ODBER_KLIC): ' + vlastnosti.getProperty('KLIC'));
  var aliasy = GmailApp.getAliases();  // zároveň si vyžádá oprávnění k Gmailu
  Logger.log(aliasy.indexOf(NASTAVENI.odeslatZ) >= 0
    ? 'E-maily odejdou z adresy ' + NASTAVENI.odeslatZ
    : 'Adresa ' + NASTAVENI.odeslatZ + ' v Gmailu není nastavená jako „Odesílat poštu jako“, e-maily odejdou z ' + Session.getEffectiveUser().getEmail());
}

function tabulka_() {
  var vlastnosti = PropertiesService.getScriptProperties();
  var id = vlastnosti.getProperty('TABULKA_ID');
  if (id) return SpreadsheetApp.openById(id);
  var ss = SpreadsheetApp.create('Nová cesta – odběratelé');
  vlastnosti.setProperty('TABULKA_ID', ss.getId());
  return ss;
}

// ---------- webová aplikace ----------

function doPost(e) {
  var p = (e && e.parameter) || {};
  var zamek = LockService.getScriptLock();
  zamek.waitLock(20000);
  try {
    if (p.akce === 'prihlasit') return json_(prihlasit_(p.email));
    if (p.akce === 'novy-clanek') {
      if (p.klic !== PropertiesService.getScriptProperties().getProperty('KLIC')) return json_({ ok: false, chyba: 'klic' });
      var novy = ohlasitClanek_(p);
      zamek.releaseLock();
      if (novy) rozeslat();
      return json_({ ok: true, novy: novy });
    }
    return json_({ ok: false, chyba: 'akce' });
  } finally {
    try { zamek.releaseLock(); } catch (x) {}
  }
}

function doGet(e) {
  var p = (e && e.parameter) || {};
  var radek = najdiPodleTokenu_(p.t);
  if (!radek) return stranka_('Odkaz už neplatí', 'Tenhle odkaz už neplatí. Možná jste odběr mezitím zrušili nebo znovu potvrdili.');
  var list = tabulka_().getSheetByName(LIST_ODBERATELE);
  if (p.akce === 'potvrdit') {
    list.getRange(radek, 2).setValue('potvrzeno');
    list.getRange(radek, 5).setValue(new Date());
    list.getRange(radek, 6).setValue(posledniClanek_() ? posledniClanek_().slug : '');
    return stranka_('Děkuji, odběr je potvrzený', 'Kdykoli na blogu ' + NASTAVENI.nazevWebu + ' přibude nový článek, pošlu vám e-mail.');
  }
  if (p.akce === 'odhlasit') {
    list.deleteRow(radek);
    return stranka_('Odběr je zrušený', 'Vaši adresu jsem z odběru smazal. Kdybyste si to rozmysleli, přihlásit se můžete znovu na webu.');
  }
  return stranka_(NASTAVENI.nazevWebu, '');
}

// ---------- přihlášení ----------

function prihlasit_(email) {
  email = String(email || '').trim().toLowerCase();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) || email.length > 200) return { ok: false, chyba: 'email' };
  var list = tabulka_().getSheetByName(LIST_ODBERATELE);
  var data = list.getDataRange().getValues();
  var token = Utilities.getUuid();
  for (var i = 1; i < data.length; i++) {
    if (data[i][0] === email) {
      if (data[i][1] === 'potvrzeno') return { ok: true };
      list.getRange(i + 1, 3).setValue(token);
      posliPotvrzeni_(email, token);
      return { ok: true };
    }
  }
  list.appendRow([email, 'čeká', token, new Date(), '', '']);
  posliPotvrzeni_(email, token);
  return { ok: true };
}

function posliPotvrzeni_(email, token) {
  if (MailApp.getRemainingDailyQuota() < 1) return;
  var odkaz = ScriptApp.getService().getUrl() + '?akce=potvrdit&t=' + token;
  posli_({
    to: email,
    subject: 'Potvrďte prosím odběr blogu ' + NASTAVENI.nazevWebu,
    body: 'Dobrý den,\n\nděkuji za zájem o blog ' + NASTAVENI.nazevWebu + '. Odběr prosím potvrďte kliknutím na odkaz:\n' + odkaz +
      '\n\nPokud jste se nepřihlašovali, tento e-mail ignorujte.\n\nMichal Nedvídek',
    htmlBody: obalEmailu_('<p>Dobrý den,</p><p>děkuji za zájem o blog ' + NASTAVENI.nazevWebu + '. Odběr prosím potvrďte kliknutím na tlačítko:</p>' +
      tlacitko_(odkaz, 'Potvrdit odběr') + '<p style="color:#6b665e;font-size:14px">Pokud jste se nepřihlašovali, tento e-mail ignorujte.</p><p>Michal Nedvídek</p>')
  });
}

/**
 * Odeslání e-mailu. Když je v Gmailu adresa NASTAVENI.odeslatZ nastavená jako „Odesílat poštu jako“,
 * odejde e-mail z ní (přes poštovní server domény). Když tam není, odejde z gmailové adresy účtu
 * a odpovědi míří na adresu na doméně. Rozesílka tak běží dál, i kdyby alias z Gmailu zmizel.
 */
function posli_(m) {
  var opt = { name: NASTAVENI.odesilatel, replyTo: NASTAVENI.odpovediNa, htmlBody: m.htmlBody };
  if (GmailApp.getAliases().indexOf(NASTAVENI.odeslatZ) >= 0) opt.from = NASTAVENI.odeslatZ;
  GmailApp.sendEmail(m.to, m.subject, m.body, opt);
}

// ---------- rozesílání článků ----------

function ohlasitClanek_(p) {
  if (!p.slug || !p.nazev || !p.url) return false;
  var list = tabulka_().getSheetByName(LIST_CLANKY);
  var slugy = list.getRange(1, 1, Math.max(list.getLastRow(), 1), 1).getValues().map(function (r) { return r[0]; });
  if (slugy.indexOf(p.slug) !== -1) return false;
  list.appendRow([p.slug, p.nazev, p.url, p.perex || '', new Date()]);
  return true;
}

function posledniClanek_() {
  var list = tabulka_().getSheetByName(LIST_CLANKY);
  if (list.getLastRow() < 2) return null;
  var r = list.getRange(list.getLastRow(), 1, 1, 4).getValues()[0];
  return { slug: r[0], nazev: r[1], url: r[2], perex: r[3] };
}

/** Pošle nejnovější článek všem potvrzeným odběratelům, kteří ho ještě nedostali. Spouští se i každou hodinu. */
function rozeslat() {
  var clanek = posledniClanek_();
  if (!clanek) return;
  var zamek = LockService.getScriptLock();
  if (!zamek.tryLock(20000)) return;
  try {
    var list = tabulka_().getSheetByName(LIST_ODBERATELE);
    var data = list.getDataRange().getValues();
    for (var i = 1; i < data.length; i++) {
      if (data[i][1] !== 'potvrzeno' || data[i][5] === clanek.slug) continue;
      if (MailApp.getRemainingDailyQuota() < 1) break; // zbytek dopošle další spuštění
      var odhlasit = ScriptApp.getService().getUrl() + '?akce=odhlasit&t=' + data[i][2];
      posli_({
        to: data[i][0],
        subject: 'Nový článek: ' + clanek.nazev,
        body: clanek.nazev + '\n\n' + clanek.perex + '\n\nČíst dál: ' + clanek.url + '\n\nMichal Nedvídek\n\nOdhlásit odběr: ' + odhlasit,
        htmlBody: obalEmailu_('<h1 style="font-family:Georgia,serif;font-size:26px;color:#3c3c3b;margin:0 0 12px">' + esc_(clanek.nazev) + '</h1>' +
          '<p>' + esc_(clanek.perex) + '</p>' + tlacitko_(clanek.url, 'Číst článek') + '<p>Michal Nedvídek</p>', odhlasit)
      });
      list.getRange(i + 1, 6).setValue(clanek.slug);
    }
  } finally {
    zamek.releaseLock();
  }
}

// ---------- pomocné ----------

function najdiPodleTokenu_(t) {
  if (!t) return 0;
  var data = tabulka_().getSheetByName(LIST_ODBERATELE).getDataRange().getValues();
  for (var i = 1; i < data.length; i++) if (data[i][2] === t) return i + 1;
  return 0;
}

function obalEmailu_(obsah, odhlasit) {
  var pata = '<p style="color:#6b665e;font-size:13px;border-top:1px solid #e3dccf;padding-top:12px;margin-top:24px">' +
    '<a href="' + NASTAVENI.webUrl + '" style="color:#6b665e">' + NASTAVENI.nazevWebu + '</a> · Michal na cestě' +
    (odhlasit ? ' · <a href="' + odhlasit + '" style="color:#6b665e">Odhlásit odběr</a>' : '') + '</p>';
  return '<div style="max-width:560px;margin:0 auto;font-family:Georgia,serif;font-size:17px;line-height:1.6;color:#3c3c3b">' +
    '<div style="height:6px;background:#af1917;margin-bottom:20px"></div>' + obsah + pata + '</div>';
}

function tlacitko_(url, text) {
  return '<p><a href="' + url + '" style="display:inline-block;background:#af1917;color:#ffffff;text-decoration:none;font-family:Arial,sans-serif;font-weight:bold;padding:12px 20px">' + text + '</a></p>';
}

function esc_(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function json_(o) {
  return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
}

function stranka_(nadpis, text) {
  var h = '<!doctype html><html lang="cs"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
    '<title>' + esc_(nadpis) + '</title></head><body style="font-family:Georgia,serif;background:#faf7f2;color:#3c3c3b;margin:0;padding:32px 16px">' +
    '<div style="max-width:560px;margin:0 auto"><div style="height:6px;background:#af1917;margin-bottom:24px"></div>' +
    '<h1 style="font-size:28px">' + esc_(nadpis) + '</h1><p style="font-size:18px;line-height:1.6">' + esc_(text) + '</p>' +
    '<p><a href="' + NASTAVENI.webUrl + '" style="color:#af1917">Zpět na blog ' + NASTAVENI.nazevWebu + '</a></p></div></body></html>';
  return HtmlService.createHtmlOutput(h).setTitle(nadpis).addMetaTag('viewport', 'width=device-width, initial-scale=1');
}
