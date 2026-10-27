# Ready or Not PvP: SWAT players against suspect players in a co-op mission, with CS2-style rounds.
#
# The mod.io version of HostBrain's hb_pvp.lua (and hb_menu, hb_loadout, hb_hunt), written for kc.lang:
# compiled by pakmod/kc/lang.py into Blueprint classes, never run by Python. The director actor is spawned
# on every map by ModActorSpawnData (docs/modio-pak-research.md); its logic runs on the host only
# (KismetSystemLibrary.IsServer), so only the host needs the pak. A client with the pak only draws its own
# scoreboard on Tab from replicated state.
#
# Differences from the UE4SS version, which patched the game's code natively:
#   * the hidden co-op PvP flag (CoopGS.bCrouchingTigerHiddenDragon) stays off: without the native team
#     rules patch it makes every AI shoot the civilians. Enemies follow the normal rules (SWAT against
#     team 3), dead players may spectate anyone;
#   * suspect players' SWAT actions (arrest, yell, TOC reports) are not filtered: suspects carry no zip
#     cuffs, the rest is up to the players;
#   * mission score popups still show.

SWAT = 2
SUSPECT = 3
# rule sets the host picks in the menu (PvPState.Rules): the AI as the mission built them, or more chances
# for the suspects (rifles for suspect players, the AI squad in a SWAT player's default Kevlar)
RULES_VANILLA = 0
RULES_BALANCED = 1
# EEvidenceActorState::Collected
EVIDENCE_COLLECTED = 1
SQUAD = 5
SLOT = "RoNPvP"
VERSION = "0.4.0-alpha"
COOP_MODE = "BS_COOP"
RESPAWN_DELAY = 10.0
SAFE_DISTANCE = 1000.0
BREAK_SECONDS = 6.0
READY_AFTER = 8.0
HEAR_RANGE = 4000.0
HINT_AFTER = 60.0
HINT_SPREAD = 1500.0
SLOTS = 5
MAX_ROWS = 8
# a co-op mission spawns four AI officers; the fifth is spawned by the mode
MAX_BOTS = 5
# a suspect player who takes over an AI suspect cannot be hurt for a moment
PROTECT_SECONDS = 3.0
STAT_ROWS = 10

# UMG enums
VISIBLE = 0
COLLAPSED = 1
HIDDEN = 2
SELF_HIT_TEST_INVISIBLE = 4
ALIGN_LEFT = 1
ALIGN_CENTER = 2
ALIGN_RIGHT = 3

# W_StandardButton_C.DisplayStyle (StandardButtonStyles, picked on screen)
STYLE_LIGHT = 0
STYLE_RED = 3
STYLE_DARK = 6
STYLE_YELLOW = 8

W_PreMission = "/Game/Blueprints/Widgets/PreMission/W_PreMission.W_PreMission_C"
W_StandardButton = "/Game/Blueprints/Widgets/Common/W_StandardButton.W_StandardButton_C"
W_HumanCharacter_HUD = "/Game/Blueprints/Widgets/HUD/W_HumanCharacter_HUD_V2.W_HumanCharacter_HUD_V2_C"
# the game's scoreboard parts (its PvP modes): the blurred panel, the column titles and fonts, a player's line
W_Scoreboard = "/Game/Blueprints/Widgets/Common/W_Scoreboard.W_Scoreboard_C"
W_ScoreboardFill = "/Game/Blueprints/Widgets/Common/W_ScoreboardFill.W_ScoreboardFill_C"
W_Scoreboard_Line = "/Game/Blueprints/Widgets/Common/W_Scoreboard_Line.W_Scoreboard_Line_C"


@blueprint("/Game/Mods/RoNPvP/BP_PvPSave")
class PvPSave(SaveGame):
    """The host's menu settings between game sessions (SaveGameToSlot "RoNPvP")."""
    Auto: bool
    Bots: bool
    Minutes: int
    RoundsToWin: int
    Swap: bool
    BotAccuracy: float
    Rules: int
    # "ru" or "en"; empty in a save from before 0.4.0: the game's language decides
    Lang: str
    BotSlots: int
    SlotsSaved: bool


@blueprint("/Game/Mods/RoNPvP/BP_PvPLog")
class PvPLog(SaveGame):
    """The mode's log for bug reports: SaveGames/RoNPvPLog.sav (the strings are readable in the file)."""
    Lines: List[str]


@blueprint("/Game/Mods/RoNPvP/BP_PvPState")
class PvPState(Object):
    """The match across mission reloads: a ModPersistentObjectSubsystem object lives the whole game session."""
    Ready: bool
    Auto: bool
    Bots: bool
    Minutes: int
    RoundsToWin: int
    Swap: bool
    BotAccuracy: float
    Rules: int
    Lang: str
    # AI officers the host wants in the SWAT slots (the free slots after the SWAT players cap it)
    BotSlots: int
    Active: bool
    AutoMatch: bool
    Phase: str
    Round: int
    ScoreSwat: int
    ScoreSuspects: int
    Teams: Map[str, int]
    # players' kills and deaths by name: the match, the round being played
    Kills: Map[str, int]
    Deaths: Map[str, int]
    RoundKills: Map[str, int]
    RoundDeaths: Map[str, int]
    HasResult: bool
    ResultRound: int
    ResultSwatWon: bool
    ResultReason: str
    ResultFinal: bool
    ResultSwapped: bool
    ResultSwatScore: int
    ResultSuspectScore: int
    ResultWinners: str
    # the result page's table: name, team, kills, deaths per row; the best player
    ResultNames: List[str]
    ResultTeams: List[int]
    ResultKills: List[int]
    ResultDeaths: List[int]
    ResultMvp: str
    PageMode: str
    TravelAt: float
    Log: List[str]
    LogDirty: bool


