# Changelog

## 0.4.0-alpha — 27.10.2026

- **Scoreboard on Tab** during a PvP round, over the mission journal:
  - the round, the score and the time left;
  - every player's kills, deaths, status and ping, in the game's own scoreboard lines;
  - the AI officers and how many AI suspects are left.

  A client with the pak gets it too, drawn from replicated state.
- **Match stats:**
  - a kill feed in chat, marked the way the game marks its own: "King killed w4me (Superbnova)". It shows kills
    that involve a player or cost SWAT an officer;
  - the players' kills and deaths for the match and the round, written into their PlayerState, so the game's
    scoreboard lines show them;
  - a table (player, kills, deaths) and the best player on the round and match result pages.
- **Bot slots:**
  - the SWAT card has five slots: a click on a bot takes it away, a click on a free slot adds one;
  - with the host on the suspects' side SWAT get five bots. The mod spawns a fifth officer (Gideon) next to the
    mission's four (King, Swan, Prescott, Eli), with the first officer's kit and clothes;
  - the «БОТЫ SWAT» on/off button is gone.
- **English.** The menu, the messages and the scoreboard are in Russian or English:
  - on the first start the mode takes the game's language;
  - «ЯЗЫК / LANGUAGE» in the menu switches it;
  - a client's scoreboard follows the client's own game language.
- **Spawn protection.** A suspect player who takes over an AI suspect cannot be hurt for 3 s.
- **No SWAT helmet cameras for suspects.** The game's team view lists every SWAT officer while its hidden PvP flag
  is off, so a suspect could watch where SWAT were; the mode closes such a view at once (a client needs the pak).
- **No SWAT score or objective popups for suspects** ("Reported suspect", "+10", mission objectives): they are hidden
  as soon as they show; the mode's own popups stay (a client needs the pak).
- **SWAT bots hunt again.** With no SWAT player the squad is led by a bot, and the game's AI then carries out only
  orders of a few metres, so the bots stood at their start. Now, while no suspect player can see the squad and it
  is not fighting, it hops every 12 s to a doorway up to 16 m closer to the last sighting, gunshot or hint (never
  within 9 m of a suspect player or in sight of one), walks the last metres and fights on its own on contact.
  Hints come every 30 s and are closer (±8 m).
- **Suspect players get the AI's real guns.** Only the AI suspects' own guns were matched, so an AI carrying a
  player gun (an MPX, an M4, a DLC gun) gave a pistol only; now a player gun is handed over as it is, and an
  unknown AI gun by its kind. The log names the AI's guns.
- **Locked doors for suspects:** the game still offered a suspect player the multitool on a locked door; a locked
  door now unlocks while a suspect player stands at it and locks again when it is closed and no suspect is near
  (unless SWAT used it last).
- **Guns lying as evidence** (a scoped rifle on a table and the like) can be picked up by a suspect like a dropped
  gun: a sniper rifle becomes the TAC-700, other guns by their kind.
- The legacy UE4SS version (HostBrain) freezes the AI squad when it is installed next to the Mods-menu version: its
  native guards load even when it leaves the mission to the pak. Turn it off or uninstall it.
- **A native look:**
  - round events show for the host as the game's own objective popups at the bottom centre: round start, result,
    side swap, time warnings, takeover, pickup;
  - clients get these events as short chat lines;
  - the long rules text is no longer repeated in chat: it is in the menu;
  - the mode no longer posts toasts;
  - the menu uses the game's font (Barlow, as on the pre-mission screen) and darker, neutral panels.

## 0.3.0-alpha — 27.10.2026

The Mods-menu version (mod.io) is now the mod; the UE4SS installer version stays at 0.2.1 and is not developed further.

- **Rule sets**, a «ПРАВИЛА» (Rules) button in the host's menu, saved with the other settings:
  - **vanilla** (default): the AI keep the armour and guns the mission gives them; a suspect player gets the player
    version of the AI's own guns, a pistol only if the AI had only a pistol;
  - **balanced**: the 0.2.1 rules, rifles firing FMJ for suspect players and Kevlar for the AI SWAT squad.
- **Suspects open any door**, locked ones too, through the game's own `Door.bSuspectAlwaysUnlocks`. A door that was
  locked locks again when a suspect closes it; SWAT still find it locked.
- **Suspects pick up dropped guns:** collecting a dropped gun as evidence gives it to a suspect player instead (a SWAT
  gun as it is, an AI suspect's gun as its player version), in place of the primary or the pistol.
- The round-start message names the rule set and the door and pickup rules.
- The repository's documentation is in English.

## 0.2.1-alpha — 27.10.2026

- **Suspects can wound SWAT again.** The game was not treating their shots as friendly fire; armour and weapons were
  the problem:
  - AI SWAT wear level 6 ceramic or steel, which no round in the game penetrates in the torso, and have 250 HP
    against a player's 160;
  - suspects mostly got MP5s and pistols, and pistol calibres do not penetrate even Kevlar.
- Suspect players get rifles firing FMJ (SLR-47, FAL; SBR and MK18 in place of AI carbines) instead of the MP5, MP9
  and shotguns.
- The AI SWAT squad in PvP wears the default SWAT player armour (Kevlar) instead of ceramic and steel.

## 0.2.0-alpha — 27.10.2026

- **Version for the in-game Mods menu (mod.io): `RoNPvP.pak`.** The same mode without UE4SS: team menu, rounds and
  results, side swap, takeover of AI suspects, suspect loadouts and clothes, SWAT bots and their hunting, 10-player
  lobbies, saved settings. The logic is started by the game's own mod mechanism (`ModActorSpawnData`).
  - Friends need to turn on "Join modded servers" or subscribe to the mod.
  - No filter for suspects' SWAT actions and no hiding of score popups (both need native code).
  - The mode's log: `SaveGames\RoNPvPLog.sav`.
- `pakmod/kc`: a compiler from logic in Python syntax to cooked UE 5.3 Blueprint assets, without the editor.
- The UE4SS version leaves the mission to the pak version if both are installed.

## 0.1.0-alpha — 27.10.2026

First public alpha.

- PvP in any co-op mission: SWAT players against suspect players; only the host installs it.
- «ВЫБЕРИТЕ КОМАНДУ» (Choose a team) menu on the pre-mission screen: team cards, bots, settings, «ГОТОВ» (Ready).
  The other players pick a side in chat (`!swat`, `!suspect`).
- Rounds: a match to N wins, the mod's own round and match result screens, halftime side swap, automatic round start.
- Suspects spawn in place of AI suspects, with their weapons and clothes, without armour or SWAT gear; after a death
  they take over a living AI suspect.
- Optional AI SWAT squad; with no SWAT players it hunts the suspects on its own.
- Suspects cannot arrest, yell "get down" or report to TOC; civilians are neutral; no score popups.
- 10-player lobbies.
- One-click installer (`Install.bat`) with RE-UE4SS.
