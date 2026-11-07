"""Translate LaTeX maths into mathguard's own expression syntax.

The translation is purely textual: the result is handed to the safe parser in
:mod:`mathguard.parsing`, so nothing in the LaTeX source can ever be executed.

LaTeX conventions are followed where they differ from mathguard's plain syntax:

* adjacent letters are a product (``mv^2`` is ``m*v^2``),
* subscripts belong to the name (``v_0`` becomes the variable ``v0``,
  ``E_{kin}`` becomes ``Ekin``),
* ``\\frac``, ``\\sqrt``, ``\\cdot``, ``\\left( \\right)``, Greek letters,
  ``\\sin`` … and ``|x|`` are understood,
* ``60^\\circ`` becomes ``60*pi/180`` and ``9{,}81`` becomes ``9.81``.

>>> latex_to_expr(r"\\frac{1}{2} m v_0^2")
'((1)/(2)) m v0 ^(2)'
"""

from __future__ import annotations

import re

from .parsing import ParseError

GREEK = {
    "alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta", "iota",
    "kappa", "lambda", "mu", "nu", "xi", "rho", "sigma", "tau", "upsilon", "phi",
    "chi", "psi", "omega", "Gamma", "Delta", "Theta", "Lambda", "Xi", "Sigma",
    "Upsilon", "Phi", "Psi", "Omega",
}
_GREEK_ALIASES = {"varepsilon": "epsilon", "vartheta": "theta", "varphi": "phi",
                  "varrho": "rho", "varsigma": "sigma", "varpi": "pi"}

FUNCTIONS = {
    "sin", "cos", "tan", "cot", "sec", "csc", "arcsin", "arccos", "arctan",
    "sinh", "cosh", "tanh", "exp", "ln", "log",
}

_SPACING = {",", ";", ":", "!", " ", "quad", "qquad", "displaystyle", "textstyle",
            "limits", "nolimits", "big", "Big", "bigg", "Bigg", "bigl", "bigr",
            "Bigl", "Bigr", "middle"}
_DROP_WITH_ARG = {"label", "tag", "hspace", "vspace"}
_ACCENTS = {"dot": "dot", "ddot": "ddot", "hat": "hat", "bar": "bar", "tilde": "tilde",
            "vec": "", "mathbf": "", "boldsymbol": "", "overline": "bar"}
_NAME_WRAPPERS = {"mathrm", "mathit", "operatorname", "text", "textrm", "mathsf"}
_UNSUPPORTED = {"int", "iint", "oint", "sum", "prod", "lim", "partial", "nabla",
                "begin", "end", "binom", "pm", "mp", "prime"}
_RELATIONS = {"approx", "neq", "ne", "leq", "le", "geq", "ge", "lt", "gt", "equiv",
              "sim", "simeq", "propto", "to", "rightarrow", "Rightarrow", "implies"}

_TOKEN = re.compile(r"\\([A-Za-z]+|.)|(\s+)|(.)", re.S)


def _tokenize(src: str) -> list[str]:
    out: list[str] = []
    for m in _TOKEN.finditer(src):
        if m.group(1) is not None:
            out.append("\\" + m.group(1))
        elif m.group(2) is not None:
            out.append(" ")
        else:
            out.append(m.group(3))
    return out


