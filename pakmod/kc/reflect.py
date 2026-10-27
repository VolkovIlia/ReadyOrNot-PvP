"""The game's reflection (classes, structs, enums, functions, properties) from JMAP dumps of the running game.

The dumps (re/dumps/**/*.jmap, made with UE4SS, not in git) only hold what was loaded when they were taken, so all of
them are merged, a newer dump winning; the result is read once and cached as re/dumps/merged.reflect.pkl.
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
    dumps = sorted(glob.glob(os.path.join(DUMPS, "**", "*.jmap"), recursive=True), key=os.path.getmtime)
    if not dumps:
        raise FileNotFoundError("no JMAP dump in " + DUMPS + " (see docs/development.md)")
    cache = os.path.join(DUMPS, "merged.reflect.pkl")
    if os.path.exists(cache):
        cached = pickle.load(open(cache, "rb"))
        if cached.get("dumps") == [(p, os.path.getmtime(p)) for p in dumps]:
            return cached["db"]
    db = {}
    for path in dumps:  # oldest first: a newer dump overwrites what both have
        objects = json.load(open(path, encoding="utf-8"))["objects"]
        for name, obj in objects.items():
            if obj.get("class") in KEPT:
                db[name] = {k: obj.get(k) for k in (
                    "class", "outer", "super_struct", "properties", "function_flags", "class_flags",
                    "properties_size", "class_default_object", "names", "children")}
                if obj.get("class") in ("/Script/CoreUObject.Enum", "/Script/Engine.UserDefinedEnum"):
                    db[name]["enum_names"] = obj.get("names") or obj.get("enum_names")
        del objects
    pickle.dump({"dumps": [(p, os.path.getmtime(p)) for p in dumps], "db": db}, open(cache, "wb"))
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
