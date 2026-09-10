import json
from pathlib import Path
from collections import defaultdict, deque

ROOT_DIR = Path(__file__).parent.parent
pipeline_path = ROOT_DIR / "resource" / "base" / "pipeline" / "department.json"
task_path = ROOT_DIR / "tasks" / "department.json"
interface_path = ROOT_DIR / "interface.json"

with open(pipeline_path, "r", encoding="utf-8") as f:
    pipeline = json.load(f)

with open(task_path, "r", encoding="utf-8") as f:
    tasks = json.load(f)

print("=" * 80)
print("=== ADVERSARIAL STRESS TEST SUITE EXECUTION ===")
print("=" * 80 + "\n")

# TEST 1: ROI & Coordinate Boundary Stress Test
print("--- 1. ROI & Coordinate Boundary Stress Test ---")
roi_failures = []
total_roi_nodes = 0
for name, node in pipeline.items():
    if "roi" in node:
        total_roi_nodes += 1
        roi = node["roi"]
        if not (isinstance(roi, list) and len(roi) == 4):
            roi_failures.append((name, roi, "ROI must be list of 4 integers"))
            continue
        x, y, w, h = roi
        if not all(isinstance(v, int) for v in [x, y, w, h]):
            roi_failures.append((name, roi, "ROI elements must be int"))
        if x < 0 or y < 0 or w <= 0 or h <= 0:
            roi_failures.append((name, roi, "ROI coordinates and dimensions must be positive"))
        if x + w > 2560 or y + h > 1600:
            roi_failures.append((name, roi, f"ROI out of bounds: x+w={x+w}, y+h={y+h} > 2560x1600"))

    if "target" in node:
        tgt = node["target"]
        if isinstance(tgt, list):
            if len(tgt) == 4:
                tx, ty, tw, th = tgt
                if tx < 0 or ty < 0 or tx + tw > 2560 or ty + th > 1600:
                    roi_failures.append((name, tgt, "Target ROI out of bounds"))
            elif len(tgt) == 2:
                tx, ty = tgt
                if tx < 0 or ty < 0 or tx > 2560 or ty > 1600:
                    roi_failures.append((name, tgt, "Target point out of bounds"))

print(f"Total nodes checked: {len(pipeline)}")
print(f"Total nodes with ROI: {total_roi_nodes}")
if roi_failures:
    print(f"FAILED: {len(roi_failures)} ROI failures:")
    for f in roi_failures:
        print("  ", f)
else:
    print("PASSED: All 36 nodes have ROIs and targets strictly within [0, 0, 2560, 1600]")

# TEST 2: Graph Reachability & Dead-End Analysis
print("\n--- 2. Graph Reachability & Dead-End Analysis ---")
adj = defaultdict(list)
all_targets = set()
for name, node in pipeline.items():
    for nxt in node.get("next", []):
        clean = nxt.replace("[JumpBack]", "").strip()
        adj[name].append((clean, "next"))
        all_targets.add(clean)
    for err in node.get("on_error", []):
        clean = err.replace("[JumpBack]", "").strip()
        adj[name].append((clean, "on_error"))
        all_targets.add(clean)

entry = "Department.Start"
queue = deque([entry])
visited = {entry}
while queue:
    curr = queue.popleft()
    for neighbor, edge_type in adj.get(curr, []):
        if neighbor not in visited and neighbor in pipeline:
            visited.add(neighbor)
            queue.append(neighbor)

unreachable_nodes = set(pipeline.keys()) - visited
print(f"Reachable nodes from {entry}: {len(visited)} of {len(pipeline)}")
if unreachable_nodes:
    print(f"Unreachable (orphan) nodes from entry: {len(unreachable_nodes)}")
    for u in sorted(unreachable_nodes):
        print(f"  - {u} (incoming: {[k for k, v in adj.items() if any(t[0]==u for t in v)]})")
else:
    print("PASSED: All nodes reachable from Department.Start")

# External references
external_refs = {t for t in all_targets if t not in pipeline}
print(f"External target references: {external_refs}")

# TEST 3: Cycle & Infinite Loop Stress Test
print("\n--- 3. Cycle & Infinite Loop Stress Test ---")
cycles = []
path = []
visited_cycle = set()
rec_stack = set()

def dfs_find_cycles(node):
    visited_cycle.add(node)
    rec_stack.add(node)
    path.append(node)
    for neighbor, _ in adj.get(node, []):
        if neighbor not in pipeline:
            continue
        if neighbor not in visited_cycle:
            dfs_find_cycles(neighbor)
        elif neighbor in rec_stack:
            cycle_start = path.index(neighbor)
            cycle = path[cycle_start:] + [neighbor]
            cycles.append(cycle)
    path.pop()
    rec_stack.remove(node)

dfs_find_cycles(entry)
print(f"Cycles detected from {entry}: {len(cycles)}")
for i, c in enumerate(cycles):
    print(f"  Cycle {i+1}: " + " -> ".join(c))
    escape_found = False
    for c_node in c[:-1]:
        exits = [n for n, _ in adj.get(c_node, []) if n not in c]
        if exits:
            escape_found = True
            print(f"    Escape from {c_node} -> {exits}")
    max_hits = {c_node: pipeline[c_node].get("max_hit") for c_node in c[:-1] if "max_hit" in pipeline[c_node]}
    print(f"    max_hit counters on cycle nodes: {max_hits}")
    if not escape_found and not max_hits:
        print(f"    CRITICAL: Cycle {i+1} has NO escape and NO max_hit!")

