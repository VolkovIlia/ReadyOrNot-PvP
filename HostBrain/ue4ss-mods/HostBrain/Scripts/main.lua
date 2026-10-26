-- HostBrain: host-side controller of RoN Competitive.
--
-- Only the player who hosts (the listen server) runs it; clients play with the shared pak alone.
-- Stage 1 hosts the game's own PvP modes as the developers built them (Firefight first, no bomb):
--   * comp_start travels the host to "<map>?listen?game=<mode>" with the game's mode aliases;
--   * RonCompNative.dll guards the round reset crash (Multicast_StopSequence(nullptr));
--   * server-side hit validation (UHitRegistrationSettings) is switched on for the host.
-- Modules: hb_common (helpers), hb_loadout (suspect equipment), hb_solo (suspect vs AI SWAT),
-- hb_pvp (SWAT players vs suspect players in a co-op mission).
--
-- Console commands (UE console, or any ExecuteConsoleCommand on the host):
--   comp_pvp <map|here> [minutes] [bots] [test]
--                               PvP in a co-op mission: SWAT players against suspect players; "here"
--                               switches the current mission (on its pre-mission screen); "bots" keeps an
--                               AI SWAT squad where the mission has one, "test" starts without one side
--   comp_pvp_team <player|me> swat|suspect
--                               put a player on a team (players can also type !swat / !suspect)
--   comp_pvp_time <min> [takeover s], comp_pvp_bots <on|off> [aim], comp_pvp_status, comp_pvp_end
--   comp_start <map> [mode] [force]
--                               host a PvP match (default mode: ff); from a hosted lobby it server-travels
--                               everyone, otherwise it opens a new listen server. Unverified map/mode
--                               pairs need "force".
--   comp_maps                   list map shortcuts
--   comp_modes                  list PvP mode aliases
--   comp_status                 log mode, match state, guards and hit validation
--   comp_hitvalidation <0|1>    switch server-side hit validation
--   comp_maxplayers [n]         player cap of the lobbies the host creates from now on (default 10)
--   comp_play_suspect [map] [n] solo match: you are a suspect, the AI SWAT squad of a co-op mission
--                               storms the building; rounds until one side has n wins (default 3)
--   comp_round_time <s> [prep]  assault time to survive (default 240) and preparation (default 20)
--   comp_bot_hints <0|1>        give the squad a rough area around you after 60 s without contact
--   comp_suspect [here|off]     switch the host to the suspects' side on the current map (no rounds)
--   comp_unstuck                move to another free spot next to the AI suspects
--   comp_alert                  make every AI SWAT target you
--   comp_bot_accuracy <x>       AI SWAT aim penalty while you are a suspect (1 = normal, default 2)

local UEHelpers = require("UEHelpers")

local ModDir = (debug.getinfo(1, "S").source:gsub("^@", ""):gsub("[\\/]Scripts[\\/]main%.lua$", ""))
local NativeDir = ModDir .. "\\native"
local NativeDll = NativeDir .. "\\RonCompNative.dll"
local NativeIni = NativeDir .. "\\RonCompNative.ini"
local NativeLog = NativeDir .. "\\RonCompNative.log"

local Config = {
    DefaultMode = "ff",
    HitValidation = true,
    LobbyCap = 10, -- 5v5; the game's default is 5
}

-- Shortcuts for comp_start; any level name (e.g. RoN_Campus_Core) is accepted as well.
local Maps = {
    agency = "Ron_Agency_Core", bank = "RoN_Bank_Core", beachfront = "RoN_Beachfront_Core",
    boat = "RoN_Boat_Core", campus = "RoN_Campus_Core", club = "RoN_Club_Core", coyote = "RoN_Coyote_Core",
    datacenter = "RoN_Datacenter_Core", dealer = "RoN_Dealer_Core", dorms = "RoN_Dorms_Core",
    farm = "RoN_Farm_Core", fastfood = "RoN_FastFood_Core", gas = "RoN_Gas_Core", home = "RoN_Home_Core",
    hospital = "RoN_Hospital_Core", importer = "RoN_Importer_Core", lawmaker = "RoN_Lawmaker_Core",
    meth = "RoN_Meth_Core", narcos = "RoN_Narcos_Core", penthouse = "RoN_Penthouse_Core",
    pier = "RoN_Pier_Core", port = "RoN_Port_Core_NEW", prison = "RoN_Prison_Core",
    ridgeline = "RoN_Ridgeline_Core", sins = "RoN_Sins_Core", streamer = "RoN_Streamer_Core",
    tower = "RoN_Tower_Core", valley = "RoN_Valley_Core",
}

