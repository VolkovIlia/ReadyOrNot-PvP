-- HostBrain solo mode: the host plays a suspect against the AI SWAT squad of a co-op mission, in
-- rounds (comp_play_suspect) or freely (comp_suspect).

local UEHelpers = require("UEHelpers")
local C = require("hb_common")
local L = require("hb_loadout")
local H = require("hb_hunt")

local Log, Valid, HostPawn, Exec = C.Log, C.Valid, C.HostPawn, C.Exec
local TeamSuspect, TeamSwatBlue, TeamSquad, CoopMode = C.TeamSuspect, C.TeamSwatBlue, C.TeamSquad, C.CoopMode
local Worlds, TrackWorld, WorldTime = C.Worlds, C.TrackWorld, C.WorldTime
local DownReason, IsDown, Location, Distance, LivingSwat = C.DownReason, C.IsDown, C.Location, C.Distance, C.LivingSwat
local Banner, Toast, Clock = C.Banner, C.Toast, C.Clock
local EquipSuspectLoadout = L.EquipSuspectLoadout

local Solo = {}

---------------------------------------------------------------- suspect side vs AI SWAT (bots)

-- The game's bot spawners (SpawnBotsForGame, SpawnAI, StartSwatAutomation) are empty in the shipping
-- build, so the bots are the AI SWAT squad of a co-op mission. With the host's PlayerState.Team and
-- pawn DefaultTeam set to TT_SUSPECT, CyberneticController::IsCharacterEnemy flips: AI SWAT treat the
-- host as an enemy, AI suspects as an ally, civilians as a threat (docs/re-findings.md).

local Suspect = {
    Active = false,
    MovedInWorld = nil, -- world generation in which the host was moved to the suspects
    Pawn = nil,         -- address of the host pawn last seen
}

-- AI SWAT know the suspect host as an enemy and track the host, but their rules of engagement never clear
-- a player target for fire. The director orders short scripted bursts
-- (BaseCombatActivity::ScriptedFireAtActor) from every AI SWAT that can see the host.
local Bots = {
    Accuracy = 2.0, -- AccuracyPenaltyMultiplier: 1 = the AI's normal aim, higher = worse
    Burst = 0.7,    -- seconds of fire per order; orders repeat every 0.5 s while the host is visible
}

local function SetHostSuspect()
    local controller = UEHelpers.GetPlayerController()
    local pawn = HostPawn()
    if not Valid(controller) or not Valid(pawn) then return false end
    local playerState = controller.PlayerState
    if not Valid(playerState) then return false end
    if playerState.Team ~= TeamSuspect then
        playerState.Team = TeamSuspect
        pcall(function() playerState:OnRep_Team() end)
    end
    if pawn.DefaultTeam ~= TeamSuspect then
        pawn.DefaultTeam = TeamSuspect
    end
    return true
end

-- Starts the host among the AI suspects instead of next to the SWAT van (see C.PlaceNextToSuspect).
local function MoveHostToSuspects(avoid)
    return C.PlaceNextToSuspect(HostPawn(), avoid)
end

-- The co-op squad waits for orders; a token hit from the host makes every living AI SWAT track the
-- host as its target (they then demand surrender and fire when threatened).
local function AlertSwat()
    local pawn = HostPawn()
    local controller = UEHelpers.GetPlayerController()
    local statics = UEHelpers.GetGameplayStatics()
    local alerted = 0
    for _, character in ipairs(LivingSwat()) do
        local enemy = false
        pcall(function() enemy = character.Controller:IsCharacterEnemy(pawn) end)
        if enemy then
            statics:ApplyDamage(character, 1.0, controller, pawn, nil)
            alerted = alerted + 1
        end
    end
    return alerted
end

-- Spawning happens as SWAT: a co-op map has no player starts for the suspect team, and a missing
-- start spot aborts the game ("Couldn't spawn player"). The suspect side is applied to a living pawn.
local function ResetHostTeamForSpawn()
    local controller = UEHelpers.GetPlayerController()
    local playerState = Valid(controller) and controller.PlayerState or nil
    if Valid(playerState) and playerState.Team ~= TeamSwatBlue then
        playerState.Team = TeamSwatBlue
        pcall(function() playerState:OnRep_Team() end)
    end
end