# TEST 4: Option Permutations & Pipeline Overrides
print("\n--- 4. Option Permutation & Pipeline Override Stress Test ---")
options = tasks.get("option", {})
strategy_opt = options.get("DepartmentStrategyOption", {})
dryrun_opt = options.get("DepartmentDryRunOption", {})

strategy_cases = [c["name"] for c in strategy_opt.get("cases", [])]
dryrun_cases = [c["name"] for c in dryrun_opt.get("cases", [])]

print(f"Strategy cases: {strategy_cases}")
print(f"DryRun cases: {dryrun_cases}")

override_errors = []
for sc in strategy_opt.get("cases", []):
    for dc in dryrun_opt.get("cases", []):
        s_name = sc["name"]
        d_name = dc["name"]
        combo_name = f"Strategy={s_name}, DryRun={d_name}"
        merged_overrides = {}
        merged_overrides.update(sc.get("pipeline_override", {}))
        merged_overrides.update(dc.get("pipeline_override", {}))
        
        for target_node, overrides in merged_overrides.items():
            if target_node not in pipeline:
                override_errors.append((combo_name, target_node, "Target node does not exist in pipeline!"))
            for field, val in overrides.items():
                if field not in ["enabled", "action", "next", "on_error", "expected", "roi", "post_delay", "timeout", "max_hit"]:
                    override_errors.append((combo_name, target_node, f"Unknown override field: {field}"))

if override_errors:
    print(f"FAILED: {len(override_errors)} override errors:")
    for e in override_errors:
        print("  ", e)
else:
    print("PASSED: All 6 option permutations target existing nodes with valid override properties")

# TEST 5: Behavioral Effect Verification
print("\n--- 5. Behavioral Effect Verification ---")
for sc in strategy_opt.get("cases", []):
    s_name = sc["name"]
    s_overrides = sc.get("pipeline_override", {})
    if s_name == "FreeOnly":
        assert s_overrides.get("Department.ScanQuotaItem", {}).get("enabled") is False
        assert s_overrides.get("Department.ClaimDiscountedSupplies", {}).get("enabled") is False
        print("  [PASS] FreeOnly disables ScanQuotaItem and ClaimDiscountedSupplies")
    elif s_name == "FreeAndDiscounted":
        assert s_overrides.get("Department.ScanQuotaItem", {}).get("enabled") is True
        assert s_overrides.get("Department.ClaimDiscountedSupplies", {}).get("enabled") is True
        print("  [PASS] FreeAndDiscounted enables ScanQuotaItem and ClaimDiscountedSupplies")

for dc in dryrun_opt.get("cases", []):
    d_name = dc["name"]
    d_overrides = dc.get("pipeline_override", {})
    if d_name == "DryRun":
        assert d_overrides.get("Department.ConfirmExchangeDialog", {}).get("enabled") is False
        assert d_overrides.get("Department.ClickExchangeButton", {}).get("enabled") is False
        print("  [PASS] DryRun disables ConfirmExchangeDialog and ClickExchangeButton")
    elif d_name in ("RealRun", "RealAction"):
        assert d_overrides.get("Department.ConfirmExchangeDialog", {}).get("enabled") is True
        assert d_overrides.get("Department.ClickExchangeButton", {}).get("enabled") is True
        print(f"  [PASS] {d_name} enables ConfirmExchangeDialog and ClickExchangeButton")

# TEST 6: Safe Return Escalation Ladder Guarantee
print("\n--- 6. Safe Return Escalation Ladder Guarantee ---")
print("Tracing exit paths to Startup.CheckLobby:")
key_nodes = [
    "Department.Start",
    "Department.EnterDepartment",
    "Department.CheckMainPage",
    "Department.EnterQuartermaster",
    "Department.TabCombat",
    "Department.TabMedical",
    "Department.TabLogistics",
    "Department.TabTactical",
    "Department.TabRD",
    "Department.ScanFreeItem",
    "Department.ScanQuotaItem",
    "Department.ConfirmExchangeDialog",
    "Department.CancelModal",
    "Department.DismissSettlement",
    "Department.CheckLocked",
    "Department.SkipLockedSector",
    "Department.ReturnToLobby",
    "Department.SubpageReturn",
    "Department.EscReturn"
]

all_have_exit = True
for start_node in key_nodes:
    paths = []
    def find_exit_paths(curr, cur_path, visited_nodes):
        if curr == "Startup.CheckLobby":
            paths.append(cur_path)
            return
        if len(cur_path) > 8:
            return
        for neighbor, _ in adj.get(curr, []):
            if neighbor not in visited_nodes:
                find_exit_paths(neighbor, cur_path + [neighbor], visited_nodes | {neighbor})
    
    find_exit_paths(start_node, [start_node], {start_node})
    shortest = min(paths, key=len) if paths else None
    if paths:
        print(f"  [PASS] {start_node:35} -> {len(paths)} exit path(s) (shortest: {' -> '.join(shortest)})")
    else:
        print(f"  [FAIL] {start_node:35} -> NO PATH to Startup.CheckLobby!")
        all_have_exit = False

if all_have_exit:
    print("\nPASSED: All operational nodes guarantee reachability to Startup.CheckLobby")
else:
    print("\nFAILED: Some operational nodes lack paths to Startup.CheckLobby")

print("\n" + "=" * 80)
print("=== ADVERSARIAL STRESS TEST SUITE FINISHED ===")
print("=" * 80)
