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
