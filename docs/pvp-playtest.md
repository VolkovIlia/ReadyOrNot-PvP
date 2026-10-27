# PvP test with a friend

Goal: check what the host cannot see when playing alone:
- what a client without mods sees and can do;
- how spectating, chat and team cameras work;
- how takeover and the suspect restrictions work against a live opponent.

After the game, send these files from the host's machine:
- `<game>/ReadyOrNot/Binaries/Win64/ue4ss/UE4SS.log`;
- `<game>/ReadyOrNot/Binaries/Win64/ue4ss/Mods/HostBrain/native/RonCompNative.log`;
- screenshots, if something looked wrong.

## Setup
- Host: UE4SS and the mods are installed (`tools/install_ue4ss.ps1`, `tools/deploy_ue4ss_mods.ps1`). The friend has
  the vanilla game.
- The host starts the game and, before creating a lobby, runs `comp_status` in the console: it shows the line
  `lobby cap: 10`.
- The host creates a lobby in Multiplayer, the friend joins.
  - If the friend can see the number of slots in the lobby list or on the lobby screen, write it down (expected: 10).
- For parts 1–2 the host turns the bots off: `comp_pvp_bots off` (the setting is saved; turn it back on in part 3).
- For parts 1–3 the match is a single round: `comp_pvp_rounds 1`; rounds are tested in part 4.
- The host picks a mission on the campus. On the pre-mission screen HostBrain turns on side selection by itself: the
  host sees the «ПОМЕНЯТЬ КОМАНДЫ» (Swap teams) button and the «PvP · вы за SWAT» (PvP · you are SWAT) line at the
  top, and both players see the mode rules and the team lists in chat.

## Part 1: friend as suspect, host as SWAT
1. The friend types `!suspect` in chat.
   - Both see in chat: «<имя> → …» (<name> → …) and the team list line. If the friend does not see HostBrain's chat
     messages, note it.
2. Both press «Готов» (Ready).
   - In chat: the mode rules and «Раунд 1 · SWAT 0 : 0 Подозреваемые» (Round 1 · SWAT 0 : 0 Suspects).
   - The friend spawns not at the van but inside the building, in place of an AI suspect.
3. The friend's appearance and gear as the host sees them:
   - suspect clothes: shirt and trousers, bare hands (if a SWAT uniform is visible, note it);
   - no armour or helmet;
   - a weapon from the suspect set.

   In first person the friend sees bare hands, without SWAT gloves.
4. The friend checks on their side:
   - no armour or NVGs, no grenades, zip ties, tablet or mirror;
   - there is ammo;
   - no SWAT squad panel and no list of squad members.
5. The friend walks up to a civilian and tries to:
   - yell "get down";
   - restrain the civilian;
   - order the civilian to move to the exit;
   - report the civilian and a killed AI suspect to TOC.

   Expected: nothing happens (the report animation and voice may play for the friend, but TOC does not answer). The
   host's `RonCompNative.log` has lines `blocked Server_… from a suspect`.
   The friend opens doors normally.
6. The host kills the friend.
   - The friend sees the death screen and a countdown to the takeover (the standard timer or the chat message
     «Вселение … через 10 с» (Takeover … in 10 s)).
   - In spectator mode the friend sees only suspects (AI or themself), not the host and not the SWAT cameras.
   - After 10 s the friend appears in place of another AI suspect, far from the host.
7. Team chat (`Y`/team channel): the host does not see the friend's messages, and vice versa.
8. The host kills all AI suspects and the friend.
   - In chat: «Раунд 1: победа SWAT…» (Round 1: SWAT win…) and «Матч окончен…» (Match over…); there is no standard
     debriefing screen, and the mission reloads after 6 s. The host sees the «МАТЧ ОКОНЧЕН» (Match over) page, the
     friend sees the normal pre-mission screen.

## Part 2: host as suspect, friend as SWAT
1. The host presses «НОВЫЙ МАТЧ» (New match), sets «РАУНД: 5 МИН» (Round: 5 min) in the settings and joins the
   suspects; the friend types `!swat`.
2. The host spawns in place of an AI suspect. Check items 3–7 of part 1 the other way round: the SWAT friend kills
   the host, the host takes over an AI suspect, and so on.
