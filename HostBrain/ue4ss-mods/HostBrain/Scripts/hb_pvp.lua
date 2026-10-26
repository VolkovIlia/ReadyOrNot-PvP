-- HostBrain PvP: SWAT players against suspect players in a co-op mission.
--
-- It stands on the game's hidden co-op PvP (CoopGS.bCrouchingTigerHiddenDragon, docs/re-findings.md):
-- the flag replicates, and every game instance then judges friend and foe by team, keeps team view and
-- spectating within a team and drops the SWAT radio chatter. The console commands that switched it on
-- (a.Ron.PVP.Start/Unlock) are empty in the shipping build, so HostBrain sets the flag and adds the
-- rules of the mode:
--   * teams are chosen on the pre-mission screen (host command comp_pvp_team, chat !swat / !suspect);
--   * a suspect player takes an AI suspect's place at the start and, after every death, takes over
--     another living AI suspect that no SWAT can see, while any are left; suspects carry suspect guns
--     and clothes, no armour and no SWAT gear;
--   * SWAT win by the mission rules (every AI suspect and suspect player out, nobody left to take
--     over); suspects win by taking out every SWAT player or by holding out for the time limit.
--
-- Everybody spawns as SWAT: co-op maps have no suspect starts, and the mission start spawns the AI
-- squad around the host's pawn, so a host without a pawn crashes the game (ACoopGM friendly-AI spawn,
-- docs/re-findings.md). A suspect player's new pawn is moved onto the chosen AI suspect's spot in the
-- frame it appears (Pvp.FrameTick), and that AI leaves the mission.

local UEHelpers = require("UEHelpers")
local C = require("hb_common")
local L = require("hb_loadout")

local Log, Valid, Exec = C.Log, C.Valid, C.Exec
local TeamSwatRed, TeamSwatBlue, TeamSuspect, CoopMode = C.TeamSwatRed, C.TeamSwatBlue, C.TeamSuspect, C.CoopMode
local IsDown, Location, Distance, LivingSwat, TraceBlocked = C.IsDown, C.Location, C.Distance, C.LivingSwat, C.TraceBlocked

local Pvp = {}
local Deps = {} -- from main.lua (Pvp.RegisterCommands)

local Settings = {
    Bots = false,        -- keep the AI SWAT squad (only single-player missions have one; "bots" to try)
    Minutes = 15,        -- suspects win when they hold out this long
    RespawnDelay = 10,   -- seconds from a suspect player's death to taking over an AI suspect
    SafeDistance = 1000, -- cm: an AI suspect this close to a SWAT is not taken over
    BotAccuracy = 2.0,   -- AI SWAT aim penalty against suspect players (1 = normal aim)
    Test = false,        -- start even without one of the sides (testing alone)
}

local Match = {
    Active = false,
    Phase = "idle",   -- travel, briefing (pre-mission screen), live, ended
    TravelFrom = nil, -- world generation the server travel started from
    World = nil,      -- world generation of the mission
    StartedAt = 0,
    EndsAt = 0,
    Teams = {},       -- player name -> team chosen for the next mission
    Suspects = {},    -- player name -> true: plays a suspect in this mission
    Converts = {},    -- player name -> { Ai, Spot, Yaw, Weapons }: the next pawn takes this AI's place
    Deaths = {},      -- player name -> { At, Where, Told } while waiting to take over an AI suspect
    Stripped = {},    -- pawn address -> true once its SWAT gear is gone
    Removed = {},     -- address -> true for AI suspects taken over (gone at the end of the frame)
    LastRoster = -math.huge,
    Bots = false,      -- this mission has the AI squad (Settings.Bots and a SWAT host)
    SquadSeen = false, -- the AI squad spawns a little after the players
    Warned = {},
    Winner = nil,
}

---------------------------------------------------------------- players and messages

