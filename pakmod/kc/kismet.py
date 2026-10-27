"""Kismet bytecode as UAssetAPI JSON: expression constructors, in-memory sizes and jump resolution.

UE 5.3 measures script offsets (jump targets, EX_Context skips, UFunction::Script size) in the layout the
bytecode has in memory after loading, not on disk: object and property references are 8-byte pointers,
FNames are 12-byte FScriptNames, skip and jump offsets are 4 bytes. UAssetAPI recomputes a function's total
size when it writes the asset but keeps the offsets inside expressions as given, so they are computed here.
"""

EXPR = "UAssetAPI.Kismet.Bytecode.Expressions.{0}, UAssetAPI"

PTR = 8           # UObject*, FField*
SCRIPT_NAME = 12  # FScriptName
SKIP = 4          # CodeSkipSizeType / jump offsets


def kind(expr):
    return expr["$type"].split(",")[0].split(".")[-1]


def make(name, **fields):
    expr = {"$type": EXPR.format(name)}
    expr.update(fields)
    return expr


def _string_size(value):
    # EX_StringConst is ANSI with a terminator; non-ASCII text needs EX_UnicodeStringConst
    return len(value.encode("latin-1")) + 1


def size(expr):
    """In-memory size of one expression, its token included."""
    k = kind(expr)
    s = SIZES.get(k)
    if s is None:
        raise NotImplementedError("no size rule for " + k)
    return 1 + s(expr)


def _params(expr):
    return sum(size(p) for p in expr["Parameters"]) + 1  # + EX_EndFunctionParms


def _text(expr):
    value = expr["Value"]
    history = value["TextLiteralType"]
    total = 1  # EBlueprintTextLiteralType
    if history == "Empty":
        return total
    if history == "LocalizedText":
        return total + sum(size(value[k]) for k in ("LocalizedSource", "LocalizedKey", "LocalizedNamespace"))
    if history in ("InvariantText", "LiteralString"):
        return total + size(value["InvariantLiteralString" if history == "InvariantText" else "LiteralString"])
    if history == "StringTableEntry":
        return total + PTR + size(value["StringTableId"]) + size(value["StringTableKey"])
    raise NotImplementedError("text literal " + history)


def _switch(expr):
    total = 2 + SKIP + size(expr["IndexTerm"])
    for case in expr["Cases"]:
        total += size(case["CaseIndexValueTerm"]) + SKIP + size(case["CaseTerm"])
    return total + size(expr["DefaultTerm"])


