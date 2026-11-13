#!/usr/bin/env python3
"""Převezme hotové texty z /mnt/project-files/blog/clanky/ do content/ (hlavičky v content/ zůstávají).

- vynechá značky 📷/✏️, dočasné výzvy v hranatých závorkách a výzvu k odběru (tu má web sám),
- obrázky zkopíruje do content/fotky/ a nechá u nich popisek (řádek *…* pod obrázkem),
- odkazy na artefakty a .md soubory převede na adresy webu.
"""
import re
import shutil
from pathlib import Path

ZDROJ = Path('/mnt/project-files/blog/clanky')
KOREN = Path(__file__).resolve().parent
SOUBORY = {  # zdroj -> (cíl, adresa na webu)
    '00-o-mne.md': ('content/stranky/o-mne.md', 'o-mne/'),
    '01-proc-jedu.md': ('content/clanky/proc-jedu.md', 'clanky/proc-jedu/'),
    '02-vikend-1-ostrava.md': ('content/clanky/vikend-1-ostrava.md', 'clanky/vikend-1-ostrava/'),
}
ODKAZY = {  # artefakty a soubory -> stránky webu
    'JarPvbR6YFmA4rFU3ziZQX': 'clanky/proc-jedu/', 'FxPEtEEeTLULsTtSysr3vL': 'clanky/vikend-1-ostrava/',
    '6LNWomkNQEUWNcMjpAmUUN': 'o-mne/',
    '01-proc-jedu.md': 'clanky/proc-jedu/', '02-vikend-1-ostrava.md': 'clanky/vikend-1-ostrava/', '00-o-mne.md': 'o-mne/',
}


def relativne(z, na):
    hloubka = z.count('/')
    return '../' * hloubka + na


for jmeno, (cil, adresa) in SOUBORY.items():
    t = (ZDROJ / jmeno).read_text(encoding='utf-8')
    radky = [l for l in t.split('\n') if not l.startswith(('> 📷', '> ✏️', '*Jestli chcete'))]
    t = '\n'.join(radky)
    t = t.split('\n', 1)[1].strip()                                         # bez nadpisu (je v hlavičce)
    t = re.sub(r'^\*\d+\.[^*\n]*\d{4}\*\s*$', '', t, count=1, flags=re.M).strip()  # bez řádku s datem

    def fotka(m):
        src = (ZDROJ / m.group(2)).resolve()
        shutil.copy(src, KOREN / 'content' / 'fotky' / src.name)
        return f'![{m.group(1)}]({src.name})'
    t = re.sub(r'!\[([^\]]*)\]\(([^)\s]+)\)', fotka, t)

    def odkaz(m):
        for klic, stranka in ODKAZY.items():
            if klic in m.group(2):
                return f'[{m.group(1)}]({relativne(adresa, stranka)})'
        return m.group(0)
    t = re.sub(r'(?<!!)\[([^\]]+)\]\(([^)]+)\)', odkaz, t)
    t = re.sub(r'\n{3,}', '\n\n', t).strip()

    cesta = KOREN / cil
    hlava = cesta.read_text(encoding='utf-8').split('---', 2)[1]
    if cil.startswith('content/clanky/'):
        # první odstavec je perex
        perex, t = t.split('\n\n', 1)
        hlava = re.sub(r'^perex:.*$', lambda _: 'perex: ' + perex.strip(), hlava, flags=re.M)
    cesta.write_text('---' + hlava + '---\n\n' + t + '\n', encoding='utf-8')
    print('převzato', cil)