-- Every human player: { Controller, State, Name, Team, Pawn (a living character or nil) }.
local function Players()
    local list = {}
    for _, controller in ipairs(FindAllOf("ReadyOrNotPlayerController") or {}) do
        if Valid(controller) and Valid(controller.PlayerState) then
            local state = controller.PlayerState
            local ok, name = pcall(function() return state:GetPlayerName():ToString() end)
            local pawn = controller.Pawn
            list[#list + 1] = {
                Controller = controller,
                State = state,
                Name = ok and name or "?",
                Team = state.Team,
                Pawn = (Valid(pawn) and not IsDown(pawn)) and pawn or nil,
            }
        end
    end
    return list
end

local function IsSwatTeam(team)
    return team == TeamSwatBlue or team == TeamSwatRed
end

local function ChatMessage(text, color)
    return { SenderName = "HostBrain", Message = text, Color = color or { R = 1.0, G = 0.75, B = 0.2, A = 1.0 } }
end

-- A line in everyone's chat (and on the host's HUD).
local function Say(text)
    local gameState = UEHelpers.GetGameStateBase()
    if Valid(gameState) then pcall(function() gameState:Multicast_BroadcastChatMessage(ChatMessage(text)) end) end
    C.Toast(text)
end

-- A line in one player's chat.
local function Tell(player, text)
    Log("to %s: %s", player.Name, text)
    pcall(function() player.Controller:Client_SendChatMessage(ChatMessage(text, { R = 0.6, G = 0.9, B = 1.0, A = 1.0 })) end)
    local host = UEHelpers.GetPlayerController()
    if Valid(host) and player.Controller:GetAddress() == host:GetAddress() then C.Toast(text) end
end

local function TeamName(team)
    return team == TeamSuspect and "подозреваемые" or "SWAT"
end

