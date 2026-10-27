"""Data assets of the game's mod support (ReadyOrNot module): ModActorSpawnData and friends."""

from .uasset import Package, API

PROPS = "UAssetAPI.PropertyTypes.Objects.{0}, UAssetAPI"


def _property(kind, name, value, **extra):
    data = {"$type": PROPS.format(kind), "Name": name, "ArrayIndex": 0, "PropertyGuid": None, "IsZero": False,
            "PropertyTagFlags": "None", "PropertyTypeName": None, "PropertyTagExtensions": "NoExtension"}
    data.update(extra)
    data["Value"] = value
    return data


def actor_spawn_data(package_path, classes):
    """A ModActorSpawnData asset: the game spawns one actor of each class on every map load
    (UModActorSpawnSubsystem::OnWorldBeginPlay, docs/modio-pak-research.md)."""
    package = Package(package_path)
    elements = [_property("ObjectPropertyData", str(i), package.object(path)) for i, path in enumerate(classes)]
    data = [_property("ArrayPropertyData", package.fname("BlueprintsToSpawn"), elements, ArrayType="ObjectProperty")]
    index = package.object_export(package.short, "/Script/ReadyOrNot.ModActorSpawnData",
                                  "/Script/ReadyOrNot.Default__ModActorSpawnData",
                                  "RF_Public, RF_Standalone, RF_Transactional", is_asset=True, extras="", data=data)
    export = package.exports[index - 1]
    export["SerializationBeforeCreateDependencies"] = [package.object("/Script/ReadyOrNot.ModActorSpawnData"),
                                                       package.object("/Script/ReadyOrNot.Default__ModActorSpawnData")]
    export["CreateBeforeSerializationDependencies"] = [package.object(path) for path in classes]
    return package
