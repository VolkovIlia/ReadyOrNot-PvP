-- HostBrain suspect equipment.

local C = require("hb_common")
local Log, Valid = C.Log, C.Valid

local L = {}

-- Every round hands the host a random pair of suspect-style guns and no armour or tactical gear, like
-- the AI suspects. The guns are player weapons (/Game/Blueprints/Items/WeaponsRevised): the AI
-- suspects' own weapons (WeaponsSuspect) have no magazines for a player, and drawing their pistols
-- breaks the first-person animation and throws the player out of the map.
-- AK-102, AK-103, G3A3 and Saiga-12 are left out: their handling (InertiaDragStrafeRotation/Location 1.0,
-- FreeAimLimitADS up to 4.5, against 0.4/0.2 and 1.0 on the SWAT MK18) throws the sights about when a
-- player aims while stepping sideways. SLR-47 is the AK-pattern rifle with SWAT-like handling.
-- Only rifles: their full metal jacket rounds (penetration 4) go through a SWAT player's default Kevlar
-- (armour level 3); pistol-calibre SMGs and buckshot (penetration 0-2) do not.
local SuspectPrimaries = {
    "Primary_SLR47", "Primary_FAL",
}
local SuspectSecondaries = {
    "Secondary_M1911_V2", "Secondary_M92FS_V2", "Secondary_G19_V2", "Secondary_Python_V2", "Secondary_P99",
}

local function PlayerWeapon(name)
    local path = string.format("/Game/Blueprints/Items/WeaponsRevised/%s.%s_C", name, name)
    local class = StaticFindObject(path)
    if not Valid(class) then
        pcall(LoadAsset, path)
        class = StaticFindObject(path)
    end
    return Valid(class) and class or nil
end

local function WeaponTitle(name)
    return (name:gsub("^%a+_", ""):gsub("_[Vv]%d+$", ""))
end

-- A magazine slot count of -1 gives each gun its default magazines (the game's own random loadouts
-- in GM_Firefight are built that way); a gun that still comes out empty is refilled.
local function FillMagazines(pawn)
    pawn.InventoryComp.InventoryItems:ForEach(function(_, element)
        local item = element:get()
        pcall(function()
            if item:GetMagazineCount() == 0 or not item:HasAnyAmmo() then
                item:ReplenishAmmo()
                Log("refilled %s: %d magazines", item:GetClass():GetFName():ToString(), item:GetMagazineCount())
            end
        end)
    end)
end