class _Converter:
    def __init__(self, src: str):
        self.src = src
        self.toks = _tokenize(src)
        self.i = 0
        self.abs_open = False

    # -- helpers -----------------------------------------------------------
    def peek(self, skip_space: bool = True) -> str | None:
        j = self.i
        while skip_space and j < len(self.toks) and self.toks[j] == " ":
            j += 1
        return self.toks[j] if j < len(self.toks) else None

    def next(self, skip_space: bool = True) -> str:
        while skip_space and self.i < len(self.toks) and self.toks[self.i] == " ":
            self.i += 1
        if self.i >= len(self.toks):
            raise ParseError(f"unexpected end of LaTeX in '{self.src}'")
        t = self.toks[self.i]
        self.i += 1
        return t

    def group_raw(self) -> str:
        """Return the raw text of the next {...} group (or single token)."""
        t = self.next()
        if t != "{":
            return t.lstrip("\\")
        depth, parts = 1, []
        while True:
            t = self.next(skip_space=False)
            if t == "{":
                depth += 1
            elif t == "}":
                depth -= 1
                if depth == 0:
                    return "".join(parts)
            parts.append(t)

    def arg(self) -> str:
        """Convert the next argument: a {...} group or a single token."""
        t = self.peek()
        if t == "{":
            self.next()
            return "(" + self.until("}") + ")"
        if t is not None and t.isdigit():
            return "(" + self.next() + ")"  # \frac12 = 1/2: one digit each
        return "(" + self.atom() + ")"

    def until(self, closer: str) -> str:
        parts = []
        while True:
            t = self.peek(skip_space=False)
            if t is None:
                raise ParseError(f"missing '{closer}' in '{self.src}'")
            if t == closer:
                self.next(skip_space=False)
                return " ".join(p for p in parts if p).strip()
            parts.append(self.item())

    # -- grammar -----------------------------------------------------------
    def convert(self) -> str:
        parts = []
        while self.peek(skip_space=False) is not None:
            parts.append(self.item())
        if self.abs_open:
            raise ParseError(f"unbalanced '|' in '{self.src}'")
        text = " ".join(p for p in parts if p)
        return re.sub(r"\s+", " ", text).strip()

    def item(self) -> str:
        t = self.peek(skip_space=False)
        if t == " ":
            self.next(skip_space=False)
            return ""
        if t in ("^", "_"):
            self.next()
            if t == "_":
                raise ParseError(f"subscript without a name in '{self.src}'")
            return self.power()
        return self.atom()

    def power(self) -> str:
        if self.peek() in ("\\circ", "\\degree"):
            self.next()
            return "*pi/180"
        nxt = self.peek()
        if nxt == "{":
            self.next()
            inner = self.until("}")
            if inner.replace(" ", "") in ("\\circ", "*pi/180"):
                return "*pi/180"
            return "^(" + inner + ")"
        return "^(" + self.atom() + ")"

    def subscript(self) -> str:
        raw = self.group_raw()
        raw = re.sub(r"\\(?:mathrm|text|mathit|textrm)\s*", "", raw)
        name = "".join(ch for ch in raw if ch.isalnum())
        greek = re.sub(r"[^A-Za-z]", "", raw)
        if not name and greek:
            name = greek
        if not name:
            raise ParseError(f"cannot read subscript '{raw}' in '{self.src}'")
        return name

    def with_subscript(self, name: str) -> str:
        if self.peek(skip_space=False) == "_":
            self.next(skip_space=False)
            name += self.subscript()
        # primes are part of the name: v' -> vprime, v_1'' -> v1primeprime
        while True:
            if self.peek(skip_space=False) == "'":
                self.next(skip_space=False)
                name += "prime"
            elif self.toks[self.i:self.i + 2] == ["^", "\\prime"]:
                self.i += 2
                name += "prime"
            else:
                break
        if self.peek(skip_space=False) == "_" and "prime" in name:
            self.next(skip_space=False)
            name += self.subscript()
        return name

    def atom(self) -> str:
        t = self.next()
        if t == "{":
            inner = self.until("}")
            if inner == ",":
                return "."
            return "(" + inner + ")" if inner else ""
        if t in ("(", "["):
            return "(" + self.until(")" if t == "(" else "]") + ")"
        if t in (")", "]", "}"):
            raise ParseError(f"unbalanced '{t}' in '{self.src}'")
        if t == "|":
            self.abs_open = not self.abs_open
            return "Abs(" if self.abs_open else ")"
        if t in ("+", "-", "/", "*"):
            return t
        if t == "=":
            raise ParseError("'=' inside an expression; split equations first")
        if t in ("<", ">"):
            raise ParseError(f"relation '{t}' inside an expression")
        if t == "'":
            raise ParseError("a prime must follow a name (v')")
        if t == ",":
            return ","
        if t == "&":
            return ""
        if t.isdigit() or t == ".":
            num = t
            while (p := self.peek(skip_space=False)) is not None and (p.isdigit() or p == "."):
                num += self.next(skip_space=False)
            # 9{,}81 -> 9.81
            if self.toks[self.i:self.i + 3] == ["{", ",", "}"]:
                self.i += 3
                frac = ""
                while (p := self.peek(skip_space=False)) is not None and p.isdigit():
                    frac += self.next(skip_space=False)
                num += "." + frac
            return num
        if t.isalpha():
            return self.with_subscript(t)
        if t.startswith("\\"):
            return self.command(t[1:])
        raise ParseError(f"unsupported character '{t}' in '{self.src}'")

    def command(self, name: str) -> str:
        if name in _SPACING:
            return ""
        if name in ("left", "right"):
            d = self.next()
            if d in ("(", "[", "\\{"):
                return "(" + self.until_right() + ")"
            if d == "|":
                inner = self.until_right()
                return "Abs(" + inner + ")"
            if d in (".",):
                return ""
            if name == "right":
                raise ParseError(f"unbalanced \\right in '{self.src}'")
            raise ParseError(f"unsupported delimiter \\left{d}")
        if name in ("frac", "dfrac", "tfrac", "cfrac"):
            num, den = self.arg(), self.arg()
            return f"({num}/{den})"
        if name == "sqrt":
            if self.peek() == "[":
                self.next()
                n = self.until("]")
                return f"({self.arg()}^(1/({n})))"
            return f"sqrt{self.arg()}"
        if name in ("cdot", "times", "ast"):
            return "*"
        if name == "div":
            return "/"
        if name in ("infty", "infin"):
            return "oo"
        if name == "pi":
            return self.with_subscript("pi")
        if name in GREEK:
            return self.with_subscript(name)
        if name in _GREEK_ALIASES:
            return self.with_subscript(_GREEK_ALIASES[name])
        if name in ("ell",):
            return self.with_subscript("l")
        if name in ("hbar",):
            return self.with_subscript("hbar")
        if name in FUNCTIONS:
            return self.function(name)
        if name in _NAME_WRAPPERS:
            raw = self.group_raw().strip()
            if raw in FUNCTIONS or raw in ("arsinh", "arcosh", "artanh"):
                return self.function({"arsinh": "asinh", "arcosh": "acosh",
                                      "artanh": "atanh"}.get(raw, raw))
            if raw == "e":
                return "e"
            if raw == "d":
                raise ParseError("differentials (d x) are not supported in expressions")
            word = re.sub(r"[^A-Za-z0-9]", "", raw)
            if not word:
                return ""
            if name.startswith("text") and len(word) > 3:
                raise ParseError(f"text inside a formula: '{raw}'")
            return self.with_subscript(word)
        if name in _ACCENTS:
            raw = self.group_raw()
            base = re.sub(r"[^A-Za-z0-9]", "", raw)
            return self.with_subscript(base + _ACCENTS[name])
        if name in _DROP_WITH_ARG:
            self.group_raw()
            return ""
        if name == "circ" or name == "degree":
            return "*pi/180"
        if name in ("{", "}"):
            return "(" if name == "{" else ")"
        if name in ("lvert", "rvert", "vert"):
            self.abs_open = not self.abs_open
            return "Abs(" if self.abs_open else ")"
        if name in _RELATIONS:
            raise ParseError(f"relation '\\{name}' inside an expression")
        if name in _UNSUPPORTED:
            raise ParseError(f"'\\{name}' is not supported yet")
        raise ParseError(f"unknown LaTeX command '\\{name}'")

    def until_right(self) -> str:
        parts = []
        while True:
            t = self.peek(skip_space=False)
            if t is None:
                raise ParseError(f"missing \\right in '{self.src}'")
            if t == "\\right":
                self.next(skip_space=False)
                self.next()  # the closing delimiter
                return " ".join(p for p in parts if p)
            parts.append(self.item())

    def function(self, name: str) -> str:
        name = {"arcsin": "asin", "arccos": "acos", "arctan": "atan"}.get(name, name)
        power = ""
        if self.peek() == "^":
            self.next()
            power = self.power()
            if power.startswith("^(-1)"):
                raise ParseError(f"\\{name}^{{-1}} is ambiguous; write \\arc{name}")
        nxt = self.peek()
        if nxt in ("(", "\\left"):
            argument = self.atom()
        elif nxt == "{":
            argument = self.atom()
        else:
            # \sin 2\alpha, \sin\theta: take factors up to the next operator
            parts = []
            while True:
                if self.peek(skip_space=False) in ("\\,", "\\;", "\\:", "\\quad", "\\qquad"):
                    break  # "\sin\alpha\, t" means sin(alpha)*t
                p = self.peek()
                if p is None or p in ("+", "-", "=", ")", "]", "}", ",", "&", "|",
                                      "\\right", "\\cdot", "\\times", "/") \
                        or (p.startswith("\\") and p[1:] in FUNCTIONS | _RELATIONS):
                    break
                if p == "^":
                    self.next()
                    parts.append(self.power())
                    continue
                parts.append(self.atom())
            if not parts:
                raise ParseError(f"\\{name} without an argument")
            argument = "(" + " ".join(parts) + ")"
        if not argument.startswith("("):
            argument = "(" + argument + ")"
        out = f"{name}{argument}"
        return f"({out}){power}" if power else out


def latex_to_expr(src: str) -> str:
    """Translate one LaTeX expression (no relation signs) into mathguard syntax."""
    if not isinstance(src, str):
        raise ParseError("LaTeX input must be a string")
    src = src.strip().strip("$").strip()
    if not src:
        raise ParseError("empty LaTeX expression")
    text = _Converter(src).convert()
    if not text:
        raise ParseError(f"nothing to check in '{src}'")
    return text


def parse_latex(src: str, assumptions=None):
    """Parse a LaTeX expression into a SymPy object (safely)."""
    from .parsing import parse
    return parse(latex_to_expr(src), assumptions)
