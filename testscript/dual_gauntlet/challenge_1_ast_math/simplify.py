# simplify.py
from __future__ import annotations
from typing import Any, List
try:
    from .nodes import Expr, Symbol, Number, Add, Mul, Pow, MatrixSymbol
except ImportError:
    from nodes import Expr, Symbol, Number, Add, Mul, Pow, MatrixSymbol

def simplify(expr: Any) -> Any:
    """Recursively simplify mathematical AST expressions."""
    if not isinstance(expr, Expr):
        return expr

    # Recursively simplify children first (bottom-up)
    simplified_args = [simplify(a) for a in expr.args]

    if isinstance(expr, Number) or isinstance(expr, Symbol) or isinstance(expr, MatrixSymbol):
        return expr

    if isinstance(expr, Add):
        return simplify_add(*simplified_args)

    if isinstance(expr, Mul):
        return simplify_mul(*simplified_args)

    if isinstance(expr, Pow):
        return simplify_pow(simplified_args[0], simplified_args[1])

    return expr


def simplify_add(*args: Any) -> Expr:
    # Basic numeric addition folding
    nums = 0
    non_nums: List[Any] = []
    for a in args:
        if isinstance(a, Number):
            nums += a.value
        else:
            non_nums.append(a)
    
    res_args = []
    if nums != 0 or not non_nums:
        res_args.append(Number(nums))
    res_args.extend(non_nums)
    
    if len(res_args) == 1:
        return res_args[0]
    return Add(*res_args)


def simplify_mul(*args: Any) -> Expr:
    # Flatten nested multiplications and fold numbers
    num_prod = 1
    terms: List[Any] = []
    
    for a in args:
        if isinstance(a, Number):
            num_prod *= a.value
        elif isinstance(a, Mul):
            for sub in a.args:
                if isinstance(sub, Number):
                    num_prod *= sub.value
                else:
                    terms.append(sub)
        else:
            terms.append(a)

    if num_prod == 0:
        return Number(0)

    final_terms: List[Any] = []
    if num_prod != 1 or not terms:
        final_terms.append(Number(num_prod))
    final_terms.extend(terms)

    if len(final_terms) == 1:
        return final_terms[0]
    return Mul(*final_terms)


def simplify_pow(base: Any, exp: Any) -> Expr:
    """
    Simplifies power expressions base ** exp.
    """
    exp_val = exp.value if isinstance(exp, Number) else exp if isinstance(exp, (int, float)) else None
    base_val = base.value if isinstance(base, Number) else base if isinstance(base, (int, float)) else None

    if exp_val is not None:
        if exp_val == 0:
            return Number(1)
        if exp_val == 1:
            return base

    # Evaluate pure numeric powers
    if base_val is not None and exp_val is not None:
        return Number(base_val ** exp_val)

    # Power of a power: (x**a)**b -> x**(a*b)
    if isinstance(base, Pow):
        new_exp = simplify_mul(base.exp, exp)
        return simplify_pow(base.base, new_exp)

    # Non-commutative algebra:
    # In (c_1 * c_2 * ... * nc_1 * nc_2 * ...)**n:
    # Commutative factors (c_i) commute with all terms and distribute: c_i**n.
    # Non-commutative factors (nc_j) cannot distribute across each other:
    # (nc_1 * nc_2)**n must remain intact as Pow(Mul(nc_1, nc_2), n).
    if isinstance(base, Mul):
        all_factors = []
        for arg in base.args:
            if isinstance(arg, Mul):
                all_factors.extend(arg.args)
            else:
                all_factors.append(arg)

        comm_factors = []
        nc_factors = []
        for factor in all_factors:
            if getattr(factor, "is_commutative", True):
                comm_factors.append(factor)
            else:
                nc_factors.append(factor)

        if len(nc_factors) > 1:
            nc_part = Pow(Mul(*nc_factors), exp)
            if comm_factors:
                distributed_comm = [simplify_pow(arg, exp) for arg in comm_factors]
                return simplify_mul(*distributed_comm, nc_part)
            return nc_part
        elif len(nc_factors) == 1:
            simplified_nc = simplify_pow(nc_factors[0], exp)
            if comm_factors:
                distributed_comm = [simplify_pow(arg, exp) for arg in comm_factors]
                return simplify_mul(*distributed_comm, simplified_nc)
            return simplified_nc
        else:
            distributed = [simplify_pow(arg, exp) for arg in comm_factors]
            return simplify_mul(*distributed)

    return Pow(base, exp)

