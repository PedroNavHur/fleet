"""Score PHP functions from PHP's own tokenizer; see complexity_core.py.

Usage: python complexity_php.py [--php BINARY] FILE...   (prints JSON)

Needs PHP 8 on PATH (or --php). PHP tokenizes each file; this script parses
the token stream into statements and expressions. Language mappings:
- `elseif` and `else if` are else-ifs (+1 flat); `else` is +1 flat; the
  alternative syntax (`if (...):` ... `endif;`) scores the same.
- `switch` and `match` are one structural increment each; every `case` and
  every non-default `match` condition is a cyclomatic decision.
- `&&`/`and`, `||`/`or`, and `xor` form operator runs. `??`, `??=`, and the
  short ternary `?:` are shorthand: cyclomatic decisions, cognitively free.
- `break N`/`continue N` with N > 1 and `goto` are +1 flat, like labeled jumps.
- Closures and arrow functions nest like any nested function. Recursion: a
  call to the function's own name, or `$this->`, `self::`, `static::`, or the
  class name plus the method's name.
"""

from __future__ import annotations

import json
import subprocess
import sys

from complexity_core import Scorer, emit, operator_runs

TOKENIZE = r"""
$out = [];
foreach (array_slice($argv, 1) as $path) {
    try {
        $tokens = PhpToken::tokenize(file_get_contents($path), TOKEN_PARSE);
        $out[$path] = array_map(fn($t) => [$t->getTokenName(), $t->text, $t->line], $tokens);
    } catch (Throwable $e) {
        $out[$path] = ["error" => get_class($e) . ": " . $e->getMessage() . " on line " . $e->getLine()];
    }
}
echo json_encode($out);
"""
SKIPPED = {"T_WHITESPACE", "T_COMMENT", "T_DOC_COMMENT", "T_OPEN_TAG"}
OPENERS = {"(": ")", "[": "]", "{": "}", "T_CURLY_OPEN": "}", "T_DOLLAR_OPEN_CURLY_BRACES": "}", "T_ATTRIBUTE": "]"}
BOOLEAN = {"T_BOOLEAN_AND": "and", "T_LOGICAL_AND": "and", "T_BOOLEAN_OR": "or", "T_LOGICAL_OR": "or", "T_LOGICAL_XOR": "xor"}
SHORTHAND = {"T_COALESCE", "T_COALESCE_EQUAL"}
CALLABLE_BEFORE = {
    "T_STRING", "T_VARIABLE", "T_NAME_QUALIFIED", "T_NAME_FULLY_QUALIFIED", "T_NAME_RELATIVE",
    ")", "]", "}", "T_STATIC", "T_ARRAY", "T_ISSET", "T_EMPTY", "T_EXIT", "T_LIST", "T_UNSET", "T_EVAL",
}
MODIFIERS = {"T_PUBLIC", "T_PROTECTED", "T_PRIVATE", "T_STATIC", "T_ABSTRACT", "T_FINAL", "T_READONLY", "T_VAR"}
CLASSLIKE = {"T_CLASS", "T_INTERFACE", "T_TRAIT", "T_ENUM"}
EXPRESSION_END = {";", "T_CLOSE_TAG"}


