# NomadNet pack

Makes the Stump a **Nomad Network node**. People on
[NomadNet](https://github.com/markqvist/NomadNet) or MeshChat find it
among the nodes they hear (it announces itself under the Stump's name)
and browse it, over the Stump's Wi-Fi or over LoRa:

- **Home**: the Stump's name, its greeting, links, and its LXMF address.
- **Rooms**: each open room and who's there; a room's last 15 lines,
  and a field to say something in it.
- **Billboard**: the latest notices, and a form to post one.
- **Files**: the shared files' names and sizes. Downloading stays on the
  Stump's Wi-Fi (the Files page): too heavy for the radio.

**NomadNet's own chat, in the Stump's rooms.** The pack also makes the
Stump an RRC hub (the chat protocol NomadNet's *Channels* speaks): in
NomadNet, Channels → New hub, the hub address (on the Stump's home
page, card *NomadNet*), or the *Chat in NomadNet* link next to each
room on its pages. The hub's rooms are the Stump's rooms: what people
say on the web, in FireFly or over LXMF shows in NomadNet, and the
other way round. `/list` and `/who` work; private messages to a
NomadNet user arrive as notices, and `/msg <name> <text>` sends one.
MeshChatX and Eridanus speak RRC too and should work the same
(untested).

**And the other way: NomadNet from the Stump.**

- **Browse NomadNet nodes**: the card *NomadNet: browse* lists the
  nodes the Stump hears; open one and its pages show as web pages on
  any phone on the Stump, with their links and forms.
- **Join other communities' hubs**: in `/admin` → *NomadNet hubs
  joined*, add a hub's address (or its `rrc://` link) and its rooms to
  join. Each becomes a room here (`#lobby-aleph`), both ways: their
  people show as `zoe@aleph`, yours there as `rod@<your Stump>`.
- **People heard**: the people the Stump hears from NomadNet, Sideband
  and other LXMF apps, listed with how to write to them.

On a computer Stump, NomadNet on the same Wi-Fi finds the Stump with no
setup (the firmware's local discovery, 1.0.0-beta.55); on a CAM, over
LoRa, or with a UDP interface pointed at it (`CHAIN.md`).

Writing (in a room, on the billboard) takes an identity the app proves
to the node (NomadNet: the page menu, *Identify*). It goes through the
same checks as a message from an LXMF app: the Stump's access mode, the
flood guards, the other plugins. Restricted rooms aren't shown; a
Stump in *mandatory* mode shows its rooms only to an identified visitor.
Pages are in the Stump's default language.

Install it like the other packs (`PACKS.md`); switch it off or on in
`/admin` → **Plugins**, no restart. It needs firmware 1.0.0-beta.53 or
later (plugin API 2).

| Setting (`config.py`) | Default | |
|---|---|---|
| `NOMADNET_ANNOUNCE_MIN` | 30 | Minutes between announces (5 or more) |
| `NOMADNET_HUB` | True | Be an RRC hub too |
