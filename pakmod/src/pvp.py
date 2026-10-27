# Ready or Not PvP: SWAT players against suspect players in a co-op mission, with CS2-style rounds.
#
# The mod.io version of HostBrain's hb_pvp.lua (and hb_menu, hb_loadout, hb_hunt), written for kc.lang:
# compiled by pakmod/kc/lang.py into Blueprint classes, never run by Python. The director actor is spawned
# on every map by ModActorSpawnData (docs/modio-pak-research.md); its logic runs on the host only
# (KismetSystemLibrary.IsServer), so only the host needs the pak.
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
SQUAD = 5
SLOT = "RoNPvP"
VERSION = "0.2.0-alpha"
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

# UMG enums
VISIBLE = 0
COLLAPSED = 1
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


@blueprint("/Game/Mods/RoNPvP/BP_PvPSave")
class PvPSave(SaveGame):
    """The host's menu settings between game sessions (SaveGameToSlot "RoNPvP")."""
    Auto: bool
    Bots: bool
    Minutes: int
    RoundsToWin: int
    Swap: bool
    BotAccuracy: float


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
    Active: bool
    AutoMatch: bool
    Phase: str
    Round: int
    ScoreSwat: int
    ScoreSuspects: int
    Teams: Map[str, int]
    HasResult: bool
    ResultRound: int
    ResultSwatWon: bool
    ResultReason: str
    ResultFinal: bool
    ResultSwapped: bool
    ResultSwatScore: int
    ResultSuspectScore: int
    ResultWinners: str
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
    GunPrimary: str
    GunSecondary: str
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
    SuspectHeader: Border
    SuspectCount: TextBlock
    SuspectRows: List[Border]
    SuspectTexts: List[TextBlock]
    SuspectStatus: TextBlock
    SuspectJoin: W_StandardButton_C
    BotsButton: W_StandardButton_C
    AccuracyButton: W_StandardButton_C
    MinutesButton: W_StandardButton_C
    RoundsButton: W_StandardButton_C
    SwapButton: W_StandardButton_C
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
    RoundButtons: List[Widget]
    NewMatchButton: Widget
    RowTexts: List[str]
    RowColors: List[LinearColor]

    # ================================================================ lifecycle

    def ReceiveBeginPlay(self):
        self.Server = IsServer(self)
        if not self.Server:
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
        self.State.Log.append("---- " + VERSION + " · " + GetCurrentLevelName(True))
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
        save.Bots = st.Bots
        save.Minutes = st.Minutes
        save.RoundsToWin = st.RoundsToWin
        save.Swap = st.Swap
        save.BotAccuracy = st.BotAccuracy
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
            return "подозреваемые"
        return "SWAT"

    def Chat(self, text: str, color: LinearColor) -> RChatMessage:
        return RChatMessage(SenderName="PvP", Message=text, Color=color)

    def Say(self, text: str):
        """A line in everyone's chat and on the host's HUD."""
        gs = cast(GetGameState(), ReadyOrNotGameState)
        if gs:
            gs.Multicast_BroadcastChatMessage(self.Chat(text, LinearColor(R=1.0, G=0.75, B=0.2, A=1.0)))
        self.Toast(text)
        self.Log(text)

    def Tell(self, pc: ReadyOrNotPlayerController, text: str):
        pc.Client_SendChatMessage(self.Chat(text, LinearColor(R=0.6, G=0.9, B=1.0, A=1.0)))
        if self.IsHost(pc):
            self.Toast(text)
        self.Log("to " + self.NameOf(pc) + ": " + text)

    def Hud(self) -> W_HumanCharacter_HUD_V2_C:
        for widget in GetAllWidgetsOfClass(W_HumanCharacter_HUD_V2_C, False):
            if widget.IsInViewport():
                return cast(widget, W_HumanCharacter_HUD_V2_C)
        return None

    def Toast(self, text: str):
        hud = self.Hud()
        if hud:
            hud.AddToast(text)

    def Banner(self, text: str):
        hud = self.Hud()
        if hud:
            popup: Text = Text(text)
            hud.AddObjectivePopup(popup)

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
        return "SWAT: " + ("—" if swat == "" else swat) + " · Подозреваемые: " + ("—" if suspects == "" else suspects)

    def ScoreLine(self) -> str:
        return f"SWAT {self.State.ScoreSwat} : {self.State.ScoreSuspects} Подозреваемые"

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

    def NewMatch(self):
        st = self.State
        st.Round = 1
        st.ScoreSwat = 0
        st.ScoreSuspects = 0
        st.HasResult = False
        st.PageMode = "teams"

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
        return self.WeaponTitle(self.GunPrimary) + " + " + self.WeaponTitle(self.GunSecondary)

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
        self.Log(f"{name} took an AI suspect's place ({stripped} SWAT items removed)")
        self.Tell(pc, f"Вы — подозреваемый: {self.WeaponTitle(primary)} + {self.WeaponTitle(secondary)}. ИИ-подозреваемых в запасе: {len(self.LivingAiSuspects())}")

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
        self.Log(f"{name} took over an AI suspect ({weapons}, {stripped} SWAT items removed)")
        self.Tell(pc, f"Вы — подозреваемый: {weapons}. ИИ-подозреваемых в запасе: {len(self.LivingAiSuspects())}")
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
        if not self.State.Bots or self.SquadSeen or not self.IsHost(pc):
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
        if EndsWith(title, "_V2", 1):
            title = LeftChop(title, 3)
        return title

    def RandomPrimary(self) -> str:
        names: List[str] = ["Primary_SLR47", "Primary_FAL", "Primary_870mcs", "Primary_MP5A2"]
        return names[RandomIntegerInRange(0, 3)]

    def RandomSecondary(self) -> str:
        names: List[str] = ["Secondary_M1911_V2", "Secondary_M92FS_V2", "Secondary_G19_V2", "Secondary_Python_V2", "Secondary_P99"]
        return names[RandomIntegerInRange(0, 4)]

    def ClassName(self, item: Object) -> str:
        name = GetObjectName(GetObjectClass(item))
        if EndsWith(name, "_C", 0):
            name = LeftChop(name, 2)
        return name

    def GunsFor(self, ai: ReadyOrNotCharacter):
        """Player guns of the same kind as the AI suspect's (GunPrimary, GunSecondary); a random suspect-style
        pair fills what is missing. AKs become the SLR-47 and the G3 and machine guns the FAL (their
        handling throws the sights about when a player aims while stepping sideways)."""
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
        if self.GunPrimary == "":
            self.GunPrimary = self.RandomPrimary()
        if self.GunSecondary == "":
            self.GunSecondary = self.RandomSecondary()

    def SuspectLoadout(self, primary: str, secondary: str) -> SavedLoadout:
        loadout = SavedLoadout(PrimaryAmmoSlotsCount=-1, SecondaryAmmoSlotsCount=-1, GrenadeSlotsCount=0, TacticalSlotsCount=0)
        loadout.Primary = self.PlayerWeapon(primary)
        loadout.Secondary = self.PlayerWeapon(secondary)
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
        options = LoadoutEquipOptions(EquipItemCategory=1, bReplicates=True, bSanitizeLoadout=False)
        return EquipLoadoutOnPlayer(self.SuspectLoadout(primary, secondary), pawn, options)

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

    # ================================================================ AI SWAT against suspect players

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
            winners = "ИИ-отряд SWAT" if swat_won else "ИИ-подозреваемые"
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
        side = "SWAT" if swat_won else "подозреваемых"
        text = f"Раунд {st.Round}: победа {side} — {reason}. {self.ScoreLine()}"
        self.Say(text)
        self.Banner(text)
        if final:
            self.Say(f"Матч окончен: победили {'SWAT' if swat_won else 'подозреваемые'} ({winners}). {self.ScoreLine()}")
        elif swapped:
            self.Say("Половина матча: после этого раунда команды меняются сторонами")

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
            self.Say("PvP: не удалось перезапустить миссию для следующего раунда — режим выключен")
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
        self.MatchBots = st.Bots
        if swat_players == 0 and not self.MatchBots:
            self.Say("PvP: нет ни игроков SWAT, ни ботов — режим выключен")
            self.StopMode()
            return
        if not self.MatchBots:
            self.HostPC().DestroySwatTeam()
        st.Phase = "live"
        self.StartedAt = now
        self.EndsAt = now + st.Minutes * 60.0
        self.DeathAt.clear()
        self.DeathTold.clear()
        self.Warned300 = False
        self.Warned60 = False
        st.PageMode = "teams"
        self.HuntReset(now)
        for pc in players:
            # a suspect whose booking was lost (AI gone, ready state missed) takes over now
            if self.IsSuspect(pc) and not (self.NameOf(pc) in self.ConvertAi) and self.StateOf(pc).Team != SUSPECT:
                self.DeathAt[self.NameOf(pc)] = now - RESPAWN_DELAY
                self.DeathTold[self.NameOf(pc)] = True
        if st.Round == 1:
            length = f"до {st.RoundsToWin} побед" if st.RoundsToWin > 1 else "из одного раунда"
            squad = "ИИ-отряд SWAT в игре." if self.MatchBots else "Без ИИ-отряда SWAT."
            self.Say(f"PvP: матч {length}, раунд {st.Minutes} мин. Подозреваемые берут раунд, если положат всех SWAT или продержатся; SWAT — если нейтрализует всех подозреваемых. Убитый подозреваемый через 10 с вселяется в ИИ-подозреваемого. {squad}")
        text = f"Раунд {st.Round} · {self.ScoreLine()} · {st.Minutes} мин"
        self.Say(text)
        self.Banner(text)

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
                self.Say("Старт ждёт хоста: выберите сторону в меню и нажмите «Готов»")

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
                self.Say("PvP: следующий раунд не загрузился — режим выключен")
                self.StopMode()
            return
        players = self.Players()
        if st.Phase == "briefing":
            self.BriefingTick(now, players)
        elif st.Phase == "live":
            self.LiveTick(now, players)
        elif st.Phase == "roundover" and now >= self.BreakEnds:
            self.LoadNextRound(players)

    def FastTick(self):
        if not self.Server or not self.State.Active:
            return
        if self.State.Phase == "briefing":
            self.HoldStart()
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
        self.SetSquadVariable(st.Bots and (any_suspect or st.Round > 1))
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
            squad = "ИИ-отряд SWAT в игре" if st.Bots else "без ИИ-отряда SWAT"
            self.Say(f"PvP: SWAT против подозреваемых · раунд {st.Minutes} мин · {squad}. Подозреваемые воюют вместе с ИИ-подозреваемыми и после смерти вселяются в них")
        roster = self.Roster(players)
        if roster != self.LastRosterText:
            self.LastRosterText = roster
            if st.Round > 1:
                self.Say(f"Раунд {st.Round} · {roster}")
            else:
                self.Say(roster + ". Выбор стороны: у хоста меню на экране подготовки, у остальных — чат !swat или !suspect")
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
        if self.MatchBots:
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
                            self.Tell(pc, f"Вселение в ИИ-подозреваемого через 10 с (в запасе: {ai_left})")
                        else:
                            self.Tell(pc, "ИИ-подозреваемых не осталось — вы наблюдаете за своими до конца раунда")
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
            self.Say("PvP: ИИ-отряд SWAT не появился — играем без ботов")
        if now - self.StartedAt < 10.0:
            return
        if swat_players > 0 and swat_alive == 0:
            self.EndRound(now, players, False, "все бойцы SWAT нейтрализованы")
        elif swat_players == 0 and self.MatchBots and self.SquadSeen and squad == 0:
            self.EndRound(now, players, False, "ИИ-отряд SWAT уничтожен")
        elif now >= self.EndsAt:
            self.EndRound(now, players, False, "время вышло, подозреваемые продержались")
        elif ai_left == 0 and suspect_alive == 0 and waiting == 0:
            self.EndRound(now, players, True, "все подозреваемые нейтрализованы")
        else:
            left = self.EndsAt - now
            if left <= 300.0 and not self.Warned300 and self.EndsAt - self.StartedAt > 300.0:
                self.Warned300 = True
                self.Say(f"До конца раунда 5:00 · ИИ-подозреваемых: {ai_left}")
            if left <= 60.0 and not self.Warned60 and self.EndsAt - self.StartedAt > 60.0:
                self.Warned60 = True
                self.Say(f"До конца раунда 1:00 · ИИ-подозреваемых: {ai_left}")

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
                self.Tell(sender, "Команду можно сменить только до начала раунда")
                return
            st.Teams[self.NameOf(sender)] = team
            self.Say(self.NameOf(sender) + " → " + self.TeamName(team))
        elif text == "!teams" or text == "!команды":
            self.Tell(sender, self.Roster(self.Players()))

    # ================================================================ the host's menu

    def Col(self, r: float, g: float, b: float, a: float) -> LinearColor:
        return LinearColor(R=r, G=g, B=b, A=a)

    def Paint(self, text: TextBlock, color: LinearColor):
        text.SetColorAndOpacity(SlateColor(SpecifiedColor=color, ColorUseRule=0))

    def MakeText(self, value: str, size: int, color: LinearColor) -> TextBlock:
        text = cast(SpawnObject(TextBlock, self.Screen.WidgetTree), TextBlock)
        text.SetText(Text(value))
        font = text.Font
        font.Size = size
        text.SetFont(font)
        self.Paint(text, color)
        return text

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
        """A team card: coloured header with the title and "n / 5", the player rows, a status line and the
        join button."""
        swat = key == "swat"
        body = self.Fill(self.Col(0.006, 0.012, 0.025, 0.96) if swat else self.Col(0.025, 0.012, 0.004, 0.96), 0.0, 0.0, 0.0, 0.0)
        box = self.VBox()
        body.SetContent(box)
        header = self.Fill(self.Col(0.04, 0.1, 0.27, 1.0) if swat else self.Col(0.36, 0.13, 0.015, 1.0), 22.0, 16.0, 22.0, 16.0)
        self.Add(box, header, 0.0, 0.0, 0.0, 0.0, 0, False, 0)
        header_row = self.HBox()
        header.SetContent(header_row)
        self.Add(header_row, self.MakeText("SWAT" if swat else "ПОДОЗРЕВАЕМЫЕ", 32, self.Col(1.0, 1.0, 1.0, 1.0)), 0.0, 0.0, 0.0, 0.0, 0, True, 0)
        count = self.MakeText("0 / 5", 28, self.Col(1.0, 1.0, 1.0, 1.0))
        self.Add(header_row, count, 24.0, 4.0, 0.0, 0.0, 0, False, 0)
        accent = self.Col(0.3, 0.5, 1.0, 1.0) if swat else self.Col(1.0, 0.5, 0.12, 1.0)
        rows = self.VBox()
        self.Add(box, rows, 22.0, 18.0, 22.0, 0.0, 0, False, 0)
        self.Add(rows, self.MakeText("ИГРОКИ", 14, accent), 0.0, 0.0, 0.0, 8.0, 0, False, 0)
        for i in range(MAX_ROWS):
            row = self.Fill(self.Col(0.0, 0.0, 0.0, 0.45), 14.0, 9.0, 14.0, 9.0)
            text = self.MakeText("", 20, self.Col(1.0, 1.0, 1.0, 1.0))
            row.SetContent(text)
            self.Add(rows, row, 0.0, 3.0, 0.0, 3.0, 0, False, 0)
            if swat:
                self.SwatRows.append(row)
                self.SwatTexts.append(text)
            else:
                self.SuspectRows.append(row)
                self.SuspectTexts.append(text)
        status = self.MakeText("", 16, accent)
        self.Add(rows, status, 0.0, 12.0, 0.0, 0.0, 0, False, 0)
        join = self.MakeButton("ВСТУПИТЬ", STYLE_LIGHT if swat else STYLE_RED, key, 22)
        self.Add(box, join, 22.0, 14.0, 22.0, 22.0, 0, False, 0)
        if swat:
            self.SwatHeader = header
            self.SwatCount = count
            self.SwatStatus = status
            self.SwatJoin = join
        else:
            self.SuspectHeader = header
            self.SuspectCount = count
            self.SuspectStatus = status
            self.SuspectJoin = join
        return self.Sized(body, 560.0, 0.0)

    def ScoreBox(self, swat: bool) -> SizeBox:
        """One side of the score: the team's name and round wins on its colour, the number by the colon."""
        box = self.Fill(self.Col(0.04, 0.1, 0.27, 1.0) if swat else self.Col(0.36, 0.13, 0.015, 1.0), 30.0, 10.0, 30.0, 10.0)
        box.SetHorizontalAlignment(ALIGN_RIGHT if swat else ALIGN_LEFT)
        box.SetVerticalAlignment(ALIGN_CENTER)
        row = self.HBox()
        box.SetContent(row)
        name = self.MakeText("SWAT" if swat else "ПОДОЗРЕВАЕМЫЕ", 28, self.Col(1.0, 1.0, 1.0, 1.0))
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

    def BuildMenu(self):
        """The page over the host's pre-mission screen, built from UMG primitives in the screen's root
        canvas; the buttons are the game's W_StandardButton_C."""
        self.Actions.clear()
        self.SwatRows.clear()
        self.SwatTexts.clear()
        self.SuspectRows.clear()
        self.SuspectTexts.clear()
        self.RoundButtons.clear()
        root = cast(self.Screen.WidgetTree.RootWidget, CanvasPanel)
        if not root:
            self.Log("menu: the pre-mission screen has no root canvas")
            return
        page = self.Fill(self.Col(0.01, 0.012, 0.016, 0.86), 0.0, 0.0, 0.0, 0.0)
        page.SetHorizontalAlignment(ALIGN_CENTER)
        page.SetVerticalAlignment(ALIGN_CENTER)
        slot = root.AddChildToCanvas(page)
        slot.SetAnchors(Anchors(Minimum=Vector2D(X=0.0, Y=0.0), Maximum=Vector2D(X=1.0, Y=1.0)))
        slot.SetOffsets(Margin(Left=0.0, top=0.0, Right=0.0, bottom=0.0))
        content = self.VBox()
        page.SetContent(content)
        white = self.Col(1.0, 1.0, 1.0, 1.0)
        grey = self.Col(0.32, 0.34, 0.37, 1.0)

        teams = self.VBox()
        self.Add(content, teams, 0.0, 0.0, 0.0, 0.0, ALIGN_CENTER, False, 0)
        self.Add(teams, self.MakeText("ВЫБЕРИТЕ КОМАНДУ", 54, white), 0.0, 0.0, 0.0, 0.0, ALIGN_CENTER, False, 0)
        self.Subtitle = self.MakeText("", 18, grey)
        self.Add(teams, self.Subtitle, 0.0, 4.0, 0.0, 30.0, ALIGN_CENTER, False, 0)
        cards = self.HBox()
        self.Add(teams, cards, 0.0, 0.0, 0.0, 0.0, ALIGN_CENTER, False, 0)
        self.Add(cards, self.Card("swat"), 0.0, 0.0, 20.0, 0.0, 0, False, 0)
        self.Add(cards, self.Card("suspect"), 20.0, 0.0, 0.0, 0.0, 0, False, 0)
        bar = self.HBox()
        self.Add(teams, bar, 0.0, 28.0, 0.0, 0.0, ALIGN_CENTER, False, 0)
        self.BotsButton = self.MakeButton("", STYLE_DARK, "bots", 18)
        self.AccuracyButton = self.MakeButton("", STYLE_DARK, "accuracy", 18)
        self.MinutesButton = self.MakeButton("", STYLE_DARK, "minutes", 18)
        self.RoundsButton = self.MakeButton("", STYLE_DARK, "rounds", 18)
        self.SwapButton = self.MakeButton("", STYLE_DARK, "swap", 18)
        self.Add(bar, self.BotsButton, 0.0, 0.0, 0.0, 0.0, 0, False, 0)
        self.Add(bar, self.AccuracyButton, 12.0, 0.0, 0.0, 0.0, 0, False, 0)
        self.Add(bar, self.MinutesButton, 12.0, 0.0, 0.0, 0.0, 0, False, 0)
        self.Add(bar, self.RoundsButton, 12.0, 0.0, 0.0, 0.0, 0, False, 0)
        self.Add(bar, self.SwapButton, 12.0, 0.0, 0.0, 0.0, 0, False, 0)
        actions = self.HBox()
        self.Add(teams, actions, 0.0, 14.0, 0.0, 0.0, ALIGN_CENTER, False, 0)
        self.Add(actions, self.MakeButton("АВТОВЫБОР", STYLE_DARK, "auto", 18), 0.0, 0.0, 0.0, 0.0, 0, False, ALIGN_CENTER)
        self.ReadyButton = self.MakeButton("ГОТОВ", STYLE_YELLOW, "ready", 24)
        self.Add(actions, self.Sized(self.ReadyButton, 260.0, 0.0), 24.0, 0.0, 0.0, 0.0, 0, False, 0)
        self.Add(teams, self.MakeText("Остальные игроки выбирают сторону в чате: !swat или !suspect · список команд: !teams", 15,
                                      self.Col(0.16, 0.17, 0.19, 1.0)), 0.0, 18.0, 0.0, 0.0, ALIGN_CENTER, False, 0)
        self.TeamsBox = teams

        result = self.VBox()
        self.Add(content, result, 0.0, 0.0, 0.0, 0.0, ALIGN_CENTER, False, 0)
        self.ResTop = self.MakeText("", 22, grey)
        self.Add(result, self.ResTop, 0.0, 0.0, 0.0, 0.0, ALIGN_CENTER, False, 0)
        self.ResWinner = self.MakeText("", 68, white)
        self.Add(result, self.ResWinner, 0.0, 4.0, 0.0, 0.0, ALIGN_CENTER, False, 0)
        self.ResReason = self.MakeText("", 22, grey)
        self.Add(result, self.ResReason, 0.0, 0.0, 0.0, 34.0, ALIGN_CENTER, False, 0)
        scores = self.HBox()
        self.Add(result, scores, 0.0, 0.0, 0.0, 0.0, ALIGN_CENTER, False, 0)
        self.Add(scores, self.ScoreBox(True), 0.0, 0.0, 0.0, 0.0, 0, False, ALIGN_CENTER)
        self.Add(scores, self.MakeText(":", 64, grey), 22.0, 0.0, 22.0, 0.0, 0, False, ALIGN_CENTER)
        self.Add(scores, self.ScoreBox(False), 0.0, 0.0, 0.0, 0.0, 0, False, ALIGN_CENTER)
        self.ResNotice = self.MakeText("", 26, self.Col(1.0, 0.62, 0.05, 1.0))
        self.Add(result, self.ResNotice, 0.0, 34.0, 0.0, 0.0, ALIGN_CENTER, False, 0)
        self.ResCountdown = self.MakeText("", 22, white)
        self.Add(result, self.ResCountdown, 0.0, 12.0, 0.0, 0.0, ALIGN_CENTER, False, 0)
        buttons = self.HBox()
        self.Add(result, buttons, 0.0, 30.0, 0.0, 0.0, ALIGN_CENTER, False, 0)
        start_now = self.Sized(self.MakeButton("НАЧАТЬ СЕЙЧАС", STYLE_YELLOW, "startnow", 22), 300.0, 0.0)
        teams_button = self.MakeButton("КОМАНДЫ И НАСТРОЙКИ", STYLE_DARK, "teams", 18)
        reset = self.MakeButton("СБРОСИТЬ МАТЧ", STYLE_DARK, "newmatch", 18)
        new_match = self.Sized(self.MakeButton("НОВЫЙ МАТЧ", STYLE_YELLOW, "newmatch", 24), 320.0, 0.0)
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
            return "НИЗКАЯ"
        if self.State.BotAccuracy >= 1.5:
            return "СРЕДНЯЯ"
        return "ВЫСОКАЯ"

    def FillCard(self, swat: bool, chosen: bool):
        """The rows collected in RowTexts/RowColors, then free slots up to five."""
        rows = self.SwatRows if swat else self.SuspectRows
        texts = self.SwatTexts if swat else self.SuspectTexts
        header = self.SwatHeader if swat else self.SuspectHeader
        if swat:
            header.SetBrushColor(self.Col(0.07, 0.19, 0.5, 1.0) if chosen else self.Col(0.04, 0.1, 0.27, 1.0))
        else:
            header.SetBrushColor(self.Col(0.6, 0.24, 0.03, 1.0) if chosen else self.Col(0.36, 0.13, 0.015, 1.0))
        for i in range(MAX_ROWS):
            if i < len(self.RowTexts):
                texts[i].SetText(Text(self.RowTexts[i]))
                self.Paint(texts[i], self.RowColors[i])
                self.Show(rows[i], True)
            elif i < SLOTS:
                texts[i].SetText(Text("свободно"))
                self.Paint(texts[i], self.Col(0.16, 0.17, 0.19, 1.0))
                self.Show(rows[i], True)
            else:
                self.Show(rows[i], False)
        status = self.SwatStatus if swat else self.SuspectStatus
        status.SetText(Text("ВЫ В ЭТОЙ КОМАНДЕ" if chosen else ""))
        self.Label(self.SwatJoin if swat else self.SuspectJoin, "ВЫ ЗДЕСЬ" if chosen else "ВСТУПИТЬ")

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
            self.Subtitle.SetText(Text(f"Раунд {st.Round} · {self.ScoreLine()} · матч до {st.RoundsToWin} побед"))
        else:
            self.Subtitle.SetText(Text(f"PvP · раунд {st.Minutes} мин · убитый подозреваемый вселяется в живого ИИ-подозреваемого"))
        white = self.Col(1.0, 1.0, 1.0, 1.0)
        for team in [SWAT, SUSPECT]:
            self.RowTexts.clear()
            self.RowColors.clear()
            count = 0
            for pc in players:
                if (self.TeamOf(pc) == SUSPECT) == (team == SUSPECT):
                    count += 1
                    ready = self.HostConfirmed if self.IsHost(pc) else self.StateOf(pc).bReady
                    self.RowTexts.append(self.NameOf(pc) + (" · хост" if self.IsHost(pc) else "") + (" · готов" if ready else ""))
                    self.RowColors.append(white)
            if team == SWAT:
                if st.Bots:
                    for name in ["King", "Swan", "Prescott", "Eli"]:
                        self.RowTexts.append("БОТ  " + name)
                        self.RowColors.append(self.Col(0.22, 0.32, 0.55, 1.0))
                self.SwatCount.SetText(Text(f"{count} / {SLOTS}"))
                self.FillCard(True, host_team != SUSPECT)
            else:
                ai = len(self.LivingAiSuspects())
                self.RowTexts.append(f"ИИ-подозреваемые · {ai}" if ai > 0 else "ИИ-подозреваемые миссии")
                self.RowColors.append(self.Col(0.62, 0.32, 0.1, 1.0))
                self.SuspectCount.SetText(Text(f"{count} / {SLOTS}"))
                self.FillCard(False, host_team == SUSPECT)
        self.Label(self.BotsButton, "БОТЫ SWAT: ВКЛ" if st.Bots else "БОТЫ SWAT: ВЫКЛ")
        self.Label(self.AccuracyButton, "МЕТКОСТЬ: " + self.AccuracyName())
        self.Label(self.MinutesButton, f"РАУНД: {st.Minutes} МИН")
        self.Label(self.RoundsButton, "МАТЧ: 1 РАУНД" if st.RoundsToWin == 1 else f"МАТЧ: ДО {st.RoundsToWin} ПОБЕД")
        self.Label(self.SwapButton, "СМЕНА СТОРОН: ВКЛ" if st.Swap else "СМЕНА СТОРОН: ВЫКЛ")
        self.Label(self.ReadyButton, "ЖДЁМ ОСТАЛЬНЫХ" if self.HostConfirmed else "ГОТОВ")

    def FillResult(self, final: bool, host: ReadyOrNotPlayerController, now: float):
        st = self.State
        swat_won = st.ResultSwatWon
        self.ResTop.SetText(Text("МАТЧ ОКОНЧЕН" if final else f"РАУНД {st.ResultRound}"))
        self.ResWinner.SetText(Text("ПОБЕДА SWAT" if swat_won else "ПОБЕДА ПОДОЗРЕВАЕМЫХ"))
        self.Paint(self.ResWinner, self.Col(0.3, 0.5, 1.0, 1.0) if swat_won else self.Col(1.0, 0.5, 0.12, 1.0))
        self.ResReason.SetText(Text(f"решающий раунд {st.ResultRound}: {st.ResultReason}" if final else st.ResultReason))
        self.ResSwatNumber.SetText(Text(str(st.ResultSwatScore)))
        self.ResSuspectNumber.SetText(Text(str(st.ResultSuspectScore)))
        self.ResSwatBox.SetBrushColor(self.Col(0.07, 0.19, 0.5, 1.0) if swat_won else self.Col(0.04, 0.1, 0.27, 1.0))
        self.ResSuspectBox.SetBrushColor(self.Col(0.36, 0.13, 0.015, 1.0) if swat_won else self.Col(0.6, 0.24, 0.03, 1.0))
        for button in self.RoundButtons:
            self.Show(button, not final)
        self.Show(self.NewMatchButton, final)
        host_team = self.TeamName(self.TeamOf(host))
        if final:
            self.ResNotice.SetText(Text("Победители: " + st.ResultWinners))
            self.ResCountdown.SetText(Text(f"Матч до {st.RoundsToWin} побед. «Новый матч» — снова выбор команд на этой же карте"))
            return
        if st.ResultSwapped:
            self.ResNotice.SetText(Text(f"СМЕНА СТОРОН · теперь вы за {host_team} · {self.ScoreLine()}"))
        else:
            self.ResNotice.SetText(Text(f"Следующий раунд: вы за {host_team} · матч до {st.RoundsToWin} побед"))
        gs = cast(GetGameState(), ReadyOrNotGameState)
        if gs and gs.IsEveryoneReady():
            seconds = max(0, int(gs.TimeTillGameStartCountdown + 0.99))
            self.ResCountdown.SetText(Text(f"Раунд {st.Round} начнётся через {seconds} с"))
        else:
            start = self.BriefedAt if self.BriefedAt >= 0.0 else now
            seconds = max(0, int(start + READY_AFTER - now + 0.99))
            self.ResCountdown.SetText(Text(f"Раунд {st.Round} · автостарт через {seconds} с"))

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
                self.Say(name + " → " + self.TeamName(team))
            st.Teams[name] = team
        elif action == "auto":
            # the side with fewer players; on a tie the suspects (SWAT have the bots when they are on)
            swat = 0
            suspects = 0
            for pc in players:
                if not self.IsHost(pc):
                    if self.TeamOf(pc) == SUSPECT:
                        suspects += 1
                    else:
                        swat += 1
            team = SUSPECT if suspects < swat or (suspects == swat and st.Bots) else SWAT
            if self.TeamOf(host) != team:
                self.Say(name + " → " + self.TeamName(team))
            st.Teams[name] = team
        elif action == "bots":
            st.Bots = not st.Bots
            self.SaveSettings()
            self.Say("PvP: ИИ-отряд SWAT включён" if st.Bots else "PvP: ИИ-отряд SWAT выключен")
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
            self.Say(f"PvP: новый матч до {st.RoundsToWin} побед — выбор команд")
        elif action == "ready":
            if not self.StateOf(host).bReady and self.Screen:
                self.Screen.ToggleReady()
            if not self.HostConfirmed:
                self.HostConfirmed = True
                self.MenuHidden = True
                self.Say(name + " готов: " + self.TeamName(self.TeamOf(host)))
        self.ShowMenu(players, host, self.Now())

    def NextStep(self, steps: List[int], current: int) -> int:
        for i in range(len(steps)):
            if steps[i] == current:
                return steps[(i + 1) % len(steps)]
        return steps[0]
