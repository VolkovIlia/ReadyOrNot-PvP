# Находки реверса

Каждая запись: **наблюдение** (что видно напрямую), **вывод** (что из этого следует), **неизвестно** (что ещё проверить).
Если находка получена через REA, рядом указывается Evidence ID.

## Инструменты
- **REA** (`npx rea-agents@6.8.0`) с провайдером Ghidra: `GHIDRA_INSTALL_DIR=%USERPROFILE%\Tools\ghidra_12.1.4_PUBLIC`,
  `JAVA_HOME=C:\Program Files\Eclipse Adoptium\jdk-21.0.12.101-hotspot` (заданы в пользовательских переменных Windows;
  MCP-сервер увидит их после перезапуска клиента). `rea doctor --client claude_code` — Ghidra healthy.
- **Точечная декомпиляция без полного автоанализа** (полный анализ exe на 150 МБ занимает часы):
  `pwsh -File tools/ghidra_decompile.ps1 -Out %USERPROFILE%\Tools\ron_re\out -Depth 1 0x1449a06e0 dis:0x142a52df0:12`.
  Проект Ghidra и копия exe живут в `%USERPROFILE%\Tools\ron_re` (лаунчер Ghidra не переносит пробелы и скобки в путях).
- **Откуда брать адреса:** `.pdata` (границы функций), поле `func` у UFunction в JMAP (exec-обёртки),
  слоты vtable из поля `vtable` у CDO в JMAP (реализации `_Implementation`), `re/annotate_strings.py` подставляет строки.

## Установка игры (25.10.2026)

Наблюдение:
- Путь: `C:\Program Files (x86)\Steam\steamapps\common\Ready Or Not`.
- Исполняемый файл: `ReadyOrNot/Binaries/Win64/ReadyOrNotSteam-Win64-Shipping.exe` (154,5 МБ, сборка от 07.10.2026).
  Version info пустая.
- Рядом лежит `RedpointEOS/EOSSDK-Win64-Shipping.dll`: сессии идут через плагин Redpoint EOS Online Framework.
- Паки: `pakchunk0..24, 99-Windows.pak` + `.sig`. Файлов `.utoc`/`.ucas` нет.
- `Manifest_UFSFiles_Win64.txt` — список всех 467 100 файлов в паках. Позволяет искать ассеты без распаковки.
- `GameFeatures`-плагины DLC: `ReadyOrNot/Plugins/GameFeatures/ReadyOrNotDLC2/...`.

Вывод:
- Формат — классический pak, а не IoStore. Сборка мода: cook → UnrealPak (`*_P.pak`), retoc не нужен.
- Паки подписаны (`.sig`), но pak-моды через mod.io и `~mods` работают — подпись для модов, судя по всему, не проверяется.

Неизвестно:
- Точная версия движка (5.3.x) — проверить по строкам exe через REA.
- Требует ли загрузчик модов `.sig` для мод-паков.

## Остатки PvP в игре (S3, предварительно)

Наблюдение (по манифесту файлов):
- `Content/Blueprints/Games/` содержит пары GameMode/GameState для PvP-режимов:
  - `GM_Defusal` / `GS_Defusal`, `GM_TDM` / `GS_TDM` + `HUD_TDM`, `GM_Firefight` / `GS_Firefight`;
  - `GM_VIPEscort` / `GS_VIPEscort` + `HUD_VIPEscort`, `GM_ArrestAndRescue`, `GM_CaptureTheFlag` + `HUD_CaptureTheFlag`;
  - `GM_GunGame`, `GM_KingOfTheHill`, `GM_TugOfWar`, `GM_Incrimination`, `GM_Commander`, `GM_FreeMode`.
- Ко-оп режимы: `GM_COOP` и `COOPModes/GM_COOP_{ActiveShooter,BarricadedSuspects,BombThreat,HostageRescue,Raid}`.
- Таблица настроек режимов: `Content/Blueprints/DataTables/GameModeSettingsDataTable`.
- PvP-интерфейс:
  - `Blueprints/Gameplay/Defusal/W_DefusalBuyMenu` — **меню закупки для Defusal**;
  - `Widgets/GameModeRound/W_PVP_RoundEnd`, `Widgets/Menus/W_MissionEnd_PVP`;
  - `Widgets/TeamSelection/W_TeamSelection` (+ `W_TeamSelectionPlayerListEntry`);
  - `Widgets/Common/W_Scoreboard*`, `Widgets/HUD/Tablet/W_Scoreboard_V2`.
- PvP-данные: `ReadyOrNot/Data/DT_ActorsToHandleInPvP`, `Data/Interactions/Multitool_Free_PvP`, `Zipcuff_PvP_Arrest{1,2,3}`,
  `Localization/Game/en/loc_PvP`.
- Играбельный подозреваемый (MLO):
  - руки от первого лица `Character/MLO/ron_suspect_fp_player_mlo`, `ron_suspect_fp_player_heavy_v1`;
  - материалы `PVP__MI_MLO_ARMOR_BA`, `PVP__MI_MLO_BODY_BA`;
  - фракция `Blueprints/AI/FactionManagers/Faction_MLO`.
- Бомба: `Blueprints/Gameplay/COOP/BP_BombActor`, `BP_BombActor_v2`; взаимодействия `Data/Interactions/DisarmBomb_DisarmA/B`.
- PvP-анимации: арест (`PVP_Arrest_V2`), MVP-эмоции (`Animations/TP/mvp/...`), `LS_PVP_Afteraction_Win`.

Вывод:
- В игре почти целиком лежит каркас CS-подобного режима: Defusal с меню закупки, выбор команды, таблица счёта,
  экран конца раунда, играбельные подозреваемые. Основной путь — оживить `GM_Defusal`/`GS_Defusal`
  и нарастить правила CS2 в HostBrain, а не писать всё с нуля.

Неизвестно:
- Логика нативных классов (см. ниже) — нужен SDK-дамп и REA.
- Работает ли `?game=` в URL перехода.

## Нативный PvP-код в exe (S3, строки exe)

Метод: скан ASCII/UTF-16 строк `ReadyOrNotSteam-Win64-Shipping.exe`
(скрипт в scratchpad, полный вывод не коммитится). Это статические строки, а не наблюдение выполнения.

Наблюдение:
- Нативные классы: `ADefusalGM`, `ADefusalGS`, `AFirefightGM`, `AFirefightGS`, `AVIPEscortGM`, `AVIPEscortGS`,
  `AReadyOrNotGameMode_PVP`, `APVPTriggerBox`, `UMissionEndPvPWidget`, `URoundEndWidget_PVP`.
- Состояния Defusal: `EDefusalMatchSate::{DMS_Warmup, DMS_PreRoundTimer, DMS_Playing, DMS_HalfTime, DMS_MatchFinished}`,
  свойства `DefusalMatchState`, `DefusalHudClass`, `IsInDefusalWarmup`, `Defusal_SuspectSpawn`, `bPVPBombOnly`.
- Общее состояние PvP: `EPvPState::{PVPS_Off, PVPS_TeamSelection, PVPS_RoundStarting, PVPS_RoundInProgress,
  PVPS_RoundEnding, PVPS_RoundFinished, PVPS_BetweenRounds, PVPS_End}`.
- События PvP: `EPVPEvent::{PlayerKilled, PlayerArrested, PlayerFreed, KillConfirmed, VIP*, Flag*, Intel*, ...}`.
- **Консольные переменные:**
  - `a.Ron.PVP.Unlock` — «Unlocks PvP mode.»;
  - `a.Ron.PVP.Start` — «Starts PvP match if called on the host.»;
  - `a.Ron.PVP.MinTeams` — «How many teams are required to enter PvP.»;
  - `a.Ron.PVP.SpawnAtTheSameLocation`, `a.Ron.PVP.ForceRespawnAsSpectatorWhenKilled`.
- Секретный режим и меню: `IsSecretPvP`, `IsSecretPvPUnlocked`, `ShowPVPUnlockedVisual`, `IsPvPSupported`, `bSupportsPvP`,
  `bEnableFindSessionPVPButton`, `FindPVPSessionBtn`, `bPVPSession`.
- Оружие по командам: `RedPVPUniquePrimaryWeapons`, `BluePVPUniquePrimaryWeapons`;
  внешний вид: `bOverrideSuspectCustomizationInPvp`.
- RPC: `Multicast_HandlePvPActors`, `Server_PlayPVPSpeech`, `CoopGS::HandlePvPActors`.

Вывод:
- PvP-режимы не вырезаны из кода, а **спрятаны за флагом разблокировки** («secret PvP»). Defusal в нативном коде
  уже умеет разминку, отсчёт перед раундом, раунды, перерыв и конец матча — почти как CS.
