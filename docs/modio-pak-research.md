# PvP as a `.pak` from the Mods menu (mod.io): research

Question: can the "SWAT vs Suspects" mode ship as a `.pak` that a player installs from the Mods menu (mod.io) in the
game's main menu, without RE-UE4SS and `RonCompNative.dll`?

Sources: the JMAP reflection dump and the game binary (`re/dumps/`, local), targeted decompilation in Ghidra
(`tools/ghidra_decompile.ps1`), searches for RIP-relative references and calls in `.text` and for UFunction pointers in
Blueprint bytecode (session scripts, not in git), [docs/re-findings.md](re-findings.md), public modding guides.
Addresses are static VAs with base `0x140000000`, exe build of 07.10.2026.

## Summary

- **The game runs logic from a pak by itself.** Since version 1.3 the game has `ModActorSpawnData` (MASD): a data
  asset with a list of actors that the game spawns on every map load. UE4SS is not needed for this.
  - The spawn happens **on every machine that has the pak**, without any check of the network role.
  - If only the host has the pak, the logic runs only on the host. This is the same scheme HostBrain uses now.
- **Almost everything from Lua can move to Blueprint.** This needs a stub module with declarations of the game's
  classes: through it, Blueprint calls functions and writes properties that the game did not expose to Blueprint.
- **The native parts are impossible in a pak:**
  - the friend/foe rules patch — there is a workaround: do not turn on the hidden PvP flag;
  - the SWAT RPC filter — no workaround, only mitigations;
  - score suppression — there is a hypothesis that needs testing.
- **Only the host has to install the pak, but the pak makes the host's game "modded".** The lobby then has the
  attribute `MODDED = true`. A vanilla client with default settings does not see such a lobby in search, and when
  joining by invite gets "Cannot join a modded session". The client's "Join modded servers" toggle helps, or the pak
  on the client itself. The current UE4SS release does not make the host modded.
- **Recommendation:** build a "PvP Lite" pak version, but first run a short feasibility check (stages 0–1 below).
  Details are at the end of the document.

## 1. How the game loads mods

Observation:
- mod.io puts mods not into `Content/Paks/Modio` but into `ReadyOrNot/Content/Paks/mod.io/3791/mods/<mod id>/`:
  - `Saved/Logs/Modio.log` has the line "Overriding RootLocalStoragePath to …\Content\Paks\mod.io\";
  - the path template in the SDK is `{}/mods/{}`;
  - 3791 is the game's id on mod.io.
  
  At the moment the user's `cache/mods/*` holds only logos; no mods are installed.
- This is a subfolder of `Content/Paks`, and at startup the engine mounts all `.pak` files in it recursively. Manual
  `~mods` and `LogicMods` work the same way.
- A new mod is not in memory until a restart: `ModioManager` has `IsRestartRequired`, the main menu has
  `Initialize Mod Installing Modal`. Disabled mods are stored in `ReadyOrNotModData.DisabledMods` (SaveGame).
- For mod logic the game provides three native classes:

  | Class | What it does |
  |---|---|
  | `UModActorSpawnData : UDataAsset` | `TArray<TSubclassOf<AActor>> BlueprintsToSpawn` |
  | `UModPersistentObjectData : UDataAsset` | `TArray<TSubclassOf<UObject>> ClassesToInstantiate` |
  | `UModPersistentObjectSubsystem : UGameInstanceSubsystem` | BlueprintCallable static: `CreatePersistentObject`, `GetPersistentObject`, `GetAllPersistentObjects`, `RemovePersistentObject` |

  There are also `ModLevelData` (custom maps in mission selection) and `ModCampaignData`.
