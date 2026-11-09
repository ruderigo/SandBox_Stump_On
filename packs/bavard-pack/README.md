# Bavard pack

A bot that never stops talking, to test a Stump's guardrails for days.

**Alone**, Bavard posts a line of numbers in `#bavard`, at a pace that
swings from near-instant to a minute and a half of silence:

```
[2026-11-09 05:12:03.417Z] #000123 4821-9055-1770-2246
```

Date and time in UTC, to the millisecond (a `~` in front means the
node's clock hasn't been set by the network yet), the line's number, and
16 digits that are a scramble of that number: never the same twice for
this bot, and no lexicon or table to carry.

**When it finds another Bavard on another Stump**, the two play
Molière in the original French, réplique by réplique:

```
[2026-11-09 05:14:41.032Z] Le Misanthrope I, 1 · PHILINTE — Qu'est-ce donc ? Qu'avez-vous ?
[2026-11-09 05:14:41.288Z] Le Misanthrope I, 1 · ALCESTE — Laissez-moi, je vous prie.
```

Each bot takes half the characters (they alternate in the order they
first speak), posts its own lines on its own Stump and passes the turn
to the other over a Reticulum link. The twelve plays of the collection
come round in a loop, so a duet doesn't run out: a simulated 72 hours at
the default pace played about 21,000 répliques, the collection twice
over, with the bots' memory flat.

## How two Bavards find each other

Every Bavard is a Reticulum destination, `bavard.bot`, and announces
itself every 5 minutes. A Bavard that hears another one calls it if its
own hash is the smaller of the two (the other waits, and calls itself
after 3 minutes if it hasn't been called). The two say hello with where
they are in the plays (the one further along wins), then pass the turn
back and forth with a few bytes each time: the text never crosses, each
reads it from its own card.

Bot lines aren't relayed to the other Stumps of a chain (`rrc.post`
with `bot=True`), so each Stump's `#bavard` shows its own bot's
characters; the full play, both sides, is in the transcripts.

If the partner goes quiet for 5 minutes, the bot goes back to numbers;
when they hear each other again, the play picks up where it stopped.
One partner at a time (`BAVARD_PARTNER` pins one).

## What it measures

Bavard never works around a guardrail: every line goes through the
plugin posting budget (`plugins._post`, 6 room lines a minute). A line
the budget refuses is counted, logged as `DROP`, and in a duet tried
again two seconds later, so no réplique is lost. Then:

- **`/p/bavard/`** (a card on the home page) and **`/p/bavard/stats.json`**:
  lines tried, posted and refused by the budget, the longest silence,
  bots heard, the partner, links made and lost, the link's round trip,
  where the play is, errors.
- **`/sd/plugins/bavard/log-YYYYMMDD.txt`**: every line tried, `OK` or
  `DROP`, with its time, and the link events (`--`). Seven days kept, 16
  MB a day at most.
- **`!bavard`**: the same in one line.
- **`/admin` → Bavard**: pause, leave the duet, start Molière again.

Paces (`BAVARD_PACE`): `variable` (default: 40 % near-instant, 30 %
within 3 s, 20 % within 15 s, 10 % up to 90 s), `quick`, `burst`
(always near-instant: hammers the budget), `polite` (10.5–15 s, under the
budget).

### Seen while writing it

`tests/mp/bavard_duet.py` (run by `tests/run.py`) drives two bots on a
fake clock through the real `plugins.py`. Two things for Team CyberSec:

- **The budget is a fixed window, not a sliding one.** It counts 6 posts
  from a plugin's first post and resets 60 s later, so a plugin can post
  6 at the end of one window and 6 more at the start of the next: the
  test saw **11 lines in one sliding minute**. Over LoRa, that's twice the
  airtime the "6 a minute" suggests, in a burst.
- **The budget is only on `ctx.post()` / `plugins._post()`.** Nothing
  stops a plugin calling `rrc.post()` itself, and the Tavern pack does
  (closing a poll). Bavard doesn't; a malicious pack would. Plugins are
  trusted code (PLUGINS.md), but the budget isn't a guardrail against
  them.

The link between the bots isn't budgeted at all: at the `burst` pace,
two bots across LoRa pass the turn as fast as the budget lets them post,
a packet or two each time. Worth watching on a radio-only pair.

## Settings

All optional, in `config.py` (the wizard asks them under "advanced"):

| | Default | |
|---|---|---|
| `BAVARD_ROOM` | `bavard` | The room it talks in (made if missing). `lora-mesh` puts every line on the radio: careful |
| `BAVARD_PACE` | `variable` | `variable`, `quick`, `burst`, `polite` |
| `BAVARD_ANNOUNCE` | `300` | Seconds between announces |
| `BAVARD_PARTNER` | | Only pair with this Bavard (its `me` in `stats.json`) |
| `BAVARD_LOG` | `on` | `off`: no transcript on the card |
| `BAVARD_NICK` | `Bavard` | The name it posts as |
| `BAVARD_CORPUS` | `/sd/tools/bavard` | Where the plays are |

## The plays

Molière's plays are in the public domain. The text comes from the
Théâtre Classique editions (theatre-classique.fr) as encoded by
[FreDraCor](https://github.com/dracor-org/fredracor), under **CC BY-NC-SA
4.0**: the edition, not Molière, carries that licence, so the corpus in
`tools/` keeps it (credit kept, non-commercial, same licence when
shared). The code is MIT. If Project Stump is ever sold, rebuild the
corpus from a public-domain transcription (Wikisource, Gutenberg) or
check with Théâtre Classique.

`tools/` holds Le Misanthrope, Le Tartuffe, L'Avare, L'École des
femmes, Les Femmes savantes, Le Malade imaginaire, Le Bourgeois
gentilhomme, Dom Juan, Les Fourberies de Scapin, Les Précieuses
ridicules, Le Médecin malgré lui and George Dandin: about 1.1 MB, a
quarter of an hour over USB. Stage directions are left out; a long
speech is cut into several lines of the same character; verse breaks
show as ` / `.

It goes on the SD card, in `tools/bavard/` (so it is also on the Tools
page). Without it, or when the two bots' corpora differ, they play the
first scene of Le Misanthrope, built into the plugin, in a loop.

To rebuild it, or to take every play:

```
git clone --depth 1 https://github.com/dracor-org/fredracor
python3 build_corpus.py fredracor/tei          # the twelve
python3 build_corpus.py fredracor/tei --all    # all 34 (about 2.5 MB: by card reader)
python3 ../../provisioner.py --hash-pack .
```

## Install

Like the other packs (`PACKS.md`):

```
python3 provisioner.py --install-pack PORT packs/bavard-pack
```

then restart the node. It needs firmware 1.0.0-beta.55 or later (plugin
API 3), an SD card for the plays and the transcript, and a second Stump
with Bavard for the duet.
