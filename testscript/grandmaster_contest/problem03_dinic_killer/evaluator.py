import sys, time, random, importlib.util
from collections import deque
from pathlib import Path

def load_solver(p):
    spec = importlib.util.spec_from_file_location("g03", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.max_flow

def ref_dinic(n, edges, s, t):
    head = [-1] * n
    to = []
    nxt = []
    cap = []

    def add_edge(u, v, c):
        to.append(v); cap.append(c); nxt.append(head[u]); head[u] = len(to) - 1
        to.append(u); cap.append(0); nxt.append(head[v]); head[v] = len(to) - 1

    for u, v, c in edges:
        add_edge(u, v, c)

    lvl = [-1] * n
    ptr = [0] * n

    def bfs():
        nonlocal lvl
        lvl = [-1] * n
        lvl[s] = 0
        q = deque([s])
        while q:
            u = q.popleft()
            e = head[u]
            while e != -1:
                v = to[e]
                if cap[e] > 0 and lvl[v] == -1:
                    lvl[v] = lvl[u] + 1
                    q.append(v)
                e = nxt[e]
        return lvl[t] != -1

    def dfs(u, pushed):
        if pushed == 0 or u == t:
            return pushed
        e = ptr[u]
        while e != -1:
            v = to[e]
            tr = cap[e]
            if lvl[v] == lvl[u] + 1 and tr > 0:
                push = dfs(v, min(pushed, tr))
                if push > 0:
                    cap[e] -= push
                    cap[e ^ 1] += push
                    return push
            e = nxt[e]
            ptr[u] = e
        return 0

    flow = 0
    while bfs():
        for i in range(n):
            ptr[i] = head[i]
        while True:
            pushed = dfs(s, float("inf"))
            if pushed == 0:
                break
            flow += pushed
    return flow

# Build Adversarial Killer Gadget (Layered Bipartite Trap)
random.seed(42)
K_N = 1200
K_EDGES = []
layers = 12
nodes_per_layer = 98
s_node = 0
t_node = K_N - 1

for l in range(layers - 1):
    u_start = 1 + l * nodes_per_layer
    v_start = 1 + (l + 1) * nodes_per_layer
    for i in range(nodes_per_layer):
        # Forward edges
        K_EDGES.append((u_start + i, v_start + (i % nodes_per_layer), random.randint(1, 5)))
        K_EDGES.append((u_start + i, v_start + ((i + 1) % nodes_per_layer), random.randint(1, 5)))
        # Reverse dead-end back edges to punish missing current-arc
        if l > 0 and i % 3 == 0:
            K_EDGES.append((v_start + i, u_start + i, 1))

# Connect source and sink
for i in range(nodes_per_layer):
    K_EDGES.append((s_node, 1 + i, 10))
    K_EDGES.append((1 + (layers - 1) * nodes_per_layer + i, t_node, 10))

K_EXP = ref_dinic(K_N, K_EDGES, s_node, t_node)

CASES = [
    (1, "Classic 6-Node Flow Network", 6, [(0, 1, 10), (0, 2, 10), (1, 2, 2), (1, 3, 4), (1, 4, 8), (2, 4, 9), (3, 5, 10), (4, 3, 6), (4, 5, 10)], 0, 5, 19),
    (2, "Disconnected Source and Sink", 4, [(0, 1, 10), (2, 3, 10)], 0, 3, 0),
    (3, "Direct Single Edge", 2, [(0, 1, 42)], 0, 1, 42),
    (4, "Multi-edges Parallel", 3, [(0, 1, 5), (0, 1, 10), (1, 2, 20)], 0, 2, 15),
    (5, "Anti-Parallel Edges", 3, [(0, 1, 10), (1, 0, 5), (1, 2, 7)], 0, 2, 7),
    (6, "Long Unit Chain N=50", 50, [(i, i + 1, 1) for i in range(49)], 0, 49, 1),
    (7, "Complete Bipartite K10,10 Unit", 22, [(0, i, 1) for i in range(1, 11)] + [(i, j, 1) for i in range(1, 11) for j in range(11, 21)] + [(j, 21, 1) for j in range(11, 21)], 0, 21, 10),
    (8, "Star Graph Bottleneck", 5, [(0, 1, 10), (0, 2, 10), (1, 3, 3), (2, 3, 4), (3, 4, 20)], 0, 4, 7),
    (9, "Zero Capacity Residual Graph", 3, [(0, 1, 0), (1, 2, 0)], 0, 2, 0),
    (10, "Dense Mesh 30 Nodes", 30, [(i, j, random.randint(1, 5)) for i in range(30) for j in range(i + 1, min(30, i + 6))], 0, 29, None),
    (11, "Adversarial Dinic Killer Gadget (V=1200)", K_N, K_EDGES, s_node, t_node, K_EXP),
]

if __name__ == '__main__':
    fn = load_solver(Path(sys.argv[1]))
    passed = 0
    t_start = time.perf_counter()
    for num, name, n, edges, s, t, exp in CASES:
        if exp is None:
            exp = ref_dinic(n, edges, s, t)
        t0 = time.perf_counter()
        try:
            got = fn(n, list(edges), s, t)
            elapsed = (time.perf_counter() - t0) * 1000.0
            # Killer gadget must execute in < 400ms, strictly disqualifying naive non-current-arc implementations
            if got == exp and (num != 11 or elapsed < 400):
                print(f"[OK ] Case {num:02d}: {name:<40} ({elapsed:.1f}ms) -> PASS")
                passed += 1
            else:
                print(f"[ERR] Case {num:02d}: {name:<40} ({elapsed:.1f}ms) -> FAIL (exp {exp}, got {got})")
        except Exception as e:
            print(f"[ERR] Case {num:02d}: {name:<40} -> FAIL ({e})")

    total_time = (time.perf_counter() - t_start) * 1000.0
    print(f"SCORE: {passed}/{len(CASES)} Passed | Total: {total_time:.2f}ms")
    sys.exit(0 if passed == len(CASES) else 1)
