import sys
from pathlib import Path

WORKSPACE = Path("/tmp/etta_bench_test2_ws")
WORKSPACE.mkdir(parents=True, exist_ok=True)
src_dir = WORKSPACE / "src"
src_dir.mkdir(exist_ok=True)
tests_dir = WORKSPACE / "tests"
tests_dir.mkdir(exist_ok=True)

# Cargo.toml
cargo_toml = """[package]
name = "strict-vault"
version = "0.1.0"
edition = "2021"

[dependencies]
"""
(WORKSPACE / "Cargo.toml").write_text(cargo_toml, encoding="utf-8")

# Implementation with subtle boundary bug
lib_rs = """// Thread-safe Token Bucket Rate Limiter
pub struct TokenBucket {
    pub capacity: u64,
    pub current_tokens: u64,
}

impl TokenBucket {
    pub fn new(capacity: u64) -> Self {
        Self { capacity, current_tokens: capacity }
    }

    pub fn try_consume(&mut self, tokens: u64) -> bool {
        // Buggy: strictly greater than instead of greater than or equal to
        if self.current_tokens > tokens {
            self.current_tokens -= tokens;
            true
        } else {
            false
        }
    }
}
"""
(src_dir / "lib.rs").write_text(lib_rs, encoding="utf-8")

# Strict adversarial acceptance gate test
test_rs = """use strict_vault::TokenBucket;

#[test]
fn test_exact_capacity_consumption() {
    let mut bucket = TokenBucket::new(10);
    // Boundary condition: consuming exact capacity must return true
    assert!(bucket.try_consume(10), "Consuming exact capacity (10 tokens from 10) must succeed");
    assert_eq!(bucket.current_tokens, 0);
}
"""
(tests_dir / "boundary_test.rs").write_text(test_rs, encoding="utf-8")
print(f"Created adversarial acceptance gate workspace at {WORKSPACE}")
