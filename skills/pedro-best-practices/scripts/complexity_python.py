"""Score Python functions; see complexity_core.py for the metrics.

Usage: python complexity_python.py FILE...   (prints JSON)

Run it with an interpreter at least as new as the code's syntax; the
repository's own virtualenv is the safe choice. Language mappings:
- `elif` is an else-if (+1 flat); `else` on if, for, and while is +1 flat.
- `try`, `else` on try, and `finally` are free; each `except` is structural.
- `match` is one structural increment; each non-wildcard `case` is a
  cyclomatic decision, and a case guard adds 1 to both metrics.
- Comprehensions: each `if` clause and each `for` clause after the first add 1
  to both metrics; the first `for` adds 1 to cyclomatic only.
- Recursion: a function calling its own name, or a method calling itself
  through `self.` or `cls.`.
"""

from __future__ import annotations

import ast
import sys

from complexity_core import Scorer, emit, operator_runs

COMPREHENSIONS = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)


class Analyzer:
    def __init__(self, source: str):
        self.lines = source.splitlines()
        self.scorer = Scorer()
        self.seen_boolops: set[int] = set()
        self.classes: list[str] = []

    def walk(self, node: ast.AST) -> None:
        handler = getattr(self, f"visit_{type(node).__name__}", None)
        if handler:
            handler(node)
        else:
            self.children(node)

    def children(self, node: ast.AST) -> None:
        for child in ast.iter_child_nodes(node):
            self.walk(child)

    def body(self, statements: list[ast.stmt]) -> None:
        for statement in statements:
            self.walk(statement)

    def nested_body(self, statements: list[ast.stmt]) -> None:
        with self.scorer.nested():
            self.body(statements)

    # Functions and classes

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        for expression in [*node.decorator_list, *node.bases, *node.keywords]:
            self.walk(expression)
        self.classes.append(node.name)
        self.body(node.body)
        self.classes.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        for expression in [*node.decorator_list, *node.args.defaults, *node.args.kw_defaults]:
            if expression is not None:
                self.walk(expression)
        in_class = bool(self.classes) and not self.scorer.active
        name = ".".join([*self.classes, node.name]) if in_class else node.name
        # Inside a method, a bare name is a module-level call, not recursion.
        own = (f"self.{node.name}", f"cls.{node.name}") if in_class else (node.name,)
        with self.scorer.function(name, node.lineno, node.end_lineno or node.lineno, own):
            self.body(node.body)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Lambda(self, node: ast.Lambda) -> None:
        with self.scorer.function("<lambda>", node.lineno, node.end_lineno or node.lineno):
            self.walk(node.body)

    def visit_Call(self, node: ast.Call) -> None:
        function = node.func
        if isinstance(function, ast.Name):
            self.scorer.call(function.id)
        elif isinstance(function, ast.Attribute) and isinstance(function.value, ast.Name):
            self.scorer.call(f"{function.value.id}.{function.attr}")
        self.children(node)

    # Branches

    def is_elif(self, node: ast.If) -> bool:
        line = self.lines[node.lineno - 1]
        return line[node.col_offset:].startswith("elif")

    def visit_If(self, node: ast.If, as_elif: bool = False) -> None:
        if as_elif:
            self.scorer.fundamental()
        else:
            self.scorer.structural()
        self.scorer.decision()
        self.walk(node.test)
        self.nested_body(node.body)
        if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If) and self.is_elif(node.orelse[0]):
            self.visit_If(node.orelse[0], as_elif=True)
        elif node.orelse:
            self.scorer.fundamental()
            self.nested_body(node.orelse)

    def visit_IfExp(self, node: ast.IfExp) -> None:
        self.scorer.structural()
        self.scorer.decision()
        self.walk(node.test)
        with self.scorer.nested():
            self.walk(node.body)
            self.walk(node.orelse)

    def loop(self, header: list[ast.AST], node) -> None:
        self.scorer.structural()
        self.scorer.decision()
        for expression in header:
            self.walk(expression)
        self.nested_body(node.body)
        if node.orelse:
            self.scorer.fundamental()
            self.nested_body(node.orelse)

    def visit_For(self, node: ast.For) -> None:
        self.loop([node.target, node.iter], node)

    visit_AsyncFor = visit_For

    def visit_While(self, node: ast.While) -> None:
        self.loop([node.test], node)

    def visit_Try(self, node) -> None:
        self.body(node.body)
        for handler in node.handlers:
            self.scorer.structural()
            self.scorer.decision()
            if handler.type is not None:
                self.walk(handler.type)
            self.nested_body(handler.body)
        self.body(node.orelse)
        self.body(node.finalbody)

    visit_TryStar = visit_Try

    def visit_Match(self, node) -> None:
        self.scorer.structural()
        self.walk(node.subject)
        for case in node.cases:
            wildcard = type(case.pattern).__name__ == "MatchAs" and case.pattern.pattern is None and case.guard is None
            if not wildcard:
                self.scorer.decision()
            if case.guard is not None:
                self.scorer.fundamental()
                self.scorer.decision()
                self.walk(case.guard)
            self.nested_body(case.body)

    # Expressions

    def flatten(self, node: ast.AST, operators: list[str]) -> None:
        if not isinstance(node, ast.BoolOp):
            return
        self.seen_boolops.add(id(node))
        operator = "and" if isinstance(node.op, ast.And) else "or"
        for index, value in enumerate(node.values):
            if index:
                operators.append(operator)
            self.flatten(value, operators)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        if id(node) not in self.seen_boolops:
            operators: list[str] = []
            self.flatten(node, operators)
            self.scorer.fundamental(operator_runs(operators))
        self.scorer.decision(len(node.values) - 1)
        self.children(node)

    def comprehension(self, node) -> None:
        for index, generator in enumerate(node.generators):
            self.scorer.decision(1 + len(generator.ifs))
            self.scorer.fundamental((1 if index else 0) + len(generator.ifs))
        self.children(node)

    visit_ListComp = visit_SetComp = visit_DictComp = visit_GeneratorExp = comprehension


def analyze(path: str):
    with open(path, encoding="utf-8") as handle:
        source = handle.read()
    analyzer = Analyzer(source)
    analyzer.walk(ast.parse(source, filename=path))
    return analyzer.scorer.functions


def main(paths: list[str]) -> int:
    results: dict[str, object] = {}
    for path in paths:
        try:
            results[path] = analyze(path)
        except (SyntaxError, UnicodeDecodeError, ValueError) as error:
            results[path] = {"error": f"{type(error).__name__}: {error}"}
    emit(results)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
