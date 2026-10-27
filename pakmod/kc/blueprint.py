"""A Blueprint class built in code: member variables, functions with locals, statements and jumps.

This is the layer kc.lang compiles to; it follows the shapes the Blueprint compiler gives cooked bytecode:
  * a call with a result assigns it to a temporary: EX_Let(temp, EX_Context(target, call)) or
    EX_Let(temp, EX_CallMath(...)) for static native functions;
  * a member of another object is EX_Context(object, EX_InstanceVariable(property of the declaring class)),
    usable on both sides of an assignment;
  * events (ReceiveBeginPlay, ReceiveTick, ...) are overrides of the native event with their own locals.
"""

from . import kismet, reflect
from .kismet import make
from .types import Type, from_record, BOOL
from .uasset import Package, known, API

FIELD_PATH = API.format("UnrealTypes.FFieldPath")
PROP_POINTER = API.format("Kismet.Bytecode.KismetPropertyPointer")

# static library functions with custom thunks (wildcard parameters): called through the library's CDO
CONTEXT_LIBRARIES = ("/Script/Engine.KismetArrayLibrary", "/Script/Engine.BlueprintSetLibrary",
                     "/Script/Engine.BlueprintMapLibrary")


def prop_pointer(name, owner):
    return {"$type": PROP_POINTER, "New": {"$type": FIELD_PATH, "Path": [name] if name else [],
                                           "ResolvedOwner": owner}}


NULL_PROP = prop_pointer(None, 0)


class Expr:
    """An expression: its UAssetAPI JSON and its type; lvalue when it can be assigned to."""

    def __init__(self, json, type, lvalue=False, prop=None):
        self.json, self.type, self.lvalue = json, type, lvalue
        self.prop = prop  # property pointer of the variable it reads (EX_Context r-value, EX_Let)
        self.literal = None  # the Python value of a constant


class Var:
    def __init__(self, name, type, owner, member):
        self.name, self.type, self.owner, self.member = name, type, owner, member

    def pointer(self):
        return prop_pointer(self.name, self.owner)

    def expr(self):
        token = "EX_InstanceVariable" if self.member else "EX_LocalVariable"
        return Expr(make(token, Variable=self.pointer()), self.type, True, self.pointer())


class Label:
    def __init__(self):
        self.at = None  # statement index


