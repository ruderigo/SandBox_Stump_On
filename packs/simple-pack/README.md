# Simple pack

The Stump talks to every LXMF app in compact lines that a Stump app
like FireFly turns into rooms and bubbles:

```
→ #lora-mesh
<rod> anyone near the market?
✓ ~maria
[DM] <maria>: I am, 5 min away
```

In Sideband, Columba or MeshChat that reads like a terminal. With this
pack, a person writes **`simple`** to the Stump and gets sentences from
then on:

```
You're now in #lora-mesh.
rod: anyone near the market?
maria joined.
Private message from maria: I am, 5 min away
```

**`simple off`** goes back. Everyone is told once, at the end of their
first message from the Stump, that they can ask. It's per person,
because over LoRa the Stump can't tell FireFly from Sideband, and
FireFly needs the compact lines. What apps read rather than people
(`AUTH-...`, the profiles other Stumps exchange) is never touched.

Install it like the other packs (`PACKS.md`); switch it off or on in
`/admin` → **Plugins**, no restart. It needs firmware 1.0.0-beta.53 or
later (plugin API 2).
