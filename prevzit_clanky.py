#!/usr/bin/env python3
"""Převezme texty článků z /mnt/project-files/blog/clanky/ do content/clanky/ (hlavičky zůstávají).
Vynechá značky 📷/✏️ a výzvu k odběru (tu má web sám), obrázky převede na figure s popiskem."""
import re
from pathlib import Path

ZDROJ = Path('/mnt/project-files/blog/clanky')
OBRAZKY = {
    'proc-jedu': {'plakat-dobre-mene-dobre.jpg': ('Plakát z kurzu se seznamem dobrých a méně dobrých motivací k dobrovolnictví', 'Jeden z plakátů z prvního víkendu kurzu: dobré a méně dobré důvody, proč jet.')},
    'vikend-1-ostrava': {'michal-s-talirem.jpg': ('Michal s talířem domácího jídla, fotka na seznamovací hru', 'Moje fotka na seznamovací hru.'),
                         'plakat-dobre-mene-dobre.jpg': ('Plakát z kurzu se seznamem dobrých a méně dobrých motivací k dobrovolnictví', 'Plakát, který jsme ve skupinkách sepsali o motivacích.')},
}
SOUBORY = {'proc-jedu': '01-proc-jedu.md', 'vikend-1-ostrava': '02-vikend-1-ostrava.md'}

for slug, jmeno in SOUBORY.items():
    t = (ZDROJ / jmeno).read_text(encoding='utf-8')
    t = '\n'.join(l for l in t.split('\n') if not l.startswith(('> 📷', '> ✏️', '*Jestli chcete')))
    t = t.split('\n', 1)[1].strip()                      # bez nadpisu
    t = re.sub(r'^\*\d+\.[^*]*\*\s*$', '', t, count=1, flags=re.M).strip()  # bez řádku s datem
    perex, telo = t.split('\n\n', 1)
    def obr(m):
        soubor = Path(m.group(1)).name
        alt, pop = OBRAZKY[slug][soubor]
        return f'![{alt}]({soubor} "{pop}")'
    telo = re.sub(r'!\[[^\]]*\]\(([^)\s]+)\)', obr, telo)
    telo = re.sub(r'\((\d\d-)?([a-z0-9-]+)\.md\)', lambda m: f'(../{m.group(2).replace("01-", "")}/)', telo)
    telo = re.sub(r'\n{3,}', '\n\n', telo).strip()
    cil = Path('content/clanky') / f'{slug}.md'
    hlava = cil.read_text(encoding='utf-8').split('---', 2)[1]
    hlava = re.sub(r'^perex:.*$', lambda _: 'perex: ' + perex.strip(), hlava, flags=re.M)
    cil.write_text('---' + hlava + '---\n\n' + telo + '\n', encoding='utf-8')
    print('převzato', slug)