class Function:
    def __init__(self, bp, name, flags, override=None):
        self.bp, self.name, self.override = bp, name, override
        self.index = bp.package.function_export(bp.class_index, name, flags, override)
        self.params = []   # (name, Type, property flags)
        self.locals = {}   # name -> Var
        self.order = []    # property names in definition order (params first)
        self.statements = []
        self.labels = []
        self.temp_count = 0
        self.returns = None

    # ---- variables
    def param(self, name, type, out=False, ret=False, const=False):
        flags = ["CPF_Parm"]
        if out or ret:
            flags.append("CPF_OutParm")
        if ret:
            flags.append("CPF_ReturnParm")
        if const:
            flags.append("CPF_ConstParm")
        if type.kind in ("str", "text", "array", "map", "set", "struct") and not (out or ret):
            pass
        flags.append("CPF_BlueprintVisible" if not ret else "CPF_None")
        self.params.append((name, type, ", ".join(f for f in flags if f != "CPF_None")))
        var = Var(name, type, self.index, False)
        self.locals[name] = var
        self.order.append(name)
        if ret:
            self.returns = var
        return var

    def local(self, name, type):
        if name in self.locals:
            if self.locals[name].type != type:
                raise TypeError("%s.%s: local %s is %r, not %r" % (self.bp.name, self.name, name, self.locals[name].type, type))
            return self.locals[name]
        var = Var(name, type, self.index, False)
        self.locals[name] = var
        self.order.append(name)
        return var

    def temp(self, type, hint="Temp"):
        self.temp_count += 1
        return self.local("%s_%d" % (hint, self.temp_count), type)

    # ---- statements
    def emit(self, statement):
        self.statements.append(statement)

    def label(self):
        label = Label()
        self.labels.append(label)
        return label

    def mark(self, label):
        label.at = len(self.statements)

    def jump(self, label):
        self.emit(make("EX_Jump", CodeOffset=label))

    def jump_if_not(self, condition, label):
        self.emit(make("EX_JumpIfNot", CodeOffset=label, BooleanExpression=condition.json))

    def assign(self, target, value):
        if not target.lvalue:
            raise TypeError("cannot assign to this expression")
        let = target.type.let()
        if let == "EX_Let":
            self.emit(make("EX_Let", Value=target.prop or NULL_PROP, Variable=target.json, Expression=value.json))
        else:
            self.emit(make(let, VariableExpression=target.json, AssignmentExpression=value.json))

    def ret(self):
        self.emit(make("EX_Return", ReturnExpression=make("EX_Nothing")))

    # ---- expressions
    def self_expr(self):
        return Expr(make("EX_Self"), Type("object", cls=self.bp.path))

    def member(self, target, name):
        """target.name: a member variable of our class (target None) or a property of a game object."""
        if target is None or (target.json.get("$type", "").endswith("EX_Self, UAssetAPI")):
            if name in self.bp.members:
                return self.bp.members[name].expr()
            target = self.self_expr()
            owner_struct, record = reflect.find_property(self.bp.super, name)
            pointer = prop_pointer(name, self.bp.package.object(owner_struct))
            return Expr(make("EX_InstanceVariable", Variable=pointer), from_record(record), True, pointer)
        cls = target.type.cls
        if target.type.kind == "struct":
            owner_struct, record = reflect.find_property(target.type.struct, name)
            pointer = prop_pointer(name, self.bp.package.object(owner_struct))
            return Expr(make("EX_StructMemberContext", StructMemberExpression=pointer, StructExpression=target.json),
                        from_record(record), target.lvalue, pointer)
        owner_struct, record = reflect.find_property(cls, name)
        pointer = prop_pointer(name, self.bp.package.object(owner_struct))
        inner = make("EX_InstanceVariable", Variable=pointer)
        return Expr(self.context(target, inner, pointer), from_record(record), True, pointer)

    def context(self, target, inner_json, rvalue):
        return make("EX_Context", ObjectExpression=target.json, Offset=kismet.size(inner_json), PropertyType=0,
                    RValuePointer=rvalue or NULL_PROP, ContextExpression=inner_json)

    def call(self, function, target, args, result=None):
        """Calls a game function or one of our own; returns the result expression (a temporary) or None.

        function: a reflection path (/Script/Engine.Actor:K2_DestroyActor), or the name of one of our functions.
        target: None for static functions and calls on self. args: Exprs for the inputs in order; out
        parameters take lvalue Exprs.
        """
        own = self.bp.functions.get(function) if isinstance(function, str) and ":" not in function else None
        if own is not None:
            params = [(n, t, f) for n, t, f in own.params]
            ret_param = next(((n, t) for n, t, f in params if "CPF_ReturnParm" in f), None)
            inputs = [(n, t, f) for n, t, f in params if "CPF_ReturnParm" not in f]
            call_json = make("EX_LocalFinalFunction", StackNode=own.index,
                             Parameters=self._args(inputs, args, own.name))
            return self._finish_call(call_json, ret_param, None, result)
        flags = reflect.flags(function)
        params = reflect.params(function)
        ret_record = next((p for p in params if "CPF_ReturnParm" in p["flags"]), None)
        inputs = [(p["name"], from_record(p), p["flags"]) for p in params if "CPF_ReturnParm" not in p["flags"]]
        owner = function.split(":")[0]
        parameters = self._args(inputs, args, function)
        if "FUNC_Static" in flags:
            if owner in CONTEXT_LIBRARIES or "FUNC_BlueprintCosmetic" in flags or "FUNC_BlueprintAuthorityOnly" in flags \
                    or "FUNC_Native" not in flags:
                call_json = make("EX_FinalFunction", StackNode=self.bp.package.object(function), Parameters=parameters)
                target = Expr(make("EX_ObjectConst", Value=self.bp.package.object(
                    owner.rsplit(".", 1)[0] + ".Default__" + owner.rsplit(".", 1)[1])), Type("object", cls=owner))
            else:
                call_json = make("EX_CallMath", StackNode=self.bp.package.object(function), Parameters=parameters)
                target = None
        elif "FUNC_Final" in flags:
            call_json = make("EX_FinalFunction", StackNode=self.bp.package.object(function), Parameters=parameters)
        else:
            call_json = make("EX_VirtualFunction", VirtualFunctionName=self.bp.package.fname(function.split(":")[1]),
                             Parameters=parameters)
        ret_param = (ret_record["name"], from_record(ret_record)) if ret_record else None
        return self._finish_call(call_json, ret_param, target, result)

    def _args(self, inputs, args, what):
        if len(args) != len(inputs):
            raise TypeError("%s takes %d arguments (%s), got %d" % (what, len(inputs), ", ".join(n for n, _, _ in inputs), len(args)))
        out = []
        for (name, type, flags), arg in zip(inputs, args):
            if "CPF_OutParm" in flags and not arg.lvalue:
                raise TypeError("%s: argument %s must be a variable (out parameter)" % (what, name))
            out.append(arg.json)
        return out

    def _finish_call(self, call_json, ret_param, target, result):
        if ret_param is None:
            if target is not None and not target.json["$type"].endswith("EX_Self, UAssetAPI"):
                self.emit(self.context(target, call_json, None))
            else:
                self.emit(call_json)
            return None
        dest = result or self.temp(ret_param[1], "Ret").expr()
        value_json = call_json
        if target is not None and not target.json["$type"].endswith("EX_Self, UAssetAPI"):
            value_json = self.context(target, call_json, dest.prop)
        self.assign(dest, Expr(value_json, dest.type))
        return dest

    # ---- output
    def finish(self):
        package = self.bp.package
        export = package.exports[self.index - 1]
        if not self.statements or kismet.kind(self.statements[-1]) != "EX_Return":
            self.ret()
        code = self.statements + [make("EX_EndOfScript")]
        starts, _ = kismet.offsets(self._sized(code))
        for statement in code:
            if isinstance(statement.get("CodeOffset"), Label):
                label = statement["CodeOffset"]
                statement["CodeOffset"] = starts[label.at] if label.at < len(starts) else starts[-1]
        export["ScriptBytecode"] = code
        definitions = []
        for name in self.order:
            var = self.locals[name]
            param = next((p for p in self.params if p[0] == name), None)
            definitions.append(var.type.definition(package, name, param[2] if param else "CPF_None"))
        export["LoadedProperties"] = definitions
        refs = sorted({i for i in _indices(code + definitions) if i != self.index}, key=abs)
        export["CreateBeforeSerializationDependencies"] = refs
        export["CreateBeforeCreateDependencies"] = [self.bp.class_index] + ([package.object(self.override)] if self.override else [])
        export["SerializationBeforeSerializationDependencies"] = [package.object(self.override)] if self.override else []

    @staticmethod
    def _sized(code):
        # labels stand in for 4-byte offsets while sizes are measured
        def clean(x):
            if isinstance(x, dict):
                return {k: (0 if isinstance(v, Label) else clean(v)) for k, v in x.items()}
            if isinstance(x, list):
                return [clean(v) for v in x]
            return x
        return [clean(s) for s in code]


