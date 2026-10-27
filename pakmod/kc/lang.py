"""kc.lang: compiles mod logic written in a Python-syntax subset into Blueprint classes (kc.blueprint).

The source is parsed with Python's ast module and never run. A module holds Blueprint classes:

    @blueprint("/Game/Mods/RoNPvP/BP_PvPDirector")
    class PvPDirector(Actor):
        Phase: int = 0                        # member variable (initialised at the start of ReceiveBeginPlay)
        Teams: Map[str, int]

        def ReceiveBeginPlay(self):           # an override of the parent's event: parameters come from it
            pc = GameplayStatics.GetPlayerController(0)      # WorldContextObject is filled in with self
            if IsValid(pc):
                pc.ReadyUp()                  # any function or property of the game, BlueprintCallable or not

        def Score(self, team: int) -> str:    # own function: annotated parameters and result
            return f"team {team}"

Names resolve against the game's reflection (classes, structs, enums, library functions). Module-level
NAME = "/Game/...Class_C" strings declare aliases for Blueprint classes; other module constants are inlined.
Types: int, float (double), bool, byte, str, Name, Text, a class (object reference), Class[X], a struct,
an enum, List[T], Map[K, V], Set[T].
"""

import ast
import collections

from . import kismet, reflect
from . import types as T
from .blueprint import Blueprint, Expr, Var, prop_pointer, NULL_PROP
from .kismet import make


class CompileError(Exception):
    pass


# ---------------------------------------------------------------- game symbols

PRIORITY = ["/Script/CoreUObject", "/Script/Engine", "/Script/UMG", "/Script/SlateCore", "/Script/ReadyOrNot",
            "/Script/AIModule", "/Script/GameplayTags"]
CLASS_KINDS = {"/Script/CoreUObject.Class", "/Script/Engine.BlueprintGeneratedClass",
               "/Script/UMG.WidgetBlueprintGeneratedClass", "/Script/Engine.AnimBlueprintGeneratedClass"}
STRUCT_KINDS = {"/Script/CoreUObject.ScriptStruct", "/Script/Engine.UserDefinedStruct"}
ENUM_KINDS = {"/Script/CoreUObject.Enum", "/Script/Engine.UserDefinedEnum"}

# free functions are looked up in these libraries, in order
LIBRARIES = ["/Script/Engine.KismetSystemLibrary", "/Script/Engine.KismetMathLibrary",
             "/Script/Engine.KismetStringLibrary", "/Script/Engine.KismetTextLibrary",
             "/Script/Engine.GameplayStatics", "/Script/UMG.WidgetBlueprintLibrary",
             "/Script/Engine.KismetInputLibrary", "/Script/ReadyOrNot.BpGameplayHelperLib",
             "/Script/ReadyOrNot.ReadyOrNotFunctionLibrary"]


def _rank(path):
    package = path.split(".")[0]
    return PRIORITY.index(package) if package in PRIORITY else len(PRIORITY) + (0 if package.startswith("/Script/") else 1)


class Symbols:
    def __init__(self):
        index = collections.defaultdict(list)
        for path, obj in reflect.DB.items():
            if ":" in path:
                continue
            kind = obj["class"]
            if kind in CLASS_KINDS or kind in STRUCT_KINDS or kind in ENUM_KINDS:
                short = path.rsplit(".", 1)[1]
                index[short].append(path)
                if short.endswith("_C"):
                    index[short[:-2]].append(path)
        self.index = {name: sorted(paths, key=_rank) for name, paths in index.items()}
        self.aliases = {}

    def find(self, name):
        if name in self.aliases:
            return self.aliases[name]
        paths = self.index.get(name)
        return paths[0] if paths else None


SYMBOLS = None


def symbols():
    global SYMBOLS
    if SYMBOLS is None:
        SYMBOLS = Symbols()
    return SYMBOLS


def kind_of(path):
    from .uasset import KNOWN
    return KNOWN.get(path) or reflect.kind(path)


# ---------------------------------------------------------------- the compiler

def const(token, value, type, literal=None):
    e = Expr(make(token, Value=value) if value is not None else make(token), type)
    e.literal = literal
    return e


def is_self(expr):
    return expr.json["$type"].endswith("EX_Self, UAssetAPI")


def as_byte(value):
    """A 1-byte enum value (EnumProperty) behaves as a byte in arithmetic, comparisons and conversions."""
    if value.type is not None and value.type.kind == "enum":
        e = Expr(value.json, T.Type("byte", enum=value.type.enum), value.lvalue, value.prop)
        e.literal = value.literal
        return e
    return value


class Module:
    """Compiles one source module into Blueprints."""

    def __init__(self, source, filename="<mod>"):
        self.tree = ast.parse(source, filename)
        self.filename = filename
        self.constants = {}
        self.classes = []
        for node in self.tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                value = node.value
                if isinstance(value, ast.Constant) and isinstance(value.value, str) and value.value.startswith("/Game/"):
                    symbols().aliases[node.targets[0].id] = value.value
                else:
                    self.constants[node.targets[0].id] = value
            elif isinstance(node, ast.ClassDef):
                self.classes.append(node)
            elif isinstance(node, (ast.Import, ast.ImportFrom, ast.Expr)):
                pass
            else:
                raise self.error(node, "only constants and classes at module level")

    def error(self, node, message):
        return CompileError("%s:%d: %s" % (self.filename, getattr(node, "lineno", 0), message))

    def compile(self):
        blueprints = []
        for node in self.classes:
            blueprints.append(ClassCompiler(self, node).compile())
        return blueprints


