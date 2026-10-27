"""Types of Blueprint variables and parameters, and their property definitions (UAssetAPI FProperty JSON).

Element sizes are the game's runtime sizes (FProperty::ElementSize of the shipping build): a serialized size
that is too small would make later properties overlap.
"""

from . import reflect

API = "UAssetAPI.{0}, UAssetAPI"

SIZES = {
    "bool": 1, "byte": 1, "int": 4, "int64": 8, "float": 4, "double": 8, "name": 8, "str": 16, "text": 24,
    "object": 8, "class": 8, "weak": 8, "soft": 40, "softclass": 40, "interface": 16, "array": 16, "map": 80,
    "set": 80, "delegate": 16, "mcdelegate": 16, "enum": 1,
}

SERIALIZED = {
    "bool": "BoolProperty", "byte": "ByteProperty", "int": "IntProperty", "int64": "Int64Property",
    "float": "FloatProperty", "double": "DoubleProperty", "name": "NameProperty", "str": "StrProperty",
    "text": "TextProperty", "object": "ObjectProperty", "class": "ClassProperty", "weak": "WeakObjectProperty",
    "soft": "SoftObjectProperty", "softclass": "SoftClassProperty", "interface": "InterfaceProperty",
    "array": "ArrayProperty", "map": "MapProperty", "set": "SetProperty", "delegate": "DelegateProperty",
    "mcdelegate": "MulticastInlineDelegateProperty", "enum": "EnumProperty", "struct": "StructProperty",
}


class Type:
    """kind: one of SERIALIZED's keys. cls: object/class/weak/soft class path; meta: class property meta class;
    struct, enum: paths; inner: array/set element Type; key, value: map Types; signature: delegate function."""

    def __init__(self, kind, cls=None, meta=None, struct=None, enum=None, inner=None, key=None, value=None,
                 signature=None):
        self.kind, self.cls, self.meta, self.struct, self.enum = kind, cls, meta, struct, enum
        self.inner, self.key, self.value, self.signature = inner, key, value, signature

    def __repr__(self):
        extra = self.cls or self.struct or self.enum or self.signature or ""
        if self.inner:
            extra = repr(self.inner)
        if self.key:
            extra = "%r, %r" % (self.key, self.value)
        return "%s<%s>" % (self.kind, extra) if extra else self.kind

    def __eq__(self, other):
        return isinstance(other, Type) and repr(self) == repr(other)

    def __hash__(self):
        return hash(repr(self))

    @property
    def is_object(self):
        return self.kind in ("object", "class")

    @property
    def size(self):
        if self.kind == "struct":
            return reflect.get(self.struct)["properties_size"]
        if self.kind == "byte" and self.enum:
            return 1
        return SIZES[self.kind]

    def let(self):
        """The EX_Let flavour the Blueprint compiler uses for this type."""
        return {"bool": "EX_LetBool", "object": "EX_LetObj", "class": "EX_LetObj", "weak": "EX_LetWeakObjPtr",
                "delegate": "EX_LetDelegate", "mcdelegate": "EX_LetMulticastDelegate"}.get(self.kind, "EX_Let")

    def definition(self, package, name, flags="CPF_None", object_flags="RF_Public"):
        """FProperty JSON for a variable or parameter of this type."""
        prop = {
            "$type": API.format("FieldTypes.FGenericProperty"),
            "ArrayDim": "TArray", "ElementSize": self.size, "PropertyFlags": flags, "RepIndex": 0,
            "RepNotifyFunc": package.fname("None"), "BlueprintReplicationCondition": "COND_None", "RawValue": None,
            "SerializedType": package.fname(SERIALIZED[self.kind]), "Name": package.fname(name),
            "Flags": object_flags, "MetaDataMap": None,
        }
        k = self.kind

        def typed(cls_name, **fields):
            prop["$type"] = API.format("FieldTypes." + cls_name)
            prop.update(fields)

        if k == "bool":
            typed("FBoolProperty", FieldSize=1, ByteOffset=0, ByteMask=1, FieldMask=255, NativeBool=True, Value=True)
        elif k in ("object", "weak", "soft", "interface"):
            typed("FInterfaceProperty" if k == "interface" else "FObjectProperty",
                  **({"InterfaceClass": package.object(self.cls)} if k == "interface"
                     else {"PropertyClass": package.object(self.cls or "/Script/CoreUObject.Object")}))
        elif k in ("class", "softclass"):
            typed("FClassProperty", PropertyClass=package.object("/Script/CoreUObject.Class"),
                  MetaClass=package.object(self.meta or "/Script/CoreUObject.Object"))
        elif k == "struct":
            typed("FStructProperty", Struct=package.object(self.struct))
        elif k == "byte":
            typed("FByteProperty", Enum=package.object(self.enum) if self.enum else 0)
        elif k == "enum":
            underlying = Type("byte").definition(package, "UnderlyingType")
            typed("FEnumProperty", Enum=package.object(self.enum), UnderlyingProp=underlying)
        elif k in ("array", "set"):
            typed("FArrayProperty" if k == "array" else "FSetProperty",
                  **{("Inner" if k == "array" else "ElementProp"): self.inner.definition(package, name)})
        elif k == "map":
            typed("FMapProperty", KeyProp=self.key.definition(package, name + "_Key"),
                  ValueProp=self.value.definition(package, name))
        elif k in ("delegate", "mcdelegate"):
            typed("FDelegateProperty" if k == "delegate" else "FMulticastInlineDelegateProperty",
                  SignatureFunction=package.object(self.signature))
        return prop


