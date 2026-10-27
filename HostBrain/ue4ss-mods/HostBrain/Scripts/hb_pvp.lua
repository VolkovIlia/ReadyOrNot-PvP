-- HostBrain PvP: SWAT players against suspect players in a co-op mission.
--
-- It stands on the game's hidden co-op PvP (CoopGS.bCrouchingTigerHiddenDragon, docs/re-findings.md):
-- the flag replicates, and every game instance then judges friend and foe by team, keeps team view and
-- spectating within a team and drops the SWAT radio chatter. The console commands that switched it on
-- (a.Ron.PVP.Start/Unlock) are empty in the shipping build, so HostBrain sets the flag and adds the
-- rules of the mode:
--   * teams are chosen on the pre-mission screen (the host's team button, chat !swat / !suspect,
--     host command comp_pvp_team);
--   * a suspect player takes an AI suspect's place at the start and, after every death, takes over
--     another living AI suspect that no SWAT can see, while any are left; suspects carry suspect guns
--     and clothes, no armour and no SWAT gear;
--   * SWAT take a round by the mission rules (every AI suspect and suspect player out, nobody left to
--     take over); suspects take it by taking out every SWAT player or by holding out for the time limit;
--   * a match is played in rounds, as in CS2: the round ends inside the mission (no debriefing), the
--     same mission loads again with a result page on the host's pre-mission screen, the sides swap at
--     halftime and the first side to Settings.RoundsToWin round wins takes the match;
--   * with bots the mission's AI SWAT squad fights for SWAT: it follows a living SWAT player, and with
--     none it hunts the suspect players on its own (hb_hunt), whichever side the host plays.
--
-- Everybody spawns as SWAT: co-op maps have no suspect starts, and the mission start spawns the AI
-- squad around the host's pawn, so a host without a pawn crashes the game (ACoopGM friendly-AI spawn,
-- docs/re-findings.md). A suspect player's new pawn is moved onto the chosen AI suspect's spot in the
-- frame it appears (Pvp.FrameTick), and that AI leaves the mission.

local UEHelpers = require("UEHelpers")
local C = require("hb_common")
local L = require("hb_loadout")
local H = require("hb_hunt")
local Menu = require("hb_menu")

local Log, Valid, Exec = C.Log, C.Valid, C.Exec
local TeamSwatRed, TeamSwatBlue, TeamSuspect, CoopMode = C.TeamSwatRed, C.TeamSwatBlue, C.TeamSuspect, C.CoopMode
local IsDown, Location, Distance, LivingSwat, TraceBlocked = C.IsDown, C.Location, C.Distance, C.LivingSwat, C.TraceBlocked

local Pvp = {}
local Deps = {} -- from main.lua (Pvp.RegisterCommands)

-- The menu's settings are kept in the mod's settings.txt (C.SaveSetting).
local Saved = C.LoadSettings()
local Settings = {
    Auto = Saved.pvp_auto ~= "0",   -- offer the team choice on every co-op mission's pre-mission screen
    Bots = Saved.pvp_bots ~= "0",   -- give SWAT the mission's AI squad
    Minutes = tonumber(Saved.pvp_minutes or "") or 10, -- suspects win a round when they hold out this long
    RoundsToWin = tonumber(Saved.pvp_rounds or "") or 3, -- round wins that take the match
    Swap = Saved.pvp_swap ~= "0",   -- the players change sides at halftime, as in CS2
    BreakSeconds = 6,    -- from a round's end to loading the next round
    ReadyAfter = 8,      -- seconds of the round result before everyone is readied for the next round
    RespawnDelay = 10,   -- seconds from a suspect player's death to taking over an AI suspect
    SafeDistance = 1000, -- cm: an AI suspect this close to a SWAT is not taken over
    BotAccuracy = tonumber(Saved.pvp_bot_accuracy or "") or 2.0, -- AI SWAT aim penalty against suspect players (1 = normal aim)
    Test = false,        -- start even without one of the sides (testing alone)
}

