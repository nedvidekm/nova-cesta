/**
 * Teploměr sbírky na nanoveceste.cz: samostatný skript (nezávislý na odběru e-mailů).
 * Každých 15 minut se zeptá Fio API na příchozí platby na transparentní účet a sečte je.
 * Web si součet načte z adresy této webové aplikace.
 * Záznamy: ?akce=historie vrátí posledních 100 běhů (čas, odpověď Fio, nové platby, součet)
 * a posledních 60 nepovedených načtení teploměru na webu (s důvodem).
 *
 * Nastavení: Vlastnosti skriptu → FIO_TOKEN = token Fio API (Sledování účtu).
 * Pak jednou spustit funkci nastavitKontroluUctu a nasadit jako webovou aplikaci
 * (Spustit jako: Já, Kdo má přístup: Kdokoli).
 */

var FIO_OD = '2026-11-16'; // od tohoto dne se platby počítají

function doGet(e) {
  var vl = PropertiesService.getScriptProperties();
  var akce = e && e.parameter && e.parameter.akce;
  if (akce === 'web') { // web hlásí jen nepovedená načtení teploměru (úspěšná se nezapisují)
    var p = e.parameter;
    if (p.ok === '1') return json_({ ok: true });
    pripsat_('WEB_ZAZNAM', { t: new Date().toISOString(), ok: p.ok === '1', v: Number(p.v || 0), chyba: String(p.chyba || '').slice(0, 80), str: String(p.str || '').slice(0, 30) }, 60);
    return json_({ ok: true });
  }
  if (akce === 'historie') {
    return json_({ ok: true, behy: nacti_('HISTORIE'), web: nacti_('WEB_ZAZNAM') });
  }
  return json_({ ok: true, vybrano: Number(vl.getProperty('VYBRANO') || 0), kdy: vl.getProperty('FIO_STAV_KDY') || '' });
}

function json_(data) {
  return ContentService.createTextOutput(JSON.stringify(data)).setMimeType(ContentService.MimeType.JSON);
}

function nacti_(klic) {
  try { return JSON.parse(PropertiesService.getScriptProperties().getProperty(klic) || '[]'); } catch (x) { return []; }
}

/** Přidá záznam na konec seznamu ve vlastnostech skriptu, drží jen posledních max záznamů. */
function pripsat_(klic, zaznam, max) {
  var zamek = LockService.getScriptLock();
  try {
    zamek.waitLock(5000);
    var seznam = nacti_(klic);
    seznam.push(zaznam);
    if (seznam.length > max) seznam = seznam.slice(seznam.length - max);
    PropertiesService.getScriptProperties().setProperty(klic, JSON.stringify(seznam));
  } catch (x) {
    console.log('Záznam se nepovedl: ' + x);
  } finally {
    try { zamek.releaseLock(); } catch (x) {}
  }
}

function nactiFio() {
  var vl = PropertiesService.getScriptProperties();
  var token = vl.getProperty('FIO_TOKEN');
  if (!token) { console.log('Chybí vlastnost FIO_TOKEN'); return; }
  var dnes = new Date();
  var od = new Date(dnes.getTime() - 30 * 24 * 3600 * 1000);
  var start = new Date(FIO_OD + 'T00:00:00');
  if (od < start) od = start;
  var f = function (d) { return Utilities.formatDate(d, 'Europe/Prague', 'yyyy-MM-dd'); };
  var odpoved = UrlFetchApp.fetch('https://fioapi.fio.cz/v1/rest/periods/' + token + '/' + f(od) + '/' + f(dnes) + '/transactions.json', { muteHttpExceptions: true });
  if (odpoved.getResponseCode() !== 200) {
    console.log('Fio odpověď ' + odpoved.getResponseCode());
    pripsat_('HISTORIE', { t: new Date().toISOString(), fio: odpoved.getResponseCode() }, 100);
    return;
  }
  var vypis = JSON.parse(odpoved.getContentText()).accountStatement || {};
  var pohyby = (vypis.transactionList && vypis.transactionList.transaction) || [];
  var vybrano = Number(vl.getProperty('VYBRANO') || 0);
  var posledni = Number(vl.getProperty('FIO_POSLEDNI_ID') || 0);
  var nejvyssi = posledni, novych = 0;
  pohyby.forEach(function (t) {
    var id = t.column22 && Number(t.column22.value);
    var castka = t.column1 && Number(t.column1.value);
    if (!id || id <= posledni) return; // každý pohyb jen jednou
    if (castka > 0) { vybrano += castka; novych++; }  // jen příchozí platby
    if (id > nejvyssi) nejvyssi = id;
  });
  vl.setProperties({ VYBRANO: String(Math.round(vybrano * 100) / 100), FIO_POSLEDNI_ID: String(nejvyssi), FIO_STAV_KDY: new Date().toISOString() });
  pripsat_('HISTORIE', { t: new Date().toISOString(), fio: 200, pohybu: pohyby.length, novych: novych, v: Math.round(vybrano * 100) / 100 }, 100);
  console.log('Vybráno celkem: ' + vybrano + ' Kč');
}

/** Spustit JEDNOU ručně: nastaví kontrolu účtu každých 15 minut a hned ji provede. */
function nastavitKontroluUctu() {
  ScriptApp.getProjectTriggers().forEach(function (t) { if (t.getHandlerFunction() === 'nactiFio') ScriptApp.deleteTrigger(t); });
  ScriptApp.newTrigger('nactiFio').timeBased().everyMinutes(15).create();
  nactiFio();
}
