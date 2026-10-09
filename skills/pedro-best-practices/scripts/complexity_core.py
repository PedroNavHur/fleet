"""Shared scoring for the per-language complexity analyzers.

Cognitive complexity follows the SonarSource whitepaper (G. Ann Campbell,
v1.7): structural increments cost 1 plus the current nesting, fundamental
increments cost 1, nested functions add a nesting level and fold their score
into the enclosing top-level function. Cyclomatic complexity follows ESLint's
classic `complexity` rule: 1 plus one per decision point, scored for every
function on its own. Each analyzer walks its language's syntax tree and calls
the methods below; this module owns the arithmetic so every language scores
the same way.
"""

from __future__ import annotations

import json
import sys
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field


@dataclass
class Function:
    name: str
    line: int
    end_line: int
    cyclomatic: int = 1
    cognitive: int | None = None  # None for nested functions: counted in the top-level one


@dataclass
class _Frame:
    function: Function
    nesting: int
    recursion_counted: bool = False
    own_names: tuple[str, ...] = ()


@dataclass
class Scorer:
    functions: list[Function] = field(default_factory=list)
    _frames: list[_Frame] = field(default_factory=list)

    @property
    def active(self) -> bool:
        return bool(self._frames)

    @contextmanager
    def function(self, name: str, line: int, end_line: int, own_names: tuple[str, ...] = ()):
        """Score a function body. `own_names` are the call forms that count as recursion."""
        function = Function(name, line, end_line)
        if self._frames:
            nesting = self._frames[-1].nesting + 1
        else:
            nesting = 0
            function.cognitive = 0
        self.functions.append(function)
        self._frames.append(_Frame(function, nesting, own_names=own_names))
        try:
            yield function  # callers that find the end while parsing set end_line here
        finally:
            self._frames.pop()

    @contextmanager
    def nested(self):
        """A nesting region: the body of an if, else, loop, catch, case, or ternary branch."""
        if not self._frames:
            yield
            return
        self._frames[-1].nesting += 1
        try:
            yield
        finally:
            self._frames[-1].nesting -= 1

    def _top(self) -> Function | None:
        return self._frames[0].function if self._frames else None

    def structural(self) -> None:
        """if, ternary, switch/match, loop, catch: 1 plus the nesting level."""
        if self._frames:
            self._top().cognitive += 1 + self._frames[-1].nesting

    def fundamental(self, amount: int = 1) -> None:
        """else, else-if, operator runs, labeled jumps, recursion: a flat 1 each."""
        if self._frames and amount:
            self._top().cognitive += amount

    def decision(self, amount: int = 1) -> None:
        """A cyclomatic decision point in the innermost function."""
        if self._frames and amount:
            self._frames[-1].function.cyclomatic += amount

    def call(self, form: str) -> None:
        """Count recursion once per function when `form` names the function itself."""
        if not self._frames:
            return
        frame = self._frames[-1]
        if not frame.recursion_counted and form in frame.own_names:
            frame.recursion_counted = True
            self.fundamental()


def operator_runs(operators: list[str]) -> int:
    """Runs of like operators in a flattened boolean chain: `a && b || c` is 2."""
    runs, previous = 0, None
    for operator in operators:
        if operator != previous:
            runs += 1
            previous = operator
    return runs


def emit(results: dict[str, object]) -> None:
    """Print {path: [functions] or {"error": message}} as JSON for measure_complexity.py."""
    def encode(value):
        return [asdict(f) for f in value] if isinstance(value, list) else value
    json.dump({path: encode(value) for path, value in results.items()}, sys.stdout)
