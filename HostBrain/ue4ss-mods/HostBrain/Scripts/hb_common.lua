-- HostBrain shared helpers: logging, console, worlds, character state, geometry, HUD messages.

local UEHelpers = require("UEHelpers")

local C = {}

---------------------------------------------------------------- basics

local function Log(format, ...)
    print(string.format("[HostBrain] " .. format .. "\n", ...))
end

local function Valid(object)
    return object ~= nil and type(object) == "userdata" and object.IsValid ~= nil and object:IsValid()
end

-- The local player's pawn; nil while there is none or while the controller is between pawns (a death
-- can make UEHelpers.GetPlayer fail for a frame).
local function HostPawn()
    local ok, pawn = pcall(UEHelpers.GetPlayer)
    return ok and Valid(pawn) and pawn or nil
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

---------------------------------------------------------------- teams and worlds

-- ETeamType values; SWATManager orders addressed to TT_SQUAD go to the whole AI squad.
local TeamSwatRed = 1
local TeamSwatBlue = 2
local TeamSuspect = 3
local TeamSquad = 5
local CoopMode = "BS_COOP"

-- Counts loaded worlds. Reloading a mission may put the new UWorld at the old one's address, but the
-- new world's clock starts again from zero.
local Worlds = { Key = nil, Time = 0, Generation = 0 }

local function TrackWorld()
    local world = UEHelpers.GetWorld()
    if not Valid(world) then return end
    local key = tostring(world:GetAddress())
    local now = UEHelpers.GetGameplayStatics():GetTimeSeconds(world)
    if key ~= Worlds.Key or now < Worlds.Time then
        Worlds.Key = key
        Worlds.Generation = Worlds.Generation + 1
    end
    Worlds.Time = now
end

local function WorldTime()
    local world = UEHelpers.GetWorld()
    return Valid(world) and UEHelpers.GetGameplayStatics():GetTimeSeconds(world) or 0
end

---------------------------------------------------------------- characters

-- Why a character is out of the fight (nil while it fights): dead, unconscious, downed, arrested or
-- surrendered. Anything that is not a character (the spectator pawn before a spawn and after a
-- death) is out as well.
local function DownReason(character)
    if not Valid(character) then return "no pawn" end
    local ok, reason = pcall(function()
        if character:IsDeadOrUnconscious() then return "dead" end
        if character:IsIncapacitated() then return "incapacitated" end
        if character:IsArrested() then return "arrested" end
        if character:IsSurrendered() then return "surrendered" end
        return nil
    end)
    if not ok then return "not a character: " .. character:GetClass():GetFName():ToString() end
    return reason
end

local function IsDown(character)
    return DownReason(character) ~= nil
end

local function Location(actor)
    local at = actor:K2_GetActorLocation()
    return { X = at.X, Y = at.Y, Z = at.Z }
end

local function Distance(a, b)
    return math.sqrt((a.X - b.X) ^ 2 + (a.Y - b.Y) ^ 2 + (a.Z - b.Z) ^ 2)
end

-- The combat AI SWAT of a co-op mission (CyberneticsSwatTrailer_C are non-combat extras).
local function LivingSwat()
    local swat = {}
    for _, character in ipairs(FindAllOf("CyberneticsSwat_V2_C") or {}) do
        if not IsDown(character) then swat[#swat + 1] = character end
    end
    return swat
end

local NoColor = { R = 0, G = 0, B = 0, A = 0 }

-- Visibility trace (KismetSystemLibrary::LineTraceSingle); nil when the trace itself fails.
local function TraceBlocked(from, to, ignore)
    local ok, hit = pcall(function()
        return UEHelpers.GetKismetSystemLibrary():LineTraceSingle(UEHelpers.GetWorld(), from, to, 0, false, ignore, 0, {},
            true, NoColor, NoColor, 0)
    end)
    if not ok then return nil end
    return hit
end

-- Puts a player pawn among the AI suspects instead of next to the SWAT van. Spots go round a living
-- suspect (8 directions, 1.5 to 3 m): the suspect must see the spot (not behind a wall) and it needs a
-- floor below. AActor::TeleportTo then refuses a spot where the pawn's capsule would overlap furniture
-- or walls and nudges it out of small overlaps, so it never lands inside a desk or a chair. Spots
-- within 1.5 m of "avoid" are skipped (comp_unstuck). When the traces fail, the collision check alone
-- decides.
local function PlaceNextToSuspect(pawn, avoid)
    for _, useTraces in ipairs({ true, false }) do
        for _, suspect in ipairs(FindAllOf("CyberneticsSuspect_V2_C") or {}) do
            if not IsDown(suspect) then
                local at = Location(suspect)
                local yaw = suspect:K2_GetActorRotation().Yaw
                for _, distance in ipairs({ 150, 220, 300 }) do
                    for step = 0, 7 do
                        local angle = math.rad(yaw + step * 45)
                        local spot = { X = at.X + math.cos(angle) * distance, Y = at.Y + math.sin(angle) * distance, Z = at.Z + 10 }
                        local usable = not avoid or Distance(spot, avoid) > 150
                        if usable and useTraces then
                            local ignore = { suspect, pawn }
                            usable = TraceBlocked({ X = at.X, Y = at.Y, Z = at.Z + 60 }, { X = spot.X, Y = spot.Y, Z = spot.Z + 60 }, ignore) == false
                                and TraceBlocked(spot, { X = spot.X, Y = spot.Y, Z = spot.Z - 250 }, ignore) == true
                        end
                        if usable then
                            local ok, moved = pcall(function() return pawn:K2_TeleportTo(spot, { Pitch = 0, Yaw = yaw, Roll = 0 }) end)
                            if ok and moved then
                                Log("placed %.1f m from an AI suspect (%s)", distance / 100, useTraces and "traced spot" or "collision check only")
                                return true
                            end
                        end
                    end
                end
            end
        end
    end
    return false
end

---------------------------------------------------------------- messages

-- Messages go to the host's HUD: a banner at the bottom centre and toasts on the left. The death
-- screen hides the HUD, so round results are repeated when the next round has loaded.
local function Hud()
    for _, hud in ipairs(FindAllOf("W_HumanCharacter_HUD_V2_C") or {}) do
        if hud:IsValid() and hud:IsInViewport() then return hud end
    end
    return nil
end

local function Banner(text)
    Log("%s", text)
    local hud = Hud()
    if hud then pcall(function() hud:AddObjectivePopup(FText(text)) end) end
end

local function Toast(text)
    Log("%s", text)
    local hud = Hud()
    if hud then pcall(function() hud:AddToast(text) end) end
end

local function Clock(seconds)
    return string.format("%d:%02d", seconds // 60, seconds % 60)
end

C.Log, C.Valid, C.HostPawn, C.Exec, C.ReadFile = Log, Valid, HostPawn, Exec, ReadFile
C.TeamSwatRed, C.TeamSwatBlue, C.TeamSuspect, C.TeamSquad, C.CoopMode = TeamSwatRed, TeamSwatBlue, TeamSuspect, TeamSquad, CoopMode
C.Worlds, C.TrackWorld, C.WorldTime = Worlds, TrackWorld, WorldTime
C.DownReason, C.IsDown, C.Location, C.Distance, C.LivingSwat = DownReason, IsDown, Location, Distance, LivingSwat
C.TraceBlocked, C.PlaceNextToSuspect = TraceBlocked, PlaceNextToSuspect
C.Hud, C.Banner, C.Toast, C.Clock = Hud, Banner, Toast, Clock

return C
