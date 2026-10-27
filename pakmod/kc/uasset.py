"""One cooked UE 5.3 package (.uasset/.uexp) as UAssetAPI JSON: name map, imports, exports.

Objects are referred to by their UE path; package.object(path) returns the import (negative) or export
(positive) index, creating the import and its outers on first use. Classes and other objects of the game
are looked up in the game's reflection; objects of other packages of the mod are declared with known().
"""

import base64
import json
import os
import struct as binary
import uuid
import zlib

from . import reflect

API = "UAssetAPI.{0}, UAssetAPI"
HEADER = json.load(open(os.path.join(os.path.dirname(__file__), "header.json")))

# kinds of objects outside the reflection dump
KNOWN = {}


def known(path, kind):
    """Declares an object of another package of the mod (e.g. its Blueprint class) for imports."""
    KNOWN[path] = kind


def object_kind(path):
    if path in KNOWN:
        return KNOWN[path]
    return reflect.kind(path)


def split(path):
    """('/Script/Engine', 'Actor', None) for a top-level object, (outer path, name, ':') for a member."""
    if ":" in path:
        outer, name = path.rsplit(":", 1)
        return outer, name, ":"
    if "." in path.rsplit("/", 1)[-1]:
        outer, name = path.rsplit(".", 1)
        return outer, name, "."
    return None, path, None


def _export(kind, name, class_index, super_index, outer, template, flags, is_asset=False, extras=""):
    return {
        "$type": API.format("ExportTypes." + kind), "ObjectGuid": None, "SerializationControl": "NoExtension",
        "Operation": "None", "HasLeadingFourNullBytes": False, "ObjectName": name, "OuterIndex": outer,
        "ClassIndex": class_index, "SuperIndex": super_index, "TemplateIndex": template, "ObjectFlags": flags,
        "SerialSize": 0, "SerialOffset": 0, "ScriptSerializationStartOffset": 0, "ScriptSerializationEndOffset": 0,
        "bForcedExport": False, "bNotForClient": False, "bNotForServer": False,
        "PackageGuid": "{00000000-0000-0000-0000-000000000000}", "IsInheritedInstance": False,
        "PackageFlags": "PKG_None", "bNotAlwaysLoadedForEditorGame": is_asset, "bIsAsset": is_asset,
        "GeneratePublicHash": False, "SerializationBeforeSerializationDependencies": [],
        "CreateBeforeSerializationDependencies": [], "SerializationBeforeCreateDependencies": [],
        "CreateBeforeCreateDependencies": [], "Extras": extras,
    }


