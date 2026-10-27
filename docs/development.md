# Разработка

## Как это устроено

- **HostBrain** (`HostBrain/ue4ss-mods/HostBrain`) — Lua-мод для RE-UE4SS. Его ставит **только хост** (listen server).
  Все правила режима живут здесь, клиенты получают состояние через штатную репликацию игры и штатные RPC.
- **RonCompNative.dll** (`HostBrain/native/RonCompNative.cpp`, MSVC) — нативная часть: защита от краша при сбросе раунда,
  фильтр SWAT-действий подозреваемых (подмена `UFunction::Func` у серверных RPC), правила «свой/чужой» для
  скрытого ко-оп PvP, отключение всплывающих очков. Lua загружает её через `package.loadlib` и обменивается с ней
  через ini и лог.
- **Чистое ядро** (`HostBrain/src/core`) не зависит от UE: фазы раунда, экономика, настройки в духе cvar для будущего
  режима в духе CS2 ([design.md](design.md)). Покрыто юнит-тестами, собирается и проверяется вне игры.
- **RonCompProbe** (`HostBrain/ue4ss-mods/RonCompProbe`) — удалённая консоль для разработки ([testing.md](testing.md)).
  В релиз не входит.

Находки реверса: [re-findings.md](re-findings.md). Тестирование: [testing.md](testing.md).
Чек-лист игры с другом: [pvp-playtest.md](pvp-playtest.md).

## Структура

```
HostBrain/ue4ss-mods/  Lua-моды UE4SS: HostBrain (сам мод) и RonCompProbe (удалённая консоль)
HostBrain/native/      RonCompNative.dll
HostBrain/src/core     чистое ядро, HostBrain/tests — юнит-тесты
data/                  competitive.cfg (настройки в духе cvar), items.csv
docs/                  дизайн, находки реверса, тестирование
re/                    скрипты реверса (крупные дампы и распаковка игры не коммитятся)
tools/                 сборка, установка UE4SS, деплой, упаковка релиза
assets/                картинки мода
```

## Сборка

Нужны Visual Studio 2022 (MSVC, CMake) и PowerShell.

Сборка `RonCompNative.dll` и тесты ядра:
```bash
powershell -File tools/build_hostbrain.ps1
```

Установка UE4SS (сборка из `tools/bin/ue4ss/<версия>/extracted`; `-Dev` включает консоль UE4SS и горячую перезагрузку):
```bash
powershell -File tools/install_ue4ss.ps1 -Dev
```

Копирование модов в игру (можно при запущенной игре; скрипты подхватываются после перезапуска игры):
```bash
powershell -File tools/deploy_ue4ss_mods.ps1
```

Архив релиза в `dist/` (HostBrain с собранной DLL, без RonCompProbe):
```bash
powershell -File tools/package_release.ps1
```

Версия мода — `Version` в `HostBrain/ue4ss-mods/HostBrain/Scripts/main.lua` и запись в [CHANGELOG.md](../CHANGELOG.md).

## Pak-версия для меню «Моды» (`pakmod/`)

Режим для mod.io собирается без редактора UE: логика написана на подмножестве Python (`pakmod/src/pvp.py`), компилятор
`pakmod/kc` переводит её в байткод Kismet и пишет cooked-ассеты UE 5.3 как JSON UAssetAPI; UAssetGUI делает из них
`.uasset`/`.uexp`, `repak` упаковывает в pak. Подробно — в [modio-pak-research.md](modio-pak-research.md).

Что нужно:
- JMAP-дамп рефлексии игры в `re/dumps/*.jmap` и `.usmap` (снимаются UE4SS, в git не входят);
- `tools/bin/uassetgui/UAssetGUI.exe` (1.1.0) и `tools/bin/repak/repak.exe` (0.2.3) из их релизов на GitHub;
- карта типов: `%LOCALAPPDATA%\UAssetGUI\Mappings\RoN.usmap` (копия `.usmap` из дампа).

Сборка, установка в `Paks/~mods` и архив для mod.io:
```bash
python pakmod/build.py pvp --deploy --zip
```

Устройство:
- `kc/kismet.py` — выражения Kismet и их размеры в памяти (проверены на 146 функциях Blueprint игры);
- `kc/uasset.py` — пакет: таблица имён, импорты, экспорты;
- `kc/blueprint.py` — класс, функции, переменные, вызовы;
- `kc/lang.py` — компилятор языка;
- `kc/data.py` — `ModActorSpawnData`;
- `kc/reflect.py`, `kc/types.py` — рефлексия игры и типы свойств.

Справка по функциям и свойствам игры: `python pakmod/sig.py ReadyOrNotPlayerController:ReadyUp "W_StandardButton_C:*Click*"`.

Правила байткода, на которых уже падала игра:
- результат функции пишется через `EX_LocalOutVariable(ReturnValue)`, а вызов присваивается `EX_Let(temp, вызов)`.
  Передавать адрес результата аргументом нельзя: `ProcessScriptFunction` пропускает параметр результата;
- `EX_Return` без значения: копирование результата в буфер вызова-инструкции (64 байта, не инициализирован)
  роняет игру на массивах и строках;
- имя вида `Ret_1` движок хранит как `Ret` с номером, базовое имя тоже нужно в таблице имён.

Отладка: директор пишет журнал в `Notes` (UE4SS: `FindAllOf("BP_PvPDirector_C")[1].Notes`) и в
`SaveGames\RoNPvPLog.sav`. Функции Blueprint можно вызывать из UE4SS напрямую.

## Экспериментальное: штатные PvP-режимы игры

В игре остались собственные PvP-режимы (Firefight, Defusal и др.). `comp_start` переносит лобби на карту в таком режиме.
Это заготовка следующих этапов: режимы нестабильны и могут прервать игру у всех.

```
comp_start campus ff      нативный Firefight на Watt Community College (проверено)
comp_start campus RR_PVP  Defusal с бомбой (проверено; правила CS2 — следующий этап)
comp_start <карта> <режим> force   непроверенная пара: может прервать игру у всех
comp_status               режим, счёт, защита, проверка попаданий
comp_maps / comp_modes    список карт и режимов
```

## Одиночный матч за подозреваемых против ботов SWAT (консоль)

Старый одиночный режим, до меню команд. Сейчас то же самое удобнее делать через меню PvP (вступить за подозреваемых
и играть одному).

```
comp_play_suspect campus [n]  матч до n побед (по умолчанию 3): вы — подозреваемый, ИИ-подозреваемые — союзники,
                              отряд ИИ SWAT штурмует здание
comp_round_time 240 20        время штурма и подготовки, с (со следующего раунда)
comp_bot_hints 0|1            подсказка отряду после 60 с без контакта (по умолчанию включена)
comp_bot_accuracy 3           точность ботов SWAT: 1 = обычная, больше = хуже (по умолчанию 2)
comp_suspect off              выйти из режима
```
