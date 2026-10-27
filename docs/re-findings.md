# Reverse-engineering findings

Each entry has an **observation** (what is seen directly), a **conclusion** (what follows from it) and **unknown**
(what is still to be checked). If a finding was obtained through REA, its Evidence ID is given next to it.

## Tools
- **REA** (`npx rea-agents@6.8.0`) with the Ghidra provider:
  `GHIDRA_INSTALL_DIR=%USERPROFILE%\Tools\ghidra_12.1.4_PUBLIC`,
  `JAVA_HOME=C:\Program Files\Eclipse Adoptium\jdk-21.0.12.101-hotspot` (set in the Windows user environment
  variables; the MCP server sees them after a client restart). `rea doctor --client claude_code` — Ghidra healthy.
- **Targeted decompilation without full auto-analysis** (a full analysis of the 150 MB exe takes hours):
  `pwsh -File tools/ghidra_decompile.ps1 -Out %USERPROFILE%\Tools\ron_re\out -Depth 1 0x1449a06e0 dis:0x142a52df0:12`.
  The Ghidra project and a copy of the exe live in `%USERPROFILE%\Tools\ron_re` (the Ghidra launcher does not handle
  spaces and parentheses in paths).
- **Where addresses come from:** `.pdata` (function boundaries), the `func` field of a UFunction in JMAP (exec
  wrappers), vtable slots from the `vtable` field of a CDO in JMAP (`_Implementation` functions),
  `re/annotate_strings.py` fills in strings.

## Game installation (25.10.2026)

Observation:
- Path: `C:\Program Files (x86)\Steam\steamapps\common\Ready Or Not`.
- Executable: `ReadyOrNot/Binaries/Win64/ReadyOrNotSteam-Win64-Shipping.exe` (154.5 MB, build of 07.10.2026).
  Version info is empty.
- Next to it is `RedpointEOS/EOSSDK-Win64-Shipping.dll`: sessions go through the Redpoint EOS Online Framework plugin.
- Paks: `pakchunk0..24, 99-Windows.pak` + `.sig`. There are no `.utoc`/`.ucas` files.
- `Manifest_UFSFiles_Win64.txt` — a list of all 467,100 files in the paks. It lets you search for assets without
  unpacking.
- DLC `GameFeatures` plugins: `ReadyOrNot/Plugins/GameFeatures/ReadyOrNotDLC2/...`.

Conclusion:
- The format is classic pak, not IoStore. Building a mod: cook → UnrealPak (`*_P.pak`); retoc is not needed.
- The paks are signed (`.sig`), but pak mods through mod.io and `~mods` work, so apparently the signature is not
  checked for mods.

Unknown:
- The exact engine version (5.3.x): check against exe strings with REA.
- Whether the mod loader requires `.sig` for mod paks.

## PvP remnants in the game (S3, preliminary)

Observation (from the file manifest):
- `Content/Blueprints/Games/` contains GameMode/GameState pairs for PvP modes:
  - `GM_Defusal` / `GS_Defusal`, `GM_TDM` / `GS_TDM` + `HUD_TDM`, `GM_Firefight` / `GS_Firefight`;
  - `GM_VIPEscort` / `GS_VIPEscort` + `HUD_VIPEscort`, `GM_ArrestAndRescue`, `GM_CaptureTheFlag` + `HUD_CaptureTheFlag`;
  - `GM_GunGame`, `GM_KingOfTheHill`, `GM_TugOfWar`, `GM_Incrimination`, `GM_Commander`, `GM_FreeMode`.
- Co-op modes: `GM_COOP` and `COOPModes/GM_COOP_{ActiveShooter,BarricadedSuspects,BombThreat,HostageRescue,Raid}`.
- Mode settings table: `Content/Blueprints/DataTables/GameModeSettingsDataTable`.
- PvP UI:
  - `Blueprints/Gameplay/Defusal/W_DefusalBuyMenu` — **a buy menu for Defusal**;
  - `Widgets/GameModeRound/W_PVP_RoundEnd`, `Widgets/Menus/W_MissionEnd_PVP`;
  - `Widgets/TeamSelection/W_TeamSelection` (+ `W_TeamSelectionPlayerListEntry`);
  - `Widgets/Common/W_Scoreboard*`, `Widgets/HUD/Tablet/W_Scoreboard_V2`.
- PvP data: `ReadyOrNot/Data/DT_ActorsToHandleInPvP`, `Data/Interactions/Multitool_Free_PvP`,
  `Zipcuff_PvP_Arrest{1,2,3}`, `Localization/Game/en/loc_PvP`.
- A playable suspect (MLO):
  - first-person arms `Character/MLO/ron_suspect_fp_player_mlo`, `ron_suspect_fp_player_heavy_v1`;
  - materials `PVP__MI_MLO_ARMOR_BA`, `PVP__MI_MLO_BODY_BA`;
  - faction `Blueprints/AI/FactionManagers/Faction_MLO`.
- Bomb: `Blueprints/Gameplay/COOP/BP_BombActor`, `BP_BombActor_v2`; interactions
  `Data/Interactions/DisarmBomb_DisarmA/B`.
- PvP animations: arrest (`PVP_Arrest_V2`), MVP emotes (`Animations/TP/mvp/...`), `LS_PVP_Afteraction_Win`.

Conclusion:
- The game contains almost the whole skeleton of a CS-like mode: Defusal with a buy menu, team selection, a
  scoreboard, a round end screen, playable suspects. The main path is to revive `GM_Defusal`/`GS_Defusal`
  and build CS2 rules on top of it in HostBrain, rather than write everything from scratch.

Unknown:
- The logic of the native classes (see below): needs an SDK dump and REA.
- Whether `?game=` works in a travel URL.

## Native PvP code in the exe (S3, exe strings)

Method: a scan of ASCII/UTF-16 strings of `ReadyOrNotSteam-Win64-Shipping.exe`
(the script is in the scratchpad, the full output is not committed). These are static strings, not an observation of
execution.

Observation:
- Native classes: `ADefusalGM`, `ADefusalGS`, `AFirefightGM`, `AFirefightGS`, `AVIPEscortGM`, `AVIPEscortGS`,
  `AReadyOrNotGameMode_PVP`, `APVPTriggerBox`, `UMissionEndPvPWidget`, `URoundEndWidget_PVP`.
- Defusal states: `EDefusalMatchSate::{DMS_Warmup, DMS_PreRoundTimer, DMS_Playing, DMS_HalfTime, DMS_MatchFinished}`,
  properties `DefusalMatchState`, `DefusalHudClass`, `IsInDefusalWarmup`, `Defusal_SuspectSpawn`, `bPVPBombOnly`.
- The general PvP state: `EPvPState::{PVPS_Off, PVPS_TeamSelection, PVPS_RoundStarting, PVPS_RoundInProgress,
  PVPS_RoundEnding, PVPS_RoundFinished, PVPS_BetweenRounds, PVPS_End}`.
- PvP events: `EPVPEvent::{PlayerKilled, PlayerArrested, PlayerFreed, KillConfirmed, VIP*, Flag*, Intel*, ...}`.
- **Console variables:**
  - `a.Ron.PVP.Unlock` — "Unlocks PvP mode.";
  - `a.Ron.PVP.Start` — "Starts PvP match if called on the host.";
  - `a.Ron.PVP.MinTeams` — "How many teams are required to enter PvP.";
  - `a.Ron.PVP.SpawnAtTheSameLocation`, `a.Ron.PVP.ForceRespawnAsSpectatorWhenKilled`.
- The secret mode and its menu: `IsSecretPvP`, `IsSecretPvPUnlocked`, `ShowPVPUnlockedVisual`, `IsPvPSupported`,
  `bSupportsPvP`, `bEnableFindSessionPVPButton`, `FindPVPSessionBtn`, `bPVPSession`.
- Weapons per team: `RedPVPUniquePrimaryWeapons`, `BluePVPUniquePrimaryWeapons`;
  appearance: `bOverrideSuspectCustomizationInPvp`.
- RPCs: `Multicast_HandlePvPActors`, `Server_PlayPVPSpeech`, `CoopGS::HandlePvPActors`.

Conclusion:
- The PvP modes were not cut from the code but **hidden behind an unlock flag** ("secret PvP"). The native Defusal
  already handles warmup, the pre-round countdown, rounds, halftime and match end — almost like CS.
- The shortest path to S3: on the host, run `a.Ron.PVP.Unlock 1`, then `a.Ron.PVP.Start`.
  In Shipping the console is usually closed, so HostBrain (UE4SS) has to run the command
  through `UKismetSystemLibrary::ExecuteConsoleCommand` or `IConsoleManager`.

Unknown:
- How functional Defusal is today (the Fire Fight and PvP Revival mods report crashes and breakage).

## In-game run with RE-UE4SS (26.10.2026)

Environment: RE-UE4SS experimental `v3.0.1-1183-gcdbc0b66` (`tools/install_ue4ss.ps1 -Dev`), the probe
`HostBrain/ue4ss-mods/RonCompProbe`.
Raw logs and dumps: `re/dumps/` (not committed).