class Package:
    def __init__(self, path):
        self.path = path                      # /Game/Mods/RoNPvP/BP_PvPDirector
        self.short = path.rsplit("/", 1)[1]
        self.names = {"None"}
        self.imports = []
        self.exports = []
        self.index = {}                       # object path -> index
        self.class_tags = []                  # class exports whose tag map needs the final name map

    # ---- names and objects
    def fname(self, value):
        self.names.add(value)
        return value

    def object(self, path):
        if path in self.index:
            return self.index[path]
        outer, name, sep = split(path)
        if outer is None:  # a package
            return self._import(path, name, "/Script/CoreUObject", "Package", 0)
        if name.startswith("Default__"):
            class_path = outer + "." + name[len("Default__"):]
            class_package, class_name = class_path.rsplit(".", 1)
            return self._import(path, name, class_package, class_name, self.object(outer))
        kind_package, kind_name = object_kind(path).rsplit(".", 1)
        return self._import(path, name, kind_package, kind_name, self.object(outer))

    def _import(self, path, name, class_package, class_name, outer):
        for value in (name, class_package, class_name):
            self.fname(value)
        self.imports.append({"$type": API.format("Import"), "ObjectName": name, "OuterIndex": outer,
                             "ClassPackage": class_package, "ClassName": class_name, "PackageName": None,
                             "bImportOptional": False})
        self.index[path] = -len(self.imports)
        return self.index[path]

    def add(self, path, export):
        self.fname(export["ObjectName"])
        self.exports.append(export)
        self.index[path] = len(self.exports)
        return self.index[path]

    # ---- exports
    def class_export(self, name, super_path, kind="/Script/Engine.BlueprintGeneratedClass"):
        """A Blueprint class; functions, properties and the CDO are filled in by kc.blueprint."""
        kind_package, kind_name = kind.rsplit(".", 1)
        export = _export("ClassExport", name, self.object(kind), self.object(super_path), 0,
                         self.object(kind_package + ".Default__" + kind_name), "RF_Public, RF_Transactional", True)
        export.update({
            "FuncMap": [], "ClassFlags": "CLASS_ReplicationDataIsSetUp, CLASS_CompiledFromBlueprint",
            "ClassWithin": self.object("/Script/CoreUObject.Object"), "ClassConfigName": self.fname("Engine"),
            "Interfaces": [], "ClassGeneratedBy": 0, "bDeprecatedForceScriptOrder": False, "bCooked": True,
            "ClassDefaultObject": 0, "SuperStruct": self.object(super_path), "Children": [], "LoadedProperties": [],
            "ScriptBytecode": [], "ScriptBytecodeSize": 0, "ScriptBytecodeRaw": None,
            "Field": {"$type": API.format("FieldTypes.UField"), "Next": None}, "Data": [],
        })
        self.fname("BlueprintType")
        self.class_tags.append(export)
        return self.add(self.path + "." + name, export)

    def function_export(self, owner, name, flags, super_function=None):
        export = _export("FunctionExport", name, self.object("/Script/CoreUObject.Function"),
                         self.object(super_function) if super_function else 0, owner,
                         self.object("/Script/CoreUObject.Default__Function"), "RF_Public", extras="AAAAAAAAAAA=")
        export.update({
            "FunctionFlags": flags, "SuperStruct": export["SuperIndex"], "Children": [], "LoadedProperties": [],
            "ScriptBytecode": [], "ScriptBytecodeSize": 0, "ScriptBytecodeRaw": None,
            "Field": {"$type": API.format("FieldTypes.UField"), "Next": None}, "Data": [],
        })
        owner_path = next(p for p, i in self.index.items() if i == owner)
        return self.add(owner_path + ":" + name, export)

    def object_export(self, name, class_path, template_path, flags, outer=0, is_asset=False, extras="AAAAAA==",
                      data=None):
        export = _export("NormalExport", name, self.object(class_path), 0, outer, self.object(template_path),
                         flags, is_asset, extras)
        export["Data"] = data or []
        outer_path = self.path if outer == 0 else next(p for p, i in self.index.items() if i == outer)
        return self.add(outer_path + ("." if outer == 0 else ":") + name, export)

    # ---- output
    NAME_FIELDS = ("ObjectName", "ClassPackage", "ClassName", "SerializedType", "Name", "VirtualFunctionName",
                   "FunctionName", "RepNotifyFunc", "ArrayType", "StructType", "ClassConfigName", "Value")

    def _collect_names(self, node):
        """Every FName the JSON uses must be in the name map: property pointers, property and type names."""
        if isinstance(node, dict):
            t = node.get("$type", "")
            for key, value in node.items():
                if key == "Path" and t.startswith(API.format("UnrealTypes.FFieldPath")[:-11]) and isinstance(value, list):
                    self.names.update(value)
                elif key in self.NAME_FIELDS and isinstance(value, str) and (key != "Value" or "NameConst" in t or "NamePropertyData" in t):
                    self.names.add(value)
                else:
                    self._collect_names(value)
        elif isinstance(node, list):
            for value in node:
                if isinstance(value, list) and len(value) == 2 and isinstance(value[0], str):  # FuncMap entry
                    self.names.add(value[0])
                else:
                    self._collect_names(value)

    def to_json(self):
        self._collect_names(self.exports)
        self._collect_names(self.imports)
        # "Ret_1" is the name "Ret" with number 2 (FName splits a numeric suffix), so the base goes in the map
        for name in list(self.names):
            base, _, number = name.rpartition("_")
            if base and number.isdigit() and (number == "0" or not number.startswith("0")):
                self.names.add(base)
        names = sorted(self.names, key=lambda n: (n.lower(), n))
        for export in self.class_tags:
            # the class's cooked tag map: {"BlueprintType": "BPTYPE_Normal"}
            tags = binary.pack("<iii", 1, names.index("BlueprintType"), 0)
            value = b"BPTYPE_Normal\x00"
            export["Extras"] = base64.b64encode(tags + binary.pack("<i", len(value)) + value).decode()
        asset = dict(HEADER)
        guid = uuid.UUID(int=zlib.crc32(self.path.encode()) * (2 ** 96) + 0x5EED)
        asset.update({
            "$type": API.format("UAsset"), "NameMap": names, "Imports": self.imports, "Exports": self.exports,
            "DependsMap": [[] for _ in self.exports],
            "Generations": [{"$type": API.format("FGenerationInfo"), "ExportCount": len(self.exports),
                             "NameCount": len(names)}],
            "PackageGuid": "{%s}" % str(guid).upper(), "FolderName": self.path, "PackageSource": zlib.crc32(self.path.encode()),
            "NamesReferencedFromExportDataCount": len(names), "SoftObjectPathsOffset": 0,
            "PackageFlags": "PKG_Cooked, PKG_UnversionedProperties, PKG_FilterEditorOnly",
        })
        return asset

    def save(self, folder):
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, self.short + ".json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_json(), f, indent=1, ensure_ascii=False)
        return path
