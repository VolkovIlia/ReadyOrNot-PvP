-- HostBrain squad hunt: the co-op AI SWAT squad hunting suspect players with no SWAT player to lead it
-- (the solo mode, and PvP with bots).
--
-- The squad learns where its targets are only the way it would in a mission: an AI SWAT sees one of them
-- or hears their shots. Without contact it clears the building room by room; a long stalemate gives it a
-- rough area around a target (Settings.Hints).

local C = require("hb_common")

local Log, Valid, IsDown, Location, Distance = C.Log, C.Valid, C.IsDown, C.Location, C.Distance

local H = {}

H.Settings = {
    HearRange = 4000,  -- cm: AI SWAT closer than this to a shot learn where it came from
    Hints = true,
    HintAfter = 60,    -- seconds without contact before a hint
    HintSpread = 1500, -- cm: random offset of a hint from a target
}

local Hunt = {
    Targets = {},      -- address -> true for the pawns being hunted (refreshed by H.Direct)
    Contact = nil,     -- { Location, Time, Source } of the latest sighting, gunshot or hint
    Ordered = nil,     -- the contact the squad was last sent to
    LastOrder = 0,
    LastHint = 0,
    Searching = false,
    Shot = nil,        -- location of a target's gunshot not yet processed
}

function H.SquadManager()
    local manager = FindFirstOf("SWATManager")
    return Valid(manager) and manager or nil
end

-- Orders go to the squad leader's team, and the squad follows its leader. In a co-op mission the host
-- leads it, so when the leader is down or is one of the hunted pawns a living AI SWAT takes the lead.
function H.Lead(manager, swat, hunted)
    local leader = manager.SquadLeader
    local replace = IsDown(leader)
    if not replace then
        local address = leader:GetAddress()
        for _, pawn in ipairs(hunted or {}) do
            if Valid(pawn) and pawn:GetAddress() == address then replace = true end
        end
    end
    if replace and #swat > 0 then manager.SquadLeader = swat[1] end
end

local function Order(manager, command, location)
    local ok, err = pcall(function()
        if command == "move" then
            manager:GiveMoveCommand(C.TeamSquad, location)
        else
            manager:GiveSearchAndSecureCommand(C.TeamSquad, location, false)
        end
    end)
    if not ok then Log("squad order %s failed: %s", command, tostring(err)) end
end

function H.Reset(now)
    Hunt.Targets, Hunt.Contact, Hunt.Ordered, Hunt.Shot = {}, nil, nil, nil
    Hunt.LastOrder, Hunt.LastHint, Hunt.Searching = now, now, false
end

local function Nearest(targets, from)
    local best, bestDistance = targets[1], math.huge
    for _, pawn in ipairs(targets) do
        local distance = Distance(Location(pawn), from)
        if distance < bestDistance then best, bestDistance = pawn, distance end
    end
    return best
end

-- One step of the hunt: targets are the living suspect pawns, swat the living AI SWAT.
function H.Direct(now, targets, swat)
    local manager = H.SquadManager()
    if not manager or #targets == 0 or #swat == 0 then return end
    H.Lead(manager, swat, targets)
    Hunt.Targets = {}
    for _, pawn in ipairs(targets) do Hunt.Targets[tostring(pawn:GetAddress())] = true end

    local seen = nil
    for _, character in ipairs(swat) do
        pcall(function()
            for _, pawn in ipairs(targets) do
                if not seen and character.Controller.TargetingComponent:CanCharacterBeSeen(pawn) then seen = pawn end
            end
        end)
    end
    if seen then
        Hunt.Contact = { Location = Location(seen), Time = now, Source = "sighting" }
    elseif Hunt.Shot then
        for _, character in ipairs(swat) do
            if Distance(Location(character), Hunt.Shot) <= H.Settings.HearRange then
                Hunt.Contact = { Location = Hunt.Shot, Time = now, Source = "gunshot" }
                break
            end
        end
    end
    Hunt.Shot = nil
    local leaderAt = Location(manager.SquadLeader)
    local lastNews = math.max(Hunt.Contact and Hunt.Contact.Time or 0, Hunt.LastHint)
    if H.Settings.Hints and now - lastNews >= H.Settings.HintAfter then
        local here = Location(Nearest(targets, leaderAt))
        local angle, offset = math.random() * 2 * math.pi, math.random() * H.Settings.HintSpread
        Hunt.Contact = {
            Location = { X = here.X + math.cos(angle) * offset, Y = here.Y + math.sin(angle) * offset, Z = here.Z },
            Time = now,
            Source = "hint",
        }
        Hunt.LastHint = now
    end
    if seen then return end -- in contact: the fire director handles it
    if Hunt.Contact and Hunt.Contact ~= Hunt.Ordered then
        Order(manager, "move", Hunt.Contact.Location)
        Log("squad: moving to the last %s, %.0f m from the nearest suspect", Hunt.Contact.Source,
            Distance(Hunt.Contact.Location, Location(Nearest(targets, Hunt.Contact.Location))) / 100)
        Hunt.Ordered, Hunt.LastOrder, Hunt.Searching = Hunt.Contact, now, false
    elseif not Hunt.Searching then
        -- At the last contact (or without one): clear the rooms from there.
        local target = Hunt.Ordered and Hunt.Ordered.Location
        if not target or Distance(leaderAt, target) < 600 or now - Hunt.LastOrder >= 45 then
            Order(manager, "search", target or leaderAt)
            Log("squad: search and secure from %s", target and "the last contact" or "its position")
            Hunt.Searching, Hunt.LastOrder = true, now
        end
    end
end

-- Weapons fire through the Server_OnFire / Multicast_OnFire RPCs; only the hunted pawns' shots count.
local function OnWeaponFire(context)
    if next(Hunt.Targets) == nil then return end
    local ok, owner = pcall(function() return context:get():GetOwner() end)
    if ok and Valid(owner) and Hunt.Targets[tostring(owner:GetAddress())] then
        Hunt.Shot = Location(owner)
    end
end

for _, rpc in ipairs({ "Server_OnFire", "Multicast_OnFire" }) do
    local ok, err = pcall(RegisterHook, "/Script/ReadyOrNot.BaseMagazineWeapon:" .. rpc, OnWeaponFire)
    if not ok then Log("cannot hook %s: %s", rpc, tostring(err)) end
end

return H
