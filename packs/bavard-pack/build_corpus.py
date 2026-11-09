#!/usr/bin/env python3
"""Builds the Molière corpus of the Bavard pack (tools/*.txt) from the
FreDraCor TEI files (https://github.com/dracor-org/fredracor, tei/).

    git clone --depth 1 https://github.com/dracor-org/fredracor
    python3 build_corpus.py fredracor/tei            # the default selection
    python3 build_corpus.py fredracor/tei --all      # every Molière play

Runs on the laptop, not the node (this file isn't uploaded). Writes, in
tools/ next to it:

    plays.txt          one line per play: slug<TAB>title<TAB>lines
    <slug>.txt         the play, one record per line:
                         T<TAB>title
                         S<TAB>act, scene     (e.g. "I, 1")
                         L<TAB>SPEAKER<TAB>text
    LICENCE-corpus.txt where the text comes from

A réplique longer than CHUNK characters is cut into several L records of
the same speaker (at verse breaks first), so every one fits in a chat
line. Stage directions are left out. Verse lines are joined with " / ".
Then: python3 ../../provisioner.py --hash-pack .
"""

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

TEI = "{http://www.tei-c.org/ns/1.0}"
CHUNK = 320

# The default selection: the great comedies, ~1 MB in all, so a USB
# upload (about 1 KB/s) stays around a quarter of an hour. The bots go
# round it in a loop; --all gives every play.
DEFAULT = [
    "misanthrope", "tartuffe", "avare", "ecole-des-femmes", "femmes-savantes",
    "malade-imaginaire", "bourgeois-gentilhomme", "dom-juan", "fourberies-de-scapin",
    "precieuses-ridicules", "medecin-malgre-lui", "george-dandin",
]

ROMAN = ["", "I", "II", "III", "IV", "V", "VI", "VII"]


def norm(s):
    return re.sub(r"\s+", " ", s or "").strip()


def text_of(el):
    """Text of an element, without its <stage> directions or notes."""
    out = [el.text or ""]
    for c in el:
        if c.tag not in (TEI + "stage", TEI + "note"):
            out.append(text_of(c))
        out.append(c.tail or "")
    return "".join(out)


def replique(sp):
    parts, verse = [], False
    for el in sp.iter():
        if el.tag == TEI + "l":
            parts.append(norm(text_of(el)))
            verse = True
        elif el.tag == TEI + "p":
            parts.append(norm(text_of(el)))
    parts = [p for p in parts if p]
    return (" / " if verse else " ").join(parts)


def chunks(text):
    if len(text) <= CHUNK:
        return [text]
    out, cur = [], ""
    for piece in re.split(r"(?<= / )|(?<=[.!?;:] )", text):
        while len(piece) > CHUNK:                       # one huge sentence
            cut = piece.rfind(" ", 0, CHUNK)
            cut = cut if cut > 0 else CHUNK
            if cur:
                out.append(cur.strip())
                cur = ""
            out.append(piece[:cut].strip())
            piece = piece[cut:]
        if len(cur) + len(piece) > CHUNK and cur:
            out.append(cur.strip())
            cur = ""
        cur += piece
    if cur.strip():
        out.append(cur.strip())
    return [c.rstrip(" /") for c in out if c.strip(" /")]


def speaker(sp):
    s = sp.find(TEI + "speaker")
    name = norm(text_of(s)) if s is not None else (sp.get("who") or "?").lstrip("#").upper()
    name = name.rstrip(" .,")
    return re.sub(r"\s*,.*$", "", name)[:24] or "?"      # "ALCESTE, à part" -> ALCESTE


def build(path):
    root = ET.parse(path).getroot()
    title = norm(text_of(root.find(".//" + TEI + "titleStmt/" + TEI + "title")))
    body = root.find(".//" + TEI + "body")
    recs = ["T\t" + title]
    act = scene = 0
    n = 0

    def walk(el):
        nonlocal act, scene, n
        for c in el:
            if c.tag == TEI + "div":
                kind = (c.get("type") or "").lower()
                if kind in ("acte", "act"):
                    act += 1
                    scene = 0
                elif kind in ("scene", "scène"):
                    scene += 1
                    a = ROMAN[act] if 0 < act < len(ROMAN) else (str(act) if act else "")
                    recs.append("S\t" + (a + ", " if a else "") + str(scene))
                elif kind in ("prologue",):
                    recs.append("S\tPrologue")
                walk(c)
            elif c.tag == TEI + "sp":
                text = replique(c)
                if text:
                    who = speaker(c)
                    for part in chunks(text):
                        recs.append("L\t%s\t%s" % (who, part.replace("\t", " ")))
                        n += 1
            elif c.tag not in (TEI + "head", TEI + "stage", TEI + "castList"):
                walk(c)

    walk(body)
    return title, recs, n


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    src = Path(sys.argv[1])
    out = Path(__file__).resolve().parent / "tools"
    out.mkdir(exist_ok=True)
    slugs = sorted(p.stem[len("moliere-"):] for p in src.glob("moliere-*.xml")) \
        if "--all" in sys.argv else DEFAULT
    index, total = [], 0
    for old in out.glob("*.txt"):
        old.unlink()
    for slug in slugs:
        title, recs, n = build(src / ("moliere-%s.xml" % slug))
        if n < 20:
            print("skipped (too short):", slug)
            continue
        (out / (slug + ".txt")).write_text("\n".join(recs) + "\n", encoding="utf-8")
        index.append("%s\t%s\t%d" % (slug, title, n))
        size = (out / (slug + ".txt")).stat().st_size
        total += size
        print("%-24s %5d lines %7d bytes  %s" % (slug, n, size, title))
    write_scene(Path(__file__).resolve().parent / "bavard" / "scene.py", src)
    (out / "plays.txt").write_text("\n".join(index) + "\n", encoding="utf-8")
    (out / "LICENCE-corpus.txt").write_text(LICENCE, encoding="utf-8")
    print("%d plays, %d bytes" % (len(index), total))


def write_scene(path, src):
    """bavard/scene.py: the first scene of Le Misanthrope, built in, so two
    bots can still play something on Stumps without the corpus."""
    title, recs, _ = build(src / "moliere-misanthrope.xml")
    lines, seen = [], 0
    for r in recs:
        if r.startswith("S\t"):
            seen += 1
            if seen > 1:
                break
        elif r.startswith("L\t"):
            _, who, text = r.split("\t", 2)
            lines.append((who, text))
    body = ["# Built in: the first scene of Le Misanthrope (Molière, 1666), for",
            "# Stumps without the corpus on their card. Made by build_corpus.py from",
            "# FreDraCor / Théâtre Classique (CC BY-NC-SA 4.0): see tools/LICENCE-corpus.txt.",
            "TITLE = %r" % title, "SCENE = \"I, 1\"", "LINES = ("]
    body += ["    (%r, %r)," % l for l in lines]
    body.append(")")
    path.write_text("\n".join(body) + "\n", encoding="utf-8")


LICENCE = """Molière (1622-1673): the plays themselves are in the public domain.

This corpus is made from the digital editions of Théâtre Classique
(theatre-classique.fr, Paul Fièvre) as encoded in TEI by FreDraCor
(the French Drama Corpus, https://github.com/dracor-org/fredracor),
distributed under CC BY-NC-SA 4.0
(https://creativecommons.org/licenses/by-nc-sa/4.0/).

These files are a derived, reduced form of those editions (stage
directions removed, long speeches cut for chat): CC BY-NC-SA 4.0 as
well. Non-commercial use, credit kept, same licence when shared.
"""

if __name__ == "__main__":
    main()
