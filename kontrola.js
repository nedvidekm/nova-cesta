// Kontrola webu před nasazením (bod 13): node kontrola.js [--rychla]
// Sestavený web v _site/ projde ve všech šířkách, ve světlém i tmavém režimu.
// Hlídá: chyby v konzoli, nefunkční vnitřní odkazy a obrázky, přetékání každého prvku,
// jednu h1, délku titulku a popisu, alt texty, kontrast textu (WCAG AA), velikost dotykových ploch.
const http = require('http');
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');
const AXE = fs.readFileSync(require.resolve('axe-core/axe.min.js'), 'utf8');

const KOREN = path.join(__dirname, '_site');
const RYCHLA = process.argv.includes('--rychla');
const SIRKY = RYCHLA ? [320, 390, 1280] : [320, 360, 375, 390, 412, 768, 1024, 1280, 1440];
const REZIMY = ['light', 'dark'];
const TYPY = { '.html': 'text/html; charset=utf-8', '.css': 'text/css', '.js': 'text/javascript', '.svg': 'image/svg+xml', '.jpg': 'image/jpeg', '.png': 'image/png', '.xml': 'application/xml', '.json': 'application/json', '.txt': 'text/plain' };

function server() {
  return new Promise(res => {
    const s = http.createServer((req, odp) => {
      let p = decodeURIComponent(req.url.split('?')[0].split('#')[0]);
      let f = path.join(KOREN, p);
      if (fs.existsSync(f) && fs.statSync(f).isDirectory()) f = path.join(f, 'index.html');
      if (!fs.existsSync(f)) { odp.writeHead(404); odp.end('404'); return; }
      odp.writeHead(200, { 'Content-Type': TYPY[path.extname(f)] || 'application/octet-stream' });
      fs.createReadStream(f).pipe(odp);
    }).listen(0, () => res(s));
  });
}

function stranky() {
  const out = [];
  (function projdi(d) {
    for (const x of fs.readdirSync(d)) {
      const f = path.join(d, x);
      if (fs.statSync(f).isDirectory()) projdi(f);
      else if (x === 'index.html') out.push('/' + path.relative(KOREN, d).split(path.sep).join('/') + (d === KOREN ? '' : '/'));
    }
  })(KOREN);
  return out.map(p => p.replace('//', '/'));
}