class ClassCompiler:
    def __init__(self, module, node):
        self.module, self.node = module, node
        decorator = next((d for d in node.decorator_list if isinstance(d, ast.Call) and getattr(d.func, "id", "") == "blueprint"), None)
        if decorator is None:
            raise module.error(node, "class needs @blueprint(\"/Game/...\")")
        self.package_path = decorator.args[0].value
        if len(node.bases) != 1:
            raise module.error(node, "class needs one parent class")
        self.super = self.resolve_class(node.bases[0])
        self.bp = Blueprint(self.package_path, self.super)
        symbols().aliases[node.name] = self.bp.path
        self.defaults = []

    def resolve_class(self, node):
        name = node.id if isinstance(node, ast.Name) else None
        path = symbols().find(name) if name else None
        if not path:
            raise self.module.error(node, "unknown class %s" % ast.unparse(node))
        return path

    def type_of(self, node):
        """Type from an annotation."""
        if isinstance(node, ast.Constant) and node.value is None:
            return None
        if isinstance(node, ast.Name):
            simple = {"int": T.INT, "float": T.DOUBLE, "bool": T.BOOL, "byte": T.BYTE, "str": T.STR,
                      "Name": T.NAME, "Text": T.TEXT, "int64": T.INT64, "float32": T.FLOAT}
            if node.id in simple:
                return simple[node.id]
            path = symbols().find(node.id)
            if path is None:
                raise self.module.error(node, "unknown type %s" % node.id)
            kind = kind_of(path)
            if kind in STRUCT_KINDS:
                return T.struct(path)
            if kind in ENUM_KINDS:
                return T.Type("byte", enum=path)
            return T.obj(path)
        if isinstance(node, ast.Subscript):
            outer = node.value.id
            args = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
            if outer in ("List", "Array"):
                return T.array(self.type_of(args[0]))
            if outer == "Set":
                return T.Type("set", inner=self.type_of(args[0]))
            if outer == "Map":
                return T.Type("map", key=self.type_of(args[0]), value=self.type_of(args[1]))
            if outer == "Class":
                return T.Type("class", cls="/Script/CoreUObject.Class", meta=self.type_of(args[0]).cls)
            if outer == "Weak":
                return T.Type("weak", cls=self.type_of(args[0]).cls)
        raise self.module.error(node, "unsupported type %s" % ast.unparse(node))

    def compile(self):
        functions = []
        for item in self.node.body:
            if isinstance(item, ast.AnnAssign):
                name = item.target.id
                self.bp.member(name, self.type_of(item.annotation))
                if item.value is not None:
                    self.defaults.append((name, item.value))
            elif isinstance(item, ast.FunctionDef):
                functions.append(item)
            elif isinstance(item, (ast.Pass, ast.Expr)):
                pass
            else:
                raise self.module.error(item, "unsupported class member")
        # signatures first, so functions can call each other in any order
        compilers = []
        for item in functions:
            override = None
            try:
                candidate = reflect.find_function(self.super, item.name)
                if "FUNC_BlueprintEvent" in reflect.flags(candidate):
                    override = candidate
            except KeyError:
                pass
            function = self.bp.function(item.name, override=override)
            if not override:
                for arg in item.args.args[1:]:
                    if arg.annotation is None:
                        raise self.module.error(arg, "parameter %s needs a type" % arg.arg)
                    function.param(arg.arg, self.type_of(arg.annotation))
                result = self.type_of(item.returns) if item.returns is not None else None
                if result is not None:
                    function.param("ReturnValue", result, ret=True)
            compilers.append(FunctionCompiler(self, item, function))
        if self.defaults and "ReceiveBeginPlay" not in self.bp.functions:
            function = self.bp.function("ReceiveBeginPlay", override=reflect.find_function(self.super, "ReceiveBeginPlay"))
            compilers.append(FunctionCompiler(self, None, function))
        for compiler in compilers:
            compiler.compile()
        return self.bp


class Loop:
    def __init__(self, top, end):
        self.top, self.end = top, end


