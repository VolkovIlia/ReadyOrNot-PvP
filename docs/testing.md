# Тестирование

## Уровни
1. **Юнит-тесты ядра** (`HostBrain/tests`) — без игры, на каждой сборке:
   ```bash
   powershell -File tools/test_core.ps1
   ```
   Покрывают фазы, счёт, смену сторон, овертайм, экономику, закупку и статистику.
2. **Проверка на старте HostBrain** — все хукнутые функции и свойства игры найдены, размеры совпадают.
   Если нет — мод отключается с понятной ошибкой в логе UE4SS.
3. **Сценарии в игре** — `comp_autotest <scenario>`: боты + форсированные события → JSONL-лог → `tools/logcheck.py`.
4. **UI** — скриншоты HUD и меню закупки через computer-use.
5. **Сеть** — 2 экземпляра или 2 ПК, профили clumsy 0/60/120 мс и 1% потерь, логи попаданий с обеих сторон.
6. **Реальные плейтесты** — лобби с людьми на каждом выходе из фазы.

## Удалённая консоль RonCompProbe (разработка)

Позволяет управлять игрой и наблюдать за ней без мыши и клавиатуры.

1. Один раз: `powershell -File tools/install_ue4ss.ps1 -Dev`, затем `powershell -File tools/deploy_ue4ss_mods.ps1`.
2. Запустить игру напрямую: `ReadyOrNot.exe` в папке игры. Через `steam://rungameid` Steam сначала спросит параметры запуска.
3. Положить Lua-скрипт в `<игра>/ReadyOrNot/Binaries/Win64/ue4ss/Mods/RonCompProbe/inbox.lua`.
   Зонд выполнит его на игровом потоке в течение секунды и переименует в `inbox.done.lua`.
   В скрипте доступны `State()`, `Exec(cmd)`, `CallStatic(class, fn, ...)`, `Get(obj, prop)`, `PC()`, `GM()`, `GS()`, `World()`,
   `Shot(tag)`, `Log(fmt, ...)`, `Quit()`.
   Задержки и циклы в скриптах — только `ExecuteInGameThreadWithDelay` / `LoopInGameThreadWithDelay`:
   `ExecuteWithDelay`/`LoopAsync` исполняют Lua на рабочем потоке UE4SS и со временем роняют игру
   (docs/re-findings.md, «Краш через ~2 ч игры»). `obj:GetClass()` вызывать только после `obj:IsValid()`:
   на нулевом объекте UE4SS читает `+0x10` и игра падает. `ApplyDamage` — только с инстигатором и причиной.
   Новые скрипты HostBrain после деплоя подхватываются `RestartMod("HostBrain")`, но только пока HostBrain не
   поставил хуки на Blueprint-функции (`SwapTeams`, `ToggleReady`, `OnClicked_Derived` — после первого экрана
   подготовки). `RestartMod` снимает только нативные хуки, а скриптовые остаются привязаны к удалённому Lua-состоянию:
   следующий вызов такой функции вешает игру. После экрана подготовки — перезапуск игры.
4. Вывод пишется в `Mods/RonCompProbe/probe.log`.
5. Скриншоты сохраняются в `<игра>/ReadyOrNot/Ready Or Not/Saved/Screenshots/`:
   `Exec("shot showui")` снимает кадр с интерфейсом, `HighResShot 1` — только 3D-сцену.

Пример: запуск Defusal на кампусе от лица хоста:
```lua
Exec("open RoN_Campus_Core?listen?game=RR_PVP")
```
