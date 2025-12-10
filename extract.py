import time
import os
import ast
from pathlib import Path
import NodeCollector
import json

def _module_name_from_path(filepath, package_root):
    """
    Optional helper: derive module name from the file path.
    - filepath: e.g. "/root/project/pkg/subpkg/mod.py"
    - package_root: e.g. "/root/project" or "/root/project/pkg"
    """
    if package_root is None:
        return None

    root = Path(package_root).resolve()
    file = Path(filepath).resolve()
    rel = file.relative_to(root).with_suffix("")  # strip .py
    return ".".join(rel.parts)

def extract_ast_nodes(filepath, package_root: str | None = None):
    with open(filepath, "r", encoding="utf-8") as source:
        code = source.read()

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return

    module_name = _module_name_from_path(filepath, package_root)
    collector = NodeCollector.NodeCollector(module_name=module_name)
    collector.visit(tree)

    return {filepath: collector.result}
    

def extract(pkgstr: str, dir:str):
    seen_namespaces = set()
    result = {}


    # TODO: use os.walk to go through each file
    # for each file, use AST and get components

    start = time.time()
    for root, _, files in os.walk(dir):
        for filename in files:
            if not filename.endswith(".py"):
                continue
            path = os.path.join(root, filename ) #filename
            qualified_file_name = _derive_module_namespace(pkgstr, dir, filename) #qualified name
            if qualified_file_name not in seen_namespaces:
                seen_namespaces.add(qualified_file_name)
                # nodes.Namespaces.append(qualified_name) # TODO: Change this to QName instead of namespaces
                nodes_dict = extract_ast_nodes(path)
                if nodes_dict:
                    result.update(nodes_dict)

            
    

    elapsed = time.time() - start
    return result, elapsed


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

    res, elapsed = extract(pkg, work_dir)
    json_output = json.dumps(res, indent=2)
    # print(json_output)
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