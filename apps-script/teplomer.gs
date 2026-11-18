/**
 * Teploměr sbírky na nanoveceste.cz: samostatný skript (nezávislý na odběru e-mailů).
 * Každých 15 minut se zeptá Fio API na příchozí platby na transparentní účet a sečte je.
 * Web si součet načte z adresy této webové aplikace (?akce=stav).
 *
 * Nastavení: Vlastnosti skriptu → FIO_TOKEN = token Fio API (Sledování účtu).
 * Pak jednou spustit funkci nastavitKontroluUctu a nasadit jako webovou aplikaci
 * (Spustit jako: Já, Kdo má přístup: Kdokoli).
 */

var FIO_OD = '2026-11-16'; // od tohoto dne se platby počítají

function doGet() {
  var vl = PropertiesService.getScriptProperties();
  var data = { ok: true, vybrano: Number(vl.getProperty('VYBRANO') || 0), kdy: vl.getProperty('FIO_STAV_KDY') || '' };
  return ContentService.createTextOutput(JSON.stringify(data)).setMimeType(ContentService.MimeType.JSON);
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
  if (odpoved.getResponseCode() !== 200) { console.log('Fio odpověď ' + odpoved.getResponseCode()); return; }
  var vypis = JSON.parse(odpoved.getContentText()).accountStatement || {};
  var pohyby = (vypis.transactionList && vypis.transactionList.transaction) || [];
  var vybrano = Number(vl.getProperty('VYBRANO') || 0);
  var posledni = Number(vl.getProperty('FIO_POSLEDNI_ID') || 0);
  var nejvyssi = posledni;
  pohyby.forEach(function (t) {
    var id = t.column22 && Number(t.column22.value);
    var castka = t.column1 && Number(t.column1.value);
    if (!id || id <= posledni) return; // každý pohyb jen jednou
    if (castka > 0) vybrano += castka;  // jen příchozí platby
    if (id > nejvyssi) nejvyssi = id;
  });
  vl.setProperties({ VYBRANO: String(Math.round(vybrano * 100) / 100), FIO_POSLEDNI_ID: String(nejvyssi), FIO_STAV_KDY: new Date().toISOString() });
  console.log('Vybráno celkem: ' + vybrano + ' Kč');
}

/** Spustit JEDNOU ručně: nastaví kontrolu účtu každých 15 minut a hned ji provede. */
function nastavitKontroluUctu() {
  ScriptApp.getProjectTriggers().forEach(function (t) { if (t.getHandlerFunction() === 'nactiFio') ScriptApp.deleteTrigger(t); });
  ScriptApp.newTrigger('nactiFio').timeBased().everyMinutes(15).create();
  nactiFio();
}
