-- RonCompProbe: development remote console for Ready or Not (not shipped).
--
-- Every second it looks for Mods/RonCompProbe/inbox.lua. If present, the file is run as a Lua chunk
-- on the game thread with the helpers below in scope, its return values are logged, and the file is
-- renamed to inbox.done.lua. All output goes to Mods/RonCompProbe/probe.log (and UE4SS.log), so the
-- game can be driven and observed from outside without touching the mouse or keyboard.
-- It also logs every world change and takes a screenshot a few seconds after each one.

local UEHelpers = require("UEHelpers")

local ModDir = (debug.getinfo(1, "S").source:gsub("^@", ""):gsub("[\\/]Scripts[\\/]main%.lua$", ""))
local InboxPath = ModDir .. "\\inbox.lua"
local DonePath = ModDir .. "\\inbox.done.lua"
local LogPath = ModDir .. "\\probe.log"

local P = {}

---------------------------------------------------------------- logging

function P.Log(format, ...)
    local line = string.format(format, ...)
    print("[RonCompProbe] " .. line .. "\n")
    local file = io.open(LogPath, "a")
    if file then
        file:write(os.date("%H:%M:%S "), line, "\n")
        file:close()
    end
end
local Log = P.Log

function P.Valid(object)
    return object ~= nil and type(object) == "userdata" and object.IsValid ~= nil and object:IsValid()
end
local Valid = P.Valid

