# Находки реверса

Каждая запись: **наблюдение** (что видно напрямую), **вывод** (что из этого следует), **неизвестно** (что ещё проверить).
Если находка получена через REA, рядом указывается Evidence ID.

## Инструменты
- **REA** (`npx rea-agents@6.8.0`) с провайдером Ghidra: `GHIDRA_INSTALL_DIR=C:\Users\iliav\Tools\ghidra_12.1.4_PUBLIC`,
  `JAVA_HOME=C:\Program Files\Eclipse Adoptium\jdk-21.0.12.101-hotspot` (заданы в пользовательских переменных Windows;
  MCP-сервер увидит их после перезапуска клиента). `rea doctor --client claude_code` — Ghidra healthy.
- **Точечная декомпиляция без полного автоанализа** (полный анализ exe на 150 МБ занимает часы):
  `pwsh -File tools/ghidra_decompile.ps1 -Out C:\Users\iliav\Tools\ron_re\out -Depth 1 0x1449a06e0 dis:0x142a52df0:12`.
  Проект Ghidra и копия exe живут в `C:\Users\iliav\Tools\ron_re` (лаунчер Ghidra не переносит пробелы и скобки в путях).
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
