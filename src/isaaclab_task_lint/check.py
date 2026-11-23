# See LICENSE and NOTICE.
"""Isaac Lab 3.0 environment ownership rules."""

import ast
from pathlib import Path

from .index import Index, Unresolved
from .resources import RESOURCE_FIELDS, check_resource

TERMS = {
    "Reward": "rewards",
    "Event": "events",
    "Observation": "observations",
    "Termination": "terminations",
    "Curriculum": "curriculums",
    "Action": "actions",
    "Command": "commands",
    "Recorder": "recorders",
}
EXTENSIONS = {
    "actuators",
    "assets",
    "controllers",
    "sensors",
    "terrains",
    "managers",
    "sim",
    "physics",
    "scene",
    "devices",
    "renderers",
    "visualizers",
    "markers",
    "cloner",
    "scene_data",
    "ui",
}
ENV_TYPES = {"ManagerBasedEnv", "ManagerBasedRLEnv", "DirectRLEnv", "DirectMARLEnv", "ManagerBasedRLMimicEnv"}
COMPONENT_FIELDS = {
    "scene",
    "sim",
    "actions",
    "observations",
    "rewards",
    "terminations",
    "events",
    "commands",
    "curriculum",
    "recorders",
    "viewer",
    "xr",
    "teleop_devices",
    "video_recorders",
    "observation_noise_model",
    "action_noise_model",
    "sensors",
    "actuators",
    "robot",
    "spawn",
    "physics",
    "visualizer_cfgs",
}


def framework(name: str) -> bool:
    top = name.partition(".")[0]
    return top in {
        "isaaclab",
        "isaaclab_assets",
        "isaaclab_rl",
        "isaaclab_tasks",
        "isaaclab_contrib",
        "isaaclab_mimic",
        "isaaclab_experimental",
        "isaaclab_tasks_experimental",
        "isaaclab_newton",
        "isaaclab_physx",
        "isaaclab_ov",
        "isaaclab_visualizers",
        "isaaclab_teleop",
        "isaaclab_ppisp",
    }


