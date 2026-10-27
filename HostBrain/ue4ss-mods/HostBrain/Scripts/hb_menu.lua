-- HostBrain team menu: a CS2-style team choice drawn over the host's own pre-mission screen.
--
-- No pak is involved: the page is built at runtime from UMG primitives (Border, boxes, SizeBox,
-- TextBlock) placed in the screen's root canvas, and the buttons are the game's W_StandardButton_C.
-- Their clicks (mouse or SimulateClicked) all pass through W_StandardButton_C::OnClicked_Derived,
-- which is hooked once and told apart by the button's address. Clients see none of it (no UE4SS
-- there); they pick teams in chat.
--
-- Layout, after CS2's team select: a dark full-screen page, "ВЫБЕРИТЕ КОМАНДУ", two team cards side by
-- side (SWAT blue, suspects orange) with a coloured header, "players / 5", the player slots (bots fill
-- SWAT's free slots by their squad names) and a join button; below, the match settings, auto-select
-- and Ready.
--
-- Between rounds the same page shows the round result instead, after CS2's round-end and match-end
-- screens: the winning side in its colour, the reason, the score in the two teams' colours, what comes
-- next (halftime swap, countdown) and the round or match buttons.

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

-- UMG enums
local Visible, Collapsed, SelfHitTestInvisible = 0, 1, 4
local AlignLeft, AlignCenter, AlignRight = 1, 2, 3
local SizeAuto, SizeFill = 0, 1

-- UMG colours are linear: 0.2 shows as about 0.48 on screen.
local Colors = {
    White = { 1, 1, 1 },
    Grey = { 0.32, 0.34, 0.37 },
    Dim = { 0.16, 0.17, 0.19 },
    Yellow = { 1, 0.62, 0.05 },
    Swat = { 0.3, 0.5, 1 },
    SwatBot = { 0.22, 0.32, 0.55 },
    Suspect = { 1, 0.5, 0.12 },
    SuspectAi = { 0.62, 0.32, 0.1 },
}

local Teams = {
    swat = {
        Title = "SWAT", Header = { 0.04, 0.1, 0.27, 1 }, HeaderChosen = { 0.07, 0.19, 0.5, 1 },
        Body = { 0.006, 0.012, 0.025, 0.96 }, Accent = Colors.Swat, JoinStyle = Style.Light,
    },
    suspect = {
        Title = "ПОДОЗРЕВАЕМЫЕ", Header = { 0.36, 0.13, 0.015, 1 }, HeaderChosen = { 0.6, 0.24, 0.03, 1 },
        Body = { 0.025, 0.012, 0.004, 0.96 }, Accent = Colors.Suspect, JoinStyle = Style.Red,
    },
}

local Slots = 5    -- per team, as in a 5v5
local MaxRows = 8  -- rows a card can show (players beyond five, the AI line)

local Menu = {
    Screen = nil,   -- address of the pre-mission screen the page lives on
    Page = nil,
    Parts = nil,
    Buttons = {},   -- button address -> action
    Shown = {},     -- widget -> last text, colour or label
    Hooked = nil,   -- address of the hooked OnClicked_Derived function
    Hidden = false,
    OnAction = nil, -- function(action) set by hb_pvp
}

---------------------------------------------------------------- building blocks

-- FMargin's fields are reflected as Left, top, Right, bottom in this build (FName casing), and UE4SS
-- matches struct keys case-sensitively, so both spellings are given.
local function Margin(left, top, right, bottom)
    return { Left = left, Right = right, top = top, bottom = bottom, Top = top, Bottom = bottom }
end

local function Make(tree, class, name)
    if name then return StaticConstructObject(StaticFindObject(Classes[class]), tree, name) end
    return StaticConstructObject(StaticFindObject(Classes[class]), tree)
end

local function Paint(text, color)
    local key = table.concat(color, ",")
    if Menu.Shown[text] == key then return end
    Menu.Shown[text] = key
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

local function Fill(tree, rgba, left, top, right, bottom)
    local border = Make(tree, "Border")
    pcall(function() border.Background.DrawAs = 3 end) -- ESlateBrushDrawType::Image
    border:SetBrushColor({ R = rgba[1], G = rgba[2], B = rgba[3], A = rgba[4] })
    border:SetPadding(Margin(left or 0, top or left or 0, right or left or 0, bottom or top or left or 0))
    return border
end

local function Recolor(border, rgba)
    local key = table.concat(rgba, ",")
    if Menu.Shown[border] == key then return end
    Menu.Shown[border] = key
    border:SetBrushColor({ R = rgba[1], G = rgba[2], B = rgba[3], A = rgba[4] })
end

local function Sized(tree, child, width, height)
    local size = Make(tree, "Size")
    if width then pcall(function() size:SetWidthOverride(width) end) end
    if height then pcall(function() size:SetHeightOverride(height) end) end
    size:SetContent(child)
    return size
end

-- Adds to a vertical or horizontal box; pad = { left, top, right, bottom }. In a horizontal box
-- valign centres the child vertically.
local function Add(box, child, pad, align, fill, valign)
    local slot = box:AddChild(child)
    if pad then pcall(function() slot:SetPadding(Margin(pad[1] or 0, pad[2] or 0, pad[3] or 0, pad[4] or 0)) end) end
    if align then pcall(function() slot:SetHorizontalAlignment(align) end) end
    if fill then pcall(function() slot:SetSize({ SizeRule = SizeFill, Value = 1 }) end) end
    if valign then pcall(function() slot:SetVerticalAlignment(valign) end) end
    return slot, child
end

local function Button(screen, label, style, action, size)
    local wbl = StaticFindObject("/Script/UMG.Default__WidgetBlueprintLibrary")
    local button = wbl:Create(screen, StaticFindObject(Classes.Button), screen:GetOwningPlayer())
    button.DisplayStyle = style
    button.TextSize = size or 18
    button.ButtonText = FText(label)
    pcall(function() button:PreConstruct(false) end)
    pcall(function() button:SetButtonText(FText(label)) end)
    Menu.Buttons[tostring(button:GetAddress())] = action
    return button
end

local function SetLabel(button, label)
    if Menu.Shown[button] ~= label then
        Menu.Shown[button] = label
        pcall(function() button:SetButtonText(FText(label)) end)
    end
end

local function SetText(text, value)
    if Menu.Shown[text] ~= value then
        Menu.Shown[text] = value
        text:SetText(FText(value))
    end
end

local function Show(widget, on, shown)
    local value = on and (shown or SelfHitTestInvisible) or Collapsed
    if Menu.Shown[widget] ~= value then
        Menu.Shown[widget] = value
        widget:SetVisibility(value)
    end
end

---------------------------------------------------------------- layout

local function Card(screen, tree, key)
    local team = Teams[key]
    local body = Fill(tree, team.Body, 0)
    local box = Make(tree, "VBox")
    body:SetContent(box)

    local header = Fill(tree, team.Header, 22, 16, 22, 16)
    Add(box, header)
    local headerRow = Make(tree, "HBox")
    header:SetContent(headerRow)
    Add(headerRow, Text(tree, team.Title, 32, Colors.White), nil, nil, true)
    local count = Text(tree, "0 / 5", 28, Colors.White)
    Add(headerRow, count, { 24, 4, 0, 0 })

    local list = Make(tree, "VBox")
    Add(box, list, { 22, 18, 22, 0 })
    Add(list, Text(tree, "ИГРОКИ", 14, team.Accent), { 0, 0, 0, 8 })
    local rows = {}
    for i = 1, MaxRows do
        local row = Fill(tree, { 0, 0, 0, 0.45 }, 14, 9, 14, 9)
        local text = Text(tree, "", 20, Colors.White)
        row:SetContent(text)
        local _, holder = Add(list, row, { 0, 3, 0, 3 })
        rows[i] = { Row = holder, Text = text }
    end
    local status = Text(tree, "", 16, team.Accent)
    Add(list, status, { 0, 12, 0, 0 })
    local join = Button(screen, "ВСТУПИТЬ", team.JoinStyle, key, 22)
    Add(box, join, { 22, 14, 22, 22 })
    return Sized(tree, body, 560), { Header = header, Count = count, Rows = rows, Status = status, Join = join }
end

-- One side of the score: the team's name and its round wins on the team colour, the number next to
-- the colon in the middle.
local function ScoreBox(tree, key, label, numberFirst)
    local box = Fill(tree, Teams[key].Header, 30, 10, 30, 10)
    pcall(function() box:SetHorizontalAlignment(numberFirst and AlignLeft or AlignRight) end)
    pcall(function() box:SetVerticalAlignment(AlignCenter) end)
    local row = Make(tree, "HBox")
    box:SetContent(row)
    local name = Text(tree, label, 28, Colors.White)
    local number = Text(tree, "0", 72, Colors.White)
    if numberFirst then
        Add(row, number, nil, nil, nil, AlignCenter)
        Add(row, name, { 24, 0, 0, 0 }, nil, nil, AlignCenter)
    else
        Add(row, name, nil, nil, nil, AlignCenter)
        Add(row, number, { 24, 0, 0, 0 }, nil, nil, AlignCenter)
    end
    return Sized(tree, box, 460, 120), { Box = box, Number = number }
end

local function ResultPage(screen, tree, box)
    local top = Text(tree, "", 22, Colors.Grey)
    Add(box, top, nil, AlignCenter)
    local winner = Text(tree, "", 68, Colors.White)
    Add(box, winner, { 0, 4, 0, 0 }, AlignCenter)
    local reason = Text(tree, "", 22, Colors.Grey)
    Add(box, reason, { 0, 0, 0, 34 }, AlignCenter)

    local scores = Make(tree, "HBox")
    Add(box, scores, nil, AlignCenter)
    local swatBox, swat = ScoreBox(tree, "swat", "SWAT", false)
    Add(scores, swatBox, nil, nil, nil, AlignCenter)
    Add(scores, Text(tree, ":", 64, Colors.Grey), { 22, 0, 22, 0 }, nil, nil, AlignCenter)
    local suspectBox, suspect = ScoreBox(tree, "suspect", "ПОДОЗРЕВАЕМЫЕ", true)
    Add(scores, suspectBox, nil, nil, nil, AlignCenter)

    local notice = Text(tree, "", 26, Colors.Yellow)
    Add(box, notice, { 0, 34, 0, 0 }, AlignCenter)
    local countdown = Text(tree, "", 22, Colors.White)
    Add(box, countdown, { 0, 12, 0, 0 }, AlignCenter)

    local buttons = Make(tree, "HBox")
    Add(box, buttons, { 0, 30, 0, 0 }, AlignCenter)
    local startNow = Sized(tree, Button(screen, "НАЧАТЬ СЕЙЧАС", Style.Yellow, "startnow", 22), 300)
    local teams = Button(screen, "КОМАНДЫ И НАСТРОЙКИ", Style.Dark, "teams")
    local reset = Button(screen, "СБРОСИТЬ МАТЧ", Style.Dark, "newmatch")
    local newMatch = Sized(tree, Button(screen, "НОВЫЙ МАТЧ", Style.Yellow, "newmatch", 24), 320)
    Add(buttons, startNow, nil, nil, nil, AlignCenter)
    Add(buttons, teams, { 16, 0, 0, 0 }, nil, nil, AlignCenter)
    Add(buttons, reset, { 16, 0, 0, 0 }, nil, nil, AlignCenter)
    Add(buttons, newMatch, nil, nil, nil, AlignCenter)
    return {
        Root = box, Top = top, Winner = winner, Reason = reason, Swat = swat, Suspect = suspect,
        Notice = notice, Countdown = countdown, RoundButtons = { startNow, teams, reset }, NewMatch = newMatch,
    }
end

-- The page's name carries a prefix, so a page left by an earlier HostBrain (RestartMod drops the Lua
-- state, not the widgets) is found and removed. Names stay unique: reusing one would replace an object.
local PagePrefix = "HostBrainTeamMenu"