def _indices(x):
    """Every import/export index referenced in bytecode or property definitions."""
    keys = ("StackNode", "Value", "PropertyClass", "MetaClass", "Struct", "Enum", "SignatureFunction", "ClassPtr",
            "InterfaceClass", "ResolvedOwner")
    found = set()

    def walk(v, key=None):
        if isinstance(v, dict):
            t = v.get("$type", "")
            for k, child in v.items():
                if k in keys and isinstance(child, int) and child != 0 and (k != "Value" or "ObjectConst" in t):
                    found.add(child)
                else:
                    walk(child, k)
        elif isinstance(v, list):
            for child in v:
                walk(child, key)
    walk(x)
    return found


class Blueprint:
    def __init__(self, package_path, super_path):
        self.package = Package(package_path)
        self.name = package_path.rsplit("/", 1)[1] + "_C"
        self.path = package_path + "." + self.name
        self.super = super_path
        known(self.path, "/Script/Engine.BlueprintGeneratedClass")
        known(package_path + ".Default__" + self.name, self.path)
        self.class_index = self.package.class_export(self.name, super_path)
        self.members = {}
        self.member_flags = {}
        self.functions = {}

    def member(self, name, type, flags="CPF_Edit, CPF_BlueprintVisible, CPF_DisableEditOnInstance"):
        var = Var(name, type, self.class_index, True)
        self.members[name] = var
        self.member_flags[name] = flags
        return var

    def function(self, name, override=None, flags=None):
        """override: the native event or function this one implements (e.g. /Script/Engine.Actor:ReceiveTick)."""
        if override:
            super_flags = reflect.flags(override)
            flags = flags or ", ".join(f for f in super_flags.split(" | ") if f not in ("FUNC_Native", "FUNC_RequiredAPI"))
        function = Function(self, name, flags or "FUNC_Final, FUNC_Public, FUNC_BlueprintCallable", override)
        self.functions[name] = function
        if override:
            for record in reflect.params(override):
                function.param(record["name"], from_record(record), out="CPF_OutParm" in record["flags"],
                               ret="CPF_ReturnParm" in record["flags"], const="CPF_ConstParm" in record["flags"])
        return function

    def finish(self, cdo_data=None):
        package = self.package
        for function in self.functions.values():
            function.finish()
        cls = package.exports[self.class_index - 1]
        cls["FuncMap"] = [[package.fname(f.name), f.index] for f in sorted(self.functions.values(), key=lambda f: f.name)]
        cls["Children"] = [f.index for f in self.functions.values()]
        cls["LoadedProperties"] = [v.type.definition(package, n, self.member_flags[n], "RF_Public, RF_LoadCompleted")
                                   for n, v in self.members.items()]
        super_cdo = self.super.rsplit(".", 1)[0] + ".Default__" + self.super.rsplit(".", 1)[1]
        cdo = package.object_export("Default__" + self.name, self.path, super_cdo,
                                    "RF_Public, RF_ClassDefaultObject, RF_ArchetypeObject", data=cdo_data)
        cls["ClassDefaultObject"] = cdo
        structs = sorted({i for i in _indices(cls["LoadedProperties"]) if i != self.class_index}, key=abs)
        cls["SerializationBeforeSerializationDependencies"] = [package.object(self.super)] + structs + [package.object(super_cdo)]
        cls["CreateBeforeSerializationDependencies"] = [f.index for f in self.functions.values()]
        cls["SerializationBeforeCreateDependencies"] = [package.object("/Script/Engine.BlueprintGeneratedClass"),
                                                        package.object("/Script/Engine.Default__BlueprintGeneratedClass")]
        cls["CreateBeforeCreateDependencies"] = [package.object(self.super)]
        cdo_export = package.exports[cdo - 1]
        cdo_export["SerializationBeforeCreateDependencies"] = [self.class_index, package.object(super_cdo)]
        return package
