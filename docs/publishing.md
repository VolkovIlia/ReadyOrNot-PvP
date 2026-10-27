# Публикация

Картинка мода — `assets/pvp-cover.png` (1920×1080, подходит как логотип mod.io и первая картинка Nexus).
Архивы собираются так:
- pak для mod.io: `python pakmod/build.py pvp --zip` → `dist/RoNPvP-<версия>-modio.zip`;
- установщик UE4SS: `powershell -File tools/package_release.ps1` → `dist/RoN-PvP-<версия>.zip`.

Оба архива прикладываются к релизу на GitHub (пре-релиз, пока альфа).

## mod.io (меню «Моды» в игре)

Публикует владелец аккаунта mod.io: https://mod.io/g/readyornot → Add mod.

- **Name:** PvP - SWAT vs Suspects (Alpha)
- **Logo:** `assets/pvp-cover.png`
- **File:** `dist/RoNPvP-<версия>-modio.zip`, версия `<версия>`
- **Tags:** Gameplay / Game Mode / Multiplayer (что есть в списке)
- **Summary:**
  ALPHA. Turns any co-op mission into PvP: SWAT players vs suspect players, a CS2-style team menu, rounds and a
  halftime side swap. Suspects respawn by taking over AI suspects. Optional AI SWAT bots. Only the host needs it;
  friends turn on "Join modded servers". Bugs: GitHub Issues.
- **Description:**

```
ALPHA VERSION - expect bugs. Please report them on GitHub: https://github.com/VolkovIlia/ReadyOrNot-PvP/issues
(attach %LOCALAPPDATA%\ReadyOrNot\Saved\SaveGames\RoNPvPLog.sav - the mode's log).

Turns any Ready or Not co-op mission into PvP: SWAT players against suspect players.

- CS2-style team menu on the host's pre-mission screen: team cards, bots, match settings, Ready.
  Other players pick a side in chat: !swat or !suspect.
- Rounds: a match to N wins (default 3), round and match result screens instead of the SWAT debriefing,
  halftime side swap, the next round starts by itself.
- Suspect players spawn in an AI suspect's place with suspect guns and clothes, no armour or SWAT gear,
  and after a death take over another living AI suspect.
- Optional AI SWAT squad: fights for SWAT and hunts suspects on its own when no SWAT player is alive.
  You can play alone against bots on either side.
- 10-player lobbies (5v5).

HOW TO PLAY
1. Host: subscribe and restart the game. Friends: subscribe too, or turn on Settings > Game >
   "Join modded servers" once (the game hides modded lobbies otherwise).
2. Host a lobby and start any co-op mission: the team menu opens on the pre-mission screen.

KNOWN LIMITS
- The menu and messages are in Russian for now.
- Suspect players can still use SWAT radio reports and yells, mission score popups still show and dead players
  may spectate anyone: blocking those needs native code (the installer version on GitHub does it).
- Little tested with live opponents yet.

Open source (MIT): https://github.com/VolkovIlia/ReadyOrNot-PvP
Unofficial fan mod, not affiliated with VOID Interactive.
```

## Nexus Mods (установщик UE4SS)

Файл — `dist/RoN-PvP-<версия>.zip` (Main file).


**Mod name:** PvP - SWAT vs Suspects (Alpha)

**Version:** 0.2.0-alpha

**Category:** Gameplay (если есть «Game Modes» — она)

**Summary (до 350 символов):**
ALPHA. Turns any co-op mission into PvP: SWAT players vs suspect players, CS2-style team menu, rounds and halftime side swap. Suspects respawn by taking over AI suspects. Optional AI SWAT bots. Host-only: run Install.bat, friends need nothing. Report bugs on GitHub Issues.

**Requirements:** RE-UE4SS (уже внутри архива, ставится Install.bat). Ссылка: https://github.com/UE4SS-RE/RE-UE4SS

**Tags:** Gameplay, Multiplayer, PvP, Game Mode (что есть в списке)

**Permissions:** открытый исходный код, MIT — ссылка на GitHub.

## Description (BBCode)

```
[center][size=6][b]PvP - SWAT vs Suspects[/b][/size]
[size=4][color=#ffb000][b]ALPHA VERSION[/b][/color][/size][/center]

[color=#ffb000][b]This is an alpha.[/b][/color] The mode is playable, but expect bugs - it has seen little play against live opponents.
[b]Please report bugs on GitHub:[/b] [url=https://github.com/VolkovIlia/ReadyOrNot-PvP/issues]github.com/VolkovIlia/ReadyOrNot-PvP/issues[/url]
Attach the host's logs: [i]ReadyOrNot\Binaries\Win64\ue4ss\UE4SS.log[/i] and [i]ue4ss\Mods\HostBrain\native\RonCompNative.log[/i].

[size=5][b]What it does[/b][/size]
Turns any Ready or Not co-op mission into PvP: SWAT players against suspect players.
[list]
[*][b]CS2-style team menu[/b] on the host's pre-mission screen: team cards, bots, match settings, Ready. Other players pick a side in chat: [b]!swat[/b] or [b]!suspect[/b].
[*][b]Rounds[/b]: a match to N wins (default 3), round and match result screens instead of the SWAT debriefing, halftime side swap, the next round starts by itself.
[*][b]Suspect players[/b] spawn in an AI suspect's place with suspect guns and clothes, no armour or SWAT gear. After a death they take over another living AI suspect that no SWAT can see.
[*][b]Optional AI SWAT squad[/b]: it fights for SWAT and hunts suspects on its own when no SWAT player is alive. You can play alone against bots on either side.
[*][b]Fair rules[/b]: suspects cannot arrest, yell or report to TOC and get no SWAT score; civilians stay neutral; dead players spectate only their own team.
[*][b]10-player lobbies[/b] (5v5) instead of 5.
[/list]

[size=5][b]Install (host only)[/b][/size]
[list=1]
[*]Close the game, download the archive and unzip it anywhere.
[*]Run [b]Install.bat[/b]. It finds the game through Steam and installs the mod together with RE-UE4SS (an existing UE4SS is kept).
[*]Host a lobby and start any co-op mission - the team menu opens on the pre-mission screen.
[/list]
Friends need nothing installed. Uninstall: [b]Uninstall.bat[/b]. Update: run Install.bat of the new version (settings are kept).
There is also a version for the in-game Mods menu (mod.io, no UE4SS, slightly fewer rules): see GitHub.

[size=5][b]Known limitations[/b][/size]
[list]
[*]The in-game menu and messages are in Russian for now.
[*]Client suspects still see the SWAT squad panel (a vanilla client cannot hide it).
[*]A suspect's own radio-report animation still plays; the server ignores the report.
[*]Game updates may break the mod: it relies on the game's internals.
[*]Antivirus tools may flag dwmapi.dll - that is the RE-UE4SS loader.
[/list]

[size=5][b]Source and credits[/b][/size]
Open source (MIT): [url=https://github.com/VolkovIlia/ReadyOrNot-PvP]github.com/VolkovIlia/ReadyOrNot-PvP[/url]
Bundled: [url=https://github.com/UE4SS-RE/RE-UE4SS]RE-UE4SS[/url] v3.0.1-1183 (MIT).
Unofficial fan mod, not affiliated with VOID Interactive.
```
