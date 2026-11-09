# Security

Project Stump handles security findings in the open. Please report them as a
**public issue** in this repository, or as a pull request with the fix. There is
no private channel, and that's on purpose: the people who run Stumps should be
able to see what was found, what it affects and when it was fixed, all in one
place.

A useful report says:

- what you found, and which release or commit you tested;
- how to reproduce it (a test in `tests/` is best);
- what it lets someone do, and from where: a visitor on the Stump's Wi-Fi,
  someone on the mesh, a plugin, or someone with the board in hand.

What a Stump protects, from whom, and what it doesn't, is in
[docs/THREAT_MODEL.md](docs/THREAT_MODEL.md). Two things to know before you
report:

- **Plugins and packs are trusted code.** They run inside the node with the
  same access as the core. Their limits, such as the posting budget, the
  command flood control and the 100 ms slow-callback log, are there to stop
  mistakes from flooding the chat or the radio. They are not a sandbox against a
  hostile plugin. A way around them is still worth a public issue, since it
  says how far those limits can be relied on, but it isn't a remote attack. Only
  install packs whose code you trust.
- **A Stump's own Wi-Fi is open by design** (a captive portal). What a visitor
  can and can't reach is in the threat model.

If a finding is serious enough that you think it shouldn't be public yet,
open an issue that says only that, without the details, and we'll talk it
through in the open.
