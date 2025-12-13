import ast
from typing import Dict, Any, Optional, List, Union
from rel_types import RelType, KIND_TO_REL, rel_to_str

def _get_node_kind(node: ast.AST) -> str:
    kind_map = {
        ast.ClassDef: "class",
        ast.FunctionDef: "function",
        ast.AsyncFunctionDef: "async_function",
        ast.Return: "returns",
        ast.Yield: "yields",
        ast.YieldFrom: "yields",
        ast.Import: "import",
        ast.ImportFrom: "import",
        ast.Assign: "assignment",
        ast.AugAssign: "augmented_assignment",
    }
    return kind_map.get(type(node), "skip_node")


class NodeCollector(ast.NodeVisitor):
    def __init__(self, module_name: Optional[str] = None, source_file: Optional[str] = None):
        self.module_name = module_name
        self.source_file = source_file
        self.scope_stack: list[str] = []
        self.scope_kinds: list[str] = []
        self.result: Dict[str, Dict[str, Any]] = {}

        # NEW: counter for synthetic nodes so keys don't need line/col
        self._synthetic_counters: Dict[tuple[str, str], int] = {}

    # ---------- helpers ----------

    def _make_base_meta(
        self,
        qualified_name: str,
        parent_qualified_name: Optional[str],
        *,
        name: Optional[str] = None,
        kind: Optional[str] = None,
        ast_type: Optional[str] = None,
        pos: Optional[Dict[str, Optional[int]]] = None,
        annotation: Optional[str] = None,
        modifier: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return canonical meta dict with all canonical fields present."""
        if pos is None:
            pos = {"start": None, "end": None}
        return {
            "name": name,
            "kind": kind,
            "ast_type": ast_type,
            "pos": pos,
            "qualified_name": qualified_name,
            "parent_qualified_name": parent_qualified_name,
            "annotation": annotation,
            "modifier": modifier,
            "docstring": None,
            "relations": [],
        }


    def _current_scope_qual(self) -> Optional[str]:
        """Return qualname of current scope, or None at top level."""
        return self.scope_stack[-1] if self.scope_stack else None

    def _make_qualname(self, name: str) -> str:
        """Build a qualified name for a new named scope."""
        parent = self._current_scope_qual()
        if parent is None:
            if self.module_name:
                return f"{self.module_name}.{name}"
            return name
        return f"{parent}.{name}"

    def _pos_dict(self, node: ast.AST) -> Dict[str, Optional[int]]:
        return {
            "start": getattr(node, "lineno", None),
            "end": getattr(node, "end_lineno", None),
        }

    def _current_scope_kind(self) -> Optional[str]:
        return self.scope_kinds[-1] if self.scope_kinds else None

    def _current_class_scope(self) -> Optional[str]:
        for qual, kind in reversed(list(zip(self.scope_stack, self.scope_kinds))):
            if kind == "class":
                return qual
        return None

    def _current_callable_scope(self) -> Optional[str]:
        for qual, kind in reversed(list(zip(self.scope_stack, self.scope_kinds))):
            if kind in {"function", "async_function"}:
                return qual
        return None

    def _push_scope(self, qual: str, kind: str):
        self.scope_stack.append(qual)
        self.scope_kinds.append(kind)

    def _pop_scope(self):
        if self.scope_stack:
            self.scope_stack.pop()
        if self.scope_kinds:
            self.scope_kinds.pop()

    def _expr_to_name(self, expr: Optional[ast.AST]) -> Optional[str]:
        """Return a compact, readable name for an expression, or None."""
        if expr is None:
            return None
        # simple name or attribute
        try:
            if isinstance(expr, ast.Name):
                return expr.id
            if isinstance(expr, ast.Attribute):
                return self._extract_call_name(expr)
            # constants: show value shorthand
            if isinstance(expr, ast.Constant):
                return repr(expr.value)
            # subsume calls, subscripts, etc. into an unparse fallback
            try:
                return ast.unparse(expr)
            except Exception:
                return None
        except Exception:
            return None
        
    def _make_synthetic_key(self, node: ast.AST, kind: str) -> str:
        """
        Create a stable key for unnamed nodes.

        Strategy:
        - If the node has an obvious name (Assign/AugAssign) use that name.
        - For Return nodes use the returned-expression text when available, or "null" if returning nothing.
        - For Yield nodes use "yield".
        - Otherwise fall back to the node's line number for stability.
        """
        parent = self._current_scope_qual() or self.module_name or self.source_file or "<unknown>"

        # Try to extract a name-like part
        try:
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        return f"{parent}.{kind}.{t.id}"
            if isinstance(node, ast.AugAssign):
                if isinstance(node.target, ast.Name):
                    return f"{parent}.{kind}.{node.target.id}"
            if isinstance(node, ast.Return):
                # prefer the returned-expression string; use literal "null" when no value
                name_part = self._expr_to_name(node.value)
                if name_part is None:
                    if node.value is None:
                        name_part = "null"
                    else:
                        # fallback to line number if we couldn't name the expression
                        name_part = str(getattr(node, "lineno", 0))
                return f"{parent}.{kind}.{name_part}"
            if isinstance(node, (ast.Yield, ast.YieldFrom)):
                return f"{parent}.{kind}.yield"
        except Exception:
            pass

        lineno = getattr(node, "lineno", None) or 0
        return f"{parent}.{kind}.{lineno}"


    def _set_relation(self, meta: Dict[str, Any], source: Optional[str], rel_type: Optional[Union[RelType, str]], target: Optional[str], pos: Optional[Dict[str, Optional[int]]] = None):
        """Append a relation to the meta's relations list."""
        if not source or not target or rel_type is None:
            return
        rel_str = rel_to_str(rel_type)
        if rel_str is None:
            return
        meta["relations"].append({
            "source": source,
            "rel_type": rel_str,
            "target": target,
            "pos": pos or {"start": None, "end": None},
        })




    # ---------- recording helpers ----------

    def _record_named_node(self, node: ast.AST, kind: str):
        raw_name = getattr(node, "name", None)
        if raw_name is None:
            return

        qualified_name = self._make_qualname(raw_name)
        parent_qual = self._current_scope_qual() or self.module_name

        meta = self._make_base_meta(
            qualified_name=qualified_name,
            parent_qualified_name=parent_qual,
            name=raw_name,
            kind=kind,
            ast_type=type(node).__name__,
            pos=self._pos_dict(node),
            annotation=None,
            modifier=None,
        )

        meta["docstring"] = self._extract_docstring(node)

        rel_type = None
        if kind == "class":
            rel_type = RelType.CLASS_DEF
        elif kind in {"function", "async_function"}:
            rel_type = RelType.FUNCTION_DEF

        if rel_type:
            self._set_relation(meta, source=qualified_name, rel_type=rel_type, target=parent_qual, pos=meta["pos"])

        self.result[qualified_name] = meta



    def _record_unnamed_node(self, node: ast.AST, kind: str):
        if kind == "skip_node":
            return
        parent_qual = self._current_scope_qual() or self.module_name
        key = self._make_synthetic_key(node, kind)
        meta = self._make_base_meta(
            qualified_name=key,
            parent_qualified_name=parent_qual,
            name=None,
            kind=kind,
            ast_type=type(node).__name__,
            pos=self._pos_dict(node),
            annotation=None,
            modifier=None,
        )
        self.result[key] = meta


    def _record_import_node(self, node: ast.AST, module: str, alias: Optional[str]):
        name = alias or module
        # Use qualified name so the key is file-prefixed / scope-prefixed
        key = self._make_qualname(name)
        parent_qual = self._current_scope_qual() or self.module_name

        meta = self._make_base_meta(
            qualified_name=key,
            parent_qualified_name=parent_qual,
            name=name,
            kind="import",
            ast_type=type(node).__name__,
            pos=self._pos_dict(node),
            annotation=None,
            modifier=None,
        )
        self._set_relation(meta, source=key, rel_type=RelType.IMPORTS, target=parent_qual, pos=meta["pos"])
        self.result[key] = meta



    def _record_param_node(self, func_qual: str, arg: ast.arg, modifier: str = ""):
        param_name = getattr(arg, "arg", None)
        if not param_name:
            return
        key = f"{func_qual}.param.{param_name}"
        annotation = None
        if getattr(arg, "annotation", None) is not None:
            try:
                annotation = ast.unparse(arg.annotation)
            except Exception:
                annotation = None

        meta = self._make_base_meta(
            qualified_name=key,
            parent_qualified_name=func_qual,
            name=param_name,
            kind="params_of",
            ast_type="arg",
            pos={"start": getattr(arg, "lineno", None), "end": getattr(arg, "end_lineno", None)},
            annotation=annotation,
            modifier=modifier or None,
        )
        self._set_relation(meta, source=key, rel_type=RelType.PARAM_OF, target=func_qual, pos=meta["pos"])
        self.result[key] = meta


    def _record_return_node(self, func_qual: str, node: ast.AST):
        if getattr(node, "returns", None) is None:
            return
        try:
            return_type = ast.unparse(node.returns)
        except Exception:
            return_type = None

        key = f"{func_qual}.return"
        meta = self._make_base_meta(
            qualified_name=key,
            parent_qualified_name=func_qual,
            name=return_type,
            kind="returns",
            ast_type=type(node.returns).__name__ if node.returns is not None else "NoneType",
            pos=self._pos_dict(node.returns),
            annotation=None,
            modifier=None,
        )
        self._set_relation(meta, source=key, rel_type=RelType.RETURNS, target=func_qual, pos=meta["pos"])
        self.result[key] = meta


    def _record_function_relationships(self, func_qual: str):
        # Intentionally minimal: no extra relationships beyond definition edges
        return
    
    def _extract_docstring(self, node):
        """Extract docstring from the first statement if it's a string constant."""
        if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str):
            return node.body[0].value.value
        return None

    def _extract_call_name(self, func: ast.AST) -> Optional[str]:
        if isinstance(func, ast.Name):
            return func.id
        if isinstance(func, ast.Attribute):
            parts: List[str] = []
            current = func
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            base: Optional[str] = None
            if isinstance(current, ast.Name):
                base = current.id
            else:
                try:
                    base = ast.unparse(current)
                except Exception:
                    base = None

            if base in {"self", "cls"}:
                class_scope = self._current_class_scope()
                if class_scope:
                    base = class_scope
            if base is None:
                return None
            parts.append(base)
            parts.reverse()
            return ".".join(parts)
        try:
            return ast.unparse(func)
        except Exception:
            return None

    # ---------- named scopes ----------

    def visit_ClassDef(self, node: ast.ClassDef):
        kind = _get_node_kind(node)  # "class"
        self._record_named_node(node, kind)

        qual = self._make_qualname(node.name)
        # Add inheritance relations
        for base in node.bases:
            base_name = self._extract_call_name(base)
            if base_name:
                self._set_relation(self.result[qual], source=qual, rel_type=RelType.INHERITS_FROM, target=base_name, pos=self._pos_dict(node))
        # Add decorator relations
        for decorator in node.decorator_list:
            decorator_name = self._extract_call_name(decorator)
            if decorator_name:
                self._set_relation(self.result[qual], source=qual, rel_type=RelType.DECORATED_BY, target=decorator_name, pos=self._pos_dict(decorator))
        self._push_scope(qual, kind)
        self.generic_visit(node)
        self._pop_scope()

    def visit_FunctionDef(self, node: ast.FunctionDef):
        kind = _get_node_kind(node)  # "function"
        self._record_named_node(node, kind)

        qual = self._make_qualname(node.name)
        self._record_function_relationships(qual)
        for arg in node.args.posonlyargs:
            self._record_param_node(qual, arg, modifier="posonly")
        for arg in node.args.args:
            self._record_param_node(qual, arg)
        if node.args.vararg:
            self._record_param_node(qual, node.args.vararg, modifier="vararg")
        for arg in node.args.kwonlyargs:
            self._record_param_node(qual, arg, modifier="kwonly")
        if node.args.kwarg:
            self._record_param_node(qual, node.args.kwarg, modifier="kwarg")
        self._record_return_node(qual, node)
        # Add decorator relations
        for decorator in node.decorator_list:
            decorator_name = self._extract_call_name(decorator)
            if decorator_name:
                self._set_relation(self.result[qual], source=qual, rel_type=RelType.DECORATED_BY, target=decorator_name, pos=self._pos_dict(decorator))
        self._push_scope(qual, kind)
        self.generic_visit(node)
        self._pop_scope()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        kind = _get_node_kind(node)  # "async_function"
        self._record_named_node(node, kind)

        qual = self._make_qualname(node.name)
        self._record_function_relationships(qual)
        for arg in node.args.posonlyargs:
            self._record_param_node(qual, arg, modifier="posonly")
        for arg in node.args.args:
            self._record_param_node(qual, arg)
        if node.args.vararg:
            self._record_param_node(qual, node.args.vararg, modifier="vararg")
        for arg in node.args.kwonlyargs:
            self._record_param_node(qual, arg, modifier="kwonly")
        if node.args.kwarg:
            self._record_param_node(qual, node.args.kwarg, modifier="kwarg")
        self._record_return_node(qual, node)
        # Add decorator relations
        for decorator in node.decorator_list:
            decorator_name = self._extract_call_name(decorator)
            if decorator_name:
                self._set_relation(self.result[qual], source=qual, rel_type=RelType.DECORATED_BY, target=decorator_name, pos=self._pos_dict(decorator))
        self._push_scope(qual, kind)
        self.generic_visit(node)
        self._pop_scope()

    # ---------- assignments ----------

    def visit_Assign(self, node: ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name):
                parent = self._current_scope_qual() or self.module_name
                key = f"{parent}.asignment.{target.id}"
                meta = self._make_base_meta(
                    qualified_name=key,
                    parent_qualified_name=self._current_scope_qual() or self.module_name,
                    name=target.id,
                    kind="assignment",
                    ast_type="Assign",
                    pos=self._pos_dict(node),
                )
                self._set_relation(meta, source=key, rel_type=RelType.ASSIGNS, target=self._current_scope_qual() or self.module_name, pos=meta["pos"])
                self.result[key] = meta
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign):
        if isinstance(node.target, ast.Name):
            parent = self._current_scope_qual() or self.module_name
            key = f"{parent}.augmented_assignment.{node.target.id}"
            meta = self._make_base_meta(
                qualified_name=key,
                parent_qualified_name=self._current_scope_qual() or self.module_name,
                name=node.target.id,
                kind="augmented_assignment",
                ast_type="AugAssign",
                pos=self._pos_dict(node),
            )
            self._set_relation(meta, source=key, rel_type=RelType.ASSIGNS, target=self._current_scope_qual() or self.module_name, pos=meta["pos"])
            self.result[key] = meta
        self.generic_visit(node)

    # ---------- control-flow statements ----------

    def visit_For(self, node: ast.For):
        kind = _get_node_kind(node)  # currently "skip_node" unless added to kind_map
        self._record_unnamed_node(node, kind)
        self.generic_visit(node)

    def visit_AsyncFor(self, node: ast.AsyncFor):
        kind = _get_node_kind(node)
        self._record_unnamed_node(node, kind)
        self.generic_visit(node)

    def visit_While(self, node: ast.While):
        kind = _get_node_kind(node)
        self._record_unnamed_node(node, kind)
        self.generic_visit(node)

    def visit_If(self, node: ast.If):
        kind = _get_node_kind(node)
        self._record_unnamed_node(node, kind)
        self.generic_visit(node)

    def visit_Try(self, node: ast.Try):
        kind = _get_node_kind(node)
        self._record_unnamed_node(node, kind)
        self.generic_visit(node)

    def visit_With(self, node: ast.With):
        kind = _get_node_kind(node)
        self._record_unnamed_node(node, kind)
        self.generic_visit(node)

    def visit_AsyncWith(self, node: ast.AsyncWith):
        kind = _get_node_kind(node)
        self._record_unnamed_node(node, kind)
        self.generic_visit(node)

    # ---------- expressions / comprehensions / lambdas ----------

    def visit_ListComp(self, node: ast.ListComp):
        kind = _get_node_kind(node)
        self._record_unnamed_node(node, kind)
        self.generic_visit(node)

    def visit_DictComp(self, node: ast.DictComp):
        kind = _get_node_kind(node)
        self._record_unnamed_node(node, kind)
        self.generic_visit(node)

    def visit_SetComp(self, node: ast.SetComp):
        kind = _get_node_kind(node)
        self._record_unnamed_node(node, kind)
        self.generic_visit(node)

    def visit_GeneratorExp(self, node: ast.GeneratorExp):
        kind = _get_node_kind(node)
        self._record_unnamed_node(node, kind)
        self.generic_visit(node)

    def visit_Lambda(self, node: ast.Lambda):
        kind = _get_node_kind(node)
        self._record_unnamed_node(node, kind)
        self.generic_visit(node)

    # ---------- imports ----------

    def visit_Import(self, node: ast.Import):
        kind = _get_node_kind(node)  # "import"
        for alias in node.names:
            self._record_import_node(node, alias.name, alias.asname)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        kind = _get_node_kind(node)  # "import"
        module = node.module or ""
        for alias in node.names:
            target = f"{module}.{alias.name}" if module else alias.name
            self._record_import_node(node, target, alias.asname)
        self.generic_visit(node)

    # ---------- simple statements / flow control ----------

    def visit_Return(self, node: ast.Return):
        kind = _get_node_kind(node)
        if kind == "returns":
            func_qual = self._current_callable_scope()
            # compute a key that includes the returned-expression (or "null")
            key = self._make_synthetic_key(node, kind)
            returned_name = self._expr_to_name(node.value)  # None when no value or not nameable
            meta = self._make_base_meta(
                qualified_name=key,
                parent_qualified_name=func_qual or self.module_name,
                name=returned_name,
                kind=kind,
                ast_type=type(node).__name__,
                pos=self._pos_dict(node),
                annotation=None,
                modifier=None,
            )
            self._set_relation(meta, source=key, rel_type=RelType.RETURNS, target=func_qual, pos=meta["pos"])
            self.result[key] = meta
        self.generic_visit(node)

    def visit_Yield(self, node: ast.Yield):
        kind = _get_node_kind(node)
        if kind == "yields":
            func_qual = self._current_callable_scope()
            key = self._make_synthetic_key(node, kind)
            meta = self._make_base_meta(
                qualified_name=key,
                parent_qualified_name=func_qual or self.module_name,
                name=None,
                kind=kind,
                ast_type=type(node).__name__,
                pos=self._pos_dict(node),
                annotation=None,
                modifier=None,
            )
            self._set_relation(meta, source=key, rel_type=RelType.YIELDS, target=func_qual, pos=meta["pos"])
            self.result[key] = meta
        self.generic_visit(node)


    def visit_YieldFrom(self, node: ast.YieldFrom):
        kind = _get_node_kind(node)
        if kind == "yields":
            func_qual = self._current_callable_scope()
            key = self._make_synthetic_key(node, kind)
            meta = self._make_base_meta(
                qualified_name=key,
                parent_qualified_name=func_qual or self.module_name,
                name=None,
                kind=kind,
                ast_type=type(node).__name__,
                pos=self._pos_dict(node),
                annotation=None,
                modifier=None,
            )
            self._set_relation(meta, source=key, rel_type=RelType.YIELDS, target=func_qual, pos=meta["pos"])
            self.result[key] = meta
        self.generic_visit(node)

    def visit_Raise(self, node: ast.Raise):
        kind = _get_node_kind(node)  # currently "skip_node"
        self._record_unnamed_node(node, kind)
        self.generic_visit(node)

    def visit_Assert(self, node: ast.Assert):
        kind = _get_node_kind(node)  # currently "skip_node"
        self._record_unnamed_node(node, kind)
        self.generic_visit(node)

    def visit_Break(self, node: ast.Break):
        kind = _get_node_kind(node)
        self._record_unnamed_node(node, kind)
        # no children to visit

    def visit_Continue(self, node: ast.Continue):
        kind = _get_node_kind(node)
        self._record_unnamed_node(node, kind)
        # no children to visit

    def visit_Pass(self, node: ast.Pass):
        kind = _get_node_kind(node)
        self._record_unnamed_node(node, kind)
        # no children to visit

    def visit_Call(self, node: ast.Call):
        caller = self._current_callable_scope()
        callee = self._extract_call_name(node.func)
        if caller and callee:
            pos = self._pos_dict(node)
            self._set_relation(self.result[caller], source=caller, rel_type=RelType.CALLS, target=callee, pos=pos)
            if callee in self.result:
                self._set_relation(self.result[callee], source=callee, rel_type=RelType.CALLED_BY, target=caller, pos=pos)
        self.generic_visit(node)