3. The friend dies → «Раунд 1: победа подозреваемых — все бойцы SWAT нейтрализованы» (Round 1: suspects win — all
   SWAT officers neutralized).
4. Once more, until the timer runs out → «время вышло, подозреваемые продержались» (time is up, the suspects held
   out).

## Part 3: host as SWAT with the AI squad, friend as suspect
1. The host types `comp_pvp_bots on` and keeps the SWAT side on the pre-mission screen; the friend types `!suspect`.
   - In chat at the start: «ИИ-отряд SWAT в игре» (AI SWAT squad in play).
   - The host gets a squad of 4 bots that follow the host. If after 30 s chat says «ИИ-отряд SWAT не появился» (AI
     SWAT squad did not appear), note it.
2. The bots treat the suspect friend as an enemy: they demand surrender and shoot when he is close.
3. The friend kills a bot: the friend gets no score popups and no penalties.
4. The friend kills the host. The bots are still alive, but chat says «Раунд 1: победа подозреваемых — все бойцы SWAT
   нейтрализованы»: bots do not count.

## Part 4: a match of several rounds
1. The host types `comp_pvp_rounds 2 1` (to 2 wins, with a side swap) and presses «НОВЫЙ МАТЧ»; the host plays SWAT,
   the friend types `!suspect`.
2. The round ends (to speed this up, the host types `comp_pvp_endround swat`).
   - Both see the round result in chat and «Половина матча: … меняются сторонами» (Halftime: … swap sides).
   - After 6 s both load into the same mission. The friend has not dropped out of the lobby.
   - The host sees the results page: «ПОБЕДА SWAT» (SWAT WIN), the score, «СМЕНА СТОРОН · теперь вы за
     подозреваемых» (SIDE SWAP · you are now the suspects).
   - The friend sees the normal pre-mission screen; after ~8 s the friend is marked ready without pressing «Готов»,
     and the round starts by itself.
3. In the second round the friend is SWAT at the van, the host is in place of an AI suspect. The SWAT friend wears
   their own clothes, not the suspect's (if the suspect shirt is still there, note it).
4. A round won by the suspects → score 1 : 1, a third round without a side swap. Then the deciding round → the host
   sees the «МАТЧ ОКОНЧЕН» page, and the start waits for «НОВЫЙ МАТЧ».

## More than five players
- The sixth and later players join the lobby without "Server is full!". If someone could not join, note which player
  it was (sixth, seventh and so on).
- At mission start the SWAT players spawn at the van and can move (nobody is stuck inside another player).

## What to write down
- The items where the result did not match the expectation: what exactly was visible, to whom (host or friend),
  approximate time.
- 20–30 minutes of play without crashes. If someone crashed: the time and what was happening.

## Mods-menu version 0.4.0: what needs a friend

The host and the friend both subscribe to the mod (the friend may instead turn on "Join modded servers"; then the
items marked "with the pak" do not apply).

1. **Tab scoreboard on the friend's side** (with the pak): during a round, holding Tab shows the round, the score,
   the time left, both players with kills and deaths, the bots and the AI suspects left. It opens together with the
   mission journal; if the journal hides it or Tab does nothing, note it.
2. **The friend's language** (with the pak): the scoreboard follows the friend's game language; chat lines from the
   mod are in the host's language.
3. **Kill feed:** when the host kills the friend or a bot, both see a line like "w4me killed King (SR-16)" in chat.
4. **Round events for the friend:** round start, result, side swap and "Taking over an AI suspect in 10 s" come to
   the friend as short chat lines; the host sees them as popups at the bottom centre.
5. **Stats:** the result page shows both players' kills and deaths and the best player; the friend's scoreboard
   shows the same numbers.
6. **Spawn protection:** the friend, just after a takeover, cannot be hurt for about 3 s.
7. **Bot slots:** with the host on the suspects' side and the friend on SWAT, the SWAT card shows the friend and four
   bot slots; removing two leaves the friend with two bots in the round.
8. **No score popups for anybody** (without the pak too): reports, arrests and kills give the friend and the host no
   "+N" or objective popup.
9. **Views keep to one's own side** (with the pak): the friend as SWAT cannot open the host's helmet camera while the
   host plays a suspect; killed, the friend's spectator view does not stay on the host.