(async () => {
  const srv = await server();
  const zaklad = `http://127.0.0.1:${srv.address().port}`;
  const prohlizec = await chromium.launch();
  const nalezy = [];
  const pridej = (str, co) => nalezy.push(`${str}: ${co}`);
  const seznam = stranky();
  const overeneOdkazy = new Map();

  for (const rezim of REZIMY) {
    for (const sirka of SIRKY) {
      const ctx = await prohlizec.newContext({ viewport: { width: sirka, height: 800 }, colorScheme: rezim });
      await ctx.addInitScript(r => { try { localStorage.setItem('rezim', r); } catch (x) {} }, rezim);  // web je výchozí světlý, tmavý se zapíná přepínačem
      const page = await ctx.newPage();
      for (const str of seznam) {
        const kde = `${str} [${sirka}px, ${rezim}]`;
        const chyby = [];
        page.removeAllListeners('console'); page.removeAllListeners('pageerror'); page.removeAllListeners('requestfailed');
        page.on('console', m => { if (m.type() === 'error') chyby.push(m.text()); });
        page.on('pageerror', e => chyby.push(String(e)));
        page.on('requestfailed', r => { if (r.url().startsWith(zaklad)) chyby.push('nenačteno ' + r.url()); });
        const odp = await page.goto(zaklad + str, { waitUntil: 'networkidle' }).catch(e => null);
        if (!odp || odp.status() !== 200) { pridej(kde, 'stránka se nenačetla'); continue; }
        await page.evaluate(() => document.fonts && document.fonts.ready);
        chyby.filter(c => !/fonts\.(googleapis|gstatic)/.test(c)).forEach(c => pridej(kde, 'chyba: ' + c));

        const v = await page.evaluate(() => {
          const out = { preteka: [], h1: document.querySelectorAll('h1').length, alt: [], kontrast: [], male: [], odkazy: [] };
          const sirka = document.documentElement.clientWidth;
          if (document.documentElement.scrollWidth > sirka) out.preteka.push(`stránka ${document.documentElement.scrollWidth} > ${sirka}`);
          const popis = el => el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\s+/).join('.') : '');
          const rgb = s => { const m = s.match(/[\d.]+/g); return m ? m.map(Number) : [0, 0, 0, 1]; };
          const lum = c => { const a = c.slice(0, 3).map(x => { x /= 255; return x <= 0.03928 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4); }); return 0.2126 * a[0] + 0.7152 * a[1] + 0.0722 * a[2]; };
          const pozadi = el => { while (el) { const c = rgb(getComputedStyle(el).backgroundColor); if (c.length < 4 || c[3] > 0.5) { if (getComputedStyle(el).backgroundColor !== 'rgba(0, 0, 0, 0)') return c; } el = el.parentElement; } return [255, 255, 255, 1]; };
          for (const el of document.querySelectorAll('body *')) {
            const cs = getComputedStyle(el);
            if (cs.display === 'none' || cs.visibility === 'hidden') continue;
            const r = el.getBoundingClientRect();
            if (r.width === 0 && r.height === 0) continue;
            if (el.closest('.sr-only, .skip')) continue;
            const ov = cs.overflowX;
            if (ov !== 'auto' && ov !== 'hidden' && ov !== 'scroll' && el.scrollWidth > el.clientWidth + 1 && el.clientWidth > 0) out.preteka.push(`${popis(el)} ${el.scrollWidth} > ${el.clientWidth}`);
            if (r.right > sirka + 1) out.preteka.push(`${popis(el)} přesahuje okraj (${Math.round(r.right)} > ${sirka})`);
            if (el.tagName === 'IMG' && !el.hasAttribute('alt')) out.alt.push(el.src);
            const textovy = [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
            if (textovy) {
              const fg = rgb(cs.color), bg = pozadi(el);
              const k = (Math.max(lum(fg), lum(bg)) + 0.05) / (Math.min(lum(fg), lum(bg)) + 0.05);
              const velky = parseFloat(cs.fontSize) >= 24 || (parseFloat(cs.fontSize) >= 18.66 && Number(cs.fontWeight) >= 700);
              if (k < (velky ? 3 : 4.5)) out.kontrast.push(`${popis(el)} „${el.textContent.trim().slice(0, 30)}“ ${k.toFixed(2)}:1`);
              if (parseFloat(cs.fontSize) < 14) out.kontrast.push(`${popis(el)} písmo ${cs.fontSize}`);
            }
            if (el.matches('a, button, input, label.souhlas') && !el.closest('article p, article li, figcaption, .box p, .souhlas span')) {
              if (r.height < 44 && el.tagName !== 'LABEL' && !(el.type === 'checkbox')) out.male.push(`${popis(el)} „${(el.textContent || el.value || '').trim().slice(0, 20)}“ ${Math.round(r.width)}×${Math.round(r.height)}`);
            }
          }
          for (const a of document.querySelectorAll('a[href], img[src], link[href], script[src]')) out.odkazy.push(a.href || a.src);
          return out;
        });
        v.preteka.forEach(x => pridej(kde, 'přetéká: ' + x));
        if (rezim === 'light' && sirka === SIRKY[0]) {
          if (v.h1 !== 1) pridej(str, `počet h1 = ${v.h1}`);
          v.alt.forEach(x => pridej(str, 'chybí alt: ' + x));
          const t = await page.title();
          const d = await page.$eval('meta[name=description]', m => m.content).catch(() => '');
          if (t.length > 60) pridej(str, `titulek má ${t.length} znaků`);
          if (!d || d.length > 155) pridej(str, `popis má ${d.length} znaků`);
          for (const u of v.odkazy) {
            if (!u.startsWith(zaklad) || overeneOdkazy.has(u.split('#')[0])) continue;
            const r = await page.request.get(u.split('#')[0]).catch(() => null);
            overeneOdkazy.set(u.split('#')[0], r ? r.status() : 0);
            if (!r || r.status() !== 200) pridej(str, `nefunkční odkaz ${u.replace(zaklad, '')}`);
          }
        }
        if (sirka === SIRKY[0] || sirka === 1280) {
          await page.addScriptTag({ content: AXE });
          const axe = await page.evaluate(async () => (await axe.run(document, { runOnly: ['wcag2a', 'wcag2aa', 'wcag21aa', 'best-practice'] })).violations
            .map(v => `${v.id}: ${v.nodes.slice(0, 3).map(n => n.target.join(' ')).join(', ')}`));
          axe.forEach(x => pridej(kde, 'axe ' + x));
          v.kontrast.forEach(x => pridej(kde, 'kontrast: ' + x));
          v.male.forEach(x => pridej(kde, 'malá dotyková plocha: ' + x));
        }
      }
      await ctx.close();
    }
  }
  await prohlizec.close(); srv.close();
  const unik = [...new Set(nalezy)];
  console.log(`Stránek: ${seznam.length}, šířky: ${SIRKY.join(', ')}, režimy: světlý a tmavý, vnitřních odkazů ověřeno: ${overeneOdkazy.size}`);
  if (unik.length) { console.log(`NÁLEZY (${unik.length}):`); unik.forEach(x => console.log(' - ' + x)); process.exit(1); }
  console.log('Vše v pořádku, 0 nálezů.');
})();