-- PvP aliases from GameMapsSettings.GameModeClassAliases (docs/re-findings.md). All of them run on
-- ReadyOrNotGameMode_PVP and therefore need the StopSequence guard.
local PvpModes = {
    ff = "Firefight: SWAT vs suspects, round-based elimination",
    tdm = "Team deathmatch",
    RR_PVP = "Defusal (bomb), stage 2",
    vip = "VIP escort",
    aar = "Arrest and rescue",
    koth = "King of the hill",
    ctf = "Capture the flag",
    tow = "Tug of war",
    gungame = "Gun game",
    Incrim = "Incrimination",
}

-- The game marks no map as PvP-capable (BpGameplayHelperLib::IsPvPSupported is false everywhere), so
-- map/mode pairs are verified by playing them. A missing start spot is a fatal error for every player
-- (UEngine: "Couldn't spawn player: Could not find a starting spot"), so unverified pairs need "force".
local VerifiedPairs = {
    RoN_Campus_Core = { ff = true, RR_PVP = true },
}
local BrokenPairs = {
    RoN_Valley_Core = { tdm = "no team start spots for TDM: the game aborts while loading" },
}

local State = {
    GuardsInstalled = false,
    GuardsAttempts = 0,
    FilterInstalled = false,
    FilterAttempts = 0,
}

local C = require("hb_common")
local Solo = require("hb_solo")
local Pvp = require("hb_pvp")
local Log, Valid, Exec, ReadFile = C.Log, C.Valid, C.Exec, C.ReadFile

---------------------------------------------------------------- native guards

-- Hands the FName of Multicast_StopSequence to RonCompNative (it cannot call into Lua) and runs its
-- installer; the outcome is read back from its log.
local function InstallNativeGuards()
    if State.GuardsInstalled then return true end
    State.GuardsAttempts = State.GuardsAttempts + 1

    local stopSequence = StaticFindObject("/Script/ReadyOrNot.ReadyOrNotGameState:Multicast_StopSequence")
    if not Valid(stopSequence) then
        Log("Multicast_StopSequence not found; native guards not installed")
        return false
    end

    local token = string.format("%d-%d", os.time(), math.random(1000000, 9999999))
    local ini = io.open(NativeIni, "w")
    if not ini then
        Log("cannot write %s", NativeIni)
        return false
    end
    ini:write("[guards]\n")
    ini:write(string.format("stop_sequence_fname_index=%d\n", stopSequence:GetFName():GetComparisonIndex()))
    ini:write(string.format("session_token=%s\n", token))
    ini:close()

    local install, loadError = package.loadlib(NativeDll, "RonCompNative_InstallGuards")
    if not install then
        Log("cannot load %s: %s", NativeDll, tostring(loadError))
        return false
    end
    install()

    local status = (ReadFile(NativeLog) or ""):match("STATUS " .. token:gsub("%-", "%%-") .. " (%a+)")
    State.GuardsInstalled = status == "ok"
    Log("native guards: %s (session %s, see %s)", State.GuardsInstalled and "installed" or ("FAILED: " .. tostring(status or "no answer")), token, NativeLog)
    return State.GuardsInstalled
end

-- SWAT-only server RPCs a suspect player's character must not get through (RonCompNative filter):
-- mode 0 blocks them outright, mode 1 only when the target is a character (doors and items stay usable).
local FilteredRpcs = {
    { "/Script/ReadyOrNot.ReadyOrNotCharacter:Server_Yell", 0 },
    { "/Script/ReadyOrNot.ReadyOrNotCharacter:Server_ReportToTOC", 0 },
    { "/Script/ReadyOrNot.ReadyOrNotCharacter:Server_ReportTarget", 0 },
    { "/Script/ReadyOrNot.ReadyOrNotCharacter:Server_CarryArrestedTarget", 0 },
    { "/Script/ReadyOrNot.PlayerCharacter:Server_InstaStartArrest", 0 },
    { "/Script/ReadyOrNot.PlayerCharacter:Server_GiveAIMoveTo", 0 },
    { "/Script/ReadyOrNot.PlayerCharacter:Server_GiveAIMoveToExit", 0 },
    { "/Script/ReadyOrNot.PlayerCharacter:Server_GiveAITurnAroundOrder", 0 },
    { "/Script/ReadyOrNot.ReadyOrNotCharacter:Server_Interact", 1 },
    { "/Script/ReadyOrNot.ReadyOrNotCharacter:Server_Interact_PrimaryUse", 1 },
    { "/Script/ReadyOrNot.ReadyOrNotCharacter:Server_DoubleTapInteract", 1 },
}
local DefaultTeamOffset = 0x1129 -- AReadyOrNotCharacter::DefaultTeam (JMAP dump); the DLL self-tests it

