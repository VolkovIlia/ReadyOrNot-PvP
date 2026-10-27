"""kc.lang probe: pakmod/src/probe.py compiled to a Blueprint and spawned through ModActorSpawnData."""

import os

from kc.data import actor_spawn_data
from kc.lang import compile_source

PAK_NAME = "RoNPvPProbe"
SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src", "probe.py")


def build():
    blueprints = compile_source(open(SRC, encoding="utf-8").read(), SRC)
    packages = [bp.finish() for bp in blueprints]
    packages.append(actor_spawn_data("/Game/Mods/RoNPvP/MASD_RoNPvP", [bp.path for bp in blueprints]))
    return packages
