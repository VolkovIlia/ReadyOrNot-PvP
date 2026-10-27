"""The game's reflection (classes, structs, enums, functions, properties) from a JMAP dump of the running game.

The dump (re/dumps/*.jmap, made with UE4SS, not in git) is read once and cached next to it as a pickle.
Paths are UE object paths: "/Script/Engine.Actor", "/Script/Engine.Actor:ReceiveBeginPlay",
"/Game/Blueprints/Widgets/Common/W_StandardButton.W_StandardButton_C".
"""

import glob
import json
import os
import pickle

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DUMPS = os.path.join(ROOT, "re", "dumps")

# object kinds kept from the dump
KEPT = {
    "/Script/CoreUObject.Class", "/Script/CoreUObject.ScriptStruct", "/Script/CoreUObject.Enum",
    "/Script/CoreUObject.Function", "/Script/CoreUObject.DelegateFunction",
    "/Script/CoreUObject.SparseDelegateFunction", "/Script/Engine.BlueprintGeneratedClass",
    "/Script/UMG.WidgetBlueprintGeneratedClass", "/Script/Engine.UserDefinedEnum",
    "/Script/Engine.UserDefinedStruct", "/Script/Engine.AnimBlueprintGeneratedClass",
}


def _load():
    dumps = sorted(glob.glob(os.path.join(DUMPS, "*.jmap")))
    if not dumps:
        raise FileNotFoundError("no JMAP dump in " + DUMPS + " (see docs/development.md)")
    path = dumps[-1]
    cache = path + ".reflect.pkl"
    if os.path.exists(cache) and os.path.getmtime(cache) >= os.path.getmtime(path):
        return pickle.load(open(cache, "rb"))
    objects = json.load(open(path, encoding="utf-8"))["objects"]
    db = {}
    for name, obj in objects.items():
        if obj.get("class") in KEPT:
            db[name] = {k: obj.get(k) for k in (
                "class", "outer", "super_struct", "properties", "function_flags", "class_flags",
                "properties_size", "class_default_object", "names", "children")}
            if obj.get("class") in ("/Script/CoreUObject.Enum", "/Script/Engine.UserDefinedEnum"):
                db[name]["enum_names"] = obj.get("names") or obj.get("enum_names")
    pickle.dump(db, open(cache, "wb"))
    return db


DB = _load()


def get(path):
    obj = DB.get(path)
    if obj is None:
        raise KeyError("not in the game's reflection: " + path)
    return obj


def exists(path):
    return path in DB


def kind(path):
    """Class of the object: /Script/CoreUObject.Class, .../BlueprintGeneratedClass, ScriptStruct, Function..."""
    return get(path)["class"]


def supers(path):
    """The struct and its ancestors, nearest first."""
    while path:
        yield path
        path = get(path).get("super_struct")


def is_child_of(path, ancestor):
    return ancestor in supers(path)


def find_property(struct, name):
    """(declaring struct, property record) for a member property, looking through the ancestors."""
    for owner in supers(struct):
        for prop in get(owner).get("properties") or []:
            if prop["name"] == name:
                return owner, prop
    raise KeyError("%s has no property %s" % (struct, name))


def find_function(cls, name):
    """Path of a function callable on the class, looking through the ancestors."""
    for owner in supers(cls):
        path = owner + ":" + name
        if path in DB:
            return path
    raise KeyError("%s has no function %s" % (cls, name))


def params(function):
    """Parameter records of a function in declaration order (the return value is the one with CPF_ReturnParm)."""
    return [p for p in get(function).get("properties") or [] if "CPF_Parm" in p["flags"]]


def flags(function):
    return get(function).get("function_flags") or ""
