// Přihlášení k odběru nových článků (Google Apps Script, viz apps-script/odber.gs)
(function () {
  var box = document.getElementById('odber');
  var form = document.getElementById('f-odber');
  if (!box || !form) return;
  var ok = document.getElementById('odber-ok');
  var chyba = document.getElementById('odber-chyba');
  function ukaz(el, text) { ok.hidden = chyba.hidden = true; el.textContent = text; el.hidden = false; }

  form.addEventListener('submit', function (ev) {
    ev.preventDefault();
    var email = form.email.value.trim();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { ukaz(chyba, 'Zkontrolujte prosím e-mailovou adresu.'); form.email.focus(); return; }
    if (!form.souhlas.checked) { ukaz(chyba, 'Potvrďte prosím souhlas se zasíláním článků.'); form.souhlas.focus(); return; }
    if (form.web.value) return; // ochrana proti robotům
    var stav = box.getAttribute('data-stav');
    if (stav === 'nahled') { ukaz(ok, 'Testovací verze: nic se neodesílá. Na ostrém webu sem přijde potvrzení přihlášení.'); return; }
    if (stav !== 'ok') { ukaz(ok, 'Odběr právě spouštím. Zkuste to prosím za pár dní, děkuji.'); return; }
    var tlacitko = form.querySelector('button');
    tlacitko.disabled = true;
    fetch(box.getAttribute('data-url'), {
      method: 'POST', mode: 'no-cors',
      body: new URLSearchParams({ akce: 'prihlasit', email: email, stranka: location.pathname })
    }).then(function () {
      form.hidden = true;
      ukaz(ok, 'Děkuji! Poslal jsem vám e-mail. Klikněte v něm prosím na odkaz a odběr tím potvrďte.');
    }).catch(function () {
      ukaz(chyba, 'Přihlášení se nepodařilo odeslat. Zkuste to prosím znovu za chvíli.');
    }).finally(function () { tlacitko.disabled = false; });
  });
})();
