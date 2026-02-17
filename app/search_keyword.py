from typing import Optional, List
import re

# Tokenizer regex: parentheses, AND/OR/NOT, '-', quoted phrases, or bare terms
_TOKEN_RE = re.compile(
    r'\s*(\(|\)|\bAND\b|\bOR\b|\bNOT\b|-|"[^"]+"|[^()\s]+)\s*',
    re.IGNORECASE
)

def _tokenize(query: str) -> List[str]:
    raw = [t for t in _TOKEN_RE.findall(query) if t.strip() != ""]
    normalized = []
    for t in raw:
        up = t.upper()
        if up in ("AND", "OR", "NOT", "-"):
            normalized.append(up if up != "-" else "NOT")
        elif t == "(" or t == ")":
            normalized.append(t)
        else:
            # keep quoted content without quotes
            if len(t) >= 2 and t[0] == '"' and t[-1] == '"':
                normalized.append(t[1:-1])
            else:
                normalized.append(t)
    # Insert implicit AND between adjacent terms or between term and '(' or ')' and term
    out = []
    prev = None
    for tok in normalized:
        if prev is not None:
            prev_is_term = (prev not in ("AND", "OR", "NOT", "(", ")"))
            cur_is_term = (tok not in ("AND", "OR", "NOT", "(", ")"))
            if (prev_is_term and cur_is_term) or (prev_is_term and tok == "(") or (prev == ")" and cur_is_term):
                out.append("AND")
        out.append(tok)
        prev = tok
    return out


# AST nodes for keyword queries
class Node:
    def evaluate(self, text: str) -> bool:
        raise NotImplementedError


class TermNode(Node):
    def __init__(self, term: str):
        self.term = term

        # use plain substring match if phrase or no wildcards for speed
        self._has_space = " " in term
        self._has_wild = ("*" in term) or ("?" in term)

        if self._has_wild:
            # convert wildcard pattern to regex
            esc = re.escape(term)
            esc = esc.replace(r'\*', '.*').replace(r'\?', '.')
            self._re = re.compile(esc, re.IGNORECASE)
            self._plain = False
        else:
            # plain substring match (case-insensitive)
            self._plain = True
            self._needle = term.lower()

    def evaluate(self, text: str) -> bool:
        if self._plain:
            return self._needle in text.lower()
        return bool(self._re.search(text))


class AndNode(Node):
    def __init__(self, left: Node, right: Node):
        self.left = left
        self.right = right

    def evaluate(self, text: str) -> bool:
        return self.left.evaluate(text) and self.right.evaluate(text)


class OrNode(Node):
    def __init__(self, left: Node, right: Node):
        self.left = left
        self.right = right

    def evaluate(self, text: str) -> bool:
        return self.left.evaluate(text) or self.right.evaluate(text)


class NotNode(Node):
    def __init__(self, node: Node):
        self.node = node

    def evaluate(self, text: str) -> bool:
        return not self.node.evaluate(text)


# Recursive-descent parser
class Parser:
    def __init__(self, tokens: List[str]):
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> Optional[str]:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def consume(self, expected: Optional[str] = None) -> str:
        tok = self.peek()
        if tok is None:
            raise ValueError("Unexpected end of input")
        if expected and tok != expected:
            raise ValueError(f"Expected {expected!r} but got {tok!r}")
        self.pos += 1
        return tok

    def parse(self) -> Node:
        if not self.tokens:
            raise ValueError("Empty keyword expression")
        node = self._parse_or()
        if self.peek() is not None:
            raise ValueError(f"Unexpected token: {self.peek()!r}")
        return node

    def _parse_or(self) -> Node:
        node = self._parse_and()
        while True:
            tok = self.peek()
            if tok == "OR":
                self.consume("OR")
                rhs = self._parse_and()
                node = OrNode(node, rhs)
            else:
                break
        return node

    def _parse_and(self) -> Node:
        node = self._parse_not()
        while True:
            tok = self.peek()
            if tok == "AND":
                self.consume("AND")
                rhs = self._parse_not()
                node = AndNode(node, rhs)
            else:
                break
        return node

    def _parse_not(self) -> Node:
        tok = self.peek()
        if tok == "NOT":
            self.consume("NOT")
            node = self._parse_not()
            return NotNode(node)
        return self._parse_atom()

    def _parse_atom(self) -> Node:
        tok = self.peek()
        if tok == "(":
            self.consume("(")
            node = self._parse_or()
            if self.peek() != ")":
                raise ValueError("Missing closing parenthesis")
            self.consume(")")
            return node
        if tok is None:
            raise ValueError("Unexpected end of input while parsing term")
        self.consume()
        return TermNode(tok)


# Build AST from query; return None for empty input; raises ValueError on syntax errors
def build_keyword_node(query: Optional[str]) -> Optional[Node]:
    if query is None:
        return None
    q = query.strip()
    if not q:
        return None
    tokens = _tokenize(q)
    parser = Parser(tokens)
    node = parser.parse()  # may raise ValueError
    return node