# RoN Competitive design

## Principle
One shared pak for everyone + the rules "brain" on the host only.

| Where | What | How it is installed |
|---|---|---|
| All players | Shared pak: Blueprint actors with replicated state, widgets, `DT_CompItems` | mod.io / `~mods` |
| Host only | RE-UE4SS + HostBrain (C++): rules, economy, hooks, lobby limit of 10 | GitHub / Nexus |
| Optional, client | Add-on for a detailed net graph | GitHub / Nexus |

Clients do not need UE4SS. The pak is the same for everyone, so the Server-Side Checksum passes.

## Order of work (user's decision, 26.10.2026)
1. **Native PvP without the bomb — the way the developers designed it.** The game's built-in modes through aliases:
   `ff` (Firefight — elimination rounds of SWAT against suspects) and `tdm`. HostBrain only starts them, guards against
   known crashes and turns on server-side hit validation.
2. **Bomb** — Defusal (`RR_PVP`) with CS2 rules from the core (`HostBrain/src/core`).
3. **Hostage extraction.**

## How HostBrain works now (v0)
A full C++ UE4SS mod needs the private `UEPseudo` submodule (a GitHub account linked to Epic), and
`UE4SS.dll` does not export the Lua C API. So v0 has two parts:
- **The Lua mod `HostBrain`** (`HostBrain/ue4ss-mods/HostBrain`) — everything that can be done through reflection:
  the console commands `comp_start <map> [mode]`, `comp_status`, `comp_maps`, `comp_modes`, `comp_hitvalidation`;
  turning on `UHitRegistrationSettings.bEnableValidation` in the CDO on the host.
- **`RonCompNative.dll`** (`HostBrain/native`, C++/MSVC, no third-party libraries) — native protections. Lua loads it
  through `package.loadlib`; the entry function does not touch the Lua state, reads its input from
  `RonCompNative.ini` and writes the result to `RonCompNative.log`. The first protection is a detour of the native
  `Multicast_StopSequence` stub that drops a call with `nullptr` before `ProcessEvent` (the RPC is not sent to
  clients). The DLL finds the stub by a byte pattern and the FName index that Lua passes in.
- The rules core (`HostBrain/src/core`) is built by the same CMake and waits for stage 2. It can be connected to the
  game once there is access to `UEPseudo` (the full UE4SS C++ API), or through our own Lua binding inside
  `RonCompNative`.

Build: `powershell -File tools/build_hostbrain.ps1`, deploy: `powershell -File tools/deploy_ue4ss_mods.ps1`.

## Layers
- **L0 — tools (not shipped):** REA (static exe analysis, Frida, version diffs), SDK dump (Dumper-7 + UE4SS),
  a UE 5.3 stub project, Blueprint automation, pak build.
- **L1 — shared pak** `/Game/Mods/RoNComp/`:
  `BP_CompGameMode`, `BP_CompState`, `BP_CompPlayerProxy`, `BP_BombSite`, `BP_Bomb`, `BP_BuyZone`, `DT_CompItems`,
  widgets.
- **L2 — HostBrain:**
  - `src/core` — the pure core: `Settings` (cvar), `Items` (catalogue), `Match` (phases, score, economy, statistics);
  - `src/adapters` — UE4SS hooks, lookup by name through reflection, startup check.

## Sides and factions
The core knows only sides: `Attackers` (like T in CS: they plant the bomb) and `Defenders` (like CT: they defend and
defuse). Which faction plays which side is set by `mp_attackers_faction`. By default the suspects (MLO) attack and
SWAT defends, as in CS.

> Open design question: in RoN's alpha "Defusal" mode it was the other way round — the bomb is already planted, the
> suspects guard it, SWAT storms in and defuses it. This variant can be added as a second rule set
> (`mp_objective defuse_only`).

Team 0 starts as the attackers. Sides swap after round 12 and at every overtime half.

## Match rules (defaults; everything is configurable in `data/competitive.cfg`)

**Phases:** Warmup → FreezeTime → Live → (BombPlanted) → RoundEnd → [Halftime] → … → MatchEnd

| Parameter | Value |
|---|---|
| Rounds in regulation | 24, 13 to win |
| Warmup | 60 s, unlimited money, instant respawn |
| Freeze time | 15 s |
| Round time | 1:55 |
| Bomb timer | 40 s |
| Buy time | freeze time + 20 s, only in the buy zone |
| Pause between rounds | 7 s |
| Halftime break at the side swap | 15 s |
| Overtime | at 12:12, 6 rounds each (MR3), starting money of $12,500 in each half |

**End of a round:**
- before the bomb is planted: all attackers dead → the defence wins; all defenders dead → the attack wins;
  time runs out → the defence wins;
- after the plant: the round goes on until the explosion (the attack wins) or the defuse (the defence wins).
  Eliminating a team does not end the round.

**Economy:**
- start $800, maximum $16,000;
- win: $3,250 (elimination or time), $3,500 (explosion or defuse);
- loss: a ladder of $1,400 → $1,900 → $2,400 → $2,900 → $3,400. The loss counter is 1 at the start of each half,
  so the loser of the pistol round gets $1,900. A win lowers the counter by 1;
- attackers who are alive when time runs out get no loss bonus;
- bomb planted but round lost: +$800 to each attacker;
- planting the bomb: +$300, defusing it: +$300;
- the kill reward depends on the weapon class (`items.csv`); killing a teammate: −$300;
- at the side swap and at every overtime half, money resets to the starting amount.

**Statistics:** K/D/A, damage, ADR, headshots, MVP. An assist is more than 40 damage to the victim when the player
is not the killer.
MVP: on an explosion, the player who planted the bomb; on a defuse, the defuser; otherwise the player of the winning
team with the most kills (ties broken by damage).

## Event flow
The adapters pass game events to the core: `OnDamage`, `OnKill`, `OnBombPlanted`, `OnBombDefused`, `TryBuy`,
player connect and leave.
The core answers with events for the adapters: `PhaseChanged`, `RoundStarted` (respawn, inventory reset), `RoundEnded`,
`MoneyChanged`, `GiveBomb`, `ItemPurchased`, `SidesSwapped`, `MatchEnded`.
The adapters carry out these events in the game and write them into the replicated `BP_CompState`.
