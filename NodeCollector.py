import ast
from typing import Dict, Any, Optional


def _get_node_kind(node: ast.AST) -> str:
    kind_map = {
        ast.ClassDef: "class",
        ast.FunctionDef: "function",
        ast.AsyncFunctionDef: "async_function",
        ast.For: "for_loop",
        ast.While: "while_loop",
        ast.If: "if_statement",
        ast.Try: "try_statement",
        ast.With: "with_statement",
        ast.AsyncWith: "async_with_statement",
        ast.AsyncFor: "async_for_loop",
        ast.ListComp: "list_comprehension",
        ast.DictComp: "dict_comprehension",
        ast.SetComp: "set_comprehension",
        ast.GeneratorExp: "generator_expression",
        ast.Lambda: "lambda",
        ast.Return: "return_statement",
        ast.Yield: "yield_statement",
        ast.YieldFrom: "yield_from_statement",
        ast.Raise: "raise_statement",
        ast.Assert: "assert_statement",
        ast.Break: "break_statement",
        ast.Continue: "continue_statement",
        ast.Pass: "pass_statement",
    }
    return kind_map.get(type(node), "skip_node")


class NodeCollector(ast.NodeVisitor):
    def __init__(self, module_name: Optional[str] = None):
        # Optional: logical module name (e.g. "pkg.subpkg.mod")
        self.module_name = module_name

        # scope stack holds *qualified* names of enclosing class/func scopes
        # e.g. ["pkg.mod.A", "pkg.mod.A.f"]
        self.scope_stack: list[str] = []

        # final result: key -> metadata
        self.result: Dict[str, Dict[str, Any]] = {}

    # ---------- helpers ----------

    def _current_scope_qual(self) -> Optional[str]:
        """Return qualname of current scope, or None at top level."""
        return self.scope_stack[-1] if self.scope_stack else None

    def _make_qualname(self, name: str) -> str:
        """Build a qualified name for a new named scope."""
        parent = self._current_scope_qual()
        if parent is None:
            # top-level class/function
            if self.module_name:
                # if you prefer including module: return f"{self.module_name}.{name}"
                return f"{self.module_name}.{name}"
            return name
        return f"{parent}.{name}"

    def _pos_dict(self, node: ast.AST) -> Dict[str, Optional[int]]:
        return {
            "start": getattr(node, "lineno", None),
            "end": getattr(node, "end_lineno", None),
        }

    def _make_synthetic_key(self, node: ast.AST, kind: str) -> str:
        """
        Create a stable-ish key for unnamed nodes, based on parent scope,
        kind, and position.
        """
        parent = self._current_scope_qual() or "<module>"
        line = getattr(node, "lineno", 0)
        col = getattr(node, "col_offset", 0)
        return f"{parent}:{kind}"

    def _record_named_node(self, node: ast.AST, kind: str):
        """
        Record nodes that have a .name: ClassDef, FunctionDef, AsyncFunctionDef.
        """
        raw_name = getattr(node, "name", None)
        if raw_name is None:
            return

        qualified_name = self._make_qualname(raw_name)
        parent_qual = self._current_scope_qual()

        key = qualified_name  # natural choice for named nodes

        self.result[key] = {
            "kind": kind,                       # your human-readable kind
            "ast_type": type(node).__name__,   # exact AST type
            "name": raw_name,
            "qualified_name": qualified_name,
            "parent_qualified_name": parent_qual,
            "pos": self._pos_dict(node),
        }

    def _record_unnamed_node(self, node: ast.AST, kind: str):
        """
        Record nodes without a .name (loops, returns, etc.).
        """
        parent_qual = self._current_scope_qual()
        key = self._make_synthetic_key(node, kind)

        self.result[key] = {
            "kind": kind,
            "ast_type": type(node).__name__,
            "name": None,
            "qualified_name": None,
            "parent_qualified_name": parent_qual,
            "pos": self._pos_dict(node),
        }

    # ---------- named scopes ----------

    def visit_ClassDef(self, node: ast.ClassDef):
        kind = _get_node_kind(node)  # "class"
        self._record_named_node(node, kind)

        # descend with extended scope
        qual = self._make_qualname(node.name)
        self.scope_stack.append(qual)
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef):
        kind = _get_node_kind(node)  # "function"
        self._record_named_node(node, kind)

        qual = self._make_qualname(node.name)
        self.scope_stack.append(qual)
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        kind = _get_node_kind(node)  # "async_function"
        self._record_named_node(node, kind)

        qual = self._make_qualname(node.name)
        self.scope_stack.append(qual)
        self.generic_visit(node)
        self.scope_stack.pop()

    # ---------- control-flow statements ----------

    def visit_For(self, node: ast.For):
        kind = _get_node_kind(node)  # "for_loop"
        self._record_unnamed_node(node, kind)
        self.generic_visit(node)

    def visit_AsyncFor(self, node: ast.AsyncFor):
        kind = _get_node_kind(node)  # "async_for_loop"
        self._record_unnamed_node(node, kind)
        self.generic_visit(node)

    def visit_While(self, node: ast.While):
        kind = _get_node_kind(node)  # "while_loop"
        self._record_unnamed_node(node, kind)
        self.generic_visit(node)

    def visit_If(self, node: ast.If):
        kind = _get_node_kind(node)  # "if_statement"
        self._record_unnamed_node(node, kind)
        self.generic_visit(node)

    def visit_Try(self, node: ast.Try):
        kind = _get_node_kind(node)  # "try_statement"
        self._record_unnamed_node(node, kind)
        self.generic_visit(node)

    def visit_With(self, node: ast.With):
        kind = _get_node_kind(node)  # "with_statement"
        self._record_unnamed_node(node, kind)
        self.generic_visit(node)

    def visit_AsyncWith(self, node: ast.AsyncWith):
        kind = _get_node_kind(node)  # "async_with_statement"
        self._record_unnamed_node(node, kind)
        self.generic_visit(node)

    # ---------- expressions / comprehensions / lambdas ----------

    def visit_ListComp(self, node: ast.ListComp):
        kind = _get_node_kind(node)  # "list_comprehension"
        self._record_unnamed_node(node, kind)
        self.generic_visit(node)

    def visit_DictComp(self, node: ast.DictComp):
        kind = _get_node_kind(node)  # "dict_comprehension"
        self._record_unnamed_node(node, kind)
        self.generic_visit(node)

    def visit_SetComp(self, node: ast.SetComp):
        kind = _get_node_kind(node)  # "set_comprehension"
        self._record_unnamed_node(node, kind)
        self.generic_visit(node)

    def visit_GeneratorExp(self, node: ast.GeneratorExp):
        kind = _get_node_kind(node)  # "generator_expression"
        self._record_unnamed_node(node, kind)
        self.generic_visit(node)

    def visit_Lambda(self, node: ast.Lambda):
        kind = _get_node_kind(node)  # "lambda"
        self._record_unnamed_node(node, kind)
        self.generic_visit(node)

    # ---------- simple statements / flow control ----------

    def visit_Return(self, node: ast.Return):
        kind = _get_node_kind(node)  # "return_statement"
        self._record_unnamed_node(node, kind)
        self.generic_visit(node)

    def visit_Yield(self, node: ast.Yield):
        kind = _get_node_kind(node)  # "yield_statement"
        self._record_unnamed_node(node, kind)
        self.generic_visit(node)

    def visit_YieldFrom(self, node: ast.YieldFrom):
        kind = _get_node_kind(node)  # "yield_from_statement"
        self._record_unnamed_node(node, kind)
        self.generic_visit(node)

    def visit_Raise(self, node: ast.Raise):
        kind = _get_node_kind(node)  # "raise_statement"
        self._record_unnamed_node(node, kind)
        self.generic_visit(node)

    def visit_Assert(self, node: ast.Assert):
        kind = _get_node_kind(node)  # "assert_statement"
        self._record_unnamed_node(node, kind)
        self.generic_visit(node)

    def visit_Break(self, node: ast.Break):
        kind = _get_node_kind(node)  # "break_statement"
        self._record_unnamed_node(node, kind)
        # no children to visit

    def visit_Continue(self, node: ast.Continue):
        kind = _get_node_kind(node)  # "continue_statement"
        self._record_unnamed_node(node, kind)
        # no children to visit

    def visit_Pass(self, node: ast.Pass):
        kind = _get_node_kind(node)  # "pass_statement"
        self._record_unnamed_node(node, kind)
        # no children to visit
