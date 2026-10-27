# Publishing

The mod image is `assets/pvp-cover.png` (1920×1080; it works as the mod.io logo and as the first Nexus image).
The archives are built like this:
- pak for mod.io: `python pakmod/build.py pvp --zip` → `dist/RoNPvP-<version>-modio.zip`;
- UE4SS installer: `powershell -File tools/package_release.ps1` → `dist/RoN-PvP-<version>.zip`.

Both archives are attached to the GitHub release (a pre-release while the mod is in alpha).

## mod.io (the in-game Mods menu)

Mod page: https://mod.io/g/readyornot/m/pvp-swat-vs-suspects (created 2026-10-27). New versions are uploaded by the
account owner: mod page → Edit → File manager (zip, version number, changelog, acceptance of the mod.io terms).
The mod.io form fields only update on the change event: when they are filled in by a browser script, the value has to
be passed to the Vue component, otherwise "Create mod" answers "Field is required".

- **Name:** PvP - SWAT vs Suspects (Alpha)
- **Logo:** `assets/pvp-cover.png`
- **Gallery:** `assets/screenshots/*.jpg` in file order (team menu, Tab scoreboard, round end with the kill feed, round
  results, round start)
- **File:** `dist/RoNPvP-<version>-modio.zip`, version `<version>`
- **Tags:** Gameplay, AI
- **Summary:**
  ALPHA. Any co-op mission becomes PvP: SWAT players vs suspect players. Team menu, rounds, side swap, Tab
  scoreboard, kill feed. Dead suspects take over AI suspects. Up to 5 SWAT bots. EN/RU. Friends enable "Join
  modded servers". (mod.io limit: 250 characters)
- **Description:**

```
ALPHA VERSION - expect bugs. Please report them on GitHub: https://github.com/VolkovIlia/ReadyOrNot-PvP/issues
(attach %LOCALAPPDATA%\ReadyOrNot\Saved\SaveGames\RoNPvPLog.sav - the mode's log).

Turns any Ready or Not co-op mission into PvP: SWAT players against suspect players.

- Team menu on the host's pre-mission screen: team cards, bot slots, match settings, Ready.
  Other players pick a side in chat: !swat or !suspect.
- Rounds: a match to N wins (default 3), round and match result screens instead of the SWAT debriefing,
  halftime side swap, the next round starts by itself.
- Scoreboard on Tab in the game's own style: round, score, time left, every player's kills, deaths, status and
  ping, the AI officers and the AI suspects left.
- Match stats: a kill feed in chat, kills and deaths on the result pages, the best player.
- Suspect players spawn in an AI suspect's place with suspect clothes and no SWAT gear, and after a death take
  over another living AI suspect (3 s of spawn protection).
- Two rule sets in the host's menu: vanilla (the AI keep the guns and armour the mission gives them, a suspect
  player gets the AI's own guns, ammo and armour) or balanced (rifles for suspect players, Kevlar for the AI SWAT
  squad).
- No mission score: nobody gets score or objective popups. Helmet cameras and spectating keep to one's own side.
- Suspects open any door, locked ones too; SWAT still find locked doors locked.
- Suspects pick up dropped guns: hold the evidence-collect key on a gun.
- Up to five AI SWAT bots fill the free SWAT slots: they fight for SWAT and hunt suspects on their own when no
  SWAT player is alive. You can play alone against bots on either side.
- English and Russian: the game's language at first, a switch in the menu.
- 10-player lobbies (5v5).

HOW TO PLAY
1. Host: subscribe and restart the game. Friends: subscribe too, or turn on Settings > Game >
   "Join modded servers" once (the game hides modded lobbies otherwise).
2. Host a lobby and start any co-op mission: the team menu opens on the pre-mission screen.
3. In a round hold Tab for the scoreboard.

KNOWN LIMITS
- Suspect players can still yell "get down" and report to TOC: filtering that needs native code, which a
  Mods-menu mod cannot load. A report gives no score.
- A friend gets the Tab scoreboard, and helmet cameras and spectating limited to their own side, only with the mod
  subscribed.
- With no SWAT player the bots close in by unseen hops from doorway to doorway (the game's AI does not take a
  bot-led squad far).
- Uninstall the old UE4SS version of this mod if you have it: it freezes the AI squad.
- Little tested with live opponents yet.

Open source (MIT): https://github.com/VolkovIlia/ReadyOrNot-PvP
Unofficial fan mod, not affiliated with VOID Interactive.
```

## Nexus Mods (UE4SS installer)

File: `dist/RoN-PvP-<version>.zip` (Main file).


**Mod name:** PvP - SWAT vs Suspects (Alpha)

**Version:** 0.2.1-alpha

**Category:** Gameplay (or "Game Modes" if that category exists)

**Summary (up to 350 characters):**
ALPHA. Turns any co-op mission into PvP: SWAT players vs suspect players, team menu, rounds and halftime side swap. Suspects respawn by taking over AI suspects. Optional AI SWAT bots. Host-only: run Install.bat, friends need nothing. Report bugs on GitHub Issues.

**Requirements:** RE-UE4SS (already inside the archive, installed by Install.bat). Link: https://github.com/UE4SS-RE/RE-UE4SS

**Tags:** Gameplay, Multiplayer, PvP, Game Mode (whichever are in the list)

**Permissions:** open source, MIT; link to GitHub.

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
[*][b]Team menu[/b] on the host's pre-mission screen: team cards, bots, match settings, Ready. Other players pick a side in chat: [b]!swat[/b] or [b]!suspect[/b].
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
