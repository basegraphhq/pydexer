import time
import os
import ast

def _get_node_kind(node: ast.AST) -> str:
    """
    Map AST node types to human-readable kinds.
    Returns a short kind string for nodes we care about, or "statement" for others.
    """
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

def extract_ast_nodes(filepath):
    """Extract selected AST nodes (filtered by kind) with their positions"""
    with open(filepath, "r", encoding="utf-8") as source:
        code = source.read()

    result = {}
    try:
        program = ast.parse(code)
        for node in ast.walk(program):
            kind = _get_node_kind(node)
            if kind == "skip_node":
                continue  # skip nodes we don't map explicitly
            if not hasattr(node, "name"):
                continue

            # has the following attributes
            # ('lineno', 'col_offset', 'end_lineno', 'end_col_offset')
            # TODO: figure out where the "name" attribute is coming from and find qualified_name
            
            node_type = type(node).__name__
            start_line = getattr(node, "lineno", None)
            end_line = getattr(node, "end_lineno", None)
            name = getattr(node, "name", None)

            # # Prefer a readable key: use `name` for classes/functions, otherwise node type + start line
            # key = f"{node_type}:{node.name}"
            key = name
            result[key] = {
                "kind": node_type,
                "name": name,
                "pos": {"start": start_line, "end": end_line},
            }

        return {filepath: result}
    except SyntaxError:
        return
    

def extract(pkgstr: str, dir:str):
    seen_namespaces = set()


    # TODO: use os.walk to go through each file
    # for each file, use AST and get components

    start = time.time()
    for root, _, files in os.walk(dir):
        for filename in files:
            if not filename.endswith(".py"):
                continue
            path = os.path.join(root, filename ) #filename
            qualified_name = _derive_module_namespace(pkgstr, dir, filename) #qualified name
            if qualified_name not in seen_namespaces:
                seen_namespaces.add(qualified_name)
                # nodes.Namespaces.append(qualified_name) # TODO: Change this to QName instead of namespaces

            nodes_dict = extract_ast_nodes(path)
            print(nodes_dict)
    

    elapsed = time.time() - start
    return elapsed


def _derive_module_namespace(pkgstr: str, dir_path: str, file_path: str) -> str:
    rel = os.path.relpath(file_path, dir_path)
    if rel.endswith(".py"):
        rel = rel[: -len(".py")]
    rel = rel.replace(os.sep, ".")
    if rel.endswith(".__init__"):
        rel = rel[: -len(".__init__")]
    rel = rel.strip(".")
    if pkgstr:
        if rel:
            return f"{pkgstr}.{rel}"
        return pkgstr
    return rel

def extract_cli() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Extract Python codegraph")
    parser.add_argument("--pkg", dest="pkg", default="", help="Package/module prefix (e.g. github.com/org/repo)")
    parser.add_argument("--dir", dest="dir", default=".", help="Root directory to walk (ignored if --repo set)")
    parser.add_argument("--repo", dest="repo", default="", help="Git repo URL to clone and index")
    parser.add_argument("--ref", dest="ref", default="", help="Git ref (branch/tag/sha) to checkout when cloning")
    parser.add_argument(
        "--keep-clone",
        dest="keep_clone",
        action="store_true",
        help="Keep the cloned repository directory (default: delete)",
    )
    parser.add_argument(
        "--out",
        dest="out",
        default="output/output.json",
        help="Path to write JSON output (default: output/output.json)",
    )
    args = parser.parse_args()

    work_dir = args.dir
    cloned_dir = ""
    pkg = args.pkg

    # if args.repo:
    #     cloned_dir = _clone_repo(args.repo, args.ref or None)
    #     work_dir = cloned_dir
    #     if not pkg:
    #         pkg = _pkg_from_repo_url(args.repo)

    elapsed = extract(pkg, work_dir)
    # out_path = args.out
    # out_dir = os.path.dirname(out_path) or "."
    # os.makedirs(out_dir, exist_ok=True)
    # with open(out_path, "w", encoding="utf-8") as f:
    #     json.dump({"nodes": nodes.to_dict(), "relations": rels.to_dict()}, f, indent=2)
    # print(f"Wrote results to {out_path}")

    # if cloned_dir and not args.keep_clone:
    #     shutil.rmtree(cloned_dir, ignore_errors=True)
    print(f"Total time elapsed: {elapsed}")



if __name__ == "__main__":
    extract_cli()