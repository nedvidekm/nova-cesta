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
    if (stav === 'nahled') { ukaz(ok, 'Testovací verze: nic se neodesílá. Na ostrém webu se tu ukáže, že je odběr aktivní.'); return; }
    if (stav !== 'ok') { ukaz(ok, 'Odběr právě spouštím. Zkuste to prosím za pár dní, děkuji.'); return; }
    var tlacitko = form.querySelector('button');
    tlacitko.disabled = true;
    fetch(box.getAttribute('data-url'), {
      method: 'POST', mode: 'no-cors',
      body: new URLSearchParams({ akce: 'prihlasit', email: email, stranka: location.pathname })
    }).then(function () {
      form.hidden = true;
      ukaz(ok, 'Děkuji! Odběr je aktivní a do schránky vám právě jde uvítací e-mail.');
    }).catch(function () {
      ukaz(chyba, 'Přihlášení se nepodařilo odeslat. Zkuste to prosím znovu za chvíli.');
    }).finally(function () { tlacitko.disabled = false; });
  });
})();

// Přepínač světlý / tmavý: výchozí je světlý, volba se pamatuje v prohlížeči
(function () {
  var t = document.querySelector('.menu .rezim');
  if (!t) return;
  var koren = document.documentElement;
  function popis() { t.setAttribute('aria-label', koren.dataset.theme === 'dark' ? 'Přepnout na světlý režim' : 'Přepnout na tmavý režim'); }
  t.hidden = false; popis();
  t.addEventListener('click', function () {
    koren.dataset.theme = koren.dataset.theme === 'dark' ? 'light' : 'dark';
    try { localStorage.setItem('rezim', koren.dataset.theme); } catch (x) {}
    popis();
  });
})();

// Zkopírování čísla účtu na stránce Podpořit
(function () {
  document.querySelectorAll('.qr-castky button').forEach(function (b) {
    b.addEventListener('click', function () {
      var f = b.closest('.ucet-qr');
      f.querySelector('img').src = b.getAttribute('data-qr');
      f.querySelectorAll('.qr-castky button').forEach(function (x) { x.setAttribute('aria-pressed', x === b ? 'true' : 'false'); });
    });
  });
  document.querySelectorAll('.kopirovat').forEach(function (b) {
    b.addEventListener('click', function () {
      var text = b.getAttribute('data-text');
      var zprava = document.querySelector('.ucet-ok');
      function hotovo(t) { if (zprava) { zprava.textContent = t; zprava.hidden = false; } }
      if (navigator.clipboard) {
        navigator.clipboard.writeText(text).then(function () { hotovo('Číslo účtu je zkopírované.'); },
          function () { hotovo('Zkopírovat se nepodařilo, číslo účtu prosím opište.'); });
      } else { hotovo('Zkopírovat se nepodařilo, číslo účtu prosím opište.'); }
    });
  });
})();

// Teploměr: aktuální součet příchozích plateb z transparentního účtu (Apps Script čte Fio API každých 15 minut)
(function () {
  var box = document.querySelector('.sbirka[data-url]');
  if (!box || !box.dataset.url || !window.fetch || /^(localhost|127\.)/.test(location.hostname)) return;
  var cil = Number(box.dataset.cil), stare = Number(box.dataset.vybrano);
  function kc(n) { return Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ') + ' Kč'; }
  fetch(box.dataset.url).then(function (r) { return r.json(); }).then(function (d) {
    if (!d || !d.ok || !(d.vybrano > stare)) return;
    var v = d.vybrano, presne = v * 100 / cil, pct = Math.min(100, Math.round(presne));
    var txt = (presne > 0 && presne < 10 && presne !== Math.floor(presne)) ? presne.toFixed(1).replace('.', ',') : String(pct);
    box.querySelector('.sbirka-cisla b').textContent = kc(v);
    var pruh = box.querySelector('.sbirka-pruh');
    pruh.setAttribute('aria-label', 'Vybráno ' + txt + ' % z cíle ' + kc(cil));
    pruh.querySelector('span').style.width = Math.max(pct, 1) + '%';
    var kdy = d.kdy ? new Date(d.kdy) : new Date();
    var mesice = ['ledna','února','března','dubna','května','června','července','srpna','září','října','listopadu','prosince'];
    box.querySelector('.sbirka-pozn').textContent = 'Vybráno ' + txt + ' % · stav k ' + kdy.getDate() + '. ' + mesice[kdy.getMonth()] + ' ' + kdy.getFullYear();
  }).catch(function () {});
})();
