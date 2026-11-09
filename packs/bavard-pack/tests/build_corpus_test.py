#!/usr/bin/env python3
"""build_corpus.py on a tome laid out like Project Gutenberg's Molière
(Chasles): a prose play and a verse play, with notices, footnotes, stage
directions, a verse line split between two speakers. Regular Python.

    python3 tests/build_corpus_test.py
"""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import build_corpus as B

FAIL = []
def check(name, cond, info=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  " + repr(info)[:600]))
    if not cond:
        FAIL.append(name)

TOME = """The Project Gutenberg eBook of Molière - Œuvres complètes, Tome 3
*** START OF THE PROJECT GUTENBERG EBOOK MOLIÈRE ***

  TROISIÈME ÉPOQUE

     XV. 1664. TARTUFFE[1].
    XVI. 1665. DON JUAN, OU LE FESTIN DE PIERRE.

NOTICE

Don Juan fut joué en 1665. Le Misanthrope suivit.


DON JUAN
OU
LE FESTIN DE PIERRE

COMÉDIE

REPRÉSENTÉE POUR LA PREMIÈRE FOIS, A PARIS, SUR LE THÉATRE DU
PALAIS-ROYAL, LE 15 FÉVRIER 1665.

  PERSONNAGES.                                ACTEURS.

  DON JUAN, fils de don Louis.                LA GRANGE.
  SGANARELLE.                                 MOLIÈRE.
  M. DIMANCHE, marchand.                      DU CROISY.

    La scène est en Sicile


ACTE PREMIER

Un palais.


SCÈNE I.--SGANARELLE, GUSMAN.

SGANARELLE, tenant une tabatière.

Quoi que puisse dire Aristote et toute la philosophie, il n'est rien
d'égal au tabac[2]: c'est la passion des honnêtes gens.

Mais c'est assez de cette matière, reprenons un peu notre discours.

  [2] Une note de l'éditeur,
  sur deux lignes.

GUSMAN.

Et la raison encore? (A part.) Dis-moi.

    Il se laisse tomber en tournant.

SCÈNE II.--DON JUAN, SGANARELLE.

DON JUAN.

Quel homme te parlait là?

M. DIMANCHE.

Monsieur, je suis votre serviteur.

FIN DE DON JUAN.



LE MISANTHROPE

COMÉDIE

  PERSONNAGES.

  ALCESTE, amant de Célimène.
  PHILINTE, ami d'Alceste.


ACTE PREMIER


SCÈNE PREMIÈRE.--PHILINTE, ALCESTE.

  PHILINTE.

  Qu'est-ce donc? Qu'avez-vous?

  ALCESTE.

                                    Laissez-moi, je vous prie.

  PHILINTE.

  Mais encor, dites-moi, quelle bizarrerie...

  ALCESTE.

  Laissez-moi là, vous dis-je, et courez vous cacher.

  PHILINTE, à Alceste.

  Mais on entend les gens, au moins, sans se fâcher.

FIN DU PREMIER ACTE.

ACTE DEUXIÈME

SCÈNE I.--ALCESTE, PHILINTE.

  ALCESTE.

  Moi, je veux me fâcher, et ne veux point entendre[3].
  Rayez cela de vos papiers.

  [3] Note.

FIN DU MISANTHROPE.

*** END OF THE PROJECT GUTENBERG EBOOK MOLIÈRE ***
Project Gutenberg licence text...
"""

lines = B.body_of(TOME).splitlines()
plays = B.find_plays(lines)
check("two plays found, by their titles", [p[0] for p in plays] == ["DON JUAN", "LE MISANTHROPE"], plays)
check("slugs", [B.slugify(p[0]) for p in plays] == ["dom-juan", "misanthrope"])
dj = B.build(lines[plays[0][1]:plays[0][2]], "Dom Juan")[0]
check("prose: a speaker's paragraphs joined, notes and markers out",
      "L\tSGANARELLE\tQuoi que puisse dire Aristote et toute la philosophie, il n'est rien d'égal au tabac: "
      "c'est la passion des honnêtes gens. Mais c'est assez de cette matière, reprenons un peu notre discours." in dj, dj)
check("an aside in parentheses and a stage direction left out", "L\tGUSMAN\tEt la raison encore? Dis-moi." in dj, dj)
check("scenes numbered, M. DIMANCHE a speaker", dj[1] == "S\tI, 1" and "S\tI, 2" in dj
      and "L\tM. DIMANCHE\tMonsieur, je suis votre serviteur." in dj, dj)
check("nothing of the notice, the cast or the place", not any("Notice" in r or "Sicile" in r or "palais" in r for r in dj), dj)
mi, n = B.build(lines[plays[1][1]:plays[1][2]], "Le Misanthrope")
check("verse: a half line, speakers indented", mi[1:4] == ["S\tI, 1", "L\tPHILINTE\tQu'est-ce donc? Qu'avez-vous?",
                                                           "L\tALCESTE\tLaissez-moi, je vous prie."], mi)
check("a speaker with a direction", "L\tPHILINTE\tMais on entend les gens, au moins, sans se fâcher." in mi, mi)
check("\"FIN DU PREMIER ACTE\" doesn't end the play; act II", "S\tII, 1" in mi
      and "L\tALCESTE\tMoi, je veux me fâcher, et ne veux point entendre. / Rayez cela de vos papiers." in mi, mi)
check("counted", n == 6, n)
long = B.chunks(" / ".join(["Un vers de douze syllabes pour voir comment on coupe"] * 12))
check("a long réplique cut at verse breaks, each fits", len(long) > 1 and all(len(c) <= B.CHUNK for c in long), long)
print("FAILURES:", FAIL)
sys.exit(1 if FAIL else 0)