local function SuspectTick()
    if not Suspect.Active then return end
    local pawn = HostPawn()
    if not Valid(pawn) then return end
    local address = pawn:GetAddress()
    if address ~= Suspect.Pawn then
        Suspect.Pawn = address
        Log("host pawn: %s %s", pawn:GetClass():GetFName():ToString(), tostring(DownReason(pawn) or "alive"))
    end
    -- Before the first spawn the controller possesses a spectator pawn, which is not a character.
    local isCharacter, dead = pcall(function() return pawn:IsDeadOrUnconscious() end)
    if not isCharacter then return end
    if dead then
        ResetHostTeamForSpawn()
        Suspect.MovedInWorld = nil -- move back to the suspects after the respawn
        return
    end
    if not SetHostSuspect() then return end
    C.HideSquadHud()
    if Suspect.MovedInWorld ~= Worlds.Generation and MoveHostToSuspects() then
        Suspect.MovedInWorld = Worlds.Generation
        L.ApplySuspectOutfit(UEHelpers.GetPlayerController().PlayerState, UEHelpers.GetGameModeBase())
        Log("you play as a suspect: AI suspects are your team, the AI SWAT squad is the enemy")
    end
end

---------------------------------------------------------------- rounds against the AI SWAT

-- A match is a series of rounds on one co-op mission; the mission reloads for every round and the
-- score lives here (the Lua state survives map loads). The host wins a round by taking out the AI
-- SWAT squad or by holding out for the round time; the squad wins by taking the host down.
local Match = {
    Active = false,
    Level = nil,
    RoundsToWin = 3,
    RoundTime = 240, -- seconds of assault the host has to survive
    PrepTime = 20,   -- seconds before the squad moves in
    Round = 0,
    Suspects = 0,
    Swat = 0,
    Phase = "idle",  -- loading, prep, live, ended, over (match decided), result (shown, a new match follows)
    PhaseEnds = 0,   -- world time
    World = nil,     -- world generation of the running round
    LoadedFrom = nil,
    Final = false,   -- the reload after the deciding round shows the result first
    Winner = nil,
    LastResult = nil,
    ReadyAsked = 0,
    Warned = {},
}

local function BotsMayFire()
    return Suspect.Active and not Match.Final and Match.Phase ~= "over"
end

local function DirectSwatFire()
    if not BotsMayFire() then return end
    local pawn = HostPawn()
    if IsDown(pawn) or pawn.DefaultTeam ~= TeamSuspect then return end
    for _, character in ipairs(LivingSwat()) do
        pcall(function()
            local ai = character.Controller
            if ai:IsCharacterEnemy(pawn) and ai.TargetingComponent:CanCharacterBeSeen(pawn) then
                ai.CombatActivity:ScriptedFireAtActor(pawn, Bots.Burst, true, Bots.Accuracy, false)
            end
        end)
    end
end

-- Every round reloads the mission, which brings the pre-mission screen back; the host is readied the
-- way its Ready button does it.
local function SkipPreMission(now)
    if now - Match.ReadyAsked < 8 then return end -- bReady follows ReadyUp about 4 s later
    local controller = UEHelpers.GetPlayerController()
    if not Valid(controller) then return end
    local playerState = controller.PlayerState
    if Valid(playerState) and playerState.bReady then return end
    for _, widget in ipairs(FindAllOf("W_PreMission_C") or {}) do
        if widget:IsValid() and widget:IsInViewport() then
            Match.ReadyAsked = now
            local ok, err = pcall(function() controller:ReadyUp() end)
            Log("pre-mission screen: ready up %s", ok and "sent" or ("failed: " .. tostring(err)))
            return
        end
    end
end

local function ScoreLine()
    return string.format("Подозреваемые %d : %d SWAT", Match.Suspects, Match.Swat)
end

local function LoadRound(final)
    TrackWorld()
    ResetHostTeamForSpawn()
    Suspect.Active = true
    Suspect.MovedInWorld = Worlds.Generation -- move once the reloaded mission is up
    Match.Final = final
    Match.Phase = "loading"
    Match.LoadedFrom = Worlds.Generation
    Match.ReadyAsked = -math.huge
    Exec(string.format("open %s?game=%s", Match.Level, CoopMode))
end