- Самый короткий путь к S3: у хоста выполнить `a.Ron.PVP.Unlock 1`, затем `a.Ron.PVP.Start`.
  В Shipping консоль обычно закрыта, поэтому команду должен выполнить HostBrain (UE4SS)
  через `UKismetSystemLibrary::ExecuteConsoleCommand` или `IConsoleManager`.

Неизвестно:
- Насколько Defusal рабочий сегодня (моды Fire Fight и PvP Revival сообщают о крашах и поломках).

## Прогон в игре с RE-UE4SS (26.10.2026)

Окружение: RE-UE4SS experimental `v3.0.1-1183-gcdbc0b66` (`tools/install_ue4ss.ps1 -Dev`), зонд `HostBrain/ue4ss-mods/RonCompProbe`.
Сырые логи и дампы: `re/dumps/` (не коммитятся).

Наблюдение (UE4SS.log):
- Движок **5.3.2 Shipping**. UE4SS нашёл GUObjectArray, GMalloc, FName, StaticConstructObject, GNatives, ProcessEvent.
  Не нашёл `ConsoleManagerSingleton` (два кандидата: `7FF67D76A7C0`, `7FF681DA2FD0` при базе `0x7ff67cc10000`).
- Главное меню: `MainMenu_V2`, `BP_MenuGameMode_C`, `ReadyOrNotGameState` (`MatchState=2`, `bPvPMode=false`).
- Консольные переменные читаются через `KismetSystemLibrary::GetConsoleVariableIntValue`:
  `a.Ron.PVP.MinTeams=2`, `a.Ron.PVP.ForceRespawnAsSpectatorWhenKilled=1`, `SpawnAtTheSameLocation=0`;
  `Unlock`/`Start` возвращают 0 — вероятно, это команды, а не переменные.
- `ExecuteConsoleCommand("a.Ron.PVP.MinTeams 1")` **не меняет значение**, `a.Ron.PVP.Unlock 1` и `a.Ron.PVP.Start`
  видимого эффекта не дают ни в меню, ни в лобби. При этом `open <map>?listen` через тот же вызов работает.
- `open RoN_Station_MultiplayerLobby?listen` загружает лобби с `GM_COOP_BarricadedSuspects_C` / `GS_COOP_BarricadedSuspects_C`
  (`PvPState=0`), но экран остаётся чёрным — в обход меню не хватает параметров сессии/режима.
- `HighResShot 1` сохраняет PNG в `ReadyOrNot/Ready Or Not/Saved/Screenshots/` — так можно смотреть на игру без управления экраном.

Наблюдение (JMAP-дамп рефлексии, 49 429 объектов):
- `ReadyOrNotFunctionLibrary::IsSecretPvPUnlocked() -> bool` (static, без параметров), `IsSecretPvP(WorldContext) -> bool`,
  `IsInDefusalWarmup() -> bool`; `BpGameplayHelperLib::IsPvPSupported(FLevelDataLookupTable) -> bool`.
- Иерархия: `GM_Defusal_C` → `DefusalGM` → `ReadyOrNotGameMode_PVP` → `ReadyOrNotGameMode` → `GameModeBase`.
  - `ReadyOrNotGameMode_PVP`: `RoundWonTeam(ETeamType)`, `RoundWon`, `RoundEnd`, `NextRound` [Exec], `MatchEnd`,
    `CheckRoundEnd` [BP event], `TimelimitReached`, `Multicast_SetWinningTeam`, `RoundEndResetDelay`, `MatchEndResetDelay`.
  - `ReadyOrNotGameMode`: `StartMatch`, `SetMatchState`, `SwapPlayerTeams`, `RespawnAllPlayers(OnTeam)`, `RespawnPlayer`,
    `RespawnDeadPlayers`, `IsTeamDead(Team, bIncludeArrestedAsDead)`, `SpawnPlayerCharacter`, `SpawnSpectator`,
    `MinimumPlayersToStart`, `RespawnMode`, `bCanRespawn`, теги стартов `SWATRedStartTag`/`SWATBlueStartTag`/`SuspectStartTag`.
  - `DefusalGM`: `SelectedBombActor`, `SwatSpawn`, `SuspectSpawn`, `SpawnPoints[AISpawn]`, `SuspectSpawnData`, `SuspectFPArmsOverride`.
  - `DefusalGS`: `DefusalMatchState`, `CountdownUntilMatchStarts`, `ElapsedRoundTime`, `BombTimeRemaining`.
  - `ReadyOrNotGameState` (реплицируется всем): `RedTeamWins`, `BlueTeamWins`, `RoundsPlayed`, `RoundsToPlay`,
    `RoundTimeRemaining`, `RoundWinningTeam`, `MatchWinningTeam`, `TeamPlayers`, `bPvPMode`, `ModeURL_Replicated`,
    `Multicast_OnRoundReset`.
- Команды: `ETeamType::{TT_NONE, TT_SERT_RED, TT_SERT_BLUE, TT_SUSPECT, TT_CIVILIAN, TT_SQUAD}`.
- **Алиасы режимов** (`GameMapsSettings.GameModeClassAliases`): `RR_PVP` → `GM_Defusal`, `ff` → `GM_Firefight`,
  `tdm`, `vip`, `aar`, `koth`, `ctf`, `tow`, `gungame`, `Incrim`, `free`, `lobby`, `coop`, `*_COOP`, `commander`.
  Игра сама строит URL вида `?game=lobby`, `?game=coop`, `?game=commander?save=`, `?Listen?Port=`.

Вывод:
- `a.Ron.PVP.*` — скорее всего cheat-переменные/команды (`ECVF_Cheat`): в Shipping через консоль не меняются.
  Если понадобятся, HostBrain выставит их напрямую через `IConsoleManager` (C++), выбрав верный из двух кандидатов синглтона.
- Они и не обязательны: **Defusal запускается штатным алиасом `?game=RR_PVP`**, а нативный каркас раундов и реплицируемый
  счёт уже есть в `ReadyOrNotGameMode_PVP`/`ReadyOrNotGameState`. HostBrain может вызывать эти функции и писать эти поля,
  а клиенты увидят результат в существующем PvP-интерфейсе игры — объём нашего pak сильно сокращается.

## Запуск Defusal через `?game=RR_PVP` (S3 подтверждён, 26.10.2026)

Метод: удалённая консоль зонда (`inbox.lua`), из главного меню `open RoN_Campus_Core?listen?game=RR_PVP`.

Наблюдение:
- `ReadyOrNotFunctionLibrary::IsSecretPvPUnlocked()` = false, `IsSecretPvP(World)` = false, `IsDMOPVPOnly()` = false.
- Через ~25 с загрузилась карта `RoN_Campus_Core` (Watt Community College) с **`GM_Defusal_C` + `GS_Defusal_C`**:
  `bPvPMode=true`, `ModeURL_Replicated=RR_PVP`, `RoundsToPlay=8`, `DefusalMatchState=0` (Warmup),
  `MinimumPlayersToStart=1`, `GameStartWaitTime=10`, `RespawnMode=NoRespawn`.
- Игрок заспавнен как `BasePlayer_C` (вид от первого лица), команда `2` = `TT_SERT_BLUE`.
- `DefusalGM` сам выбрал бомбу `BP_BombActor_v2` (`RoN_Campus_BarricadedSuspects` → `BP_BombActor5`) и спавн SWAT `PlayerStart_1`.
  `SuspectSpawn` невалиден — на этой карте нет отдельного спавна подозреваемых-игроков.
- В разминке тикают `BombTimeRemaining` (192 → 145 за 47 с) и `RoundTimeRemaining`; `DefusalMatchState` остаётся 0.
- После `PC:ReadyUp()` состояние не изменилось. `IsInDefusalWarmup()` = false, хотя `DefusalMatchState` = 0.
- На экране осталось одноразовое окно первого запуска `W_DLC_Acknowledgement_C` (дерево `W_MainMenu_V3_C`);
  `RemoveFromParent`/`SetVisibility` его не скрывают — закрывается кнопкой «Подтвердить».

Вывод:
- **Скрытый Defusal запускается штатно, без подмены ассетов и без cheat-переменных**: хосту достаточно перейти на карту
  с `?listen?game=RR_PVP`. Точка входа HostBrain — команда `comp_start <карта>`, собирающая такой URL.
- Спавн подозреваемых придётся задавать нам (данные карт `data/maps/*.json`), как и предполагал план.

**Вылет при истечении таймера бомбы в разминке** (00:44:59, ровно когда `BombTimeRemaining` дошёл до 0; один игрок, команда SWAT):
- `EXCEPTION_ACCESS_VIOLATION reading address 0x2d8` — разыменование нулевого указателя (поле со смещением 0x2D8).
- Верх стека: `ReadyOrNotSteam-Win64-Shipping+0x2a52df0` ← `+0x4ec77dc` ← `+0x48f34a9` ← … ← `UE4SS+0x466cb5` (хук ProcessEvent) ← тик движка.
  За секунду до вылета CheatManagerEnabler сообщил о новом PlayerController — шёл сброс раунда.
