"""Feasibility probe (docs/modio-pak-research.md, stage 1): an actor the game spawns through ModActorSpawnData
that writes a member, calls a non-BlueprintCallable function (ReadyUp) and writes a property Blueprint may
only read (ReadyOrNotPlayerState.Team). Read back with UE4SS: FindAllOf("BP_PvPProbe_C")."""

from kc import types as T
from kc.blueprint import Blueprint, Expr
from kc.data import actor_spawn_data
from kc.kismet import make

PAK_NAME = "RoNPvPProbe"
FOLDER = "/Game/Mods/RoNPvP"


def build():
    bp = Blueprint(FOLDER + "/BP_PvPProbe", "/Script/Engine.Actor")
    stage = bp.member("ProbeStage", T.INT)
    team_before = bp.member("TeamBefore", T.BYTE)

    f = bp.function("ReceiveBeginPlay", override="/Script/Engine.Actor:ReceiveBeginPlay")
    one = Expr(make("EX_IntConst", Value=1), T.INT)
    f.assign(stage.expr(), one)
    pc = f.call("/Script/Engine.GameplayStatics:GetPlayerController", None,
                [f.self_expr(), Expr(make("EX_IntConst", Value=0), T.INT)])
    valid = f.call("/Script/Engine.KismetSystemLibrary:IsValid", None, [pc])
    skip = f.label()
    f.jump_if_not(valid, skip)
    state = f.member(pc, "PlayerState")
    ron_state = f.local("RonState", T.obj("/Script/ReadyOrNot.ReadyOrNotPlayerState"))
    cast = make("EX_DynamicCast", ClassPtr=bp.package.object("/Script/ReadyOrNot.ReadyOrNotPlayerState"), Target=state.json)
    f.assign(ron_state.expr(), Expr(cast, ron_state.type))
    is_state = f.call("/Script/Engine.KismetSystemLibrary:IsValid", None, [ron_state.expr()])
    f.jump_if_not(is_state, skip)
    team = f.member(ron_state.expr(), "Team")
    f.assign(team_before.expr(), Expr(team.json, T.BYTE))
    f.assign(team, Expr(make("EX_ByteConst", Value=4), team.type))
    f.assign(stage.expr(), Expr(make("EX_IntConst", Value=2), T.INT))
    f.call("/Script/ReadyOrNot.ReadyOrNotPlayerController:ReadyUp", pc, [])
    f.assign(stage.expr(), Expr(make("EX_IntConst", Value=3), T.INT))
    f.mark(skip)
    probe = bp.finish()

    spawn = actor_spawn_data(FOLDER + "/MASD_RoNPvP", [bp.path])
    return [probe, spawn]
