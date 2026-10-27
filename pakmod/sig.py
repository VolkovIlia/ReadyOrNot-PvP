"""Prints the game's signatures for kc.lang sources.

    python pakmod/sig.py ReadyOrNotPlayerController:ReadyUp GameplayStatics:GetAllActorsOfClass RChatMessage
    python pakmod/sig.py "W_StandardButton_C:*Click*"      (wildcards list matching members)
"""

import fnmatch
import sys

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))

from kc import reflect, types as T
from kc.lang import symbols


def describe_type(record):
    try:
        return repr(T.from_record(record))
    except NotImplementedError:
        return record["type"]


def show_function(path):
    params = reflect.params(path)
    inputs = ", ".join("%s%s: %s" % ("out " if "CPF_OutParm" in p["flags"] and "CPF_ReferenceParm" not in p["flags"] else
                                     "ref " if "CPF_ReferenceParm" in p["flags"] else "", p["name"], describe_type(p))
                       for p in params if "CPF_ReturnParm" not in p["flags"])
    ret = next((describe_type(p) for p in params if "CPF_ReturnParm" in p["flags"]), "None")
    flags = [f.replace("FUNC_", "") for f in reflect.flags(path).split(" | ")
             if f in ("FUNC_Static", "FUNC_BlueprintCallable", "FUNC_Net", "FUNC_NetServer", "FUNC_NetClient",
                      "FUNC_NetMulticast", "FUNC_BlueprintEvent", "FUNC_Final", "FUNC_Exec", "FUNC_BlueprintPure")]
    print("  %s(%s) -> %s  [%s]" % (path, inputs, ret, " ".join(flags)))


def show(query):
    owner, _, member = query.partition(":")
    path = owner if owner.startswith("/") else symbols().find(owner)
    if path is None:
        print("? no class", owner)
        return
    if not member:
        obj = reflect.get(path)
        print("%s (%s, parent %s)" % (path, obj["class"].rsplit(".", 1)[1], obj.get("super_struct")))
        for p in obj.get("properties") or []:
            print("  .%s: %s" % (p["name"], describe_type(p)))
        if obj["class"].endswith("Enum"):
            print("  ", obj.get("enum_names"))
        return
    if any(c in member for c in "*?"):
        for cls in reflect.supers(path):
            for key in reflect.DB:
                if key.startswith(cls + ":") and fnmatch.fnmatch(key.split(":", 1)[1].lower(), member.lower()):
                    show_function(key)
            for p in reflect.get(cls).get("properties") or []:
                if fnmatch.fnmatch(p["name"].lower(), member.lower()):
                    print("  %s.%s: %s" % (cls, p["name"], describe_type(p)))
        return
    try:
        show_function(reflect.find_function(path, member))
    except KeyError:
        try:
            cls, record = reflect.find_property(path, member)
            print("  %s.%s: %s  (%s)" % (cls, member, describe_type(record), record["flags"]))
        except KeyError:
            print("? %s has no %s" % (path, member))


if __name__ == "__main__":
    for query in sys.argv[1:]:
        show(query)
