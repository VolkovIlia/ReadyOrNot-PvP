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
