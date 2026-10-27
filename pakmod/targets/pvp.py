"""The mod.io pak: pakmod/src/pvp.py compiled into Blueprints, its director spawned by ModActorSpawnData."""

import os

from kc.data import actor_spawn_data
from kc.lang import compile_source

PAK_NAME = "RoNPvP"
SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src", "pvp.py")
DIRECTOR = "/Game/Mods/RoNPvP/BP_PvPDirector.BP_PvPDirector_C"


def build():
    blueprints = compile_source(open(SRC, encoding="utf-8").read(), SRC)
    packages = [bp.finish() for bp in blueprints]
    packages.append(actor_spawn_data("/Game/Mods/RoNPvP/MASD_RoNPvP", [DIRECTOR]))
    return packages
