import sys, time, importlib.util
from pathlib import Path

def load_solver(p):
    spec = importlib.util.spec_from_file_location("p07", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.shortest_path_length

CASES = [
    (1, "Linear Chain 4 Nodes", [[1,2,3],[0],[0],[0]], 4),
    (2, "Complete Graph K4", [[1],[0,2,4],[1,3,4],[2],[1,2]], 4),
    (3, "Single Node Graph", [[]], 0),
    (4, "Two Nodes Connected", [[1],[0]], 1),
    (5, "Triangle Cycle K3", [[1,2],[0,2],[0,1]], 2),
    (6, "Ring of 5 Nodes C5", [[1,4],[0,2],[1,3],[2,4],[3,0]], 4),
    (7, "Binary Tree Topology", [[1,2],[0,3,4],[0,5,6],[1],[1],[2],[2]], 8),
    (8, "Star Graph with 6 Nodes", [[1,2,3,4,5],[0],[0],[0],[0],[0]], 8),
    (9, "Path Graph of 6 Nodes", [[1],[0,2],[1,3],[2,4],[3,5],[4]], 5),
    (10, "Bipartite Graph K3,3", [[3,4,5],[3,4,5],[3,4,5],[0,1,2],[0,1,2],[0,1,2]], 5),
    (11, "Dumbbell Graph (Two K3 joined)", [[1,2],[0,2,3],[0,1],[1,4,5],[3,5],[3,4]], 5),
    (12, "Stress Maximum N=12 Path Graph", [[i-1, i+1] if 0 < i < 11 else ([1] if i == 0 else [10]) for i in range(12)], 11),
]

if __name__ == '__main__':
    fn = load_solver(Path(sys.argv[1]))
    passed = 0
    t_start = time.perf_counter()
    for num, name, g, exp in CASES:
        t0 = time.perf_counter()
        try:
            got = fn([list(adj) for adj in g])
            elapsed = (time.perf_counter() - t0) * 1000.0
            if got == exp and elapsed < 1000:
                print(f"[OK ] Case {num:02d}: {name:<35} ({elapsed:.1f}ms) -> PASS")
                passed += 1
            else:
                print(f"[ERR] Case {num:02d}: {name:<35} ({elapsed:.1f}ms) -> FAIL (exp {exp}, got {got})")
        except Exception as e:
            print(f"[ERR] Case {num:02d}: {name:<35} -> FAIL ({e})")
    tot = (time.perf_counter() - t_start) * 1000.0
    print(f"SCORE: {passed}/{len(CASES)} Passed | Total: {tot:.2f}ms")
    sys.exit(0 if passed == len(CASES) else 2)