class Check:
    def __init__(self, root: Path, package: str):
        self.index = Index(root)
        self.package = package
        self.tasks = root / "src" / package / "tasks"
        self.extensions = root / "src" / (package + "_isaaclabs")
        self.diagnostics = set()
        self.components = set()
        self.environments = set()
        self.registrations = set()
        self.term_classes = set()
        self.bound_terms = set()

    def report(self, mod, node, code, message):
        path = mod.path.relative_to(self.index.root).as_posix()
        self.diagnostics.add((path, node.lineno, node.col_offset + 1, code, message))

    def task_entries(self, entries, path):
        lines = path.read_text().splitlines()
        for key, entry in entries.items():
            if not isinstance(entry, str):
                raise ValueError(f"expected a module reference for task entry {key}")
            module, _, symbol = entry.partition(":")
            if module not in self.index.modules or (symbol and f"{module}.{symbol}" not in self.index.defs):
                for line, text in enumerate(lines, 1):
                    if entry in text:
                        self.diagnostics.add((
                            path.name,
                            line,
                            text.index(entry) + 1,
                            "ORG005",
                            f"{key} = {entry!r}: missing task discovery target",
                        ))
                        break
                else:
                    self.diagnostics.add((path.name, 1, 1, "ORG005", f"{key} = {entry!r}: missing discovery target"))

    def family(self, mod):
        if mod.path.is_relative_to(self.tasks):
            parts = mod.path.relative_to(self.tasks).parts
            if len(parts) > 1 and parts[0] not in {"manager_based", "direct"}:
                return self.tasks / parts[0]
        return None

    def resolve(self, mod, expr):
        try:
            return self.index.expr(mod, expr)
        except Unresolved as exc:
            self.report(mod, expr, "ORG005", f"{ast.unparse(expr)}: {exc}")
            return ""

    def bases(self, name, visited=frozenset()):
        if name in visited:
            owner, node = self.index.defs[name]
            self.report(owner, node, "ORG005", f"{name}: cyclic inheritance")
            return set()
        item = self.index.defs.get(name)
        if not item or not isinstance(item[1], ast.ClassDef):
            return {name}
        ancestors = set()
        for base in item[1].bases:
            try:
                parent = self.index.expr(item[0], base.value if isinstance(base, ast.Subscript) else base)
            except Unresolved as exc:
                if self.family(item[0]) or item[0].path.is_relative_to(self.extensions):
                    self.report(item[0], base, "ORG005", f"{ast.unparse(base)}: {exc}")
                continue
            ancestors.add(parent)
            ancestors.update(self.bases(parent, visited | {name}))
        return ancestors

    def location(self, mod, node, name, directory, code, filename=None):
        item = self.index.defs.get(name)
        if not item:
            return
        self.components.add(name)
        target, definition = item
        correct = directory is not None and target.path.is_relative_to(directory)
        if correct and filename:
            tail = target.path.relative_to(directory)
            correct = tail.as_posix() == filename + ".py" or (
                filename in {"actions", "commands", "recorders"} and tail.parts[0] == filename
            )
        if not correct:
            expected = directory.relative_to(self.index.root) if directory else "a recognized task family"
            if filename:
                expected = f"{expected}/{filename}"
            self.report(
                mod,
                node,
                code,
                f"{name} defined at {target.path.relative_to(self.index.root)}:"
                f"{definition.lineno}; expected {expected}",
            )

    def classify(self, name, mod, node):
        for base in sorted(self.bases(name)):
            if not framework(base):
                continue
            parts = base.split(".")
            short = parts[-1]
            family = self.family(mod)
            self.components.add(name)
            if short.removesuffix("Cfg") in ENV_TYPES:
                self.environments.add(name)
                workflow = short.removesuffix("Cfg")
                suffix = {"DirectRLEnv": "_direct", "DirectMARLEnv": "_marl_direct"}.get(workflow, "")
                if family is None or not family.name.endswith(suffix):
                    self.report(mod, node, "ORG001", f"{name} belongs under {self.package}/tasks/<family>{suffix}/")
            elif short in {"InteractiveSceneCfg", "ObservationGroupCfg", "PresetCfg"}:
                if family is None:
                    self.report(mod, node, "ORG006", f"task configuration {name} belongs in a task family")
            elif parts[0] == "isaaclab_rl":
                if family is None or "agents" not in mod.path.relative_to(family).parts:
                    self.report(mod, node, "ORG006", f"agent configuration {name} belongs with its task variant")
            elif short in {"ManagerTermBase", "ManagerTermBaseCfg"} or any(
                short.endswith(end + suffix) for end in TERMS for suffix in ("Term", "TermCfg")
            ):
                self.term_classes.add(name)
            elif len(parts) > 2 and parts[1] in EXTENSIONS:
                area = parts[1]
                code = {"terrains": "ORG002", "managers": "ORG003"}.get(area, "ORG007")
                self.location(mod, node, name, self.extensions / area, code)
            elif len(parts) > 3 and (
                parts[1:3] == ["envs", "mdp"]
                or (parts[1] == "utils" and parts[2] in {"noise", "modifiers", "tensor_processors"})
            ):
                if parts[1] == "utils":
                    self.location(mod, node, name, self.extensions / "utils" / parts[2], "ORG007")
            else:
                self.report(mod, node, "ORG008", f"{name} derives from {base}; no organization rule for this component")

    def binding(self, mod, expr, role):
        name = self.resolve(mod, expr)
        if not name or framework(name):
            return
        if name not in self.index.defs:
            self.report(mod, expr, "ORG005", f"{ast.unparse(expr)}: no source definition for {name}")
            return
        if role in EXTENSIONS or (role and role.startswith("utils/")):
            self.location(mod, expr, name, self.extensions / role, "ORG002" if role == "terrains" else "ORG007")
        elif role:
            self.bound_terms.add(name)
            family = self.family(mod)
            self.location(mod, expr, name, family / "mdp" if family else None, "ORG004", role)
        else:
            self.components.add(name)
            owner, node = self.index.defs[name]
            if not any(framework(b) for b in self.bases(name)):
                self.report(
                    mod,
                    expr,
                    "ORG008",
                    f"{name} at {owner.path.relative_to(self.index.root)}:"
                    f"{node.lineno}; no component ownership rule for {ast.unparse(expr)}",
                )

    def component_arguments(self, mod, call, seen):
        """Inspect component slots on a configuration constructor or replacement."""
        for keyword in call.keywords:
            if keyword.arg in COMPONENT_FIELDS:
                self.composition(mod, keyword.value, seen)
            elif keyword.arg is None:
                self.composition(mod, keyword.value, seen, expanded=True)

    def expanded_component_arguments(self, mod, expr, seen):
        if isinstance(expr, ast.Dict):
            for key, value in zip(expr.keys, expr.values, strict=True):
                if key is None:
                    self.composition(mod, value, seen, expanded=True)
                elif isinstance(key, ast.Constant) and isinstance(key.value, str):
                    if key.value in COMPONENT_FIELDS:
                        self.composition(mod, value, seen)
                else:
                    self.report(mod, key, "ORG005", f"{ast.unparse(key)}: unknown component keyword")
        else:
            self.report(mod, expr, "ORG005", f"{ast.unparse(expr)}: cannot determine expanded component fields")

    def composition(self, mod, expr, seen=frozenset(), *, expanded=False):
        """Follow each component of a scene/config, including values in asset and actuator maps."""
        if isinstance(expr, ast.Name | ast.Attribute):
            text = ast.unparse(expr)
            key = (mod.name, text)
            if key in seen:
                self.report(mod, expr, "ORG005", f"{text}: cyclic component reference")
                return
            value = mod.names.get(text)
            if isinstance(value, ast.expr):
                self.composition(mod, value, seen | {key}, expanded=expanded)
                return
            if isinstance(value, str):
                source, _, attr = value.rpartition(".")
                owner = self.index.modules.get(source)
                if owner and attr in owner.names:
                    self.composition(owner, ast.copy_location(ast.Name(id=attr), expr), seen | {key}, expanded=expanded)
                    return
        if expanded:
            self.expanded_component_arguments(mod, expr, seen)
            return
        if isinstance(expr, ast.Constant):
            return
        if isinstance(expr, ast.Dict | ast.List | ast.Tuple):
            children = expr.values if isinstance(expr, ast.Dict) else expr.elts
            for child in children:
                self.composition(mod, child, seen)
            return
        if isinstance(expr, ast.Call) and isinstance(expr.func, ast.Attribute) and expr.func.attr == "replace":
            self.composition(mod, expr.func.value, seen)
            self.component_arguments(mod, expr, seen)
            return
        callee = expr.func if isinstance(expr, ast.Call) else expr
        name = self.resolve(mod, callee)
        if not name:
            return
        if name == "typing.cast" and isinstance(expr, ast.Call) and len(expr.args) == 2:
            self.composition(mod, expr.args[1], seen)
            return
        if name == "dataclasses.MISSING":
            return
        if isinstance(expr, ast.Call):
            self.component_arguments(mod, expr, seen)
        if framework(name):
            self.components.add(name)
            return
        target = self.index.defs.get(name)
        if target and isinstance(target[1], ast.ClassDef):
            self.components.add(name)
            if not any(framework(b) for b in self.bases(name)):
                owner, cls = target
                configured = any(ast.unparse(d).split(".")[-1] == "configclass" for d in cls.decorator_list)
                if not (configured and self.family(owner)):
                    self.report(
                        mod,
                        expr,
                        "ORG008",
                        f"{name} at {owner.path.relative_to(self.index.root)}:"
                        f"{cls.lineno}; no ownership rule for bound component",
                    )
        else:
            self.report(mod, expr, "ORG005", f"{ast.unparse(expr)}: component implementation cannot be determined")

    def registration(self, mod, call):
        keywords = {k.arg: k.value for k in call.keywords}
        self.registrations.add((mod.name, call.lineno))
        family = self.family(mod)
        variant = None
        if family:
            relative = mod.path.relative_to(family).parts
            if len(relative) >= 3 and relative[0] == "config":
                variant = family / relative[0] / relative[1]
        if not variant:
            self.report(mod, call, "ORG001", "registration belongs under tasks/<family>/config/<robot>/")
        kwargs = keywords.get("kwargs")
        if None in keywords:
            self.report(mod, keywords[None], "ORG005", "registration argument expansion: unknown targets")
        fields = [(k, v) for k, v in keywords.items() if k == "entry_point"]
        if isinstance(kwargs, ast.Name) and isinstance(mod.names.get(kwargs.id), ast.expr):
            kwargs = mod.names[kwargs.id]
        if isinstance(kwargs, ast.Dict):
            for key, value in zip(kwargs.keys, kwargs.values, strict=True):
                if not isinstance(key, ast.Constant):
                    self.report(mod, key or value, "ORG005", "registration kwargs: unknown key or mapping expansion")
                elif str(key.value).endswith("_entry_point"):
                    fields.append((key.value, value))
        elif isinstance(kwargs, ast.Call) and ast.unparse(kwargs.func) == "dict" and not kwargs.args:
            for kw in kwargs.keywords:
                if kw.arg is None:
                    self.report(mod, kw.value, "ORG005", "registration kwargs: unknown mapping expansion")
                elif kw.arg.endswith("_entry_point"):
                    fields.append((kw.arg, kw.value))
        elif kwargs is not None:
            self.report(mod, kwargs, "ORG005", "registration kwargs: cannot determine configuration entry points")
        for key, expr in fields:
            try:
                if not isinstance(expr, ast.Constant | ast.JoinedStr):
                    name = self.index.expr(mod, expr)
                else:
                    raw = self.index.string(mod, expr)
                    module, sep, symbol = raw.partition(":")
                    if not sep:
                        raise Unresolved(f"missing module:symbol in {raw}")
                    if symbol.endswith((".yaml", ".yml", ".json", ".toml")):
                        owner = self.index.modules.get(module)
                        if not owner or not (owner.path.parent / symbol).is_file():
                            raise Unresolved(f"missing registered resource {raw}")
                        if not variant or not owner.path.is_relative_to(variant):
                            self.report(mod, expr, "ORG006", f"resource {raw} belongs with the registered variant")
                        continue
                    name = self.index.lookup(f"{module}.{symbol}")
                if framework(name):
                    continue
                if name not in self.index.defs:
                    raise Unresolved(f"missing registered target {name}")
                if key in {"entry_point", "env_cfg_entry_point"}:
                    expected = ENV_TYPES if key == "entry_point" else {t + "Cfg" for t in ENV_TYPES}
                    if not any(b.rsplit(".", 1)[-1] in expected for b in self.bases(name)):
                        self.report(mod, expr, "ORG006", f"{key}: {name} does not implement the environment contract")
                if key != "entry_point":
                    self.location(mod, expr, name, variant, "ORG001")
                else:
                    self.location(mod, expr, name, family, "ORG006")
            except Unresolved as exc:
                self.report(mod, expr, "ORG005", f"{ast.unparse(expr)}: {exc}")

    def roles(self, name):
        roles = set()
        for base in {name} | self.bases(name):
            if not framework(base):
                continue
            short = base.rsplit(".", 1)[-1]
            for prefix, role in TERMS.items():
                if short in {prefix + "TermCfg", prefix + "Term"}:
                    roles.add(role)
            if ".terrains." in base:
                roles.add("terrains")
            area = base.split(".")[1:2]
            if area and area[0] in EXTENSIONS - {"managers", "terrains"}:
                roles.add(area[0])
            for area in ("noise", "tensor_processors", "modifiers"):
                if f".utils.{area}." in base:
                    roles.add("utils/" + area)
            if ".envs.mdp." in base:
                for prefix in ("Action", "Command", "Recorder"):
                    if short.endswith((prefix, prefix + "Cfg")):
                        roles.add(TERMS[prefix])
        return roles

    def check_binding(self, mod, expression, config_type):
        roles = sorted(self.roles(config_type))
        if len(roles) > 1:
            self.report(mod, expression, "ORG005", f"{ast.unparse(expression)}: ambiguous roles {roles}")
        else:
            self.binding(mod, expression, roles[0] if roles else None)

    def local_component_call(self, mod, expression):
        if not isinstance(expression, ast.Call):
            return False
        try:
            constructor = self.index.expr(mod, expression.func)
        except Unresolved:
            return False
        target = self.index.defs.get(constructor)
        return target is not None

    def reassignment(self, mod, target, value):
        if not isinstance(target, ast.Attribute) or target.attr not in {"func", "function", "class_type"}:
            return
        path = ast.unparse(target).split(".")
        roles = set(path) & set(TERMS.values())
        if "terrain" in path or "terrain_generator" in path:
            roles.add("terrains")
        if len(roles) > 1:
            self.report(mod, target, "ORG005", f"{ast.unparse(target)}: ambiguous binding categories {sorted(roles)}")
        else:
            self.binding(mod, value, next(iter(roles), None))

    def check_class(self, mod, node):
        name = f"{mod.scopes.get(node, mod.name)}.{node.name}"
        if name in self.index.defs:
            self.classify(name, mod, node)
        lineage = {base.split(".")[-1] for base in self.bases(name)}
        is_scene = "InteractiveSceneCfg" in lineage
        task_config = self.family(mod) and any(
            ast.unparse(d).split(".")[-1] == "configclass" for d in node.decorator_list
        )
        for method in node.body:
            if not (
                lineage & ENV_TYPES
                and isinstance(method, ast.FunctionDef)
                and method.name in {"__init__", "_setup_scene"}
            ):
                continue
            for assignment in ast.walk(method):
                if isinstance(assignment, ast.Assign):
                    for dest in assignment.targets:
                        if isinstance(dest, ast.Attribute) and (
                            dest.attr in COMPONENT_FIELDS or self.local_component_call(mod, assignment.value)
                        ):
                            value = assignment.value
                            # Looking up a scene entity uses the already-checked scene configuration.
                            if isinstance(value, ast.Subscript) and ast.unparse(value.value) == "self.scene":
                                continue
                            self.composition(mod, value)
        for field in node.body:
            if isinstance(field, ast.AnnAssign | ast.Assign):
                target = field.target if isinstance(field, ast.AnnAssign) else field.targets[0]
                if (
                    field.value
                    and isinstance(target, ast.Name)
                    and (
                        target.id in COMPONENT_FIELDS
                        or (task_config and self.local_component_call(mod, field.value))
                        or (is_scene and isinstance(field.value, ast.Call) and not target.id.startswith("_"))
                    )
                ):
                    self.composition(mod, field.value)
                if field.value and isinstance(target, ast.Name) and target.id in {"class_type", "function", "func"}:
                    self.check_binding(mod, field.value, name)

    def check_call(self, mod, node):
        try:
            callee = self.index.expr(mod, node.func)
        except Unresolved as exc:
            head = ast.unparse(node.func).partition(".")[0]
            source = mod.names.get(head)
            if self.family(mod) and isinstance(source, str) and framework(source):
                self.report(mod, node.func, "ORG005", f"{ast.unparse(node.func)}: {exc}")
            callee = ""
        if callee in {"gymnasium.register", "gymnasium.envs.registration.register", "gym.register"}:
            self.registration(mod, node)
        if node.args and self.roles(callee) & set(TERMS.values()):
            self.check_binding(mod, node.args[0], callee)
        for kw in node.keywords:
            if kw.arg in RESOURCE_FIELDS and (framework(callee) or self.family(mod)):
                try:
                    check_resource(self.index, mod, kw.value)
                except Unresolved as exc:
                    self.report(mod, kw.value, "ORG005", f"{ast.unparse(kw.value)}: {exc}")
            if kw.arg in COMPONENT_FIELDS and framework(callee):
                self.composition(mod, kw.value)
            if kw.arg in {"func", "function", "class_type"}:
                roles = self.roles(callee)
                if roles or self.family(mod) or framework(callee):
                    self.check_binding(mod, kw.value, callee)

    def run(self):
        # Imports from outside src may discover more in-repository modules.
        scanned = set()
        while remaining := sorted(self.index.modules.keys() - scanned):
            for module in remaining:
                scanned.add(module)
                mod = self.index.modules[module]
                for node in ast.walk(mod.tree):
                    if isinstance(node, ast.ClassDef):
                        self.check_class(mod, node)
                    elif isinstance(node, ast.Call):
                        self.check_call(mod, node)
                    elif self.family(mod) and isinstance(node, ast.Assign):
                        for target in node.targets:
                            self.reassignment(mod, target, node.value)
        for name in self.term_classes - self.bound_terms:
            mod, node = self.index.defs[name]
            family = self.family(mod)
            roles = self.roles(name)
            if family and any(
                mod.path.is_relative_to(family / "mdp" / role)
                or mod.path in {family / "mdp" / (role + ".py"), family / "mdp" / (role + "_cfg.py")}
                for role in roles or TERMS.values()
            ):
                continue
            self.report(mod, node, "ORG004", f"{name}: term definition belongs in its task's MDP role module")