class Parser:
    def __init__(self, tokens: list[list]):
        self.tokens = [t for t in tokens if t[0] not in SKIPPED]
        self.i = 0
        self.scorer = Scorer()
        self.match = self.pair_brackets()

    # Cursor

    def kind(self, offset: int = 0) -> str:
        index = self.i + offset
        return self.tokens[index][0] if index < len(self.tokens) else "EOF"

    def text(self, offset: int = 0) -> str:
        index = self.i + offset
        return self.tokens[index][1] if index < len(self.tokens) else ""

    def line(self, index: int | None = None) -> int:
        index = self.i if index is None else index
        return self.tokens[min(index, len(self.tokens) - 1)][2] if self.tokens else 1

    def at_end(self) -> bool:
        return self.i >= len(self.tokens)

    def pair_brackets(self) -> dict[int, int]:
        pairs, stack = {}, []
        for index, (kind, _, _) in enumerate(self.tokens):
            if kind in OPENERS:
                stack.append((index, OPENERS[kind]))
            elif stack and kind == stack[-1][1]:
                pairs[stack.pop()[0]] = index
        return pairs

    def skip_group(self) -> int:
        """Jump past the bracketed group starting at the cursor; return the closer's index."""
        closer = self.match.get(self.i, len(self.tokens) - 1)
        self.i = closer + 1
        return closer

    def skip_until(self, kinds: set[str]) -> None:
        while not self.at_end() and self.kind() not in kinds:
            if self.kind() in OPENERS:
                self.skip_group()
            else:
                self.i += 1

    def expect(self, kind: str) -> None:
        if self.kind() == kind:
            self.i += 1

    # Statements

    def parse(self) -> None:
        while not self.at_end():
            before = self.i
            self.statement()
            if self.i == before:
                self.i += 1  # never stall on an unexpected token

    def statement(self) -> None:
        kind = self.kind()
        if kind in ("T_INLINE_HTML", "T_CLOSE_TAG", ";"):
            self.i += 1
        elif kind == "T_OPEN_TAG_WITH_ECHO":
            self.i += 1
            self.expression(EXPRESSION_END)
            self.expect(";")
        elif kind == "{":
            self.block()
        elif kind == "T_ATTRIBUTE":
            self.skip_group()
        elif kind in ("T_ABSTRACT", "T_FINAL", "T_READONLY"):
            self.i += 1
        elif kind in CLASSLIKE:
            self.class_declaration()
        elif kind == "T_FUNCTION" and self.named_function_follows():
            self.function_declaration(None)
        elif kind == "T_IF":
            self.if_statement()
        elif kind in ("T_WHILE", "T_FOR", "T_FOREACH"):
            self.loop({"T_WHILE": "T_ENDWHILE", "T_FOR": "T_ENDFOR", "T_FOREACH": "T_ENDFOREACH"}[kind])
        elif kind == "T_DO":
            self.do_while()
        elif kind == "T_SWITCH":
            self.switch()
        elif kind == "T_TRY":
            self.try_statement()
        elif kind == "T_GOTO":
            self.scorer.fundamental()
            self.skip_until(EXPRESSION_END)
        elif kind in ("T_BREAK", "T_CONTINUE"):
            self.i += 1
            if self.kind() == "T_LNUMBER" and int(self.text(), 0) > 1:
                self.scorer.fundamental()
            self.skip_until(EXPRESSION_END)
        elif kind in ("T_NAMESPACE", "T_USE", "T_DECLARE"):
            self.i += 1
            self.skip_until({";", "{", "T_CLOSE_TAG"})
            if self.kind() == "{":
                self.block()
        else:
            self.expression(EXPRESSION_END)
            self.expect(";")

    def block(self) -> None:
        closer = self.match.get(self.i, len(self.tokens))
        self.i += 1
        while self.i < closer and not self.at_end():
            before = self.i
            self.statement()
            if self.i == before:
                self.i += 1
        self.i = closer + 1

    def body(self, alternative_ends: set[str]) -> None:
        """A braced block, an alternative-syntax block, or a single statement."""
        if self.kind() == "{":
            self.block()
        elif self.kind() == ":":
            self.i += 1
            while not self.at_end() and self.kind() not in alternative_ends:
                before = self.i
                self.statement()
                if self.i == before:
                    self.i += 1
        else:
            self.statement()

    def condition(self) -> None:
        if self.kind() == "(":
            closer = self.match.get(self.i, len(self.tokens))
            self.i += 1
            self.expression({")"}, limit=closer)
            self.i = closer + 1

    def if_statement(self) -> None:
        ends = {"T_ELSEIF", "T_ELSE", "T_ENDIF"}
        self.i += 1
        self.scorer.structural()
        self.scorer.decision()
        self.condition()
        with self.scorer.nested():
            self.body(ends)
        while True:
            if self.kind() == "T_ELSEIF" or (self.kind() == "T_ELSE" and self.kind(1) == "T_IF"):
                self.i += 1 if self.kind() == "T_ELSEIF" else 2
                self.scorer.fundamental()
                self.scorer.decision()
                self.condition()
                with self.scorer.nested():
                    self.body(ends)
            elif self.kind() == "T_ELSE":
                self.i += 1
                self.scorer.fundamental()
                with self.scorer.nested():
                    self.body({"T_ENDIF"})
                break
            else:
                break
        if self.kind() == "T_ENDIF":
            self.i += 1
            self.expect(";")

    def loop(self, alternative_end: str) -> None:
        self.i += 1
        self.scorer.structural()
        self.scorer.decision()
        self.condition()
        with self.scorer.nested():
            self.body({alternative_end})
        if self.kind() == alternative_end:
            self.i += 1
            self.expect(";")

    def do_while(self) -> None:
        self.i += 1
        self.scorer.structural()
        self.scorer.decision()
        with self.scorer.nested():
            self.statement()
        self.expect("T_WHILE")
        self.condition()
        self.expect(";")

    def switch(self) -> None:
        self.i += 1
        self.scorer.structural()
        self.condition()
        if self.kind() == "{":
            end, closer = None, self.match.get(self.i, len(self.tokens))
            self.i += 1
        else:
            end, closer = "T_ENDSWITCH", len(self.tokens)
            self.expect(":")
        while not self.at_end() and self.i < closer and self.kind() != end:
            if self.kind() == "T_CASE":
                self.scorer.decision()
                self.i += 1
                self.expression({":", ";"})
                self.i += 1
            elif self.kind() == "T_DEFAULT":
                self.i += 1
                self.expect(":")
                self.expect(";")
            else:
                before = self.i
                with self.scorer.nested():
                    self.statement()
                if self.i == before:
                    self.i += 1
        self.i = closer + 1 if end is None else self.i + 1
        if end is not None:
            self.expect(";")

    def try_statement(self) -> None:
        self.i += 1
        self.block()
        while self.kind() == "T_CATCH":
            self.i += 1
            self.scorer.structural()
            self.scorer.decision()
            self.skip_group()  # caught types
            with self.scorer.nested():
                self.block()
        if self.kind() == "T_FINALLY":
            self.i += 1
            self.block()

    # Declarations

    def named_function_follows(self) -> bool:
        offset = 2 if self.kind(1) == "&" else 1
        return self.kind(offset) not in ("(", "EOF")

    def class_declaration(self, name: str | None = None) -> None:
        self.i += 1
        if name is None and self.kind() == "T_STRING":
            name = self.text()
        self.skip_until({"{"})
        self.class_body(name or "class@anonymous")

    def class_body(self, name: str) -> None:
        closer = self.match.get(self.i, len(self.tokens))
        self.i += 1
        while self.i < closer and not self.at_end():
            kind = self.kind()
            if kind == "T_FUNCTION":
                self.function_declaration(name)
            elif kind in MODIFIERS or kind == "T_ATTRIBUTE":
                if kind == "T_ATTRIBUTE":
                    self.skip_group()
                else:
                    self.i += 1
            elif kind == "T_USE":
                self.skip_until({";", "{"})
                if self.kind() == "{":
                    self.skip_group()
                else:
                    self.i += 1
            else:  # properties, constants, enum cases
                self.skip_until({";", "}"} if self.kind() != "{" else {";"})
                self.expect(";")
        self.i = closer + 1

    def function_declaration(self, class_name: str | None) -> None:
        start = self.i
        self.i += 1
        self.expect("&")
        name = self.text()
        self.i += 1
        if self.kind() == "(":
            self.skip_group()  # parameters, including nullable types
        self.skip_until({"{", ";"})
        if self.kind() == ";":  # abstract or interface method
            self.i += 1
            return
        closer = self.match.get(self.i, len(self.tokens) - 1)
        if class_name:
            qualified = f"{class_name}::{name}"
            own = (f"$this->{name}", f"self::{name}", f"static::{name}", f"{class_name}::{name}")
        else:
            qualified, own = name, (name,)
        with self.scorer.function(qualified, self.line(start), self.line(closer), own):
            self.block()

    def closure(self) -> None:
        start = self.i
        self.i += 1
        self.expect("&")
        if self.kind() == "(":
            self.skip_group()
        self.skip_until({"{"})
        closer = self.match.get(self.i, len(self.tokens) - 1)
        with self.scorer.function("<closure>", self.line(start), self.line(closer)):
            self.block()

    def arrow_function(self, stop: set[str], limit: int | None) -> None:
        start = self.i
        self.i += 1
        self.expect("&")
        if self.kind() == "(":
            self.skip_group()
        self.skip_until({"T_DOUBLE_ARROW"})
        self.i += 1
        with self.scorer.function("<arrow>", self.line(start), self.line(start)) as function:
            self.expression(stop | {",", ")", "]", "}"}, limit=limit)
            function.end_line = self.line(max(self.i - 1, start))

    def match_expression(self) -> None:
        self.i += 1
        self.scorer.structural()
        self.condition()
        closer = self.match.get(self.i, len(self.tokens))
        self.i += 1
        while self.i < closer and not self.at_end():
            if self.kind() == "T_DEFAULT":
                self.i += 1
            else:
                while self.i < closer:
                    self.scorer.decision()
                    self.expression({",", "T_DOUBLE_ARROW"}, limit=closer)
                    if self.kind() != ",":
                        break
                    self.i += 1
            self.expect("T_DOUBLE_ARROW")
            with self.scorer.nested():
                self.expression({","}, limit=closer)
            self.expect(",")
        self.i = closer + 1

    # Expressions

    def call_form(self) -> str | None:
        """The recursion form of a call whose name is at the cursor, if any."""
        before = self.tokens[self.i - 1][0] if self.i else ""
        name = self.text()
        if before in ("T_FUNCTION", "T_NEW", "T_FN"):
            return None
        if before in ("T_OBJECT_OPERATOR", "T_NULLSAFE_OBJECT_OPERATOR"):
            owner = self.tokens[self.i - 2][1] if self.i > 1 else ""
            return f"{owner}->{name}" if owner == "$this" else None
        if before == "T_DOUBLE_COLON":
            owner = self.tokens[self.i - 2][1] if self.i > 1 else ""
            return f"{owner}::{name}"
        return name

    def expression(self, stop: set[str], limit: int | None = None, operators: list[str] | None = None) -> None:
        """Walk tokens until a stop kind; score ternaries, chains, calls, and nested functions."""
        own = operators is None
        chain: list[str] = [] if own else operators

        def flush() -> None:
            if own:
                self.scorer.fundamental(operator_runs(chain))
                chain.clear()

        while not self.at_end() and (limit is None or self.i < limit):
            kind = self.kind()
            if kind in stop or kind in (")", "]", "}"):
                break
            if kind in BOOLEAN:
                chain.append(BOOLEAN[kind])
                self.scorer.decision()
                self.i += 1
            elif kind in SHORTHAND:
                flush()
                self.scorer.decision()
                self.i += 1
            elif kind == "?" and self.kind(1) == ":":  # short ternary
                flush()
                self.scorer.decision()
                self.i += 2
            elif kind == "?":
                flush()
                self.scorer.structural()
                self.scorer.decision()
                self.i += 1
                with self.scorer.nested():
                    self.expression({":"}, limit=limit)
                    self.expect(":")
                    self.expression(stop, limit=limit)
                break
            elif kind in (",", "T_DOUBLE_ARROW"):
                flush()
                self.i += 1
            elif kind == "(":
                closer = self.match.get(self.i, len(self.tokens))
                before = self.tokens[self.i - 1][0] if self.i else ""
                self.i += 1
                if before in CALLABLE_BEFORE or before == "!":
                    while self.i < closer:
                        self.expression({","}, limit=closer)
                        if self.kind() == ",":
                            self.i += 1
                        else:
                            break
                else:  # grouping parentheses continue the chain
                    self.expression(set(), limit=closer, operators=chain)
                self.i = closer + 1
            elif kind in ("[", "T_CURLY_OPEN", "T_DOLLAR_OPEN_CURLY_BRACES", "{"):
                closer = self.match.get(self.i, len(self.tokens))
                self.i += 1
                while self.i < closer:
                    self.expression({",", "T_DOUBLE_ARROW"}, limit=closer)
                    if self.kind() in (",", "T_DOUBLE_ARROW"):
                        self.i += 1
                    else:
                        break
                self.i = closer + 1
            elif kind == "T_FUNCTION":
                self.closure()
            elif kind == "T_FN":
                self.arrow_function(stop, limit)
            elif kind == "T_MATCH":
                self.match_expression()
            elif kind == "T_NEW" and self.kind(1) == "T_CLASS":
                self.i += 1
                self.class_declaration("class@anonymous")
            elif kind == "T_ATTRIBUTE":
                self.skip_group()
            elif kind in ("T_STRING", "T_NAME_QUALIFIED", "T_NAME_FULLY_QUALIFIED") and self.kind(1) == "(":
                form = self.call_form()
                if form:
                    self.scorer.call(form)
                self.i += 1
            else:
                self.i += 1
        flush()


def tokenize(php: str, paths: list[str]) -> dict[str, object]:
    result = subprocess.run([php, "-r", TOKENIZE, "--", *paths], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        sys.exit(f"php tokenizer failed: {result.stderr.strip() or result.stdout.strip()}")
    return json.loads(result.stdout)


def main(argv: list[str]) -> int:
    php = "php"
    if argv[:1] == ["--php"]:
        php, argv = argv[1], argv[2:]
    results: dict[str, object] = {}
    for path, tokens in tokenize(php, argv).items():
        if isinstance(tokens, dict):
            results[path] = tokens
            continue
        parser = Parser(tokens)
        parser.parse()
        results[path] = parser.scorer.functions
    emit(results)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
