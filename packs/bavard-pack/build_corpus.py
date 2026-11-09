#!/usr/bin/env python3
"""Builds the Molière corpus of the Bavard pack (tools/*.txt) from Project
Gutenberg's French "Molière - Œuvres complètes" (Philarète Chasles's
edition, tomes 1 to 4): public domain, free for any use.

    python3 build_corpus.py              # downloads the four tomes, the twelve plays
    python3 build_corpus.py --all        # every play in the four tomes (22)
    python3 build_corpus.py --list       # what it finds, nothing written
    python3 build_corpus.py --from DIR   # tomes already downloaded (pg40086.txt, ...)

Runs on the laptop, not the node (this file isn't uploaded). The tomes
are kept in gutenberg/ next to this file, so a second run doesn't
download them again. Writes, in tools/ next to it:

    plays.txt          one line per play: slug<TAB>title<TAB>lines
    <slug>.txt         the play, one record per line:
                         T<TAB>title
                         S<TAB>act, scene     (e.g. "I, 1")
                         L<TAB>SPEAKER<TAB>text
    SOURCES.txt        where the text comes from

and bavard/scene.py, the first scene of Le Misanthrope built in.

A réplique longer than CHUNK characters is cut into several L records of
the same speaker (at verse breaks first), so every one fits in a chat
line. Stage directions, footnotes and the editor's notices are left out.
Verse lines are joined with " / ".
Then: python3 ../../provisioner.py --hash-pack .
"""

import re
import sys
import unicodedata
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHUNK = 320

# Molière - Œuvres complètes (Philarète Chasles), Project Gutenberg.
TOMES = {
    1: 40086,    # Médecin volant ... Précieuses ridicules, Sganarelle, Don Garcie
    2: 43535,    # École des maris ... École des femmes ... Princesse d'Élide
    3: 50173,    # Tartuffe, Don Juan, Amour médecin, Misanthrope ...
    4: 57270,    # Amphitryon, George Dandin, Avare, Pourceaugnac
}
URL = "https://www.gutenberg.org/cache/epub/%d/pg%d.txt"

# The default selection, in the order they're played: ~1 MB in all, so a
# USB upload (about 1 KB/s) stays around a quarter of an hour. A slug is
# found by its title (the leading article left out). --all gives every
# play in the tomes.
DEFAULT = [
    "misanthrope", "tartuffe", "avare", "ecole-des-femmes", "precieuses-ridicules",
    "dom-juan", "george-dandin", "ecole-des-maris", "amphitryon",
    "monsieur-de-pourceaugnac", "amour-medecin", "sganarelle",
]
ALIASES = {                     # other spellings of a title -> the slug
    "don-juan": "dom-juan", "georges-dandin": "george-dandin",
    "m-de-pourceaugnac": "monsieur-de-pourceaugnac",
}
NICE = {                        # titles as they're shown in the chat
    "misanthrope": "Le Misanthrope", "tartuffe": "Le Tartuffe", "avare": "L'Avare",
    "ecole-des-femmes": "L'École des femmes", "precieuses-ridicules": "Les Précieuses ridicules",
    "dom-juan": "Dom Juan ou le Festin de pierre", "george-dandin": "George Dandin",
    "ecole-des-maris": "L'École des maris", "amphitryon": "Amphitryon",
    "monsieur-de-pourceaugnac": "Monsieur de Pourceaugnac", "amour-medecin": "L'Amour médecin",
    "sganarelle": "Sganarelle ou le Cocu imaginaire",
}

ROMAN = ["", "I", "II", "III", "IV", "V", "VI", "VII"]
ACTS = {"PREMIER": 1, "DEUXIÈME": 2, "SECOND": 2, "TROISIÈME": 3, "QUATRIÈME": 4,
        "CINQUIÈME": 5, "UNIQUE": 1}
UP = "A-ZÀÂÄÇÉÈÊËÎÏÔÖÙÛÜŸŒÆ"
GENRE = re.compile(r"^(COMÉDIE|TRAGI|PASTORALE|FARCE|BALLET|DIVERTISSEMENT|REPRÉSENTÉE|OU\b)")
ACT_RE = re.compile(r"^ACTE\s+([%s]+)\b" % UP)
SCENE_RE = re.compile(r"^SC[ÈE]NE\s+([IVXL]+|PREMI[ÈE]RE|UNIQUE|DERNI[ÈE]RE)\b")
SPEAKER_RE = re.compile(r"^([%s][%s'’ .\-]*[%s])\.?(,[^.]*)?\.$" % (UP, UP, UP))
NOTE_RE = re.compile(r"^\[\d+\]")
MARK_RE = re.compile(r"\[\d+\]")
END_RE = re.compile(r"^FIN(\.|\s+D(?!.*\bACTE\b))")