def from_record(record):
    """Type of a property record from the game's reflection."""
    t = record["type"]
    simple = {v: k for k, v in SERIALIZED.items() if k not in ("struct", "enum", "byte", "object", "class",
                                                              "array", "map", "set", "delegate", "mcdelegate")}
    if t in simple:
        return Type(simple[t])
    if t == "ObjectProperty":
        return Type("object", cls=record.get("property_class"))
    if t == "WeakObjectProperty":
        return Type("weak", cls=record.get("property_class"))
    if t == "SoftObjectProperty":
        return Type("soft", cls=record.get("property_class"))
    if t == "ClassProperty":
        return Type("class", cls="/Script/CoreUObject.Class", meta=record.get("meta_class"))
    if t == "SoftClassProperty":
        return Type("softclass", meta=record.get("meta_class"))
    if t == "InterfaceProperty":
        return Type("interface", cls=record.get("interface_class"))
    if t == "StructProperty":
        return Type("struct", struct=record.get("struct"))
    if t == "ByteProperty":
        return Type("byte", enum=record.get("enum"))
    if t == "EnumProperty":
        return Type("enum", enum=record.get("enum"))
    if t == "ArrayProperty":
        return Type("array", inner=from_record(record["inner"]))
    if t == "SetProperty":
        return Type("set", inner=from_record(record.get("inner") or record.get("element")))
    if t == "MapProperty":
        return Type("map", key=from_record(record["key_prop"] if "key_prop" in record else record["key"]),
                    value=from_record(record["value_prop"] if "value_prop" in record else record["value"]))
    if t == "DelegateProperty":
        return Type("delegate", signature=record.get("signature_function"))
    if t == "MulticastInlineDelegateProperty":
        return Type("mcdelegate", signature=record.get("signature_function"))
    raise NotImplementedError("property type " + t)


# shorthands
BOOL, BYTE, INT, INT64, FLOAT, DOUBLE = Type("bool"), Type("byte"), Type("int"), Type("int64"), Type("float"), Type("double")
NAME, STR, TEXT = Type("name"), Type("str"), Type("text")


def obj(cls="/Script/CoreUObject.Object"):
    return Type("object", cls=cls)


def struct(path):
    return Type("struct", struct=path)


def array(inner):
    return Type("array", inner=inner)
