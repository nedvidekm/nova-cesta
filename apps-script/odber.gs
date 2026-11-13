/**
 * Odběr nových článků blogu Nová cesta (Google Apps Script).
 *
 * Co dělá:
 *  - přihlášení z formuláře na webu (doPost, akce=prihlasit) a potvrzovací e-mail,
 *  - potvrzení a odhlášení odkazem z e-mailu (doGet, akce=potvrdit / odhlasit),
 *  - rozeslání nového článku, když ho web ohlásí po zveřejnění (doPost, akce=novy-clanek + klíč),
 *  - e-maily odcházejí přes SMTP2GO z adresy na doméně; co se nepodaří odeslat, dopošle každou hodinu funkce rozeslat().
 *
 * Nastavení (jednou): vložit do projektu Apps Script v Gmailu pro blog, spustit funkci nastavit(),
 * povolit oprávnění, pak Nasadit → Nové nasazení → Webová aplikace (Spustit jako: Já, Přístup: Kdokoli).
 * Postup krok za krokem je v README.md.
 */

var NASTAVENI = {
  nazevWebu: 'Nová cesta',
  odesilatel: 'Michal Nedvídek | Nová cesta',
  odpovediNa: 'michal@nanoveceste.cz',
  odeslatZ: 'michal@nanoveceste.cz',   // adresa odesílatele na doméně ověřené v SMTP2GO
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
  if (vlastnosti.getProperty('SMTP2GO_KLIC')) {
    Logger.log('E-maily odejdou přes SMTP2GO z adresy ' + NASTAVENI.odeslatZ);
  } else {
    var aliasy = GmailApp.getAliases();
    Logger.log('Klíč SMTP2GO_KLIC ve vlastnostech skriptu chybí, e-maily odejdou přes Gmail z adresy ' +
      (aliasy.indexOf(NASTAVENI.odeslatZ) >= 0 ? NASTAVENI.odeslatZ : Session.getEffectiveUser().getEmail()));
  }
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
 * Odeslání e-mailu. Vrací true, když e-mail odešel.
 *
 * 1) Když je ve vlastnostech skriptu klíč SMTP2GO_KLIC, odejde e-mail přes službu SMTP2GO
 *    z adresy NASTAVENI.odeslatZ (doména musí být v SMTP2GO ověřená).
 * 2) Bez klíče odejde přes Gmail účtu: z adresy na doméně, pokud je v Gmailu nastavená jako
 *    „Odesílat poštu jako“, jinak z gmailové adresy s odpovědí na doménu.
 */
function posli_(m) {
  var klic = PropertiesService.getScriptProperties().getProperty('SMTP2GO_KLIC');
  if (klic) return posliSmtp2go_(m, klic);
  if (MailApp.getRemainingDailyQuota() < 1) return false;
  var opt = { name: NASTAVENI.odesilatel, replyTo: NASTAVENI.odpovediNa, htmlBody: m.htmlBody };
  if (GmailApp.getAliases().indexOf(NASTAVENI.odeslatZ) >= 0) opt.from = NASTAVENI.odeslatZ;
  GmailApp.sendEmail(m.to, m.subject, m.body, opt);
  return true;
}

/** SMTP2GO: POST /v3/email/send. Odpověď 200 může nést chybu, proto se čte data.succeeded. */
function posliSmtp2go_(m, klic) {
  var hlavicky = [{ header: 'Reply-To', value: NASTAVENI.odpovediNa }];
  if (m.odhlasit) hlavicky.push({ header: 'List-Unsubscribe', value: '<' + m.odhlasit + '>' });
  var odp = UrlFetchApp.fetch('https://eu-api.smtp2go.com/v3/email/send', {
    method: 'post',
    contentType: 'application/json',
    headers: { 'X-Smtp2go-Api-Key': klic },
    muteHttpExceptions: true,
    payload: JSON.stringify({
      sender: NASTAVENI.odesilatel + ' <' + NASTAVENI.odeslatZ + '>',
      to: [m.to],
      subject: m.subject,
      text_body: m.body,
      html_body: m.htmlBody,
      custom_headers: hlavicky
    })
  });
  var ok = false;
  try { ok = odp.getResponseCode() === 200 && JSON.parse(odp.getContentText()).data.succeeded === 1; } catch (x) {}
  if (!ok) console.error('SMTP2GO neodeslalo (' + odp.getResponseCode() + '): ' + odp.getContentText().slice(0, 300));
  return ok;
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
      var odhlasit = ScriptApp.getService().getUrl() + '?akce=odhlasit&t=' + data[i][2];
      var odeslano = posli_({
        to: data[i][0],
        odhlasit: odhlasit,
        subject: 'Nový článek: ' + clanek.nazev,
        body: clanek.nazev + '\n\n' + clanek.perex + '\n\nČíst dál: ' + clanek.url + '\n\nMichal Nedvídek\n\nOdhlásit odběr: ' + odhlasit,
        htmlBody: obalEmailu_('<h1 style="font-family:Georgia,serif;font-size:26px;color:#3c3c3b;margin:0 0 12px">' + esc_(clanek.nazev) + '</h1>' +
          '<p>' + esc_(clanek.perex) + '</p>' + tlacitko_(clanek.url, 'Číst článek') + '<p>Michal Nedvídek</p>', odhlasit)
      });
      if (!odeslano) break; // limit nebo chyba služby: zbytek dopošle další spuštění
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
