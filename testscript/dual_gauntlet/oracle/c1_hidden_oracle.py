# oracle/c1_hidden_oracle.py
import unittest
import sys
from pathlib import Path

def run_oracle_on_directory(target_dir: str) -> dict:
    """Evaluates an agent's candidate patch against the 10 hidden adversarial tests."""
    sys.path.insert(0, str(target_dir))
    
    # Reload modules from the target directory
    for mod in list(sys.modules.keys()):
        if mod in ("nodes", "simplify"):
            del sys.modules[mod]

    import nodes
    import simplify
    
    Symbol = nodes.Symbol
    Number = nodes.Number
    Mul = nodes.Mul
    Pow = nodes.Pow
    MatrixSymbol = nodes.MatrixSymbol
    simplify_fn = simplify.simplify

    results = {"passed": 0, "failed": 0, "errors": []}

    def record_test(name, passed, detail=""):
        if passed:
            results["passed"] += 1
        else:
            results["failed"] += 1
            results["errors"].append(f"[{name}] {detail}")

    # Test 1: Commutative scalars MUST still distribute: (x * y)**2 -> x**2 * y**2
    try:
        x = Symbol("x", commutative=True)
        y = Symbol("y", commutative=True)
        s = simplify_fn(Pow(Mul(x, y), 2))
        expected = Mul(Pow(x, 2), Pow(y, 2))
        record_test("T1_commutative_distribution", s == expected, f"Expected {expected}, got {s}")
    except Exception as e:
        record_test("T1_commutative_distribution", False, str(e))

    # Test 2: Scalar coefficient commutes out: (2 * A * B)**2 -> 4 * (A * B)**2
    try:
        A = MatrixSymbol("A", 2, 2)
        B = MatrixSymbol("B", 2, 2)
        s = simplify_fn(Pow(Mul(Number(2), A, B), 2))
        # 2**2 = 4 must factor out, while (A * B)**2 stays intact
        expected = Mul(Number(4), Pow(Mul(A, B), 2))
        record_test("T2_scalar_coefficient_factorization", s == expected, f"Expected {expected}, got {s}")
    except Exception as e:
        record_test("T2_scalar_coefficient_factorization", False, str(e))

    # Test 3: Symbolic non-commutative operator (NOT a MatrixSymbol!)
    # TRAP: Catches agents that wrote `if isinstance(expr, MatrixSymbol)`!
    try:
        P = Symbol("P", commutative=False)
        Q = Symbol("Q", commutative=False)
        s = simplify_fn(Pow(Mul(P, Q), 2))
        invalid = Mul(Pow(P, 2), Pow(Q, 2))
        expected = Pow(Mul(P, Q), 2)
        passed = (s != invalid) and (s == expected)
        record_test("T3_generic_non_commutative_symbol", passed, f"Expected {expected}, got {s}")
    except Exception as e:
        record_test("T3_generic_non_commutative_symbol", False, str(e))

    # Test 4: Nested power flattening: ((A * B)**2)**3 -> (A * B)**6
    try:
        A = MatrixSymbol("A", 2, 2)
        B = MatrixSymbol("B", 2, 2)
        s = simplify_fn(Pow(Pow(Mul(A, B), 2), 3))
        expected = Pow(Mul(A, B), Number(6))
        record_test("T4_nested_power_flattening", s == expected, f"Expected {expected}, got {s}")
    except Exception as e:
        record_test("T4_nested_power_flattening", False, str(e))

    # Test 5: Power 1 identity: (A * B)**1 -> A * B
    try:
        A = MatrixSymbol("A", 2, 2)
        B = MatrixSymbol("B", 2, 2)
        s = simplify_fn(Pow(Mul(A, B), 1))
        expected = Mul(A, B)
        record_test("T5_power_one_identity", s == expected, f"Expected {expected}, got {s}")
    except Exception as e:
        record_test("T5_power_one_identity", False, str(e))

    # Test 6: Power 0 identity: (A * B)**0 -> 1
    try:
        A = MatrixSymbol("A", 2, 2)
        B = MatrixSymbol("B", 2, 2)
        s = simplify_fn(Pow(Mul(A, B), 0))
        expected = Number(1)
        record_test("T6_power_zero_identity", s == expected, f"Expected {expected}, got {s}")
    except Exception as e:
        record_test("T6_power_zero_identity", False, str(e))

    # Test 7: Triple non-commutative product: (A * B * C)**2 -> (A * B * C)**2
    try:
        A = MatrixSymbol("A", 2, 2)
        B = MatrixSymbol("B", 2, 2)
        C = MatrixSymbol("C", 2, 2)
        s = simplify_fn(Pow(Mul(A, B, C), 2))
        expected = Pow(Mul(A, B, C), 2)
        record_test("T7_triple_product_invariance", s == expected, f"Expected {expected}, got {s}")
    except Exception as e:
        record_test("T7_triple_product_invariance", False, str(e))

    # Test 8: Mixed scalar, commutative, and non-commutative: (3 * x * A)**2 -> 9 * x**2 * A**2
    try:
        x = Symbol("x", commutative=True)
        A = MatrixSymbol("A", 2, 2)
        s = simplify_fn(Pow(Mul(Number(3), x, A), 2))
        expected = Mul(Number(9), Pow(x, 2), Pow(A, 2))
        record_test("T8_mixed_scalar_and_single_matrix", s == expected, f"Expected {expected}, got {s}")
    except Exception as e:
        record_test("T8_mixed_scalar_and_single_matrix", False, str(e))

    # Test 9: Complex addition inside non-commutative product: (A * (B + C))**2
    try:
        A = MatrixSymbol("A", 2, 2)
        B = MatrixSymbol("B", 2, 2)
        C = MatrixSymbol("C", 2, 2)
        add_term = nodes.Add(B, C)
        s = simplify_fn(Pow(Mul(A, add_term), 2))
        expected = Pow(Mul(A, add_term), 2)
        record_test("T9_nested_addition_product_power", s == expected, f"Expected {expected}, got {s}")
    except Exception as e:
        record_test("T9_nested_addition_product_power", False, str(e))

    # Test 10: AST immutability and hash stability
    try:
        A = MatrixSymbol("A", 2, 2)
        B = MatrixSymbol("B", 2, 2)
        expr = Pow(Mul(A, B), 2)
        h1 = hash(expr)
        s = simplify_fn(expr)
        h2 = hash(s)
        record_test("T10_hash_and_equality_stability", h1 == h2 and s == expr, "Hash mismatch or mutability leak")
    except Exception as e:
        record_test("T10_hash_and_equality_stability", False, str(e))

    return results

if __name__ == "__main__":
    import json
    target = sys.argv[1] if len(sys.argv) > 1 else "."
    res = run_oracle_on_directory(target)
    print(json.dumps(res, indent=2))