local function BeginRound(now, pawn)
    local swat = LivingSwat()
    if #swat == 0 then
        Banner("HostBrain: на этой карте нет отряда ИИ SWAT, матч остановлен")
        Match.Active, Match.Phase = false, "idle"
        return
    end
    local manager = H.SquadManager()
    if manager then H.Lead(manager, swat, { pawn }) end
    local weapons = EquipSuspectLoadout(pawn)
    Match.World = Worlds.Generation
    Match.Phase, Match.PhaseEnds = "prep", now + Match.PrepTime
    Banner(string.format("Раунд %d · %s", Match.Round, ScoreLine()))
    if Match.LastResult then Toast(Match.LastResult) end
    Toast(string.format("Оружие: %s. Отряд SWAT (%d) начнёт штурм через %d с", weapons or "прежнее", #swat, Match.PrepTime))
end

local function GoLive(now)
    Match.Phase, Match.PhaseEnds, Match.Warned = "live", now + Match.RoundTime, {}
    H.Reset(now)
    Banner(string.format("SWAT пошёл на штурм! Продержитесь %s или уничтожьте отряд", Clock(Match.RoundTime)))
end

local function EndRound(now, suspectsWon, reason)
    if suspectsWon then Match.Suspects = Match.Suspects + 1 else Match.Swat = Match.Swat + 1 end
    Match.LastResult = string.format("Раунд %d: %s (%s). %s", Match.Round,
        suspectsWon and "победа подозреваемых" or "победа SWAT", reason, ScoreLine())
    Banner(Match.LastResult)
    if Match.Suspects >= Match.RoundsToWin or Match.Swat >= Match.RoundsToWin then
        Match.Winner = Match.Suspects >= Match.RoundsToWin and "подозреваемые" or "SWAT"
        Banner(string.format("Матч окончен: победили %s. %s", Match.Winner, ScoreLine()))
        Match.Phase = "over"
    else
        Match.Phase = "ended"
    end
    Match.PhaseEnds = now + 7
end

-- The deciding round may end on the death screen, so the result is shown again in the reloaded
-- mission, and a new match starts there after a short pause (comp_suspect off leaves).
local function FinishMatch(now)
    local manager, swat = H.SquadManager(), LivingSwat()
    if manager then H.Lead(manager, swat, { HostPawn() }) end -- the squad stops following the host
    Banner(string.format("Матч окончен: победили %s. %s", Match.Winner, ScoreLine()))
    Toast(string.format("Новый матч до %d побед через 8 с. Выйти из режима: comp_suspect off", Match.RoundsToWin))
    Match.Round, Match.Suspects, Match.Swat, Match.Final = 1, 0, 0, false
    Match.Winner, Match.LastResult = nil, nil
    Match.World, Match.Phase, Match.PhaseEnds = Worlds.Generation, "result", now + 8
end

local function RoundTick()
    if not Match.Active then return end
    local now = WorldTime()
    local pawn = HostPawn()
    if Match.Phase == "loading" then
        if Worlds.Generation == Match.LoadedFrom then return end -- the old mission is still up
        SkipPreMission(now)
        if Suspect.MovedInWorld ~= Worlds.Generation or IsDown(pawn) then return end
        if Match.Final then FinishMatch(now) else BeginRound(now, pawn) end
        return
    end
    if Worlds.Generation ~= Match.World then
        Log("the round's mission was left; match stopped")
        Match.Active, Match.Phase = false, "idle"
        return
    end
    if Match.Phase == "result" then
        if now >= Match.PhaseEnds and not IsDown(pawn) then BeginRound(now, pawn) end
    elseif Match.Phase == "prep" or Match.Phase == "live" then
        -- No pawn at all is a controller between pawns; a death leaves a DeadSpectator_C pawn.
        if not pawn then return end
        local swat = LivingSwat()
        if IsDown(pawn) then
            Log("host is out: %s", DownReason(pawn))
            EndRound(now, false, "подозреваемый нейтрализован")
        elseif #swat == 0 then
            EndRound(now, true, "отряд SWAT уничтожен")
        elseif Match.Phase == "prep" then
            if now >= Match.PhaseEnds then GoLive(now) end
        elseif now >= Match.PhaseEnds then
            EndRound(now, true, "время штурма вышло")
        else
            H.Direct(now, { pawn }, swat)
            local left = Match.PhaseEnds - now
            for _, mark in ipairs({ 60, 30 }) do
                if left <= mark and not Match.Warned[mark] then
                    Match.Warned[mark] = true
                    Toast(string.format("До конца штурма %d с · SWAT осталось: %d", mark, #swat))
                end
            end
        end
    elseif now >= Match.PhaseEnds then -- ended / over
        if Match.Phase == "ended" then Match.Round = Match.Round + 1 end
        LoadRound(Match.Phase == "over")
    end
end

local function StopMatch()
    Match.Active, Match.Phase, Match.Final = false, "idle", false
end

---------------------------------------------------------------- commands

-- Console commands of the solo mode; deps gives EnsureGuards(), ResolveMap(name) and StopOtherModes()
-- from main.lua.
function Solo.RegisterCommands(Register, deps)
    Register("comp_play_suspect", function(parts, out)
        local level = deps.ResolveMap(parts[1] or "campus")
        if not deps.EnsureGuards() then
            out("refusing to start: the round-reset crash guard is not installed")
            return
        end
        local rounds = tonumber(parts[2] or "")
        if rounds and rounds >= 1 then Match.RoundsToWin = math.floor(rounds) end
        Match.Active, Match.Level, Match.Round, Match.Suspects, Match.Swat = true, level, 1, 0, 0
        Match.LastResult, Match.Winner = nil, nil
        deps.StopOtherModes()
        out(string.format("HostBrain: %s, you are a suspect against the AI SWAT squad, first to %d rounds", level, Match.RoundsToWin))
        LoadRound(false)
    end)
    Register("comp_suspect", function(parts, out)
        -- comp_suspect: join the suspects and move next to one; "here": join without moving; "off": stop.
        StopMatch()
        TrackWorld()
        Suspect.Active = parts[1] ~= "off"
        if Suspect.Active then deps.StopOtherModes() end
        Suspect.MovedInWorld = parts[1] == "here" and Worlds.Generation or nil
        if not Suspect.Active then ResetHostTeamForSpawn() end
        out(Suspect.Active and "suspect side on: applied as soon as you have a living pawn" or "suspect side off")
    end)
    Register("comp_round_time", function(parts, out)
        local value = tonumber(parts[1] or "")
        if value and value >= 30 then Match.RoundTime = math.floor(value) end
        local prep = tonumber(parts[2] or "")
        if prep and prep >= 0 then Match.PrepTime = math.floor(prep) end
        out(string.format("round: %ds of assault after %ds of preparation (from the next round)", Match.RoundTime, Match.PrepTime))
    end)
    Register("comp_bot_hints", function(parts, out)
        if parts[1] then H.Settings.Hints = parts[1] ~= "0" end
        out(string.format("AI SWAT hints: %s (after %ds without contact the squad gets an area within %dm of you)",
            H.Settings.Hints and "on" or "off", H.Settings.HintAfter, H.Settings.HintSpread // 100))
    end)
    Register("comp_unstuck", function(_, out)
        local pawn = HostPawn()
        if not Suspect.Active or IsDown(pawn) then
            out("comp_unstuck works for a living suspect host")
            return
        end
        out(MoveHostToSuspects(Location(pawn)) and "moved to a free spot next to the AI suspects" or "no free spot found next to the AI suspects")
    end)
    Register("comp_alert", function(_, out)
        out(string.format("%d AI SWAT are now hunting you", AlertSwat()))
    end)
    Register("comp_bot_accuracy", function(parts, out)
        local value = tonumber(parts[1] or "")
        if value and value > 0 then Bots.Accuracy = value end
        out(string.format("AI SWAT accuracy penalty: %.2f (1 = normal aim, higher = worse)", Bots.Accuracy))
    end)
end

function Solo.Status(out)
    if Match.Active or Match.Phase ~= "idle" then
        out(string.format("suspect match on %s: round %d, phase %s, suspects %d : %d SWAT (first to %d), round time %ds, prep %ds, hints %s",
            tostring(Match.Level), Match.Round, Match.Phase, Match.Suspects, Match.Swat, Match.RoundsToWin,
            Match.RoundTime, Match.PrepTime, H.Settings.Hints and "on" or "off"))
    end
end

function Solo.Active()
    return Suspect.Active or Match.Active
end

-- Leaves the solo mode altogether (another mode starts).
function Solo.Stop()
    Suspect.Active = false
    StopMatch()
end

function Solo.Tick()
    local ok, err = pcall(SuspectTick)
    if not ok then Log("suspect tick failed: %s", tostring(err)) end
    ok, err = pcall(RoundTick)
    if not ok then Log("round tick failed: %s", tostring(err)) end
end

function Solo.FireTick()
    local ok, err = pcall(DirectSwatFire)
    if not ok then Log("bot director failed: %s", tostring(err)) end
end

return Solo
