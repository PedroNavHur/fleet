"""Score GDScript functions with gdtoolkit's parser; see complexity_core.py.

Usage: python complexity_gdscript.py FILE...   (prints JSON)

Run it with a Python that has gdtoolkit 4 installed (a Godot repository's
lint virtualenv, or `pip install "gdtoolkit==4.*"`). Language mappings:
- `elif` is an else-if (+1 flat); `else` is +1 flat.
- `match` is one structural increment; each non-wildcard branch is a
  cyclomatic decision, and a `when` guard adds 1 to both metrics.
- `and`/`&&` and `or`/`||` are the same operators; `not` ends a chain.
- Lambdas nest like any nested function; property getters and setters score
  as their own functions.
- Recursion: a call to the function's own name, or `self.` plus that name.
"""

from __future__ import annotations

import sys

from complexity_core import Scorer, emit, operator_runs

BOOLEAN = {"or_test": "or", "asless_or_test": "or", "and_test": "and", "asless_and_test": "and"}
TERNARY = {"test_expr", "asless_test_expr"}
LOOPS = {"for_stmt", "for_stmt_typed", "while_stmt"}


def is_tree(node) -> bool:
    return hasattr(node, "data")


def token_text(node) -> str:
    return str(node) if not is_tree(node) else ""


def end_line(node) -> int:
    lines = [getattr(token, "end_line", None) or token.line for token in node.scan_values(lambda v: hasattr(v, "line"))]
    return max(lines, default=node.meta.line)


def first_name(node) -> str:
    for child in node.children:
        if not is_tree(child) and child.type == "NAME":
            return str(child)
    return "<anonymous>"


class Analyzer:
    def __init__(self):
        self.scorer = Scorer()
        self.seen_boolean: set[int] = set()
        self.classes: list[str] = []

    def walk(self, node) -> None:
        if not is_tree(node):
            return
        handler = getattr(self, f"visit_{node.data}", None)
        if handler:
            handler(node)
        elif node.data in LOOPS:
            self.visit_loop(node)
        elif node.data in BOOLEAN:
            self.visit_boolean(node)
        elif node.data in TERNARY:
            self.visit_ternary(node)
        else:
            self.children(node)

    def children(self, node) -> None:
        for child in node.children:
            self.walk(child)

    def nested_children(self, children) -> None:
        with self.scorer.nested():
            for child in children:
                self.walk(child)

    # Functions and classes

    def visit_class_def(self, node) -> None:
        self.classes.append(first_name(node))
        self.children(node)
        self.classes.pop()

    def function(self, node, name: str, body) -> None:
        in_class = not self.scorer.active
        qualified = ".".join([*self.classes, name]) if in_class and self.classes else name
        own = (name, f"self.{name}")
        with self.scorer.function(qualified, node.meta.line, end_line(node), own):
            for child in body:
                self.walk(child)

    def visit_func_def(self, node) -> None:
        header, *body = node.children
        self.function(node, first_name(header), body)

    def visit_property_custom_setter(self, node) -> None:
        self.function(node, "set", node.children)

    def visit_property_custom_getter(self, node) -> None:
        self.function(node, "get", node.children)

    def visit_lambda(self, node) -> None:
        header, *body = node.children
        name = first_name(header)
        with self.scorer.function(name if name != "<anonymous>" else "<lambda>", node.meta.line, end_line(node), (name,)):
            for child in body:
                self.walk(child)

    def visit_standalone_call(self, node) -> None:
        self.scorer.call(first_name(node))
        self.children(node)

    def visit_getattr_call(self, node) -> None:
        target = node.children[0]
        if is_tree(target) and target.data == "getattr":
            names = [str(t) for t in target.children if not is_tree(t) and t.type == "NAME"]
            if len(names) == 2:
                self.scorer.call(".".join(names))
        self.children(node)

    # Branches

    def visit_if_stmt(self, node) -> None:
        for branch in node.children:
            if not is_tree(branch):
                continue
            if branch.data == "if_branch":
                self.scorer.structural()
            else:
                self.scorer.fundamental()
            if branch.data == "else_branch":
                self.nested_children(branch.children)
                continue
            self.scorer.decision()
            condition, *body = branch.children
            self.walk(condition)
            self.nested_children(body)

    def visit_loop(self, node) -> None:
        self.scorer.structural()
        self.scorer.decision()
        children = [child for child in node.children if is_tree(child)]
        header = next((i for i, child in enumerate(children) if child.data == "expr"), 0)
        for child in children[: header + 1]:
            self.walk(child)
        self.nested_children(children[header + 1 :])

    def visit_match_stmt(self, node) -> None:
        self.scorer.structural()
        subject, *branches = node.children
        self.walk(subject)
        for branch in branches:
            if not is_tree(branch):
                continue
            pattern, *rest = branch.children
            wildcard = is_tree(pattern) and any(
                is_tree(c) and c.data == "wildcard_pattern" for c in pattern.children
            )
            if branch.data == "guarded_match_branch":
                guard, *rest = rest
                self.scorer.decision(1 if wildcard else 2)
                self.scorer.fundamental()
                self.walk(guard)
            elif not wildcard:
                self.scorer.decision()
            self.nested_children(rest)

    # Expressions

    def visit_ternary(self, node) -> None:
        parts = [child for child in node.children if is_tree(child) or token_text(child) not in ("if", "else")]
        if len(parts) != 3:
            self.children(node)
            return
        value, condition, alternative = parts
        self.scorer.structural()
        self.scorer.decision()
        self.walk(condition)
        self.nested_children([value, alternative])

    def flatten(self, node, operators: list[str]) -> None:
        if not (is_tree(node) and node.data in BOOLEAN):
            return
        self.seen_boolean.add(id(node))
        for child in node.children:
            if is_tree(child):
                self.flatten(child, operators)
            elif token_text(child) in ("or", "||"):
                operators.append("or")
            elif token_text(child) in ("and", "&&"):
                operators.append("and")

    def visit_boolean(self, node) -> None:
        own = [child for child in node.children if not is_tree(child) and token_text(child) in ("or", "||", "and", "&&")]
        if id(node) not in self.seen_boolean:
            operators: list[str] = []
            self.flatten(node, operators)
            self.scorer.fundamental(operator_runs(operators))
        self.scorer.decision(len(own))
        self.children(node)


def analyze(path: str):
    from gdtoolkit.parser import parser

    with open(path, encoding="utf-8") as handle:
        source = handle.read()
    analyzer = Analyzer()
    analyzer.walk(parser.parse(source, gather_metadata=True))
    return analyzer.scorer.functions


def main(paths: list[str]) -> int:
    try:
        import gdtoolkit  # noqa: F401
    except ImportError:
        sys.exit("gdtoolkit is not installed for this Python; install gdtoolkit 4 or use the repository's lint virtualenv")
    results: dict[str, object] = {}
    for path in paths:
        try:
            results[path] = analyze(path)
        except Exception as error:  # lark raises many parse error types
            results[path] = {"error": f"{type(error).__name__}: {str(error).splitlines()[0] if str(error) else ''}"}
    emit(results)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
