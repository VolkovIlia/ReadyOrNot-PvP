-- HostBrain team menu: a CS2-style team choice drawn on the host's own pre-mission screen.
--
-- No pak is involved: the panel is built at runtime from UMG primitives (Border, boxes, TextBlock)
-- placed in the screen's root canvas, and the buttons are the game's W_StandardButton_C. Their clicks
-- (mouse or SimulateClicked) all pass through W_StandardButton_C::OnClicked_Derived, which is hooked
-- once and told apart by the button's address. Clients see none of it (no UE4SS there); they pick
-- teams in chat.

local C = require("hb_common")

local Log, Valid = C.Log, C.Valid

local M = {}

local Classes = {
    Border = "/Script/UMG.Border",
    VBox = "/Script/UMG.VerticalBox",
    HBox = "/Script/UMG.HorizontalBox",
    Text = "/Script/UMG.TextBlock",
    Size = "/Script/UMG.SizeBox",
    Button = "/Game/Blueprints/Widgets/Common/W_StandardButton.W_StandardButton_C",
}
local ClickHook = Classes.Button .. ":OnClicked_Derived"

-- W_StandardButton_C.DisplayStyle values (StandardButtonStyles has no names; picked on screen)
local Style = { Light = 0, Red = 3, Dark = 6, Yellow = 8 }

local Colors = {
    White = { 1, 1, 1 },
    Grey = { 0.62, 0.64, 0.68 },
    Swat = { 0.55, 0.75, 1 },
    SwatBot = { 0.45, 0.58, 0.75 },
    Suspect = { 1, 0.47, 0.42 },
    SuspectAi = { 0.78, 0.48, 0.45 },
}

local Lines = 10 -- names per column

local Menu = {
    Screen = nil,   -- address of the pre-mission screen the panel lives on
    Panel = nil,
    Buttons = {},   -- button address -> action
    Widgets = {},
    Hooked = nil,   -- address of the hooked OnClicked_Derived function
    Hidden = false,
    OnAction = nil, -- function(action) set by hb_pvp
}

---------------------------------------------------------------- building blocks

local function Make(tree, class)
    return StaticConstructObject(StaticFindObject(Classes[class]), tree)
end

local function Paint(text, color)
    pcall(function() text:SetColorAndOpacity({ SpecifiedColor = { R = color[1], G = color[2], B = color[3], A = 1 }, ColorUseRule = 0 }) end)
end

local function Text(tree, value, size, color)
    local text = Make(tree, "Text")
    text:SetText(FText(value))
    pcall(function()
        local font = text.Font
        font.Size = size
        text:SetFont(font)
    end)
    Paint(text, color or Colors.White)
    return text
end

local function Panel(tree, rgba, padding)
    local border = Make(tree, "Border")
    pcall(function() border.Background.DrawAs = 3 end) -- ESlateBrushDrawType::Image
    border:SetBrushColor({ R = rgba[1], G = rgba[2], B = rgba[3], A = rgba[4] })
    border:SetPadding({ Left = padding, Top = padding, Right = padding, Bottom = padding })
    return border
end

local function Add(box, child, top, bottom)
    local slot = box:AddChild(child)
    pcall(function() slot:SetPadding({ Left = 0, Top = top or 0, Right = 0, Bottom = bottom or 0 }) end)
    return slot
end

local function Button(screen, label, style, action)
    local wbl = StaticFindObject("/Script/UMG.Default__WidgetBlueprintLibrary")
    local button = wbl:Create(screen, StaticFindObject(Classes.Button), screen:GetOwningPlayer())
    button.DisplayStyle = style
    button.TextSize = 18
    button.ButtonText = FText(label)
    pcall(function() button:PreConstruct(false) end)
    pcall(function() button:SetButtonText(FText(label)) end)
    Menu.Buttons[tostring(button:GetAddress())] = action
    return button
end

local function SetLabel(button, label)
    if Menu.Widgets[button] ~= label then
        Menu.Widgets[button] = label
        pcall(function() button:SetButtonText(FText(label)) end)
    end
end

local function SetText(text, value)
    if Menu.Widgets[text] ~= value then
        Menu.Widgets[text] = value
        text:SetText(FText(value))
    end
end

