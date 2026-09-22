import os
import sys
from pathlib import Path

def create_monolithic_repo(base_dir: Path):
    base_dir.mkdir(parents=True, exist_ok=True)
    src_dir = base_dir / "src"
    src_dir.mkdir(exist_ok=True)
    
    # Generate a realistic 2,500-line monolithic enterprise data pipeline module (~65,000 tokens)
    lines = [
        "// Enterprise Financial Telemetry Engine v4.8",
        "// Monolithic Core Pipeline with 120 Structs, Serialization, and Validation",
        "#![allow(dead_code)]",
        "use std::collections::{HashMap, BTreeMap};",
        "use std::sync::{Arc, Mutex};",
        ""
    ]
    
    for i in range(1, 150):
        lines.append(f"#[derive(Debug, Clone)]")
        lines.append(f"pub struct TelemetryRecordBatch{i} {{")
        lines.append(f"    pub batch_id: u64,")
        lines.append(f"    pub timestamp: i64,")
        lines.append(f"    pub ticker: String,")
        lines.append(f"    pub bid_ask_spread: f64,")
        lines.append(f"    pub volume_profile: Vec<u64>,")
        lines.append(f"    pub metrics_payload: HashMap<String, f64>,")
        lines.append(f"}}")
        lines.append("")
        lines.append(f"impl TelemetryRecordBatch{i} {{")
        lines.append(f"    pub fn calculate_weighted_index(&self) -> f64 {{")
        lines.append(f"        self.metrics_payload.values().sum::<f64>() * self.bid_ask_spread")
        lines.append(f"    }}")
        lines.append(f"    pub fn is_anomaly(&self) -> bool {{")
        lines.append(f"        self.bid_ask_spread > 0.05 || self.volume_profile.is_empty()")
        lines.append(f"    }}")
        lines.append(f"}}")
        lines.append("")

    # The target function where the refactor is needed
    lines.append("// Target processor function requiring trait implementation and mutability fix")
    lines.append("pub fn aggregate_settlement_pipeline(records: &mut [TelemetryRecordBatch1]) -> f64 {")
    lines.append("    let mut total_index = 0.0;")
    lines.append("    for record in records.iter_mut() {")
    lines.append("        total_index += record.calculate_weighted_index();")
    lines.append("    }")
    lines.append("    total_index")
    lines.append("}")
    lines.append("")

    (src_dir / "lib.rs").write_text("\n".join(lines), encoding="utf-8")
    
    # Cargo.toml
    cargo_toml = """[package]
name = "enterprise-telemetry"
version = "0.1.0"
edition = "2021"

[dependencies]
"""
    (base_dir / "Cargo.toml").write_text(cargo_toml, encoding="utf-8")
    print(f"Created monolithic enterprise repo at {base_dir} with {len(lines)} lines (~{len(lines)*28} tokens)")

if __name__ == "__main__":
    target = Path("/tmp/etta_bench_test1_ws")
    create_monolithic_repo(target)
