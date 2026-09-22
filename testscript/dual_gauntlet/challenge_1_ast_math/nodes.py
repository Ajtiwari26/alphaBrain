# packages/math_ast/nodes.py
from __future__ import annotations
from typing import Any, Tuple, Union

class Expr:
    is_commutative: bool = True
    
    def __init__(self, *args: Any):
        self._args = tuple(args)
        self._hash = None

    @property
    def args(self) -> Tuple[Any, ...]:
        return self._args

    def __hash__(self) -> int:
        if self._hash is None:
            self._hash = hash((self.__class__.__name__, self._args, self.is_commutative))
        return self._hash

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Expr):
            return False
        return self.__class__ == other.__class__ and self._args == other._args and self.is_commutative == other.is_commutative

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({', '.join(map(repr, self._args))})"

    def __add__(self, other: Any) -> Expr:
        return Add(self, other)

    def __mul__(self, other: Any) -> Expr:
        return Mul(self, other)

    def __pow__(self, other: Any) -> Expr:
        return Pow(self, other)


class Symbol(Expr):
    def __init__(self, name: str, commutative: bool = True):
        super().__init__(name)
        self.name = name
        self.is_commutative = commutative

    def __repr__(self) -> str:
        comm_flag = "" if self.is_commutative else ", commutative=False"
        return f"Symbol('{self.name}'{comm_flag})"


class Number(Expr):
    is_commutative = True
    
    def __init__(self, value: Union[int, float]):
        super().__init__(value)
        self.value = value

    def __repr__(self) -> str:
        return str(self.value)


class Add(Expr):
    def __init__(self, *args: Any):
        super().__init__(*args)
        self.is_commutative = all(getattr(a, "is_commutative", True) for a in self._args)


class Mul(Expr):
    def __init__(self, *args: Any):
        super().__init__(*args)
        self.is_commutative = all(getattr(a, "is_commutative", True) for a in self._args)


class Pow(Expr):
    def __init__(self, base: Any, exp: Any):
        super().__init__(base, exp)
        self.base = base
        self.exp = exp
        self.is_commutative = getattr(base, "is_commutative", True)


class MatrixSymbol(Expr):
    is_commutative = False
    
    def __init__(self, name: str, rows: int, cols: int):
        super().__init__(name, rows, cols)
        self.name = name
        self.rows = rows
        self.cols = cols

    def __repr__(self) -> str:
        return f"MatrixSymbol('{self.name}', {self.rows}, {self.cols})"
