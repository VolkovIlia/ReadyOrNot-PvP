# Development

## How it works

- **HostBrain** (`HostBrain/ue4ss-mods/HostBrain`) — a Lua mod for RE-UE4SS. **Only the host** installs it (listen
  server). All the rules of the mode live here; clients receive the state through the game's own replication and RPCs.
- **RonCompNative.dll** (`HostBrain/native/RonCompNative.cpp`, MSVC) — the native part: crash protection on round reset,
  a filter for suspects' SWAT actions (replacing `UFunction::Func` of server RPCs), friend/foe rules for the hidden
  co-op PvP, disabling score popups. Lua loads it through `package.loadlib` and exchanges data with it through an ini
  file and a log.
- **The pure core** (`HostBrain/src/core`) does not depend on UE: round phases, economy, cvar-style settings for a
  future CS2-style mode ([design.md](design.md)). It is covered by unit tests and is built and tested outside the game.
- **RonCompProbe** (`HostBrain/ue4ss-mods/RonCompProbe`) — a remote console for development ([testing.md](testing.md)).
  Not included in releases.

Reverse-engineering findings: [re-findings.md](re-findings.md). Testing: [testing.md](testing.md).
Checklist for a session with a friend: [pvp-playtest.md](pvp-playtest.md).

## Layout

```
HostBrain/ue4ss-mods/  UE4SS Lua mods: HostBrain (the mod itself) and RonCompProbe (remote console)
HostBrain/native/      RonCompNative.dll
HostBrain/src/core     pure core, HostBrain/tests — unit tests
data/                  competitive.cfg (cvar-style settings), items.csv
docs/                  design, reverse-engineering findings, testing
re/                    reverse-engineering scripts (large dumps and the unpacked game are not committed)
tools/                 build, UE4SS install, deploy, release packaging
assets/                mod images
```

## Building

You need Visual Studio 2022 (MSVC, CMake) and PowerShell.

Build `RonCompNative.dll` and run the core tests:
```bash
powershell -File tools/build_hostbrain.ps1
```

Install UE4SS (the build from `tools/bin/ue4ss/<version>/extracted`; `-Dev` enables the UE4SS console and hot reload):
```bash
powershell -File tools/install_ue4ss.ps1 -Dev
```

Copy the mods into the game (works while the game is running; scripts are picked up after a game restart):
```bash
powershell -File tools/deploy_ue4ss_mods.ps1
```

Release archive in `dist/` (HostBrain with the built DLL, without RonCompProbe):
```bash
powershell -File tools/package_release.ps1
```

The mod version is `Version` in `HostBrain/ue4ss-mods/HostBrain/Scripts/main.lua` plus an entry in
[CHANGELOG.md](../CHANGELOG.md).

## Pak version for the Mods menu (`pakmod/`)

The mod.io version of the mode is built without the UE editor: the logic is written in a subset of Python
(`pakmod/src/pvp.py`), the `pakmod/kc` compiler turns it into Kismet bytecode and writes cooked UE 5.3 assets as
UAssetAPI JSON; UAssetGUI turns them into `.uasset`/`.uexp`, and `repak` packs them into a pak. Details are in
[modio-pak-research.md](modio-pak-research.md).

Requirements:
- a JMAP dump of the game's reflection in `re/dumps/*.jmap` and a `.usmap` (taken with UE4SS, not in git);
- `tools/bin/uassetgui/UAssetGUI.exe` (1.1.0) and `tools/bin/repak/repak.exe` (0.2.3) from their GitHub releases;
- the type mappings: `%LOCALAPPDATA%\UAssetGUI\Mappings\RoN.usmap` (a copy of the `.usmap` from the dump).

Build, install into `Paks/~mods` and create the mod.io archive:
```bash
python pakmod/build.py pvp --deploy --zip
```

Structure:
- `kc/kismet.py` — Kismet expressions and their in-memory sizes (checked against 146 functions of the game's
  Blueprints);
- `kc/uasset.py` — the package: name table, imports, exports;
- `kc/blueprint.py` — class, functions, variables, calls;
- `kc/lang.py` — the language compiler;
- `kc/data.py` — `ModActorSpawnData`;
- `kc/reflect.py`, `kc/types.py` — the game's reflection and property types.

Reference for the game's functions and properties:
`python pakmod/sig.py ReadyOrNotPlayerController:ReadyUp "W_StandardButton_C:*Click*"`.

Bytecode rules that the game has already crashed on:
- a function result is written through `EX_LocalOutVariable(ReturnValue)`, and a call is assigned with
  `EX_Let(temp, call)`. Passing the address of the result as an argument does not work: `ProcessScriptFunction`
  skips the return parameter;
- `EX_Return` without a value: copying the result into the buffer of the calling instruction (64 bytes,
  uninitialized) crashes the game on arrays and strings;
- the engine stores a name like `Ret_1` as `Ret` plus a number, so the base name must be in the name table too.

Debugging: the director writes a log into `Notes` (UE4SS: `FindAllOf("BP_PvPDirector_C")[1].Notes`) and into
`SaveGames\RoNPvPLog.sav`. Blueprint functions can be called from UE4SS directly.

## Experimental: the game's own PvP modes

The game still contains its own PvP modes (Firefight, Defusal and others). `comp_start` moves the lobby to a map in
such a mode. This is groundwork for later stages: the modes are unstable and can end the game for everyone.

```
comp_start campus ff      native Firefight on Watt Community College (tested)
comp_start campus RR_PVP  Defusal with a bomb (tested; CS2 rules are the next stage)
comp_start <map> <mode> force   untested pair: may end the game for everyone
comp_status               mode, score, protections, hit validation
comp_maps / comp_modes    list of maps and modes
```

## Solo match as a suspect against SWAT bots (console)

The old solo mode, from before the team menu. Today the same thing is easier through the PvP menu (join the suspects
and play alone).

```
comp_play_suspect campus [n]  match to n wins (3 by default): you are a suspect, AI suspects are your allies,
                              an AI SWAT squad storms the building
comp_round_time 240 20        assault and preparation time, s (from the next round)
comp_bot_hints 0|1            hint for the squad after 60 s without contact (on by default)
comp_bot_accuracy 3           SWAT bot accuracy: 1 = normal, higher = worse (2 by default)
comp_suspect off              leave the mode
```
