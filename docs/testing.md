# Testing

## Levels
1. **Core unit tests** (`HostBrain/tests`) — without the game, on every build:
   ```bash
   powershell -File tools/test_core.ps1
   ```
   They cover phases, score, side swap, overtime, economy, buying and statistics.
2. **HostBrain startup check** — all hooked game functions and properties are found and their sizes match.
   If not, the mod disables itself with a clear error in the UE4SS log.
3. **In-game scenarios** — `comp_autotest <scenario>`: bots + forced events → JSONL log → `tools/logcheck.py`.
4. **UI** — screenshots of the HUD and the buy menu through computer-use.
5. **Network** — 2 instances or 2 PCs, clumsy profiles of 0/60/120 ms and 1% loss, hit logs from both sides.
6. **Real playtests** — a lobby with people at the end of every phase.

## RonCompProbe remote console (development)

Lets you control and watch the game without a mouse and keyboard.

1. Once: `powershell -File tools/install_ue4ss.ps1 -Dev`, then `powershell -File tools/deploy_ue4ss_mods.ps1`.
2. Start the game directly: `ReadyOrNot.exe` in the game folder. Through `steam://rungameid`, Steam first asks for
   launch options.
3. Put a Lua script into `<game>/ReadyOrNot/Binaries/Win64/ue4ss/Mods/RonCompProbe/inbox.lua`.
   The probe runs it on the game thread within a second and renames it to `inbox.done.lua`.
   Scripts can use `State()`, `Exec(cmd)`, `CallStatic(class, fn, ...)`, `Get(obj, prop)`, `PC()`, `GM()`, `GS()`,
   `World()`, `Shot(tag)`, `Log(fmt, ...)`, `Quit()`.
   For delays and loops in scripts use only `ExecuteInGameThreadWithDelay` / `LoopInGameThreadWithDelay`:
   `ExecuteWithDelay`/`LoopAsync` run Lua on a UE4SS worker thread and sooner or later crash the game
   (docs/re-findings.md, "Crash after ~2 h of play"). Call `obj:GetClass()` only after `obj:IsValid()`:
   on a null object UE4SS reads `+0x10` and the game crashes. Call `ApplyDamage` only with an instigator and a damage
   causer.
   After a deploy, new HostBrain scripts are picked up by `RestartMod("HostBrain")`, but only until HostBrain has
   hooked Blueprint functions (`SwapTeams`, `ToggleReady`, `OnClicked_Derived` — after the first pre-mission
   screen). `RestartMod` removes only native hooks, while script hooks stay bound to the deleted Lua state: the next
   call of such a function hangs the game. After the pre-mission screen, restart the game instead.
4. Output is written to `Mods/RonCompProbe/probe.log`.
5. Screenshots are saved to `<game>/ReadyOrNot/Ready Or Not/Saved/Screenshots/`:
   `Exec("shot showui")` captures a frame with the UI, `HighResShot 1` captures only the 3D scene.

Example: starting Defusal on the campus as the host:
```lua
Exec("open RoN_Campus_Core?listen?game=RR_PVP")
```