class FunctionCompiler:
    def __init__(self, cls, node, function):
        self.cls, self.node, self.f = cls, node, function
        self.bp = cls.bp
        self.loops = []
        self.vars = dict(function.locals)  # params

    def error(self, node, message):
        return self.cls.module.error(node, "%s.%s: %s" % (self.bp.name, self.f.name, message))

    # ---------------------------------------------------------------- statements
    def compile(self):
        if self.f.name == "ReceiveBeginPlay":
            for name, value in self.cls.defaults:
                target = self.bp.members[name].expr()
                self.f.assign(target, self.coerce(self.expr(value), target.type, value))
        if self.node is not None:
            for statement in self.node.body:
                self.statement(statement)

    def block(self, statements):
        for statement in statements:
            self.statement(statement)

    def statement(self, node):
        method = getattr(self, "s_" + type(node).__name__, None)
        if method is None:
            raise self.error(node, "unsupported statement %s" % type(node).__name__)
        method(node)

    def s_Pass(self, node):
        pass

    def s_Expr(self, node):
        if isinstance(node.value, ast.Constant):  # docstring
            return
        self.expr(node.value, statement=True)

    def s_AnnAssign(self, node):
        type = self.cls.type_of(node.annotation)
        var = self.declare(node.target, type)
        if node.value is not None:
            self.f.assign(var.expr(), self.coerce(self.expr(node.value, want=type), type, node.value))

    def s_Assign(self, node):
        if len(node.targets) != 1:
            raise self.error(node, "one target per assignment")
        target = node.targets[0]
        if isinstance(target, ast.Tuple):
            values = self.expr(node.value, multi=True)
            if not isinstance(values, tuple) or len(values) != len(target.elts):
                raise self.error(node, "cannot unpack")
            for t, v in zip(target.elts, values):
                self.assign_to(t, v, node)
            return
        want = None
        if isinstance(target, ast.Name) and target.id in self.vars:
            want = self.vars[target.id].type
        self.assign_to(target, self.expr(node.value, want=want), node.value)

    def assign_to(self, target, value, source):
        if isinstance(target, ast.Name):
            if target.id == "_":
                return
            if target.id not in self.vars:
                if value.type is None:
                    raise self.error(source, "cannot infer the type of %s" % target.id)
                self.declare(target, value.type)
            var = self.vars[target.id]
            self.f.assign(var.expr(), self.coerce(value, var.type, source))
        elif isinstance(target, ast.Attribute):
            lhs = self.attribute(target)
            self.f.assign(lhs, self.coerce(value, lhs.type, source))
        elif isinstance(target, ast.Subscript):
            container = self.expr(target.value)
            key = self.expr(target.slice)
            if container.type.kind == "array":
                self.call_lib("/Script/Engine.KismetArrayLibrary:Array_Set",
                              [container, self.coerce(key, T.INT, target), self.coerce(value, container.type.inner, source),
                               const("EX_False", None, T.BOOL)], types=[container.type, T.INT, container.type.inner, T.BOOL])
            elif container.type.kind == "map":
                self.call_lib("/Script/Engine.BlueprintMapLibrary:Map_Add",
                              [container, self.coerce(key, container.type.key, target), self.coerce(value, container.type.value, source)],
                              types=[container.type, container.type.key, container.type.value])
            else:
                raise self.error(target, "cannot index %r" % container.type)
        else:
            raise self.error(target, "cannot assign to this")

    def declare(self, target, type):
        name = target.id if isinstance(target, ast.Name) else None
        if name is None:
            raise self.error(target, "declare a local by name")
        if name in self.vars:
            if self.vars[name].type != type:
                raise self.error(target, "%s is already %r" % (name, self.vars[name].type))
            return self.vars[name]
        if name in self.bp.members:
            raise self.error(target, "%s is a member: use self.%s" % (name, name))
        var = self.f.local(name, type)
        self.vars[name] = var
        return var

    def s_AugAssign(self, node):
        binop = ast.BinOp(left=node.target, op=node.op, right=node.value)
        ast.copy_location(binop, node)
        load = ast.parse(ast.unparse(node.target), mode="eval").body
        binop.left = load
        ast.fix_missing_locations(binop)
        self.assign_to(node.target, self.expr(binop), node)

    def s_If(self, node):
        cond = self.condition(node.test)
        else_label, end = self.f.label(), self.f.label()
        self.f.jump_if_not(cond, else_label)
        self.block(node.body)
        if node.orelse:
            self.f.jump(end)
        self.f.mark(else_label)
        self.block(node.orelse)
        self.f.mark(end)

    def s_While(self, node):
        top, end = self.f.label(), self.f.label()
        self.f.mark(top)
        self.f.jump_if_not(self.condition(node.test), end)
        self.loops.append(Loop(top, end))
        self.block(node.body)
        self.loops.pop()
        self.f.jump(top)
        self.f.mark(end)

    def s_Break(self, node):
        if not self.loops:
            raise self.error(node, "break outside a loop")
        self.f.jump(self.loops[-1].end)

    def s_Continue(self, node):
        if not self.loops:
            raise self.error(node, "continue outside a loop")
        self.f.jump(self.loops[-1].top)

    def s_For(self, node):
        if not isinstance(node.target, ast.Name):
            raise self.error(node, "for needs one loop variable")
        it = node.iter
        if isinstance(it, ast.Call) and isinstance(it.func, ast.Name) and it.func.id == "range":
            args = [self.coerce(self.expr(a), T.INT, a) for a in it.args]
            start, stop = (args[0], args[1]) if len(args) > 1 else (const("EX_IntConst", 0, T.INT, 0), args[0])
            step = args[2] if len(args) > 2 else const("EX_IntConst", 1, T.INT, 1)
            stop_var = self.f.temp(T.INT, "Stop")
            self.f.assign(stop_var.expr(), stop)
            var = self.declare(node.target, T.INT)
            self.f.assign(var.expr(), start)
            top, next_, end = self.f.label(), self.f.label(), self.f.label()
            self.f.mark(top)
            self.f.jump_if_not(self.math("Less_IntInt", var.expr(), stop_var.expr()), end)
            self.loops.append(Loop(next_, end))
            self.block(node.body)
            self.loops.pop()
            self.f.mark(next_)
            self.f.assign(var.expr(), self.math("Add_IntInt", var.expr(), step))
            self.f.jump(top)
            self.f.mark(end)
            return
        container = self.expr(it)
        if container.type.kind == "map":
            container = self.map_keys(container)
        if container.type.kind not in ("array", "set"):
            raise self.error(node, "cannot iterate over %r" % container.type)
        if container.type.kind == "set":
            container = self.set_array(container)
        items = self.f.temp(container.type, "Items")
        self.f.assign(items.expr(), container)
        count = self.f.temp(T.INT, "Count")
        self.call_lib("/Script/Engine.KismetArrayLibrary:Array_Length", [items.expr()], types=[items.type], result=count.expr())
        index = self.f.temp(T.INT, "Index")
        self.f.assign(index.expr(), const("EX_IntConst", 0, T.INT, 0))
        var = self.declare(node.target, container.type.inner)
        top, next_, end = self.f.label(), self.f.label(), self.f.label()
        self.f.mark(top)
        self.f.jump_if_not(self.math("Less_IntInt", index.expr(), count.expr()), end)
        self.call_lib("/Script/Engine.KismetArrayLibrary:Array_Get", [items.expr(), index.expr(), var.expr()],
                      types=[items.type, T.INT, container.type.inner])
        self.loops.append(Loop(next_, end))
        self.block(node.body)
        self.loops.pop()
        self.f.mark(next_)
        self.f.assign(index.expr(), self.math("Add_IntInt", index.expr(), const("EX_IntConst", 1, T.INT, 1)))
        self.f.jump(top)
        self.f.mark(end)

    def s_Return(self, node):
        if node.value is not None:
            if self.f.returns is None:
                raise self.error(node, "this function returns nothing")
            target = self.f.returns.expr()
            self.f.assign(target, self.coerce(self.expr(node.value, want=target.type), target.type, node.value))
        self.f.ret()

    # ---------------------------------------------------------------- expressions
    def condition(self, node):
        value = self.expr(node, want=T.BOOL)
        if value.type is None or value.type.kind != "bool":
            if value.type is not None and value.type.kind in ("object", "class", "weak"):
                return self.call_game("/Script/Engine.KismetSystemLibrary:IsValid", None, [value])
            raise self.error(node, "condition is not a bool (%r)" % value.type)
        return value

    def expr(self, node, want=None, statement=False, multi=False):
        method = getattr(self, "e_" + type(node).__name__, None)
        if method is None:
            raise self.error(node, "unsupported expression %s" % type(node).__name__)
        result = method(node, want) if type(node).__name__ not in ("Call",) else method(node, want, statement)
        if isinstance(result, tuple) and not multi:
            result = result[0]
        if result is None and not statement:
            raise self.error(node, "expression has no value")
        return result

    def e_Constant(self, node, want):
        v = node.value
        if v is None:
            e = Expr(make("EX_NoObject"), T.obj())
            e.literal = None
            return e
        if isinstance(v, bool):
            return const("EX_True" if v else "EX_False", None, T.BOOL, v)
        if isinstance(v, int):
            if want is not None and want.kind == "double":
                return const("EX_DoubleConst", float(v), T.DOUBLE, float(v))
            if want is not None and want.kind == "byte":
                return const("EX_ByteConst", v, want, v)
            return const("EX_IntConst", v, T.INT, v)
        if isinstance(v, float):
            return const("EX_DoubleConst", v, T.DOUBLE, v)
        if isinstance(v, str):
            if want is not None and want.kind == "name":
                return const("EX_NameConst", self.bp.package.fname(v), T.NAME, v)
            if want is not None and want.kind == "text":
                return self.text_literal(v)
            return self.string_literal(v)
        raise self.error(node, "unsupported constant %r" % (v,))

    def string_literal(self, value):
        try:
            value.encode("ascii")
            return const("EX_StringConst", value, T.STR, value)
        except UnicodeEncodeError:
            return const("EX_UnicodeStringConst", value, T.STR, value)

    def text_literal(self, value):
        literal = self.string_literal(value)
        return self.call_game("/Script/Engine.KismetTextLibrary:Conv_StringToText", None, [literal])

    def e_Name(self, node, want):
        name = node.id
        if name == "self":
            return self.f.self_expr()
        if name in self.vars:
            return self.vars[name].expr()
        if name in self.cls.module.constants:
            return self.expr(self.cls.module.constants[name], want)
        if name in ("True", "False"):
            return const("EX_True" if name == "True" else "EX_False", None, T.BOOL, name == "True")
        path = symbols().find(name)
        if path is not None and kind_of(path) in CLASS_KINDS:
            # a class as a value (TSubclassOf)
            return Expr(make("EX_ObjectConst", Value=self.bp.package.object(path)),
                        T.Type("class", cls="/Script/CoreUObject.Class", meta=path))
        raise self.error(node, "unknown name %s" % name)

    def attribute(self, node):
        """obj.member as an lvalue/rvalue Expr (properties, our members, enum values)."""
        if isinstance(node.value, ast.Name) and node.value.id not in self.vars and node.value.id != "self":
            path = symbols().find(node.value.id)
            if path is not None and kind_of(path) in ENUM_KINDS:
                return self.enum_value(path, node.attr, node)
        if isinstance(node.value, ast.Name) and node.value.id == "self":
            if node.attr in self.bp.members:
                return self.bp.members[node.attr].expr()
            try:
                return self.f.member(None, node.attr)
            except KeyError:
                raise self.error(node, "self has no member %s" % node.attr)
        target = self.expr(node.value)
        if target.type is None or target.type.kind not in ("object", "struct", "class"):
            raise self.error(node, "%r has no members" % target.type)
        try:
            return self.f.member(target, node.attr)
        except KeyError as e:
            raise self.error(node, str(e))

    def enum_value(self, path, name, node):
        names = reflect.get(path).get("enum_names") or []
        for full, value in names:
            if full.split("::")[-1] == name:
                return const("EX_ByteConst", value, T.Type("byte", enum=path), value)
        raise self.error(node, "%s has no value %s" % (path, name))

    def e_Attribute(self, node, want):
        return self.attribute(node)

    def e_UnaryOp(self, node, want):
        if isinstance(node.op, ast.Not):
            return self.math("Not_PreBool", self.condition(node.operand))
        if isinstance(node.op, ast.USub):
            if isinstance(node.operand, ast.Constant):
                return self.e_Constant(ast.Constant(-node.operand.value), want)
            value = self.expr(node.operand)
            if value.type.kind == "int":
                return self.math("Subtract_IntInt", const("EX_IntConst", 0, T.INT, 0), value)
            return self.math("Subtract_DoubleDouble", const("EX_DoubleConst", 0.0, T.DOUBLE, 0.0), self.coerce(value, T.DOUBLE, node))
        raise self.error(node, "unsupported unary operator")

    def e_BoolOp(self, node, want):
        result = self.f.temp(T.BOOL, "Logic")
        end = self.f.label()
        is_and = isinstance(node.op, ast.And)
        for i, value in enumerate(node.values):
            self.f.assign(result.expr(), self.condition(value))
            if i < len(node.values) - 1:
                if is_and:
                    self.f.jump_if_not(result.expr(), end)
                else:
                    self.f.jump_if_not(self.math("Not_PreBool", result.expr()), end)
        self.f.mark(end)
        return result.expr()

    def e_IfExp(self, node, want):
        a_label, end = self.f.label(), self.f.label()
        cond = self.condition(node.test)
        self.f.jump_if_not(cond, a_label)
        body = self.expr(node.body, want)
        result = self.f.temp(want or body.type, "Choice")
        self.f.assign(result.expr(), self.coerce(body, result.type, node.body))
        self.f.jump(end)
        self.f.mark(a_label)
        self.f.assign(result.expr(), self.coerce(self.expr(node.orelse, result.type), result.type, node.orelse))
        self.f.mark(end)
        return result.expr()

    ARITH = {ast.Add: "Add", ast.Sub: "Subtract", ast.Mult: "Multiply", ast.Div: "Divide", ast.Mod: "Percent"}
    COMPARE = {ast.Eq: "EqualEqual", ast.NotEq: "NotEqual", ast.Lt: "Less", ast.Gt: "Greater", ast.LtE: "LessEqual",
               ast.GtE: "GreaterEqual"}

    def numeric(self, a, b, node):
        """Brings two numbers to a common type: int, double or byte."""
        a, b = as_byte(a), as_byte(b)
        if a.type.kind == b.type.kind and a.type.kind in ("int", "double", "byte", "int64"):
            return a, b, a.type.kind
        if {a.type.kind, b.type.kind} <= {"int", "byte"}:
            return self.coerce(a, T.INT, node), self.coerce(b, T.INT, node), "int"
        if {a.type.kind, b.type.kind} <= {"int", "double", "byte", "float"}:
            return self.coerce(a, T.DOUBLE, node), self.coerce(b, T.DOUBLE, node), "double"
        raise self.error(node, "cannot combine %r and %r" % (a.type, b.type))

    def e_BinOp(self, node, want):
        a, b = self.expr(node.left), self.expr(node.right)
        op = type(node.op)
        if op == ast.Add and (a.type.kind == "str" or b.type.kind == "str"):
            return self.math("Concat_StrStr", self.to_str(a, node), self.to_str(b, node))
        if op == ast.FloorDiv:
            a, b, kind = self.numeric(a, b, node)
            if kind == "int":
                return self.math("Divide_IntInt", a, b)
            return self.math("FFloor", self.math("Divide_DoubleDouble", a, b))
        if op not in self.ARITH:
            raise self.error(node, "unsupported operator")
        a, b, kind = self.numeric(a, b, node)
        if op == ast.Div and kind == "int":
            a, b, kind = self.coerce(a, T.DOUBLE, node), self.coerce(b, T.DOUBLE, node), "double"
        suffix = {"int": "IntInt", "double": "DoubleDouble", "byte": "ByteByte", "int64": "Int64Int64"}[kind]
        name = self.ARITH[op] + "_" + suffix
        if op == ast.Mod and kind == "double":
            name = "FMod"
            result = self.call_game("/Script/Engine.KismetMathLibrary:FMod", None, [a, b], multi=True)
            return result[1] if isinstance(result, tuple) else result
        return self.math(name, a, b)

    def e_Compare(self, node, want):
        if len(node.ops) != 1:
            raise self.error(node, "one comparison at a time")
        op = type(node.ops[0])
        right_node = node.comparators[0]
        if op in (ast.In, ast.NotIn):
            container = self.expr(right_node)
            item = self.expr(node.left)
            if container.type.kind == "array":
                result = self.call_lib("/Script/Engine.KismetArrayLibrary:Array_Contains",
                                       [container, self.coerce(item, container.type.inner, node)],
                                       types=[container.type, container.type.inner], ret=T.BOOL)
            elif container.type.kind == "map":
                result = self.call_lib("/Script/Engine.BlueprintMapLibrary:Map_Contains",
                                       [container, self.coerce(item, container.type.key, node)],
                                       types=[container.type, container.type.key], ret=T.BOOL)
            elif container.type.kind == "set":
                result = self.call_lib("/Script/Engine.BlueprintSetLibrary:Set_Contains",
                                       [container, self.coerce(item, container.type.inner, node)],
                                       types=[container.type, container.type.inner], ret=T.BOOL)
            elif container.type.kind == "str":
                result = self.call_game("/Script/Engine.KismetStringLibrary:Contains", None,
                                        [container, self.to_str(item, node), const("EX_False", None, T.BOOL), const("EX_False", None, T.BOOL)])
            else:
                raise self.error(node, "cannot look into %r" % container.type)
            return self.math("Not_PreBool", result) if op == ast.NotIn else result
        if op in (ast.Is, ast.IsNot):
            a, b = self.expr(node.left), self.expr(right_node)
            name = "EqualEqual_ObjectObject" if op == ast.Is else "NotEqual_ObjectObject"
            return self.math(name, a, b)
        a = as_byte(self.expr(node.left))
        b = as_byte(self.expr(right_node, want=a.type))
        if a.type.kind == "byte" and b.literal is not None and isinstance(b.literal, int):
            b = const("EX_ByteConst", b.literal, a.type, b.literal)
        if b.type.kind == "byte" and a.literal is not None and isinstance(a.literal, int):
            a = const("EX_ByteConst", a.literal, b.type, a.literal)
        kinds = {a.type.kind, b.type.kind}
        prefix = self.COMPARE[op]
        if kinds <= {"object", "class", "weak"}:
            if op not in (ast.Eq, ast.NotEq):
                raise self.error(node, "objects only compare with == and !=")
            suffix = "ClassClass" if kinds == {"class"} else "ObjectObject"
            return self.math(prefix + "_" + suffix, a, b)
        if kinds == {"str"}:
            if op not in (ast.Eq, ast.NotEq):
                raise self.error(node, "strings only compare with == and !=")
            return self.call_game("/Script/Engine.KismetStringLibrary:%s_StrStr" % prefix, None, [a, b])
        if kinds == {"name"}:
            return self.math(prefix + "_NameName", a, b)
        if kinds == {"bool"}:
            return self.math(prefix + "_BoolBool", a, b)
        if kinds == {"text"}:
            return self.call_game("/Script/Engine.KismetTextLibrary:%s_TextText" % prefix, None, [a, b])
        a, b, kind = self.numeric(a, b, node)
        suffix = {"int": "IntInt", "double": "DoubleDouble", "byte": "ByteByte", "int64": "Int64Int64"}[kind]
        return self.math(prefix + "_" + suffix, a, b)

    def e_JoinedStr(self, node, want):
        parts = []
        for value in node.values:
            if isinstance(value, ast.Constant):
                parts.append(self.string_literal(value.value))
            else:
                inner = self.expr(value.value)
                if value.format_spec is not None:
                    spec = "".join(v.value for v in value.format_spec.values if isinstance(v, ast.Constant))
                    inner = self.format_number(inner, spec, value)
                parts.append(self.to_str(inner, value))
        if not parts:
            return self.string_literal("")
        result = parts[0]
        for part in parts[1:]:
            result = self.math("Concat_StrStr", result, part)
        return result

    def format_number(self, value, spec, node):
        """f"{x:.1f}" (fixed decimals) and f"{n:02d}" (zero padded)."""
        if spec.startswith(".") and spec.endswith("f"):
            digits = int(spec[1:-1])
            text = self.call_game("/Script/Engine.KismetTextLibrary:Conv_DoubleToText", None, [
                self.coerce(value, T.DOUBLE, node), const("EX_ByteConst", 0, T.Type("byte", enum="/Script/Engine.ERoundingMode"), 0),
                const("EX_False", None, T.BOOL), const("EX_False", None, T.BOOL),
                const("EX_IntConst", 1, T.INT, 1), const("EX_IntConst", 324, T.INT, 324),
                const("EX_IntConst", digits, T.INT, digits), const("EX_IntConst", digits, T.INT, digits)])
            return self.call_game("/Script/Engine.KismetTextLibrary:Conv_TextToString", None, [text])
        if spec.endswith("d"):
            width = int(spec[:-1].lstrip("0") or 0)
            text = self.call_game("/Script/Engine.KismetTextLibrary:Conv_IntToText", None, [
                self.coerce(value, T.INT, node), const("EX_False", None, T.BOOL), const("EX_False", None, T.BOOL),
                const("EX_IntConst", width, T.INT, width), const("EX_IntConst", 324, T.INT, 324)])
            return self.call_game("/Script/Engine.KismetTextLibrary:Conv_TextToString", None, [text])
        raise self.error(node, "unsupported format %s" % spec)

    def e_Subscript(self, node, want):
        container = self.expr(node.value)
        key = self.expr(node.slice)
        if container.type.kind == "array":
            item = self.f.temp(container.type.inner, "Item")
            self.call_lib("/Script/Engine.KismetArrayLibrary:Array_Get", [container, self.coerce(key, T.INT, node), item.expr()],
                          types=[container.type, T.INT, container.type.inner])
            return item.expr()
        if container.type.kind == "map":
            value = self.f.temp(container.type.value, "Value")
            self.call_lib("/Script/Engine.BlueprintMapLibrary:Map_Find",
                          [container, self.coerce(key, container.type.key, node), value.expr()],
                          types=[container.type, container.type.key, container.type.value], ret=T.BOOL)
            return value.expr()
        raise self.error(node, "cannot index %r" % container.type)

    def e_Tuple(self, node, want):
        return tuple(self.expr(e) for e in node.elts)

    def e_List(self, node, want):
        if want is None or want.kind != "array":
            raise self.error(node, "list literal needs a known array type (annotate the variable)")
        result = self.f.temp(want, "List")
        self.call_lib("/Script/Engine.KismetArrayLibrary:Array_Clear", [result.expr()], types=[want])
        for element in node.elts:
            self.call_lib("/Script/Engine.KismetArrayLibrary:Array_Add",
                          [result.expr(), self.coerce(self.expr(element, want.inner), want.inner, element)],
                          types=[want, want.inner], ret=T.INT)
        return result.expr()

    def e_Dict(self, node, want):
        if want is None or want.kind != "map":
            raise self.error(node, "dict literal needs a known map type (annotate the variable)")
        result = self.f.temp(want, "Map")
        self.call_lib("/Script/Engine.BlueprintMapLibrary:Map_Clear", [result.expr()], types=[want])
        for k, v in zip(node.keys, node.values):
            self.call_lib("/Script/Engine.BlueprintMapLibrary:Map_Add",
                          [result.expr(), self.coerce(self.expr(k, want.key), want.key, k),
                           self.coerce(self.expr(v, want.value), want.value, v)], types=[want, want.key, want.value])
        return result.expr()

    # ---------------------------------------------------------------- calls
    def e_Call(self, node, want, statement=False):
        func = node.func
        args = node.args
        if isinstance(func, ast.Name):
            name = func.id
            builtin = getattr(self, "b_" + name, None)
            if builtin is not None:
                return builtin(node, want)
            path = symbols().find(name)
            if path is not None:
                kind = kind_of(path)
                if kind in STRUCT_KINDS:
                    return self.make_struct(path, node)
            for library in LIBRARIES:
                function = library + ":" + name
                if reflect.exists(function):
                    return self.call_game(function, None, [self.expr(a) for a in args], node=node, multi=True)
            raise self.error(node, "unknown function %s" % name)
        if isinstance(func, ast.Attribute):
            method = func.attr
            owner = func.value
            if isinstance(owner, ast.Name) and owner.id == "self":
                if method in self.bp.functions:
                    own = self.bp.functions[method]
                    inputs = [(n, t) for n, t, f in own.params if "CPF_ReturnParm" not in f]
                    values = [self.coerce(self.expr(a, t), t, a) for a, (n, t) in zip(args, inputs)]
                    return self.f.call(method, None, values)
                try:
                    function = reflect.find_function(self.bp.super, method)
                except KeyError:
                    raise self.error(node, "self has no function %s" % method)
                return self.call_game(function, self.f.self_expr(), [self.expr(a) for a in args], node=node, multi=True)
            if isinstance(owner, ast.Name) and owner.id not in self.vars:
                path = symbols().find(owner.id)
                if path is not None and kind_of(path) in CLASS_KINDS:
                    try:
                        function = reflect.find_function(path, method)
                    except KeyError:
                        raise self.error(node, "%s has no function %s" % (owner.id, method))
                    return self.call_game(function, None, [self.expr(a) for a in args], node=node, multi=True)
            target = self.expr(owner)
            container = getattr(self, "m_" + target.type.kind + "_" + method, None) if target.type else None
            if container is not None:
                return container(target, args, node)
            if target.type.kind not in ("object", "class"):
                raise self.error(node, "%r has no method %s" % (target.type, method))
            cls = target.type.cls if target.type.kind == "object" else target.type.meta
            try:
                function = reflect.find_function(cls, method)
            except KeyError:
                raise self.error(node, "%s has no function %s" % (cls, method))
            return self.call_game(function, target, [self.expr(a) for a in args], node=node, multi=True)
        raise self.error(node, "unsupported call")

    def call_game(self, function, target, args, node=None, multi=False):
        """Calls a game function with Expr arguments; inputs are coerced to the parameter types. Out
        parameters left out of the call come back as extra results: (result, out1, out2...)."""
        params = reflect.params(function)
        inputs = [p for p in params if "CPF_ReturnParm" not in p["flags"]]
        if inputs and inputs[0]["name"] == "WorldContextObject" and len(args) == len(inputs) - 1:
            args = [self.f.self_expr()] + list(args)
        required = [p for p in inputs if not ("CPF_OutParm" in p["flags"] and "CPF_ReferenceParm" not in p["flags"])]
        outs = []
        final = []
        if len(args) == len(inputs):
            for p, a in zip(inputs, args):
                final.append(self.coerce(a, T.from_record(p), node) if "CPF_OutParm" not in p["flags"] else a)
        elif len(args) == len(required):
            it = iter(args)
            for p in inputs:
                if p in required:
                    final.append(self.coerce(next(it), T.from_record(p), node) if "CPF_OutParm" not in p["flags"] else next(it))
                else:
                    out = self.f.temp(T.from_record(p), "Out").expr()
                    outs.append(out)
                    final.append(out)
        else:
            raise self.error(node, "%s takes %d arguments (%s), got %d" % (
                function, len(inputs), ", ".join(p["name"] for p in inputs), len(args)))
        result = self.f.call(function, target, final)
        if outs:
            return tuple([result] + outs) if multi else (result if result is not None else outs[0])
        return result

    def call_lib(self, function, args, types, ret=None, result=None):
        """Calls a wildcard (CustomThunk) library function: argument types come from the arguments."""
        params = reflect.params(function)
        inputs = [p for p in params if "CPF_ReturnParm" not in p["flags"]]
        if len(args) != len(inputs):
            raise CompileError("%s: %d arguments, %d given" % (function, len(inputs), len(args)))
        ret_record = next((p for p in params if "CPF_ReturnParm" in p["flags"]), None)
        owner = function.split(":")[0]
        cdo = owner.rsplit(".", 1)[0] + ".Default__" + owner.rsplit(".", 1)[1]
        call_json = make("EX_FinalFunction", StackNode=self.bp.package.object(function), Parameters=[a.json for a in args])
        target = Expr(make("EX_ObjectConst", Value=self.bp.package.object(cdo)), T.obj(owner))
        if ret_record is None:
            self.f.emit(self.f.context(target, call_json, None))
            return None
        dest = result or self.f.temp(ret or T.from_record(ret_record), "Ret").expr()
        self.f.assign(dest, Expr(self.f.context(target, call_json, dest.prop), dest.type))
        return dest

    def math(self, name, *args):
        for library in ("KismetMathLibrary", "KismetStringLibrary", "KismetTextLibrary"):
            function = "/Script/Engine.%s:%s" % (library, name)
            if reflect.exists(function):
                return self.call_game(function, None, list(args))
        raise CompileError("no library function %s" % name)

    # container methods: m_<kind>_<name>(target, args, node)
    def m_array_append(self, target, args, node):
        self.call_lib("/Script/Engine.KismetArrayLibrary:Array_Add",
                      [target, self.coerce(self.expr(args[0], target.type.inner), target.type.inner, node)],
                      types=[target.type, target.type.inner], ret=T.INT)
        return None

    def m_array_clear(self, target, args, node):
        self.call_lib("/Script/Engine.KismetArrayLibrary:Array_Clear", [target], types=[target.type])

    def m_array_remove_at(self, target, args, node):
        self.call_lib("/Script/Engine.KismetArrayLibrary:Array_Remove", [target, self.coerce(self.expr(args[0]), T.INT, node)],
                      types=[target.type, T.INT])

    def m_array_remove(self, target, args, node):
        return self.call_lib("/Script/Engine.KismetArrayLibrary:Array_RemoveItem",
                             [target, self.coerce(self.expr(args[0], target.type.inner), target.type.inner, node)],
                             types=[target.type, target.type.inner], ret=T.BOOL)

    def m_array_index(self, target, args, node):
        return self.call_lib("/Script/Engine.KismetArrayLibrary:Array_Find",
                             [target, self.coerce(self.expr(args[0], target.type.inner), target.type.inner, node)],
                             types=[target.type, target.type.inner], ret=T.INT)

    def m_array_shuffle(self, target, args, node):
        self.call_lib("/Script/Engine.KismetArrayLibrary:Array_Shuffle", [target], types=[target.type])

    def m_map_remove(self, target, args, node):
        return self.call_lib("/Script/Engine.BlueprintMapLibrary:Map_Remove",
                             [target, self.coerce(self.expr(args[0], target.type.key), target.type.key, node)],
                             types=[target.type, target.type.key], ret=T.BOOL)

    def m_map_clear(self, target, args, node):
        self.call_lib("/Script/Engine.BlueprintMapLibrary:Map_Clear", [target], types=[target.type])

    def m_map_keys(self, target, args, node):
        return self.map_keys(target)

    def m_map_values(self, target, args, node):
        values = self.f.temp(T.array(target.type.value), "Values")
        self.call_lib("/Script/Engine.BlueprintMapLibrary:Map_Values", [target, values.expr()], types=[target.type, values.type])
        return values.expr()

    def m_map_get(self, target, args, node):
        """m.get(key, default)"""
        value = self.f.temp(target.type.value, "Value")
        found = self.call_lib("/Script/Engine.BlueprintMapLibrary:Map_Find",
                              [target, self.coerce(self.expr(args[0], target.type.key), target.type.key, node), value.expr()],
                              types=[target.type, target.type.key, target.type.value], ret=T.BOOL)
        if len(args) > 1:
            done = self.f.label()
            self.f.jump_if_not(self.math("Not_PreBool", found), done)
            self.f.assign(value.expr(), self.coerce(self.expr(args[1], target.type.value), target.type.value, node))
            self.f.mark(done)
        return value.expr()

    def m_set_add(self, target, args, node):
        self.call_lib("/Script/Engine.BlueprintSetLibrary:Set_Add",
                      [target, self.coerce(self.expr(args[0], target.type.inner), target.type.inner, node)],
                      types=[target.type, target.type.inner])

    def m_set_remove(self, target, args, node):
        return self.call_lib("/Script/Engine.BlueprintSetLibrary:Set_Remove",
                             [target, self.coerce(self.expr(args[0], target.type.inner), target.type.inner, node)],
                             types=[target.type, target.type.inner], ret=T.BOOL)

    def m_set_clear(self, target, args, node):
        self.call_lib("/Script/Engine.BlueprintSetLibrary:Set_Clear", [target], types=[target.type])

    def map_keys(self, target):
        keys = self.f.temp(T.array(target.type.key), "Keys")
        self.call_lib("/Script/Engine.BlueprintMapLibrary:Map_Keys", [target, keys.expr()], types=[target.type, keys.type])
        return keys.expr()

    def set_array(self, target):
        items = self.f.temp(T.array(target.type.inner), "SetItems")
        self.call_lib("/Script/Engine.BlueprintSetLibrary:Set_ToArray", [target, items.expr()], types=[target.type, items.type])
        return items.expr()

    # builtins: b_<name>(node, want)
    def b_len(self, node, want):
        value = self.expr(node.args[0])
        if value.type.kind == "array":
            return self.call_lib("/Script/Engine.KismetArrayLibrary:Array_Length", [value], types=[value.type], ret=T.INT)
        if value.type.kind == "map":
            return self.call_lib("/Script/Engine.BlueprintMapLibrary:Map_Length", [value], types=[value.type], ret=T.INT)
        if value.type.kind == "set":
            return self.call_lib("/Script/Engine.BlueprintSetLibrary:Set_Length", [value], types=[value.type], ret=T.INT)
        if value.type.kind == "str":
            return self.call_game("/Script/Engine.KismetStringLibrary:Len", None, [value])
        raise self.error(node, "len of %r" % value.type)

    def b_str(self, node, want):
        return self.to_str(self.expr(node.args[0]), node)

    def b_int(self, node, want):
        value = self.expr(node.args[0])
        if value.type.kind == "double":
            return self.math("FTrunc", value)
        if value.type.kind == "str":
            return self.call_game("/Script/Engine.KismetStringLibrary:Conv_StringToInt", None, [value])
        return self.coerce(value, T.INT, node)

    def b_float(self, node, want):
        value = self.expr(node.args[0])
        if value.type.kind == "str":
            return self.call_game("/Script/Engine.KismetStringLibrary:Conv_StringToDouble", None, [value])
        return self.coerce(value, T.DOUBLE, node)

    def b_Text(self, node, want):
        return self.coerce(self.expr(node.args[0]), T.TEXT, node)

    def b_Name(self, node, want):
        arg = node.args[0]
        if isinstance(arg, ast.Constant):
            return const("EX_NameConst", self.bp.package.fname(arg.value), T.NAME, arg.value)
        return self.coerce(self.expr(arg), T.NAME, node)

    def b_cast(self, node, want):
        value = self.expr(node.args[0])
        path = self.cls.resolve_class(node.args[1])
        result = self.f.temp(T.obj(path), "Cast")
        cast = make("EX_DynamicCast", ClassPtr=self.bp.package.object(path), Target=value.json)
        self.f.assign(result.expr(), Expr(cast, result.type))
        return result.expr()

    def b_isinstance(self, node, want):
        return self.call_game("/Script/Engine.KismetSystemLibrary:IsValid", None, [self.b_cast(node, want)])

    def b_min(self, node, want):
        a, b, kind = self.numeric(self.expr(node.args[0]), self.expr(node.args[1]), node)
        return self.math("Min" if kind == "int" else "FMin", a, b)

    def b_max(self, node, want):
        a, b, kind = self.numeric(self.expr(node.args[0]), self.expr(node.args[1]), node)
        return self.math("Max" if kind == "int" else "FMax", a, b)

    def b_abs(self, node, want):
        value = self.expr(node.args[0])
        return self.math("Abs_Int" if value.type.kind == "int" else "Abs", value)

    def b_bind(self, node, want):
        """bind(obj.SomeDelegate, self.Handler): adds our function to a multicast delegate (event dispatcher)."""
        delegate = self.attribute(node.args[0])
        handler = node.args[1]
        if not (isinstance(handler, ast.Attribute) and isinstance(handler.value, ast.Name) and handler.value.id == "self"):
            raise self.error(node, "bind needs self.<function>")
        if delegate.type.kind != "mcdelegate":
            raise self.error(node, "bind needs an event dispatcher, not %r" % delegate.type)
        local = self.f.temp(T.Type("delegate", signature=delegate.type.signature), "Delegate")
        self.f.emit(make("EX_BindDelegate", FunctionName=self.bp.package.fname(handler.attr), Delegate=local.expr().json,
                         ObjectTerm=make("EX_Self")))
        self.f.emit(make("EX_AddMulticastDelegate", Delegate=delegate.json, DelegateToAdd=local.expr().json))
        return None

    def b_unbind(self, node, want):
        delegate = self.attribute(node.args[0])
        handler = node.args[1]
        local = self.f.temp(T.Type("delegate", signature=delegate.type.signature), "Delegate")
        self.f.emit(make("EX_BindDelegate", FunctionName=self.bp.package.fname(handler.attr), Delegate=local.expr().json,
                         ObjectTerm=make("EX_Self")))
        self.f.emit(make("EX_RemoveMulticastDelegate", Delegate=delegate.json, DelegateToAdd=local.expr().json))
        return None

    def b_classof(self, node, want):
        """classof(SomeClass) / classof("/Game/...Class_C"): the class object as a value."""
        arg = node.args[0]
        path = arg.value if isinstance(arg, ast.Constant) else self.cls.resolve_class(arg)
        return Expr(make("EX_ObjectConst", Value=self.bp.package.object(path)),
                    T.Type("class", cls="/Script/CoreUObject.Class", meta=path))

    def make_struct(self, path, node):
        """StructName(Field=value, ...): a temporary struct with the given members set."""
        result = self.f.temp(T.struct(path), "Struct")
        for keyword in node.keywords:
            member = self.f.member(result.expr(), keyword.arg)
            self.f.assign(member, self.coerce(self.expr(keyword.value, member.type), member.type, keyword.value))
        if node.args:
            raise self.error(node, "struct members are set by name: %s(Field=...)" % path.rsplit(".", 1)[1])
        return result.expr()

    # ---------------------------------------------------------------- conversions
    def to_str(self, value, node):
        value = as_byte(value)
        k = value.type.kind
        if k == "str":
            return value
        if value.literal is not None and k in ("int", "double", "bool"):
            text = ("%g" % value.literal) if k == "double" else str(value.literal).lower() if k == "bool" else str(value.literal)
            return self.string_literal(text)
        conversions = {"int": "Conv_IntToString", "double": "Conv_DoubleToString", "bool": "Conv_BoolToString",
                       "name": "Conv_NameToString", "byte": "Conv_ByteToString", "object": "Conv_ObjectToString",
                       "int64": "Conv_Int64ToString"}
        if k == "text":
            return self.call_game("/Script/Engine.KismetTextLibrary:Conv_TextToString", None, [value])
        if k in conversions:
            return self.call_game("/Script/Engine.KismetStringLibrary:" + conversions[k], None, [value])
        raise self.error(node, "cannot make a string of %r" % value.type)

    def coerce(self, value, type, node):
        if type is None or value.type is None:
            return value
        a, b = value.type.kind, type.kind
        if a == b:
            if a == "byte" and value.literal is not None:
                return const("EX_ByteConst", value.literal, type, value.literal)
            return value
        if value.literal is not None:
            v = value.literal
            if b == "double" and isinstance(v, (int, float)) and not isinstance(v, bool):
                return const("EX_DoubleConst", float(v), T.DOUBLE, float(v))
            if b == "float" and isinstance(v, (int, float)):
                return const("EX_FloatConst", float(v), T.FLOAT, float(v))
            if b in ("byte", "enum") and isinstance(v, int):
                return const("EX_ByteConst", v, type, v)
            if b == "int" and isinstance(v, int) and a == "byte":
                return const("EX_IntConst", v, T.INT, v)
            if b == "name" and isinstance(v, str):
                return const("EX_NameConst", self.bp.package.fname(v), T.NAME, v)
            if b == "text" and isinstance(v, str):
                return self.text_literal(v)
            if b in ("object", "class", "weak", "interface") and v is None:
                return Expr(make("EX_NoObject"), type)
        if b in ("object", "class") and a in ("object", "class"):
            return value
        if (a, b) == ("int", "double"):
            return self.math("Conv_IntToDouble", value)
        if (a, b) in (("double", "float"), ("float", "double")):
            # ECastToken: CST_DoubleToFloat = 3, CST_FloatToDouble = 4 (UE 5.3, as the game's Blueprints use them)
            return Expr(make("EX_PrimitiveCast", ConversionType=3 if b == "float" else 4, Target=value.json), type)
        if (a, b) == ("int", "float"):
            return self.coerce(self.math("Conv_IntToDouble", value), type, node)
        if (a, b) == ("byte", "int"):
            return self.math("Conv_ByteToInt", value)
        if (a, b) == ("int", "byte"):
            return self.math("Conv_IntToByte", value)
        if a == "byte" and b == "enum" or a == "enum" and b == "byte":
            return Expr(value.json, type, value.lvalue, value.prop)
        if (a, b) == ("byte", "double"):
            return self.math("Conv_IntToDouble", self.math("Conv_ByteToInt", value))
        if b == "str":
            return self.to_str(value, node)
        if (a, b) == ("str", "text"):
            return self.call_game("/Script/Engine.KismetTextLibrary:Conv_StringToText", None, [value])
        if (a, b) == ("str", "name"):
            return self.call_game("/Script/Engine.KismetStringLibrary:Conv_StringToName", None, [value])
        if b == "bool" and a in ("object", "class"):
            return self.call_game("/Script/Engine.KismetSystemLibrary:IsValid", None, [value])
        if a == "weak" and b == "object" or a == "object" and b == "weak":
            return Expr(value.json, type, value.lvalue, value.prop)
        raise self.error(node, "cannot use %r as %r" % (value.type, type))


def compile_source(source, filename="<mod>"):
    return Module(source, filename).compile()
