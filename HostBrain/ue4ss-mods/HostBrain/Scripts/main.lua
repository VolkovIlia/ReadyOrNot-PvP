-- HostBrain: host-side controller of RoN Competitive.
--
-- Only the player who hosts (the listen server) runs it; clients play with the shared pak alone.
-- Stage 1 hosts the game's own PvP modes as the developers built them (Firefight first, no bomb):
--   * comp_start travels the host to "<map>?listen?game=<mode>" with the game's mode aliases;
--   * RonCompNative.dll guards the round reset crash (Multicast_StopSequence(nullptr));
--   * server-side hit validation (UHitRegistrationSettings) is switched on for the host.
--
-- Console commands (UE console, or any ExecuteConsoleCommand on the host):
--   comp_start <map> [mode] [force]
--                               host a PvP match (default mode: ff); from a hosted lobby it server-travels
--                               everyone, otherwise it opens a new listen server. Unverified map/mode
--                               pairs need "force".
--   comp_maps                   list map shortcuts
--   comp_modes                  list PvP mode aliases
--   comp_status                 log mode, match state, guards and hit validation
--   comp_hitvalidation <0|1>    switch server-side hit validation

local UEHelpers = require("UEHelpers")

local ModDir = (debug.getinfo(1, "S").source:gsub("^@", ""):gsub("[\\/]Scripts[\\/]main%.lua$", ""))
local NativeDir = ModDir .. "\\native"
local NativeDll = NativeDir .. "\\RonCompNative.dll"
local NativeIni = NativeDir .. "\\RonCompNative.ini"
local NativeLog = NativeDir .. "\\RonCompNative.log"

local Config = {
    DefaultMode = "ff",
    HitValidation = true,
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
}

---------------------------------------------------------------- helpers

local function Log(format, ...)
    print(string.format("[HostBrain] " .. format .. "\n", ...))
end

local function Valid(object)
    return object ~= nil and type(object) == "userdata" and object.IsValid ~= nil and object:IsValid()
end

local function Exec(command)
    local kismet = UEHelpers.GetKismetSystemLibrary()
    local world = UEHelpers.GetWorld()
    if not Valid(kismet) or not Valid(world) then
        Log("cannot execute '%s': no world", command)
        return false
    end
    local controller = UEHelpers.GetPlayerController()
    kismet:ExecuteConsoleCommand(world, command, Valid(controller) and controller or nil)
    return true
end

local function ReadFile(path)
    local file = io.open(path, "r")
    if not file then return nil end
    local text = file:read("a")
    file:close()
    return text
end

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
    out(string.format("guards: %s, hit validation: %s", State.GuardsInstalled and "installed" or "NOT installed",
        Valid(settings) and tostring(settings.bEnableValidation) or "?"))
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

Register("comp_start", function(parts, out) Start(parts[1], parts[2], parts[3], out) end)
Register("comp_status", function(_, out) Status(out) end)
Register("comp_hitvalidation", function(parts, out)
    Config.HitValidation = parts[1] ~= "0"
    ApplyHitValidation(Config.HitValidation)
    out("hit validation " .. (Config.HitValidation and "ON" or "OFF"))
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

-- Install the guards and switch hit validation on as soon as the game is up, so that even a match
-- started from the game's own menus is protected.
local Ready = false
LoopAsync(2000, function()
    if Ready then return true end
    ExecuteInGameThread(function()
        if Ready or not Valid(UEHelpers.GetWorld()) then return end
        Ready = true
        InstallNativeGuards()
        ApplyHitValidation(Config.HitValidation)
    end)
    return false
end)

Log("loaded; commands: comp_start <map> [mode], comp_status, comp_maps, comp_modes, comp_hitvalidation <0|1>")
