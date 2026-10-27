# kc.lang feasibility probe (read back with UE4SS: FindAllOf("BP_PvPProbe_C")[1].Notes).
# Compiled by pakmod/kc/lang.py into a Blueprint; never run by Python.


@blueprint("/Game/Mods/RoNPvP/BP_PvPProbe")
class PvPProbe(Actor):
    ProbeStage: int = 0
    Notes: List[str]
    Counts: Map[str, int]
    Ticks: int = 0

    def ReceiveBeginPlay(self):
        self.ProbeStage = 1
        pc = GameplayStatics.GetPlayerController(0)
        if IsValid(pc):
            state = cast(pc.PlayerState, ReadyOrNotPlayerState)
            if state:
                self.note(f"team {state.Team} ready {state.bReady}")
        total = 0
        for i in range(5):
            total += i
        self.Counts["a"] = total
        self.Counts["b"] = total * 2
        self.note(f"total {total} counts {len(self.Counts)} b={self.Counts['b']}")
        x = 2.5
        self.note(f"x*2={x * 2:.1f} me={GetObjectName(self)} ok={x > 2 and total == 10}")
        for key in self.Counts:
            self.note("key " + key)
        K2_SetTimer(self, "OnSecond", 1.0, True, 0.0, 0.0)
        self.ProbeStage = 2

    def OnSecond(self):
        self.Ticks += 1
        if self.Ticks == 3:
            self.note("три секунды")
            K2_ClearTimer(self, "OnSecond")
            self.ProbeStage = 3

    def note(self, text: str):
        self.Notes.append(text)