local Match = {
    Active = false,
    Phase = "idle",   -- travel, briefing (pre-mission screen), live, roundover
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
    Bots = false,      -- this mission has the AI squad
    Auto = false,      -- armed by Settings.Auto rather than by comp_pvp
    AutoWorld = nil,   -- world generation Settings.Auto last armed the mode in
    LastRosterText = nil,
    HostWait = nil,    -- world time the host's first pawn started waiting for the squad to spawn
    SquadVariable = nil, -- value last set for a.RonSpawnSwatInIncompatibleMode
    SquadSeen = false, -- the AI squad spawns a little after the players
    Warned = {},
    -- Rounds: every round is the same mission loaded again; the score belongs to the players on each
    -- side and moves with them when the sides swap.
    Round = 1,
    Score = { Swat = 0, Suspects = 0 },
    Result = nil,      -- the last round: { Round, SwatWon, Reason, Final, Swapped, SwatScore, SuspectScore, Winners }
    PageMode = "teams", -- the host's page on the next pre-mission screen: teams, round (result) or final
    BreakEnds = 0,     -- world time the next round starts loading
    BriefedAt = nil,   -- world time the round result first showed on this pre-mission screen
    ReadyAsked = {},   -- player name -> world time the player was last readied for the next round
    TravelAt = 0,      -- world time of the last travel to the next round
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
-- The game spawns the AI squad of a co-op mission only in single player, unless
-- a.RonSpawnSwatInIncompatibleMode is 1 ("always spawn the swat ... even if it's a multiplayer game",
-- not a cheat variable). It is switched off again once the mission has started.
local function SetSquadVariable(on)
    local value = on and 1 or 0
    if Match.SquadVariable == value then return end
    Match.SquadVariable = value
    Exec("a.RonSpawnSwatInIncompatibleMode " .. value)
    Log("AI squad in multiplayer missions: %s", on and "on" or "off")
end

-- State of one mission; teams chosen and settings carry over.
local function ResetMission()
    Match.Suspects, Match.Converts, Match.Stripped, Match.Removed = {}, {}, {}, {}
    Match.SquadSeen, Match.HostWait, Match.LastRoster, Match.LastRosterText = false, nil, -math.huge, nil
    Match.HostConfirmed, Match.HoldTold, Match.BriefedAt, Match.ReadyAsked = false, false, nil, {}
    Menu.Reopen()
end

-- A new match: round 1, no score, the team page.
local function NewMatch()
    Match.Round, Match.Score, Match.Result, Match.PageMode = 1, { Swat = 0, Suspects = 0 }, nil, "teams"
end

local function StopMode()
    Match.Active, Match.Phase = false, "idle"
    NewMatch()
end

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
    L.ApplySuspectOutfit(player.State, UEHelpers.GetGameModeBase())
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
    L.ApplySuspectOutfit(player.State, gameMode)
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

-- The AI squad follows its leader and must never follow a suspect player. A living SWAT player leads
-- it as in co-op; without one an AI SWAT leads and the squad hunts the suspect players on its own.
local function DirectSquad(now, players)
    local swat = LivingSwat()
    local manager = H.SquadManager()
    if #swat == 0 or not manager then return end
    local leaders, targets = {}, {}
    for _, player in ipairs(players) do
        if player.Pawn then
            if Match.Suspects[player.Name] then targets[#targets + 1] = player.Pawn else leaders[#leaders + 1] = player.Pawn end
        end
    end
    if #leaders == 0 then
        H.Lead(manager, swat, targets)
        H.Direct(now, targets, swat)
        return
    end
    local leader = manager.SquadLeader
    if Valid(leader) and not IsDown(leader) then
        for _, pawn in ipairs(leaders) do
            if pawn:GetAddress() == leader:GetAddress() then return end
        end
    end
    manager.SquadLeader = leaders[1]
end

---------------------------------------------------------------- match flow

local function ScoreLine(swat, suspects)
    return string.format("SWAT %d : %d Подозреваемые", swat or Match.Score.Swat, suspects or Match.Score.Suspects)
end

-- A round ends inside the mission, without the game's mission end and its debriefing: the score goes
-- up, everyone gets the result in chat, and after a short pause the mission loads again for the next
-- round (Pvp.Tick), where the host's pre-mission screen shows the result page.
local function EndRound(now, players, swatWon, reason)
    if swatWon then Match.Score.Swat = Match.Score.Swat + 1 else Match.Score.Suspects = Match.Score.Suspects + 1 end
    local final = Match.Score.Swat >= Settings.RoundsToWin or Match.Score.Suspects >= Settings.RoundsToWin
    -- halftime after RoundsToWin - 1 rounds, as CS2 swaps after 12 rounds of a match to 13
    local swapped = not final and Settings.Swap and Settings.RoundsToWin > 1 and Match.Round == Settings.RoundsToWin - 1
    local winners = {}
    for _, player in ipairs(players) do
        if (Match.Suspects[player.Name] and true or false) ~= swatWon then winners[#winners + 1] = player.Name end
    end
    Match.Result = {
        Round = Match.Round, SwatWon = swatWon, Reason = reason, Final = final, Swapped = swapped,
        SwatScore = Match.Score.Swat, SuspectScore = Match.Score.Suspects,
        Winners = #winners > 0 and table.concat(winners, ", ") or (swatWon and "ИИ-отряд SWAT" or "ИИ-подозреваемые"),
    }
    Match.Phase, Match.BreakEnds = "roundover", now + Settings.BreakSeconds
    local text = string.format("Раунд %d: победа %s — %s. %s", Match.Round, swatWon and "SWAT" or "подозреваемых", reason, ScoreLine())
    Say(text)
    C.Banner(text)
    if final then
        Say(string.format("Матч окончен: победили %s (%s). %s", swatWon and "SWAT" or "подозреваемые", Match.Result.Winners, ScoreLine()))
    elseif swapped then
        Say("Половина матча: после этого раунда команды меняются сторонами")
    end
    Log("round %d over: %s won (%s), %s%s", Match.Round, swatWon and "SWAT" or "suspects", reason, ScoreLine(),
        final and ", match over" or (swapped and ", sides swap" or ""))
end

-- The same mission again, in the same game mode, for every connected player (servertravel keeps the
-- clients of a hosted game; a single-player game opens the level again).
local function Travel()
    local world = UEHelpers.GetWorld()
    local level, mode = nil, nil
    pcall(function() level = UEHelpers.GetGameplayStatics():GetCurrentLevelName(world, true):ToString() end)
    pcall(function() mode = UEHelpers.GetGameModeBase().OptionsString:ToString():match("[?&]game=([^?&]+)") end)
    mode = mode or CoopMode
    if not level or level == "" then
        Say("PvP: не удалось перезапустить миссию для следующего раунда — режим выключен")
        StopMode()
        return
    end
    local kismet, hosting = UEHelpers.GetKismetSystemLibrary(), false
    pcall(function() hosting = kismet:IsServer(world) and not kismet:IsStandalone(world) end)
    local command = string.format("%s %s?game=%s", hosting and "servertravel" or "open", level, mode)
    Match.Phase, Match.TravelFrom, Match.TravelAt = "travel", C.Worlds.Generation, C.WorldTime()
    Log("next round: %s", command)
    Exec(command)
end

local function LoadNextRound(players)
    local result = Match.Result
    if result.Swapped then
        for _, player in ipairs(players) do
            local team = Match.Teams[player.Name] or (Match.Suspects[player.Name] and TeamSuspect) or TeamSwatBlue
            Match.Teams[player.Name] = team == TeamSuspect and TeamSwatBlue or TeamSuspect
        end
        Match.Score.Swat, Match.Score.Suspects = Match.Score.Suspects, Match.Score.Swat
    end
    if not result.Final then Match.Round = Match.Round + 1 end
    Match.PageMode = result.Final and "final" or "round"
    -- everybody spawns as SWAT (co-op maps have no suspect starts); suspects take their AI again
    for _, player in ipairs(players) do SetTeam(player, TeamSwatBlue) end
    Travel()
end

local function StartLive(now, players)
    local swatPlayers, suspectPlayers = 0, 0
    for _, player in ipairs(players) do
        if Match.Suspects[player.Name] then suspectPlayers = suspectPlayers + 1 else swatPlayers = swatPlayers + 1 end
    end
    -- From the second round on a match goes on with the mission's AI suspects as the only suspects
    -- (a host alone after the halftime swap plays SWAT).
    local inMatch = Match.Round > 1
    if suspectPlayers == 0 and not Settings.Test and not inMatch then
        if Match.Auto then Log("PvP: nobody plays a suspect, a plain co-op mission") else Say("PvP: никто не выбрал подозреваемых — идёт обычная миссия") end
        StopMode()
        return
    end
    Match.Bots = Settings.Bots
    if suspectPlayers == 0 and Settings.Test then
        Say("PvP (тест): без подозреваемых")
    end
    if swatPlayers == 0 and not Match.Bots and not Settings.Test then
        Say("PvP: нет ни игроков SWAT, ни ботов — режим выключен")
        StopMode()
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
    Match.Deaths, Match.Warned, Match.PageMode = {}, {}, "teams"
    H.Reset(now)
    for _, player in ipairs(players) do
        -- a suspect whose booking was lost (AI gone, ready state missed) takes over now
        if Match.Suspects[player.Name] and not Match.Converts[player.Name] and player.Team ~= TeamSuspect then
            Match.Deaths[player.Name] = { At = now - Settings.RespawnDelay, Told = true }
        end
    end
    if Match.Round == 1 then
        Say(string.format("PvP: матч %s, раунд %d мин. Подозреваемые берут раунд, если положат всех SWAT или продержатся; SWAT — если нейтрализует всех подозреваемых. Убитый подозреваемый через %d с вселяется в ИИ-подозреваемого. %s",
            Settings.RoundsToWin > 1 and string.format("до %d побед", Settings.RoundsToWin) or "из одного раунда",
            Settings.Minutes, Settings.RespawnDelay, Match.Bots and "ИИ-отряд SWAT в игре." or "Без ИИ-отряда SWAT."))
    end
    local text = string.format("Раунд %d · %s · %d мин", Match.Round, ScoreLine(), Settings.Minutes)
    Say(text)
    C.Banner(text)
end

---------------------------------------------------------------- the host's team button

-- The pre-mission screen has a team button (W_PreMission_C.SwapTeams_Button) that a co-op mission keeps
-- collapsed (its AllowTeamSwapping is false for CoopGS). On the host's own screen HostBrain shows it
-- during a PvP briefing (SetVisibility replaces the binding) and makes it switch the host between SWAT
-- and the suspects. The game's SwapTeams it runs as well only moves a player between the red and blue
-- SWAT elements, which spawn alike. Clients keep the collapsed button and pick teams in chat.
local PreMission = "/Game/Blueprints/Widgets/PreMission/W_PreMission.W_PreMission_C"
local TeamButton = { Screen = nil, Widget = nil, Label = nil, Hooked = {} }

local function HostPlayer(players)
    local host = UEHelpers.GetPlayerController()
    if not Valid(host) then return nil end
    for _, player in ipairs(players) do
        if player.Controller:GetAddress() == host:GetAddress() then return player end
    end
end

local function PreMissionScreen()
    for _, widget in ipairs(FindAllOf("W_PreMission_C") or {}) do
        if widget:IsValid() and widget:IsInViewport() then return widget end
    end
end

local function ShowTeamButton(host)
    local screen = PreMissionScreen()
    TeamButton.Screen = screen
    if not screen or not host then return end
    local address = screen:GetAddress()
    if TeamButton.Widget ~= address then TeamButton.Widget, TeamButton.Label = address, nil end
    pcall(function()
        if screen.SwapTeams_Box:GetVisibility() ~= 0 then screen.SwapTeams_Box:SetVisibility(0) end -- Visible
    end)
    -- The button itself reads "Swap teams" (a separate label of the screen); its own text would lie on
    -- top of that, so it stays empty, and the chosen side goes into the mode line at the top.
    local label = Match.Teams[host.Name] == TeamSuspect and "PvP · вы за подозреваемых" or "PvP · вы за SWAT"
    if TeamButton.Label ~= label then
        local ok = pcall(function()
            screen.SwapTeams_Button:SetButtonText(FText(""))
            screen.ModeName_Text:SetText(FText(label))
        end)
        if ok then TeamButton.Label = label end
    end
end

local function OnSwapTeams(context)
    if not Match.Active or Match.Phase ~= "briefing" then return end
    local ready = false
    pcall(function() ready = context:get().bReady end)
    if ready then return end
    local host = HostPlayer(Players())
    if not host then return end
    local team = Match.Teams[host.Name] == TeamSuspect and TeamSwatBlue or TeamSuspect
    Match.Teams[host.Name] = team
    Say(string.format("%s → %s", host.Name, TeamName(team)))
    -- a host who changes sides after Ready chooses again in the team menu
    Match.HostConfirmed, Match.PageMode = false, "teams"
    Menu.Reopen()
    -- the game relabels the button after SwapTeams; ours goes back on top
    TeamButton.Label = nil
    ExecuteInGameThreadWithDelay(100, function()
        local ok, err = pcall(ShowTeamButton, host)
        if not ok then Log("team button: %s", tostring(err)) end
    end)
end

-- The host's own Ready button (or key) confirms the team choice and lets the mission start: a
-- single-player mission readies the host by itself about 4 s into the pre-mission screen, and neither
-- Server_SetReadyState(false) nor ToggleReady takes that back, so the start countdown is held instead
-- (Pvp.FrameTick) until the host presses Ready.
local function OnToggleReady()
    if not Match.Active or Match.Phase ~= "briefing" or Match.HostConfirmed then return end
    if Match.PageMode == "final" then NewMatch() end -- Ready on the final result starts a new match
    Match.HostConfirmed = true
    Menu.Hide()
    local host = HostPlayer(Players())
    Say(string.format("%s готов: %s", host and host.Name or "хост", TeamName(host and Match.Teams[host.Name] or TeamSwatBlue)))
end

-- The widget class loads with the first pre-mission screen (and may be loaded anew later), so the
-- hooks follow the function objects.
local function HookPreMission(name, callback)
    local fn = StaticFindObject(PreMission .. ":" .. name)
    if not Valid(fn) or TeamButton.Hooked[name] == fn:GetAddress() then return end
    local ok, err = pcall(RegisterHook, PreMission .. ":" .. name, callback)
    if ok then TeamButton.Hooked[name] = fn:GetAddress() else Log("cannot hook %s: %s", name, tostring(err)) end
end

-- While the host has not pressed Ready the start countdown stays full (every frame; the screen is
-- looked up once a second by ShowTeamButton).
local function HoldStart()
    local screen = TeamButton.Screen
    if Match.HostConfirmed or not Valid(screen) or not screen:IsInViewport() then return end
    local gameState = UEHelpers.GetGameStateBase()
    pcall(function()
        if gameState.TimeTillGameStartCountdown < 10 then
            gameState.TimeTillGameStartCountdown = 10
            if not Match.HoldTold then
                Match.HoldTold = true
                Say("Старт ждёт хоста: выберите сторону в меню и нажмите «Готов»")
            end
        end
    end)
end

---------------------------------------------------------------- the host's team menu (hb_menu)

local Accuracies = { { 3.0, "НИЗКАЯ" }, { 2.0, "СРЕДНЯЯ" }, { 1.0, "ВЫСОКАЯ" } }
local MinuteSteps = { 3, 5, 10, 15, 20, 30 }
local RoundSteps = { 1, 2, 3, 4, 5, 8 }

-- Between rounds nobody has to press Ready: once the result has been up for a while every player is
-- readied. The host readies through its own ReadyUp (as the solo mode does; bReady follows a few
-- seconds later, so it is asked at most every 6 s), a client on the server through
-- ReadyOrNotPlayerController::Server_SetReadyState, which runs right there on the host.
local function ReadyEveryone(players, now)
    local host = UEHelpers.GetPlayerController()
    for _, player in ipairs(players) do
        local ready = true
        pcall(function() ready = player.State.bReady end)
        local asked = Match.ReadyAsked[player.Name]
        if not ready and (not asked or now - asked >= 6) then
            Match.ReadyAsked[player.Name] = now
            local isHost = Valid(host) and player.Controller:GetAddress() == host:GetAddress()
            local ok, err = pcall(function()
                if isHost then player.Controller:ReadyUp() else player.Controller:Server_SetReadyState(true) end
            end)
            Log("round start: %s readied (%s)", player.Name, ok and (isHost and "ReadyUp" or "Server_SetReadyState") or tostring(err))
        end
    end
end

-- The round result page: who took the round, the score, what comes next.
local function ResultState(host, now)
    local result = Match.Result
    local final = Match.PageMode == "final"
    local state = {
        Top = final and "МАТЧ ОКОНЧЕН" or string.format("РАУНД %d", result.Round),
        Winner = result.SwatWon and "ПОБЕДА SWAT" or "ПОБЕДА ПОДОЗРЕВАЕМЫХ",
        WinnerSide = result.SwatWon and "swat" or "suspect",
        Reason = result.Reason,
        SwatScore = result.SwatScore, SuspectScore = result.SuspectScore,
    }
    local hostTeam = TeamName(Match.Teams[host.Name] or TeamSwatBlue)
    if final then
        state.Reason = string.format("решающий раунд %d: %s", result.Round, result.Reason)
        state.Notice = "Победители: " .. result.Winners
        state.Countdown = string.format("Матч до %d побед. «Новый матч» — снова выбор команд на этой же карте", Settings.RoundsToWin)
        return state
    end
    state.Notice = result.Swapped and string.format("СМЕНА СТОРОН · теперь вы за %s · %s", hostTeam, ScoreLine())
        or string.format("Следующий раунд: вы за %s · матч до %d побед", hostTeam, Settings.RoundsToWin)
    local gameState = UEHelpers.GetGameStateBase()
    local everyone, left = false, nil
    pcall(function()
        everyone = gameState:IsEveryoneReady()
        left = gameState.TimeTillGameStartCountdown
    end)
    if everyone and left then
        state.Countdown = string.format("Раунд %d начнётся через %d с", Match.Round, math.max(0, math.ceil(left)))
    else
        state.Countdown = string.format("Раунд %d · автостарт через %d с", Match.Round,
            math.max(0, math.ceil((Match.BriefedAt or now) + Settings.ReadyAfter - now)))
    end
    return state
end

local function AccuracyName()
    for _, level in ipairs(Accuracies) do
        if math.abs(level[1] - Settings.BotAccuracy) < 0.01 then return level[2] end
    end
    return string.format("%.1f", Settings.BotAccuracy)
end

local function Next(list, current, key)
    for i, item in ipairs(list) do
        local value = key and item[key] or item
        if value == current then return list[i % #list + 1] end
    end
    return list[1]
end

local function MenuState(players, host, now)
    local Colors = Menu.Colors
    local state = { Swat = {}, Suspects = {}, SwatCount = 0, SuspectCount = 0, Bots = Settings.Bots,
        Accuracy = AccuracyName(), Minutes = Settings.Minutes, Ready = Match.HostConfirmed,
        RoundsToWin = Settings.RoundsToWin, Swap = Settings.Swap, Mode = Match.Result and Match.PageMode or "teams" }
    if state.Mode ~= "teams" then
        state.Result = ResultState(host, now)
        return state
    end
    for _, player in ipairs(players) do
        local team = Match.Teams[player.Name] or (Match.Suspects[player.Name] and TeamSuspect) or player.Team
        local isHost = host and player.Name == host.Name
        local ready = false
        if isHost then ready = Match.HostConfirmed else pcall(function() ready = player.State.bReady end) end
        local entry = { Text = player.Name .. (isHost and " · хост" or "") .. (ready and " · готов" or ""), Color = Colors.White }
        if team == TeamSuspect then
            table.insert(state.Suspects, entry)
            state.SuspectCount = state.SuspectCount + 1
        else
            table.insert(state.Swat, entry)
            state.SwatCount = state.SwatCount + 1
        end
        if isHost then state.HostTeam = team == TeamSuspect and "suspect" or "swat" end
    end
    if Settings.Bots then
        -- the co-op squad's members, in the free slots as bots are in CS2
        for _, name in ipairs({ "King", "Swan", "Prescott", "Eli" }) do
            table.insert(state.Swat, { Text = "БОТ  " .. name, Color = Colors.SwatBot })
        end
    end
    local ai = #LivingAiSuspects()
    table.insert(state.Suspects, { Text = ai > 0 and string.format("ИИ-подозреваемые · %d", ai) or "ИИ-подозреваемые миссии", Color = Colors.SuspectAi })
    if Match.Round > 1 then
        state.Subtitle = string.format("Раунд %d · %s · матч до %d побед", Match.Round, ScoreLine(), Settings.RoundsToWin)
    else
        state.Subtitle = string.format("PvP · раунд %d мин · убитый подозреваемый вселяется в живого ИИ-подозреваемого", Settings.Minutes)
    end
    return state
end

local ShowMenu -- forward: refreshes the menu right after a click

local function OnMenuAction(action)
    local players = Players()
    local host = HostPlayer(players)
    if not host or not Match.Active or Match.Phase ~= "briefing" then return end
    if action == "swat" or action == "suspect" then
        local team = action == "suspect" and TeamSuspect or TeamSwatBlue
        if (Match.Teams[host.Name] or TeamSwatBlue) ~= team then Say(string.format("%s → %s", host.Name, TeamName(team))) end
        Match.Teams[host.Name] = team
        TeamButton.Label = nil
    elseif action == "auto" then
        -- the side with fewer players; on a tie the suspects (SWAT have the bots when they are on)
        local swat, suspects = 0, 0
        for _, player in ipairs(players) do
            if player.Name ~= host.Name then
                local team = Match.Teams[player.Name] or player.Team
                if team == TeamSuspect then suspects = suspects + 1 else swat = swat + 1 end
            end
        end
        local team = (suspects < swat or (suspects == swat and Settings.Bots)) and TeamSuspect or TeamSwatBlue
        if (Match.Teams[host.Name] or TeamSwatBlue) ~= team then Say(string.format("%s → %s", host.Name, TeamName(team))) end
        Match.Teams[host.Name] = team
        TeamButton.Label = nil
    elseif action == "bots" then
        Settings.Bots = not Settings.Bots
        C.SaveSetting("pvp_bots", Settings.Bots and 1 or 0)
        Say(Settings.Bots and "PvP: ИИ-отряд SWAT включён" or "PvP: ИИ-отряд SWAT выключен")
    elseif action == "accuracy" then
        Settings.BotAccuracy = Next(Accuracies, Settings.BotAccuracy, 1)[1]
        C.SaveSetting("pvp_bot_accuracy", Settings.BotAccuracy)
    elseif action == "minutes" then
        Settings.Minutes = Next(MinuteSteps, Settings.Minutes)
        C.SaveSetting("pvp_minutes", Settings.Minutes)
    elseif action == "rounds" then
        Settings.RoundsToWin = Next(RoundSteps, Settings.RoundsToWin)
        C.SaveSetting("pvp_rounds", Settings.RoundsToWin)
    elseif action == "swap" then
        Settings.Swap = not Settings.Swap
        C.SaveSetting("pvp_swap", Settings.Swap and 1 or 0)
    elseif action == "startnow" then
        ReadyEveryone(players, C.WorldTime())
    elseif action == "teams" then
        -- back to the team page; the start waits for the host's Ready again
        Match.PageMode, Match.HostConfirmed = "teams", false
        Menu.Reopen()
    elseif action == "newmatch" then
        NewMatch()
        Match.HostConfirmed = false
        Menu.Reopen()
        Say(string.format("PvP: новый матч до %d побед — выбор команд", Settings.RoundsToWin))
    elseif action == "ready" then
        local screen = TeamButton.Screen
        local ready = false
        pcall(function() ready = host.State.bReady end)
        -- the game's own Ready when the host is not ready yet (its hook confirms); a host the game
        -- readied by itself is confirmed directly
        if not ready and Valid(screen) then pcall(function() screen:ToggleReady() end) end
        OnToggleReady()
    end
    ShowMenu(players, host)
end

ShowMenu = function(players, host)
    local screen = TeamButton.Screen
    if not host or not Valid(screen) then return end
    local state = MenuState(players, host, C.WorldTime())
    -- the team page goes once the host is ready; a round result stays up until the round starts
    if Match.HostConfirmed and state.Mode == "teams" then Menu.Hide() end
    Menu.Show(screen, state, OnMenuAction)
    ShowTeamButton(host)
end

local function BriefingTick(now, players)
    -- the AI squad of a hosted mission only when somebody plays a suspect: a plain co-op mission stays as it is
    local anySuspect = false
    for _, player in ipairs(players) do
        if Match.Teams[player.Name] == TeamSuspect then anySuspect = true end
    end
    -- (from the second round on the match needs the squad even with only AI suspects against it)
    SetSquadVariable(Settings.Bots and (anySuspect or Match.Round > 1))
    local host = HostPlayer(players)
    HookPreMission("SwapTeams", OnSwapTeams)
    HookPreMission("ToggleReady", OnToggleReady)
    -- After a round the result shows and the next round starts by itself: the host counts as
    -- confirmed and everyone is readied after Settings.ReadyAfter seconds.
    if Match.PageMode == "round" and Match.Result then
        Match.BriefedAt = Match.BriefedAt or now
        Match.HostConfirmed = true
        if now >= Match.BriefedAt + Settings.ReadyAfter then ReadyEveryone(players, now) end
    end
    ShowTeamButton(host)
    ShowMenu(players, host)
    if Match.LastRoster == -math.huge and Match.Round == 1 then
        Say(string.format("PvP: SWAT против подозреваемых · раунд %d мин · %s. Подозреваемые воюют вместе с ИИ-подозреваемыми и после смерти вселяются в них",
            Settings.Minutes, Settings.Bots and "ИИ-отряд SWAT в игре" or "без ИИ-отряда SWAT"))
    end
    -- the roster goes out when it changes (the host's team menu shows it all the time)
    local roster = Roster(players)
    if roster ~= Match.LastRosterText then
        Match.LastRoster, Match.LastRosterText = now, roster
        Say(Match.Round > 1 and string.format("Раунд %d · %s", Match.Round, roster)
            or (roster .. ". Выбор стороны: у хоста кнопка «Поменять команды», у остальных — чат !swat или !suspect"))
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
    local host = HostPlayer(players)
    if host and Match.Suspects[host.Name] and host.Pawn then C.HideSquadHud() end
    if Match.Bots then DirectSquad(now, players) end
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
    if Match.SquadSeen or now - Match.StartedAt > 30 then SetSquadVariable(false) end
    if Match.Bots and not Match.SquadSeen and now - Match.StartedAt > 30 then
        -- the mission has no AI squad (its level script spawns none), or the spawn was refused
        Match.Bots = false
        Say("PvP: ИИ-отряд SWAT не появился — играем без ботов")
    end
    if now - Match.StartedAt < 10 then return end
    if swatPlayers > 0 and swatAlive == 0 then
        EndRound(now, players, false, "все бойцы SWAT нейтрализованы")
    elseif swatPlayers == 0 and Match.Bots and Match.SquadSeen and squad == 0 then
        EndRound(now, players, false, "ИИ-отряд SWAT уничтожен")
    elseif now >= Match.EndsAt then
        EndRound(now, players, false, "время вышло, подозреваемые продержались")
    elseif aiLeft == 0 and suspectAlive == 0 and waiting == 0 then
        EndRound(now, players, true, "все подозреваемые нейтрализованы")
    else
        local left = Match.EndsAt - now
        for _, mark in ipairs({ 300, 60 }) do
            if left <= mark and not Match.Warned[mark] and Match.EndsAt - Match.StartedAt > mark then
                Match.Warned[mark] = true
                Say(string.format("До конца раунда %s · ИИ-подозреваемых: %d", C.Clock(mark), aiLeft))
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

-- Settings.Auto: on the host's pre-mission screen of any co-op mission the mode arms itself, so the
-- team choice needs no console. Nobody choosing the suspects leaves a plain co-op mission.
local function AutoArm()
    if not Settings.Auto or Match.AutoWorld == C.Worlds.Generation or (Deps.OtherModeActive and Deps.OtherModeActive()) then return end
    -- the mod.io version of the mode (pakmod) runs its own director: two team menus would fight
    local director = FindFirstOf("BP_PvPDirector_C")
    if Valid(director) then
        Match.AutoWorld = C.Worlds.Generation
        Log("PvP: the mod.io version (BP_PvPDirector) runs this mission; HostBrain's mode stands down")
        return
    end
    local gameMode = UEHelpers.GetGameModeBase()
    local coop = StaticFindObject("/Script/ReadyOrNot.CoopGM")
    if not Valid(gameMode) or not Valid(coop) or not gameMode:IsA(coop) or not PreMissionScreen() then return end
    Match.AutoWorld = C.Worlds.Generation
    Match.Active, Match.Auto, Match.Phase, Match.World = true, true, "briefing", C.Worlds.Generation
    Settings.Test = false
    NewMatch()
    ResetMission()
    Log("PvP armed on the pre-mission screen (auto)")
end

-- RonCompNative drops score popups while a match runs (Deps.SetNativePvp).
local function SyncNativePvp()
    local on = Match.Active and (Match.Phase == "live" or Match.Phase == "roundover")
    if Match.NativePvp ~= on and Deps.SetNativePvp then
        Match.NativePvp = on
        Deps.SetNativePvp(on)
    end
end

function Pvp.Tick()
    if not Match.Active then AutoArm() end
    SyncNativePvp()
    if not Match.Active then return end
    local now = C.WorldTime()
    if Match.Phase == "travel" then
        if C.Worlds.Generation == Match.TravelFrom then
            -- a travel blocks the old world while it loads; the old world still ticking means it failed
            if Match.TravelAt > 0 and now - Match.TravelAt > 30 then
                Say("PvP: следующий раунд не загрузился — режим выключен")
                StopMode()
            end
            return
        end
        Match.Phase, Match.World = "briefing", C.Worlds.Generation
        ResetMission()
    end
    if Match.World ~= C.Worlds.Generation then
        if Match.Phase == "briefing" then
            -- a travel can pass through a transition world first: follow it until the mission starts
            Match.World = C.Worlds.Generation
            ResetMission()
        else
            Log("PvP: the mission was left; mode stopped")
            StopMode()
            return
        end
    end
    EnablePvpFlags()
    local players = Players()
    if Match.Phase == "briefing" then
        BriefingTick(now, players)
    elseif Match.Phase == "live" then
        LiveTick(now, players)
    elseif Match.Phase == "roundover" and now >= Match.BreakEnds then
        LoadNextRound(players)
    end
end

-- The mission start spawns the AI squad around the host's pawn, so with bots a suspect host stays at
-- the van until the squad is there (at most 5 s).
local function HostWaitsForSquad(player)
    if not Settings.Bots or Match.SquadSeen then return false end
    local host = UEHelpers.GetPlayerController()
    if not Valid(host) or player.Controller:GetAddress() ~= host:GetAddress() then return false end
    if #LivingSwat() > 0 then
        Match.SquadSeen = true
        return false
    end
    local now = C.WorldTime()
    Match.HostWait = Match.HostWait or now
    return now - Match.HostWait < 5
end

-- Every frame while a booking waits: the player's new pawn takes the AI's place in its first frame.
function Pvp.FrameTick()
    if Match.Active and Match.Phase == "briefing" then HoldStart() end
    if not Match.Active or next(Match.Converts) == nil then return end
    for _, player in ipairs(Players()) do
        local convert = Match.Converts[player.Name]
        if convert and player.Pawn and not Match.Stripped[tostring(player.Pawn:GetAddress())] and not HostWaitsForSquad(player) then
            Convert(player, convert)
        end
    end
end

function Pvp.FireTick()
    if Match.Active and Match.Phase == "live" and Match.Bots then DirectSwatFire(Players()) end
end

function Pvp.Stop()
    if Match.Active then SetSquadVariable(false) end
    StopMode()
    SyncNativePvp()
end

function Pvp.Status(out)
    out(string.format("PvP team choice on co-op pre-mission screens: %s, bots %s, %d min rounds, match to %d wins, halftime swap %s",
        Settings.Auto and "on" or "off", Settings.Bots and "on" or "off", Settings.Minutes, Settings.RoundsToWin, Settings.Swap and "on" or "off"))
    if not Match.Active and Match.Phase == "idle" then return end
    local now = C.WorldTime()
    out(string.format("PvP: round %d, SWAT %d : %d suspects, phase %s%s, page %s, bots %s, takeover after %d s, AI suspects left %d%s",
        Match.Round, Match.Score.Swat, Match.Score.Suspects, Match.Phase, Match.Auto and " (auto)" or "", Match.PageMode,
        Settings.Bots and "on" or "off", Settings.RespawnDelay, #LivingAiSuspects(),
        Match.Phase == "live" and string.format(", %s left", C.Clock(math.max(0, math.floor(Match.EndsAt - now)))) or ""))
    out(Roster(Players()))
end

-- deps: EnsureGuards(), ResolveMap(name), StopOtherModes(), OtherModeActive(), FilterInstalled(), SetNativePvp(on)
-- from main.lua.
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
        Match.Active, Match.Auto = true, false
        NewMatch()
        if target == "here" then
            Match.Phase, Match.World = "briefing", C.Worlds.Generation
            ResetMission()
            out(string.format("PvP on this mission: %s, %d min; players pick teams with !swat / !suspect before the start",
                Settings.Bots and "with AI SWAT" or "no AI SWAT", Settings.Minutes))
            return
        end
        local level = deps.ResolveMap(target)
        Match.Phase, Match.TravelFrom, Match.TravelAt = "travel", C.Worlds.Generation, C.WorldTime()
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
        if minutes and minutes >= 1 then
            Settings.Minutes = math.floor(minutes)
            C.SaveSetting("pvp_minutes", Settings.Minutes)
        end
        if delay and delay >= 0 then Settings.RespawnDelay = math.floor(delay) end
        out(string.format("PvP: %d min, takeover %d s after a suspect's death", Settings.Minutes, Settings.RespawnDelay))
    end)
    Register("comp_pvp_bots", function(parts, out)
        if parts[1] then
            Settings.Bots = parts[1] ~= "0" and parts[1]:lower() ~= "off"
            C.SaveSetting("pvp_bots", Settings.Bots and 1 or 0)
        end
        local accuracy = tonumber(parts[2] or "")
        if accuracy and accuracy > 0 then Settings.BotAccuracy = accuracy end
        out(string.format("PvP AI SWAT squad: %s, aim penalty %.1f", Settings.Bots and "on" or "off", Settings.BotAccuracy))
    end)
    Register("comp_pvp_auto", function(parts, out)
        if parts[1] then
            Settings.Auto = parts[1] ~= "0" and parts[1]:lower() ~= "off"
            C.SaveSetting("pvp_auto", Settings.Auto and 1 or 0)
        end
        out(string.format("PvP team choice on every co-op pre-mission screen: %s", Settings.Auto and "on" or "off"))
    end)
    Register("comp_pvp_rounds", function(parts, out)
        -- comp_pvp_rounds [wins] [swap 0|1]
        local wins, swap = tonumber(parts[1] or ""), parts[2]
        if wins and wins >= 1 then
            Settings.RoundsToWin = math.floor(wins)
            C.SaveSetting("pvp_rounds", Settings.RoundsToWin)
        end
        if swap then
            Settings.Swap = swap ~= "0" and swap:lower() ~= "off"
            C.SaveSetting("pvp_swap", Settings.Swap and 1 or 0)
        end
        out(string.format("PvP match to %d round wins, halftime swap %s", Settings.RoundsToWin, Settings.Swap and "on" or "off"))
    end)
    Register("comp_pvp_endround", function(parts, out)
        -- comp_pvp_endround swat|suspects: ends the running round (testing the round flow)
        if not Match.Active or Match.Phase ~= "live" then
            out("no PvP round is running")
            return
        end
        local swatWon = (parts[1] or ""):lower() == "swat"
        EndRound(C.WorldTime(), Players(), swatWon, "раунд завершён хостом")
        out(string.format("round %d ended: %s", Match.Result.Round, swatWon and "SWAT" or "suspects"))
    end)
    Register("comp_pvp_status", function(_, out) Pvp.Status(out) end)
    Register("comp_pvp_end", function(_, out)
        Pvp.Stop()
        out("PvP mode off (the hidden co-op PvP flag stays until the mission changes)")
    end)
end

return Pvp