local function EquipSuspectLoadout(pawn)
    local primaryName = SuspectPrimaries[math.random(#SuspectPrimaries)]
    local secondaryName = SuspectSecondaries[math.random(#SuspectSecondaries)]
    local primary, secondary = PlayerWeapon(primaryName), PlayerWeapon(secondaryName)
    if not primary or not secondary then
        Log("suspect weapons %s / %s not found", primaryName, secondaryName)
        return nil
    end
    local helpers = StaticFindObject("/Script/ReadyOrNot.Default__BpGameplayHelperLib")
    if not Valid(helpers) then return nil end
    local ok, equipped = pcall(function()
        return helpers:EquipLoadoutOnPlayer({
            Primary = primary, PrimaryAmmoSlotsCount = -1,
            Secondary = secondary, SecondaryAmmoSlotsCount = -1,
            GrenadeSlotsCount = 0, TacticalSlotsCount = 0,
        }, pawn, { EquipItemCategory = 1, bReplicates = true, bSanitizeLoadout = false })
    end)
    if not ok or not equipped then
        Log("suspect loadout failed: %s", ok and "EquipLoadoutOnPlayer returned false" or tostring(equipped))
        return nil
    end
    pcall(FillMagazines, pawn)
    return WeaponTitle(primaryName) .. " + " .. WeaponTitle(secondaryName)
end

---------------------------------------------------------------- PvP: taking over an AI suspect

-- The player version of an AI suspect's gun (WeaponsSuspect class name without "_C"), so a player who
-- takes an AI's place fights with a gun of a similar kind. AKs and SMGs become the SLR-47, the G3,
-- machine guns and shotguns the FAL (see SuspectPrimaries for why).
local PlayerEquivalent = {
    Primary_AKM = "Primary_SLR47", Primary_S_AK103 = "Primary_SLR47", Primary_AK104 = "Primary_SLR47",
    Primary_AKS74U = "Primary_SLR47", Primary_QBZ = "Primary_SLR47", Primary_CAR = "Primary_SBR",
    Primary_Calico = "Primary_SLR47", Primary_UZI = "Primary_SLR47", Primary_M249 = "Primary_FAL",
    Primary_RPD = "Primary_FAL", Primary_S_G3A3 = "Primary_FAL", Primary_S_MK18_VAR1 = "Primary_MK18",
    Primary_S_MK18_VAR2 = "Primary_MK18", Primary_S_MK18_VAR3_CMAG = "Primary_MK18", Primary_M37 = "Primary_FAL",
    Primary_S_870mcs = "Primary_FAL", Primary_SawnOff = "Primary_FAL", Primary_Trenchgun = "Primary_FAL",
    Secondary_Makarov = "Secondary_M92FS_V2", Secondary_Makarov_2Handed = "Secondary_M92FS_V2",
    Secondary_S_G18 = "Secondary_G19_V2", Secondary_S_G19 = "Secondary_G19_V2", Secondary_S_M1911 = "Secondary_M1911_V2",
    Secondary_S_Python = "Secondary_Python_V2", Secondary_Tec9 = "Secondary_P99", Secondary_Flaregun = "Secondary_M1911_V2",
}

local NoArmorPath = "/Game/Blueprints/Items/ArmorRevised/Armor_NoArmor.Armor_NoArmor_C"
local NoHelmetPath = "/Game/Blueprints/Items/ArmorRevised/Helmet_None.Helmet_None_C"

local function LoadClass(path)
    local class = StaticFindObject(path)
    if not Valid(class) then
        pcall(LoadAsset, path)
        class = StaticFindObject(path)
    end
    return Valid(class) and class or nil
end

-- Player guns for an AI suspect's inventory; a random suspect-style pair fills what is missing.
local function GunsFor(ai)
    local primary, secondary
    pcall(function()
        ai.InventoryComp.InventoryItems:ForEach(function(_, element)
            local item = element:get()
            if Valid(item) then
                local name = item:GetClass():GetFName():ToString():gsub("_C$", "")
                if PlayerEquivalent[name] and name:find("^Primary_") then primary = primary or PlayerEquivalent[name] end
                if PlayerEquivalent[name] and name:find("^Secondary_") then secondary = secondary or PlayerEquivalent[name] end
            end
        end)
    end)
    return primary or SuspectPrimaries[math.random(#SuspectPrimaries)],
        secondary or SuspectSecondaries[math.random(#SuspectSecondaries)]
end

-- The next spawn of this player gets the suspect kit: the player spawns with PlayerState.ServerSavedLoadout
-- (verified: RespawnPlayer gave AK-103 4x30, M1911 3x7, no armour, no helmet). The game's own suspect
-- clothes (CoopGM.SuspectPlayerCustomizationOverride, the hidden co-op PvP outfit) go into the
-- loadout's customization.
local function PrepareSuspectSpawn(playerState, primaryName, secondaryName, gameMode)
    local loadout = playerState.ServerSavedLoadout
    loadout.Primary = PlayerWeapon(primaryName)
    loadout.PrimaryAmmoSlotsCount = -1
    loadout.Secondary = PlayerWeapon(secondaryName)
    loadout.SecondaryAmmoSlotsCount = -1
    loadout.Armor = LoadClass(NoArmorPath)
    loadout.Helmet = LoadClass(NoHelmetPath)
    loadout.GrenadeSlotsCount = 0
    loadout.TacticalSlotsCount = 0
    pcall(function() loadout.GrenadeSlots:Empty() end)
    pcall(function() loadout.TacticalSlots:Empty() end)
    if Valid(gameMode) then
        pcall(function()
            local outfit, saved = gameMode.SuspectPlayerCustomizationOverride, loadout.SavedCustomization
            for _, field in ipairs({ "Character", "Voice", "Helmet", "Shirt", "Pants", "Shoes", "Eyewear", "Belt", "Gloves", "Watch", "Tattoo" }) do
                saved[field] = outfit[field]
            end
            loadout.bHasCustomization = true
        end)
    end
    return WeaponTitle(primaryName) .. " + " .. WeaponTitle(secondaryName)
end

-- Puts the suspect kit on a living pawn: the mission-start spawn does not take ServerSavedLoadout, so
-- the kit is equipped directly (EquipLoadoutOnPlayer replaces armour and helmet with the "none" items).
local function EquipSuspectKit(pawn, primaryName, secondaryName)
    local helpers = StaticFindObject("/Script/ReadyOrNot.Default__BpGameplayHelperLib")
    if not Valid(helpers) then return false end
    local ok, equipped = pcall(function()
        return helpers:EquipLoadoutOnPlayer({
            Primary = PlayerWeapon(primaryName), PrimaryAmmoSlotsCount = -1,
            Secondary = PlayerWeapon(secondaryName), SecondaryAmmoSlotsCount = -1,
            Armor = LoadClass(NoArmorPath), Helmet = LoadClass(NoHelmetPath),
            GrenadeSlotsCount = 0, TacticalSlotsCount = 0,
        }, pawn, { EquipItemCategory = 1, bReplicates = true, bSanitizeLoadout = false })
    end)
    if not ok or not equipped then
        Log("suspect kit failed: %s", ok and "EquipLoadoutOnPlayer returned false" or tostring(equipped))
        return false
    end
    return true
end

-- The game's suspect clothes for players (CoopGM.SuspectPlayerCustomizationOverride, the hidden co-op
-- PvP outfit) through the replicated PlayerState.Customization; bForceLiveUpdate re-dresses the
-- living character. The player's saved customization is not touched: the next mission's PlayerState
-- starts from it again.
local OutfitFields = { "Character", "Voice", "Helmet", "Shirt", "Pants", "Shoes", "Eyewear", "Belt", "Gloves", "Watch", "Tattoo" }

local function ApplySuspectOutfit(playerState, gameMode)
    if not Valid(gameMode) then return false end
    local ok, err = pcall(function()
        local source = gameMode.SuspectPlayerCustomizationOverride
        local outfit = {}
        for _, field in ipairs(OutfitFields) do
            local value = source[field]
            if Valid(value) then outfit[field] = value end
        end
        playerState:Server_SetCustomization(outfit, true)
    end)
    if not ok then Log("suspect outfit failed: %s", tostring(err)) end
    return ok
end

-- Items a suspect must not carry: the SWAT kit's grenades, devices (zip cuffs, multitool, C2, tablet,
-- detonator, chem lights), the mirror gun, launchers and facewear.
local SwatGear = { "^Grenade_", "^Device_", "^DevicesDetonator", "^Mirrorgun", "^BP_Facewear", "^Launcher_", "^Optiwand" }

local function StripSwatGear(pawn)
    local doomed = {}
    pawn.InventoryComp.InventoryItems:ForEach(function(_, element)
        local item = element:get()
        if Valid(item) then
            local name = item:GetClass():GetFName():ToString()
            for _, pattern in ipairs(SwatGear) do
                if name:find(pattern) then doomed[#doomed + 1] = item break end
            end
        end
    end)
    for _, item in ipairs(doomed) do
        pcall(function() pawn.InventoryComp:DestroyInventoryItem(item) end)
    end
    return #doomed
end

-- The AI squad wears ceramic or steel plates (armour level 6) that no bullet in the game goes through
-- until a ceramic plate wears out, and steel never does: suspect players could only wound them in the
-- limbs. In PvP the squad wears the default SWAT player's Kevlar instead, as a SWAT player would.
local KevlarPath = "/Game/Blueprints/Items/ArmorRevised/ArmorMaterials/AM_Kevlar.AM_Kevlar"

local function ArmourSquad(swat)
    local kevlar = StaticFindObject(KevlarPath)
    if not Valid(kevlar) then
        pcall(LoadAsset, KevlarPath)
        kevlar = StaticFindObject(KevlarPath)
        if not Valid(kevlar) then return 0 end
    end
    local armourClass = StaticFindObject("/Script/ReadyOrNot.SWATArmour")
    local changed = 0
    for _, ai in ipairs(swat) do
        pcall(function()
            ai.InventoryComp.InventoryItems:ForEach(function(_, element)
                local item = element:get()
                if Valid(item) and item:IsA(armourClass) then
                    local material = item.ArmourMaterial
                    if not Valid(material) or material:GetAddress() ~= kevlar:GetAddress() then
                        item.ArmourMaterial = kevlar
                        changed = changed + 1
                    end
                end
            end)
        end)
    end
    if changed > 0 then Log("AI squad armour -> Kevlar: %d", changed) end
    return changed
end

L.SuspectPrimaries, L.SuspectSecondaries = SuspectPrimaries, SuspectSecondaries
L.PlayerWeapon, L.WeaponTitle, L.FillMagazines, L.EquipSuspectLoadout = PlayerWeapon, WeaponTitle, FillMagazines, EquipSuspectLoadout
L.GunsFor, L.PrepareSuspectSpawn, L.EquipSuspectKit, L.StripSwatGear = GunsFor, PrepareSuspectSpawn, EquipSuspectKit, StripSwatGear
L.ApplySuspectOutfit, L.ArmourSquad = ApplySuspectOutfit, ArmourSquad

return L
