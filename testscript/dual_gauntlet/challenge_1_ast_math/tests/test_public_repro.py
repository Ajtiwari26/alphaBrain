import unittest
import sys
from pathlib import Path

# Add root directory to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from nodes import Symbol, MatrixSymbol, Mul, Pow
from simplify import simplify

class TestPublicNonCommutativeRepro(unittest.TestCase):
    def test_non_commutative_power_must_not_commute(self):
        """
        Public Issue Description:
        When computing power of a product of non-commutative elements, e.g. (A * B)**2,
        the AST simplifier erroneously simplifies it to A**2 * B**2.
        For non-commutative matrices or operators, (A*B)**2 is A*B*A*B != A**2 * B**2.
        The power must remain un-distributed across non-commuting elements: Pow(Mul(A, B), 2).
        """
        A = MatrixSymbol("A", 2, 2)
        B = MatrixSymbol("B", 2, 2)
        
        prod = Mul(A, B)
        expr = Pow(prod, 2)
        
        simplified = simplify(expr)
        
        # (A * B)**2 must NOT simplify to A**2 * B**2
        invalid_simplified = Mul(Pow(A, 2), Pow(B, 2))
        
        self.assertNotEqual(
            simplified,
            invalid_simplified,
            f"ERROR: Non-commutative product power (A*B)**2 was incorrectly collapsed to {simplified}!"
        )
        # It should preserve Pow(Mul(A, B), 2)
        self.assertEqual(simplified, Pow(Mul(A, B), 2))

if __name__ == "__main__":
    unittest.main()