-- Replaces the [rpc_filter] section of RonCompNative.ini, keeping [guards].
local function WriteFilterSection(lines)
    local kept = {}
    local inFilter = false
    for line in ((ReadFile(NativeIni) or "") .. "\n"):gmatch("([^\n]*)\n") do
        if line:match("^%[") then inFilter = line == "[rpc_filter]" end
        if not inFilter and line ~= "" then kept[#kept + 1] = line end
    end
    local ini = io.open(NativeIni, "w")
    if not ini then return false end
    ini:write(table.concat(kept, "\n") .. "\n[rpc_filter]\n" .. table.concat(lines, "\n") .. "\n")
    ini:close()
    return true
end

-- Installs the suspect RPC filter once the host has a living character (its team is the self-test).
local function InstallRpcFilter()
    if State.FilterInstalled or State.FilterAttempts >= 3 then return State.FilterInstalled end
    local pawn = C.HostPawn()
    if C.IsDown(pawn) then return false end
    State.FilterAttempts = State.FilterAttempts + 1
    local characterClass = StaticFindObject("/Script/ReadyOrNot.ReadyOrNotCharacter")
    local characterSuper = StaticFindObject("/Script/Engine.Character")
    if not Valid(characterClass) or not Valid(characterSuper) then
        Log("suspect RPC filter: character classes not found")
        return false
    end
    local token = string.format("%d-%d", os.time(), math.random(1000000, 9999999))
    local lines = {
        "session_token=" .. token,
        string.format("team_offset=%d", DefaultTeamOffset),
        string.format("blocked_team=%d", C.TeamSuspect),
        string.format("character_class=%d", characterClass:GetAddress()),
        string.format("character_super=%d", characterSuper:GetAddress()),
        string.format("probe_pawn=%d", pawn:GetAddress()),
        string.format("probe_team=%d", pawn.DefaultTeam),
    }
    local count = 0
    for _, entry in ipairs(FilteredRpcs) do
        local fn = StaticFindObject(entry[1])
        if not Valid(fn) then
            Log("suspect RPC filter: %s not found", entry[1])
            return false
        end
        lines[#lines + 1] = string.format("function_%d=%d", count, fn:GetAddress())
        lines[#lines + 1] = string.format("mode_%d=%d", count, entry[2])
        lines[#lines + 1] = string.format("name_%d=%s", count, entry[1]:match(":(.+)$"))
        count = count + 1
    end
    lines[#lines + 1] = string.format("count=%d", count)
    if not WriteFilterSection(lines) then
        Log("cannot write %s", NativeIni)
        return false
    end
    local install, loadError = package.loadlib(NativeDll, "RonCompNative_InstallRpcFilter")
    if not install then
        Log("suspect RPC filter: cannot load %s: %s", NativeDll, tostring(loadError))
        return false
    end
    install()
    local status = (ReadFile(NativeLog) or ""):match("STATUS " .. token:gsub("%-", "%%-") .. " (%a+)")
    State.FilterInstalled = status == "ok"
    Log("suspect RPC filter: %s (session %s, see %s)", State.FilterInstalled and "installed" or ("FAILED: " .. tostring(status or "no answer")), token, NativeLog)
    return State.FilterInstalled
end

---------------------------------------------------------------- hit validation

local HitSettingsPath = "/Script/ReadyOrNot.Default__HitRegistrationSettings"

local function ApplyHitValidation(enabled)
    local settings = StaticFindObject(HitSettingsPath)
    if not Valid(settings) then
        Log("HitRegistrationSettings not found")
        return false
    end
    settings.bEnableValidation = enabled
    Log("hit validation %s (HitscanForgiveness=%.1f ShooterForgiveness=%.1f TraceDistanceForgiveness=%.1f)",
        settings.bEnableValidation and "ON" or "OFF", settings.HitscanForgiveness, settings.ShooterForgiveness,
        settings.TraceDistanceForgiveness)
    return true
end

---------------------------------------------------------------- lobby cap

-- UEOSMultiplayerSubsystem keeps the cap (5 from its constructor) and creates every lobby with it as
-- NumPublicConnections; the host's PreLogin answers "Server is full!" from that session setting, and
-- EOS caps the lobby members the same way. EOSMultiplayerStatics::SetMaxPlayers (also the console's
-- ConsoleSetMaxPlayers) is its only writer and changes no lobby that already exists.
-- GameSession.MaxPlayers is 16, so caps above 16 would need more than this.
local StaticsPath = "/Script/ReadyOrNot.Default__EOSMultiplayerStatics"
local MaxLobbyCap = 16

local function ApplyLobbyCap()
    local statics = StaticFindObject(StaticsPath)
    local context = UEHelpers.GetPlayerController()
    if not Valid(statics) or not Valid(context) then return nil end
    local current = statics:GetMaxPlayers(context)
    if current == Config.LobbyCap then return current end
    statics:SetMaxPlayers(context, Config.LobbyCap)
    local applied = statics:GetMaxPlayers(context)
    local kismet = UEHelpers.GetKismetSystemLibrary()
    local world = UEHelpers.GetWorld()
    local hosting = Valid(kismet) and kismet:IsServer(world) and not kismet:IsStandalone(world)
    Log("lobby cap %d -> %d for lobbies created from now on%s", current, applied,
        hosting and "; the lobby that is already open keeps its cap until it is created again" or "")
    return applied
end

---------------------------------------------------------------- commands

local function ResolveMap(name)
    if not name or name == "" then return nil end
    return Maps[name:lower()] or name
end

local function Start(mapName, mode, force, out)
    local level = ResolveMap(mapName)
    mode = mode or Config.DefaultMode
    if not level then
        out("usage: comp_start <map> [mode] [force]; comp_maps lists shortcuts")
        return
    end
    if not PvpModes[mode] then
        out("unknown mode '" .. mode .. "'; comp_modes lists them")
        return
    end
    local broken = BrokenPairs[level] and BrokenPairs[level][mode]
    if broken then
        out(string.format("refusing %s + %s: %s", level, mode, broken))
        return
    end
    local verified = VerifiedPairs[level] and VerifiedPairs[level][mode]
    if not verified and force ~= "force" then
        out(string.format("%s + %s is not verified yet and may abort the game for everyone; add 'force' to try it", level, mode))
        return
    end
    if not State.GuardsInstalled and not InstallNativeGuards() then
        out("refusing to start: the round-reset crash guard is not installed (see " .. NativeLog .. ")")
        return
    end
    ApplyHitValidation(Config.HitValidation)

    -- Already hosting (e.g. a lobby created from the game's own multiplayer menu): server travel keeps
    -- every connected player. From the main menu or single player: open a fresh listen server.
    local kismet = UEHelpers.GetKismetSystemLibrary()
    local world = UEHelpers.GetWorld()
    local hosting = Valid(kismet) and Valid(world) and kismet:IsServer(world) and not kismet:IsStandalone(world)
    if hosting then
        local url = string.format("%s?game=%s", level, mode)
        out("HostBrain: server travel to " .. url .. " with all connected players")
        Exec("servertravel " .. url)
    else
        local url = string.format("%s?listen?game=%s", level, mode)
        out("HostBrain: hosting " .. url)
        Exec("open " .. url)
    end
end

local function Status(out)
    local gameMode = UEHelpers.GetGameModeBase()
    local gameState = UEHelpers.GetGameStateBase()
    out(string.format("world: %s", Valid(UEHelpers.GetWorld()) and UEHelpers.GetWorld():GetFullName() or "<none>"))
    out(string.format("game mode: %s", Valid(gameMode) and gameMode:GetClass():GetFName():ToString() or "<not host>"))
    if Valid(gameState) then
        out(string.format("game state: %s pvp=%s match=%s rounds %s/%s red %s blue %s",
            gameState:GetClass():GetFName():ToString(), tostring(gameState.bPvPMode), tostring(gameState.MatchState),
            tostring(gameState.RoundsPlayed), tostring(gameState.RoundsToPlay),
            tostring(gameState.RedTeamWins), tostring(gameState.BlueTeamWins)))
    end
    local settings = StaticFindObject(HitSettingsPath)
    out(string.format("guards: %s, suspect RPC filter: %s, hit validation: %s", State.GuardsInstalled and "installed" or "NOT installed",
        State.FilterInstalled and "installed" or "NOT installed", Valid(settings) and tostring(settings.bEnableValidation) or "?"))
    local statics = StaticFindObject(StaticsPath)
    local context = UEHelpers.GetPlayerController()
    out(string.format("lobby cap: %s (setting %d)", Valid(statics) and Valid(context) and tostring(statics:GetMaxPlayers(context)) or "?", Config.LobbyCap))
    Solo.Status(out)
    Pvp.Status(out)
end

local function Register(name, handler)
    RegisterConsoleCommandGlobalHandler(name, function(_, parts, ar)
        local function out(text)
            Log("%s", text)
            if ar then pcall(function() ar:Log(text) end) end
        end
        local ok, err = pcall(handler, parts, out)
        if not ok then out(name .. " failed: " .. tostring(err)) end
        return true
    end)
end

Register("comp_start", function(parts, out)
    Solo.Stop()
    Pvp.Stop()
    Start(parts[1], parts[2], parts[3], out)
end)
Register("comp_status", function(_, out) Status(out) end)
Register("comp_hitvalidation", function(parts, out)
    Config.HitValidation = parts[1] ~= "0"
    ApplyHitValidation(Config.HitValidation)
    out("hit validation " .. (Config.HitValidation and "ON" or "OFF"))
end)
Register("comp_maxplayers", function(parts, out)
    local cap = tonumber(parts[1] or "")
    if parts[1] and (not cap or cap < 2 or cap > MaxLobbyCap or cap % 1 ~= 0) then
        out(string.format("usage: comp_maxplayers [2..%d]", MaxLobbyCap))
        return
    end
    Config.LobbyCap = cap or Config.LobbyCap
    out(string.format("lobby cap: %s; it applies to lobbies created from now on", tostring(ApplyLobbyCap())))
end)
Register("comp_maps", function(_, out)
    local names = {}
    for shortcut, level in pairs(Maps) do
        local modes = {}
        for mode in pairs(VerifiedPairs[level] or {}) do modes[#modes + 1] = mode end
        table.sort(modes)
        names[#names + 1] = shortcut .. "=" .. level .. (#modes > 0 and (" [verified: " .. table.concat(modes, ",") .. "]") or "")
    end
    table.sort(names)
    for _, line in ipairs(names) do out(line) end
end)
Register("comp_modes", function(_, out)
    for alias, description in pairs(PvpModes) do out(alias .. ": " .. description) end
end)

local function EnsureGuards()
    return State.GuardsInstalled or InstallNativeGuards()
end
Solo.RegisterCommands(Register, {
    EnsureGuards = EnsureGuards,
    ResolveMap = ResolveMap,
    StopOtherModes = function() Pvp.Stop() end,
})
Pvp.RegisterCommands(Register, {
    EnsureGuards = EnsureGuards,
    ResolveMap = ResolveMap,
    StopOtherModes = function() Solo.Stop() end,
    FilterInstalled = function() return State.FilterInstalled end,
})

-- Install the guards and switch hit validation on as soon as the game is up, so that even a match
-- started from the game's own menus is protected; afterwards run the modes.
local Ready = false
local function Tick()
    if not Valid(UEHelpers.GetWorld()) then return end
    if not Ready then
        Ready = true
        InstallNativeGuards()
        ApplyHitValidation(Config.HitValidation)
    end
    C.TrackWorld()
    ApplyLobbyCap()
    if not State.FilterInstalled then InstallRpcFilter() end
    Solo.Tick()
    local ok, err = pcall(Pvp.Tick)
    if not ok then Log("pvp tick failed: %s", tostring(err)) end
end

-- Every line of Lua runs on the game thread. LoopAsync callbacks run on a UE4SS worker thread while
-- the game thread runs this mod's hooks and ticks in the same Lua state, which is not thread-safe:
-- after a few hours of play the two threads corrupted the state and the game crashed in
-- lua_setiuservalue (docs/re-findings.md).
LoopInGameThreadWithDelay(1000, function()
    local ok, err = pcall(Tick)
    if not ok then Log("tick failed: %s", tostring(err)) end
end)

LoopInGameThreadWithDelay(500, function()
    Solo.FireTick()
    local ok, err = pcall(Pvp.FireTick)
    if not ok then Log("pvp bot director failed: %s", tostring(err)) end
end)

-- PvP moves a suspect player's new pawn onto its AI suspect's spot in the pawn's first frame.
LoopInGameThreadAfterFrames(1, function()
    local ok, err = pcall(Pvp.FrameTick)
    if not ok then Log("pvp frame tick failed: %s", tostring(err)) end
end)

Log("loaded; commands: comp_start <map> [mode], comp_pvp <map|here>, comp_play_suspect [map], comp_status")