- **How MASD works** (decompilation).
  - `ModActorSpawnSubsystem` (`UWorldSubsystem`) overrides vtable slot `+0x2d8`: `0x144e81c10`; in the base class
    this slot is an empty function. The function receives `UWorld&` and passes it to `SpawnActor`, so it is
    `OnWorldBeginPlay`.
  - The sequence:
    1. `AssetRegistry->GetAssetsByClass(ModActorSpawnData)`.
    2. Loads every asset found.
    3. For every `AActor` subclass in `BlueprintsToSpawn` calls `UWorld::SpawnActor` at the origin with default
       parameters.
  - There are no `NetMode`/`HasAuthority` checks. `ShouldCreateSubsystem` is not overridden, so the subsystem exists
    in every game world: in the main menu, in the lobby and in the mission, on the host and on clients.
  - `OnWorldBeginPlay` is called before `GameMode->StartPlay`. So the MASD actor appears before the mission starts.
- `ModPersistentObjectSubsystem::Initialize` (`0x144e74d70`) likewise collects all `ModPersistentObjectData`.
  It creates the objects through `NewObject` with the subsystem as the outer (`0x144e62780`) and keeps them in
  `PersistentModObjects`. An object lives for the whole game session and survives `servertravel`.
- Public sources:
  - VOID ([Community Resources](https://voidinteractive.net/community-resources/)): MASD appeared in 1.3 (Los
    Sueños Stories) and spawns actors on every level change, including the main menu. UE 5.3.2 is required.
  - The community reports that MASD does not fire in the **first** main menu after the game starts. The workaround
    is to enter any level and come back.
  - The Simple Blueprint Loader from Nexus became unnecessary because of MASD.

Conclusion:
- There is an entry point for logic without UE4SS, and it is official. Our actor `BP_PvPDirector` in
  `BlueprintsToSpawn` works the same way as the HostBrain tick does now:
  - on the host (`IsServer`) it runs the rules;
  - on a client with the pak it can draw UI;
  - a client without the pak simply does not have it.
- The match state between mission reloads is kept in a `ModPersistentObject` object; now Lua holds it.

Unknown:
- How the game adds mod assets to the AssetRegistry: whether it reads `AssetRegistry.bin` from the pak or scans the
  path. The first-menu bug comes from this. To be checked with a test pak.
- Whether `.sig` is required for mod paks. Community experience says it is not.

### Replacing game assets

Observation:
- The classic pak-mod approach: an asset at the same path in a pak with the `_P` suffix (patch priority) replaces the
  game's asset. For new content, guides instead recommend the path `Content/Mods/<author>/` and a name without `_P`.
- `GM_COOP_{ActiveShooter,BarricadedSuspects,BombThreat,HostageRescue,Raid}_C` are empty subclasses of `GM_COOP_C`:
  0 functions, only default values. `GM_COOP_C` is also an almost empty child of the native `CoopGM`.
  `GS_COOP_*` are built the same way.
- `W_PreMission_C` has 111 functions, about 39 KB of bytecode and 80 properties of its own. There is no source graph:
  a graph cannot be recovered from a cooked asset.

Conclusion:
- **The GameMode (`GM_COOP_*`) can be replaced.** It exists only on the server, so the pak on the host is enough. But
  the game's default values would have to be repeated after every patch, and with MASD no replacement is needed at
  all.
- **The GameState (`GS_COOP_*`) must not be replaced.** It is replicated, and different versions of the class on the
  host and on clients would break replication.
- **Replacing `W_PreMission` is not realistic.** It would have to be rebuilt from scratch without sources, and it is
  client-side, so every player would need it. Instead of replacing it, the MASD actor puts its own widget on top of
  the pre-mission screen (`AddToViewport`) or into its panel.

### What the "ModKit" gives

Observation:
- Ready or Not has no official SDK. In VOID's June 2024 briefing an SDK was promised
  ([Vol. 74](https://voidinteractive.net/?p=1721)).
- VOID's [Community Resources](https://voidinteractive.net/community-resources/) page points to UE 5.3.2 and the
  community **Community Mapping Framework** (Nexus, mod 1384). It is a template `ReadyOrNot` project with
  Blueprint templates for maps and an automatic packaging tool.
  - Build: cook for Windows → take `Saved/Cooked/Windows/ReadyOrNot/Content` → pack with UnrealPak
    ([guide](https://unofficial-modding-guide.com/posts/mapping_gettingstartedue5/)).
  - Unpacking the game's assets with FModel takes about 100 GB. We do not need it.
- What exactly the CMF contains in C++ (stubs of the `ReadyOrNot` module?) and where it was taken from is not
  publicly described.

Conclusion:
- A Blueprint mod needs UE 5.3.2 and a project named `ReadyOrNot`: then the `/Game/...` and `/Script/ReadyOrNot` paths
  match the game. It also needs a stub module with declarations of the game classes we use.
- We generate the stubs ourselves from our JMAP dump (reflection of the binary). Then we do not depend on the unclear
  origin of the CMF and do not touch leaked sources. About 15 classes are enough.

### The stub module: why it is required

Many functions and properties that HostBrain touches are not visible to Blueprint because of their flags:

| Not `BlueprintCallable` | Properties not writable from Blueprint |
|---|---|
| `ReadyOrNotPlayerController::ReadyUp`, `Server_SetReadyState` | `PlayerState.Team` (read-only) |
| `ReadyOrNotPlayerState::OnRep_Team`, `Server_SetCustomization` | `ReadyOrNotCharacter.DefaultTeam` (protected) |
| `CoopGS::OnRep_CrouchingTigerHiddenDragon` (private) | `CoopGS.bCrouchingTigerHiddenDragon` (private) |
| `NotifyRespawnTime`, `Multicast_BroadcastChatMessage`, `Client_SendChatMessage` | `GameState.TimeTillGameStartCountdown`, `SWATManager.SquadLeader` (read-only) |
| | `CoopGM.SuspectPlayerCustomizationOverride`, `CyberneticController.CombatActivity`, `bSpectateKillerOnDeath` |

- The `BlueprintCallable` and `BlueprintReadWrite` flags are checked only by the Blueprint compiler in the editor.
  - Cooked bytecode refers to `UFunction` and `FProperty` by import path.
  - The VM calls them directly: RPCs through `GetFunctionCallspace`, everything else through `Invoke`.
  - So a stub with the same names and **exactly the same signatures** (from JMAP), but with open flags, lets our
    Blueprint call them.
- Console variables (`a.Ron…`) and `servertravel` are available without a stub too, through
  `KismetSystemLibrary::ExecuteConsoleCommand`. This is exactly the call that Lua uses. The controller's Exec functions
  (`DestroySwatTeam`) should work the same way (to be checked); if not, through the stub.

Check first: that a cooked Blueprint from our project really calls `ReadyUp` through the stub and writes
`PlayerState.Team` in the live game.

## 2. Mod features: what is possible in a pak

"Stub" means that the stub module from the section above is needed. All actions are performed by the MASD actor on the
host unless stated otherwise.

| Feature | In a pak | How |
|---|---|---|
| Team selection and the menu on the pre-mission screen | **Yes** | Our own UMG widget on top of `W_PreMission_C`. Find the class with `LoadClassAsset_Blocking` by path, the screen with `WidgetBlueprintLibrary::GetAllWidgetsOfClass`. Our own buttons and events, no hooks needed (in Lua they broke on `RestartMod`). Team: writing `Team` + `OnRep_Team` (stub). Host readiness: our own button → `ReadyUp` (stub) or the `PC.OnPlayerReadyChange` delegate. Holding the countdown: writing `TimeTillGameStartCountdown` (stub). Clients without the pak pick a team in chat: `GameState.OnChatMessageReceived` (BlueprintAssignable; `RChatMessage` has `SenderPlayerState` and `Message`). On a client with the pak, the same menu is drawn by its local actor, and the choice goes to the host through a standard RPC (chat or `Server_SetTeamType`). |
| Rounds with a mission reload | **Yes** | `ExecuteConsoleCommand("servertravel <map>?game=<mode>")`, in single player `open`. Map: `GetCurrentLevelName`, mode: `GameModeBase.OptionsString`. Score, round and rosters between loads are kept in a `ModPersistentObject` object. Client readiness: `Server_SetReadyState(true)` on the server (stub). Results: our own widget on the host and chat (`SendChatMessage` is BlueprintCallable, broadcasting needs the stub). |
| Takeover of AI suspects | **Yes** | `GetAllActorsOfClass`, `LineTraceSingle`, `K2_TeleportTo`, `K2_DestroyActor`, `ReadyOrNotGameMode::SpawnPlayerCharacter` (all BlueprintCallable). Writing `DefaultTeam`, `Team` + `OnRep_Team`, `NotifyRespawnTime`: stub. Teleport in the pawn's first frame: the actor's tick. Visibility to SWAT: `TargetingComponent::CanCharacterBeSeen` (BlueprintCallable). |
| Suspect loadout and clothes | **Yes** | `BpGameplayHelperLib::EquipLoadoutOnPlayer`, `InventoryComponent::DestroyInventoryItem`, `ReplenishAmmo`, `GetMagazineCount` are BlueprintCallable. Clothes: reading `CoopGM.SuspectPlayerCustomizationOverride` and `Server_SetCustomization(…, true)`: stub. Weapon substitution (AK → SLR-47 and so on): a table in Blueprint. |
| SWAT bots (`a.RonSpawnSwatInIncompatibleMode`, `hb_hunt.lua`) | **Yes** (one thing to check) | The variable has no `ECVF_Cheat` and is set through `ExecuteConsoleCommand`, as now. `DestroySwatTeam` is an Exec function: through the console (to be checked) or the stub. The "hunter": writing `SWATManager.SquadLeader` (stub), `GiveMoveCommand` / `GiveSearchAndSecureCommand`, `CanCharacterBeSeen`, `ScriptedFireAtActor` (BlueprintCallable; reading `CombatActivity`: stub). Player shots instead of the `Server_OnFire` hook: the `BaseMagazineWeapon.OnWeaponFire(Weapon, bServer)` delegate (BlueprintAssignable) on suspect weapons. Check that it fires on the host for clients' weapons. |
| Lobby limit (`EOSMultiplayerStatics::SetMaxPlayers`) | **Partly** | The function is a BlueprintCallable static, called directly. The value lives in the GameInstance subsystem until the game exits. But if MASD really does not fire in the first menu after startup, the first lobby opens with 5 slots. The limit of 10 applies from the next lobby, after any level. |
| The `CoopGS.bCrouchingTigerHiddenDragon` flag | **Partly** | Writing it and `OnRep_*` are possible through the stub. But without the native patch (next row) the flag makes civilians enemies of all AI, and the AI squad kills hostages. **The pak version does not turn the flag on.** Then enemies follow the normal rules: SWAT 1/2/5 against suspects 3, civilians neutral. This is exactly what the patch restores now. We lose three things: spectating and cameras limited to one's own team, suppression of the radio queue, and disabled auto-assignment on join (the latter does not bother us: we set the teams ourselves). Spectating can be partly fixed from the host: return a dead player's camera to a teammate through `PC.Client_SetViewTargetWithBlend` (BlueprintCallable). |
| Native: friend/foe rules (patch of `IsEnemyTeam` / `IsFriendlyTeam`) | **No** | This is a change to machine code. Workaround: do not turn on the flag (row above). |
| Native: filter of suspects' SWAT RPCs | **No** | A server RPC cannot be intercepted from Blueprint. Mitigations (to be checked one by one): without handcuffs in the loadout a suspect cannot arrest; `PlayerCharacter.YelloutEffectRadius = 0` on the suspect's pawn on the host (stub): if the server takes the yell radius from there, the yell affects nobody; resetting `bHasBeenReported` after a report. Nothing can block reports to TOC, orders to civilians and interaction with characters. `bDisableInteraction` would block doors as well. |
| Native: suppressing `Multicast_DisplayScore` | **No** (there is a hypothesis) | A multicast cannot be intercepted from Blueprint. Hypothesis: clear `ScoringManager.ObjectiveScoreGroups` / `PenaltyScoreGroups` on the host (Net, protected: stub), and there will be nothing to award. On clients with the pak the score popups can be hidden in their own HUD. |
| Native: the `Multicast_StopSequence(nullptr)` protection | Not needed | Only the native Firefight and Defusal need it (`comp_start`). Co-op PvP does not hit this path, and those modes are not part of the pak version. |
| Side item: hit validation (`HitRegistrationSettings.bEnableValidation`) | **No** (for now) | This is the CDO or an ini. Blueprint cannot write to a CDO, and replacing `DefaultGame.ini` from a pak is fragile. For now it stays in the UE4SS version only. |
| Side item: the `comp_*` console commands and `settings.txt` | **Yes**, differently | There is no console without UE4SS. Settings go into the menu, storage is `SaveGameToSlot`. |

## 3. Who needs the pak: the host or everyone

Observation (decompilation):
- `ReadyOrNotGameInstance::IsGameModded` (exec `0x1448eb880`) returns the global byte `0x148e0daf0`. It is set by:
  - mounting a mod pak (`0x144ea2060` adds the name to the mod list, `0x144e9c99b`: the list is not empty);
  - finding difficulty files `Difficulties/*.ini` (`0x144becda0`);
  - a check in the code that reads `_worldgen_*.sav` of custom maps nearby (`0x144da341e`).

  UE4SS and the DLL do not touch the flag. The current host with HostBrain is "unmodded".
- **Lobby creation** (`0x144ee465e`): session attribute `MODDED = bAllowModdedPlayers || IsGameModded`.
  `bAllowModdedPlayers` is `GameUserSettings+0x371`, getter `0x144de9c40`. When the settings are saved
  (`0x144b94c90`), the game itself sets `bAllowModdedPlayers = IsGameModded`.
- **Lobby search** (`0x144ee30aa`) filters by `MODDED`:
  - a vanilla client without the toggle sees only lobbies with `MODDED = false`;
  - a modded client sees only lobbies with `MODDED = true`;
  - with the toggle, all lobbies.
- **Joining a lobby** (`0x144ee7570`):
  - `MODDED = false` and the client is modded → "Cannot join session as mods are not allowed.";
  - `MODDED = true` and the client has neither `bJoinModdedServers` (`+0x370`, `0x144deabd0`) nor mods of its own →
    "Cannot join a modded session."
- The values in the user's `GameUserSettings.ini`: `bJoinModdedServers=False`, `bAllowModdedPlayers=False`,
  `bServerSideChecksum=True`. The Settings > Game menu has the toggles `JoinModdedServers` and `AllowModdedPlayers`.
- **"Server Side Checksum" currently has no effect.**
  - The native getter (`0x144deb950`) is called only by the Blueprint wrapper `LoadServersideChecksum`.
  - In the dump, the only Blueprint that calls it is the debug `W_PermanentOverlay`.
  - The ReadyOrNot code has no strings about a pak checksum.
  - Caveats: the dump contains only the Blueprints loaded when it was taken; native code reading the field directly
    is not ruled out. Old Steam complaints about a "pak checksum mismatch" date back to the UE4 era.
- No mechanism in the code was found that would download the host's mods to a client on join.

Conclusion:

| Who installs the pak | Result |
|---|---|
| Only the host | The rules work: the MASD actor exists only on the host, and everything else reaches clients through standard replication, as now. **But every vanilla friend has to turn on "Join modded servers" once**, otherwise the lobby is not visible and an invite gives "Cannot join a modded session". Clients pick a team in chat. |
| Host and clients | The toggle is not needed: the client is modded itself. Its local actor (without authority) can show the team menu and hide the SWAT squad panel on a suspect client, which is now a limitation listed in the README. The pak versions must match for everyone: the actor is not replicated, but the client's menu and the host's rules must understand each other. |
| A client with the pak, a host without it (the current UE4SS host) | Joining is blocked ("mods are not allowed") while the host has `AllowModdedPlayers` turned off. |

The MASD actor is made non-replicated (`bReplicates = false`). Then a client without the pak does not need to know its
class, and the instances on clients with the pak live on their own. Branching is done with `IsServer` /
`IsDedicatedServer` / `HasAuthority`.

## Feasibility check without the editor (27.10.2026)

There is no UE 5.3.2 editor on the machine: the Epic Games Launcher requires a sign-in, and the engine sources are not
available to this GitHub account. So the assets are built directly, without the editor:
- **The `pakmod/kc` compiler.** It writes cooked assets as UAssetAPI JSON: the Blueprint class, functions with Kismet
  bytecode, the CDO and the data asset. Then UAssetGUI 1.1.0 (`fromjson`) turns the JSON into `.uasset`/`.uexp`, and
  `repak` packs them into a V11 pak.
- **Bytecode sizes.** In UE 5.3 memory pointers take 8 bytes, FScriptName 12, offsets 4. The rules were checked
  against 146 functions of four game Blueprints: the total sizes, the `EX_Context` offsets and the jump targets matched.
- **Whether the stub module is needed.** It is not: bytecode refers to `UFunction` and properties by import path, and
  the `BlueprintCallable` and `BlueprintReadWrite` flags are checked only by the editor.

Observation (test pak `pakmod/targets/probe.py` in `Content/Paks/~mods`):
- The game loaded the pak and created the actor from `ModActorSpawnData` **already in the first main menu** after
  startup (the community report that MASD does not fire in the first menu was not confirmed on this build) and again
  in a co-op mission.
- The actor's `ReceiveBeginPlay` ran to the end. Steps:
  - `GetPlayerController` (BlueprintCallable);
  - cast of `PlayerState` to `ReadyOrNotPlayerState`;
  - **writing `ReadyOrNotPlayerState.Team`**, a property that Blueprint can only read: the value became 4;
  - **calling `ReadyOrNotPlayerController::ReadyUp`**, a function that is not BlueprintCallable: it went through
    without errors.
- Name table: the engine stores a name like `Ret_1` as `Ret` plus a number, so the table must contain the base name too.

Conclusion: items 1 and 2 of stage 1 are confirmed on the host; stages 0 and 2 (editor, stubs, graph generator) are not
needed. The logic is written as code and compiled into bytecode.

## Porting the mode (27.10.2026)

Instead of stages 2–3 of the plan below (editor, graph generator), the logic is written in a subset of Python
(`pakmod/src/pvp.py`, about 1000 lines versus 2400 lines of Lua) and compiled by `pakmod/kc/lang.py`.
Classes:
- `BP_PvPDirector` — the actor from `ModActorSpawnData`;
- `BP_PvPState` — a `ModPersistentObjectSubsystem` object: score and teams survive the mission reload;
- `BP_PvPSave` / `BP_PvPLog` — save objects for the settings and the log.

Tested on the host, single player on the campus:
- the team menu on the pre-mission screen, holding the start until «ГОТОВ» (Ready);
- buttons (subscribing to `W_StandardButton_C.OnClicked`), saving the settings to `RoNPvP.sav`;
- the chat command `!suspect` through `ReadyOrNotGameState.OnChatMessageReceived`: the server catches it;
- round start: the suspect host takes an AI's place within 0.1 s, SLR-47 + G19, 10 SWAT items removed, team 3;
- the bot squad starts clearing;
- round end on time: the mission reloads, round 2 starts by itself;
- side swap after round 2 (the host plays SWAT, the score carries over);
- match end (SWAT 3 : 0), «НОВЫЙ МАТЧ» (New match);
- the pak is also picked up from `Content/Paks/mod.io/3791/mods/<id>/`, where the Mods menu puts it;
- if HostBrain (UE4SS) is installed as well, it leaves the mission to the director of the pak version.

Not tested (needs a friend): `servertravel` with clients, client readiness through `Server_SetReadyState`, a vanilla
friend joining a "modded" lobby.

## 4. Recommended plan

**Stage 0. Preparation (2–3 days; needs the user's consent to install UE 5.3.2, about 40–60 GB).**
- A UE 5.3.2 project named `ReadyOrNot`.
- A generator of the `ReadyOrNot` stub module from JMAP: only the classes we need, signatures one to one.
- A script cook → UnrealPak → copy into `Content/Paks/~mods` for testing.

**Stage 1. Feasibility check (2–3 days and one session with a friend).** A test pak with one MASD actor:
1. The actor appears on the host in a co-op mission and in the lobby; whether it appears in the first main menu.
2. Through the stub, `ReadyUp`, writing `PlayerState.Team` + `OnRep_Team`, and `Server_SetCustomization` work.
3. PvP without the `bCrouchingTigerHiddenDragon` flag: damage between players, AI suspects allied with the suspect
   player, civilians alive, what a spectator sees.
4. A friend without the pak joins after turning on "Join modded servers"; `OnChatMessageReceived` on the host catches
   their `!suspect`.
5. Hypotheses: empty score groups give no "+N"; `YelloutEffectRadius = 0` cancels the yell; `OnWeaponFire` fires on
   the host for a client's weapon.

Criterion: if items 1–4 pass, we build the pak version. If item 2 fails, then without stubs we lose takeover, teams,
clothes and readiness, and the pak version makes no sense: we stay with the installer.

**Stage 2. Building Blueprints without a GUI (1–2 weeks).** The user did not allow screen control, and an agent cannot
assemble Blueprint graphs by hand in the editor. We need our own editor plugin or commandlet that builds graphs from a
text description (importing nodes in UE's text copy format or creating `K2Node`s directly). The upside is that the
source of the logic stays as text in git and can be reviewed.

**Stage 3. Porting the logic (3–4 weeks).** About 3,100 lines of Lua (`hb_pvp`, `hb_menu`, `hb_loadout`, `hb_hunt`,
`hb_common`, `main`; `hb_solo` is not needed, the PvP menu replaces it) move into `BP_PvPDirector`, the menu widget and
the match state object. Order: menu and teams → rounds → takeover and loadout → bots → lobby limit.

**Stage 4. Publishing (about a week).** The checklist with a friend ([pvp-playtest.md](pvp-playtest.md)), a mod.io
page with instructions about the "Join modded servers" toggle. Publishing only with the user's consent.

In total, about 6–9 weeks to a pak version without the native parts. The main risks:
- no official SDK;
- the first menu without MASD;
- game updates that change signatures, after which the stubs have to be rebuilt.

## Recommendation

**Build the pak version: yes, but only after stages 0–1.** Scope:

- **Included ("PvP Lite", only the host installs it):**
  - the team menu on top of the pre-mission screen;
  - team selection by clients through chat;
  - rounds with a mission reload and a side swap;
  - takeover of AI suspects;
  - suspect weapons and clothes;
  - SWAT bots and the "hunter";
  - lobby limit of 10 (with the caveat about the first lobby).
- **Changed:** the hidden PvP flag is not turned on. Civilians are neutral under the standard rules; spectating limited
  to one's own team is partly fixed from the host.
- **Not included:**
  - the SWAT RPC filter — only mitigations: no handcuffs, a yell without effect;
  - score suppression — if the hypothesis is not confirmed;
  - hit validation;
  - the native Firefight and Defusal.
- **Cost for players:** each friend has to turn on "Join modded servers" once or install the pak themselves. With the
  pak, the client also gets its own team menu.

The current UE4SS installer remains as the variant with strict rules. Once the pak version works, the UE4SS part should
be cut down to an add-on on top of the pak: only the native protections from `RonCompNative`, with all the logic in
Blueprint. Then there will be a single codebase.