Observation (UE4SS.log):
- The engine is **5.3.2 Shipping**. UE4SS found GUObjectArray, GMalloc, FName, StaticConstructObject, GNatives,
  ProcessEvent. It did not find `ConsoleManagerSingleton` (two candidates: `7FF67D76A7C0`, `7FF681DA2FD0` with base
  `0x7ff67cc10000`).
- Main menu: `MainMenu_V2`, `BP_MenuGameMode_C`, `ReadyOrNotGameState` (`MatchState=2`, `bPvPMode=false`).
- Console variables are read through `KismetSystemLibrary::GetConsoleVariableIntValue`:
  `a.Ron.PVP.MinTeams=2`, `a.Ron.PVP.ForceRespawnAsSpectatorWhenKilled=1`, `SpawnAtTheSameLocation=0`;
  `Unlock`/`Start` return 0, so they are probably commands, not variables.
- `ExecuteConsoleCommand("a.Ron.PVP.MinTeams 1")` **does not change the value**; `a.Ron.PVP.Unlock 1` and
  `a.Ron.PVP.Start` have no visible effect either in the menu or in the lobby. Meanwhile `open <map>?listen` through
  the same call works.
- `open RoN_Station_MultiplayerLobby?listen` loads the lobby with `GM_COOP_BarricadedSuspects_C` /
  `GS_COOP_BarricadedSuspects_C` (`PvPState=0`), but the screen stays black: bypassing the menu leaves out session/mode
  parameters.
- `HighResShot 1` saves a PNG to `ReadyOrNot/Ready Or Not/Saved/Screenshots/`, which is a way to look at the game
  without screen control.

Observation (JMAP reflection dump, 49,429 objects):
- `ReadyOrNotFunctionLibrary::IsSecretPvPUnlocked() -> bool` (static, no parameters),
  `IsSecretPvP(WorldContext) -> bool`, `IsInDefusalWarmup() -> bool`;
  `BpGameplayHelperLib::IsPvPSupported(FLevelDataLookupTable) -> bool`.
- Hierarchy: `GM_Defusal_C` → `DefusalGM` → `ReadyOrNotGameMode_PVP` → `ReadyOrNotGameMode` → `GameModeBase`.
  - `ReadyOrNotGameMode_PVP`: `RoundWonTeam(ETeamType)`, `RoundWon`, `RoundEnd`, `NextRound` [Exec], `MatchEnd`,
    `CheckRoundEnd` [BP event], `TimelimitReached`, `Multicast_SetWinningTeam`, `RoundEndResetDelay`,
    `MatchEndResetDelay`.
  - `ReadyOrNotGameMode`: `StartMatch`, `SetMatchState`, `SwapPlayerTeams`, `RespawnAllPlayers(OnTeam)`,
    `RespawnPlayer`, `RespawnDeadPlayers`, `IsTeamDead(Team, bIncludeArrestedAsDead)`, `SpawnPlayerCharacter`,
    `SpawnSpectator`, `MinimumPlayersToStart`, `RespawnMode`, `bCanRespawn`, start tags
    `SWATRedStartTag`/`SWATBlueStartTag`/`SuspectStartTag`.
  - `DefusalGM`: `SelectedBombActor`, `SwatSpawn`, `SuspectSpawn`, `SpawnPoints[AISpawn]`, `SuspectSpawnData`,
    `SuspectFPArmsOverride`.
  - `DefusalGS`: `DefusalMatchState`, `CountdownUntilMatchStarts`, `ElapsedRoundTime`, `BombTimeRemaining`.
  - `ReadyOrNotGameState` (replicated to everyone): `RedTeamWins`, `BlueTeamWins`, `RoundsPlayed`, `RoundsToPlay`,
    `RoundTimeRemaining`, `RoundWinningTeam`, `MatchWinningTeam`, `TeamPlayers`, `bPvPMode`, `ModeURL_Replicated`,
    `Multicast_OnRoundReset`.
- Teams: `ETeamType::{TT_NONE, TT_SERT_RED, TT_SERT_BLUE, TT_SUSPECT, TT_CIVILIAN, TT_SQUAD}`.
- **Mode aliases** (`GameMapsSettings.GameModeClassAliases`): `RR_PVP` → `GM_Defusal`, `ff` → `GM_Firefight`,
  `tdm`, `vip`, `aar`, `koth`, `ctf`, `tow`, `gungame`, `Incrim`, `free`, `lobby`, `coop`, `*_COOP`, `commander`.
  The game itself builds URLs like `?game=lobby`, `?game=coop`, `?game=commander?save=`, `?Listen?Port=`.

Conclusion:
- `a.Ron.PVP.*` are most likely cheat variables/commands (`ECVF_Cheat`): in Shipping they cannot be changed through the
  console. If they are needed, HostBrain will set them directly through `IConsoleManager` (C++), picking the right one
  of the two singleton candidates.
- They are not required anyway: **Defusal starts with the standard alias `?game=RR_PVP`**, and the native round
  framework and the replicated score already exist in `ReadyOrNotGameMode_PVP`/`ReadyOrNotGameState`. HostBrain can
  call these functions and write these fields, and clients will see the result in the game's existing PvP UI, which
  greatly reduces the scope of our pak.

## Starting Defusal through `?game=RR_PVP` (S3 confirmed, 26.10.2026)

Method: the probe's remote console (`inbox.lua`), from the main menu `open RoN_Campus_Core?listen?game=RR_PVP`.

Observation:
- `ReadyOrNotFunctionLibrary::IsSecretPvPUnlocked()` = false, `IsSecretPvP(World)` = false, `IsDMOPVPOnly()` = false.
- After ~25 s the map `RoN_Campus_Core` (Watt Community College) loaded with **`GM_Defusal_C` + `GS_Defusal_C`**:
  `bPvPMode=true`, `ModeURL_Replicated=RR_PVP`, `RoundsToPlay=8`, `DefusalMatchState=0` (Warmup),
  `MinimumPlayersToStart=1`, `GameStartWaitTime=10`, `RespawnMode=NoRespawn`.
- The player spawned as `BasePlayer_C` (first-person view), team `2` = `TT_SERT_BLUE`.
- `DefusalGM` picked the bomb `BP_BombActor_v2` (`RoN_Campus_BarricadedSuspects` → `BP_BombActor5`) and the SWAT spawn
  `PlayerStart_1` by itself. `SuspectSpawn` is invalid: this map has no separate spawn for suspect players.
- During warmup `BombTimeRemaining` (192 → 145 in 47 s) and `RoundTimeRemaining` tick down; `DefusalMatchState` stays 0.
- After `PC:ReadyUp()` the state did not change. `IsInDefusalWarmup()` = false, although `DefusalMatchState` = 0.
- The one-time first-launch window `W_DLC_Acknowledgement_C` (tree `W_MainMenu_V3_C`) stayed on screen;
  `RemoveFromParent`/`SetVisibility` do not hide it. It closes with the «Подтвердить» (Confirm) button.

Conclusion:
- **The hidden Defusal starts the standard way, without asset replacement and without cheat variables**: it is enough
  for the host to travel to a map with `?listen?game=RR_PVP`. The HostBrain entry point is the command
  `comp_start <map>`, which builds such a URL.
- We will have to define the suspect spawns ourselves (map data `data/maps/*.json`), as the plan assumed.

**Crash when the bomb timer runs out during warmup** (00:44:59, exactly when `BombTimeRemaining` reached 0; one player,
SWAT team):
- `EXCEPTION_ACCESS_VIOLATION reading address 0x2d8` — a null pointer dereference (a field at offset 0x2D8).
- Top of the stack: `ReadyOrNotSteam-Win64-Shipping+0x2a52df0` ← `+0x4ec77dc` ← `+0x48f34a9` ← … ← `UE4SS+0x466cb5`
  (ProcessEvent hook) ← engine tick.
  A second before the crash CheatManagerEnabler reported a new PlayerController: a round reset was under way.