def norm(s):
    return re.sub(r"\s+", " ", s or "").strip()


def slugify(title):
    t = unicodedata.normalize("NFD", title.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = re.sub(r"^(l'|le |la |les )", "", t.replace("’", "'"))
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return ALIASES.get(t, t)


def indent(line):
    return len(line) - len(line.lstrip(" "))


def body_of(text):
    """The book without Project Gutenberg's header and licence."""
    a = re.search(r"^\*\*\* ?START OF.*$", text, re.M)
    b = re.search(r"^\*\*\* ?END OF.*$", text, re.M)
    return text[a.end() if a else 0:b.start() if b else len(text)]


def find_plays(lines):
    """[(title, first, last)] for each play in a tome: its title block (a
    title line flush left, then "OU ..." or "COMÉDIE ..."), its list of
    characters, then from the first act or scene to "FIN DE ..."."""
    out, i, n = [], 0, len(lines)
    while i < n:
        t = lines[i].rstrip()
        if (t and indent(t) == 0 and not re.search("[a-zà-ÿœ]", t) and len(t) < 60
                and not GENRE.match(t) and not ACT_RE.match(t) and not SCENE_RE.match(t)
                and (i == 0 or not lines[i - 1].strip())):
            ahead = [x.strip() for x in lines[i + 1:i + 9] if x.strip()]
            if ahead and GENRE.match(ahead[0]):
                p = next((k for k in range(i, min(n, i + 4000)) if lines[k].strip().startswith("PERSONNAGES")), None)
                if p is not None:
                    s = next((k for k in range(p, n) if ACT_RE.match(lines[k].strip())
                              or SCENE_RE.match(lines[k].strip())), None)
                    if s is not None:
                        e = next((k for k in range(s, n) if END_RE.match(lines[k].strip())), n)
                        out.append((t.strip(" ."), s, e))
                        i = e + 1
                        continue
        i += 1
    return out


def paragraphs(lines):
    cur = []
    for l in lines:
        if l.strip():
            cur.append(l.rstrip())
        elif cur:
            yield cur
            cur = []
    if cur:
        yield cur


def clean(s):
    s = MARK_RE.sub("", s)
    s = re.sub(r"\([^)]*\)", "", s)               # (A Isidore.) and the like
    s = s.replace("_", "")
    return norm(s)


def speech(par):
    """A paragraph of what someone says: verse (lines indented two
    spaces, or a half-line far to the right) joined with " / "."""
    verse = all(indent(l) == 2 or indent(l) >= 16 for l in par)
    parts = [clean(l) for l in par]
    parts = [p for p in parts if p]
    return (" / " if verse else " ").join(parts), verse


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


def build(lines, title):
    """The play's records and its number of L records."""
    recs, act, scene, who, said, n = ["T\t" + title], 0, 0, None, [], [0]

    def flush():
        if who and said:
            text = said[0][0]
            for k in range(1, len(said)):
                text += (" / " if said[k - 1][1] and said[k][1] else " ") + said[k][0]
            text = norm(text).strip(" /")
            for part in chunks(text):
                recs.append("L\t%s\t%s" % (who, part.replace("\t", " ")))
                n[0] += 1
        said[:] = []

    for par in paragraphs(lines):
        first = par[0].strip()
        if NOTE_RE.match(first) or re.match(r"^FIN\b", first):   # a footnote, "FIN DU PREMIER ACTE"
            continue
        m = ACT_RE.match(first)
        if m and first.upper() == first:
            flush()
            who = None
            act = ACTS.get(m.group(1), act + 1)
            scene = 0
            continue
        if SCENE_RE.match(first):
            flush()
            who = None
            scene += 1
            a = ROMAN[act] if 0 < act < len(ROMAN) else (str(act) if act else "")
            recs.append("S\t" + (a + ", " if a else "") + str(scene))
            continue
        m = SPEAKER_RE.match(first)
        if m and len(m.group(1)) >= 2 and not re.search(r"\b(ACTE|SC[ÈE]NE|FIN)\b", m.group(1)):
            flush()
            who = re.sub(r"\s+", " ", m.group(1)).strip(" .")[:24]
            par = par[1:]
            if not par:
                continue
        if who is None:                                # a place, a direction
            continue
        if all(4 <= indent(l) < 16 for l in par):      # a stage direction
            continue
        text, verse = speech(par)
        if text:
            said.append((text, verse))
    flush()
    return recs, n[0]


def tome(path):
    lines = body_of(path.read_text(encoding="utf-8", errors="replace")).splitlines()
    for title, s, e in find_plays(lines):
        yield title, lines[s:e]


def fetch(folder):
    folder.mkdir(exist_ok=True)
    for t, num in TOMES.items():
        f = folder / ("pg%d.txt" % num)
        if f.is_file() and f.stat().st_size > 100000:
            continue
        print("downloading tome %d (Project Gutenberg #%d)..." % (t, num))
        req = urllib.request.Request(URL % (num, num), headers={"User-Agent": "bavard-build-corpus"})
        with urllib.request.urlopen(req, timeout=120) as r:
            f.write_bytes(r.read())


def main():
    args = sys.argv[1:]
    if "-h" in args or "--help" in args:
        sys.exit(__doc__)
    src = Path(args[args.index("--from") + 1]) if "--from" in args else HERE / "gutenberg"
    if "--from" not in args:
        fetch(src)
    found = {}
    for t, num in sorted(TOMES.items()):
        f = src / ("pg%d.txt" % num)
        if not f.is_file():
            sys.exit("missing %s (Project Gutenberg #%d)" % (f, num))
        for title, lines in tome(f):
            slug = slugify(title)
            recs, n = build(lines, NICE.get(slug, title.title()))
            speakers = len({r.split("\t")[1] for r in recs if r.startswith("L\t")})
            scenes = sum(1 for r in recs if r.startswith("S\t"))
            found.setdefault(slug, (recs, n))
            print("tome %d  %-26s %5d lines %3d scenes %3d speakers  %s" % (t, slug, n, scenes, speakers, title))
    if "--list" in args:
        return
    slugs = sorted(found) if "--all" in args else DEFAULT
    missing = [s for s in slugs if s not in found]
    if missing:
        print("not found in the tomes:", ", ".join(missing))
    out = HERE / "tools"
    out.mkdir(exist_ok=True)
    for old in out.glob("*.txt"):
        old.unlink()
    index, total = [], 0
    for slug in slugs:
        if slug not in found:
            continue
        recs, n = found[slug]
        if n < 20:
            print("skipped (too short, the text wasn't read right?):", slug)
            continue
        (out / (slug + ".txt")).write_text("\n".join(recs) + "\n", encoding="utf-8")
        index.append("%s\t%s\t%d" % (slug, recs[0][2:], n))
        total += (out / (slug + ".txt")).stat().st_size
    (out / "plays.txt").write_text("\n".join(index) + "\n", encoding="utf-8")
    (out / "SOURCES.txt").write_text(SOURCES, encoding="utf-8")
    if "misanthrope" in found:
        write_scene(HERE / "bavard" / "scene.py", found["misanthrope"][0])
    print("%d plays, %d bytes in %s" % (len(index), total, out))


def write_scene(path, recs):
    """bavard/scene.py: the first scene of Le Misanthrope, built in, so two
    bots can still play something on Stumps without the corpus."""
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
            "# Project Gutenberg's Œuvres complètes (public domain): see tools/SOURCES.txt.",
            "TITLE = %r" % recs[0][2:], "SCENE = \"I, 1\"", "LINES = ("]
    body += ["    (%r, %r)," % l for l in lines]
    body.append(")")
    path.write_text("\n".join(body) + "\n", encoding="utf-8")


SOURCES = """Molière (1622-1673). The plays are in the public domain, and so is
this text: free to use, share and change, for any purpose.

Made by build_corpus.py from Project Gutenberg's French edition,
"Molière - Œuvres complètes", tomes 1 to 4, edited by Philarète Chasles
(1798-1873):
  https://www.gutenberg.org/ebooks/40086
  https://www.gutenberg.org/ebooks/43535
  https://www.gutenberg.org/ebooks/50173
  https://www.gutenberg.org/ebooks/57270
with thanks to Project Gutenberg and its volunteers. The text is reduced
for chat (stage directions, notes and the editor's notices removed, long
speeches cut), and Project Gutenberg's licence and name aren't carried:
only the public-domain text.
"""

if __name__ == "__main__":
    main()