- Минидамп и логи: `re/dumps/crash-defusal-bomb-timer/`, `re/dumps/UE4SS-run2.log`, `re/dumps/probe-run2.log`.
- **Причина установлена декомпиляцией** (Ghidra 12.1.4, `tools/ghidra_decompile.ps1`; адреса — статические VA при базе 0x140000000):
  - Кадры сопоставлены с функциями по `.pdata` и указателям UFunction из JMAP:
    `0x142a52df0` — листовой геттер `ALevelSequenceActor::GetSequencePlayer` (`MOV RAX,[RCX+0x2D8]`, `RCX = nullptr`);
    `0x144ec77d0` — `AReadyOrNotGameState::Multicast_StopSequence_Implementation` (слот vtable `+0x850`, сверено с CDO);
    `0x1448f3430` — exec-обёртка `Multicast_StopSequence(ALevelSequenceActor* SequenceActor)`;
    `0x1448f0b40` — нативная заглушка, вызывающая `ProcessEvent`.
  - `0x144ec87e0` — сброс раунда в `ReadyOrNotGameMode_PVP`: берёт GameState (`this+0x300`) и **безусловно вызывает
    `GameState->Multicast_StopSequence(nullptr)`**, затем сбрасывает таймер `GS+0x694`, ставит `MatchState` (`GS+0x7C0`) = 2 и т.д.
  - Вызывается из `0x144c37620` (переопределение в `DefusalGM`: при `RoundsPlayed(+0x768) == RoundsToPlay(+0x76C) - 1`
    уходит на перерыв, уничтожает подобранные предметы через `AActor::Destroy`, затем `Super`),
    а тот — из `0x144ed8b50` (`Super::Tick` режима): в состоянии `this+0x4F8 == 2` таймер `GS+0x694` уменьшается,
    и на нуле вызывается виртуальный `+0x9C8`. Всё это внутри `0x144c4e630` — `DefusalGM::Tick`
    (по `this+0xA48 = SelectedBombActor` пишет `BombTimeRemaining` в `GS+0x988`, при состоянии бомбы 2/3 вызывает `RoundWonTeam`).
- **Вывод:** любой переход Defusal к новому раунду гарантированно падает: `Multicast_StopSequence(nullptr)` не проверяет нуль.
  Multicast выполняется и на клиентах, поэтому падали бы все.
- **Решение для HostBrain** (только хост):
  - не запускать нативный сброс раунда PvP — HostBrain сам ведёт раунды (`RespawnAllPlayers`, сброс бомбы, счёт в GameState);
  - дополнительно перехватить нативную заглушку `Multicast_StopSequence` (детур по сигнатуре) и пропускать вызов с `nullptr`
    **до** `ProcessEvent`, чтобы RPC вообще не ушёл клиентам.

Неизвестно:
- Что переводит Defusal из разминки в `DMS_PreRoundTimer` (вероятно, `a.Ron.PVP.MinTeams=2` — нужны две команды).
- Как меню строит полный URL хостинга с сессией EOS: голый `open RoN_Station_MultiplayerLobby?listen` даёт чёрный экран в лобби.

## Нативный Firefight через HostBrain (26.10.2026)

Метод: HostBrain v0 (Lua + `RonCompNative.dll`), команды через удалённую консоль зонда.

Наблюдение:
- `RonCompNative`: в `.text` 111 заглушек вида «событие с одним указателем», ровно одна — с FName `Multicast_StopSequence`
  (ComparisonIndex 67594 в этом запуске), по адресу `exe+0x48f0b40` — тот же адрес, что найден статически. Детур установлен.
- `comp_start campus ff` → `RoN_Campus_Core?listen?game=ff` → `GM_Firefight_C` + `GS_Firefight_C`, `bPvPMode=true`,
  `RoundsToPlay=2`, `RespawnMode=ImmediateRespawn`, `RoundEndResetDelay=5`, `MatchEndResetDelay=10`; игрок — команда 2 (SERT_BLUE).
- Сначала экран «Перед заданием» с кнопкой «Готовы» (`MatchState=MS_Warmup`). После `PlayerController::ReadyUp()` —
  `MS_Playing`, на карте от первого лица (скриншот).
- Один игрок: красные пусты → раунд сразу засчитан синим (`MS_RoundEnded`, `BlueTeamWins=1`). Сам следующий раунд
  не начинается (ждёт вторую команду); `ReadyOrNotGameMode_PVP::NextRound()` → раунд 2 → 2:0 → конец матча →
  через 10 с перезапуск в разминку со счётом 0:0. **Вылетов нет**; путь Firefight `StopSequence(nullptr)` не вызывает.
- `EMatchState`: `MS_None, MS_Warmup, MS_Playing, MS_RoundEnded, MS_MatchEnded, MS_GoingToNextLevel`.

Вывод:
- Нативный Firefight работает «как задумано» и без наших правок; HostBrain нужен для запуска, проверки попаданий
  и страховки. Защита `StopSequence` остаётся для Defusal (там вызов `nullptr` подтверждён вылетом).

- **Совместимость карт и режимов.** `BpGameplayHelperLib::GetMapDetailsFromName(Map)` → `FLevelDataLookupTable`
  (есть поле `SupportedGameModes`), `IsPvPSupported(row)` = **false для всех 30 карт** — официально PvP нигде не включён.
  Работает: `RoN_Campus_Core` + `ff`, `RoN_Campus_Core` + `RR_PVP`.
  Не работает: `RoN_Valley_Core` + `tdm` → `LowLevelFatalError: Couldn't spawn player: Could not find a starting spot`
  (у TDM свои точки старта команд, на карте их нет; дамп `re/dumps/crash-valley-tdm/`).
  HostBrain пускает только проверенные пары, остальные — с `force`.
- **Путь `StopSequence(nullptr)` бывает и во Firefight**: в одном из запусков через ~20 с после загрузки кампуса стек
  прошёл `144ed8b50+0x109 → 144ec87e0 → заглушка` (возврат `+0x4ec884a`).
- **Урок: `RestartMod` не снимает хуки Blueprint-функций** (27.10.2026). В логе перезапуска есть
  «Unregistering hook» только для нативных функций. Скриптовые хуки (`Registered script hook` на
  `W_PreMission_C:SwapTeams`, `W_StandardButton_C:OnClicked_Derived`) остаются и указывают на Lua-состояние,
  которого уже нет. Клик по кнопке после перезапуска повесил игру: игровой поток стоял в UE4SS в `get_lua_state`
  внутри цепочки `ProcessEvent` → `ProcessInternal` → скриптовые хуки (минидамп снят своим `hangdump.py`,
  раскрутка — `unwind.py`). В обычной игре мод не перезапускается; при разработке после первого экрана подготовки
  игру перезапускаем целиком.
- **Урок: `RestartMod` выгружает DLL.** При перезапуске Lua-мода Lua закрывает состояние и через `__gc` библиотеки
  `package` вызывает `FreeLibrary` для всего, что загружено `package.loadlib`. Патч в игре остался и прыгнул в пустую
  память → вылет «в tier0_s64» (`re/dumps/crash-after-restartmod/`). Исправлено: `RonCompNative` закрепляет себя
  (`GET_MODULE_HANDLE_EX_FLAG_PIN`) при первом вызове; статус в логе привязан к токену сессии из ini.
- **Урок: `_wfopen_s` открывает файл без разделения доступа.** Пока лог кто-то читал (забытый `tail -F`, PowerShell
  `Select-String -Quiet`), запись DLL молча не проходила (`errno 13`, `ERROR_SHARING_VIOLATION`), и Lua не видел ответа.
  Исправлено: лог открывается через `_wfsopen(..., _SH_DENYNO)`, ошибки открытия пишутся в `%TEMP%\RonCompNative_debug.log`.

- **Защита в деле** (02:05–02:08): за 2 минуты Firefight на кампусе игра трижды вызвала `StopSequence(nullptr)`
  (02:06:33, 02:07:08, 02:07:47) — все три перехвачены, игра жива. Без защиты это три вылета у всех игроков.
- **`open <map>?listen` в RoN сервер не поднимает:** и в меню, и после такого перехода
  `KismetSystemLibrary::IsStandalone = true`, `World.NetDriver` отсутствует. Игре нужна онлайн-сессия (EOS/Redpoint),
  которую создаёт меню «Игра по сети». Поэтому для игры с людьми: хост создаёт лобби через меню, затем `comp_start`
  видит сервер и делает `servertravel <map>?game=<mode>` для всех. Программное создание сессии — следующая задача
  (в рефлексии на поверхности только `CreateSessionCallbackProxy::CreateSession` и хостинг Mission Builder).

