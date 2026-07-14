"""Small, dependency-free parser for Questie's generated Lua table literals.

This is intentionally not a general Lua interpreter. Questie's generated database
uses strings, numbers, nil/booleans, and nested table constructors; supporting only
that data-only subset keeps cataloging deterministic and safe.
"""

from __future__ import annotations

from dataclasses import dataclass


class LuaParseError(ValueError):
    pass


@dataclass
class LuaTableParser:
    source: str
    pos: int = 0

    def parse(self):
        value = self._value()
        self._space()
        if self.pos != len(self.source):
            raise self._error("unexpected trailing input")
        return value

    def _error(self, message: str) -> LuaParseError:
        start = max(0, self.pos - 30)
        end = min(len(self.source), self.pos + 30)
        return LuaParseError(f"{message} at {self.pos}: {self.source[start:end]!r}")

    def _space(self) -> None:
        while self.pos < len(self.source) and self.source[self.pos].isspace():
            self.pos += 1

    def _value(self):
        self._space()
        if self.pos >= len(self.source):
            raise self._error("expected value")
        char = self.source[self.pos]
        if char == "{":
            return self._table()
        if char in "\"'":
            return self._string()
        if char == "-" or char.isdigit():
            return self._number()
        for word, value in (("nil", None), ("true", True), ("false", False)):
            if self.source.startswith(word, self.pos):
                self.pos += len(word)
                return value
        raise self._error("unsupported Lua value")

    def _table(self):
        self.pos += 1
        positional = []
        keyed = {}
        has_keys = False
        while True:
            self._space()
            if self.pos >= len(self.source):
                raise self._error("unterminated table")
            if self.source[self.pos] == "}":
                self.pos += 1
                break
            if self.source[self.pos] == "[":
                has_keys = True
                self.pos += 1
                key = self._value()
                self._space()
                if self.pos >= len(self.source) or self.source[self.pos] != "]":
                    raise self._error("expected closing key bracket")
                self.pos += 1
                self._space()
                if self.pos >= len(self.source) or self.source[self.pos] != "=":
                    raise self._error("expected key assignment")
                self.pos += 1
                keyed[key] = self._value()
            else:
                positional.append(self._value())
            self._space()
            if self.pos < len(self.source) and self.source[self.pos] in ",;":
                self.pos += 1
                continue
            if self.pos < len(self.source) and self.source[self.pos] == "}":
                continue
            raise self._error("expected table separator")
        if has_keys:
            for index, value in enumerate(positional, 1):
                keyed[index] = value
            return keyed
        return positional

    def _string(self) -> str:
        quote = self.source[self.pos]
        self.pos += 1
        result = []
        while self.pos < len(self.source):
            char = self.source[self.pos]
            self.pos += 1
            if char == quote:
                return "".join(result)
            if char != "\\":
                result.append(char)
                continue
            if self.pos >= len(self.source):
                raise self._error("unterminated escape")
            escaped = self.source[self.pos]
            self.pos += 1
            translations = {"n": "\n", "r": "\r", "t": "\t", "\\": "\\", '"': '"', "'": "'"}
            if escaped in translations:
                result.append(translations[escaped])
            elif escaped.isdigit():
                digits = escaped
                while self.pos < len(self.source) and len(digits) < 3 and self.source[self.pos].isdigit():
                    digits += self.source[self.pos]
                    self.pos += 1
                result.append(chr(int(digits)))
            else:
                result.append(escaped)
        raise self._error("unterminated string")

    def _number(self):
        start = self.pos
        if self.source[self.pos] == "-":
            self.pos += 1
        while self.pos < len(self.source) and self.source[self.pos].isdigit():
            self.pos += 1
        if self.pos < len(self.source) and self.source[self.pos] == ".":
            self.pos += 1
            while self.pos < len(self.source) and self.source[self.pos].isdigit():
                self.pos += 1
            return float(self.source[start:self.pos])
        return int(self.source[start:self.pos])


def parse_lua_table(source: str):
    return LuaTableParser(source).parse()