local function Roster(players)
    local swat, suspects = {}, {}
    for _, player in ipairs(players) do
        local wanted = Match.Teams[player.Name] or (Match.Suspects[player.Name] and TeamSuspect) or player.Team
        if wanted == TeamSuspect then suspects[#suspects + 1] = player.Name else swat[#swat + 1] = player.Name end
    end
    return string.format("SWAT: %s · Подозреваемые: %s", #swat > 0 and table.concat(swat, ", ") or "—",
        #suspects > 0 and table.concat(suspects, ", ") or "—")
end

---------------------------------------------------------------- the game's PvP switches

-- With the hidden PvP flag set before the mission starts, the mission comes without its AI SWAT squad
-- (CoopGS handles "PvP actors", DT_ActorsToHandleInPvP). With bots the flag waits until the squad
-- has spawned.
local function EnablePvpFlags()
    local gameState = UEHelpers.GetGameStateBase()
    local bots = Match.Phase == "live" and Match.Bots or Settings.Bots
    local waitForSquad = bots and not (Match.Phase == "live" and Match.SquadSeen)
    if Valid(gameState) and not waitForSquad then
        local ok, enabled = pcall(function() return gameState.bCrouchingTigerHiddenDragon end)
        if ok and enabled == false then
            gameState.bCrouchingTigerHiddenDragon = true
            pcall(function() gameState:OnRep_CrouchingTigerHiddenDragon() end)
            Log("hidden co-op PvP switched on (CoopGS.bCrouchingTigerHiddenDragon)")
        end
    end
    local gameMode = UEHelpers.GetGameModeBase()
    if Valid(gameMode) then pcall(function() gameMode.bSpectateKillerOnDeath = false end) end
end

-- In a running mission the team is written directly (the game's Server_SetTeamType only works on the
-- pre-mission screen).
local function SetTeam(player, team)
    if player.State.Team == team then return end
    player.State.Team = team
    pcall(function() player.State:OnRep_Team() end)
end

---------------------------------------------------------------- taking over AI suspects

local function LivingAiSuspects()
    local list = {}
    for _, character in ipairs(FindAllOf("CyberneticsSuspect_V2_C") or {}) do
        if not IsDown(character) and not Match.Removed[tostring(character:GetAddress())] then list[#list + 1] = character end
    end
    return list
end

local function RemoveAi(ai)
    Match.Removed[tostring(ai:GetAddress())] = true
    ai:K2_DestroyActor()
end

-- Everyone fighting for SWAT: SWAT player pawns and the AI squad.
local function SwatBodies(players)
    local bodies = {}
    for _, player in ipairs(players) do
        if not Match.Suspects[player.Name] and player.Pawn then bodies[#bodies + 1] = player.Pawn end
    end
    for _, ai in ipairs(LivingSwat()) do bodies[#bodies + 1] = ai end
    return bodies
end

local function Reserved(ai)
    local address = ai:GetAddress()
    for _, convert in pairs(Match.Converts) do
        if Valid(convert.Ai) and convert.Ai:GetAddress() == address then return true end
    end
    return false
end

-- An AI suspect to take over: no SWAT within SafeDistance and none with a line of sight to it,
-- nearest to where the player fell. Without such a one the line of sight is dropped; an AI right next
-- to SWAT is never taken, nor one another player is about to take.
local function ChooseAi(players, near)
    local swat = SwatBodies(players)
    local best, bestScore, fallback, fallbackScore = nil, math.huge, nil, math.huge
    for _, ai in ipairs(LivingAiSuspects()) do
        if not Reserved(ai) then
            local at = Location(ai)
            local safe, hidden = true, true
            for _, body in ipairs(swat) do
                local from = Location(body)
                if Distance(at, from) < Settings.SafeDistance then safe = false break end
                if hidden and TraceBlocked({ X = from.X, Y = from.Y, Z = from.Z + 60 }, { X = at.X, Y = at.Y, Z = at.Z + 60 }, { body, ai }) == false then
                    hidden = false
                end
            end
            if safe then
                local score = near and Distance(at, near) or math.random() * 1e6
                if hidden and score < bestScore then best, bestScore = ai, score end
                if score < fallbackScore then fallback, fallbackScore = ai, score end
            end
        end
    end
    return best or fallback
end

-- Books an AI suspect for the player's next pawn and gives that spawn the suspect kit (the game spawns
-- a player with PlayerState.ServerSavedLoadout).
local function Book(player, ai)
    local primary, secondary = L.GunsFor(ai)
    local weapons = L.PrepareSuspectSpawn(player.State, primary, secondary, UEHelpers.GetGameModeBase())
    Match.Converts[player.Name] = {
        Ai = ai, Spot = Location(ai), Yaw = ai:K2_GetActorRotation().Yaw,
        Primary = primary, Secondary = secondary, Weapons = weapons,
    }
    return weapons
end

local function PlaceAt(pawn, spot, yaw)
    local ok, moved = pcall(function()
        return pawn:K2_TeleportTo({ X = spot.X, Y = spot.Y, Z = spot.Z + 10 }, { Pitch = 0, Yaw = yaw, Roll = 0 })
    end)
    if not (ok and moved) then C.PlaceNextToSuspect(pawn) end
end

-- The player's new pawn takes the booked AI's place: the AI leaves, the pawn turns suspect and loses
-- the SWAT gear. The game can move a fresh pawn once more after its spawn frame, so the spot is
-- checked again shortly after.
local function Convert(player, convert)
    local pawn = player.Pawn
    Match.Converts[player.Name] = nil
    local spot, yaw = convert.Spot, convert.Yaw
    if Valid(convert.Ai) and not IsDown(convert.Ai) then
        spot, yaw = Location(convert.Ai), convert.Ai:K2_GetActorRotation().Yaw
        RemoveAi(convert.Ai)
    end
    PlaceAt(pawn, spot, yaw)
    SetTeam(player, TeamSuspect)
    pawn.DefaultTeam = TeamSuspect
    L.EquipSuspectKit(pawn, convert.Primary, convert.Secondary)
    local stripped = L.StripSwatGear(pawn)
    pcall(L.FillMagazines, pawn)
    Match.Stripped[tostring(pawn:GetAddress())] = true
    Match.Suspects[player.Name] = true
    Match.Deaths[player.Name] = nil
    Log("%s took an AI suspect's place (%s, %d SWAT items removed)", player.Name, convert.Weapons or "?", stripped)
    Tell(player, string.format("Вы — подозреваемый: %s. ИИ-подозреваемых в запасе: %d", convert.Weapons or "оружие подозреваемого", #LivingAiSuspects()))
    ExecuteInGameThreadWithDelay(300, function()
        if Valid(pawn) and not IsDown(pawn) and Distance(Location(pawn), spot) > 300 then
            PlaceAt(pawn, spot, yaw)
            Log("%s re-placed onto the AI suspect's spot", player.Name)
        end
    end)
end

local function HasLivingPawn(controller)
    local pawn = controller.Pawn
    return Valid(pawn) and not IsDown(pawn)
end

-- After a suspect player's death the player's new character is spawned right on the AI suspect's spot
-- (ReadyOrNotGameMode::SpawnPlayerCharacter possesses it and takes the team and the prepared
-- ServerSavedLoadout). RespawnPlayer is no use here: in the hidden co-op PvP a killed player comes back
-- as a spectator (a.Ron.PVP.ForceRespawnAsSpectatorWhenKilled = 1, a cheat cvar in shipping).
local function TakeOver(player, ai)
    local gameMode = UEHelpers.GetGameModeBase()
    Book(player, ai)
    local convert = Match.Converts[player.Name]
    Match.Converts[player.Name] = nil
    local spot, yaw = Location(ai), ai:K2_GetActorRotation().Yaw
    RemoveAi(ai)
    SetTeam(player, TeamSuspect)
    local ok, pawn = pcall(function()
        local transform = UEHelpers.GetKismetMathLibrary():MakeTransform({ X = spot.X, Y = spot.Y, Z = spot.Z + 10 },
            { Pitch = 0, Yaw = yaw, Roll = 0 }, { X = 1, Y = 1, Z = 1 })
        return gameMode:SpawnPlayerCharacter(player.Controller, gameMode.DefaultPawnClass, transform, true)
    end)
    if not ok or not Valid(pawn) or not HasLivingPawn(player.Controller) then
        Log("takeover of an AI suspect for %s failed: %s", player.Name, ok and "no character spawned" or tostring(pawn))
        return false
    end
    pcall(function()
        -- the dead player's spectator camera (not the body) is no longer needed
        local spectator = player.Controller.DeadSpectatorPawn
        if Valid(spectator) and spectator:GetAddress() ~= pawn:GetAddress() then spectator:K2_DestroyActor() end
    end)
    pawn.DefaultTeam = TeamSuspect
    L.EquipSuspectKit(pawn, convert.Primary, convert.Secondary)
    local stripped = L.StripSwatGear(pawn)
    pcall(L.FillMagazines, pawn)
    Match.Stripped[tostring(pawn:GetAddress())] = true
    Match.Deaths[player.Name] = nil
    Log("%s took over an AI suspect (%s, %d SWAT items removed)", player.Name, convert.Weapons, stripped)
    Tell(player, string.format("Вы — подозреваемый: %s. ИИ-подозреваемых в запасе: %d", convert.Weapons, #LivingAiSuspects()))
    return true
end

---------------------------------------------------------------- AI SWAT against suspect players

-- AI SWAT never clear a player suspect for fire by themselves (docs/re-findings.md); the ones that
-- see a suspect player get short scripted bursts, as in the solo mode.
local function DirectSwatFire(players)
    local targets = {}
    for _, player in ipairs(players) do
        if player.Team == TeamSuspect and player.Pawn then targets[#targets + 1] = player.Pawn end
    end
    if #targets == 0 then return end
    for _, ai in ipairs(LivingSwat()) do
        pcall(function()
            local controller = ai.Controller
            for _, pawn in ipairs(targets) do
                if controller:IsCharacterEnemy(pawn) and controller.TargetingComponent:CanCharacterBeSeen(pawn) then
                    controller.CombatActivity:ScriptedFireAtActor(pawn, 0.7, true, Settings.BotAccuracy, false)
                    break
                end
            end
        end)
    end
end

-- The AI squad follows its leader; it must never follow a suspect player.
local function KeepSquadOnSwat(players)
    local manager = FindFirstOf("SWATManager")
    if not Valid(manager) then return end
    local leader = manager.SquadLeader
    if Valid(leader) and not IsDown(leader) then
        local address = leader:GetAddress()
        local leaderIsSuspect = false
        for _, player in ipairs(players) do
            if player.Pawn and player.Pawn:GetAddress() == address and Match.Suspects[player.Name] then leaderIsSuspect = true end
        end
        if not leaderIsSuspect then return end
    end
    for _, player in ipairs(players) do
        if not Match.Suspects[player.Name] and player.Pawn then manager.SquadLeader = player.Pawn return end
    end
    local swat = LivingSwat()
    if #swat > 0 then manager.SquadLeader = swat[1] end
end

---------------------------------------------------------------- match flow

local function EndMatch(swatWon, reason)
    Match.Phase = "ended"
    Match.Winner = swatWon and "SWAT" or "подозреваемые"
    local text = string.format("Победа %s: %s", swatWon and "SWAT" or "подозреваемых", reason)
    Say(text)
    C.Banner(text)
    local gameMode = UEHelpers.GetGameModeBase()
    local ended = pcall(function() gameMode:MissionEnd(swatWon) end)
    if not ended then pcall(function() gameMode:StartMissionEndTimer(swatWon) end) end
    Log("mission end requested (%s)", ended and "MissionEnd" or "StartMissionEndTimer")
end

local function StartLive(now, players)
    local swatPlayers, suspectPlayers = 0, 0
    for _, player in ipairs(players) do
        if Match.Suspects[player.Name] then suspectPlayers = suspectPlayers + 1 else swatPlayers = swatPlayers + 1 end
    end
    if suspectPlayers == 0 and not Settings.Test then
        Say("PvP: никто не выбрал подозреваемых — идёт обычная миссия")
        Match.Active, Match.Phase = false, "idle"
        return
    end
    -- The AI squad is the host's: it spawns around the host and follows the host, so it only plays
    -- for SWAT when the host does.
    local host = UEHelpers.GetPlayerController()
    local hostSuspect = false
    for _, player in ipairs(players) do
        if Match.Suspects[player.Name] and Valid(host) and player.Controller:GetAddress() == host:GetAddress() then hostSuspect = true end
    end
    Match.Bots = Settings.Bots and not hostSuspect
    if Settings.Bots and hostSuspect then
        Say("PvP: ИИ-отряд SWAT ходит за хостом, а хост играет за подозреваемых — боты выключены")
    end
    if suspectPlayers == 0 and Settings.Test then
        Say("PvP (тест): без подозреваемых")
    end
    if swatPlayers == 0 and not Match.Bots and not Settings.Test then
        Say("PvP: нет ни игроков SWAT, ни ботов — режим выключен")
        Match.Active, Match.Phase = false, "idle"
        return
    end
    if not Match.Bots then
        pcall(function() UEHelpers.GetPlayerController():DestroySwatTeam() end)
        Log("AI SWAT squad removed (bots off)")
    end
    if Deps.FilterInstalled and not Deps.FilterInstalled() then
        Say("PvP: фильтр SWAT-действий не установлен — подозреваемые смогут связывать гражданских (см. лог HostBrain)")
    end
    Match.Phase, Match.StartedAt, Match.EndsAt = "live", now, now + Settings.Minutes * 60
    Match.Deaths, Match.Warned, Match.Winner, Match.SquadSeen = {}, {}, nil, false
    for _, player in ipairs(players) do
        -- a suspect whose booking was lost (AI gone, ready state missed) takes over now
        if Match.Suspects[player.Name] and not Match.Converts[player.Name] and player.Team ~= TeamSuspect then
            Match.Deaths[player.Name] = { At = now - Settings.RespawnDelay, Told = true }
        end
    end
    Say(string.format("PvP начался: %d мин. Подозреваемые побеждают, если положат всех SWAT или продержатся; SWAT — если нейтрализует всех подозреваемых. Убитый подозреваемый через %d с вселяется в ИИ-подозреваемого. %s",
        Settings.Minutes, Settings.RespawnDelay, Match.Bots and "ИИ-отряд SWAT в игре." or "Без ИИ-отряда SWAT."))
end

local function BriefingTick(now, players)
    if now - Match.LastRoster >= 20 then
        Match.LastRoster = now
        Say(Roster(players) .. ". Выбор команды в чате: !swat или !suspect")
    end
    -- Once everyone is ready the suspects get their AI suspects booked and their spawn kit set (a
    -- player's own Ready overwrites ServerSavedLoadout, so the kit is put back while it is missing).
    local gameState = UEHelpers.GetGameStateBase()
    local ready = false
    pcall(function() ready = gameState:IsEveryoneReady() end)
    for _, player in ipairs(players) do
        local wantsSuspect = Match.Teams[player.Name] == TeamSuspect
        Match.Suspects[player.Name] = wantsSuspect or nil
        if not wantsSuspect then
            Match.Converts[player.Name] = nil
        elseif ready then
            local convert = Match.Converts[player.Name]
            local armour = nil
            pcall(function() armour = player.State.ServerSavedLoadout.Armor:GetFName():ToString() end)
            if not convert or armour ~= "Armor_NoArmor_C" then
                local ai = (convert and Valid(convert.Ai) and not IsDown(convert.Ai)) and convert.Ai or ChooseAi(players, nil)
                if ai then Book(player, ai) end
            end
        end
    end
    local anyoneSpawned = false
    for _, player in ipairs(players) do
        if player.Pawn then anyoneSpawned = true end
    end
    if anyoneSpawned then StartLive(now, players) end
end

local function LiveTick(now, players)
    if Match.Bots then KeepSquadOnSwat(players) end
    local swatPlayers, swatAlive, suspectAlive, waiting = 0, 0, 0, 0
    local aiLeft = #LivingAiSuspects()
    for _, player in ipairs(players) do
        if Match.Suspects[player.Name] then
            if Match.Converts[player.Name] then
                waiting = waiting + 1
            elseif player.Pawn and player.Team == TeamSuspect then
                suspectAlive = suspectAlive + 1
                local key = tostring(player.Pawn:GetAddress())
                if player.Pawn.DefaultTeam ~= TeamSuspect then player.Pawn.DefaultTeam = TeamSuspect end
                if not Match.Stripped[key] then
                    Match.Stripped[key] = true
                    L.StripSwatGear(player.Pawn)
                end
                Match.Deaths[player.Name] = nil
            else
                local death = Match.Deaths[player.Name]
                if not death then
                    local where = nil
                    pcall(function() where = Location(player.Controller.Pawn) end)
                    death = { At = now, Where = where }
                    Match.Deaths[player.Name] = death
                end
                if not death.Told then
                    death.Told = true
                    if aiLeft > 0 then
                        pcall(function() player.Controller:NotifyRespawnTime(Settings.RespawnDelay) end)
                        Tell(player, string.format("Вселение в ИИ-подозреваемого через %d с (в запасе: %d)", Settings.RespawnDelay, aiLeft))
                    else
                        Tell(player, "ИИ-подозреваемых не осталось — вы наблюдаете за своими до конца миссии")
                    end
                end
                if aiLeft > 0 and now >= death.At + Settings.RespawnDelay then
                    local ai = ChooseAi(players, death.Where)
                    if ai and TakeOver(player, ai) then
                        waiting = waiting + 1
                    else
                        death.At = now -- try again after another delay
                    end
                end
            end
        else
            swatPlayers = swatPlayers + 1
            if player.Pawn then swatAlive = swatAlive + 1 end
        end
    end

    -- everyone and the AI squad need a moment to spawn before anybody can count as out
    local squad = #LivingSwat()
    Match.SquadSeen = Match.SquadSeen or squad > 0
    if Match.Bots and not Match.SquadSeen and now - Match.StartedAt > 30 then
        -- the game only gives a single-player mission its AI squad; a hosted (listen) mission has none
        Match.Bots = false
        Say("PvP: ИИ-отряд SWAT в сетевой миссии не появляется — играем без ботов")
    end
    if now - Match.StartedAt < 10 then return end
    if swatPlayers > 0 and swatAlive == 0 then
        EndMatch(false, "все бойцы SWAT нейтрализованы")
    elseif swatPlayers == 0 and Match.Bots and Match.SquadSeen and squad == 0 then
        EndMatch(false, "ИИ-отряд SWAT уничтожен")
    elseif now >= Match.EndsAt then
        EndMatch(false, "время вышло, подозреваемые продержались")
    elseif aiLeft == 0 and suspectAlive == 0 and waiting == 0 then
        EndMatch(true, "все подозреваемые нейтрализованы")
    else
        local left = Match.EndsAt - now
        for _, mark in ipairs({ 300, 60 }) do
            if left <= mark and not Match.Warned[mark] and Match.EndsAt - Match.StartedAt > mark then
                Match.Warned[mark] = true
                Say(string.format("До конца миссии %s · ИИ-подозреваемых: %d", C.Clock(mark), aiLeft))
            end
        end
    end
end

---------------------------------------------------------------- chat commands

-- Players pick teams in chat on the pre-mission screen: every chat line passes through the host's
-- ReadyOrNotPlayerController::Server_SendChatMessage.
local function OnChat(context, message)
    if not Match.Active then return end
    local ok, controller, text = pcall(function()
        local chat = message:get()
        return context:get(), chat.Message:ToString()
    end)
    if not ok or type(text) ~= "string" then return end
    local command = text:lower():match("^%s*!(%S+)")
    if not command then return end
    local player
    for _, candidate in ipairs(Players()) do
        if candidate.Controller:GetAddress() == controller:GetAddress() then player = candidate end
    end
    if not player then return end
    local team = (command == "swat" or command == "сват") and TeamSwatBlue
        or (command == "suspect" or command == "sus" or command == "подозреваемый") and TeamSuspect or nil
    if team then
        if Match.Phase ~= "briefing" and Match.Phase ~= "travel" then
            Tell(player, "Команду можно сменить только до начала миссии")
            return
        end
        Match.Teams[player.Name] = team
        Say(string.format("%s → %s", player.Name, TeamName(team)))
    elseif command == "teams" or command == "команды" then
        Tell(player, Roster(Players()))
    end
end

local hooked, hookError = pcall(RegisterHook, "/Script/ReadyOrNot.ReadyOrNotPlayerController:Server_SendChatMessage", OnChat)
if not hooked then Log("cannot hook chat: %s", tostring(hookError)) end

---------------------------------------------------------------- interface for main.lua

function Pvp.Tick()
    if not Match.Active then return end
    local now = C.WorldTime()
    if Match.Phase == "travel" then
        if C.Worlds.Generation == Match.TravelFrom then return end
        Match.Phase, Match.World, Match.LastRoster = "briefing", C.Worlds.Generation, -math.huge
        Match.Suspects, Match.Converts, Match.Stripped, Match.Removed = {}, {}, {}, {}
    end
    if Match.World ~= C.Worlds.Generation then
        if Match.Phase == "briefing" then
            -- a travel can pass through a transition world first: follow it until the mission starts
            Match.World, Match.LastRoster = C.Worlds.Generation, -math.huge
            Match.Suspects, Match.Converts, Match.Stripped, Match.Removed = {}, {}, {}, {}
        else
            Log("PvP: the mission was left; mode stopped")
            Match.Active, Match.Phase = false, "idle"
            return
        end
    end
    EnablePvpFlags()
    local players = Players()
    if Match.Phase == "briefing" then
        BriefingTick(now, players)
    elseif Match.Phase == "live" then
        LiveTick(now, players)
    end
end

-- Every frame while a booking waits: the player's new pawn takes the AI's place in its first frame.
function Pvp.FrameTick()
    if not Match.Active or next(Match.Converts) == nil then return end
    for _, player in ipairs(Players()) do
        local convert = Match.Converts[player.Name]
        if convert and player.Pawn and not Match.Stripped[tostring(player.Pawn:GetAddress())] then
            Convert(player, convert)
        end
    end
end

function Pvp.FireTick()
    if Match.Active and Match.Phase == "live" and Match.Bots then DirectSwatFire(Players()) end
end

function Pvp.Stop()
    Match.Active, Match.Phase = false, "idle"
end

function Pvp.Status(out)
    if not Match.Active and Match.Phase == "idle" then return end
    local now = C.WorldTime()
    out(string.format("PvP: phase %s, bots %s, %d min, takeover after %d s, AI suspects left %d%s",
        Match.Phase, Settings.Bots and "on" or "off", Settings.Minutes, Settings.RespawnDelay, #LivingAiSuspects(),
        Match.Phase == "live" and string.format(", %s left", C.Clock(math.max(0, math.floor(Match.EndsAt - now)))) or ""))
    out(Roster(Players()))
end

-- deps: EnsureGuards(), ResolveMap(name), StopOtherModes(), FilterInstalled() from main.lua.
function Pvp.RegisterCommands(Register, deps)
    Deps = deps
    local function ApplySettings(parts, first)
        for i = first, #parts do
            local word = parts[i]:lower()
            if word == "bots" or word == "on" then Settings.Bots = true
            elseif word == "nobots" or word == "off" then Settings.Bots = false
            elseif word == "test" then Settings.Test = true
            elseif tonumber(word) then Settings.Minutes = math.max(1, math.floor(tonumber(word)))
            end
        end
    end
    Register("comp_pvp", function(parts, out)
        -- comp_pvp <map|here> [bots|nobots] [minutes]
        local target = parts[1] or "here"
        deps.StopOtherModes()
        Settings.Test = false
        ApplySettings(parts, 2)
        C.TrackWorld()
        Match.Active = true
        if target == "here" then
            Match.Phase, Match.World, Match.LastRoster = "briefing", C.Worlds.Generation, -math.huge
            Match.Suspects, Match.Converts, Match.Stripped, Match.Removed = {}, {}, {}, {}
            out(string.format("PvP on this mission: %s, %d min; players pick teams with !swat / !suspect before the start",
                Settings.Bots and "with AI SWAT" or "no AI SWAT", Settings.Minutes))
            return
        end
        local level = deps.ResolveMap(target)
        Match.Phase, Match.TravelFrom = "travel", C.Worlds.Generation
        local kismet, world = UEHelpers.GetKismetSystemLibrary(), UEHelpers.GetWorld()
        local hosting = Valid(kismet) and Valid(world) and kismet:IsServer(world) and not kismet:IsStandalone(world)
        out(string.format("PvP on %s: %s, %d min", level, Settings.Bots and "with AI SWAT" or "no AI SWAT", Settings.Minutes))
        if hosting then
            Exec(string.format("servertravel %s?game=%s", level, CoopMode))
        else
            Exec(string.format("open %s?listen?game=%s", level, CoopMode))
        end
    end)
    Register("comp_pvp_team", function(parts, out)
        -- comp_pvp_team <player|me> swat|suspect
        local who, side = parts[1], (parts[2] or ""):lower()
        local team = (side == "swat") and TeamSwatBlue or (side == "suspect" or side == "suspects") and TeamSuspect or nil
        if not who or not team then
            out("usage: comp_pvp_team <player|me> swat|suspect")
            return
        end
        if who == "me" then
            local ok, name = pcall(function() return UEHelpers.GetPlayerController().PlayerState:GetPlayerName():ToString() end)
            who = ok and name or who
        end
        Match.Teams[who] = team
        out(string.format("%s → %s (for the next mission start)", who, TeamName(team)))
    end)
    Register("comp_pvp_time", function(parts, out)
        local minutes, delay = tonumber(parts[1] or ""), tonumber(parts[2] or "")
        if minutes and minutes >= 1 then Settings.Minutes = math.floor(minutes) end
        if delay and delay >= 0 then Settings.RespawnDelay = math.floor(delay) end
        out(string.format("PvP: %d min, takeover %d s after a suspect's death", Settings.Minutes, Settings.RespawnDelay))
    end)
    Register("comp_pvp_bots", function(parts, out)
        if parts[1] then Settings.Bots = parts[1] ~= "0" and parts[1]:lower() ~= "off" end
        local accuracy = tonumber(parts[2] or "")
        if accuracy and accuracy > 0 then Settings.BotAccuracy = accuracy end
        out(string.format("PvP AI SWAT squad: %s, aim penalty %.1f", Settings.Bots and "on" or "off", Settings.BotAccuracy))
    end)
    Register("comp_pvp_status", function(_, out) Pvp.Status(out) end)
    Register("comp_pvp_end", function(_, out)
        Pvp.Stop()
        out("PvP mode off (the hidden co-op PvP flag stays until the mission changes)")
    end)
end

return Pvp