Неизвестно:
- Как Firefight ведёт себя с людьми в обеих командах (нужен второй игрок): выбор команды, спавн подозреваемых, раунды.
- Какие ещё карты годятся для `ff`/`tdm` — нужен автоматический перебор с перезапуском после вылетов.
- Как игра создаёт EOS-сессию лобби (чтобы HostBrain мог поднимать её сам).

## Игрок за подозреваемых против ИИ SWAT (боты, 26.10.2026)

Наблюдение:
- Exec-функции разработчиков `ReadyOrNotPlayerController::SpawnBotsForGame`, `SpawnAI`, `StartSwatAutomation`
  в Shipping пустые (декомпиляция: заглушки). Живы `SpawnRandomAI(Count)` («Spawn AI Console Command») и
  `SpawnAIAtLocation` (не проверялась).
- Ко-оп `RoN_Campus_Core?game=BS_COOP` из меню: отряд ИИ SWAT (4× `CyberneticsSwat_V2_C` + 4× `CyberneticsSwatTrailer_C`,
  команды 1/2), 5 подозреваемых (`TT_SUSPECT`), 9 гражданских; игрок — команда 2.
- `ReadyOrNotPlayerState::SetTeam(3)` команду не меняет. Работает прямая запись `PlayerState.Team = 3` +
  `Character.DefaultTeam = 3` (+ `OnRep_Team`): `CyberneticController::IsCharacterEnemy(player)` становится true у SWAT
  и гражданских и false у подозреваемых.
- Отряд SWAT без приказов пассивен и продолжает следовать за игроком (он их лидер). После урона от игрока
  (`GameplayStatics::ApplyDamage`) `GetTrackedTarget()` = игрок, все целятся в него (скриншот).
- При переходе из идущей миссии появляется предмиссионный экран `W_PreMission_C`. `ReadyOrNotPlayerController::ReadyUp()`
  его проходит: `PlayerState.bReady` становится true примерно через 4 с после вызова, затем идёт штатный отсчёт
  `GameState.TimeTillGameStartCountdown` 10 → 0, и игрок появляется (READYWATCH-лог, 26.10.2026). Повторный вызов
  через 3,5 с готовность не сбрасывает.

- **ИИ SWAT по игроку-подозреваемому сам не стреляет**, даже когда тот убивает бойцов: у живых бойцов
  `IsCharacterKnownEnemy(player)=true`, игрок в `TargetingComponent.KnownEnemies`, `GetTrackedTarget()=player`,
  активность `SwatCombatActivity` — но правила огня его не пропускают. `CyberneticsSwatTrailer_C` — не бойцы
  (списки целей пусты). Обход: `BaseCombatActivity::ScriptedFireAtActor(player, t, bOverrideTarget=true, accuracy, false)` —
  двое видевших бойцов убили игрока за 3,5 с (160 → 0). HostBrain раз в 0,5 с отдаёт короткие очереди тем, кто видит игрока.

Вывод: HostBrain `comp_play_suspect <карта>` — спавн как SWAT (у ко-оп карт нет точек старта подозреваемых),
затем переход в `TT_SUSPECT` и телепорт к ИИ-подозреваемым; после смерти команда временно возвращается в SWAT.
`comp_alert` натравливает SWAT. Внешность остаётся SWAT — модель MLO ещё не подставлена.

### Раунды против ИИ SWAT (26.10.2026)

Сообщения на экран хоста (проверено скриншотами, кириллица отображается):
- `W_HumanCharacter_HUD_V2_C::AddObjectivePopup(FText)` — строка внизу по центру.
- `AddToast(FString)` — плашка слева.
- `AddScorePopup(FText, int, bool)` — «… +N».
- `PlayerCharacter::Client_SendToast` и `ReadyOrNotGameState::Multicast_BroadcastChatMessage` возвращают ok, но ничего не видно.
- Экран смерти («БОЕЦ УБИТ») закрывает HUD, поэтому итог раунда повторяется после перезагрузки миссии.
- Пешка после смерти — `DeadSpectator_C`, до спавна — `SpectatorPawn`.

Приказы отряду:
- Сначала `SWATManager.SquadLeader` = живой `CyberneticsSwat_V2_C`; без этого отряд следует за игроком-лидером.
- Дальше приказы с `TeamType = TT_SQUAD (5)`.
- `GiveMoveCommand(5, точка)`: 39 → 19 м по прямой за 30 с. В HUD отряда отображается «Идти к».
- `GiveSearchAndSecureCommand(5, точка, false)`: зачистка комнат («Исключить, зачистить», «Осмотр: угол»), к цели 49 → 46 м за 20 с.

Знания бота об игроке:
- `CyberneticController::IsCharacterKnownEnemy`;
- `TargetingComponent::CanCharacterBeSeen` / `GetLastKnownEnemyPosition`;
- `CyberneticController::GetHeardActorInstigator`;
- `HasBeenExposedToAggressiveNoise(sec, dist, mask)`;
- выстрелы идут через RPC `BaseMagazineWeapon::Server_OnFire` и `Multicast_OnFire`. HostBrain перехватывает их,
  чтобы отметить место выстрела игрока.

Снаряжение (`BpGameplayHelperLib::EquipLoadoutOnPlayer`):
- **Оружие ИИ-подозреваемых (`/Game/Blueprints/Items/WeaponsSuspect/*`) игроку давать нельзя.** Магазинов у него нет.
  Если достать подозреваемый пистолет (`Secondary_S_Python` и др.), ломается анимация от первого лица, игрока
  выбрасывает с карты, он погибает (`DeadSpectator_C`).
- Оружие игрока из `/Game/Blueprints/Items/WeaponsRevised` с `PrimaryAmmoSlotsCount = -1` / `SecondaryAmmoSlotsCount = -1`
  получает штатные магазины: AK-103 — 4×30, P99 — 3×15. Так же устроены 8 случайных наборов
  `Default__GM_Firefight_C.RandomLoadouts`, но это наборы SWAT.
- В `PlayerState.ServerSavedLoadout` у ко-оп игрока явные слоты: `556x45FMJ` ×5, `PrimaryAmmunition = Null_AmmunitionAttachment_C`.
- Броня снимается. Гранаты и тактические устройства из предмиссионного набора остаются, даже если в наборе
  `GrenadeSlotsCount = 0`.
- Оружие игрока в стиле подозреваемых: `Primary_AK102`, `Primary_AK103`, `Primary_SLR47`, `Primary_Saiga12`,
  `Primary_G3A3`, `Primary_FAL`, `Primary_870mcs`.

Прочее:
- В UE4SS функция, возвращающая TArray (`InventoryComponent::GetInventoryItems`), отдаёт Lua-таблицу.
  Свойство `InventoryItems` — TArray с `ForEach`.
- Телепорт через `K2_SetActorLocation(..., bTeleport=true)` без проверки может поставить игрока в стол или стул.
  `AActor::K2_TeleportTo` отказывает или выталкивает из пересечения: из застрявшей позиции сдвинул на 76 см.
  HostBrain дополнительно проверяет трассировками `LineTraceSingle`, что подозреваемый видит точку и под ней есть пол.

Внешность подозреваемого (не сделано, зацепки):
- `ReadyOrNotCharacter::UpdateOverridesFromCharacterLookOverrideDataTable(LookOverride)` (Exec) применяет строку
  таблицы образов.
- Реплицируемые `Rep_CharacterLookOverride` (FString, `OnRep_CharacterLookOverride`) и `Rep_FPMesh`.
- Структура `CharacterLookOverride` содержит `FPMeshOverride`. У ко-оп игрока `SavedLoadout.CharacterLookOverride = "SWAT_Judge"`.
- `BpGameplayHelperLib::GetCharacterLookOverrideDataTable()` в ко-оп миссии вернул `nil`: таблица не загружена.
  `Default__GM_Defusal_C.CharacterLookMap` пуст.
- Ассеты играбельного подозреваемого: руки `Character/MLO/ron_suspect_fp_player_mlo`, материалы `PVP__MI_MLO_*`,
  флаг анимации `ReadyOrNotAnimInstance.bIsTeamMLO`.

## Краш через ~2 ч игры: Lua из двух потоков (26.10.2026)

Наблюдение:
- Отчёт `%LOCALAPPDATA%\ReadyOrNot\Saved\Crashes\UECC-Windows-8BF10F...`: `EXCEPTION_ACCESS_VIOLATION reading 0xa`.
  Стек в `CrashContext.runtime-xml` без символов бесполезен.