SIZES = {
    # no operands
    **{k: (lambda e: 0) for k in (
        "EX_Nothing", "EX_EndOfScript", "EX_Self", "EX_NoObject", "EX_True", "EX_False", "EX_IntZero", "EX_IntOne",
        "EX_EndFunctionParms", "EX_EndStructConst", "EX_EndArray", "EX_EndArrayConst", "EX_EndSet", "EX_EndMap",
        "EX_EndSetConst", "EX_EndMapConst", "EX_PopExecutionFlow", "EX_NoInterface", "EX_Breakpoint",
        "EX_Tracepoint", "EX_WireTracepoint", "EX_EndParmValue")},
    # variables
    **{k: (lambda e: PTR) for k in (
        "EX_LocalVariable", "EX_InstanceVariable", "EX_DefaultVariable", "EX_LocalOutVariable",
        "EX_ClassSparseDataVariable", "EX_PropertyConst", "EX_ObjectConst")},
    "EX_Return": lambda e: size(e["ReturnExpression"]),
    "EX_Jump": lambda e: SKIP,
    "EX_JumpIfNot": lambda e: SKIP + size(e["BooleanExpression"]),
    "EX_ComputedJump": lambda e: size(e["CodeOffsetExpression"]),
    "EX_PushExecutionFlow": lambda e: SKIP,
    "EX_PopExecutionFlowIfNot": lambda e: size(e["BooleanExpression"]),
    "EX_SkipOffsetConst": lambda e: SKIP,
    # assignment
    "EX_Let": lambda e: PTR + size(e["Variable"]) + size(e["Expression"]),
    **{k: (lambda e: size(e["VariableExpression"]) + size(e["AssignmentExpression"])) for k in (
        "EX_LetObj", "EX_LetWeakObjPtr", "EX_LetBool", "EX_LetDelegate", "EX_LetMulticastDelegate")},
    "EX_LetValueOnPersistentFrame": lambda e: PTR + size(e["AssignmentExpression"]),
    # calls
    **{k: (lambda e: size(e["ObjectExpression"]) + SKIP + PTR + size(e["ContextExpression"])) for k in (
        "EX_Context", "EX_Context_FailSilent", "EX_ClassContext")},
    "EX_InterfaceContext": lambda e: size(e["InterfaceValue"]),
    **{k: (lambda e: SCRIPT_NAME + _params(e)) for k in ("EX_VirtualFunction", "EX_LocalVirtualFunction")},
    **{k: (lambda e: PTR + _params(e)) for k in ("EX_FinalFunction", "EX_LocalFinalFunction", "EX_CallMath")},
    "EX_CallMulticastDelegate": lambda e: PTR + size(e["Delegate"]) + _params(e),
    # constants
    "EX_IntConst": lambda e: 4,
    "EX_FloatConst": lambda e: 4,
    "EX_DoubleConst": lambda e: 8,
    "EX_Int64Const": lambda e: 8,
    "EX_UInt64Const": lambda e: 8,
    "EX_ByteConst": lambda e: 1,
    "EX_IntConstByte": lambda e: 1,
    "EX_NameConst": lambda e: SCRIPT_NAME,
    "EX_StringConst": lambda e: _string_size(e["Value"]),
    "EX_UnicodeStringConst": lambda e: 2 * (len(e["Value"].encode("utf-16-le")) // 2 + 1),
    "EX_TextConst": _text,
    "EX_SoftObjectConst": lambda e: size(e["Value"]),
    "EX_VectorConst": lambda e: 24,
    "EX_RotationConst": lambda e: 24,
    "EX_TransformConst": lambda e: 80,
    "EX_BitFieldConst": lambda e: PTR + 1,
    "EX_StructConst": lambda e: PTR + 4 + sum(size(v) for v in e["Value"]) + 1,
    "EX_SetArray": lambda e: size(e["AssigningProperty"]) + sum(size(v) for v in e["Elements"]) + 1,
    "EX_ArrayConst": lambda e: PTR + 4 + sum(size(v) for v in e["Elements"]) + 1,
    "EX_SetMap": lambda e: size(e["MapProperty"]) + 4 + sum(size(v) for v in e["Elements"]) + 1,
    "EX_SetSet": lambda e: size(e["SetProperty"]) + 4 + sum(size(v) for v in e["Elements"]) + 1,
    # casts and members
    **{k: (lambda e: PTR + size(e["Target"])) for k in (
        "EX_DynamicCast", "EX_MetaCast", "EX_ObjToInterfaceCast", "EX_CrossInterfaceCast", "EX_InterfaceToObjCast")},
    "EX_PrimitiveCast": lambda e: 1 + size(e["Target"]),
    "EX_StructMemberContext": lambda e: PTR + size(e["StructExpression"]),
    "EX_ArrayGetByRef": lambda e: size(e["ArrayVariable"]) + size(e["ArrayIndex"]),
    "EX_SwitchValue": _switch,
    # delegates
    "EX_InstanceDelegate": lambda e: SCRIPT_NAME,
    "EX_BindDelegate": lambda e: SCRIPT_NAME + size(e["Delegate"]) + size(e["ObjectTerm"]),
    **{k: (lambda e: size(e["Delegate"]) + size(e["DelegateToAdd"])) for k in (
        "EX_AddMulticastDelegate", "EX_RemoveMulticastDelegate")},
    "EX_ClearMulticastDelegate": lambda e: size(e["DelegateToClear"]),
}


def offsets(statements):
    """Start offset of every top-level statement and the total size."""
    result, at = [], 0
    for statement in statements:
        result.append(at)
        at += size(statement)
    return result, at