local function RemoveOldPages(root)
    for i = root:GetChildrenCount() - 1, 0, -1 do
        local child = root:GetChildAt(i)
        if Valid(child) and child:GetFName():ToString():find(PagePrefix, 1, true) == 1 then child:RemoveFromParent() end
    end
end

local function Build(screen)
    local tree = screen.WidgetTree
    local root = tree.RootWidget
    Menu.Buttons, Menu.Shown = {}, {}
    RemoveOldPages(root)

    local name = FName(string.format("%s_%d_%d", PagePrefix, os.time(), math.random(100000, 999999)))
    local page = Make(tree, "Border", name)
    pcall(function() page.Background.DrawAs = 3 end)
    page:SetBrushColor({ R = 0.01, G = 0.012, B = 0.016, A = 0.86 })
    pcall(function() page:SetHorizontalAlignment(AlignCenter) end)
    pcall(function() page:SetVerticalAlignment(AlignCenter) end)
    local slot = root:AddChildToCanvas(page)
    slot:SetAnchors({ Minimum = { X = 0, Y = 0 }, Maximum = { X = 1, Y = 1 } })
    slot:SetOffsets(Margin(0, 0, 0, 0))

    local content = Make(tree, "VBox")
    page:SetContent(content)

    local box = Make(tree, "VBox") -- the team page
    Add(content, box, nil, AlignCenter)
    Add(box, Text(tree, "ВЫБЕРИТЕ КОМАНДУ", 54, Colors.White), nil, AlignCenter)
    local subtitle = Text(tree, "", 18, Colors.Grey)
    Add(box, subtitle, { 0, 4, 0, 30 }, AlignCenter)

    local cards = Make(tree, "HBox")
    Add(box, cards, nil, AlignCenter)
    local swatCard, swat = Card(screen, tree, "swat")
    Add(cards, swatCard, { 0, 0, 20, 0 })
    local suspectCard, suspects = Card(screen, tree, "suspect")
    Add(cards, suspectCard, { 20, 0, 0, 0 })

    local bar = Make(tree, "HBox")
    Add(box, bar, { 0, 28, 0, 0 }, AlignCenter)
    local bots = Button(screen, "", Style.Dark, "bots")
    local accuracy = Button(screen, "", Style.Dark, "accuracy")
    local minutes = Button(screen, "", Style.Dark, "minutes")
    local rounds = Button(screen, "", Style.Dark, "rounds")
    local swap = Button(screen, "", Style.Dark, "swap")
    for i, button in ipairs({ bots, accuracy, minutes, rounds, swap }) do
        Add(bar, button, { i > 1 and 12 or 0, 0, 0, 0 })
    end
    local actions = Make(tree, "HBox")
    Add(box, actions, { 0, 14, 0, 0 }, AlignCenter)
    Add(actions, Button(screen, "АВТОВЫБОР", Style.Dark, "auto"), nil, nil, nil, AlignCenter)
    local ready = Button(screen, "ГОТОВ", Style.Yellow, "ready", 24)
    Add(actions, Sized(tree, ready, 260), { 24, 0, 0, 0 })

    local hint = Text(tree, "Остальные игроки выбирают сторону в чате: !swat или !suspect · список команд: !teams", 15, Colors.Dim)
    Add(box, hint, { 0, 18, 0, 0 }, AlignCenter)

    local result = Make(tree, "VBox") -- the round result page
    Add(content, result, nil, AlignCenter)

    Menu.Page = page
    Menu.Parts = {
        Teams = box, Subtitle = subtitle, Cards = { swat = swat, suspect = suspects },
        Bots = bots, Accuracy = accuracy, Minutes = minutes, Rounds = rounds, Swap = swap, Ready = ready,
        Result = ResultPage(screen, tree, result),
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

-- A card's rows: its players, then (SWAT) bots by squad name in the free slots or (suspects) the line
-- for the mission's AI suspects, then free slots up to five.
local function FillCard(card, key, entries, chosen)
    local team = Teams[key]
    Recolor(card.Header, chosen and team.HeaderChosen or team.Header)
    for i, row in ipairs(card.Rows) do
        local entry = entries[i]
        if not entry and i <= Slots then entry = { Text = "свободно", Color = Colors.Dim } end
        if entry then
            SetText(row.Text, entry.Text)
            Paint(row.Text, entry.Color)
            Show(row.Row, true)
        else
            Show(row.Row, false)
        end
    end
    SetText(card.Status, chosen and "ВЫ В ЭТОЙ КОМАНДЕ" or "")
    SetLabel(card.Join, chosen and "ВЫ ЗДЕСЬ" or "ВСТУПИТЬ")
end

local function RoundsLabel(rounds)
    if rounds == 1 then return "МАТЧ: 1 РАУНД" end
    return string.format("МАТЧ: ДО %d ПОБЕД", rounds)
end

-- result: { Top, Winner, WinnerSide ("swat"|"suspect"), Reason, SwatScore, SuspectScore, Notice, Countdown }
local function FillResult(page, result, final)
    SetText(page.Top, result.Top)
    SetText(page.Winner, result.Winner)
    Paint(page.Winner, Teams[result.WinnerSide].Accent)
    SetText(page.Reason, result.Reason)
    SetText(page.Swat.Number, tostring(result.SwatScore))
    SetText(page.Suspect.Number, tostring(result.SuspectScore))
    Recolor(page.Swat.Box, result.WinnerSide == "swat" and Teams.swat.HeaderChosen or Teams.swat.Header)
    Recolor(page.Suspect.Box, result.WinnerSide == "suspect" and Teams.suspect.HeaderChosen or Teams.suspect.Header)
    SetText(page.Notice, result.Notice or "")
    SetText(page.Countdown, result.Countdown or "")
    for _, button in ipairs(page.RoundButtons) do Show(button, not final) end
    Show(page.NewMatch, final)
end

-- state: { Mode ("teams"|"round"|"final"), Result (round and final pages, see FillResult), and for the
--          team page Subtitle, Swat = {entries}, Suspects = {entries}, SwatCount, SuspectCount,
--          HostTeam ("swat"|"suspect"), Bots, Accuracy, Minutes, RoundsToWin, Swap, Ready } where an
--          entry is { Text, Color }.
function M.Show(screen, state, onAction)
    if not Valid(screen) then return end
    Menu.OnAction = onAction
    HookClicks()
    local address = screen:GetAddress()
    if Menu.Screen ~= address or not Valid(Menu.Page) then
        Menu.Screen, Menu.Hidden = address, false
        local ok, err = pcall(Build, screen)
        if not ok then
            Log("team menu: cannot build: %s", tostring(err))
            Menu.Screen = nil
            return
        end
        Log("team menu shown on the pre-mission screen")
    end
    Show(Menu.Page, not Menu.Hidden, Visible) -- Visible: the page takes the clicks meant for the screen under it
    if Menu.Hidden then return end
    local parts = Menu.Parts
    local mode = state.Mode or "teams"
    Show(parts.Teams, mode == "teams")
    Show(parts.Result.Root, mode ~= "teams")
    if mode ~= "teams" then
        FillResult(parts.Result, state.Result, mode == "final")
        return
    end
    SetText(parts.Subtitle, state.Subtitle)
    SetText(parts.Cards.swat.Count, string.format("%d / %d", state.SwatCount, Slots))
    SetText(parts.Cards.suspect.Count, string.format("%d / %d", state.SuspectCount, Slots))
    FillCard(parts.Cards.swat, "swat", state.Swat, state.HostTeam == "swat")
    FillCard(parts.Cards.suspect, "suspect", state.Suspects, state.HostTeam == "suspect")
    SetLabel(parts.Bots, state.Bots and "БОТЫ SWAT: ВКЛ" or "БОТЫ SWAT: ВЫКЛ")
    SetLabel(parts.Accuracy, "МЕТКОСТЬ: " .. state.Accuracy)
    SetLabel(parts.Minutes, string.format("РАУНД: %d МИН", state.Minutes))
    SetLabel(parts.Rounds, RoundsLabel(state.RoundsToWin))
    SetLabel(parts.Swap, state.Swap and "СМЕНА СТОРОН: ВКЛ" or "СМЕНА СТОРОН: ВЫКЛ")
    SetLabel(parts.Ready, state.Ready and "ЖДЁМ ОСТАЛЬНЫХ" or "ГОТОВ")
end

-- Collapses the page until Reopen (the game's own "Swap teams" button brings it back).
function M.Hide()
    Menu.Hidden = true
    if Valid(Menu.Page) then pcall(function() Show(Menu.Page, false) end) end
end

function M.Reopen()
    Menu.Hidden = false
end

function M.IsHidden()
    return Menu.Hidden
end

M.Colors = Colors
M.Slots = Slots

return M