@blueprint("/Game/Mods/RoNPvP/BP_PvPDirector")
class PvPDirector(Actor):
    State: PvPState
    Notes: List[str]
    LogSavedAt: float
    Server: bool
    Coop: bool
    AutoArmed: bool
    Russian: bool
    # this mission
    Suspects: Map[str, bool]
    ConvertAi: Map[str, SuspectCharacter]
    ConvertSpot: Map[str, Vector]
    ConvertYaw: Map[str, float]
    ConvertPrimary: Map[str, str]
    ConvertSecondary: Map[str, str]
    DeathAt: Map[str, float]
    DeathWhere: Map[str, Vector]
    DeathTold: Map[str, bool]
    Stripped: List[Actor]
    LockedDoors: List[Door]
    DoorsReady: bool
    PickupBy: Map[BaseMagazineWeapon, ReadyOrNotCharacter]
    PickupPath: Map[BaseMagazineWeapon, str]
    PickupAt: float
    Removed: List[Actor]
    SquadSeen: bool
    HostWait: float
    HostConfirmed: bool
    HoldTold: bool
    BriefedAt: float
    ReadyAsked: Map[str, float]
    LastRosterText: str
    RulesTold: bool
    SquadVariable: int
    MatchBots: bool
    StartedAt: float
    EndsAt: float
    BreakEnds: float
    Warned300: bool
    Warned60: bool
    Bound: List[Object]
    Weapons: Map[str, str]
    Kevlar: ArmourMaterial
    GunPrimary: str
    GunSecondary: str
    Protected: Map[ReadyOrNotCharacter, float]
    # kills: everyone seen standing (with a name for the kill feed), the fallen
    Alive: Map[ReadyOrNotCharacter, str]
    Fallen: List[Actor]
    TrackAt: float
    BotsWanted: int
    SquadSized: bool
    SquadFirstAt: float
    # the local HUD (every machine with the pak): the scoreboard on Tab
    FontsReady: bool
    FontPlain: SlateFontInfo
    FontBold: SlateFontInfo
    Board: W_Scoreboard_C
    BoardTitle: TextBlock
    BoardSwat: VerticalBox
    BoardSuspects: VerticalBox
    BoardShown: bool
    BoardForced: bool
    BoardKey: str
    BoardAt: float
    Banners: List[str]
    BannerAfter: float
    # squad hunt
    HuntTargets: List[Actor]
    HuntContact: Vector
    HuntContactAt: float
    HuntContactSource: str
    HuntContactId: int
    HuntOrderedId: int
    HuntOrdered: Vector
    HuntLastOrder: float
    HuntLastHint: float
    HuntSearching: bool
    HuntShot: Vector
    HuntHasShot: bool
    # menu
    Screen: W_PreMission_C
    Page: Border
    MenuHidden: bool
    Actions: Map[W_StandardButton_C, str]
    Subtitle: TextBlock
    TeamsBox: VerticalBox
    ResultBox: VerticalBox
    SwatHeader: Border
    SwatCount: TextBlock
    SwatRows: List[Border]
    SwatTexts: List[TextBlock]
    SwatStatus: TextBlock
    SwatJoin: W_StandardButton_C
    SwatTitle: TextBlock
    SlotButtons: List[W_StandardButton_C]
    SuspectHeader: Border
    SuspectCount: TextBlock
    SuspectRows: List[Border]
    SuspectTexts: List[TextBlock]
    SuspectStatus: TextBlock
    SuspectJoin: W_StandardButton_C
    SuspectTitle: TextBlock
    AccuracyButton: W_StandardButton_C
    MinutesButton: W_StandardButton_C
    RoundsButton: W_StandardButton_C
    SwapButton: W_StandardButton_C
    RulesButton: W_StandardButton_C
    LangButton: W_StandardButton_C
    ReadyButton: W_StandardButton_C
    ResTop: TextBlock
    ResWinner: TextBlock
    ResReason: TextBlock
    ResSwatBox: Border
    ResSwatNumber: TextBlock
    ResSuspectBox: Border
    ResSuspectNumber: TextBlock
    ResNotice: TextBlock
    ResCountdown: TextBlock
    ResMvp: TextBlock
    StatRows: List[Widget]
    StatNames: List[TextBlock]
    StatKills: List[TextBlock]
    StatDeaths: List[TextBlock]
    RoundButtons: List[Widget]
    NewMatchButton: Widget
    RowTexts: List[str]
    RowColors: List[LinearColor]

    # ================================================================ lifecycle

    def ReceiveBeginPlay(self):
        self.Server = IsServer(self)
        # every machine with the pak draws its own scoreboard from replicated state; a client takes its own
        # game's language, the rest of the mode runs on the host
        K2_SetTimer(self, "HudTick", 0.1, True, 0.0, 0.0)
        if not self.Server:
            self.Russian = StartsWith(KismetInternationalizationLibrary.GetCurrentLanguage(), "ru", 1)
            return
        self.SquadVariable = -1
        self.HostWait = -1.0
        self.BriefedAt = -1.0
        self.Weapons = {
            "Primary_AKM": "Primary_SLR47", "Primary_S_AK103": "Primary_SLR47", "Primary_AK104": "Primary_SLR47",
            "Primary_AKS74U": "Primary_SLR47", "Primary_QBZ": "Primary_SLR47", "Primary_CAR": "Primary_SBR",
            "Primary_Calico": "Primary_MP5A2", "Primary_UZI": "Primary_MP9", "Primary_M249": "Primary_FAL",
            "Primary_RPD": "Primary_FAL", "Primary_S_G3A3": "Primary_FAL", "Primary_S_MK18_VAR1": "Primary_MK18",
            "Primary_S_MK18_VAR2": "Primary_MK18", "Primary_S_MK18_VAR3_CMAG": "Primary_MK18",
            "Primary_M37": "Primary_870mcs", "Primary_S_870mcs": "Primary_870mcs", "Primary_SawnOff": "Primary_870mcs",
            "Primary_Trenchgun": "Primary_870mcs", "Secondary_Makarov": "Secondary_M92FS_V2",
            "Secondary_Makarov_2Handed": "Secondary_M92FS_V2", "Secondary_S_G18": "Secondary_G19_V2",
            "Secondary_S_G19": "Secondary_G19_V2", "Secondary_S_M1911": "Secondary_M1911_V2",
            "Secondary_S_Python": "Secondary_Python_V2", "Secondary_Tec9": "Secondary_P99",
            "Secondary_Flaregun": "Secondary_M1911_V2",
        }
        self.LoadState()
        self.Russian = self.State.Lang == "ru"
        self.State.Log.append("---- " + VERSION + " — " + GetCurrentLevelName(True))
        # 10 players (5v5) in lobbies created from now on; the game's default is 5
        if EOSMultiplayerStatics.GetMaxPlayers() < 10:
            EOSMultiplayerStatics.SetMaxPlayers(10)
        self.Coop = isinstance(GetGameMode(), CoopGM)
        st = self.State
        # a director lives in one world: a new world is the next round's mission (a travel), or the
        # mission was left
        if st.Active:
            if st.Phase == "travel" or st.Phase == "briefing":
                if self.Coop:
                    st.Phase = "briefing"
                    self.ResetMission()
                    self.Log("next mission: briefing")
            else:
                self.Log("mission left: mode stopped")
                self.StopMode()
        mode = GetGameMode()
        if isinstance(mode, ReadyOrNotGameMode):
            cast(mode, ReadyOrNotGameMode).bSpectateKillerOnDeath = False
        K2_SetTimer(self, "SlowTick", 1.0, True, 0.0, 0.0)
        K2_SetTimer(self, "FastTick", 0.05, True, 0.0, 0.0)
        K2_SetTimer(self, "FireTick", 0.5, True, 0.0, 0.0)
        self.Log("director " + VERSION + " in " + GetCurrentLevelName(True))

    def LoadState(self):
        st = cast(ModPersistentObjectSubsystem.GetPersistentObject(PvPState), PvPState)
        if not st:
            st = cast(ModPersistentObjectSubsystem.CreatePersistentObject(PvPState), PvPState)
        self.State = st
        if st.Ready:
            return
        st.Ready = True
        st.Auto = True
        st.Bots = True
        st.Minutes = 10
        st.RoundsToWin = 3
        st.Swap = True
        st.BotAccuracy = 2.0
        st.BotSlots = MAX_BOTS
        st.Phase = "idle"
        st.PageMode = "teams"
        st.Round = 1
        if DoesSaveGameExist(SLOT, 0):
            save = cast(LoadGameFromSlot(SLOT, 0), PvPSave)
            if save:
                st.Auto = save.Auto
                st.Bots = save.Bots
                st.Minutes = save.Minutes
                st.RoundsToWin = save.RoundsToWin
                st.Swap = save.Swap
                st.BotAccuracy = save.BotAccuracy
                st.Rules = save.Rules
                st.Lang = save.Lang
                if save.SlotsSaved:
                    st.BotSlots = save.BotSlots
                elif not save.Bots:
                    st.BotSlots = 0
        if st.Lang != "ru" and st.Lang != "en":
            st.Lang = "ru" if StartsWith(KismetInternationalizationLibrary.GetCurrentLanguage(), "ru", 1) else "en"
        if st.BotSlots < 0 or st.BotSlots > MAX_BOTS:
            st.BotSlots = MAX_BOTS
        if st.Minutes < 1:
            st.Minutes = 10
        if st.RoundsToWin < 1:
            st.RoundsToWin = 3
        if st.BotAccuracy < 0.5:
            st.BotAccuracy = 2.0

    def SaveSettings(self):
        save = cast(CreateSaveGameObject(PvPSave), PvPSave)
        st = self.State
        save.Auto = st.Auto
        save.Bots = st.BotSlots > 0
        save.Minutes = st.Minutes
        save.RoundsToWin = st.RoundsToWin
        save.Swap = st.Swap
        save.BotAccuracy = st.BotAccuracy
        save.Rules = st.Rules
        save.Lang = st.Lang
        save.BotSlots = st.BotSlots
        save.SlotsSaved = True
        SaveGameToSlot(save, SLOT, 0)

    def Log(self, text: str):
        """The mode's log: this world's Notes, and the session's log kept in the persistent state and saved
        to SaveGames/RoNPvPLog.sav for bug reports."""
        line = f"{GetTimeSeconds():.1f} {text}"
        if len(self.Notes) > 300:
            self.Notes.remove_at(0)
        self.Notes.append(line)
        st = self.State
        if st:
            if len(st.Log) > 800:
                st.Log.remove_at(0)
            st.Log.append(line)
            st.LogDirty = True

    def SaveLog(self):
        st = self.State
        save = cast(CreateSaveGameObject(PvPLog), PvPLog)
        save.Lines = st.Log
        SaveGameToSlot(save, "RoNPvPLog", 0)
        st.LogDirty = False

    def Now(self) -> float:
        return GetTimeSeconds()

    # ================================================================ players and messages

    def Players(self) -> List[ReadyOrNotPlayerController]:
        result: List[ReadyOrNotPlayerController] = []
        for actor in GetAllActorsOfClass(ReadyOrNotPlayerController):
            pc = cast(actor, ReadyOrNotPlayerController)
            if pc and IsValid(pc.PlayerState):
                result.append(pc)
        return result

    def NameOf(self, pc: ReadyOrNotPlayerController) -> str:
        return pc.PlayerState.GetPlayerName()

    def StateOf(self, pc: ReadyOrNotPlayerController) -> ReadyOrNotPlayerState:
        return cast(pc.PlayerState, ReadyOrNotPlayerState)

    def IsDown(self, character: ReadyOrNotCharacter) -> bool:
        if not character:
            return True
        return character.IsDeadOrUnconscious() or character.IsIncapacitated() or character.IsArrested() or character.IsSurrendered()

    def PawnOf(self, pc: ReadyOrNotPlayerController) -> ReadyOrNotCharacter:
        pawn = cast(pc.K2_GetPawn(), ReadyOrNotCharacter)
        if self.IsDown(pawn):
            return None
        return pawn

    def HostPC(self) -> ReadyOrNotPlayerController:
        return cast(GetPlayerController(0), ReadyOrNotPlayerController)

    def IsHost(self, pc: ReadyOrNotPlayerController) -> bool:
        return pc == self.HostPC()

    def TeamOf(self, pc: ReadyOrNotPlayerController) -> int:
        """The side a player is on for the next mission start (chosen, or played in this mission)."""
        name = self.NameOf(pc)
        if name in self.State.Teams:
            return self.State.Teams[name]
        if name in self.Suspects:
            return SUSPECT
        return SWAT

    def IsSuspect(self, pc: ReadyOrNotPlayerController) -> bool:
        return self.NameOf(pc) in self.Suspects

    def TeamName(self, team: int) -> str:
        if team == SUSPECT:
            return self.L("подозреваемые", "suspects")
        return "SWAT"

    def L(self, ru: str, en: str) -> str:
        """A text in the mode's language: the host's choice in the menu (at first the game's language); on a
        client the client's own game language."""
        if self.Russian:
            return ru
        return en

    def Chat(self, text: str, killfeed: bool) -> RChatMessage:
        return RChatMessage(SenderName="PvP", Message=text, Color=LinearColor(R=1.0, G=0.75, B=0.2, A=1.0), bKillfeed=killfeed)

    # The game shows chat in a mission as the green lines at the bottom right, so the mode keeps chat for what a
    # player needs to read there: the kill feed, the team choice on the pre-mission screen, and the round events
    # for clients (they may not have the pak, so chat is all they get). The host gets the round events as the
    # game's own objective popups and the rest in the menu and on the scoreboard.

    def Say(self, text: str):
        """A line in everyone's chat (the team choice in the pre-mission screen's chat)."""
        gs = cast(GetGameState(), ReadyOrNotGameState)
        if gs:
            gs.Multicast_BroadcastChatMessage(self.Chat(text, False))
        self.Log(text)

    def Remote(self, text: str):
        """A line in the chat of every player but the host."""
        for pc in self.Players():
            if not self.IsHost(pc):
                pc.Client_SendChatMessage(self.Chat(text, False))
        self.Log(text)

    def Announce(self, text: str):
        """A round event: the host's objective popup, the clients' chat."""
        self.Banner(text)
        self.Remote(text)

    def Notify(self, pc: ReadyOrNotPlayerController, text: str):
        """One player's event: an objective popup for the host, a chat line for a client."""
        if self.IsHost(pc):
            self.Banner(text)
        else:
            pc.Client_SendChatMessage(self.Chat(text, False))
        self.Log("to " + self.NameOf(pc) + ": " + text)

    def Tell(self, pc: ReadyOrNotPlayerController, text: str):
        """A chat answer to one player (chat commands)."""
        pc.Client_SendChatMessage(self.Chat(text, False))
        self.Log("to " + self.NameOf(pc) + ": " + text)

    def Feed(self, text: str):
        """A kill feed line in everyone's chat, marked as the game marks its own kill feed."""
        gs = cast(GetGameState(), ReadyOrNotGameState)
        if gs:
            gs.Multicast_BroadcastChatMessage(self.Chat(text, True))
        self.Log("feed: " + text)

    def Hud(self) -> W_HumanCharacter_HUD_V2_C:
        for widget in GetAllWidgetsOfClass(W_HumanCharacter_HUD_V2_C, False):
            if widget.IsInViewport():
                return cast(widget, W_HumanCharacter_HUD_V2_C)
        return None

    def Banner(self, text: str):
        """The game's objective popup at the bottom centre of the host's HUD (popups stack and fade). Until the
        HUD is up and the mission has faded in, popups wait (HudTick shows them)."""
        hud = self.Hud()
        if hud and self.Now() >= self.BannerAfter:
            popup: Text = Text(ToUpper(text))
            hud.AddObjectivePopup(popup)
        else:
            self.Banners.append(text)

    def ShowBanners(self):
        if len(self.Banners) == 0 or self.Now() < self.BannerAfter:
            return
        hud = self.Hud()
        if not hud:
            return
        for text in self.Banners:
            popup: Text = Text(ToUpper(text))
            hud.AddObjectivePopup(popup)
        self.Banners.clear()

    def HideSquadHud(self):
        hud = self.Hud()
        if hud:
            if IsValid(hud.SWATTeamStatus_V2) and hud.SWATTeamStatus_V2.GetVisibility() != COLLAPSED:
                hud.SWATTeamStatus_V2.SetVisibility(COLLAPSED)
            if IsValid(hud.SWATTeamStatus_V2_Gamepad) and hud.SWATTeamStatus_V2_Gamepad.GetVisibility() != COLLAPSED:
                hud.SWATTeamStatus_V2_Gamepad.SetVisibility(COLLAPSED)

    def Roster(self, players: List[ReadyOrNotPlayerController]) -> str:
        swat = ""
        suspects = ""
        for pc in players:
            if self.TeamOf(pc) == SUSPECT:
                suspects = suspects + ("" if suspects == "" else ", ") + self.NameOf(pc)
            else:
                swat = swat + ("" if swat == "" else ", ") + self.NameOf(pc)
        nobody = self.L("никого", "nobody")
        return "SWAT: " + (nobody if swat == "" else swat) + self.L("; подозреваемые: ", "; suspects: ") + (nobody if suspects == "" else suspects)

    def ScoreLine(self) -> str:
        return f"SWAT {self.State.ScoreSwat} : {self.State.ScoreSuspects} " + self.L("Подозреваемые", "Suspects")

    # ================================================================ the game's switches

    def SetSquadVariable(self, on: bool):
        """The game spawns the co-op AI squad only in single player unless a.RonSpawnSwatInIncompatibleMode
        is 1 (not a cheat variable); it goes off again once the mission has started."""
        value = 1 if on else 0
        if self.SquadVariable == value:
            return
        self.SquadVariable = value
        ExecuteConsoleCommand("a.RonSpawnSwatInIncompatibleMode " + str(value), None)

    def ResetMission(self):
        self.Suspects.clear()
        self.ConvertAi.clear()
        self.Stripped.clear()
        self.Removed.clear()
        self.SquadSeen = False
        self.HostWait = -1.0
        self.HostConfirmed = False
        self.HoldTold = False
        self.BriefedAt = -1.0
        self.ReadyAsked.clear()
        self.LastRosterText = ""
        self.RulesTold = False
        self.MenuHidden = False
        self.Protected.clear()
        self.Alive.clear()
        self.Fallen.clear()
        self.SquadSized = False
        self.SquadFirstAt = 0.0

    def NewMatch(self):
        st = self.State
        st.Round = 1
        st.ScoreSwat = 0
        st.ScoreSuspects = 0
        st.HasResult = False
        st.PageMode = "teams"
        st.Kills.clear()
        st.Deaths.clear()
        st.RoundKills.clear()
        st.RoundDeaths.clear()

    def StopMode(self):
        self.State.Active = False
        self.State.Phase = "idle"
        self.NewMatch()

    def SetTeam(self, pc: ReadyOrNotPlayerController, team: int):
        """In a running mission the team is written directly (Server_SetTeamType only works on the
        pre-mission screen)."""
        state = self.StateOf(pc)
        if state.Team == team:
            return
        state.Team = team
        state.OnRep_Team()

    # ================================================================ taking over AI suspects

    def LivingAiSuspects(self) -> List[SuspectCharacter]:
        result: List[SuspectCharacter] = []
        for actor in GetAllActorsOfClass(SuspectCharacter):
            ai = cast(actor, SuspectCharacter)
            if ai and not self.IsDown(ai) and not (actor in self.Removed):
                result.append(ai)
        return result

    def LivingSwat(self) -> List[ReadyOrNotCharacter]:
        result: List[ReadyOrNotCharacter] = []
        manager = self.SquadManager()
        if not manager:
            return result
        for ai in manager.SwatAI:
            if not self.IsDown(ai):
                result.append(ai)
        return result

    def SquadManager(self) -> SWATManager:
        return cast(GetWorldSubsystem(self, SWATManager), SWATManager)

    def RemoveAi(self, ai: SuspectCharacter):
        self.Removed.append(ai)
        ai.K2_DestroyActor()

    def SwatBodies(self, players: List[ReadyOrNotPlayerController]) -> List[ReadyOrNotCharacter]:
        bodies: List[ReadyOrNotCharacter] = []
        for pc in players:
            pawn = self.PawnOf(pc)
            if not self.IsSuspect(pc) and pawn:
                bodies.append(pawn)
        for ai in self.LivingSwat():
            bodies.append(ai)
        return bodies

    def Reserved(self, ai: SuspectCharacter) -> bool:
        for name in self.ConvertAi:
            if self.ConvertAi[name] == ai:
                return True
        return False

    def Blocked(self, start: Vector, end: Vector, ignore: List[Actor]) -> bool:
        hit, _ = LineTraceSingle(start, end, 0, False, ignore, 0, True, LinearColor(R=0.0, G=0.0, B=0.0, A=0.0),
                                 LinearColor(R=0.0, G=0.0, B=0.0, A=0.0), 0.0)
        return hit

    def ChooseAi(self, players: List[ReadyOrNotPlayerController], near: Vector, has_near: bool) -> SuspectCharacter:
        """An AI suspect to take over: no SWAT within SAFE_DISTANCE and none with a line of sight to it,
        nearest to where the player fell. Without such a one the line of sight is dropped; an AI right next
        to SWAT is never taken, nor one another player is about to take."""
        swat = self.SwatBodies(players)
        best: SuspectCharacter = None
        fallback: SuspectCharacter = None
        best_score = 1.0e12
        fallback_score = 1.0e12
        for ai in self.LivingAiSuspects():
            if self.Reserved(ai):
                continue
            at = ai.K2_GetActorLocation()
            safe = True
            hidden = True
            for body in swat:
                start = body.K2_GetActorLocation()
                if Vector_Distance(at, start) < SAFE_DISTANCE:
                    safe = False
                    break
                if hidden:
                    ignore: List[Actor] = [body, ai]
                    if not self.Blocked(Vector(X=start.X, Y=start.Y, Z=start.Z + 60.0), Vector(X=at.X, Y=at.Y, Z=at.Z + 60.0), ignore):
                        hidden = False
            if safe:
                score = RandomFloat() * 1000000.0
                if has_near:
                    score = Vector_Distance(at, near)
                if hidden and score < best_score:
                    best = ai
                    best_score = score
                if score < fallback_score:
                    fallback = ai
                    fallback_score = score
        if best:
            return best
        return fallback

    def Book(self, pc: ReadyOrNotPlayerController, ai: SuspectCharacter) -> str:
        """Books an AI suspect for the player's next pawn and gives that spawn the suspect kit (the game
        spawns a player with PlayerState.ServerSavedLoadout)."""
        self.GunsFor(ai)
        name = self.NameOf(pc)
        self.ConvertAi[name] = ai
        self.ConvertSpot[name] = ai.K2_GetActorLocation()
        self.ConvertYaw[name] = ai.K2_GetActorRotation().Yaw
        self.ConvertPrimary[name] = self.GunPrimary
        self.ConvertSecondary[name] = self.GunSecondary
        self.PrepareSuspectSpawn(self.StateOf(pc), self.GunPrimary, self.GunSecondary)
        return self.GunsTitle(self.GunPrimary, self.GunSecondary)

    def PlaceAt(self, pawn: ReadyOrNotCharacter, spot: Vector, yaw: float):
        if not pawn.K2_TeleportTo(Vector(X=spot.X, Y=spot.Y, Z=spot.Z + 10.0), Rotator(Pitch=0.0, Yaw=yaw, Roll=0.0)):
            self.PlaceNextToSuspect(pawn)

    def PlaceNextToSuspect(self, pawn: ReadyOrNotCharacter) -> bool:
        """Spots around a living AI suspect (8 directions, 1.5 to 3 m) that it can see and that have a floor;
        K2_TeleportTo refuses spots where the capsule would be stuck."""
        for ai in self.LivingAiSuspects():
            at = ai.K2_GetActorLocation()
            yaw = ai.K2_GetActorRotation().Yaw
            for distance in [150.0, 220.0, 300.0]:
                for step in range(8):
                    angle = yaw + step * 45.0
                    spot = Vector(X=at.X + DegCos(angle) * distance, Y=at.Y + DegSin(angle) * distance, Z=at.Z + 10.0)
                    ignore: List[Actor] = [ai, pawn]
                    visible = not self.Blocked(Vector(X=at.X, Y=at.Y, Z=at.Z + 60.0), Vector(X=spot.X, Y=spot.Y, Z=spot.Z + 60.0), ignore)
                    floor = self.Blocked(spot, Vector(X=spot.X, Y=spot.Y, Z=spot.Z - 250.0), ignore)
                    if visible and floor and pawn.K2_TeleportTo(spot, Rotator(Pitch=0.0, Yaw=yaw, Roll=0.0)):
                        return True
        return False

    def Convert(self, pc: ReadyOrNotPlayerController):
        """The player's new pawn takes the booked AI's place: the AI leaves, the pawn turns suspect and
        loses the SWAT gear."""
        name = self.NameOf(pc)
        pawn = self.PawnOf(pc)
        ai = self.ConvertAi[name]
        spot = self.ConvertSpot[name]
        yaw = self.ConvertYaw[name]
        primary = self.ConvertPrimary[name]
        secondary = self.ConvertSecondary[name]
        self.ConvertAi.remove(name)
        if ai and not self.IsDown(ai):
            spot = ai.K2_GetActorLocation()
            yaw = ai.K2_GetActorRotation().Yaw
            self.RemoveAi(ai)
        self.PlaceAt(pawn, spot, yaw)
        self.SetTeam(pc, SUSPECT)
        pawn.DefaultTeam = SUSPECT
        self.EquipSuspectKit(pawn, primary, secondary)
        self.ApplySuspectOutfit(self.StateOf(pc))
        stripped = self.StripSwatGear(pawn)
        self.FillMagazines(pawn)
        self.Stripped.append(pawn)
        self.Suspects[name] = True
        self.DeathAt.remove(name)
        self.Protect(pawn)
        self.Log(f"{name} took an AI suspect's place ({stripped} SWAT items removed)")
        self.Notify(pc, self.SuspectLine(self.GunsTitle(primary, secondary)))

    def SuspectLine(self, guns: str) -> str:
        left = len(self.LivingAiSuspects())
        return self.L(f"Вы — подозреваемый — {guns} — ИИ-подозреваемых в запасе: {left}",
                      f"You are a suspect — {guns} — AI suspects left: {left}")

    def Protect(self, pawn: ReadyOrNotCharacter):
        """A player who has just taken an AI suspect's place cannot be hurt for PROTECT_SECONDS (the game's
        ReadyOrNotCharacter.bGodMode, which ShouldTakeDamage checks on the server)."""
        pawn.bGodMode = True
        self.Protected[pawn] = self.Now() + PROTECT_SECONDS

    def ProtectTick(self, now: float):
        done: List[ReadyOrNotCharacter] = []
        for pawn in self.Protected:
            if not IsValid(pawn) or now >= self.Protected[pawn]:
                done.append(pawn)
        for pawn in done:
            if IsValid(pawn):
                pawn.bGodMode = False
            self.Protected.remove(pawn)

    def TakeOver(self, pc: ReadyOrNotPlayerController, ai: SuspectCharacter) -> bool:
        """After a suspect player's death the player's new character is spawned right on the AI suspect's
        spot (ReadyOrNotGameMode.SpawnPlayerCharacter possesses it and takes the team and the prepared
        ServerSavedLoadout)."""
        mode = cast(GetGameMode(), ReadyOrNotGameMode)
        weapons = self.Book(pc, ai)
        name = self.NameOf(pc)
        self.ConvertAi.remove(name)
        spot = ai.K2_GetActorLocation()
        yaw = ai.K2_GetActorRotation().Yaw
        self.RemoveAi(ai)
        self.SetTeam(pc, SUSPECT)
        transform = MakeTransform(Vector(X=spot.X, Y=spot.Y, Z=spot.Z + 10.0), Rotator(Pitch=0.0, Yaw=yaw, Roll=0.0),
                                  Vector(X=1.0, Y=1.0, Z=1.0))
        pawn = cast(mode.SpawnPlayerCharacter(pc, mode.DefaultPawnClass, transform, True), ReadyOrNotCharacter)
        if not pawn or not self.PawnOf(pc):
            self.Log("takeover failed for " + name)
            return False
        spectator = pc.DeadSpectatorPawn
        if IsValid(spectator) and spectator != pawn:
            spectator.K2_DestroyActor()
        pawn.DefaultTeam = SUSPECT
        self.EquipSuspectKit(pawn, self.GunPrimary, self.GunSecondary)
        self.ApplySuspectOutfit(self.StateOf(pc))
        stripped = self.StripSwatGear(pawn)
        self.FillMagazines(pawn)
        self.Stripped.append(pawn)
        self.DeathAt.remove(name)
        self.Protect(pawn)
        if self.IsHost(pc):
            # the new character fades in: its popup waits
            self.BannerAfter = self.Now() + 2.0
        self.Log(f"{name} took over an AI suspect ({weapons}, {stripped} SWAT items removed)")
        self.Notify(pc, self.SuspectLine(weapons))
        return True

    def OnPawnChanged(self, OldPawn: Pawn, NewPawn: Pawn):
        """A player's new pawn takes its booked AI suspect's place in the frame it is possessed."""
        if not NewPawn or not self.State.Active:
            return
        pc = cast(NewPawn.Controller, ReadyOrNotPlayerController)
        if pc:
            self.TryConvert(pc)

    def TryConvert(self, pc: ReadyOrNotPlayerController):
        name = self.NameOf(pc)
        if not (name in self.ConvertAi):
            return
        pawn = self.PawnOf(pc)
        if not pawn or pawn in self.Stripped or self.HostWaitsForSquad(pc):
            return
        self.Convert(pc)

    def HostWaitsForSquad(self, pc: ReadyOrNotPlayerController) -> bool:
        """The mission start spawns the AI squad around the host's pawn, so with bots a suspect host stays
        at the van until the squad is there (at most 5 s)."""
        if self.BotsWanted == 0 or self.SquadSeen or not self.IsHost(pc):
            return False
        if len(self.LivingSwat()) > 0:
            self.SquadSeen = True
            return False
        now = self.Now()
        if self.HostWait < 0.0:
            self.HostWait = now
        return now - self.HostWait < 5.0

    # ================================================================ suspect equipment

    def PlayerWeapon(self, name: str) -> Class[BaseItem]:
        path = "/Game/Blueprints/Items/WeaponsRevised/" + name + "." + name + "_C"
        soft = MakeSoftClassPath(path)
        return LoadClassAsset_Blocking(Conv_SoftClassPathToSoftClassRef(soft))

    def LoadClassPath(self, path: str) -> Class[BaseItem]:
        soft = MakeSoftClassPath(path)
        return LoadClassAsset_Blocking(Conv_SoftClassPathToSoftClassRef(soft))

    def WeaponTitle(self, name: str) -> str:
        found, left, right = Split(name, "_", 1, 0)
        title = name
        if found:
            title = right
        # AI suspects' guns: Primary_S_AK103
        if StartsWith(title, "S_", 0):
            title = RightChop(title, 2)
        if EndsWith(title, "_V2", 1):
            title = LeftChop(title, 3)
        return title

    def RandomPrimary(self) -> str:
        """Balanced rules: suspect players get rifles with full metal jacket rounds (penetration 4)."""
        names: List[str] = ["Primary_SLR47", "Primary_FAL"]
        return names[RandomIntegerInRange(0, 1)]

    def Rifle(self, name: str) -> str:
        """Balanced rules: pistol-calibre SMGs and buckshot (penetration 0-2) do not get through even a SWAT
        player's default Kevlar (armour level 3), so they become the SLR-47 and the FAL."""
        if name == "Primary_MP5A2" or name == "Primary_MP9":
            return "Primary_SLR47"
        if name == "Primary_870mcs":
            return "Primary_FAL"
        return name

    def RandomSecondary(self) -> str:
        names: List[str] = ["Secondary_M1911_V2", "Secondary_M92FS_V2", "Secondary_G19_V2", "Secondary_Python_V2", "Secondary_P99"]
        return names[RandomIntegerInRange(0, 4)]

    def ClassName(self, item: Object) -> str:
        name = GetObjectName(GetObjectClass(item))
        if EndsWith(name, "_C", 0):
            name = LeftChop(name, 2)
        return name

    def GunsFor(self, ai: ReadyOrNotCharacter):
        """Player guns of the same kind as the AI suspect's (GunPrimary, GunSecondary). AKs become the SLR-47
        and the G3 and machine guns the FAL (their handling throws the sights about when a player aims while
        stepping sideways). Vanilla rules keep the AI's kit as it is (an AI with a pistol only gives a pistol
        only); balanced rules turn SMGs and shotguns into rifles and fill a missing slot at random."""
        self.GunPrimary = ""
        self.GunSecondary = ""
        for item in ai.InventoryComp.InventoryItems:
            if not item:
                continue
            name = self.ClassName(item)
            if name in self.Weapons:
                if StartsWith(name, "Primary_", 0) and self.GunPrimary == "":
                    self.GunPrimary = self.Weapons[name]
                if StartsWith(name, "Secondary_", 0) and self.GunSecondary == "":
                    self.GunSecondary = self.Weapons[name]
        if self.State.Rules == RULES_BALANCED:
            if self.GunPrimary == "":
                self.GunPrimary = self.RandomPrimary()
            self.GunPrimary = self.Rifle(self.GunPrimary)
            if self.GunSecondary == "":
                self.GunSecondary = self.RandomSecondary()
        elif self.GunPrimary == "" and self.GunSecondary == "":
            self.GunSecondary = self.RandomSecondary()

    def WeaponPath(self, name: str) -> str:
        if name == "":
            return ""
        return "/Game/Blueprints/Items/WeaponsRevised/" + name + "." + name + "_C"

    def GunsTitle(self, primary: str, secondary: str) -> str:
        if primary == "":
            return self.WeaponTitle(secondary)
        if secondary == "":
            return self.WeaponTitle(primary)
        return self.WeaponTitle(primary) + " + " + self.WeaponTitle(secondary)

    def SuspectLoadout(self, primary: str, secondary: str) -> SavedLoadout:
        return self.KitLoadout(self.WeaponPath(primary), self.WeaponPath(secondary))

    def KitLoadout(self, primary_path: str, secondary_path: str) -> SavedLoadout:
        """The suspect kit: the guns (class paths, "" for an empty slot), no armour, no helmet, no grenades."""
        loadout = SavedLoadout(PrimaryAmmoSlotsCount=-1, SecondaryAmmoSlotsCount=-1, GrenadeSlotsCount=0, TacticalSlotsCount=0)
        if primary_path != "":
            loadout.Primary = self.LoadClassPath(primary_path)
        if secondary_path != "":
            loadout.Secondary = self.LoadClassPath(secondary_path)
        loadout.Armor = self.LoadClassPath("/Game/Blueprints/Items/ArmorRevised/Armor_NoArmor.Armor_NoArmor_C")
        loadout.Helmet = self.LoadClassPath("/Game/Blueprints/Items/ArmorRevised/Helmet_None.Helmet_None_C")
        return loadout

    def PrepareSuspectSpawn(self, state: ReadyOrNotPlayerState, primary: str, secondary: str):
        """The next spawn of this player gets the suspect kit and the game's suspect clothes
        (CoopGM.SuspectPlayerCustomizationOverride) through ServerSavedLoadout."""
        loadout = self.SuspectLoadout(primary, secondary)
        mode = cast(GetGameMode(), CoopGM)
        if mode:
            loadout.SavedCustomization = mode.SuspectPlayerCustomizationOverride
            loadout.bHasCustomization = True
        state.ServerSavedLoadout = loadout

    def EquipSuspectKit(self, pawn: ReadyOrNotCharacter, primary: str, secondary: str) -> bool:
        """The mission-start spawn does not take ServerSavedLoadout, so the kit is equipped directly
        (the "none" armour and helmet replace the SWAT ones)."""
        return self.EquipKit(pawn, self.SuspectLoadout(primary, secondary), primary != "")

    def EquipKit(self, pawn: ReadyOrNotCharacter, loadout: SavedLoadout, primary_in_hands: bool) -> bool:
        # EquipItemCategory: IC_Primary 1, IC_Secondary 2 (a pistol-only kit draws the pistol)
        options = LoadoutEquipOptions(EquipItemCategory=1 if primary_in_hands else 2, bReplicates=True, bSanitizeLoadout=False)
        return EquipLoadoutOnPlayer(loadout, pawn, options)

    def ApplySuspectOutfit(self, state: ReadyOrNotPlayerState):
        """The game's suspect clothes through the replicated PlayerState.Customization; bForceLiveUpdate
        re-dresses the living character. The player's saved customization is not touched."""
        mode = cast(GetGameMode(), CoopGM)
        if mode:
            state.Server_SetCustomization(mode.SuspectPlayerCustomizationOverride, True)

    def StripSwatGear(self, pawn: ReadyOrNotCharacter) -> int:
        """Grenades, devices (zip cuffs, multitool, C2, tablet, detonator, chem lights), the mirror gun,
        launchers and facewear leave a suspect's inventory."""
        doomed: List[BaseItem] = []
        for item in pawn.InventoryComp.InventoryItems:
            if not item:
                continue
            name = self.ClassName(item)
            if StartsWith(name, "Grenade_", 0) or StartsWith(name, "Device_", 0) or StartsWith(name, "DevicesDetonator", 0) \
                    or StartsWith(name, "Mirrorgun", 0) or StartsWith(name, "BP_Facewear", 0) \
                    or StartsWith(name, "Launcher_", 0) or StartsWith(name, "Optiwand", 0):
                doomed.append(item)
        for item in doomed:
            pawn.InventoryComp.DestroyInventoryItem(item)
        return len(doomed)

    def FillMagazines(self, pawn: ReadyOrNotCharacter):
        for item in pawn.InventoryComp.InventoryItems:
            weapon = cast(item, BaseMagazineWeapon)
            if weapon:
                if weapon.GetMagazineCount() == 0 or not weapon.HasAnyAmmo():
                    weapon.ReplenishAmmo()

    # ================================================================ doors and dropped guns

    def DoorsTick(self):
        """Suspects open any door: Door.bSuspectAlwaysUnlocks lets team 3 through a locked door (the game's own
        rule in CanOpenDoor and in the opening itself), SWAT still find it locked. Opening unlocks a door, so a
        door locked at the round start locks again once it is closed and a suspect used it last (a SWAT
        lockpick or breach stays). bSuspectKnowsLockState stays off, so a client's own check lets a suspect
        player try the door."""
        if not self.DoorsReady:
            self.DoorsReady = True
            for actor in GetAllActorsOfClass(Door):
                door = cast(actor, Door)
                if door:
                    door.bSuspectAlwaysUnlocks = True
                    door.bSuspectKnowsLockState = False
                    if door.IsLocked():
                        self.LockedDoors.append(door)
            self.Log(f"doors: suspects open all of them, {len(self.LockedDoors)} locked")
        for door in self.LockedDoors:
            if door.IsLocked() or door.bDoorBroken or not door.IsClosed():
                continue
            user = door.GetLastDoorUser()
            if user and user.DefaultTeam == SUSPECT:
                door.SetLocked(True)
                door.bSuspectKnowsLockState = False

    def PickupTarget(self, gun: BaseMagazineWeapon) -> str:
        """The class path a suspect player gets for a dropped gun: a player gun as it is, an AI suspect's gun as
        its player version (balanced rules: a rifle for an SMG or a shotgun); "" for anything else."""
        name = self.ClassName(gun)
        path = GetPathName(GetObjectClass(gun))
        if Contains(path, "/WeaponsRevised/", False, False):
            if StartsWith(name, "Primary_", 0) or StartsWith(name, "Secondary_", 0):
                return path
            return ""
        if name in self.Weapons:
            target = self.Weapons[name]
            if self.State.Rules == RULES_BALANCED:
                target = self.Rifle(target)
            return self.WeaponPath(target)
        return ""

    def PickupTick(self, now: float):
        """A suspect player who collects a dropped gun as evidence (holds the use key on it) gets the gun
        instead. The collector is noted while the evidence is being collected (EvidenceComponent.
        CollectingCharacter, known on the server); the gun is handed over once the collection is done."""
        if now < self.PickupAt:
            return
        self.PickupAt = now + 0.2
        for actor in GetAllActorsOfClass(BaseMagazineWeapon):
            gun = cast(actor, BaseMagazineWeapon)
            if not gun or not gun.EvidenceComponent:
                continue
            evidence = gun.EvidenceComponent
            if evidence.bIsBeingCollected:
                collector = evidence.CollectingCharacter
                if collector and not (gun in self.PickupBy) and collector.DefaultTeam == SUSPECT \
                        and cast(collector.Controller, ReadyOrNotPlayerController):
                    path = self.PickupTarget(gun)
                    if path != "":
                        self.PickupBy[gun] = collector
                        self.PickupPath[gun] = path
            elif gun in self.PickupBy and evidence.GetEvidenceState() != EVIDENCE_COLLECTED:
                # the collection was broken off
                self.PickupBy.remove(gun)
                self.PickupPath.remove(gun)
        done: List[BaseMagazineWeapon] = []
        for gun in self.PickupBy:
            if not IsValid(gun) or gun.EvidenceComponent.GetEvidenceState() == EVIDENCE_COLLECTED:
                done.append(gun)
        for gun in done:
            pawn = self.PickupBy[gun]
            path = self.PickupPath[gun]
            self.PickupBy.remove(gun)
            self.PickupPath.remove(gun)
            if pawn and not self.IsDown(pawn):
                self.GrantGun(pawn, path)

    def GrantGun(self, pawn: ReadyOrNotCharacter, path: str):
        """The picked-up gun takes its slot in the suspect kit; the other gun stays."""
        primary = ""
        secondary = ""
        for item in pawn.InventoryComp.InventoryItems:
            if item:
                name = self.ClassName(item)
                if StartsWith(name, "Primary_", 0) and primary == "":
                    primary = GetPathName(GetObjectClass(item))
                if StartsWith(name, "Secondary_", 0) and secondary == "":
                    secondary = GetPathName(GetObjectClass(item))
        is_primary = Contains(path, ".Primary_", False, False)
        if is_primary:
            primary = path
        else:
            secondary = path
        self.EquipKit(pawn, self.KitLoadout(primary, secondary), is_primary)
        self.FillMagazines(pawn)
        found, left, right = Split(path, ".", 1, 1)
        title = self.WeaponTitle(LeftChop(right, 2)) if found else path
        pc = cast(pawn.Controller, ReadyOrNotPlayerController)
        self.Log(f"{self.NameOf(pc)} picked up {title}")
        self.Notify(pc, self.L("Подобрано: ", "Picked up: ") + title)

    # ================================================================ AI SWAT against suspect players

    def ArmourSquad(self):
        """The AI squad wears ceramic or steel plates (armour level 6) that no bullet in the game goes through
        until a ceramic plate wears out, and steel never does: suspect players could only wound them in the
        limbs. Under balanced rules the squad wears the default SWAT player's Kevlar instead."""
        if self.State.Rules != RULES_BALANCED:
            return
        if not self.Kevlar:
            kevlar = MakeSoftObjectPath("/Game/Blueprints/Items/ArmorRevised/ArmorMaterials/AM_Kevlar.AM_Kevlar")
            loaded = LoadAsset_Blocking(Conv_SoftObjPathToSoftObjRef(kevlar))
            self.Kevlar = cast(loaded, ArmourMaterial)
            if not self.Kevlar:
                return
        changed = 0
        for ai in self.LivingSwat():
            for item in ai.InventoryComp.InventoryItems:
                armour = cast(item, SWATArmour)
                if armour and armour.ArmourMaterial != self.Kevlar:
                    armour.ArmourMaterial = self.Kevlar
                    changed += 1
        if changed > 0:
            self.Log("AI squad armour -> Kevlar: " + str(changed))

    def BotCount(self, players: List[ReadyOrNotPlayerController]) -> int:
        """AI officers for this mission: the host's pick in the SWAT slots, at most the slots the SWAT players
        leave free."""
        swat = 0
        for pc in players:
            if self.TeamOf(pc) != SUSPECT:
                swat += 1
        return max(0, min(self.State.BotSlots, min(SLOTS - swat, MAX_BOTS)))

    def SizeSquad(self):
        """The mission spawns four officers: the ones beyond the host's pick leave (out of the squad lists
        first, then destroyed), a fifth is spawned next to the squad. The squad is sized 2 s after its first
        officer shows up, once the mission has spawned all of them."""
        manager = self.SquadManager()
        if self.SquadSized or not manager or len(manager.SwatAI) == 0:
            return
        if self.SquadFirstAt <= 0.0:
            self.SquadFirstAt = self.Now()
        if self.Now() - self.SquadFirstAt < 2.0:
            return
        self.SquadSized = True
        mode = cast(GetGameMode(), CoopGM)
        while len(manager.SwatAI) > self.BotsWanted:
            bot = manager.SwatAI[len(manager.SwatAI) - 1]
            manager.SwatAI.remove(bot)
            if mode:
                mode.SpawnedSWATAI.remove(bot)
            controller = bot.Controller
            bot.K2_DestroyActor()
            if controller:
                controller.K2_DestroyActor()
        if len(manager.SwatAI) < self.BotsWanted and mode:
            self.AddBot(manager, mode)
        self.Log(f"AI squad: {len(manager.SwatAI)} officers (wanted {self.BotsWanted})")

    def AddBot(self, manager: SWATManager, mode: CoopGM):
        """A fifth officer: the squad's class spawned next to the first officer in squad position Foxtrot, with
        its class's AI controller and the first officer's team, then put on the squad lists."""
        first = manager.SwatAI[0]
        at = first.K2_GetActorLocation()
        transform = MakeTransform(Vector(X=at.X + 100.0, Y=at.Y + 60.0, Z=at.Z + 20.0),
                                  Rotator(Pitch=0.0, Yaw=first.K2_GetActorRotation().Yaw, Roll=0.0), Vector(X=1.0, Y=1.0, Z=1.0))
        actor = BeginDeferredActorSpawnFromClass(mode.SwatAlphaClass, transform, 2, None, 1)
        bot = cast(actor, SWATCharacter)
        if not bot:
            self.Log("fifth officer: no spawn")
            return
        bot.SquadPosition = 4
        FinishSpawningActor(actor, transform, 1)
        if not bot.Controller:
            bot.SpawnDefaultController()
        bot.DefaultTeam = first.DefaultTeam
        manager.SwatAI.append(bot)
        mode.SpawnedSWATAI.append(bot)
        self.CopyKit(first, bot)
        # the mission dresses only its own officers: the first one's clothes with a face of the game's roster
        # (Customization is replicated, OnRep_Customization dresses the character)
        custom = first.Customization
        face = MakeSoftObjectPath("/Game/Blueprints/Customization/Characters/CC_Gideon.CC_Gideon")
        character = cast(LoadAsset_Blocking(Conv_SoftObjPathToSoftObjRef(face)), CustomizationDataBase)
        if character:
            custom.Character = character
        bot.Customization = custom
        bot.OnRep_Customization()
        item = bot.GetEquippedItem()
        self.Log("fifth officer: " + (self.ClassName(item) if item else "no weapon") + (", AI controller" if bot.Controller else ", no controller"))

    def CopyKit(self, source: ReadyOrNotCharacter, target: ReadyOrNotCharacter):
        """One officer's kit on another (the mission equips only the officers it spawns): the guns, the
        armour, the helmet with its mount, the facewear."""
        loadout = SavedLoadout(PrimaryAmmoSlotsCount=-1, SecondaryAmmoSlotsCount=-1, GrenadeSlotsCount=0, TacticalSlotsCount=0)
        for item in source.InventoryComp.InventoryItems:
            if not item:
                continue
            name = self.ClassName(item)
            path = GetPathName(GetObjectClass(item))
            if StartsWith(name, "Primary_", 0):
                loadout.Primary = self.LoadClassPath(path)
            elif StartsWith(name, "Secondary_", 0):
                loadout.Secondary = self.LoadClassPath(path)
            elif StartsWith(name, "Armor_", 0):
                loadout.Armor = self.LoadClassPath(path)
            elif StartsWith(name, "Helmet_", 0):
                loadout.Helmet = self.LoadClassPath(path)
            elif StartsWith(name, "BP_HelmetMount", 0):
                loadout.HelmetMount = self.LoadClassPath(path)
            elif StartsWith(name, "BP_Facewear", 0):
                loadout.Facewear = self.LoadClassPath(path)
        self.EquipKit(target, loadout, True)

    def CallSign(self, character: ReadyOrNotCharacter) -> str:
        """An officer's name: the face it wears (Customization.Character, CC_King: King), else the name of its
        squad position (a co-op mission's squad is King, Swan, Prescott, Eli; the mode adds Gideon)."""
        if character.Customization.Character:
            name = GetObjectName(character.Customization.Character)
            if StartsWith(name, "CC_", 0):
                return RightChop(name, 3)
        position = int(character.SquadPosition)
        if position >= 0 and position < 5:
            return self.BotNames()[position]
        return "SWAT"

    def BotNames(self) -> List[str]:
        names: List[str] = ["King", "Swan", "Prescott", "Eli", "Gideon"]
        return names

    # ================================================================ kills, deaths and the kill feed

    def Who(self, character: ReadyOrNotCharacter) -> str:
        """The kill feed's name: a player's name, an officer's call sign, a suspect, a civilian ("" for the
        reserve officers the game keeps under the map)."""
        if isinstance(character, TrailerSWATCharacter):
            return ""
        pc = cast(character.Controller, ReadyOrNotPlayerController)
        if pc and IsValid(pc.PlayerState):
            return self.NameOf(pc)
        if isinstance(character, SWATCharacter):
            return self.CallSign(character)
        if isinstance(character, SuspectCharacter):
            return self.L("подозреваемый", "suspect")
        if isinstance(character, CivilianCharacter):
            return self.L("гражданский", "civilian")
        return ""

    def SideOf(self, character: ReadyOrNotCharacter) -> int:
        """SWAT, SUSPECT, or 0 for anyone else (civilians)."""
        if isinstance(character, SuspectCharacter) or character.DefaultTeam == SUSPECT:
            return SUSPECT
        if isinstance(character, SWATCharacter) or isinstance(character, PlayerCharacter):
            return SWAT
        return 0

    def TrackTick(self, now: float):
        """Everyone seen standing is noted with a name; one that falls (dead, incapacitated, arrested or
        surrendered) counts as a kill of whoever the game noted as the killer (KilledBy, IncapacitatedBy)."""
        if now < self.TrackAt:
            return
        self.TrackAt = now + 0.25
        for actor in GetAllActorsOfClass(ReadyOrNotCharacter):
            character = cast(actor, ReadyOrNotCharacter)
            if not character or actor in self.Fallen or actor in self.Removed:
                continue
            if not self.IsDown(character):
                if not (character in self.Alive):
                    name = self.Who(character)
                    if name != "":
                        self.Alive[character] = name
                continue
            if character in self.Alive:
                self.Fallen.append(actor)
                self.Fell(character, self.Alive[character])
                self.Alive.remove(character)

    def Fell(self, victim: ReadyOrNotCharacter, name: str):
        """A player's death and a player's kill of an enemy count for the match and the round; the kill feed
        shows what involves a player or costs the SWAT an officer."""
        st = self.State
        killer = victim.KilledBy
        if not killer:
            killer = victim.IncapacitatedBy
        side = self.SideOf(victim)
        victim_player = isinstance(victim, PlayerCharacter)
        if victim_player:
            st.Deaths[name] = st.Deaths.get(name, 0) + 1
            st.RoundDeaths[name] = st.RoundDeaths.get(name, 0) + 1
        killer_name = ""
        killer_player = False
        weapon = ""
        if killer and killer != victim:
            killer_name = self.Alive.get(killer, "")
            if killer_name == "":
                killer_name = self.Who(killer)
            killer_player = isinstance(killer, PlayerCharacter)
            item = killer.GetEquippedItem()
            if item:
                weapon = self.WeaponTitle(self.ClassName(item))
            if killer_player and side != 0 and self.SideOf(killer) != side:
                st.Kills[killer_name] = st.Kills.get(killer_name, 0) + 1
                st.RoundKills[killer_name] = st.RoundKills.get(killer_name, 0) + 1
        self.Log(f"down: {name} by {killer_name} ({weapon})")
        if not victim_player and not killer_player and not isinstance(victim, SWATCharacter):
            return
        if killer_name == "":
            self.Feed(self.L(f"{name} выбыл", f"{name} is down"))
        elif weapon == "":
            self.Feed(self.L(f"{killer_name} убил {name}", f"{killer_name} killed {name}"))
        else:
            self.Feed(self.L(f"{killer_name} убил {name} ({weapon})", f"{killer_name} killed {name} ({weapon})"))

    def PublishStats(self, players: List[ReadyOrNotPlayerController]):
        """The match's kills and deaths go into the players' replicated PlayerState (the game's scoreboard
        lines show them), the score and the round's time left into the replicated GameState fields its PvP
        modes use: the scoreboard of a client with the pak reads them."""
        st = self.State
        for pc in players:
            name = self.NameOf(pc)
            state = self.StateOf(pc)
            kills = st.Kills.get(name, 0)
            deaths = st.Deaths.get(name, 0)
            if state.Kills != kills:
                state.Kills = kills
            if state.Deaths != deaths:
                state.Deaths = deaths
        gs = cast(GetGameState(), ReadyOrNotGameState)
        if not gs:
            return
        if gs.BlueTeamWins != st.ScoreSwat:
            gs.BlueTeamWins = st.ScoreSwat
        if gs.RedTeamWins != st.ScoreSuspects:
            gs.RedTeamWins = st.ScoreSuspects
        if st.Phase == "live":
            gs.RoundTimeRemaining = max(self.EndsAt - self.Now(), 1.0)
        elif st.Phase != "roundover":
            gs.RoundTimeRemaining = 0.0

    def FillStats(self, final: bool, players: List[ReadyOrNotPlayerController]):
        """The result page's table (the match's or the round's kills and deaths) and its best player: most
        kills, then fewest deaths."""
        st = self.State
        st.ResultNames.clear()
        st.ResultTeams.clear()
        st.ResultKills.clear()
        st.ResultDeaths.clear()
        best = ""
        best_kills = 0
        best_deaths = 0
        for pc in players:
            name = self.NameOf(pc)
            kills = 0
            deaths = 0
            if final:
                kills = st.Kills.get(name, 0)
                deaths = st.Deaths.get(name, 0)
            else:
                kills = st.RoundKills.get(name, 0)
                deaths = st.RoundDeaths.get(name, 0)
            st.ResultNames.append(name)
            st.ResultTeams.append(SUSPECT if self.IsSuspect(pc) else SWAT)
            st.ResultKills.append(kills)
            st.ResultDeaths.append(deaths)
            if kills > best_kills or (kills == best_kills and kills > 0 and deaths < best_deaths):
                best = name
                best_kills = kills
                best_deaths = deaths
        st.ResultMvp = best

    def FireTick(self):
        """AI SWAT never clear a player suspect for fire by themselves; the ones that see a suspect player get
        short scripted bursts."""
        if not self.Server or not self.State.Active or self.State.Phase != "live" or not self.MatchBots:
            return
        targets: List[ReadyOrNotCharacter] = []
        for pc in self.Players():
            pawn = self.PawnOf(pc)
            if pawn and self.StateOf(pc).Team == SUSPECT:
                targets.append(pawn)
        if len(targets) == 0:
            return
        for ai in self.LivingSwat():
            controller = cast(ai.Controller, CyberneticController)
            if not controller:
                continue
            for pawn in targets:
                if controller.IsCharacterEnemy(pawn) and controller.TargetingComponent.CanCharacterBeSeen(pawn):
                    controller.CombatActivity.ScriptedFireAtActor(pawn, 0.7, True, self.State.BotAccuracy, False)
                    break

    def DirectSquad(self, now: float, players: List[ReadyOrNotPlayerController]):
        """The AI squad follows its leader and must never follow a suspect player. A living SWAT player leads
        it as in co-op; without one an AI SWAT leads and the squad hunts the suspect players on its own."""
        swat = self.LivingSwat()
        manager = self.SquadManager()
        if len(swat) == 0 or not manager:
            return
        leaders: List[ReadyOrNotCharacter] = []
        targets: List[ReadyOrNotCharacter] = []
        for pc in players:
            pawn = self.PawnOf(pc)
            if pawn:
                if self.IsSuspect(pc):
                    targets.append(pawn)
                else:
                    leaders.append(pawn)
        if len(leaders) == 0:
            self.Lead(manager, swat, targets)
            self.HuntDirect(now, targets, swat)
            return
        leader = manager.SquadLeader
        if leader and not self.IsDown(leader):
            for pawn in leaders:
                if pawn == leader:
                    return
        manager.SquadLeader = leaders[0]

    def Lead(self, manager: SWATManager, swat: List[ReadyOrNotCharacter], hunted: List[ReadyOrNotCharacter]):
        leader = manager.SquadLeader
        replace = self.IsDown(leader)
        if not replace:
            for pawn in hunted:
                if pawn == leader:
                    replace = True
        if replace and len(swat) > 0:
            manager.SquadLeader = swat[0]

    def HuntReset(self, now: float):
        self.HuntTargets.clear()
        self.HuntContactId = 0
        self.HuntOrderedId = 0
        self.HuntHasShot = False
        self.HuntLastOrder = now
        self.HuntLastHint = now
        self.HuntContactAt = -1000.0
        self.HuntSearching = False

    def Nearest(self, targets: List[ReadyOrNotCharacter], start: Vector) -> ReadyOrNotCharacter:
        best = targets[0]
        best_distance = 1.0e12
        for pawn in targets:
            distance = Vector_Distance(pawn.K2_GetActorLocation(), start)
            if distance < best_distance:
                best = pawn
                best_distance = distance
        return best

    def HuntDirect(self, now: float, targets: List[ReadyOrNotCharacter], swat: List[ReadyOrNotCharacter]):
        """One step of the hunt: the squad learns where the suspect players are only by seeing them or
        hearing their shots; without contact it clears rooms, and after HINT_AFTER seconds of silence it
        gets a rough area around one of them."""
        manager = self.SquadManager()
        if not manager or len(targets) == 0 or len(swat) == 0:
            return
        # hearing: the targets' guns report their shots (OnWeaponFire)
        for pawn in targets:
            if not (pawn in self.HuntTargets):
                self.HuntTargets.append(pawn)
                for item in pawn.InventoryComp.InventoryItems:
                    weapon = cast(item, BaseMagazineWeapon)
                    if weapon and not (weapon in self.Bound):
                        bind(weapon.OnWeaponFire, self.OnWeaponFire)
                        self.Bound.append(weapon)
        seen: ReadyOrNotCharacter = None
        for ai in swat:
            controller = cast(ai.Controller, CyberneticController)
            if controller and not seen:
                for pawn in targets:
                    if not seen and controller.TargetingComponent.CanCharacterBeSeen(pawn):
                        seen = pawn
        if seen:
            self.HuntContact = seen.K2_GetActorLocation()
            self.HuntContactAt = now
            self.HuntContactSource = "sighting"
            self.HuntContactId += 1
        elif self.HuntHasShot:
            for ai in swat:
                if Vector_Distance(ai.K2_GetActorLocation(), self.HuntShot) <= HEAR_RANGE:
                    self.HuntContact = self.HuntShot
                    self.HuntContactAt = now
                    self.HuntContactSource = "gunshot"
                    self.HuntContactId += 1
                    break
        self.HuntHasShot = False
        leader_at = manager.SquadLeader.K2_GetActorLocation()
        last_news = max(self.HuntContactAt, self.HuntLastHint)
        if now - last_news >= HINT_AFTER:
            here = self.Nearest(targets, leader_at).K2_GetActorLocation()
            angle = RandomFloat() * 360.0
            offset = RandomFloat() * HINT_SPREAD
            self.HuntContact = Vector(X=here.X + DegCos(angle) * offset, Y=here.Y + DegSin(angle) * offset, Z=here.Z)
            self.HuntContactAt = now
            self.HuntContactSource = "hint"
            self.HuntContactId += 1
            self.HuntLastHint = now
        if seen:
            return  # in contact: the fire director handles it
        if self.HuntContactId != self.HuntOrderedId:
            manager.GiveMoveCommand(SQUAD, self.HuntContact)
            self.Log("squad: moving to the last " + self.HuntContactSource)
            self.HuntOrderedId = self.HuntContactId
            self.HuntOrdered = self.HuntContact
            self.HuntLastOrder = now
            self.HuntSearching = False
        elif not self.HuntSearching:
            target = leader_at
            far = True
            if self.HuntOrderedId > 0:
                target = self.HuntOrdered
                far = Vector_Distance(leader_at, target) >= 600.0
            if self.HuntOrderedId == 0 or not far or now - self.HuntLastOrder >= 45.0:
                manager.GiveSearchAndSecureCommand(SQUAD, target, False)
                self.Log("squad: search and secure")
                self.HuntSearching = True
                self.HuntLastOrder = now

    def OnWeaponFire(self, Weapon: BaseMagazineWeapon, bServer: bool):
        owner = Weapon.GetOwner()
        if owner and owner in self.HuntTargets:
            self.HuntShot = owner.K2_GetActorLocation()
            self.HuntHasShot = True

    # ================================================================ match flow

    def EndRound(self, now: float, players: List[ReadyOrNotPlayerController], swat_won: bool, reason: str):
        """A round ends inside the mission, without the game's mission end and its debriefing: the score goes
        up, everyone gets the result in chat, and after a short pause the mission loads again."""
        st = self.State
        if swat_won:
            st.ScoreSwat += 1
        else:
            st.ScoreSuspects += 1
        final = st.ScoreSwat >= st.RoundsToWin or st.ScoreSuspects >= st.RoundsToWin
        swapped = not final and st.Swap and st.RoundsToWin > 1 and st.Round == st.RoundsToWin - 1
        winners = ""
        for pc in players:
            if self.IsSuspect(pc) != swat_won:
                winners = winners + ("" if winners == "" else ", ") + self.NameOf(pc)
        if winners == "":
            winners = self.L("ИИ-отряд SWAT", "the AI SWAT squad") if swat_won else self.L("ИИ-подозреваемые", "the AI suspects")
        self.FillStats(final, players)
        st.HasResult = True
        st.ResultRound = st.Round
        st.ResultSwatWon = swat_won
        st.ResultReason = reason
        st.ResultFinal = final
        st.ResultSwapped = swapped
        st.ResultSwatScore = st.ScoreSwat
        st.ResultSuspectScore = st.ScoreSuspects
        st.ResultWinners = winners
        st.Phase = "roundover"
        self.BreakEnds = now + BREAK_SECONDS
        side = "SWAT" if swat_won else self.L("подозреваемых", "the suspects")
        self.Banner(self.L(f"Раунд {st.Round} — победа {side} — {self.ScoreLine()}", f"Round {st.Round} — {side} win — {self.ScoreLine()}"))
        self.Remote(self.L(f"Раунд {st.Round}: победа {side} — {reason}. {self.ScoreLine()}",
                           f"Round {st.Round}: {side} win — {reason}. {self.ScoreLine()}"))
        if final:
            self.Announce(self.L(f"Матч окончен — победили {winners}", f"Match over — {winners} win"))
        elif swapped:
            self.Announce(self.L("Половина матча: после этого раунда команды меняются сторонами",
                                 "Half time: the teams swap sides after this round"))

    def Travel(self):
        """The same mission again in the same game mode for every connected player (servertravel keeps a
        hosted game's clients; single player opens the level again)."""
        level = GetCurrentLevelName(True)
        mode = COOP_MODE
        mode_found, before, after = Split(GetGameMode().OptionsString, "game=", 1, 0)
        if mode_found:
            mode = after
            cut, head, tail = Split(after, "?", 1, 0)
            if cut:
                mode = head
        if level == "":
            self.Announce(self.L("PvP: не удалось перезапустить миссию для следующего раунда — режим выключен",
                                 "PvP: the mission could not be restarted for the next round — the mode is off"))
            self.StopMode()
            return
        command = "open "
        if IsServer() and not IsStandalone():
            command = "servertravel "
        self.State.Phase = "travel"
        self.State.TravelAt = self.Now()
        self.Log("next round: " + command + level + "?game=" + mode)
        ExecuteConsoleCommand(command + level + "?game=" + mode, None)

    def LoadNextRound(self, players: List[ReadyOrNotPlayerController]):
        st = self.State
        if st.ResultSwapped:
            for pc in players:
                team = SWAT if self.TeamOf(pc) == SUSPECT else SUSPECT
                st.Teams[self.NameOf(pc)] = team
            swat_score = st.ScoreSwat
            st.ScoreSwat = st.ScoreSuspects
            st.ScoreSuspects = swat_score
        if not st.ResultFinal:
            st.Round += 1
        st.PageMode = "final" if st.ResultFinal else "round"
        # everybody spawns as SWAT (co-op maps have no suspect starts); suspects take their AI again
        for pc in players:
            self.SetTeam(pc, SWAT)
        self.Travel()

    def StartLive(self, now: float, players: List[ReadyOrNotPlayerController]):
        st = self.State
        swat_players = 0
        suspect_players = 0
        for pc in players:
            if self.IsSuspect(pc):
                suspect_players += 1
            else:
                swat_players += 1
        # from the second round on a match goes on with the mission's AI suspects as the only suspects
        if suspect_players == 0 and st.Round <= 1:
            self.Log("nobody plays a suspect: a plain co-op mission")
            self.StopMode()
            return
        self.BotsWanted = self.BotCount(players)
        self.MatchBots = self.BotsWanted > 0
        if swat_players == 0 and not self.MatchBots:
            self.Announce(self.L("PvP: нет ни игроков SWAT, ни ботов — режим выключен", "PvP: no SWAT players and no bots — the mode is off"))
            self.StopMode()
            return
        if not self.MatchBots:
            self.HostPC().DestroySwatTeam()
        st.Phase = "live"
        self.StartedAt = now
        # the mission fades in from the loading screen: the round's popups wait for it
        self.BannerAfter = now + 3.0
        self.EndsAt = now + st.Minutes * 60.0
        self.DeathAt.clear()
        self.DeathTold.clear()
        self.Warned300 = False
        self.Warned60 = False
        st.PageMode = "teams"
        st.RoundKills.clear()
        st.RoundDeaths.clear()
        self.HuntReset(now)
        for pc in players:
            # a suspect whose booking was lost (AI gone, ready state missed) takes over now
            if self.IsSuspect(pc) and not (self.NameOf(pc) in self.ConvertAi) and self.StateOf(pc).Team != SUSPECT:
                self.DeathAt[self.NameOf(pc)] = now - RESPAWN_DELAY
                self.DeathTold[self.NameOf(pc)] = True
        if st.Round == 1:
            # the host read the rules in the menu; a client may not have the pak
            self.Remote(self.L("PvP: подозреваемые берут раунд, если положат всех SWAT или продержатся; убитый подозреваемый через 10 с вселяется в ИИ-подозреваемого. Подозреваемые открывают любые двери и подбирают упавшее оружие (зажать сбор улики).",
                               "PvP: the suspects win a round by taking down all SWAT or by holding out; a dead suspect takes over an AI suspect after 10 s. Suspects open any door and pick up dropped guns (hold evidence collection)."))
        self.Announce(self.L(f"Раунд {st.Round} — {self.ScoreLine()} — {st.Minutes} мин", f"Round {st.Round} — {self.ScoreLine()} — {st.Minutes} min"))

    def PreMissionScreen(self) -> W_PreMission_C:
        for widget in GetAllWidgetsOfClass(W_PreMission_C, False):
            if widget.IsInViewport():
                return cast(widget, W_PreMission_C)
        return None

    def AutoArm(self):
        """On the host's pre-mission screen of any co-op mission the mode arms itself; nobody choosing the
        suspects leaves a plain co-op mission."""
        if not self.State.Auto or self.AutoArmed or not self.Coop:
            return
        if not self.PreMissionScreen():
            return
        self.AutoArmed = True
        st = self.State
        st.Active = True
        st.AutoMatch = True
        st.Phase = "briefing"
        self.NewMatch()
        self.ResetMission()
        self.Log("armed on the pre-mission screen")

    def HoldStart(self):
        """While the host has not confirmed the team choice the start countdown stays full (a single-player
        mission readies the host by itself about 4 s into the pre-mission screen)."""
        if self.HostConfirmed or not self.Screen or not self.Screen.IsInViewport():
            return
        gs = cast(GetGameState(), ReadyOrNotGameState)
        if gs and gs.TimeTillGameStartCountdown < 10.0:
            gs.TimeTillGameStartCountdown = 10.0
            if not self.HoldTold:
                self.HoldTold = True
                self.Remote(self.L("Старт ждёт хоста: он выбирает сторону", "The start waits for the host to pick a side"))

    def ReadyEveryone(self, players: List[ReadyOrNotPlayerController], now: float):
        """Between rounds nobody has to press Ready: the host readies through its own ReadyUp (asked at most
        every 6 s, bReady follows a few seconds later), a client through Server_SetReadyState on the server."""
        for pc in players:
            name = self.NameOf(pc)
            if self.StateOf(pc).bReady:
                continue
            asked = self.ReadyAsked.get(name, -100.0)
            if now - asked < 6.0:
                continue
            self.ReadyAsked[name] = now
            if self.IsHost(pc):
                pc.ReadyUp()
            else:
                pc.Server_SetReadyState(True)
            self.Log("readied " + name)

    def SlowTick(self):
        if not self.Server:
            return
        st = self.State
        for pc in self.Players():
            if not (pc in self.Bound):
                bind(pc.OnPossessedPawnChanged, self.OnPawnChanged)
                self.Bound.append(pc)
        gs = cast(GetGameState(), ReadyOrNotGameState)
        if gs and not (gs in self.Bound):
            bind(gs.OnChatMessageReceived, self.OnChat)
            self.Bound.append(gs)
        if st.LogDirty and self.Now() - self.LogSavedAt > 10.0:
            self.LogSavedAt = self.Now()
            self.SaveLog()
        if not st.Active:
            self.AutoArm()
        if not st.Active:
            return
        now = self.Now()
        if st.Phase == "travel":
            # a travel blocks this world while it loads; this world still ticking means it failed
            if now - st.TravelAt > 30.0:
                self.Announce(self.L("PvP: следующий раунд не загрузился — режим выключен", "PvP: the next round did not load — the mode is off"))
                self.StopMode()
            return
        players = self.Players()
        self.PublishStats(players)
        if st.Phase == "briefing":
            self.BriefingTick(now, players)
        elif st.Phase == "live":
            self.LiveTick(now, players)
        elif st.Phase == "roundover" and now >= self.BreakEnds:
            self.LoadNextRound(players)

    def FastTick(self):
        if not self.Server or not self.State.Active:
            return
        now = self.Now()
        if len(self.Protected) > 0:
            self.ProtectTick(now)
        if self.State.Phase == "briefing":
            self.HoldStart()
        if self.State.Phase == "live":
            self.PickupTick(now)
            self.TrackTick(now)
        if len(self.ConvertAi) == 0:
            return
        for pc in self.Players():
            self.TryConvert(pc)

    def BriefingTick(self, now: float, players: List[ReadyOrNotPlayerController]):
        st = self.State
        any_suspect = False
        for pc in players:
            if self.TeamOf(pc) == SUSPECT:
                any_suspect = True
        # the AI squad of a hosted mission only when somebody plays a suspect (or the match goes on)
        self.BotsWanted = self.BotCount(players)
        self.SetSquadVariable(self.BotsWanted > 0 and (any_suspect or st.Round > 1))
        host = self.HostPC()
        # after a round the result shows and the next round starts by itself
        if st.PageMode == "round" and st.HasResult:
            if self.BriefedAt < 0.0:
                self.BriefedAt = now
            self.HostConfirmed = True
            if now >= self.BriefedAt + READY_AFTER:
                self.ReadyEveryone(players, now)
        self.Screen = self.PreMissionScreen()
        if self.Screen and host:
            self.ShowMenu(players, host, now)
        if not self.RulesTold and st.Round == 1:
            self.RulesTold = True
            self.Remote(self.L(f"PvP: SWAT против подозреваемых — раунд {st.Minutes} мин — ботов SWAT: {self.BotsWanted}. Подозреваемые воюют вместе с ИИ-подозреваемыми и после смерти вселяются в них",
                               f"PvP: SWAT against suspects — {st.Minutes} min rounds — SWAT bots: {self.BotsWanted}. Suspects fight alongside the AI suspects and take one over when they die"))
        roster = self.Roster(players)
        if roster != self.LastRosterText:
            self.LastRosterText = roster
            if st.Round > 1:
                self.Remote(self.L(f"Раунд {st.Round} — ", f"Round {st.Round} — ") + roster)
            else:
                self.Remote(roster + self.L(". Выбор стороны: чат !swat или !suspect", ". Pick a side in chat: !swat or !suspect"))
        # once everyone is ready the suspects get their AI suspects booked and their spawn kit set (a
        # player's own Ready overwrites ServerSavedLoadout, so the kit is put back while it is missing)
        gs = cast(GetGameState(), ReadyOrNotGameState)
        ready = gs and gs.IsEveryoneReady()
        no_armor = self.LoadClassPath("/Game/Blueprints/Items/ArmorRevised/Armor_NoArmor.Armor_NoArmor_C")
        for pc in players:
            name = self.NameOf(pc)
            wants = self.TeamOf(pc) == SUSPECT
            if wants:
                self.Suspects[name] = True
            else:
                self.Suspects.remove(name)
                self.ConvertAi.remove(name)
            if wants and ready:
                booked = name in self.ConvertAi
                ai: SuspectCharacter = None
                if booked:
                    ai = self.ConvertAi[name]
                if not booked or self.StateOf(pc).ServerSavedLoadout.Armor != no_armor:
                    if not ai or self.IsDown(ai):
                        ai = self.ChooseAi(players, Vector(X=0.0, Y=0.0, Z=0.0), False)
                    if ai:
                        self.Book(pc, ai)
        any_spawned = False
        for pc in players:
            if self.PawnOf(pc):
                any_spawned = True
        if any_spawned:
            self.StartLive(now, players)

    def LiveTick(self, now: float, players: List[ReadyOrNotPlayerController]):
        st = self.State
        host = self.HostPC()
        if host and self.IsSuspect(host) and self.PawnOf(host):
            self.HideSquadHud()
        self.DoorsTick()
        if self.MatchBots:
            self.SizeSquad()
            self.ArmourSquad()
            self.DirectSquad(now, players)
        swat_players = 0
        swat_alive = 0
        suspect_alive = 0
        waiting = 0
        ai_left = len(self.LivingAiSuspects())
        for pc in players:
            name = self.NameOf(pc)
            pawn = self.PawnOf(pc)
            if self.IsSuspect(pc):
                if name in self.ConvertAi:
                    waiting += 1
                elif pawn and self.StateOf(pc).Team == SUSPECT:
                    suspect_alive += 1
                    if pawn.DefaultTeam != SUSPECT:
                        pawn.DefaultTeam = SUSPECT
                    if not (pawn in self.Stripped):
                        self.Stripped.append(pawn)
                        self.StripSwatGear(pawn)
                    self.DeathAt.remove(name)
                else:
                    if not (name in self.DeathAt):
                        self.DeathAt[name] = now
                        self.DeathTold[name] = False
                        corpse = pc.K2_GetPawn()
                        if corpse:
                            self.DeathWhere[name] = corpse.K2_GetActorLocation()
                        else:
                            self.DeathWhere.remove(name)
                    if not self.DeathTold.get(name, False):
                        self.DeathTold[name] = True
                        if ai_left > 0:
                            pc.NotifyRespawnTime(RESPAWN_DELAY)
                            self.Notify(pc, self.L(f"Вселение в ИИ-подозреваемого через 10 с — в запасе: {ai_left}",
                                                   f"Taking over an AI suspect in 10 s — left: {ai_left}"))
                        else:
                            self.Notify(pc, self.L("ИИ-подозреваемых не осталось — вы наблюдаете до конца раунда",
                                                   "No AI suspects left — you spectate until the round ends"))
                    if ai_left > 0 and now >= self.DeathAt[name] + RESPAWN_DELAY:
                        has_where = name in self.DeathWhere
                        where = Vector(X=0.0, Y=0.0, Z=0.0)
                        if has_where:
                            where = self.DeathWhere[name]
                        ai = self.ChooseAi(players, where, has_where)
                        if ai and self.TakeOver(pc, ai):
                            waiting += 1
                        else:
                            self.DeathAt[name] = now
            else:
                swat_players += 1
                if pawn:
                    swat_alive += 1
        # everyone and the AI squad need a moment to spawn before anybody can count as out
        squad = len(self.LivingSwat())
        if squad > 0:
            self.SquadSeen = True
        if self.SquadSeen or now - self.StartedAt > 30.0:
            self.SetSquadVariable(False)
        if self.MatchBots and not self.SquadSeen and now - self.StartedAt > 30.0:
            self.MatchBots = False
            self.Announce(self.L("PvP: ИИ-отряд SWAT не появился — играем без ботов", "PvP: the AI SWAT squad did not show up — playing without bots"))
        if now - self.StartedAt < 10.0:
            return
        if swat_players > 0 and swat_alive == 0:
            self.EndRound(now, players, False, self.L("все бойцы SWAT нейтрализованы", "all SWAT players are down"))
        elif swat_players == 0 and self.MatchBots and self.SquadSeen and squad == 0:
            self.EndRound(now, players, False, self.L("ИИ-отряд SWAT уничтожен", "the AI SWAT squad is down"))
        elif now >= self.EndsAt:
            self.EndRound(now, players, False, self.L("время вышло, подозреваемые продержались", "time is up, the suspects held out"))
        elif ai_left == 0 and suspect_alive == 0 and waiting == 0:
            self.EndRound(now, players, True, self.L("все подозреваемые нейтрализованы", "all suspects are down"))
        else:
            left = self.EndsAt - now
            if left <= 300.0 and not self.Warned300 and self.EndsAt - self.StartedAt > 300.0:
                self.Warned300 = True
                self.Announce(self.L(f"До конца раунда 5:00 — ИИ-подозреваемых: {ai_left}", f"5:00 left in the round — AI suspects: {ai_left}"))
            if left <= 60.0 and not self.Warned60 and self.EndsAt - self.StartedAt > 60.0:
                self.Warned60 = True
                self.Announce(self.L(f"До конца раунда 1:00 — ИИ-подозреваемых: {ai_left}", f"1:00 left in the round — AI suspects: {ai_left}"))

    # ================================================================ chat

    def OnChat(self, Message: RChatMessage):
        """Players pick teams in chat on the pre-mission screen: !swat, !suspect, !teams."""
        st = self.State
        if not st.Active:
            return
        text = ToLower(Trim(Message.Message))
        if not StartsWith(text, "!", 0):
            return
        sender: ReadyOrNotPlayerController = None
        for pc in self.Players():
            if pc.PlayerState == Message.SenderPlayerState:
                sender = pc
        if not sender:
            return
        team = 0
        if text == "!swat" or text == "!сват":
            team = SWAT
        if text == "!suspect" or text == "!sus" or text == "!подозреваемый":
            team = SUSPECT
        if team != 0:
            if st.Phase != "briefing" and st.Phase != "travel":
                self.Tell(sender, self.L("Команду можно сменить только до начала раунда", "Teams can only be changed before the round starts"))
                return
            st.Teams[self.NameOf(sender)] = team
            self.Say(self.NameOf(sender) + " — " + self.TeamName(team))
        elif text == "!teams" or text == "!команды":
            self.Tell(sender, self.Roster(self.Players()))

    # ================================================================ the game's look

    def LoadFonts(self, pc: PlayerController):
        """The font of the game's menus (Barlow, with Cyrillic), taken from a scoreboard line's name: SemiBold
        for titles, Medium for the rest, as on the pre-mission screen. A text block made by the mode otherwise
        gets the engine's default font."""
        if self.FontsReady:
            return
        line = cast(Create(W_Scoreboard_Line_C, pc), W_Scoreboard_Line_C)
        if not line:
            return
        self.FontBold = line.Name.Font
        self.FontPlain = line.Name.Font
        self.FontPlain.TypefaceFontName = "Medium"
        self.FontsReady = True

    def Col(self, r: float, g: float, b: float, a: float) -> LinearColor:
        return LinearColor(R=r, G=g, B=b, A=a)

    def TeamColor(self, swat: bool) -> LinearColor:
        """The team colours of the game's scoreboard."""
        if swat:
            return self.Col(0.35, 0.55, 1.0, 1.0)
        return self.Col(1.0, 0.45, 0.15, 1.0)

    def Paint(self, text: TextBlock, color: LinearColor):
        text.SetColorAndOpacity(SlateColor(SpecifiedColor=color, ColorUseRule=0))

    def TextIn(self, tree: WidgetTree, value: str, size: int, bold: bool, color: LinearColor) -> TextBlock:
        text = cast(SpawnObject(TextBlock, tree), TextBlock)
        text.SetText(Text(value))
        font = text.Font
        if self.FontsReady:
            font = self.FontBold if bold else self.FontPlain
        font.Size = size
        text.SetFont(font)
        self.Paint(text, color)
        return text

    def MakeText(self, value: str, size: int, color: LinearColor) -> TextBlock:
        """A text on the pre-mission screen: the game's bold font for titles, its plain one for the rest."""
        return self.TextIn(self.Screen.WidgetTree, value, size, size >= 24, color)

    # ================================================================ the host's menu

    def Fill(self, color: LinearColor, left: float, top: float, right: float, bottom: float) -> Border:
        border = cast(SpawnObject(Border, self.Screen.WidgetTree), Border)
        border.Background.DrawAs = 3
        border.SetBrushColor(color)
        border.SetPadding(Margin(Left=left, top=top, Right=right, bottom=bottom))
        return border

    def VBox(self) -> VerticalBox:
        return cast(SpawnObject(VerticalBox, self.Screen.WidgetTree), VerticalBox)

    def HBox(self) -> HorizontalBox:
        return cast(SpawnObject(HorizontalBox, self.Screen.WidgetTree), HorizontalBox)

    def Sized(self, child: Widget, width: float, height: float) -> SizeBox:
        size = cast(SpawnObject(SizeBox, self.Screen.WidgetTree), SizeBox)
        if width > 0.0:
            size.SetWidthOverride(width)
        if height > 0.0:
            size.SetHeightOverride(height)
        size.SetContent(child)
        return size

    def Add(self, box: PanelWidget, child: Widget, left: float, top: float, right: float, bottom: float, halign: int, fill: bool, valign: int):
        """Adds to a vertical or horizontal box: padding, horizontal alignment (0 = fill), fill size,
        vertical alignment in a horizontal box (0 = fill)."""
        slot = box.AddChild(child)
        vslot = cast(slot, VerticalBoxSlot)
        if vslot:
            vslot.SetPadding(Margin(Left=left, top=top, Right=right, bottom=bottom))
            if halign != 0:
                vslot.SetHorizontalAlignment(halign)
            if fill:
                vslot.SetSize(SlateChildSize(Value=1.0, SizeRule=1))
        hslot = cast(slot, HorizontalBoxSlot)
        if hslot:
            hslot.SetPadding(Margin(Left=left, top=top, Right=right, bottom=bottom))
            if halign != 0:
                hslot.SetHorizontalAlignment(halign)
            if fill:
                hslot.SetSize(SlateChildSize(Value=1.0, SizeRule=1))
            if valign != 0:
                hslot.SetVerticalAlignment(valign)

    def MakeButton(self, label: str, style: int, action: str, size: int) -> W_StandardButton_C:
        button = cast(Create(W_StandardButton_C, self.HostPC()), W_StandardButton_C)
        button.DisplayStyle = style
        button.TextSize = size
        button.ButtonText = Text(label)
        button.PreConstruct(False)
        button.SetButtonText(Text(label))
        self.Actions[button] = action
        bind(button.OnClicked, self.OnMenuClick)
        return button

    def Label(self, button: W_StandardButton_C, label: str):
        button.SetButtonText(Text(label))

    def Show(self, widget: Widget, on: bool):
        value = SELF_HIT_TEST_INVISIBLE if on else COLLAPSED
        if widget.GetVisibility() != value:
            widget.SetVisibility(value)

    def Card(self, key: str) -> SizeBox:
        """A team card: a dark panel with the team's name in its colour and "n / 5", the player rows (the SWAT
        card then has the bot slots: a click on a bot takes it away, on a free slot adds one), a status line
        and the join button."""
        swat = key == "swat"
        white = self.Col(1.0, 1.0, 1.0, 1.0)
        grey = self.Col(0.45, 0.47, 0.5, 1.0)
        body = self.Fill(self.Col(0.006, 0.007, 0.009, 0.94), 0.0, 0.0, 0.0, 0.0)
        box = self.VBox()
        body.SetContent(box)
        header = self.Fill(self.Col(0.02, 0.022, 0.026, 1.0), 22.0, 14.0, 22.0, 14.0)
        self.Add(box, header, 0.0, 0.0, 0.0, 0.0, 0, False, 0)
        header_row = self.HBox()
        header.SetContent(header_row)
        title = self.MakeText("SWAT" if swat else self.L("ПОДОЗРЕВАЕМЫЕ", "SUSPECTS"), 30, self.TeamColor(swat))
        self.Add(header_row, title, 0.0, 0.0, 0.0, 0.0, 0, True, ALIGN_CENTER)
        count = self.MakeText("0 / 5", 26, white)
        self.Add(header_row, count, 24.0, 0.0, 0.0, 0.0, 0, False, ALIGN_CENTER)
        rows = self.VBox()
        self.Add(box, rows, 22.0, 16.0, 22.0, 0.0, 0, False, 0)
        self.Add(rows, self.MakeText(self.L("ИГРОКИ", "PLAYERS"), 15, grey), 0.0, 0.0, 0.0, 6.0, 0, False, 0)
        for i in range(MAX_ROWS):
            row = self.Fill(self.Col(1.0, 1.0, 1.0, 0.045), 14.0, 9.0, 14.0, 9.0)
            text = self.MakeText("", 20, white)
            row.SetContent(text)
            self.Add(rows, row, 0.0, 3.0, 0.0, 3.0, 0, False, 0)
            if swat:
                self.SwatRows.append(row)
                self.SwatTexts.append(text)
            else:
                self.SuspectRows.append(row)
                self.SuspectTexts.append(text)
        if swat:
            for i in range(SLOTS):
                slot_button = self.MakeButton("", STYLE_DARK, "slot" + str(i), 17)
                self.Add(rows, slot_button, 0.0, 3.0, 0.0, 3.0, 0, False, 0)
                self.SlotButtons.append(slot_button)
        status = self.MakeText("", 15, grey)
        self.Add(rows, status, 0.0, 10.0, 0.0, 0.0, 0, False, 0)
        join = self.MakeButton(self.L("ВСТУПИТЬ", "JOIN"), STYLE_LIGHT if swat else STYLE_RED, key, 22)
        self.Add(box, join, 22.0, 14.0, 22.0, 22.0, 0, False, 0)
        if swat:
            self.SwatHeader = header
            self.SwatCount = count
            self.SwatStatus = status
            self.SwatJoin = join
            self.SwatTitle = title
        else:
            self.SuspectHeader = header
            self.SuspectCount = count
            self.SuspectStatus = status
            self.SuspectJoin = join
            self.SuspectTitle = title
        return self.Sized(body, 560.0, 0.0)

    def ScoreBox(self, swat: bool) -> SizeBox:
        """One side of the score: the team's name in its colour and its round wins by the colon."""
        box = self.Fill(self.Col(0.02, 0.022, 0.026, 0.96), 30.0, 10.0, 30.0, 10.0)
        box.SetHorizontalAlignment(ALIGN_RIGHT if swat else ALIGN_LEFT)
        box.SetVerticalAlignment(ALIGN_CENTER)
        row = self.HBox()
        box.SetContent(row)
        name = self.MakeText("SWAT" if swat else self.L("ПОДОЗРЕВАЕМЫЕ", "SUSPECTS"), 28, self.TeamColor(swat))
        number = self.MakeText("0", 72, self.Col(1.0, 1.0, 1.0, 1.0))
        if swat:
            self.Add(row, name, 0.0, 0.0, 0.0, 0.0, 0, False, ALIGN_CENTER)
            self.Add(row, number, 24.0, 0.0, 0.0, 0.0, 0, False, ALIGN_CENTER)
            self.ResSwatBox = box
            self.ResSwatNumber = number
        else:
            self.Add(row, number, 0.0, 0.0, 0.0, 0.0, 0, False, ALIGN_CENTER)
            self.Add(row, name, 24.0, 0.0, 0.0, 0.0, 0, False, ALIGN_CENTER)
            self.ResSuspectBox = box
            self.ResSuspectNumber = number
        return self.Sized(box, 460.0, 120.0)

    def StatRow(self, name: str, kills: str, deaths: str, color: LinearColor) -> HorizontalBox:
        """A row of the result table: the name, kills and deaths in fixed columns."""
        row = self.HBox()
        name_text = self.MakeText(name, 20, color)
        kills_text = self.MakeText(kills, 20, color)
        deaths_text = self.MakeText(deaths, 20, color)
        kills_text.SetJustification(1)
        deaths_text.SetJustification(1)
        self.Add(row, self.Sized(name_text, 420.0, 0.0), 0.0, 0.0, 0.0, 0.0, 0, False, ALIGN_CENTER)
        self.Add(row, self.Sized(kills_text, 140.0, 0.0), 0.0, 0.0, 0.0, 0.0, 0, False, ALIGN_CENTER)
        self.Add(row, self.Sized(deaths_text, 140.0, 0.0), 0.0, 0.0, 0.0, 0.0, 0, False, ALIGN_CENTER)
        self.StatNames.append(name_text)
        self.StatKills.append(kills_text)
        self.StatDeaths.append(deaths_text)
        return row

    def BuildMenu(self):
        """The page over the host's pre-mission screen, built from UMG primitives in the screen's root canvas
        in the game's fonts; the buttons are the game's W_StandardButton_C."""
        self.Actions.clear()
        self.SwatRows.clear()
        self.SwatTexts.clear()
        self.SuspectRows.clear()
        self.SuspectTexts.clear()
        self.SlotButtons.clear()
        self.RoundButtons.clear()
        self.StatRows.clear()
        self.StatNames.clear()
        self.StatKills.clear()
        self.StatDeaths.clear()
        root = cast(self.Screen.WidgetTree.RootWidget, CanvasPanel)
        if not root:
            self.Log("menu: the pre-mission screen has no root canvas")
            return
        self.LoadFonts(self.HostPC())
        page = self.Fill(self.Col(0.01, 0.012, 0.016, 0.86), 0.0, 0.0, 0.0, 0.0)
        page.SetHorizontalAlignment(ALIGN_CENTER)
        page.SetVerticalAlignment(ALIGN_CENTER)
        slot = root.AddChildToCanvas(page)
        slot.SetAnchors(Anchors(Minimum=Vector2D(X=0.0, Y=0.0), Maximum=Vector2D(X=1.0, Y=1.0)))
        slot.SetOffsets(Margin(Left=0.0, top=0.0, Right=0.0, bottom=0.0))
        content = self.VBox()
        page.SetContent(content)
        white = self.Col(1.0, 1.0, 1.0, 1.0)
        grey = self.Col(0.45, 0.47, 0.5, 1.0)

        teams = self.VBox()
        self.Add(content, teams, 0.0, 0.0, 0.0, 0.0, ALIGN_CENTER, False, 0)
        self.Add(teams, self.MakeText(self.L("ВЫБЕРИТЕ КОМАНДУ", "CHOOSE YOUR TEAM"), 50, white), 0.0, 0.0, 0.0, 0.0, ALIGN_CENTER, False, 0)
        self.Subtitle = self.MakeText("", 18, grey)
        self.Add(teams, self.Subtitle, 0.0, 4.0, 0.0, 28.0, ALIGN_CENTER, False, 0)
        cards = self.HBox()
        self.Add(teams, cards, 0.0, 0.0, 0.0, 0.0, ALIGN_CENTER, False, 0)
        self.Add(cards, self.Card("swat"), 0.0, 0.0, 20.0, 0.0, 0, False, 0)
        self.Add(cards, self.Card("suspect"), 20.0, 0.0, 0.0, 0.0, 0, False, 0)
        bar = self.HBox()
        self.Add(teams, bar, 0.0, 26.0, 0.0, 0.0, ALIGN_CENTER, False, 0)
        self.AccuracyButton = self.MakeButton("", STYLE_DARK, "accuracy", 17)
        self.MinutesButton = self.MakeButton("", STYLE_DARK, "minutes", 17)
        self.RoundsButton = self.MakeButton("", STYLE_DARK, "rounds", 17)
        self.SwapButton = self.MakeButton("", STYLE_DARK, "swap", 17)
        self.RulesButton = self.MakeButton("", STYLE_DARK, "rules", 17)
        self.LangButton = self.MakeButton("", STYLE_DARK, "lang", 17)
        self.Add(bar, self.AccuracyButton, 0.0, 0.0, 0.0, 0.0, 0, False, 0)
        self.Add(bar, self.MinutesButton, 10.0, 0.0, 0.0, 0.0, 0, False, 0)
        self.Add(bar, self.RoundsButton, 10.0, 0.0, 0.0, 0.0, 0, False, 0)
        self.Add(bar, self.SwapButton, 10.0, 0.0, 0.0, 0.0, 0, False, 0)
        self.Add(bar, self.RulesButton, 10.0, 0.0, 0.0, 0.0, 0, False, 0)
        self.Add(bar, self.LangButton, 10.0, 0.0, 0.0, 0.0, 0, False, 0)
        actions = self.HBox()
        self.Add(teams, actions, 0.0, 14.0, 0.0, 0.0, ALIGN_CENTER, False, 0)
        self.Add(actions, self.MakeButton(self.L("АВТОВЫБОР", "AUTO PICK"), STYLE_DARK, "auto", 18), 0.0, 0.0, 0.0, 0.0, 0, False, ALIGN_CENTER)
        self.ReadyButton = self.MakeButton(self.L("ГОТОВ", "READY"), STYLE_YELLOW, "ready", 24)
        self.Add(actions, self.Sized(self.ReadyButton, 260.0, 0.0), 24.0, 0.0, 0.0, 0.0, 0, False, 0)
        self.Add(teams, self.MakeText(self.L("Остальные игроки выбирают сторону в чате: !swat или !suspect — список команд: !teams",
                                             "Other players pick a side in chat: !swat or !suspect — the teams: !teams"), 15, grey),
                 0.0, 18.0, 0.0, 0.0, ALIGN_CENTER, False, 0)
        self.TeamsBox = teams

        result = self.VBox()
        self.Add(content, result, 0.0, 0.0, 0.0, 0.0, ALIGN_CENTER, False, 0)
        self.ResTop = self.MakeText("", 22, grey)
        self.Add(result, self.ResTop, 0.0, 0.0, 0.0, 0.0, ALIGN_CENTER, False, 0)
        self.ResWinner = self.MakeText("", 64, white)
        self.Add(result, self.ResWinner, 0.0, 4.0, 0.0, 0.0, ALIGN_CENTER, False, 0)
        self.ResReason = self.MakeText("", 22, grey)
        self.Add(result, self.ResReason, 0.0, 0.0, 0.0, 30.0, ALIGN_CENTER, False, 0)
        scores = self.HBox()
        self.Add(result, scores, 0.0, 0.0, 0.0, 0.0, ALIGN_CENTER, False, 0)
        self.Add(scores, self.ScoreBox(True), 0.0, 0.0, 0.0, 0.0, 0, False, ALIGN_CENTER)
        self.Add(scores, self.MakeText(":", 64, grey), 22.0, 0.0, 22.0, 0.0, 0, False, ALIGN_CENTER)
        self.Add(scores, self.ScoreBox(False), 0.0, 0.0, 0.0, 0.0, 0, False, ALIGN_CENTER)
        table = self.Fill(self.Col(0.006, 0.007, 0.009, 0.9), 24.0, 14.0, 24.0, 14.0)
        self.Add(result, table, 0.0, 26.0, 0.0, 0.0, ALIGN_CENTER, False, 0)
        rows = self.VBox()
        table.SetContent(rows)
        self.Add(rows, self.StatRow(self.L("ИГРОК", "PLAYER"), self.L("УБИЙСТВА", "KILLS"), self.L("СМЕРТИ", "DEATHS"), grey), 0.0, 0.0, 0.0, 6.0, 0, False, 0)
        for i in range(STAT_ROWS):
            row = self.StatRow("", "", "", white)
            self.Add(rows, row, 0.0, 2.0, 0.0, 2.0, 0, False, 0)
            self.StatRows.append(row)
        self.ResMvp = self.MakeText("", 22, self.Col(1.0, 0.75, 0.2, 1.0))
        self.Add(result, self.ResMvp, 0.0, 16.0, 0.0, 0.0, ALIGN_CENTER, False, 0)
        self.ResNotice = self.MakeText("", 24, self.Col(1.0, 0.62, 0.05, 1.0))
        self.Add(result, self.ResNotice, 0.0, 22.0, 0.0, 0.0, ALIGN_CENTER, False, 0)
        self.ResCountdown = self.MakeText("", 20, white)
        self.Add(result, self.ResCountdown, 0.0, 10.0, 0.0, 0.0, ALIGN_CENTER, False, 0)
        buttons = self.HBox()
        self.Add(result, buttons, 0.0, 26.0, 0.0, 0.0, ALIGN_CENTER, False, 0)
        start_now = self.Sized(self.MakeButton(self.L("НАЧАТЬ СЕЙЧАС", "START NOW"), STYLE_YELLOW, "startnow", 22), 300.0, 0.0)
        teams_button = self.MakeButton(self.L("КОМАНДЫ И НАСТРОЙКИ", "TEAMS AND SETTINGS"), STYLE_DARK, "teams", 18)
        reset = self.MakeButton(self.L("СБРОСИТЬ МАТЧ", "RESET THE MATCH"), STYLE_DARK, "newmatch", 18)
        new_match = self.Sized(self.MakeButton(self.L("НОВЫЙ МАТЧ", "NEW MATCH"), STYLE_YELLOW, "newmatch", 24), 320.0, 0.0)
        self.Add(buttons, start_now, 0.0, 0.0, 0.0, 0.0, 0, False, ALIGN_CENTER)
        self.Add(buttons, teams_button, 16.0, 0.0, 0.0, 0.0, 0, False, ALIGN_CENTER)
        self.Add(buttons, reset, 16.0, 0.0, 0.0, 0.0, 0, False, ALIGN_CENTER)
        self.Add(buttons, new_match, 0.0, 0.0, 0.0, 0.0, 0, False, ALIGN_CENTER)
        self.RoundButtons.append(start_now)
        self.RoundButtons.append(teams_button)
        self.RoundButtons.append(reset)
        self.NewMatchButton = new_match
        self.ResultBox = result
        self.Page = page
        self.Log("team menu shown on the pre-mission screen")

    def AccuracyName(self) -> str:
        if self.State.BotAccuracy >= 2.5:
            return self.L("НИЗКАЯ", "LOW")
        if self.State.BotAccuracy >= 1.5:
            return self.L("СРЕДНЯЯ", "MEDIUM")
        return self.L("ВЫСОКАЯ", "HIGH")

    def FillCard(self, swat: bool, chosen: bool, bots: int):
        """The rows collected in RowTexts/RowColors; the SWAT card then shows its bot slots up to five, the
        suspects' card free rows."""
        rows = self.SwatRows if swat else self.SuspectRows
        texts = self.SwatTexts if swat else self.SuspectTexts
        header = self.SwatHeader if swat else self.SuspectHeader
        header.SetBrushColor(self.Col(0.05, 0.055, 0.065, 1.0) if chosen else self.Col(0.02, 0.022, 0.026, 1.0))
        for i in range(MAX_ROWS):
            if i < len(self.RowTexts):
                texts[i].SetText(Text(self.RowTexts[i]))
                self.Paint(texts[i], self.RowColors[i])
                self.Show(rows[i], True)
            elif i < SLOTS and not swat:
                texts[i].SetText(Text(self.L("свободно", "free")))
                self.Paint(texts[i], self.Col(0.3, 0.31, 0.33, 1.0))
                self.Show(rows[i], True)
            else:
                self.Show(rows[i], False)
        if swat:
            names = self.BotNames()
            for i in range(SLOTS):
                button = self.SlotButtons[i]
                if i < SLOTS - len(self.RowTexts):
                    if i < bots:
                        self.Label(button, self.L("БОТ  ", "BOT  ") + ToUpper(names[i]) + self.L("  —  убрать", "  —  remove"))
                    elif bots < MAX_BOTS:
                        self.Label(button, self.L("свободно  —  добавить бота", "free  —  add a bot"))
                    else:
                        self.Label(button, self.L("свободно", "free"))
                    self.Show(button, True)
                else:
                    self.Show(button, False)
        status = self.SwatStatus if swat else self.SuspectStatus
        status.SetText(Text(self.L("ВЫ В ЭТОЙ КОМАНДЕ", "YOU ARE ON THIS TEAM") if chosen else ""))
        self.Label(self.SwatJoin if swat else self.SuspectJoin, self.L("ВЫ ЗДЕСЬ", "YOU ARE HERE") if chosen else self.L("ВСТУПИТЬ", "JOIN"))

    def ShowMenu(self, players: List[ReadyOrNotPlayerController], host: ReadyOrNotPlayerController, now: float):
        st = self.State
        if not self.Page or self.Page.GetParent() == None:
            self.MenuHidden = False
            self.BuildMenu()
        if not self.Page:
            return
        mode = st.PageMode if st.HasResult else "teams"
        if self.HostConfirmed and mode == "teams":
            self.MenuHidden = True
        if self.MenuHidden:
            self.Show(self.Page, False)
            return
        if self.Page.GetVisibility() != VISIBLE:
            self.Page.SetVisibility(VISIBLE)  # Visible: the page takes the clicks meant for the screen under it
        self.Show(self.TeamsBox, mode == "teams")
        self.Show(self.ResultBox, mode != "teams")
        if mode != "teams":
            self.FillResult(mode == "final", host, now)
            return
        host_team = self.TeamOf(host)
        if st.Round > 1:
            self.Subtitle.SetText(Text(self.L(f"Раунд {st.Round} — {self.ScoreLine()} — матч до {st.RoundsToWin} побед",
                                              f"Round {st.Round} — {self.ScoreLine()} — first to {st.RoundsToWin} wins")))
        else:
            self.Subtitle.SetText(Text(self.L(f"Раунд {st.Minutes} мин — убитый подозреваемый вселяется в живого ИИ-подозреваемого — ",
                                              f"{st.Minutes} min rounds — a dead suspect takes over a living AI suspect — ") + self.RulesText()))
        white = self.Col(1.0, 1.0, 1.0, 1.0)
        bots = self.BotCount(players)
        for team in [SWAT, SUSPECT]:
            self.RowTexts.clear()
            self.RowColors.clear()
            count = 0
            for pc in players:
                if (self.TeamOf(pc) == SUSPECT) == (team == SUSPECT):
                    count += 1
                    ready = self.HostConfirmed if self.IsHost(pc) else self.StateOf(pc).bReady
                    notes = self.L("хост", "host") if self.IsHost(pc) else ""
                    if ready:
                        notes = notes + (", " if notes != "" else "") + self.L("готов", "ready")
                    self.RowTexts.append(self.NameOf(pc) + (" (" + notes + ")" if notes != "" else ""))
                    self.RowColors.append(white)
            if team == SWAT:
                self.SwatCount.SetText(Text(f"{count + bots} / {SLOTS}"))
                self.FillCard(True, host_team != SUSPECT, bots)
            else:
                ai = len(self.LivingAiSuspects())
                self.RowTexts.append(self.L(f"ИИ-подозреваемые: {ai}", f"AI suspects: {ai}") if ai > 0 else self.L("ИИ-подозреваемые миссии", "the mission's AI suspects"))
                self.RowColors.append(self.Col(0.62, 0.36, 0.18, 1.0))
                self.SuspectCount.SetText(Text(f"{count} / {SLOTS}"))
                self.FillCard(False, host_team == SUSPECT, 0)
        self.Label(self.AccuracyButton, self.L("МЕТКОСТЬ БОТОВ: ", "BOT ACCURACY: ") + self.AccuracyName())
        self.Label(self.MinutesButton, self.L(f"РАУНД: {st.Minutes} МИН", f"ROUND: {st.Minutes} MIN"))
        self.Label(self.RoundsButton, self.L("МАТЧ: 1 РАУНД", "MATCH: 1 ROUND") if st.RoundsToWin == 1 else self.L(f"МАТЧ: ДО {st.RoundsToWin} ПОБЕД", f"MATCH: FIRST TO {st.RoundsToWin}"))
        self.Label(self.SwapButton, self.L("СМЕНА СТОРОН: ВКЛ", "SIDE SWAP: ON") if st.Swap else self.L("СМЕНА СТОРОН: ВЫКЛ", "SIDE SWAP: OFF"))
        self.Label(self.RulesButton, self.L("ПРАВИЛА: УРАВНЕННЫЕ", "RULES: BALANCED") if st.Rules == RULES_BALANCED else self.L("ПРАВИЛА: ВАНИЛЬНЫЕ", "RULES: VANILLA"))
        self.Label(self.LangButton, "ЯЗЫК: РУССКИЙ" if self.Russian else "LANGUAGE: ENGLISH")
        self.Label(self.ReadyButton, self.L("ЖДЁМ ОСТАЛЬНЫХ", "WAITING FOR OTHERS") if self.HostConfirmed else self.L("ГОТОВ", "READY"))

    def FillResult(self, final: bool, host: ReadyOrNotPlayerController, now: float):
        st = self.State
        swat_won = st.ResultSwatWon
        self.ResTop.SetText(Text(self.L("МАТЧ ОКОНЧЕН", "MATCH OVER") if final else self.L(f"РАУНД {st.ResultRound}", f"ROUND {st.ResultRound}")))
        self.ResWinner.SetText(Text(self.L("ПОБЕДА SWAT", "SWAT WIN") if swat_won else self.L("ПОБЕДА ПОДОЗРЕВАЕМЫХ", "SUSPECTS WIN")))
        self.Paint(self.ResWinner, self.TeamColor(swat_won))
        self.ResReason.SetText(Text(self.L(f"решающий раунд {st.ResultRound}: {st.ResultReason}", f"deciding round {st.ResultRound}: {st.ResultReason}") if final else st.ResultReason))
        self.ResSwatNumber.SetText(Text(str(st.ResultSwatScore)))
        self.ResSuspectNumber.SetText(Text(str(st.ResultSuspectScore)))
        self.ResSwatBox.SetBrushColor(self.Col(0.05, 0.055, 0.065, 0.96) if swat_won else self.Col(0.02, 0.022, 0.026, 0.96))
        self.ResSuspectBox.SetBrushColor(self.Col(0.02, 0.022, 0.026, 0.96) if swat_won else self.Col(0.05, 0.055, 0.065, 0.96))
        # the table (index 0 of the text lists is the title row)
        for i in range(STAT_ROWS):
            if i < len(st.ResultNames):
                self.StatNames[i + 1].SetText(Text(st.ResultNames[i]))
                self.Paint(self.StatNames[i + 1], self.TeamColor(st.ResultTeams[i] != SUSPECT))
                self.StatKills[i + 1].SetText(Text(str(st.ResultKills[i])))
                self.StatDeaths[i + 1].SetText(Text(str(st.ResultDeaths[i])))
                self.Show(self.StatRows[i], True)
            else:
                self.Show(self.StatRows[i], False)
        if st.ResultMvp != "":
            self.ResMvp.SetText(Text(self.L("ЛУЧШИЙ ИГРОК ", "BEST PLAYER OF THE ") + (self.L("МАТЧА", "MATCH") if final else self.L("РАУНДА", "ROUND")) + ":  " + st.ResultMvp))
        else:
            self.ResMvp.SetText(Text(""))
        for button in self.RoundButtons:
            self.Show(button, not final)
        self.Show(self.NewMatchButton, final)
        host_team = self.TeamName(self.TeamOf(host))
        if final:
            self.ResNotice.SetText(Text(self.L("Победители: ", "Winners: ") + st.ResultWinners))
            self.ResCountdown.SetText(Text(self.L(f"Матч до {st.RoundsToWin} побед. «Новый матч» — снова выбор команд на этой же карте",
                                                  f"First to {st.RoundsToWin} wins. \"New match\" goes back to the team choice on this map")))
            return
        if st.ResultSwapped:
            self.ResNotice.SetText(Text(self.L(f"СМЕНА СТОРОН — теперь вы за {host_team} — {self.ScoreLine()}",
                                               f"SIDES SWAPPED — you now play {host_team} — {self.ScoreLine()}")))
        else:
            self.ResNotice.SetText(Text(self.L(f"Следующий раунд: вы за {host_team} — матч до {st.RoundsToWin} побед",
                                               f"Next round: you play {host_team} — first to {st.RoundsToWin} wins")))
        gs = cast(GetGameState(), ReadyOrNotGameState)
        if gs and gs.IsEveryoneReady():
            seconds = max(0, int(gs.TimeTillGameStartCountdown + 0.99))
            self.ResCountdown.SetText(Text(self.L(f"Раунд {st.Round} начнётся через {seconds} с", f"Round {st.Round} starts in {seconds} s")))
        else:
            start = self.BriefedAt if self.BriefedAt >= 0.0 else now
            seconds = max(0, int(start + READY_AFTER - now + 0.99))
            self.ResCountdown.SetText(Text(self.L(f"Раунд {st.Round} — автостарт через {seconds} с", f"Round {st.Round} — starts by itself in {seconds} s")))

    def OnMenuClick(self, CallingButton: W_StandardButton_C):
        st = self.State
        if not (CallingButton in self.Actions) or not st.Active or st.Phase != "briefing":
            return
        action = self.Actions[CallingButton]
        players = self.Players()
        host = self.HostPC()
        name = self.NameOf(host)
        if action == "swat" or action == "suspect":
            team = SUSPECT if action == "suspect" else SWAT
            if self.TeamOf(host) != team:
                self.Say(name + " — " + self.TeamName(team))
            st.Teams[name] = team
        elif action == "auto":
            # the side with fewer players; on a tie the suspects (SWAT have the bots when there are any)
            swat = 0
            suspects = 0
            for pc in players:
                if not self.IsHost(pc):
                    if self.TeamOf(pc) == SUSPECT:
                        suspects += 1
                    else:
                        swat += 1
            team = SUSPECT if suspects < swat or (suspects == swat and st.BotSlots > 0) else SWAT
            if self.TeamOf(host) != team:
                self.Say(name + " — " + self.TeamName(team))
            st.Teams[name] = team
        elif action == "accuracy":
            if st.BotAccuracy >= 2.5:
                st.BotAccuracy = 2.0
            elif st.BotAccuracy >= 1.5:
                st.BotAccuracy = 1.0
            else:
                st.BotAccuracy = 3.0
            self.SaveSettings()
        elif action == "minutes":
            steps: List[int] = [3, 5, 10, 15, 20, 30]
            st.Minutes = self.NextStep(steps, st.Minutes)
            self.SaveSettings()
        elif action == "rounds":
            steps: List[int] = [1, 2, 3, 4, 5, 8]
            st.RoundsToWin = self.NextStep(steps, st.RoundsToWin)
            self.SaveSettings()
        elif action == "swap":
            st.Swap = not st.Swap
            self.SaveSettings()
        elif action == "rules":
            st.Rules = RULES_VANILLA if st.Rules == RULES_BALANCED else RULES_BALANCED
            self.SaveSettings()
            self.Remote("PvP: " + self.RulesText())
        elif action == "lang":
            st.Lang = "en" if self.Russian else "ru"
            self.Russian = st.Lang == "ru"
            self.SaveSettings()
            # built again in the other language
            self.Page.RemoveFromParent()
        elif action == "startnow":
            self.ReadyEveryone(players, self.Now())
        elif action == "teams":
            # back to the team page; the start waits for the host's Ready again
            st.PageMode = "teams"
            self.HostConfirmed = False
            self.MenuHidden = False
        elif action == "newmatch":
            self.NewMatch()
            self.HostConfirmed = False
            self.MenuHidden = False
            self.Remote(self.L(f"PvP: новый матч до {st.RoundsToWin} побед — выбор команд", f"PvP: a new match, first to {st.RoundsToWin} wins — pick your teams"))
        elif action == "ready":
            if not self.StateOf(host).bReady and self.Screen:
                self.Screen.ToggleReady()
            if not self.HostConfirmed:
                self.HostConfirmed = True
                self.MenuHidden = True
                self.Say(name + self.L(" готов: ", " is ready: ") + self.TeamName(self.TeamOf(host)))
        else:
            # a SWAT slot: a bot taken away or added
            bots = self.BotCount(players)
            for i in range(SLOTS):
                if action == "slot" + str(i):
                    if i < bots:
                        st.BotSlots = bots - 1
                    elif bots < MAX_BOTS:
                        st.BotSlots = bots + 1
                    self.SaveSettings()
        self.ShowMenu(players, host, self.Now())

    def RulesText(self) -> str:
        if self.State.Rules == RULES_BALANCED:
            return self.L("правила уравненные: у подозреваемых винтовки, ИИ-отряд SWAT в кевларе",
                          "balanced rules: rifles for the suspects, Kevlar for the AI SWAT squad")
        return self.L("правила ванильные: оружие и броня как у ИИ миссии", "vanilla rules: guns and armour as the mission's AI have them")

    def NextStep(self, steps: List[int], current: int) -> int:
        for i in range(len(steps)):
            if steps[i] == current:
                return steps[(i + 1) % len(steps)]
        return steps[0]

    # ================================================================ the scoreboard on Tab (every machine with the pak)

    def HudTick(self):
        """While Tab is held in a PvP round the scoreboard shows over the mission journal; it is built once in
        a world and filled again every half second while it shows (BoardForced shows it without the key)."""
        pc = cast(GetPlayerController(0), ReadyOrNotPlayerController)
        if not pc or not cast(GetGameState(), ReadyOrNotGameState):
            return
        if self.Server:
            self.ShowBanners()
        want = self.BoardForced
        if not want and pc.IsInputKeyDown(Key(KeyName="Tab")):
            want = self.InMatch()
        if want:
            if not self.Board:
                self.BuildBoard(pc)
            if not self.Board:
                return
            now = GetTimeSeconds()
            if not self.BoardShown or now >= self.BoardAt:
                self.BoardAt = now + 0.5
                self.FillBoard(pc)
            if not self.BoardShown:
                self.BoardShown = True
                self.Board.SetVisibility(SELF_HIT_TEST_INVISIBLE)
        elif self.BoardShown:
            self.BoardShown = False
            self.Board.SetVisibility(COLLAPSED)

    def InMatch(self) -> bool:
        """A PvP round is on: the host knows it; a client sees the round time the host publishes or a player
        on the suspects' team."""
        if self.Server:
            return self.State.Active and (self.State.Phase == "live" or self.State.Phase == "roundover")
        gs = cast(GetGameState(), ReadyOrNotGameState)
        if gs.RoundTimeRemaining > 0.0:
            return True
        for ps in gs.PlayerArray:
            state = cast(ps, ReadyOrNotPlayerState)
            if state and state.Team == SUSPECT:
                return True
        return False

    def BoardText(self, value: str, size: int, color: LinearColor) -> TextBlock:
        return self.TextIn(self.Board.WidgetTree, value, size, False, color)

    def BuildBoard(self, pc: ReadyOrNotPlayerController):
        """The game's scoreboard panel (W_Scoreboard: the blur and the frame) with its content swapped for the
        mode's: a title line, the game's own column titles, a section per team of the game's player lines."""
        self.LoadFonts(pc)
        board = cast(Create(W_Scoreboard_C, pc), W_Scoreboard_C)
        if not board:
            return
        root = cast(board.WidgetTree.RootWidget, CanvasPanel)
        if not root:
            return
        overlay = cast(root.GetChildAt(0), Overlay)
        if not overlay:
            return
        fill = cast(overlay.GetChildAt(3), W_ScoreboardFill_C)
        if not fill:
            return
        # the game's column titles (their texts are written by the scoreboard's own refresh, which this one
        # never runs); the columns a co-op round has no use for go
        header = fill.Name.GetParent()
        for column in [fill.Incapacitations, fill.Arrests, fill.TimesArrested, fill.Damage, fill.Score]:
            column.SetVisibility(COLLAPSED)
        fill.Name.SetText(Text(self.L("ИМЯ", "NAME")))
        fill.Kills.SetText(Text(self.L("УБИЙСТВА", "KILLS")))
        fill.Deaths.SetText(Text(self.L("СМЕРТИ", "DEATHS")))
        fill.Status.SetText(Text(self.L("СТАТУС", "STATUS")))
        fill.Ping.SetText(Text(self.L("ПИНГ", "PING")))
        overlay.RemoveChildAt(3)
        # the spacer gives the panel its fixed size: without it the panel follows its content
        overlay.GetChildAt(2).SetVisibility(COLLAPSED)
        panel = cast(overlay.Slot, CanvasPanelSlot)
        if panel:
            panel.SetAutoSize(True)
        self.Board = board
        box = cast(SpawnObject(VerticalBox, board.WidgetTree), VerticalBox)
        slot = overlay.AddChildToOverlay(box)
        slot.SetPadding(Margin(Left=40.0, top=26.0, Right=40.0, bottom=30.0))
        self.BoardTitle = self.BoardText("", 22, self.Col(1.0, 1.0, 1.0, 1.0))
        self.Add(box, self.BoardTitle, 0.0, 0.0, 0.0, 14.0, ALIGN_CENTER, False, 0)
        header.RemoveFromParent()
        self.Add(box, header, 0.0, 0.0, 0.0, 4.0, 0, False, 0)
        self.Add(box, self.BoardText("SWAT", 18, self.TeamColor(True)), 0.0, 10.0, 0.0, 4.0, 0, False, 0)
        self.BoardSwat = cast(SpawnObject(VerticalBox, board.WidgetTree), VerticalBox)
        self.Add(box, self.BoardSwat, 0.0, 0.0, 0.0, 0.0, 0, False, 0)
        self.Add(box, self.BoardText(self.L("ПОДОЗРЕВАЕМЫЕ", "SUSPECTS"), 18, self.TeamColor(False)), 0.0, 16.0, 0.0, 4.0, 0, False, 0)
        self.BoardSuspects = cast(SpawnObject(VerticalBox, board.WidgetTree), VerticalBox)
        self.Add(box, self.BoardSuspects, 0.0, 0.0, 0.0, 0.0, 0, False, 0)
        board.AddToViewport(60)
        board.SetVisibility(COLLAPSED)
        self.BoardKey = ""

    def BoardBots(self) -> List[SWATCharacter]:
        """The AI officers in this world (the reserve ones under the map left out)."""
        result: List[SWATCharacter] = []
        for actor in GetAllActorsOfClass(SWATCharacter):
            bot = cast(actor, SWATCharacter)
            if bot and not isinstance(actor, TrailerSWATCharacter):
                result.append(bot)
        return result

    def TrimLine(self, line: W_Scoreboard_Line_C):
        line.bHideReadyCheckbox = True
        for column in [line.Incapacitations, line.Arrests, line.TimesArrested, line.Damage, line.Score]:
            column.SetVisibility(COLLAPSED)
        line.CheckboxImage.SetVisibility(COLLAPSED)

    def InfoLine(self, pc: ReadyOrNotPlayerController, name: str, status: str) -> W_Scoreboard_Line_C:
        """A line in the game's look for what has no PlayerState (an AI officer, the AI suspects): the name and
        the status written in, the rest blank."""
        line = cast(Create(W_Scoreboard_Line_C, pc), W_Scoreboard_Line_C)
        self.TrimLine(line)
        line.Name.SetText(Text(name))
        # the numbers come from a PlayerState, and without one the line shows its own choice of columns: all
        # of them transparent, keeping their place
        for column in [line.Kills, line.Incapacitations, line.Arrests, line.TimesArrested, line.Deaths, line.Damage, line.Score]:
            column.SetRenderOpacity(0.0)
        line.Status.SetText(Text(status))
        line.Ping.SetText(Text(""))
        return line

    def FillBoard(self, pc: ReadyOrNotPlayerController):
        """The title (round, score, time left) every time; the lines only when somebody joined, changed sides or
        an officer fell (a player's line follows its PlayerState by itself)."""
        gs = cast(GetGameState(), ReadyOrNotGameState)
        swat_score = gs.BlueTeamWins
        suspect_score = gs.RedTeamWins
        number = swat_score + suspect_score + 1
        left = gs.RoundTimeRemaining
        if self.Server:
            st = self.State
            swat_score = st.ScoreSwat
            suspect_score = st.ScoreSuspects
            number = st.Round
            left = max(self.EndsAt - self.Now(), 0.0) if st.Phase == "live" else 0.0
        seconds = int(left)
        minutes = int(left / 60.0)
        self.BoardTitle.SetText(Text(self.L(f"РАУНД {number}", f"ROUND {number}") + f"     SWAT  {swat_score} : {suspect_score}  "
                                     + self.L("ПОДОЗРЕВАЕМЫЕ", "SUSPECTS") + f"     {minutes}:{seconds % 60:02d}"))
        states: List[ReadyOrNotPlayerState] = []
        key = ""
        for ps in gs.PlayerArray:
            state = cast(ps, ReadyOrNotPlayerState)
            if state:
                states.append(state)
                key = key + state.GetPlayerName() + str(int(state.Team)) + ";"
        bots = self.BoardBots()
        for bot in bots:
            key = key + self.CallSign(bot) + ("-" if self.IsDown(bot) else "+")
        ai = 0
        for actor in GetAllActorsOfClass(SuspectCharacter):
            if not self.IsDown(cast(actor, SuspectCharacter)):
                ai += 1
        key = key + "ai" + str(ai)
        if key == self.BoardKey:
            return
        self.BoardKey = key
        self.BoardSwat.ClearChildren()
        self.BoardSuspects.ClearChildren()
        for state in states:
            line = cast(Create(W_Scoreboard_Line_C, pc), W_Scoreboard_Line_C)
            line.PlayerState = state
            self.TrimLine(line)
            if state.Team == SUSPECT:
                self.BoardSuspects.AddChild(line)
            else:
                self.BoardSwat.AddChild(line)
        for bot in bots:
            status = self.L("ВЫБЫЛ", "DOWN") if self.IsDown(bot) else self.L("В СТРОЮ", "ACTIVE")
            self.BoardSwat.AddChild(self.InfoLine(pc, self.CallSign(bot) + self.L("  (бот)", "  (bot)"), status))
        self.BoardSuspects.AddChild(self.InfoLine(pc, self.L("ИИ-ПОДОЗРЕВАЕМЫЕ", "AI SUSPECTS"), self.L(f"ОСТАЛОСЬ {ai}", f"{ai} LEFT")))