---------------------------------------------------------------- layout

local function Column(screen, tree, title, color, background, joinLabel, joinStyle, joinAction)
    local size = Make(tree, "Size")
    pcall(function() size:SetWidthOverride(340) end)
    local border = Panel(tree, background, 16)
    size:SetContent(border)
    local box = Make(tree, "VBox")
    border:SetContent(box)
    local header = Text(tree, title, 24, color)
    Add(box, header, 0, 8)
    local lines = {}
    for i = 1, Lines do
        local line = Text(tree, "", 18, Colors.White)
        line:SetVisibility(1) -- Collapsed until used
        Add(box, line, 2, 2)
        lines[i] = line
    end
    local join = Button(screen, joinLabel, joinStyle, joinAction)
    Add(box, join, 14, 0)
    return size, { Header = header, Lines = lines, Join = join }
end

-- The panel's name carries a prefix, so a panel left by an earlier HostBrain (RestartMod drops the Lua
-- state, not the widgets) is found and removed. Names stay unique: reusing one would replace an object.
local PanelPrefix = "HostBrainTeamMenu"

local function RemoveOldPanels(root)
    for i = root:GetChildrenCount() - 1, 0, -1 do
        local child = root:GetChildAt(i)
        if Valid(child) and child:GetFName():ToString():find(PanelPrefix, 1, true) == 1 then child:RemoveFromParent() end
    end
end

local function Build(screen)
    local tree = screen.WidgetTree
    local root = tree.RootWidget
    Menu.Buttons, Menu.Widgets = {}, {}
    RemoveOldPanels(root)

    local name = FName(string.format("%s_%d_%d", PanelPrefix, os.time(), math.random(100000, 999999)))
    local panel = StaticConstructObject(StaticFindObject(Classes.Border), tree, name)
    pcall(function() panel.Background.DrawAs = 3 end)
    panel:SetBrushColor({ R = 0.02, G = 0.02, B = 0.03, A = 0.88 })
    panel:SetPadding({ Left = 26, Top = 26, Right = 26, Bottom = 26 })
    local slot = root:AddChildToCanvas(panel)
    slot:SetAnchors({ Minimum = { X = 0.5, Y = 0.5 }, Maximum = { X = 0.5, Y = 0.5 } })
    slot:SetAlignment({ X = 0.5, Y = 0.5 })
    slot:SetAutoSize(true)
    slot:SetPosition({ X = 0, Y = -30 })

    local box = Make(tree, "VBox")
    panel:SetContent(box)
    local title = Text(tree, "ВЫБОР КОМАНДЫ", 32, Colors.White)
    Add(box, title)
    local subtitle = Text(tree, "", 16, Colors.Grey)
    Add(box, subtitle, 2, 16)

    local columns = Make(tree, "HBox")
    Add(box, columns)
    local swatColumn, swat = Column(screen, tree, "SWAT", Colors.Swat, { 0.04, 0.08, 0.16, 0.92 },
        "ИГРАТЬ ЗА SWAT", Style.Light, "swat")
    columns:AddChild(swatColumn)
    local gap = Make(tree, "Size")
    pcall(function() gap:SetWidthOverride(16) end)
    columns:AddChild(gap)
    local suspectColumn, suspects = Column(screen, tree, "ПОДОЗРЕВАЕМЫЕ", Colors.Suspect, { 0.16, 0.04, 0.04, 0.92 },
        "ИГРАТЬ ЗА ПОДОЗРЕВАЕМЫХ", Style.Red, "suspect")
    columns:AddChild(suspectColumn)

    local settings = Make(tree, "HBox")
    Add(box, settings, 16, 0)
    local bots = Button(screen, "", Style.Dark, "bots")
    local accuracy = Button(screen, "", Style.Dark, "accuracy")
    local minutes = Button(screen, "", Style.Dark, "minutes")
    for i, button in ipairs({ bots, accuracy, minutes }) do
        local buttonSlot = settings:AddChild(button)
        pcall(function() buttonSlot:SetPadding({ Left = i > 1 and 10 or 0, Top = 0, Right = 0, Bottom = 0 }) end)
    end

    local hint = Text(tree, "Выберите сторону и нажмите «Готов». Остальные игроки выбирают сторону в чате: !swat или !suspect", 15, Colors.Grey)
    Add(box, hint, 14, 0)
    local ready = Button(screen, "ГОТОВ", Style.Yellow, "ready")
    Add(box, ready, 16, 0)

    Menu.Panel = panel
    Menu.Parts = {
        Subtitle = subtitle, Swat = swat, Suspects = suspects,
        Bots = bots, Accuracy = accuracy, Minutes = minutes, Ready = ready,
    }
