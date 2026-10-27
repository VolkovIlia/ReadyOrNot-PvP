"""Builds the mod's .pak: Python/kc sources -> UAssetAPI JSON -> .uasset/.uexp (UAssetGUI) -> .pak (repak).

    python pakmod/build.py probe [--deploy]

Targets are modules in pakmod/targets with a build(out_dir) function returning the packages.
--deploy copies the .pak into the game's Content/Paks/~mods for testing.
"""

import argparse
import importlib
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

UASSETGUI = os.path.join(ROOT, "tools", "bin", "uassetgui", "UAssetGUI.exe")
REPAK = os.path.join(ROOT, "tools", "bin", "repak", "repak.exe")
GAME = r"C:\Program Files (x86)\Steam\steamapps\common\Ready Or Not"
MAPPINGS = "RoN"  # %LOCALAPPDATA%\UAssetGUI\Mappings\RoN.usmap (re/dumps/*.usmap)


def run(*args):
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0 or "Exception" in (result.stdout + result.stderr):
        raise RuntimeError("%s failed:\n%s\n%s" % (os.path.basename(args[0]), result.stdout, result.stderr))
    return result.stdout


def cook(packages, out):
    """Writes each package as JSON, converts it to .uasset/.uexp and checks that UAssetAPI reads it back."""
    work = os.path.join(out, "json")
    content = os.path.join(out, "pak", "ReadyOrNot", "Content")
    for package in packages:
        json_path = package.save(work)
        relative = package.path[len("/Game/"):].replace("/", os.sep)
        target = os.path.join(content, relative + ".uasset")
        os.makedirs(os.path.dirname(target), exist_ok=True)
        run(UASSETGUI, "fromjson", json_path, target, MAPPINGS)
        back = os.path.join(work, package.short + ".back.json")
        run(UASSETGUI, "tojson", target, back, "VER_UE5_3", MAPPINGS)
        check = json.load(open(back, encoding="utf-8-sig"))
        if len(check["Exports"]) != len(package.exports):
            raise RuntimeError("%s did not read back" % package.path)
        print("  cooked", package.path)
    return os.path.join(out, "pak")


def pack(folder, pak_path):
    if os.path.exists(pak_path):
        os.remove(pak_path)
    run(REPAK, "pack", "--version", "V11", "--mount-point", "../../../", folder, pak_path)
    print("  packed", pak_path, os.path.getsize(pak_path), "bytes")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("target")
    parser.add_argument("--deploy", action="store_true")
    args = parser.parse_args()
    target = importlib.import_module("targets." + args.target)
    out = os.path.join(ROOT, "build", "pakmod", args.target)
    if os.path.exists(out):
        shutil.rmtree(out)
    packages = target.build()
    folder = cook(packages, out)
    pak_path = os.path.join(out, target.PAK_NAME + ".pak")
    pack(folder, pak_path)
    if args.deploy:
        mods = os.path.join(GAME, "ReadyOrNot", "Content", "Paks", "~mods")
        os.makedirs(mods, exist_ok=True)
        shutil.copy2(pak_path, mods)
        print("  deployed to", mods)


if __name__ == "__main__":
    main()