- В Shipping нет своего лога, а `UE4SS.log` к моменту краша (12:43) не менялся почти 2 часа.
- Раскрутка минидампа по `.pdata` / `UNWIND_INFO` модулей с диска (скрипт `unwind.py` в рабочей папке сессии).
  Главный поток игры:
  1. тик движка (`exe+0x365f185`);
  2. обработчик игровых задач UE4SS (`UE4SS.dll+0x466c40` / `+0x45d310`);
  3. `LuaMadeSimple::Lua::call_function`;
  4. три уровня Lua (`pcall` → `pcall`);
  5. `process_lua_function`;
  6. `__index` у userdata (`UE4SS.dll+0xb9eff0`, это тот обработчик, что раньше давал ошибку
     «System: Global for __index doesn't exist»);
  7. `UE4SS.dll+0xc6a4b0` = `lua_setiuservalue`, где Udata по индексу −2 оказался NULL (`movzx r9d, word [r10+0xa]`).
- Повреждённое состояние Lua. В HostBrain тот же Lua-стейт одновременно трогали:
  - рабочий поток UE4SS: колбэки `LoopAsync` (1 с и 0,5 с) создавали замыкания и вызывали `ExecuteInGameThread`;
  - игровой поток: тики, консольные команды, хук `BaseMagazineWeapon:Multicast_OnFire` на каждый выстрел любого оружия.

Вывод: в модах не исполнять Lua вне игрового потока. Циклы — `LoopInGameThreadWithDelay`, задержки —
`ExecuteInGameThreadWithDelay`. Никаких `LoopAsync`, `ExecuteWithDelay`, `RegisterKeyBind`.
В этой сборке UE4SS есть: `LoopInGameThreadWithDelay`, `LoopInGameThreadAfterFrames`, `ExecuteInGameThreadWithDelay`,
`RetriggerableExecuteInGameThreadWithDelay`, `CancelDelayedAction`, `RegisterEngineTickPre/PostCallback`.
Ghidra по UE4SS.dll: `tools/ghidra_decompile.ps1 -Binary ...\ue4ss\UE4SS.dll -Project UE4SS <VA>` (база 0x180000000).

## Скрытый ко-оп PvP «SWAT против подозреваемых» (26.10.2026)

Наблюдение (декомпиляция и проверка в игре):
- **Флаг режима: `CoopGS.bCrouchingTigerHiddenDragon`** (смещение 0xa7d, `CPF_Net | RepNotify`, `OnRep_CrouchingTigerHiddenDragon`).
  Рядом лежат `CoopGS.PvPState` (`EPvPState`, реплицируется), `PreRoundRemainingTime`, `ActorsToHandleInPvP`,
  а у `CoopGM` — `PreRoundTimeout`.
  - Запись `0xa7d` в exe есть только в конструкторах `CoopGS` (обнуление, `tools/ghidra_decompile.ps1` + скан смещения).
    Включать режим должны были `a.Ron.PVP.Start` / `a.Ron.PVP.Unlock`, но в Shipping эти консольные команды
    (флаг `ECVF_Cheat`) привязаны к функции из одного `RET` (`0x140b07d90`).
  - Проверки флага: `FUN_144e3ad60(GameState)` и `FUN_144e3adb0()`. Вторую вызывает
    `ReadyOrNotFunctionLibrary::IsSecretPvP`: после записи флага с хоста она возвращает `true`.
- **Что игра меняет сама при флаге:**
  - `IsEnemyTeam(a, b)` → «команды разные», `IsFriendlyTeam` → «команды совпадают» (`FUN_144de8200/8290/8330`);
  - `IsOnSameTeam` (`FUN_144e76f90`) → сравнение `GetTeam()`;
  - список камер команды (`PlayerCharacter::GetAvaliablePlayersForTeamView`) и кандидаты наблюдения
    (`SpectatePawn::SpectateNextPlayer` → `FUN_144b85dd0`) — только своя команда;
  - очередь радиосообщений (`FUN_144dc7730` и соседи) не пополняется;
  - автораспределение по командам при входе (`FUN_144ea4940`) выключено.
- **ИИ флаг не трогает.** `IsCharacterEnemy` у ИИ SWAT, ИИ-подозреваемых и гражданских с флагом и без одинаков:
  ИИ SWAT не стреляют в гражданских.
- **Отряд ИИ SWAT штатно есть только в одиночной миссии.** Старт миссии (`FUN_144c05e10`) создаёт отряд
  (`FUN_144c02290`), только если выполнены все условия:
  - людей меньше двух;
  - сервер не выделенный;
  - у скрипта уровня стоит флаг `+0xcbe`;
  - у мира нет `NetDriver` (`world+0x38 == 0`).

  Обход — консольная переменная `a.RonSpawnSwatInIncompatibleMode` (её описание в exe: «always spawn the swat… even
  if… multiplayer»). Она не помечена `ECVF_Cheat`, `Exec` с хоста её ставит. Проверено: в сетевой миссии при
  значении 1 появляются 4 `CyberneticsSwat_V2_C`, и флаг PvP их не убирает.
- **Старт миссии.** Отряд ИИ создаётся вокруг пешки игрока 0 (`ACoopGM`, `FUN_144c02290`: `defaultblueone`…`trailer`,
  `&ACoopGM::FriendlyAIKilled`). Если у хоста нет пешки (команда 3 до спавна), запасная ветка вызывает нулевой
  указатель, и игра падает. Без флага та же команда 3 давала фатал «Couldn't spawn player»; с флагом пешки просто нет.
  Поэтому все появляются как SWAT и переводятся после спавна.
- `ReadyOrNotPlayerController::Server_SetTeamType` меняет команду только на предмиссионном экране.
  В идущей миссии работает прямая запись `PlayerState.Team` и `OnRep_Team`.
- **Спавн игроков.** Игра не вызывает `GameModeBase::RestartPlayer` / `K2_OnRestartPlayer` (хук не срабатывает).
  Спавн на старте миссии берёт набор не из `PlayerState.ServerSavedLoadout`. Помогает
  `BpGameplayHelperLib::EquipLoadoutOnPlayer` с `Armor_NoArmor_C` / `Helmet_None_C` — так снимаются броня и шлем.
- **`ReadyOrNotGameMode::RespawnPlayer`** (`vtable+0x9e8` → `0x144ed2700`):
  - `CurrentMatchState` = Warmup/MatchEnded — спавнит у старта;
  - `MS_Playing` — только команды 1/2 с `PlayerState.bIsInGame`;
  - в режиме с флагом убитый игрок возвращается наблюдателем (`a.Ron.PVP.ForceRespawnAsSpectatorWhenKilled = 1`).
- **`ReadyOrNotGameMode::SpawnPlayerCharacter(PC, GameMode.DefaultPawnClass, Transform, bNoFail)`**:
  - Transform собирается через `KismetMathLibrary::MakeTransform`;
  - персонаж появляется ровно в точке, контроллер вселяется сам;
  - команда берётся из `PlayerState.Team`, снаряжение — из `ServerSavedLoadout` (SBR 4 магазина, Python 3, без брони).
- `CoopGM::MissionEnd(bSuccess)` открывает штатный экран итогов («НЕ ПРОЙДЕНО» при `false`).
- `CoopGM.bOverrideSuspectCustomizationInPvp = true`, `SuspectPlayerCustomizationOverride` — штатная одежда игрока-подозреваемого:
  `CSK_RapidResponse_Shirt_Buttoned`, `CSK_DETE_Pants`, `CSK_Swat_NoGlove`.
  - Сама игра её не применяет. HostBrain переносит заданные поля в `ReadyOrNotPlayerState::Server_SetCustomization`
    с `bForceLiveUpdate = true`.
  - Реализация (`vtable+0x7e8` → `0x144a43d20`) пишет `PlayerState.Customization` (`+0xd40`) и при живом
    обновлении переодевает персонажа (`+0x730`). В сохранение профиля она не пишет: следующая миссия начинается
    с собственной одежды игрока.
  - Проверено на хосте: голые руки, рубашка и брюки подозреваемого. Шлем, обувь и слот часов (`CBP_Handcuff`)
    остаются из профиля: в образце их нет.

**Фильтр SWAT-действий (RonCompNative).** Подменяет `UFunction::Func` у серверных RPC. Найденная раскладка:
- `UFunction::Func` = `+0xd8` (единственный указатель в `.text`);
- `UStruct::SuperStruct` = `+0x40`;
- `FFrame::Code` = `+0x20`, `FFrame::Locals` = `+0x28`;
- `AReadyOrNotCharacter::DefaultTeam` = `+0x1129`.

Проверка в миссии: у персонажа команды 2 `Server_Yell` проходит. С `DefaultTeam = 3` блокируются `Server_Yell`,
`Server_Interact` (цель — гражданский) и `Server_GiveAIMoveToExit`. Вызов из байткода Blueprint (`Code != 0`)
фильтр пропускает и пишет в лог: параметры такого вызова ещё не прочитаны из кода вызывающего.

**Кнопка команды на экране подготовки** (`W_PreMission_C`, байткод Blueprint разобран по JMAP, скрипт `kdis.py`):
- `SwapTeams_Box` виден, только если `AllowTeamSwapping() && !bInGame`. `AllowTeamSwapping` даёт `false` для
  `CoopGS` и `VIPEscortGS`, поэтому в ко-оп миссии кнопки нет.
- Нажатие вызывает `SwapTeams()`. Если игрок не нажал «Готов», она меняет `PlayerState.Team` 1 ↔ 2
  (`ReadyOrNotPlayerState::SetTeam`), то есть красный ↔ синий SWAT. Подпись — «Swap to MLO team» при команде 2:
  в задумке разработчиков красная команда была MLO. HostBrain держит подозреваемых в команде 3: так ИИ-подозреваемые
  остаются им союзниками.
- UE4SS этой сборки не подменяет возвращаемое значение Blueprint-функции: ни возврат из колбэка `RegisterHook`, ни
  `:set()` параметра. Третий аргумент (пост-колбэк) не вызывается.
- Вместо этого HostBrain на экране хоста вызывает `SwapTeams_Box:SetVisibility(Visible)`: константа заменяет
  привязку Slate до пересоздания виджета.
  - Кнопка — подсказка с клавишей, а надпись «ПОМЕНЯТЬ КОМАНДЫ» — отдельный элемент экрана. Собственный текст
    кнопки (`SetButtonText`) ложится поверх неё тёмным, поэтому его HostBrain очищает.
  - Выбранная сторона показывается в строке режима: `ModeName_Text:SetText`. В UE5 `UTextBlock::SetText` снимает
    привязку.
  - Хук на `SwapTeams` переключает хоста между SWAT и подозреваемыми.
  - Клиентам кнопку так не показать (у них нет UE4SS), у них выбор через чат.
- **Меню выбора команды без pak** (`hb_menu.lua`):
  - панель собирается в корневом `CanvasPanel` экрана (`W_PreMission_C.WidgetTree.RootWidget`) из `Border`,
    `VerticalBox`, `HorizontalBox`, `SizeBox`, `TextBlock` через `StaticConstructObject(класс, WidgetTree)`;
  - фон: `Border.Background.DrawAs = Image` и `SetBrushColor`; размер шрифта — копия `TextBlock.Font` с новым
    `Size` в `SetFont`;
  - кнопки — игровые `W_StandardButton_C` (`WidgetBlueprintLibrary::Create`), вид задаёт `DisplayStyle`:
    0 светлая, 3 красная, 6 серая, 8 жёлтая (значения перечисления в игре без имён, подобраны на экране);
  - и мышь, и `SimulateClicked` проходят через `W_StandardButton_C::OnClicked_Derived`; один хук на неё
    различает кнопки по адресу. Подпись кнопки после `SetButtonText` лежит во внутреннем `Text`, а не в
    `ButtonText`.
- **Отступы UMG из Lua.** В этой сборке поля `FMargin` отражены как `Left`, `top`, `Right`, `bottom` (регистр
  FName), а UE4SS сопоставляет ключи таблицы с учётом регистра: `{Top=…}` молча пропадает. HostBrain передаёт оба
  написания (`Margin()` в `hb_menu.lua`); так работают и `Border:SetPadding`, и отступы слотов.
- **Готовность в одиночной миссии.** Примерно через 4 с после появления экрана хост становится готов без нажатия, и
  через 10 с миссия стартует. Это не HostBrain и не зонд; возможно, один из модов mod.io. Снять готовность не удалось:
  ни `Server_SetReadyState(false)`, ни `ToggleReady` не помогают. Сработало удержание отсчёта: пока хост не нажал
  «Готов» (хук `ToggleReady`), HostBrain каждый кадр возвращает `GameState.TimeTillGameStartCountdown` к 10.
  Проверено: отсчёт стоял больше минуты, после «Готов» миссия стартовала через 10 с.

**Гражданские и флаг PvP** (27.10.2026). Игроки сообщили, что ИИ-отряд убивает заложников.
- `IsEnemyTeam` (`FUN_144de8200`) при флаге отвечает «команды разные». Гражданские (`TT_CIVILIAN` = 4) становятся
  врагами ИИ SWAT (2/5) и ИИ-подозреваемых (3). `IsFriendlyTeam` (`FUN_144de8290`, `FUN_144de8330`) при флаге
  перестаёт считать SWAT и гражданских своими.
- Обычные правила: SWAT (1, 2, 5) и гражданские — враги подозреваемых (3), а подозреваемый гражданскому не враг.
- `RonCompNative` ищет по шаблону три проверки флага и делает так, чтобы они его не видели:
  - в `IsEnemyTeam` `jz` превращается в `jmp`;
  - в `IsFriendlyTeam` `test al,al; jnz` заменяется на `xor al,al; nop; nop` (дальше код сравнивает с AL).

  Наблюдение и камеры команды проверяют флаг в другом коде и остаются раздельными.
- Проверено в матче игрока за подозреваемых с 4 ботами: все 9 `Cybernetics_Civilian_V2_C` живы.

**Очки миссии в PvP.** `AScoringManager::Multicast_DisplayScore(FText, int32, bool)` рисует «+N» у всех игроков.
- Нативная заглушка (`0x14492cbd0`) найдена через глобальное FName: статический инициализатор ссылается на строку
  `Multicast_DisplayScore`; DLL ищет `mov rdx,[rip+имя]` и границы функции по `.pdata`.
- Заглушка перехвачена (пролог 16 байт без адресации от RIP). Пока Lua держит «PvP включён»
  (`RonCompNative_PvpOn` / `_PvpOff`), вызов не доходит до `ProcessEvent`, и multicast никому не уходит.
- Проверено: в матче заблокированы «+200», «+25», «+5».

**Шатание прицела у подозреваемого.** Замеряли размах положения и поворота `ItemMesh` относительно
`FirstPersonCameraComponent` при ходьбе боком (`AddMovementInput`, 3 с), а также тряску камеры.
- Команда (2 или 3), одежда, отсутствие брони и снаряжения, оружие (AK102, SBR, FAL, MK18) шатание не меняют: размах
  рысканья около 2,8°, крена около 1,4°.
- Большой размах (рысканье 22°, крен 66°) был только у персонажей, только что поставленных на место ИИ-подозреваемого:
  скорость там 288 при `MaxWalkSpeed` 240, значит, персонажа сносило (лестницы, мебель).
- Тряска камеры (`RightShake`/`ForwardShake`) около 0,1°; подавления при замерах не было.
- **Причина — сами стволы.** Игрок уточнил: качает при прицеливании и шаге вбок с AK. Замер в его игре (только
  чтение): AK-103 при прицеливании гуляет на 5–30° по тангажу за секунду, камера неподвижна.
- Параметры по умолчанию в классах оружия (`BaseItem`):

  | Оружие | `InertiaDragStrafeRotation` / `Location` | `FreeAimLimitADS` |
  |---|---|---|
  | AK-103 | 1.0 / 1.0 | 4.5 |
  | AK-102, G3A3, Saiga-12 | 1.0 / 1.0 | 1.5–4 |
  | MK18, SLR-47, MP5 | 0.4 / 0.2 | 1.0 |
  | FAL | 0.6 / 0.3 | 0 |
  | 870 | 0.4 / 0.12 | 0 |

  Пистолеты в норме. Игроку-подозреваемому эти четыре ствола больше не выдаются:
  - AK → SLR-47 (тоже АК-образный);
  - G3A3 и пулемёты → FAL;
  - в случайном наборе одиночного режима остаются SLR-47, FAL, 870 и MP5.

  Подмена при выдаче работает и для клиентов, а правка свойств экземпляра сработала бы только на хосте.

**Дверь отзывается не сразу.** Игрок: значок на двери появляется секунды через 2. В HUD
`CommandContext_Container` игра показывает (видимость 4), когда у персонажа есть контекст, в том числе дверь.
HostBrain у хоста-подозреваемого сворачивал его раз в секунду вместе с панелью отряда, поэтому подсказка
пропадала до следующего показа игрой. Теперь скрывается только `SWATTeamStatus_V2`.

Ловушки UE4SS, на которых падала игра:
- `obj:GetClass()` на нулевом объекте читает `+0x10`;
- `GameplayStatics::ApplyDamage` с пустым инстигатором роняет `TakeDamage` игры.

Вывод: HostBrain `comp_pvp` (`hb_pvp.lua`):
- ставит флаг (а с ботами — после появления отряда);
- проводит выбор команд на предмиссионном экране;
- переводит подозреваемых на места ИИ-подозреваемых в первом кадре их пешки;
- после смерти создаёт игрока через `SpawnPlayerCharacter` на месте другого ИИ;
- играет матч из раундов без `MissionEnd` (раздел «Раунды PvP» ниже).

С ботами HostBrain на старте миссии ставит `a.RonSpawnSwatInIncompatibleMode 1` и снимает его, когда отряд
появился (или через 30 с). Отряд создаётся вокруг пешки хоста и ходит за `SWATManager.SquadLeader`. Поэтому:
- хост-подозреваемый уходит к ИИ только после появления отряда (не дольше 5 с);
- лидером становится живой игрок SWAT, а без него — ИИ, и отрядом правит общий с одиночным режимом «охотник»
  (`hb_hunt.lua`).

Проверено на хосте (хост за подозреваемых, 4 бота): отряд появился у фургона, получил приказы по подсказке и по
обнаружению. После смерти хост через 10 с вселился в ИИ-подозреваемого.

## Раунды PvP (27.10.2026)

Задача: игрок жаловался, что у подозреваемых в конце штатный экран итогов SWAT (`CoopGM::MissionEnd`), а следующего
раунда нет.

Наблюдение (JMAP, проверка в игре):
- Сброс раунда в ко-оп миссии — повторная загрузка той же карты. Имя карты даёт
  `GameplayStatics::GetCurrentLevelName(world, true)` (`RoN_Campus_Core`), режим — `?game=` из
  `GameModeBase.OptionsString`, иначе `BS_COOP` (`GameState.ModeURL_Replicated` тоже `BS_COOP`).
  - В одиночной игре — `open <карта>?game=<режим>`, в сетевой — `servertravel` (клиенты остаются).
  - От команды до экрана подготовки около 11 с.
- Готовность: `ReadyOrNotPlayerController::Server_SetReadyState(bReady)` [NetServer], `ReadyUp()`,
  `ReadyOrNotGameState::IsEveryoneReady()` и `TimeTillGameStartCountdown` (отсчёт после общей готовности).
  - В одиночной игре хост отмечается готовым сам примерно через 4 с; дальше 10 с отсчёта.
- Перед загрузкой команда всех игроков возвращается в SWAT: на ко-оп картах нет стартов подозреваемых.
- В игре есть свой экран конца раунда (`W_PVP_RoundEnd`, `URoundEndWidget_PVP::OnGameModeRoundEnded`), но он
  живёт в `ReadyOrNotGameMode_PVP`, не в ко-опе.

Вывод (`hb_pvp.lua`, `hb_menu.lua`):
- раунд кончается внутри миссии: счёт, итог в чат, через 6 с та же миссия загружается заново;
- на новом экране подготовки страница меню у хоста показывает итог раунда; через 8 с всех отмечают готовыми:
  хоста через `ReadyUp`, клиентов через `Server_SetReadyState(true)` на сервере;
- после N−1 раунда игроки меняются сторонами, счёт переходит с ними. Со второго раунда матч идёт и без
  игроков-подозреваемых (хост один после смены — SWAT с ботами против ИИ-подозреваемых);
- конец матча — страница «Матч окончен», старт держится до «Новый матч».

Проверено на хосте (одиночная игра, кампус, матч до 2 побед, раунды закрывались `comp_pvp_endround`):
- раунд 1 за подозреваемых → смена сторон, хост в раунде 2 за SWAT, счёт перешёл (SWAT 1 : 0);
- раунды стартовали сами через ~14 с после экрана подготовки;
- страница итогов переключается на отсчёт игры;
- после решающего раунда — «Матч окончен», «Новый матч» вернул раунд 1 и счёт 0 : 0.

Не проверено (нужен друг): `servertravel` с клиентом, готовность клиента через `Server_SetReadyState`, одежда
клиента-SWAT после смены сторон. Игра может сама закончить миссию, когда погибли все игроки
(`ReadyOrNotGameMode::AreAllPlayersDead`); загрузка следующего раунда через 6 с её перекрывает, но штатный экран
может мелькнуть.

**Доклады подозреваемых.** Игрок-подозреваемый докладывал по рации, как SWAT. Кроме `Server_ReportTarget` и
`Server_ReportToTOC` фильтр теперь режет `ReadyOrNotCharacter::Server_PlayTOCConversation`. Вызов от пешки хоста
команды 3 дал в `RonCompNative.log` `blocked Server_PlayTOCConversation from a suspect`. Анимация и голос доклада
запускаются у игрока до RPC, ванильному клиенту их не убрать.

## Урон подозреваемых по SWAT (27.10.2026)

Задача: игрок за подозреваемых почти не ранил ИИ-SWAT и спросил, не считает ли игра его выстрелы огнём по своим.

Наблюдение (Ghidra 12.1.4, рефлексия, замеры в игре через RonCompProbe):
- **Огонь по своим ни при чём.**
  - `AReadyOrNotCharacter::TakeDamage` (`0x144e92f10`) один на всех персонажей. Урон считают обработчики
    в слоте vtable `+0xE40`: у игрока `0x144b54080`, у ИИ `0x144b1f330` / `0x144b20320`.
  - Обработчики спрашивают `IsOnSameTeam(жертва, пешка стрелка)` (`0x144e769c0` → `0x144e76f90`). При «своём»
    урон обнуляется, только если `UReadyOrNotAIConfig` даёт `FriendlyFireEnabled = false` (по умолчанию true).
  - `IsOnSameTeam` для подозреваемого (команда 3) и SWAT (2, 5) — «нет» в обеих версиях. При флаге
    `bCrouchingTigerHiddenDragon` это сравнение `GetTeam()`; без флага команды 1 и 2 считаются одной стороной,
    а 3 с ними — нет.
  - Урон по игроку дополнительно умножается на `ReadyOrNotGameState.GametypeDamageModifier` (во всех ко-оп GS 1.0).
- **ИИ-SWAT (`CyberneticsSwat_V2_C`) — 250 HP, у игрока 160.** На них лёгкий бронежилет `Armor_Light_V2`
  (`SWATArmour`) с материалом `AM_Ceramic` (`ArmourLevel` 6, `DamageReduction` 1.0, `MinDamageReduction` 0.4,
  прочность 4 на пластину, `SWATArmour.Durabilities` = [4, 4, 0]) и шлем.
  - Запасные копии отряда `CyberneticsSwatTrailer_C` стоят за картой (Z = −10000) в `AM_Steel`
    (уровень 6, 0.865/0.7, прочности нет).
  - У игрока-SWAT по умолчанию `Armor_Heavy_V2` + `AM_Kevlar` (уровень 3, 0.5/0.5).
- **Патроны** (`AmmoDataTable`, 41 строка): `PenetrationLevel` не выше 4 (винтовочные FMJ), у 9×19 FMJ — 2,
  у JHP — 0, у картечи — 1.
  - `HitsChance` / `ArmouredHitsChance` — шанс анимации попадания (`HitAnimationChanceMultiplier`), не пробития.
  - Настоящий выстрел (`Server_HitscanHit`, `0x1449a06e0`) берёт строку патрона из
    `BaseWeapon.AmmunitionTypes[AmmoTypeIndex]`, а не из `CurrentAmmoType` оружия.
- Замеры:
  - **`GameplayStatics::ApplyPointDamage` с трассой к кости из Lua:** в корпус — 0 при любом пробитии и материале,
    в руку — 21, в ногу — 30; шлем держит, пока не сносится.
    - UE4SS не возвращает в функцию `FWeakObjectPtr` из Lua-таблицы (`[push_weakobjectproperty] Error`), поэтому
      у такого `FHitResult` нет актёра и компонента, и этот путь броню не моделирует.
  - **Выстрел ИИ (`BaseCombatActivity::ScriptedFireAtActor`) 300AAC FMJ:** по кевлару −21.9 HP за попадание
    (примерно половина урона), пластина 4 → 3.67. По керамике и стали за всё время замеров урон в корпус не прошёл.
- **Чем был вооружён игрок** (журнал `RoNPvPLog.sav`): MP5A2 + M92FS / Python / P99 / M1911, один раз FAL.
  - У ИИ-подозреваемых на `RoN_Gas_BarricadedSuspects_Core` только пистолеты (Tec9, Python), поэтому основное
    оружие выбиралось случайно из SLR-47, FAL, 870 и MP5A2.
  - У ИИ-подозреваемых 360 HP.
- **`ReadyOrNotCharacter::DecreaseHealth` из скрипта на ИИ роняет игру.** Исключение в `0x144e62990`, игра
  повисает в обработчике краша (минидамп `hangdump.py`, раскрутка `unwind.py`). Здоровье ботов так не менять.

Вывод (0.2.1-alpha, обе версии):
- подозреваемые-игроки получают только винтовки под FMJ:
  - SMG, пистолеты-пулемёты и случайный выбор → SLR-47 или FAL;
  - дробовики → FAL;
  - пистолет-калибр не пробивает даже стандартный кевлар игрока-SWAT;
- ИИ-отряд SWAT в PvP переодевается в материал брони игрока по умолчанию (`AM_Kevlar`). Замену делает
  `PvPDirector.ArmourSquad` / `hb_loadout.ArmourSquad` каждую секунду живого раунда, свойство `CPF_Net`;
- проверено в игре: журнал «AI squad armour -> Kevlar: 4», у ботов `AM_Kevlar`, у хоста-подозреваемого
  SLR-47 (пробитие 4) + M92FS.

Не сделано:
- 250 HP ботов: безопасного способа менять здоровье не нашлось;
- броня игроков-SWAT: их выбор, керамика и сталь для подозреваемых почти неуязвимы в корпус.

## Лимит лобби: 5 → 10 (26.10.2026)

Наблюдение (декомпиляция, проверка значения в игре):
- **Лимит хранит `UEOSMultiplayerSubsystem`** (подсистема `GameInstance`), нерефлектированное поле `+0xac`.
  - Конструктор (`0x144826dd0`) ставит 5.
  - Других записей нет, кроме `EOSMultiplayerStatics::SetMaxPlayers` (`0x144829ab0` → `0x144f07710`).
    Её же вызывает консольная `ReadyOrNotPlayerController::ConsoleSetMaxPlayers` (`Exec`).
  - Ни один Blueprint, загруженный при снятии JMAP (в том числе `W_MainMenu_V3`), не вызывает `SetMaxPlayers` и
    `GetMaxPlayers`. Искали указатели UFunction в байткоде; контроль — `PrintString`, его нашли в 36 функциях.
- **Создание лобби.** Асинхронная операция подсистемы (`0x144ee4040`, рядом строки `'s Lobby`, `CROSSPLAY`,
  `MM_REGION_KEY`) кладёт `+0xac` в `FOnlineSessionSettings.NumPublicConnections`. Redpoint EOS по нему задаёт
  размер лобби EOS.
- **Проверка входа у хоста.** `ReadyOrNotGameMode::PreLogin` (`0x144ece4d0`) отвечает «Server is full!», если
  `игроки + PlayersJoining + 1 > NumPublicConnections` сессии `GameSession`. Если сессии нет, порог — 5.
  `ReadyOrNotGameMode.MaxPlayersAllowed` (5) и `GameSession.MaxPlayers` (16) этот вход не ограничивают.
- **Когда лобби заполнено.** `0x144f03190` при `+0xac <= RegisteredPlayers` обновляет лобби
  (видимо, закрывает его для поиска).
- **Уже созданное лобби смена значения не меняет:** число мест задаётся при создании.

Вывод: HostBrain при запуске игры (главное меню, до создания лобби) вызывает `SetMaxPlayers(10)`.
`comp_maxplayers <2..16>` меняет значение, `comp_status` его показывает. Значение 10 подтверждено в игре
(`GetMaxPlayers` до и после).

Не проверено (нужны живые игроки):
- что лобби, созданное после этого, принимает 6-го и следующих игроков;
- где появятся 6–10-й игроки. В ко-оп миссии кампуса у зоны входа один `PlayerStart`. Спавн
  (`SpawnPlayerCharacter` → `FActorSpawnParameters.SpawnCollisionHandlingOverride = 2`,
  «AdjustIfPossibleButAlwaysSpawn») не откажет, но сдвинет персонажей. Подозреваемых PvP сразу переносит к ИИ.

## Регистрация попаданий (S4)

Метод: JMAP-дамп рефлексии (RPC-сигнатуры, значения CDO по умолчанию с учётом ini), строки exe.

Наблюдение:
- Стрельба hitscan:
  - `BaseMagazineWeapon::Server_OnFire(Rotator Direction, Vector SpawnLoc, int Seed)` [Server, Reliable, **Validate**];
  - `BaseMagazineWeapon::Server_HitscanHit(FHitResult HitResult, float Time, Vector TraceBegin, float Distance, float Penetration,
    int AmmoTypeIndex, int Seed)` [Server, Reliable, **без Validate**] — клиент присылает серверу готовый результат трассировки;
  - `Multicast_OnFire`, `Multicast_PerformHitscan(FHitscanShot{Location, Direction, Seed}, bLocalOnly, Seed)`,
    `Multicast_SimulateFireForViewTargets` — эффекты для остальных;
  - `Client_HitscanDebug(bSuccess, Center, Extent, ImpactPoint)` — сервер возвращает стрелку отладку проверки по коробке;
  - `ReadyOrNotPlayerController::Client_OnProjectileValidation(int ProjectileSeed, EServerValidationState{Unvalidated, Validated, Invalid})`.
- Прямые серверные RPC урона: `BaseItem/ReadyOrNotCharacter::Server_ApplyPointDamage(DamagedActor, BaseDamage, HitFromDirection,
  HitInfo, EventInstigator, DamageCauser, DamageTypeClass)` [Validate], `PlayerCharacter::Server_TakeDamage(Damage, DamageEvent, ...)`.
- **`UHitRegistrationSettings : UDeveloperSettings`** (все поля `Config`), значения CDO в игре:
  `bEnableValidation = false`, `HitscanForgiveness = 50`, `ShooterForgiveness = 250`, `TraceDistanceForgiveness = 5`,
  `SnapshotVelocityFactor = 1.0`, `MinimumSnapshotExtent = (75, 75, 90)`.
- Консольная переменная `a.RonForceDisableHitValidation`.

Декомпиляция (Ghidra 12.1.4; реализация найдена через слот vtable `+0x978` у CDO `BaseMagazineWeapon` → `0x1449a06e0`):
- `Server_HitscanHit_Implementation(this, FHitResult*, Time, FVector* TraceBegin, Distance, Penetration, AmmoTypeIndex, Seed)`:
  1. работает только при `Role == ROLE_Authority`;
  2. берёт CDO `UHitRegistrationSettings` (`0x14483a770` — `StaticClass`, размер 0x68);
  3. **если `bEnableValidation` (`+0x38`) = false — сразу применяет попадание** (`0x144980fe0`), без проверок;
  4. иначе, если `a.RonForceDisableHitValidation == 0`, отклоняет попадание, когда:
     - `|HitResult.Location − TraceBegin| − |TraceDistanceForgiveness (+0x44)| > Distance`;
     - цель — не `AReadyOrNotCharacter` (`0x1448cbbf0`) — при включённой проверке попадания по не-персонажам не применяются;
     - `TraceBegin` вне коробок снимков стрелка ± `ShooterForgiveness (+0x40)` на момент `Time`;
     - точка попадания вне коробки цели, **линейно интерполированной между её снимками на момент `Time`**
       (массив снимков персонажа — `+0x1AD0`, элементы по 0x40: время + min/max в double);
  5. при успехе — применение попадания и счётчик для хит-маркеров (`0x14498d9e0`).
- `Server_OnFire_Implementation` (`0x1449a0e40`, слот `+0x9C0`): проверяет патроны, при нуле — сухой выстрел и
  `Client_OnProjectileValidation(Seed, Invalid)`.

Вывод (подтверждён):
- Модель — **«прав стреляющий»**: трассирует клиент, сервер получает `FHitResult`.
- В игре есть **серверная лаг-компенсация** по истории снимков позиций: коробка `MinimumSnapshotExtent`,
  растянутая по скорости (`SnapshotVelocityFactor`), с допусками. **В поставке она выключена** (`bEnableValidation=false`),
  и тогда сервер принимает любое присланное попадание.
- Для HostBrain: включить проверку **только на хосте** (запись в CDO `HitRegistrationSettings` или
  `[/Script/ReadyOrNot.HitRegistrationSettings]` в `Game.ini` хоста) и подобрать допуски замерами. Клиентам ничего ставить не нужно.
  Побочный эффект: с включённой проверкой hitscan-попадания по не-персонажам (двери, стёкла, предметы) не применяются —
  проверить в игре; при проблеме HostBrain делает свою проверку в хуке `Server_HitscanHit` только для попаданий по персонажам.
- Риск античита: `Server_ApplyPointDamage`/`Server_TakeDamage` позволяют клиенту заявлять урон — HostBrain должен их
  фильтровать в PvP (хук на сервере).

## Оружие и снаряжение (для `data/items.csv`)

Наблюдение:
- Оружие SWAT: `Blueprints/Items/WeaponsRevised/` (Primary_*, Secondary_*, Grenade_*, Device_*, Launcher_*, Sniper_M24).
- Оружие подозреваемых: `Blueprints/Items/WeaponsSuspect/` (AKM, AK104, AKS74U, Uzi, M249, RPD, SawnOff, Tec9, Makarov,
  Melee_Knife и др.).
- Броня: `Blueprints/Items/ArmorRevised/` (`Armor_Light_V2`, `Armor_Heavy_V2`, `Armor_StabVest`, `Helmet_*`).

Неизвестно:
- Можно ли выдавать игроку оружие из `WeaponsSuspect`, или оно рассчитано только на ИИ.