function P.Describe(value)
    if value == nil then return "nil" end
    if type(value) == "userdata" then
        local ok, text = pcall(function()
            if value.IsValid then
                return value:IsValid() and value:GetFullName() or "<invalid object>"
            end
            if value.ToString then return value:ToString() end
            if value.GetArrayNum then return "TArray(" .. value:GetArrayNum() .. ")" end
            return tostring(value)
        end)
        return ok and text or tostring(value)
    end
    if type(value) == "table" then
        local parts = {}
        for k, v in pairs(value) do parts[#parts + 1] = tostring(k) .. "=" .. P.Describe(v) end
        return "{" .. table.concat(parts, ", ") .. "}"
    end
    return tostring(value)
end
local Describe = P.Describe

---------------------------------------------------------------- game access

function P.World() return UEHelpers.GetWorld() end
function P.PC() return UEHelpers.GetPlayerController() end
function P.GM() return UEHelpers.GetGameModeBase() end
function P.GS() return UEHelpers.GetGameStateBase() end

function P.WorldName()
    local world = P.World()
    return Valid(world) and world:GetFullName() or "<no world>"
end

function P.Get(object, name)
    local ok, value = pcall(function() return object[name] end)
    if ok then return value end
    return nil
end

function P.Exec(command)
    local kismet = UEHelpers.GetKismetSystemLibrary()
    local world = P.World()
    if not Valid(kismet) or not Valid(world) then
        Log("exec skipped, no world: %s", command)
        return false
    end
    local controller = P.PC()
    local ok, err = pcall(function()
        kismet:ExecuteConsoleCommand(world, command, Valid(controller) and controller or nil)
    end)
    Log("exec %s: %s", ok and "ok" or ("FAILED " .. tostring(err)), command)
    return ok
end

-- Calls a static UFunction through its class default object, e.g.
-- P.CallStatic("/Script/ReadyOrNot.ReadyOrNotFunctionLibrary", "IsSecretPvP", P.World())
function P.CallStatic(classPath, functionName, ...)
    local package, class = classPath:match("^(.*)%.([^%.]+)$")
    local cdo = StaticFindObject(package .. ".Default__" .. class)
    if not Valid(cdo) then
        Log("CallStatic: no CDO for %s", classPath)
        return nil
    end
    local args = {...}
    local ok, result = pcall(function() return cdo[functionName](cdo, table.unpack(args)) end)
    Log("CallStatic %s:%s -> %s", class, functionName, ok and Describe(result) or ("FAILED " .. tostring(result)))
    if ok then return result end
    return nil
end

local ShotCount = 0
function P.Shot(tag)
    ShotCount = ShotCount + 1
    Log("screenshot #%d (%s)", ShotCount, tag or "")
    P.Exec("HighResShot 1")
end

P.StateProperties = {
    "MatchState", "CurrentMatchState", "PvPState", "bPvPMode", "DefusalMatchState",
    "CountdownUntilMatchStarts", "ElapsedRoundTime", "BombTimeRemaining",
    "RedTeamWins", "BlueTeamWins", "RoundsPlayed", "RoundsToPlay", "RoundTimeRemaining",
    "RoundWinningTeam", "MatchWinningTeam", "ModeURL_Replicated",
    "MinimumPlayersToStart", "GameStartWaitTime", "RespawnMode", "bCanRespawn",
}

function P.LogProps(tag, object, names)
    if not Valid(object) then
        Log("[%s] <invalid object>", tag)
        return
    end
    local owner = object:GetClass():GetFName():ToString()
    for _, name in ipairs(names or P.StateProperties) do
        local value = P.Get(object, name)
        if value ~= nil and not (type(value) == "userdata" and value.IsValid and not value:IsValid()) then
            Log("[%s]   %s.%s = %s", tag, owner, name, Describe(value))
        end
    end
end

function P.State(tag)
    tag = tag or "state"
    Log("[%s] world=%s", tag, P.WorldName())
    Log("[%s] gamemode=%s", tag, Valid(P.GM()) and P.GM():GetClass():GetFullName() or "<none>")
    Log("[%s] gamestate=%s", tag, Valid(P.GS()) and P.GS():GetClass():GetFullName() or "<none>")
    P.LogProps(tag, P.GM())
    P.LogProps(tag, P.GS())
    local pawn = UEHelpers.GetPlayer()
    Log("[%s] pawn=%s players=%d", tag, Valid(pawn) and pawn:GetClass():GetFullName() or "<none>", #UEHelpers.GetAllPlayerStates())
end

function P.Quit()
    P.Exec("quit")
end

---------------------------------------------------------------- remote console

local function RunInbox()
    local file = io.open(InboxPath, "r")
    if not file then return end
    local source = file:read("a")
    file:close()
    os.remove(DonePath)
    os.rename(InboxPath, DonePath)

    Log("---- inbox (%d bytes)", #source)
    local env = setmetatable({P = P, UEHelpers = UEHelpers}, {__index = function(_, key)
        if P[key] ~= nil then return P[key] end
        return _G[key]
    end})
    local chunk, compileError = load(source, "inbox", "t", env)
    if not chunk then
        Log("inbox compile error: %s", tostring(compileError))
        return
    end
    local results = table.pack(pcall(chunk))
    if not results[1] then
        Log("inbox runtime error: %s", tostring(results[2]))
    else
        for i = 2, results.n do Log("inbox result %d: %s", i - 1, Describe(results[i])) end
    end
    Log("---- inbox done")
end

---------------------------------------------------------------- tick

local LastSecond = 0
local LastWorld = ""
local ShotAt = nil

local function Tick()
    local now = os.time()
    if now == LastSecond then return end -- calls queued during a game-thread stall arrive in bursts
    LastSecond = now

    local world = P.WorldName()
    if world ~= LastWorld then
        Log("world changed: %s -> %s", LastWorld, world)
        LastWorld = world
        ShotAt = now + 8
    end
    if ShotAt and now >= ShotAt then
        ShotAt = nil
        P.State("arrived")
        P.Shot("after world change")
    end

    RunInbox()
end

-- Game thread only: Lua callbacks on UE4SS worker threads (LoopAsync, key binds) race the game
-- thread inside the same Lua state and can crash the game. Inbox scripts use
-- ExecuteInGameThreadWithDelay instead of ExecuteWithDelay for the same reason.
LoopInGameThreadWithDelay(1000, function()
    local ok, err = pcall(Tick)
    if not ok then Log("tick error: %s", tostring(err)) end
end)

Log("loaded; remote console at %s", InboxPath)