end

---------------------------------------------------------------- interface for hb_pvp

local function OnClicked(context)
    local ok, address = pcall(function() return tostring(context:get():GetAddress()) end)
    local action = ok and Menu.Buttons[address]
    if not action or not Menu.OnAction then return end
    local done, err = pcall(Menu.OnAction, action)
    if not done then Log("team menu %s: %s", action, tostring(err)) end
end

local function HookClicks()
    local fn = StaticFindObject(ClickHook)
    if not Valid(fn) or Menu.Hooked == fn:GetAddress() then return end
    local ok, err = pcall(RegisterHook, ClickHook, OnClicked)
    if ok then Menu.Hooked = fn:GetAddress() else Log("team menu: cannot hook button clicks: %s", tostring(err)) end
end

local function FillColumn(column, entries)
    for i, line in ipairs(column.Lines) do
        local entry = entries[i]
        if entry then
            SetText(line, entry.Text)
            Paint(line, entry.Color)
            line:SetVisibility(4) -- SelfHitTestInvisible
        else
            line:SetVisibility(1)
        end
    end
end

-- state: { Subtitle, Swat = {entries}, Suspects = {entries}, SwatCount, SuspectCount, HostTeam ("swat"|"suspect"),
--          Bots, Accuracy, Minutes, Ready } where an entry is { Text, Color }.
function M.Show(screen, state, onAction)
    if not Valid(screen) then return end
    Menu.OnAction = onAction
    HookClicks()
    local address = screen:GetAddress()
    if Menu.Screen ~= address or not Valid(Menu.Panel) then
        Menu.Screen, Menu.Hidden = address, false
        local ok, err = pcall(Build, screen)
        if not ok then
            Log("team menu: cannot build: %s", tostring(err))
            Menu.Screen = nil
            return
        end
        Log("team menu shown on the pre-mission screen")
    end
    Menu.Panel:SetVisibility(Menu.Hidden and 1 or 0)
    if Menu.Hidden then return end
    local parts = Menu.Parts
    SetText(parts.Subtitle, state.Subtitle)
    SetText(parts.Swat.Header, string.format("SWAT · %d", state.SwatCount))
    SetText(parts.Suspects.Header, string.format("ПОДОЗРЕВАЕМЫЕ · %d", state.SuspectCount))
    FillColumn(parts.Swat, state.Swat)
    FillColumn(parts.Suspects, state.Suspects)
    SetLabel(parts.Swat.Join, state.HostTeam == "swat" and "ВЫ ЗА SWAT" or "ИГРАТЬ ЗА SWAT")
    SetLabel(parts.Suspects.Join, state.HostTeam == "suspect" and "ВЫ ЗА ПОДОЗРЕВАЕМЫХ" or "ИГРАТЬ ЗА ПОДОЗРЕВАЕМЫХ")
    SetLabel(parts.Bots, state.Bots and "БОТЫ SWAT: ВКЛ" or "БОТЫ SWAT: ВЫКЛ")
    SetLabel(parts.Accuracy, "МЕТКОСТЬ БОТОВ: " .. state.Accuracy)
    SetLabel(parts.Minutes, string.format("ВРЕМЯ: %d МИН", state.Minutes))
    SetLabel(parts.Ready, state.Ready and "ГОТОВ · ЖДЁМ ОСТАЛЬНЫХ" or "ГОТОВ")
end

-- Collapses the panel until Reopen (the game's own "Swap teams" button brings it back).
function M.Hide()
    Menu.Hidden = true
    if Valid(Menu.Panel) then pcall(function() Menu.Panel:SetVisibility(1) end) end
end

function M.Reopen()
    Menu.Hidden = false
end

function M.IsHidden()
    return Menu.Hidden
end

M.Colors = Colors

return M