- Minidump and logs: `re/dumps/crash-defusal-bomb-timer/`, `re/dumps/UE4SS-run2.log`, `re/dumps/probe-run2.log`.
- **The cause was established by decompilation** (Ghidra 12.1.4, `tools/ghidra_decompile.ps1`; addresses are static
  VAs with base 0x140000000):
  - The frames were matched to functions using `.pdata` and the UFunction pointers from JMAP:
    `0x142a52df0` — the leaf getter `ALevelSequenceActor::GetSequencePlayer` (`MOV RAX,[RCX+0x2D8]`, `RCX = nullptr`);
    `0x144ec77d0` — `AReadyOrNotGameState::Multicast_StopSequence_Implementation` (vtable slot `+0x850`, checked
    against the CDO);
    `0x1448f3430` — the exec wrapper `Multicast_StopSequence(ALevelSequenceActor* SequenceActor)`;
    `0x1448f0b40` — the native stub that calls `ProcessEvent`.
  - `0x144ec87e0` — the round reset in `ReadyOrNotGameMode_PVP`: it takes the GameState (`this+0x300`) and
    **unconditionally calls `GameState->Multicast_StopSequence(nullptr)`**, then resets the timer `GS+0x694`, sets
    `MatchState` (`GS+0x7C0`) = 2 and so on.
  - It is called from `0x144c37620` (the override in `DefusalGM`: when
    `RoundsPlayed(+0x768) == RoundsToPlay(+0x76C) - 1` it goes to halftime, destroys picked-up items through
    `AActor::Destroy`, then calls `Super`), and that one from `0x144ed8b50` (the mode's `Super::Tick`): in state `this+0x4F8 == 2` the timer `GS+0x694`
    decreases, and at zero the virtual `+0x9C8` is called. All of this is inside `0x144c4e630` — `DefusalGM::Tick`
    (from `this+0xA48 = SelectedBombActor` it writes `BombTimeRemaining` into `GS+0x988`, and at bomb state 2/3 it calls
    `RoundWonTeam`).
- **Conclusion:** any transition of Defusal to a new round is guaranteed to crash: `Multicast_StopSequence(nullptr)`
  does not check for null. The multicast also runs on clients, so everyone would crash.
- **Fix for HostBrain** (host only):
  - do not run the native PvP round reset; HostBrain runs the rounds itself (`RespawnAllPlayers`, bomb reset, score
    in the GameState);
  - in addition, intercept the native `Multicast_StopSequence` stub (a detour by signature) and drop a call with
    `nullptr` **before** `ProcessEvent`, so the RPC never reaches clients.

Unknown:
- What moves Defusal from warmup to `DMS_PreRoundTimer` (probably `a.Ron.PVP.MinTeams=2`: two teams are needed).
- How the menu builds the full hosting URL with an EOS session: a bare `open RoN_Station_MultiplayerLobby?listen`
  gives a black screen in the lobby.

## Native Firefight through HostBrain (26.10.2026)

Method: HostBrain v0 (Lua + `RonCompNative.dll`), commands through the probe's remote console.

Observation:
- `RonCompNative`: `.text` has 111 stubs of the "event with a single pointer" kind, and exactly one of them has the
  FName `Multicast_StopSequence` (ComparisonIndex 67594 in this run), at `exe+0x48f0b40`, the same address that was
  found statically. The detour is installed.
- `comp_start campus ff` → `RoN_Campus_Core?listen?game=ff` → `GM_Firefight_C` + `GS_Firefight_C`, `bPvPMode=true`,
  `RoundsToPlay=2`, `RespawnMode=ImmediateRespawn`, `RoundEndResetDelay=5`, `MatchEndResetDelay=10`; the player is in
  team 2 (SERT_BLUE).
- First comes the «Перед заданием» (Pre-mission) screen with the «Готовы» (Ready) button (`MatchState=MS_Warmup`).
  After `PlayerController::ReadyUp()` the state is `MS_Playing`, and the player is on the map in first person
  (screenshot).
- One player: red is empty → the round is immediately awarded to blue (`MS_RoundEnded`, `BlueTeamWins=1`). The next
  round does not start by itself (it waits for the second team); `ReadyOrNotGameMode_PVP::NextRound()` → round 2 →
  2:0 → match end → after 10 s a restart into warmup with a score of 0:0. **No crashes**; the Firefight path does not
  call `StopSequence(nullptr)`.
- `EMatchState`: `MS_None, MS_Warmup, MS_Playing, MS_RoundEnded, MS_MatchEnded, MS_GoingToNextLevel`.

Conclusion:
- The native Firefight works "as designed" even without our changes; HostBrain is needed to start it, for hit
  validation and as a safety net. The `StopSequence` protection stays for Defusal (there the `nullptr` call is
  confirmed by a crash).

- **Map and mode compatibility.** `BpGameplayHelperLib::GetMapDetailsFromName(Map)` → `FLevelDataLookupTable`
  (it has the field `SupportedGameModes`), `IsPvPSupported(row)` = **false for all 30 maps**: officially, PvP is not
  enabled anywhere.
  Works: `RoN_Campus_Core` + `ff`, `RoN_Campus_Core` + `RR_PVP`.
  Does not work: `RoN_Valley_Core` + `tdm` → `LowLevelFatalError: Couldn't spawn player: Could not find a starting spot`
  (TDM has its own team start points, and the map has none; dump `re/dumps/crash-valley-tdm/`).
  HostBrain allows only tested pairs; the rest need `force`.
- **The `StopSequence(nullptr)` path happens in Firefight too**: in one run, ~20 s after the campus loaded, the stack
  went through `144ed8b50+0x109 → 144ec87e0 → stub` (return `+0x4ec884a`).
- **Lesson: `RestartMod` does not remove hooks on Blueprint functions** (27.10.2026). The restart log has
  "Unregistering hook" only for native functions. Script hooks (`Registered script hook` on
  `W_PreMission_C:SwapTeams`, `W_StandardButton_C:OnClicked_Derived`) stay and point to a Lua state that
  no longer exists. A button click after the restart hung the game: the game thread was stuck in UE4SS in
  `get_lua_state` inside the chain `ProcessEvent` → `ProcessInternal` → script hooks (minidump taken with our own
  `hangdump.py`, unwinding with `unwind.py`). In normal play the mod is not restarted; during development, after the
  first pre-mission screen we restart the whole game.
- **Lesson: `RestartMod` unloads the DLL.** When a Lua mod restarts, Lua closes its state and, through `__gc` of the
  `package` library, calls `FreeLibrary` for everything loaded with `package.loadlib`. The patch in the game stayed
  and jumped into freed memory → a crash "in tier0_s64" (`re/dumps/crash-after-restartmod/`). Fixed: `RonCompNative`
  pins itself (`GET_MODULE_HANDLE_EX_FLAG_PIN`) on the first call; the status in the log is tied to a session token
  from the ini.
- **Lesson: `_wfopen_s` opens a file without share access.** While someone was reading the log (a forgotten `tail -F`,
  PowerShell `Select-String -Quiet`), the DLL's writes silently failed (`errno 13`, `ERROR_SHARING_VIOLATION`), and
  Lua did not see the response. Fixed: the log is opened with `_wfsopen(..., _SH_DENYNO)`, open errors are written to
  `%TEMP%\RonCompNative_debug.log`.

- **The protection in action** (02:05–02:08): in 2 minutes of Firefight on the campus the game called
  `StopSequence(nullptr)` three times (02:06:33, 02:07:08, 02:07:47); all three were intercepted and the game kept
  running. Without the protection these would be three crashes for all players.
- **`open <map>?listen` does not start a server in RoN:** both in the menu and after such a travel
  `KismetSystemLibrary::IsStandalone = true` and there is no `World.NetDriver`. The game needs an online session
  (EOS/Redpoint), which the Multiplayer menu creates. So, to play with people: the host creates a lobby through the
  menu, then `comp_start` sees the server and runs `servertravel <map>?game=<mode>` for everyone. Creating the session
  programmatically is the next task (on the surface of reflection there are only
  `CreateSessionCallbackProxy::CreateSession` and Mission Builder hosting).

Unknown:
- How Firefight behaves with people on both teams (needs a second player): team selection, suspect spawn, rounds.
- Which other maps work for `ff`/`tdm`: needs automatic iteration with restarts after crashes.
- How the game creates the lobby's EOS session (so that HostBrain could create it itself).

## Player as a suspect against AI SWAT (bots, 26.10.2026)

Observation:
- The developers' Exec functions `ReadyOrNotPlayerController::SpawnBotsForGame`, `SpawnAI`, `StartSwatAutomation`
  are empty in Shipping (decompilation: stubs). `SpawnRandomAI(Count)` ("Spawn AI Console Command") and
  `SpawnAIAtLocation` (not checked) still work.
- Co-op `RoN_Campus_Core?game=BS_COOP` from the menu: an AI SWAT squad (4× `CyberneticsSwat_V2_C` + 4×
  `CyberneticsSwatTrailer_C`, teams 1/2), 5 suspects (`TT_SUSPECT`), 9 civilians; the player is in team 2.
- `ReadyOrNotPlayerState::SetTeam(3)` does not change the team. Writing `PlayerState.Team = 3` +
  `Character.DefaultTeam = 3` directly (+ `OnRep_Team`) works: `CyberneticController::IsCharacterEnemy(player)` becomes
  true for SWAT and civilians and false for suspects.
- Without orders the SWAT squad is passive and keeps following the player (who is their leader). After damage from the
  player (`GameplayStatics::ApplyDamage`) `GetTrackedTarget()` = the player, and they all aim at him (screenshot).
- When travelling from a running mission, the pre-mission screen `W_PreMission_C` appears.
  `ReadyOrNotPlayerController::ReadyUp()` gets past it: `PlayerState.bReady` becomes true about 4 s after the call, then
  the standard countdown `GameState.TimeTillGameStartCountdown` 10 → 0 runs, and the player spawns (READYWATCH log,
  26.10.2026). A repeated call after 3.5 s does not reset readiness.

- **AI SWAT do not shoot at a suspect player on their own**, even when he kills officers: living officers have
  `IsCharacterKnownEnemy(player)=true`, the player is in `TargetingComponent.KnownEnemies`, `GetTrackedTarget()=player`,
  the activity is `SwatCombatActivity`, but the rules of engagement do not let them fire at him.
  `CyberneticsSwatTrailer_C` are not combatants (their target lists are empty). Workaround:
  `BaseCombatActivity::ScriptedFireAtActor(player, t, bOverrideTarget=true, accuracy, false)` — two officers who had
  seen the player killed him in 3.5 s (160 → 0). Every 0.5 s HostBrain orders short bursts from those who see the
  player.

Conclusion: HostBrain `comp_play_suspect <map>` spawns the player as SWAT (co-op maps have no suspect start points),
then switches them to `TT_SUSPECT` and teleports them to the AI suspects; after a death the team temporarily goes back
to SWAT. `comp_alert` sets SWAT on the player. The appearance stays SWAT: the MLO model is not substituted yet.

### Rounds against AI SWAT (26.10.2026)

Messages on the host's screen (checked with screenshots; Cyrillic is displayed):
- `W_HumanCharacter_HUD_V2_C::AddObjectivePopup(FText)` — a line at the bottom centre.
- `AddToast(FString)` — a banner on the left.
- `AddScorePopup(FText, int, bool)` — "… +N".
- `PlayerCharacter::Client_SendToast` and `ReadyOrNotGameState::Multicast_BroadcastChatMessage` return ok, but nothing
  is visible.
- The death screen («БОЕЦ УБИТ», "officer down") covers the HUD, so the round result is repeated after the mission
  reloads.
- The pawn after death is `DeadSpectator_C`; before the spawn it is `SpectatorPawn`.

Squad orders:
- First `SWATManager.SquadLeader` = a living `CyberneticsSwat_V2_C`; without this the squad follows the player as its
  leader.
- Then orders with `TeamType = TT_SQUAD (5)`.
- `GiveMoveCommand(5, point)`: 39 → 19 m in a straight line in 30 s. The squad HUD shows «Идти к» (Move to).
- `GiveSearchAndSecureCommand(5, point, false)`: room clearing («Исключить, зачистить», «Осмотр: угол»: roughly
  "Exclude, clear", "Check: corner"), 49 → 46 m to the target in 20 s.

What a bot knows about the player:
- `CyberneticController::IsCharacterKnownEnemy`;
- `TargetingComponent::CanCharacterBeSeen` / `GetLastKnownEnemyPosition`;
- `CyberneticController::GetHeardActorInstigator`;
- `HasBeenExposedToAggressiveNoise(sec, dist, mask)`;
- shots go through the RPCs `BaseMagazineWeapon::Server_OnFire` and `Multicast_OnFire`. HostBrain intercepts them
  to mark where the player fired from.

Loadout (`BpGameplayHelperLib::EquipLoadoutOnPlayer`):
- **AI suspect weapons (`/Game/Blueprints/Items/WeaponsSuspect/*`) must not be given to a player.** The player gets no
  magazines for them. If a suspect pistol is drawn (`Secondary_S_Python` and others), the first-person animation
  breaks, the player is thrown off the map and dies (`DeadSpectator_C`).
- Player weapons from `/Game/Blueprints/Items/WeaponsRevised` with `PrimaryAmmoSlotsCount = -1` /
  `SecondaryAmmoSlotsCount = -1` get the standard magazines: AK-103 — 4×30, P99 — 3×15. The 8 random loadouts
  `Default__GM_Firefight_C.RandomLoadouts` are built the same way, but they are SWAT loadouts.
- In `PlayerState.ServerSavedLoadout` a co-op player has explicit slots: `556x45FMJ` ×5,
  `PrimaryAmmunition = Null_AmmunitionAttachment_C`.
- Armour is removed. Grenades and tactical devices from the pre-mission loadout remain, even if the loadout has
  `GrenadeSlotsCount = 0`.
- Suspect-style player weapons: `Primary_AK102`, `Primary_AK103`, `Primary_SLR47`, `Primary_Saiga12`,
  `Primary_G3A3`, `Primary_FAL`, `Primary_870mcs`.

Other:
- In UE4SS a function that returns a TArray (`InventoryComponent::GetInventoryItems`) gives a Lua table.
  The `InventoryItems` property is a TArray with `ForEach`.
- Teleporting with `K2_SetActorLocation(..., bTeleport=true)` without checks can put the player inside a table or a
  chair. `AActor::K2_TeleportTo` refuses or pushes the actor out of the overlap: from a stuck position it moved the
  player by 76 cm. HostBrain additionally checks with `LineTraceSingle` traces that the suspect can see the point and
  that there is a floor under it.

Suspect appearance (not done, leads):
- `ReadyOrNotCharacter::UpdateOverridesFromCharacterLookOverrideDataTable(LookOverride)` (Exec) applies a row of the
  look table.
- The replicated `Rep_CharacterLookOverride` (FString, `OnRep_CharacterLookOverride`) and `Rep_FPMesh`.
- The `CharacterLookOverride` struct contains `FPMeshOverride`. A co-op player has
  `SavedLoadout.CharacterLookOverride = "SWAT_Judge"`.
- `BpGameplayHelperLib::GetCharacterLookOverrideDataTable()` returned `nil` in a co-op mission: the table is not loaded.
  `Default__GM_Defusal_C.CharacterLookMap` is empty.
- Assets of the playable suspect: arms `Character/MLO/ron_suspect_fp_player_mlo`, materials `PVP__MI_MLO_*`,
  the animation flag `ReadyOrNotAnimInstance.bIsTeamMLO`.

## Crash after ~2 h of play: Lua from two threads (26.10.2026)

Observation:
- Report `%LOCALAPPDATA%\ReadyOrNot\Saved\Crashes\UECC-Windows-8BF10F...`: `EXCEPTION_ACCESS_VIOLATION reading 0xa`.
  The stack in `CrashContext.runtime-xml` is useless without symbols.
- Shipping has no log of its own, and `UE4SS.log` had not changed for almost 2 hours by the time of the crash (12:43).
- Unwinding the minidump with `.pdata` / `UNWIND_INFO` of the modules on disk (the `unwind.py` script in the session's
  working folder). The game's main thread:
  1. engine tick (`exe+0x365f185`);
  2. the UE4SS game-task handler (`UE4SS.dll+0x466c40` / `+0x45d310`);
  3. `LuaMadeSimple::Lua::call_function`;
  4. three Lua levels (`pcall` → `pcall`);
  5. `process_lua_function`;
  6. `__index` of a userdata (`UE4SS.dll+0xb9eff0`, the same handler that earlier gave the error
     "System: Global for __index doesn't exist");
  7. `UE4SS.dll+0xc6a4b0` = `lua_setiuservalue`, where the Udata at index −2 turned out to be NULL
     (`movzx r9d, word [r10+0xa]`).
- A corrupted Lua state. In HostBrain the same Lua state was used at the same time by:
  - the UE4SS worker thread: `LoopAsync` callbacks (1 s and 0.5 s) created closures and called `ExecuteInGameThread`;
  - the game thread: ticks, console commands, the `BaseMagazineWeapon:Multicast_OnFire` hook on every shot of any
    weapon.

Conclusion: in mods, never run Lua outside the game thread. Loops: `LoopInGameThreadWithDelay`; delays:
`ExecuteInGameThreadWithDelay`. No `LoopAsync`, `ExecuteWithDelay`, `RegisterKeyBind`.
This UE4SS build has `LoopInGameThreadWithDelay`, `LoopInGameThreadAfterFrames`, `ExecuteInGameThreadWithDelay`,
`RetriggerableExecuteInGameThreadWithDelay`, `CancelDelayedAction`, `RegisterEngineTickPre/PostCallback`.
Ghidra on UE4SS.dll: `tools/ghidra_decompile.ps1 -Binary ...\ue4ss\UE4SS.dll -Project UE4SS <VA>` (base 0x180000000).

## Hidden co-op PvP "SWAT vs suspects" (26.10.2026)

Observation (decompilation and in-game checks):
- **The mode flag: `CoopGS.bCrouchingTigerHiddenDragon`** (offset 0xa7d, `CPF_Net | RepNotify`,
  `OnRep_CrouchingTigerHiddenDragon`). Next to it are `CoopGS.PvPState` (`EPvPState`, replicated),
  `PreRoundRemainingTime`, `ActorsToHandleInPvP`, and `CoopGM` has `PreRoundTimeout`.
  - The exe writes `0xa7d` only in the `CoopGS` constructors (zeroing; `tools/ghidra_decompile.ps1` + an offset scan).
    The mode was supposed to be turned on by `a.Ron.PVP.Start` / `a.Ron.PVP.Unlock`, but in Shipping these console
    commands (flag `ECVF_Cheat`) are bound to a function consisting of a single `RET` (`0x140b07d90`).
  - Flag checks: `FUN_144e3ad60(GameState)` and `FUN_144e3adb0()`. The second one is called by
    `ReadyOrNotFunctionLibrary::IsSecretPvP`: after the flag is written on the host, it returns `true`.
- **What the game changes by itself when the flag is set:**
  - `IsEnemyTeam(a, b)` → "the teams differ", `IsFriendlyTeam` → "the teams match" (`FUN_144de8200/8290/8330`);
  - `IsOnSameTeam` (`FUN_144e76f90`) → a comparison of `GetTeam()`;
  - the list of team cameras (`PlayerCharacter::GetAvaliablePlayersForTeamView`) and the spectating candidates
    (`SpectatePawn::SpectateNextPlayer` → `FUN_144b85dd0`): own team only;
  - the radio message queue (`FUN_144dc7730` and its neighbours) is not filled;
  - automatic team assignment on join (`FUN_144ea4940`) is disabled.
- **The flag does not affect AI.** `IsCharacterEnemy` of AI SWAT, AI suspects and civilians is the same with and
  without the flag: AI SWAT do not shoot civilians.
- **By default an AI SWAT squad exists only in a single-player mission.** The mission start (`FUN_144c05e10`) creates
  the squad (`FUN_144c02290`) only if all of these conditions hold:
  - fewer than two humans;
  - the server is not dedicated;
  - the level script has the flag `+0xcbe`;
  - the world has no `NetDriver` (`world+0x38 == 0`).

  Workaround: the console variable `a.RonSpawnSwatInIncompatibleMode` (its description in the exe: "always spawn the
  swat… even if… multiplayer"). It is not marked `ECVF_Cheat`, and `Exec` on the host sets it. Tested: in a network
  mission with the value 1, 4 `CyberneticsSwat_V2_C` appear, and the PvP flag does not remove them.
- **Mission start.** The AI squad is created around the pawn of player 0 (`ACoopGM`, `FUN_144c02290`:
  `defaultblueone`…`trailer`, `&ACoopGM::FriendlyAIKilled`). If the host has no pawn (team 3 before the spawn), the
  fallback branch calls a null pointer and the game crashes. Without the flag the same team 3 gave the fatal error
  "Couldn't spawn player"; with the flag there is simply no pawn. So everyone spawns as SWAT and is switched after
  the spawn.
- `ReadyOrNotPlayerController::Server_SetTeamType` changes the team only on the pre-mission screen.
  In a running mission, writing `PlayerState.Team` directly plus `OnRep_Team` works.
- **Player spawn.** The game does not call `GameModeBase::RestartPlayer` / `K2_OnRestartPlayer` (the hook does not
  fire). The spawn at mission start does not take the loadout from `PlayerState.ServerSavedLoadout`.
  `BpGameplayHelperLib::EquipLoadoutOnPlayer` with `Armor_NoArmor_C` / `Helmet_None_C` helps: this removes the armour
  and the helmet.
- **`ReadyOrNotGameMode::RespawnPlayer`** (`vtable+0x9e8` → `0x144ed2700`):
  - `CurrentMatchState` = Warmup/MatchEnded — spawns at the start;
  - `MS_Playing` — only teams 1/2 with `PlayerState.bIsInGame`;
  - in the mode with the flag a killed player comes back as a spectator
    (`a.Ron.PVP.ForceRespawnAsSpectatorWhenKilled = 1`).
- **`ReadyOrNotGameMode::SpawnPlayerCharacter(PC, GameMode.DefaultPawnClass, Transform, bNoFail)`**:
  - the Transform is built with `KismetMathLibrary::MakeTransform`;
  - the character appears exactly at the point, and the controller possesses it by itself;
  - the team is taken from `PlayerState.Team`, the loadout from `ServerSavedLoadout` (SBR with 4 magazines, Python
    with 3, no armour).
- `CoopGM::MissionEnd(bSuccess)` opens the standard debriefing screen («НЕ ПРОЙДЕНО», "failed", with `false`).
- `CoopGM.bOverrideSuspectCustomizationInPvp = true`, `SuspectPlayerCustomizationOverride` is the game's own clothing
  for a suspect player: `CSK_RapidResponse_Shirt_Buttoned`, `CSK_DETE_Pants`, `CSK_Swat_NoGlove`.
  - The game does not apply it by itself. HostBrain copies the set fields into
    `ReadyOrNotPlayerState::Server_SetCustomization` with `bForceLiveUpdate = true`.
  - The implementation (`vtable+0x7e8` → `0x144a43d20`) writes `PlayerState.Customization` (`+0xd40`) and, with a
    live update, re-dresses the character (`+0x730`). It does not write to the profile save: the next mission starts
    with the player's own clothes.
  - Tested on the host: bare hands, a suspect shirt and trousers. The helmet, shoes and the watch slot
    (`CBP_Handcuff`) stay from the profile: the preset does not have them.

**SWAT action filter (RonCompNative).** It replaces `UFunction::Func` of server RPCs. The layout found:
- `UFunction::Func` = `+0xd8` (the only pointer into `.text`);
- `UStruct::SuperStruct` = `+0x40`;
- `FFrame::Code` = `+0x20`, `FFrame::Locals` = `+0x28`;
- `AReadyOrNotCharacter::DefaultTeam` = `+0x1129`.

Check in a mission: for a character in team 2 `Server_Yell` goes through. With `DefaultTeam = 3`, `Server_Yell`,
`Server_Interact` (target: a civilian) and `Server_GiveAIMoveToExit` are blocked. The filter lets a call from Blueprint
bytecode (`Code != 0`) through and logs it: the parameters of such a call are not yet read from the caller's code.

**The team button on the pre-mission screen** (`W_PreMission_C`, Blueprint bytecode disassembled using JMAP, script
`kdis.py`):
- `SwapTeams_Box` is visible only if `AllowTeamSwapping() && !bInGame`. `AllowTeamSwapping` returns `false` for
  `CoopGS` and `VIPEscortGS`, so a co-op mission has no such button.
- A click calls `SwapTeams()`. If the player has not pressed «Готов» (Ready), it switches `PlayerState.Team` 1 ↔ 2
  (`ReadyOrNotPlayerState::SetTeam`), that is, red ↔ blue SWAT. With team 2 the caption is "Swap to MLO team":
  in the developers' design the red team was MLO. HostBrain keeps suspects in team 3, so that AI suspects remain
  their allies.
- UE4SS in this build does not replace the return value of a Blueprint function: neither a return value from a
  `RegisterHook` callback nor `:set()` on a parameter works. The third argument (the post-callback) is not called.
- Instead, HostBrain calls `SwapTeams_Box:SetVisibility(Visible)` on the host's screen: a constant replaces the Slate
  binding until the widget is recreated.
  - The button is a key hint, and the caption «ПОМЕНЯТЬ КОМАНДЫ» (SWAP TEAMS) is a separate element of the screen.
    The button's own text (`SetButtonText`) is drawn dark on top of it, so HostBrain clears it.
  - The chosen side is shown in the mode line: `ModeName_Text:SetText`. In UE5 `UTextBlock::SetText` removes the
    binding.
  - A hook on `SwapTeams` switches the host between SWAT and suspects.
  - Clients cannot be shown the button this way (they have no UE4SS); they choose through chat.
- **Team selection menu without a pak** (`hb_menu.lua`):
  - the panel is built in the screen's root `CanvasPanel` (`W_PreMission_C.WidgetTree.RootWidget`) from `Border`,
    `VerticalBox`, `HorizontalBox`, `SizeBox`, `TextBlock` through `StaticConstructObject(class, WidgetTree)`;
  - background: `Border.Background.DrawAs = Image` and `SetBrushColor`; font size: a copy of `TextBlock.Font` with a
    new `Size` in `SetFont`;
  - the buttons are the game's `W_StandardButton_C` (`WidgetBlueprintLibrary::Create`), their look is set by
    `DisplayStyle`: 0 light, 3 red, 6 grey, 8 yellow (the enum values have no names in the game; they were picked on
    screen);
  - both the mouse and `SimulateClicked` go through `W_StandardButton_C::OnClicked_Derived`; a single hook on it
    tells the buttons apart by address. After `SetButtonText` the button caption is in the inner `Text`, not in
    `ButtonText`.
- **UMG margins from Lua.** In this build the `FMargin` fields are reflected as `Left`, `top`, `Right`, `bottom` (the
  FName case), and UE4SS matches table keys case-sensitively: `{Top=…}` is silently dropped. HostBrain passes both
  spellings (`Margin()` in `hb_menu.lua`); this works for `Border:SetPadding` and for slot paddings alike.
- **Readiness in a single-player mission.** About 4 s after the screen appears, the host becomes ready without
  pressing anything, and the mission starts 10 s later. This is neither HostBrain nor the probe; possibly one of the
  mod.io mods. Un-readying failed: neither `Server_SetReadyState(false)` nor `ToggleReady` helps. Holding the
  countdown worked: until the host presses «Готов» (the `ToggleReady` hook), HostBrain sets
  `GameState.TimeTillGameStartCountdown` back to 10 every frame.
  Tested: the countdown stood still for more than a minute, and after «Готов» the mission started 10 s later.

**Civilians and the PvP flag** (27.10.2026). Players reported that the AI squad kills hostages.
- With the flag, `IsEnemyTeam` (`FUN_144de8200`) answers "the teams differ". Civilians (`TT_CIVILIAN` = 4) become
  enemies of AI SWAT (2/5) and AI suspects (3). With the flag, `IsFriendlyTeam` (`FUN_144de8290`, `FUN_144de8330`)
  stops treating SWAT and civilians as friends.
- The normal rules: SWAT (1, 2, 5) and civilians are enemies of suspects (3), and a suspect is not an enemy of a
  civilian.
- `RonCompNative` finds the three flag checks by pattern and makes them blind to the flag:
  - in `IsEnemyTeam`, `jz` becomes `jmp`;
  - in `IsFriendlyTeam`, `test al,al; jnz` is replaced with `xor al,al; nop; nop` (the code after it compares with AL).

  Spectating and team cameras check the flag in other code and stay separate per team.
- Tested in a match with the player as a suspect and 4 bots: all 9 `Cybernetics_Civilian_V2_C` are alive.

**Mission score in PvP.** `AScoringManager::Multicast_DisplayScore(FText, int32, bool)` draws "+N" for all players.
- The native stub (`0x14492cbd0`) was found through the global FName: a static initializer refers to the string
  `Multicast_DisplayScore`; the DLL searches for `mov rdx,[rip+name]` and takes the function boundaries from `.pdata`.
- The stub is hooked (a 16-byte prologue without RIP-relative addressing). While Lua holds "PvP on"
  (`RonCompNative_PvpOn` / `_PvpOff`), the call does not reach `ProcessEvent`, and the multicast is sent to nobody.
- Tested: "+200", "+25", "+5" were blocked in a match.

**Weapon sway for a suspect.** We measured the range of position and rotation of `ItemMesh` relative to
`FirstPersonCameraComponent` while strafing (`AddMovementInput`, 3 s), and also the camera shake.
- Team (2 or 3), clothes, lack of armour and gear, weapon (AK102, SBR, FAL, MK18) do not change the sway: the yaw range
  is about 2.8°, roll about 1.4°.
- A large range (yaw 22°, roll 66°) was seen only on characters just placed at an AI suspect's spot: the speed there
  was 288 with `MaxWalkSpeed` 240, so the character was being pushed around (stairs, furniture).
- Camera shake (`RightShake`/`ForwardShake`) is about 0.1°; it was not suppressed during the measurements.
- **The cause is the guns themselves.** The player clarified: the weapon sways when aiming and strafing with an AK. A
  measurement in his game (read-only): while aiming, the AK-103 wanders 5–30° in pitch per second, and the camera is
  still.
- Default parameters in the weapon classes (`BaseItem`):

  | Weapon | `InertiaDragStrafeRotation` / `Location` | `FreeAimLimitADS` |
  |---|---|---|
  | AK-103 | 1.0 / 1.0 | 4.5 |
  | AK-102, G3A3, Saiga-12 | 1.0 / 1.0 | 1.5–4 |
  | MK18, SLR-47, MP5 | 0.4 / 0.2 | 1.0 |
  | FAL | 0.6 / 0.3 | 0 |
  | 870 | 0.4 / 0.12 | 0 |

  Pistols are fine. These four guns are no longer given to a suspect player:
  - AK → SLR-47 (also AK-like);
  - G3A3 and machine guns → FAL;
  - the random set of the solo mode keeps SLR-47, FAL, 870 and MP5.

  Substitution at issue time works for clients too, while editing the instance's properties would only work on the
  host.

**A door responds with a delay.** Player report: the icon on a door appears after about 2 seconds. In the HUD the game
shows `CommandContext_Container` (visibility 4) when the character has a context, a door included.
HostBrain collapsed it on the suspect host once a second together with the squad panel, so the hint disappeared
until the game showed it again. Now only `SWATTeamStatus_V2` is hidden.

UE4SS traps that crashed the game:
- `obj:GetClass()` on a null object reads `+0x10`;
- `GameplayStatics::ApplyDamage` with an empty instigator crashes the game's `TakeDamage`.

Conclusion: HostBrain `comp_pvp` (`hb_pvp.lua`):
- sets the flag (with bots, after the squad has appeared);
- runs team selection on the pre-mission screen;
- moves suspects to the places of AI suspects in the first frame of their pawn;
- after a death, creates the player through `SpawnPlayerCharacter` in place of another AI;
- plays a match of rounds without `MissionEnd` (the "PvP rounds" section below).

With bots, HostBrain sets `a.RonSpawnSwatInIncompatibleMode 1` at mission start and clears it once the squad has
appeared (or after 30 s). The squad is created around the host's pawn and follows `SWATManager.SquadLeader`. Therefore:
- a suspect host moves to an AI only after the squad has appeared (5 s at most);
- the leader becomes a living SWAT player, or an AI if there is none, and then the squad is driven by the "hunter"
  shared with the solo mode (`hb_hunt.lua`).

Tested on the host (host as a suspect, 4 bots): the squad appeared at the van and got orders from hints and on
detection. After a death the host took over an AI suspect 10 s later.

## PvP rounds (27.10.2026)

Problem: a player complained that the suspects got the standard SWAT debriefing screen at the end
(`CoopGM::MissionEnd`), and there was no next round.

Observation (JMAP, in-game checks):
- A round reset in a co-op mission is a reload of the same map. The map name comes from
  `GameplayStatics::GetCurrentLevelName(world, true)` (`RoN_Campus_Core`), the mode from `?game=` in
  `GameModeBase.OptionsString`, otherwise `BS_COOP` (`GameState.ModeURL_Replicated` is `BS_COOP` too).
  - In single player: `open <map>?game=<mode>`; online: `servertravel` (the clients stay).
  - It takes about 11 s from the command to the pre-mission screen.
- Readiness: `ReadyOrNotPlayerController::Server_SetReadyState(bReady)` [NetServer], `ReadyUp()`,
  `ReadyOrNotGameState::IsEveryoneReady()` and `TimeTillGameStartCountdown` (the countdown after everyone is ready).
  - In single player the host is marked ready by itself after about 4 s; then 10 s of countdown follow.
- Before the load, every player's team goes back to SWAT: co-op maps have no suspect starts.
- The game has its own round end screen (`W_PVP_RoundEnd`, `URoundEndWidget_PVP::OnGameModeRoundEnded`), but it
  lives in `ReadyOrNotGameMode_PVP`, not in co-op.

Conclusion (`hb_pvp.lua`, `hb_menu.lua`):
- a round ends inside the mission: score, result in chat, and after 6 s the same mission reloads;
- on the new pre-mission screen the host's menu page shows the round result; after 8 s everyone is marked ready:
  the host through `ReadyUp`, clients through `Server_SetReadyState(true)` on the server;
- after round N−1 the players swap sides, and the score moves with them. From the second round on the match also runs
  without suspect players (a host alone after the swap is SWAT with bots against AI suspects);
- match end: the «МАТЧ ОКОНЧЕН» (Match over) page; the start is held until «НОВЫЙ МАТЧ» (New match).

Tested on the host (single player, campus, match to 2 wins, rounds closed with `comp_pvp_endround`):
- round 1 as a suspect → side swap, the host plays SWAT in round 2, the score carried over (SWAT 1 : 0);
- the rounds started by themselves ~14 s after the pre-mission screen;
- the results page switches to the game's countdown;
- after the deciding round: «МАТЧ ОКОНЧЕН»; «НОВЫЙ МАТЧ» brought back round 1 and a score of 0 : 0.

Not tested (needs a friend): `servertravel` with a client, client readiness through `Server_SetReadyState`, the
clothes of a SWAT client after the side swap. The game may end the mission by itself when all players are dead
(`ReadyOrNotGameMode::AreAllPlayersDead`); loading the next round after 6 s overrides that, but the standard screen
may flash.

**Suspect reports.** A suspect player could report over the radio like SWAT. Besides `Server_ReportTarget` and
`Server_ReportToTOC`, the filter now also cuts `ReadyOrNotCharacter::Server_PlayTOCConversation`. A call from the
host's team 3 pawn produced `blocked Server_PlayTOCConversation from a suspect` in `RonCompNative.log`. The report
animation and voice start on the player's side before the RPC; they cannot be removed on a vanilla client.

## Suspect damage to SWAT (27.10.2026)

Problem: a player on the suspect side barely wounded AI SWAT and asked whether the game treats his shots as friendly
fire.

Observation (Ghidra 12.1.4, reflection, in-game measurements through RonCompProbe):
- **Friendly fire has nothing to do with it.**
  - `AReadyOrNotCharacter::TakeDamage` (`0x144e92f10`) is shared by all characters. Damage is computed by the handlers
    in vtable slot `+0xE40`: `0x144b54080` for a player, `0x144b1f330` / `0x144b20320` for AI.
  - The handlers ask `IsOnSameTeam(victim, shooter's pawn)` (`0x144e769c0` → `0x144e76f90`). For a teammate the damage
    is zeroed only if `UReadyOrNotAIConfig` gives `FriendlyFireEnabled = false` (true by default).
  - `IsOnSameTeam` for a suspect (team 3) and SWAT (2, 5) is "no" in both versions. With the
    `bCrouchingTigerHiddenDragon` flag it is a comparison of `GetTeam()`; without the flag teams 1 and 2 count as one
    side, and 3 is not on it.
  - Damage to a player is additionally multiplied by `ReadyOrNotGameState.GametypeDamageModifier` (1.0 in all co-op
    GS).
- **AI SWAT (`CyberneticsSwat_V2_C`) have 250 HP, a player has 160.** They wear the light vest `Armor_Light_V2`
  (`SWATArmour`) with the material `AM_Ceramic` (`ArmourLevel` 6, `DamageReduction` 1.0, `MinDamageReduction` 0.4,
  durability 4 per plate, `SWATArmour.Durabilities` = [4, 4, 0]) and a helmet.
  - The spare squad copies `CyberneticsSwatTrailer_C` stand outside the map (Z = −10000) in `AM_Steel`
    (level 6, 0.865/0.7, no durability).
  - A SWAT player has `Armor_Heavy_V2` + `AM_Kevlar` by default (level 3, 0.5/0.5).
- **Ammo** (`AmmoDataTable`, 41 rows): `PenetrationLevel` is at most 4 (rifle FMJ); 9×19 FMJ has 2,
  JHP 0, buckshot 1.
  - `HitsChance` / `ArmouredHitsChance` are the chance of a hit animation (`HitAnimationChanceMultiplier`), not of
    penetration.
  - A real shot (`Server_HitscanHit`, `0x1449a06e0`) takes the ammo row from
    `BaseWeapon.AmmunitionTypes[AmmoTypeIndex]`, not from the weapon's `CurrentAmmoType`.
- Measurements:
  - **`GameplayStatics::ApplyPointDamage` from Lua with a trace to a bone:** torso 0 with any penetration and
    material, arm 21, leg 30; the helmet holds until it is knocked off.
    - UE4SS does not pass an `FWeakObjectPtr` from a Lua table into the function (`[push_weakobjectproperty] Error`),
      so such an `FHitResult` has no actor and no component, and this path does not model armour.
  - **An AI shot (`BaseCombatActivity::ScriptedFireAtActor`) with 300AAC FMJ:** against Kevlar −21.9 HP per hit
    (about half the damage), plate 4 → 3.67. Against ceramic and steel no torso damage got through in any of the
    measurements.
- **What the player was armed with** (the `RoNPvPLog.sav` log): MP5A2 + M92FS / Python / P99 / M1911, a FAL once.
  - The AI suspects on `RoN_Gas_BarricadedSuspects_Core` have only pistols (Tec9, Python), so the primary weapon
    was picked at random from SLR-47, FAL, 870 and MP5A2.
  - AI suspects have 360 HP.
- **`ReadyOrNotCharacter::DecreaseHealth` called from a script on an AI crashes the game.** An exception in
  `0x144e62990`; the game hangs in the crash handler (minidump with `hangdump.py`, unwinding with `unwind.py`). Do not
  change bot health this way.

Conclusion (0.2.1-alpha, both versions):
- suspect players get only rifles firing FMJ:
  - SMGs, machine pistols and the random pick → SLR-47 or FAL;
  - shotguns → FAL;
  - pistol calibres do not penetrate even the standard Kevlar of a SWAT player;
- the AI SWAT squad in PvP is switched to the default player armour material (`AM_Kevlar`). The swap is done by
  `PvPDirector.ArmourSquad` / `hb_loadout.ArmourSquad` every second of a live round; the property is `CPF_Net`;
- tested in game: the log says "AI squad armour -> Kevlar: 4", the bots have `AM_Kevlar`, the suspect host has an
  SLR-47 (penetration 4) + M92FS.

Not done:
- the bots' 250 HP: no safe way to change health was found;
- the armour of SWAT players: it is their choice; ceramic and steel are almost invulnerable to suspects in the torso.

## Doors and dropped guns for suspects (27.10.2026)

Task: the player asked that suspects open any door while locked doors stay locked for SWAT, and that suspects pick
up dropped guns instead of collecting them as evidence. Everything has to work in the Mods-menu version (no UE4SS).

Findings (Ghidra 12.1.4, reflection, checks in the game through RonCompProbe):
- **Doors already have the rule.** `Door.bSuspectAlwaysUnlocks` (`+0x38F`, `CPF_Edit`, not replicated):
  - `Door::CanOpenDoor(Character)` (`0x1449bb060`) treats a locked door as closed for a character only when
    `(team != 3 or !bSuspectAlwaysUnlocks) and <team>KnowsLockState and lockable (+0xFF0 bit 0) and bLocked`;
    the team test is `GetTeam() == 3` (`0x144e784c0`);
  - the opening itself (`0x1449cece0`, reached from the `OpenDoor` UFunction) uses the same exception;
  - lock knowledge: `bSWATKnowsLockState` / `bSuspectKnowsLockState` (`+0x860` bits 1 and 2, replicated). With
    `bSuspectKnowsLockState` off, a client's own check lets a suspect player try the door;
  - opening a locked door unlocks it (`bLocked` off); `SetLocked(true)` locks it again (and clears the knowledge
    bits, `0x1449d6a20`); `GetLastDoorUser()` names the character who used the door last.
- **Checked in the game** (pak, Gas station, 7 locked doors): suspect host opens a locked door (open 90°), closes it,
  the director locks it again within a second; a SWAT bot then cannot open it; the suspect opens it again. Without
  the flag the suspect cannot open it.
- **Evidence.** A dropped gun keeps its `EvidenceComponent`:
  - `EvidenceState` (`EEvidenceActorState`: Unclaimed 0, Collected 1, Extraction 2, Dropped 3; replicated),
    `bIsBeingCollected` (replicated) and `CollectingCharacter` (server only) describe a collection in progress;
  - `ReadyOrNotCharacter::PickupEvidence` only sets `PendingEvidence`; the collection completes from the animation
    (`AnimNotify_CollectEvidence` → `CollectPendingEvidence`), so a script cannot drive it;
  - `Server_Interact(gun, nil)` does nothing: some guns have no `EvidenceInteractableComponent`.
- **Loadouts.** `BpGameplayHelperLib::EquipLoadoutOnPlayer` takes a loadout without a primary; with
  `EquipItemCategory = IC_Secondary (2)` the pistol is drawn.

Result (0.3.0-alpha, Mods-menu version):
- `PvPDirector.DoorsTick`: at the round start every door gets `bSuspectAlwaysUnlocks = true` and
  `bSuspectKnowsLockState = false`; a door locked at the start locks again once it is closed and its last user is a
  suspect (a SWAT lockpick or breach stays);
- `PvPDirector.PickupTick` (every 0.2 s): while a gun is being collected by a suspect player it notes the collector;
  when the gun is collected, the player gets it (a player gun as it is, an AI suspect's gun as its player version)
  in place of the primary or the pistol. Checked by setting the evidence state the way the server has it during a
  collection: the host got the dropped `Superbnova` into its hands and kept its pistol. Not checked: a real
  collection by a player holding the key.
- rule sets (`PvPState.Rules`, «ПРАВИЛА» (Rules) button): vanilla keeps the AI's guns and armour as the mission
  built them (a pistol-only AI gives a pistol only), balanced is the 0.2.1 rifles and Kevlar.

## Native UI, stats and a fifth officer (27.10.2026)

Task: the player found the mod's green text at the side ugly and asked for a Tab scoreboard, match stats, bot slots
(five bots when the host plays a suspect), English and spawn protection, all in the game's own style.

Findings (reflection, checks in the game through RonCompProbe, Gas station, pak):
- **Messages.**
  - In a mission the game shows chat as green lines at the bottom right, its own "<name> joins the game" too. The
    mod's chat lines landed there; `W_HumanCharacter_HUD_V2_C.AddToast` shows nothing visible in this HUD.
  - `RChatMessage.bKillfeed` marks the game's kill feed lines (they go to the same list).
    `PlayerCharacter.LocalKillFeed` covers players only, so the mod writes its own kill feed lines.
  - `AddObjectivePopup(Text)` is the game's popup at the bottom centre: popups stack and fade in about 3 s. One sent
    while the mission fades in from loading (or right after a respawn) is lost, so the mode holds them for 2–3 s.
  - The chat font has no "→"; the menu font draws "·" on the baseline, like a full stop.
- **Fonts.** The pre-mission screen uses Barlow (`/Game/ReadyOrNot/Fonts/Barlow/Barlow`, typefaces SemiBold,
  Medium, Bold) with Cyrillic. The scoreboard's column titles use TeutonNormal-Bold, which falls back to another face
  for Cyrillic. A text block made by a mod gets the engine's Roboto unless it is given a font.
- **Scoreboard parts** (`/Game/Blueprints/Widgets/Common/`):
  - `W_Scoreboard_C`: root canvas → overlay (blur, border, spacer that fixes the size, `W_ScoreboardFill_C`);
  - `W_ScoreboardFill_C` rebuilds its lists on every tick in its own co-op layout, so it cannot be filled by
    hand. Its header row (`Name`, `Kills`, …, `Ping`) can be moved out; the texts are written by its refresh, so
    they come empty;
  - `W_Scoreboard_Line_C` with `PlayerState` set shows the name, kills, deaths, status (in the game's words) and
    ping, and highlights the local player. With no `PlayerState` it collapses `Deaths` and shows another column with
    "0"; `RenderOpacity` 0 hides them and keeps their place.
- **Keys:** `PlayerController.IsInputKeyDown(FKey)` reads a key without an input binding.
- **Replicated stats:** `ReadyOrNotPlayerState.Kills/Deaths` and `ReadyOrNotGameState.BlueTeamWins/RedTeamWins/
  RoundTimeRemaining` (co-op leaves them unused). `ReadyOrNotCharacter.KilledBy/IncapacitatedBy` are set from the
  damage instigator (`ApplyDamage` with a controller and a causer).
- **Spawn protection:** `ReadyOrNotCharacter.bGodMode`, set on the server, blocks damage (checked: on right after a
  takeover, off 3 s later).
- **The squad.** `SWATManager.SwatAI` holds the mission's four `CyberneticsSwat_V2_C`, squad positions 0–3. Their
  faces are `Customization.Character`: `CC_King`, `CC_Swan`, `CC_Prescott`, `CC_Eli`; `RosterCharacter` is empty in
  co-op. `SWATManager.SwatTrailers` / `CoopGM.SpawnedTrailerSWATAI` are four `CyberneticsSwatTrailer_C` kept under
  the map (Z = −10000).
- **A fifth officer:**
  - spawn: `BeginDeferredActorSpawnFromClass(CoopGM.SwatAlphaClass)`, `SquadPosition = 4` (Foxtrot),
    `FinishSpawningActor`, then `SpawnDefaultController` (`BP_SWAT_GOAP_Controller_C`);
  - the first officer's `DefaultTeam`, then onto `SWATManager.SwatAI` and `CoopGM.SpawnedSWATAI`;
  - the mission dresses only its own officers. A spawned one has no weapon and no head:
    - `EquipLoadoutOnPlayer` with the first officer's guns, armour, helmet, mount and facewear gives the kit;
    - copying `Customization` with another face (`CC_Gideon`, one of 27 loaded `CC_*`) and calling
      `OnRep_Customization` dresses it;
  - checked: it follows the squad's orders and fights; when an officer dies, the game renumbers the squad positions
    itself (Gideon became position 3).
- Officers beyond the host's pick leave the squad lists and are destroyed 2 s after the squad appears; sizing it
  earlier missed officers the mission had not spawned yet.

## Lobby limit: 5 → 10 (26.10.2026)

Observation (decompilation, checking the value in game):
- **The limit is stored in `UEOSMultiplayerSubsystem`** (a `GameInstance` subsystem), in the unreflected field `+0xac`.
  - The constructor (`0x144826dd0`) sets 5.
  - There are no other writes except `EOSMultiplayerStatics::SetMaxPlayers` (`0x144829ab0` → `0x144f07710`).
    It is also called by the console command `ReadyOrNotPlayerController::ConsoleSetMaxPlayers` (`Exec`).
  - None of the Blueprints loaded when the JMAP was taken (`W_MainMenu_V3` included) calls `SetMaxPlayers` or
    `GetMaxPlayers`. We searched for UFunction pointers in the bytecode; as a control, `PrintString` was found in 36
    functions.
- **Lobby creation.** An asynchronous operation of the subsystem (`0x144ee4040`, next to the strings `'s Lobby`,
  `CROSSPLAY`, `MM_REGION_KEY`) puts `+0xac` into `FOnlineSessionSettings.NumPublicConnections`. Redpoint EOS uses it
  to set the size of the EOS lobby.
- **Join check on the host.** `ReadyOrNotGameMode::PreLogin` (`0x144ece4d0`) answers "Server is full!" if
  `players + PlayersJoining + 1 > NumPublicConnections` of the `GameSession` session. If there is no session, the
  threshold is 5. `ReadyOrNotGameMode.MaxPlayersAllowed` (5) and `GameSession.MaxPlayers` (16) do not limit this join.
- **When the lobby is full.** `0x144f03190` updates the lobby when `+0xac <= RegisteredPlayers`
  (apparently it closes the lobby for search).
- **Changing the value does not affect a lobby that already exists:** the number of slots is set at creation.

Conclusion: HostBrain calls `SetMaxPlayers(10)` when the game starts (main menu, before a lobby is created).
`comp_maxplayers <2..16>` changes the value, `comp_status` shows it. The value 10 is confirmed in game
(`GetMaxPlayers` before and after).

Not tested (needs live players):
- that a lobby created after this accepts the 6th and later players;
- where players 6–10 will spawn. In the campus co-op mission there is one `PlayerStart` at the entry zone. The spawn
  (`SpawnPlayerCharacter` → `FActorSpawnParameters.SpawnCollisionHandlingOverride = 2`,
  "AdjustIfPossibleButAlwaysSpawn") will not fail, but it will shift the characters. PvP moves suspects to the AI
  right away.

## Hit registration (S4)

Method: JMAP reflection dump (RPC signatures, CDO defaults with the ini applied), exe strings.

Observation:
- Hitscan shooting:
  - `BaseMagazineWeapon::Server_OnFire(Rotator Direction, Vector SpawnLoc, int Seed)` [Server, Reliable, **Validate**];
  - `BaseMagazineWeapon::Server_HitscanHit(FHitResult HitResult, float Time, Vector TraceBegin, float Distance, float Penetration,
    int AmmoTypeIndex, int Seed)` [Server, Reliable, **no Validate**]: the client sends the server a ready-made trace
    result;
  - `Multicast_OnFire`, `Multicast_PerformHitscan(FHitscanShot{Location, Direction, Seed}, bLocalOnly, Seed)`,
    `Multicast_SimulateFireForViewTargets`: effects for everyone else;
  - `Client_HitscanDebug(bSuccess, Center, Extent, ImpactPoint)`: the server sends the shooter debug data of the box
    check;
  - `ReadyOrNotPlayerController::Client_OnProjectileValidation(int ProjectileSeed, EServerValidationState{Unvalidated, Validated, Invalid})`.
- Direct server damage RPCs: `BaseItem/ReadyOrNotCharacter::Server_ApplyPointDamage(DamagedActor, BaseDamage, HitFromDirection,
  HitInfo, EventInstigator, DamageCauser, DamageTypeClass)` [Validate], `PlayerCharacter::Server_TakeDamage(Damage, DamageEvent, ...)`.
- **`UHitRegistrationSettings : UDeveloperSettings`** (all fields are `Config`), CDO values in the game:
  `bEnableValidation = false`, `HitscanForgiveness = 50`, `ShooterForgiveness = 250`, `TraceDistanceForgiveness = 5`,
  `SnapshotVelocityFactor = 1.0`, `MinimumSnapshotExtent = (75, 75, 90)`.
- The console variable `a.RonForceDisableHitValidation`.

Decompilation (Ghidra 12.1.4; the implementation was found through vtable slot `+0x978` of the `BaseMagazineWeapon`
CDO → `0x1449a06e0`):
- `Server_HitscanHit_Implementation(this, FHitResult*, Time, FVector* TraceBegin, Distance, Penetration, AmmoTypeIndex, Seed)`:
  1. works only when `Role == ROLE_Authority`;
  2. takes the `UHitRegistrationSettings` CDO (`0x14483a770` is `StaticClass`, size 0x68);
  3. **if `bEnableValidation` (`+0x38`) = false, it applies the hit right away** (`0x144980fe0`), without any checks;
  4. otherwise, if `a.RonForceDisableHitValidation == 0`, it rejects the hit when:
     - `|HitResult.Location − TraceBegin| − |TraceDistanceForgiveness (+0x44)| > Distance`;
     - the target is not an `AReadyOrNotCharacter` (`0x1448cbbf0`): with validation on, hits on non-characters are not
       applied;
     - `TraceBegin` is outside the shooter's snapshot boxes ± `ShooterForgiveness (+0x40)` at time `Time`;
     - the hit point is outside the target's box, **linearly interpolated between its snapshots at time `Time`**
       (the character's snapshot array is at `+0x1AD0`, elements of 0x40: a time + min/max as doubles);
  5. on success, it applies the hit and updates the hit-marker counter (`0x14498d9e0`).
- `Server_OnFire_Implementation` (`0x1449a0e40`, slot `+0x9C0`): checks the ammo; at zero, a dry fire and
  `Client_OnProjectileValidation(Seed, Invalid)`.

Conclusion (confirmed):
- The model is **"the shooter is right"**: the client traces, the server receives an `FHitResult`.
- The game has **server-side lag compensation** based on a history of position snapshots: a `MinimumSnapshotExtent`
  box stretched by velocity (`SnapshotVelocityFactor`), with tolerances. **It is turned off in the shipped game**
  (`bEnableValidation=false`), and then the server accepts any hit it is sent.
- For HostBrain: turn on validation **on the host only** (a write to the `HitRegistrationSettings` CDO or
  `[/Script/ReadyOrNot.HitRegistrationSettings]` in the host's `Game.ini`) and tune the tolerances by measurement.
  Clients need nothing installed.
  Side effect: with validation on, hitscan hits on non-characters (doors, glass, items) are not applied; check this
  in game. If it is a problem, HostBrain does its own check in a `Server_HitscanHit` hook for hits on characters only.
- Anti-cheat risk: `Server_ApplyPointDamage`/`Server_TakeDamage` let a client claim damage, so HostBrain should filter
  them in PvP (a hook on the server).

## Weapons and gear (for `data/items.csv`)

Observation:
- SWAT weapons: `Blueprints/Items/WeaponsRevised/` (Primary_*, Secondary_*, Grenade_*, Device_*, Launcher_*,
  Sniper_M24).
- Suspect weapons: `Blueprints/Items/WeaponsSuspect/` (AKM, AK104, AKS74U, Uzi, M249, RPD, SawnOff, Tec9, Makarov,
  Melee_Knife and others).
- Armour: `Blueprints/Items/ArmorRevised/` (`Armor_Light_V2`, `Armor_Heavy_V2`, `Armor_StabVest`, `Helmet_*`).

Unknown:
- Whether weapons from `WeaponsSuspect` can be given to a player, or whether they are meant for AI only.
