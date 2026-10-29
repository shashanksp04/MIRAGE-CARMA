"""Load pure existing definitions without importing the GPU/network stack.

These characterization tests execute repository method bodies, not replacements
of the algorithms. Integration with installed dependencies is checked on cluster.
"""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def definitions(path, names, namespace=None):
    tree = ast.parse((ROOT / path).read_text())
    tree.body = [node for node in tree.body if getattr(node, "name", None) in names]
    future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
    tree.body.insert(0, future)
    ast.fix_missing_locations(tree)
    scope = {"__file__": str(ROOT / path), "__package__": str(Path(path).parent).replace("/", "."),
             **(namespace or {})}
    exec(compile(tree, str(ROOT / path), "exec"), scope)
    return scope
