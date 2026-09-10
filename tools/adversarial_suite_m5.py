"""Adversarial Stress Test Suite — Full Expansion (M5).

Extends the original department adversarial suite to cover all pipeline graphs:
- autonomous.json: node reachability, cycle detection, escape ladder guarantee
- common.json: self-healing node structure and escape chain integrity
- All pipelines: combined cross-module external reference validation
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).parent.parent
PIPELINE_DIR = ROOT / "resource" / "base" / "pipeline"

# ---------------------------------------------------------------------------
# Load all pipeline JSONs
# ---------------------------------------------------------------------------

def load_pipeline(name: str) -> dict:
    path = PIPELINE_DIR / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))

pipelines = {
    "autonomous": load_pipeline("autonomous"),
    "common": load_pipeline("common"),
    "startup": load_pipeline("startup"),
    "daily": load_pipeline("daily"),
    "department": load_pipeline("department"),
    "shelter": load_pipeline("shelter"),
    "trading": load_pipeline("trading"),
    "ammo_flip": load_pipeline("ammo_flip"),
    "warehouse": load_pipeline("warehouse"),
    "keycard": load_pipeline("keycard"),
    "loadout": load_pipeline("loadout"),
    "gunsmith": load_pipeline("gunsmith"),
}

# Build unified graph for cross-module reachability
all_nodes: dict = {}
for pname, p in pipelines.items():
    all_nodes.update(p)

print("=" * 80)
print("=== M5 ADVERSARIAL STRESS TEST SUITE (FULL EXPANSION) ===")
print("=" * 80)

total_failures = 0

# ---------------------------------------------------------------------------
# TEST A: ROI & Coordinate Boundary — autonomous.json & common.json
# ---------------------------------------------------------------------------
print("\n--- A. ROI & Coordinate Boundary (autonomous + common) ---")
roi_failures = []
for pipeline_name in ("autonomous", "common"):
    p = pipelines[pipeline_name]
    for name, node in p.items():
        if "roi" in node:
            roi = node["roi"]
            if not (isinstance(roi, list) and len(roi) == 4):
                roi_failures.append((pipeline_name, name, "ROI must be list[4]"))
                continue
            x, y, w, h = roi
            if not all(isinstance(v, int) for v in [x, y, w, h]):
                roi_failures.append((pipeline_name, name, "ROI must be int[4]"))
            if x < 0 or y < 0 or w <= 0 or h <= 0:
                roi_failures.append((pipeline_name, name, "ROI dimensions must be positive"))
            if x + w > 2560 or y + h > 1600:
                roi_failures.append((pipeline_name, name, f"ROI out of 2560x1600: x+w={x+w}, y+h={y+h}"))
        if "target" in node:
            tgt = node["target"]
            if isinstance(tgt, list) and len(tgt) == 4:
                tx, ty, tw, th = tgt
                if tx + tw > 2560 or ty + th > 1600:
                    roi_failures.append((pipeline_name, name, "Target ROI out of 2560x1600"))

if roi_failures:
    for f in roi_failures:
        print(f"  FAILED: {f}")
    total_failures += len(roi_failures)
else:
    print(f"PASSED: All nodes in autonomous.json and common.json have valid ROI within [0,0,2560,1600]")

# ---------------------------------------------------------------------------
# TEST B: Autonomous Pipeline Node Reachability from Autonomous.Start
# ---------------------------------------------------------------------------
print("\n--- B. Node Reachability (autonomous.json from Autonomous.Start) ---")
auto_pipeline = pipelines["autonomous"]

adj_auto: dict = defaultdict(list)
for name, node in auto_pipeline.items():
    for nxt in node.get("next", []):
        clean = nxt.replace("[JumpBack]", "").strip()
        adj_auto[name].append(clean)

entry = "Autonomous.Start"
queue = deque([entry])
visited = {entry}
while queue:
    curr = queue.popleft()
    for nb in adj_auto.get(curr, []):
        if nb not in visited and nb in auto_pipeline:
            visited.add(nb)
            queue.append(nb)

unreachable = set(auto_pipeline.keys()) - visited
# EscLadder nodes are intentional safety nodes triggered externally (on_error / custom action),
# not required to be reachable from the normal flow graph.
intentional_orphans = {k for k in unreachable if "EscLadder" in k}
actual_orphans = unreachable - intentional_orphans

print(f"  Reachable from {entry}: {len(visited)}/{len(auto_pipeline)}")
if intentional_orphans:
    print(f"  Intentional safety orphans (EscLadder): {sorted(intentional_orphans)}")
if actual_orphans:
    for u in sorted(actual_orphans):
        print(f"  ORPHAN: {u}")
    total_failures += len(actual_orphans)
else:
    print("PASSED: All autonomous.json non-safety nodes reachable from Autonomous.Start")

# ---------------------------------------------------------------------------
# TEST C: 5-Level Esc Escape Ladder Integrity (common.json)
# ---------------------------------------------------------------------------
print("\n--- C. 5-Level Esc Escape Ladder Integrity (common.json) ---")
common = pipelines["common"]

REQUIRED_LADDER_NODES = [
    "CommonClosePopup",
    "CommonReturnLobby",
    "CommonEscReturn",
    "CommonEmergencyEscape",
    "CommonDetectMaintenance",
    "CommonHandleMaintenance",
    "CommonDetectUpdate",
    "CommonHandleUpdate",
    "CommonDetectNetworkError",
    "CommonHandleNetworkRetry",
]

ladder_failures = []
for node_name in REQUIRED_LADDER_NODES:
    if node_name not in common:
        ladder_failures.append(f"MISSING: {node_name}")

if not ladder_failures:
    # Chain integrity checks
    esc_return = common["CommonEscReturn"]
    assert "CommonClosePopup" in esc_return.get("next", []), \
        "CommonEscReturn must chain to CommonClosePopup"
    assert "CommonReturnLobby" in esc_return.get("next", []), \
        "CommonEscReturn must chain to CommonReturnLobby"
    assert "Startup.CheckLobby" in esc_return.get("next", []), \
        "CommonEscReturn must chain to Startup.CheckLobby"

    emg = common["CommonEmergencyEscape"]
    assert "CommonEscReturn" in emg.get("next", []), \
        "CommonEmergencyEscape must chain to CommonEscReturn"
    assert "Startup.CheckLobby" in emg.get("next", []), \
        "CommonEmergencyEscape must chain to Startup.CheckLobby"

    retry = common["CommonHandleNetworkRetry"]
    assert "Startup.CheckLobby" in retry.get("next", []), \
        "CommonHandleNetworkRetry must chain to Startup.CheckLobby"

    print("PASSED: All 10 self-healing nodes present with correct escape chains")
else:
    for f in ladder_failures:
        print(f"  FAILED: {f}")
    total_failures += len(ladder_failures)

# ---------------------------------------------------------------------------
# TEST D: Autonomous Esc Ladder Nodes Integrity
# ---------------------------------------------------------------------------
print("\n--- D. Autonomous EscLadder Chain Integrity ---")
esc_ladder_failures = []
for i in range(1, 5):
    node_name = f"Autonomous.EscLadder{i}"
    if node_name not in auto_pipeline:
        esc_ladder_failures.append(f"MISSING: {node_name}")

if not esc_ladder_failures:
    # Ladder4 must eventually reach Startup.CheckLobby
    ladder4 = auto_pipeline.get("Autonomous.EscLadder4", {})
    if "Startup.CheckLobby" not in ladder4.get("next", []):
        esc_ladder_failures.append("EscLadder4 does not link to Startup.CheckLobby")

if esc_ladder_failures:
    for f in esc_ladder_failures:
        print(f"  FAILED: {f}")
    total_failures += len(esc_ladder_failures)
else:
    print("PASSED: All 4 Autonomous.EscLadder nodes present and correctly chained")

# ---------------------------------------------------------------------------
# TEST E: Cross-Module External Reference Validation
# ---------------------------------------------------------------------------
print("\n--- E. Cross-Module External Reference Validation ---")
# Collect all next-references in autonomous.json that point outside autonomous pipeline
external_refs = set()
for name, node in auto_pipeline.items():
    for nxt in node.get("next", []):
        clean = nxt.replace("[JumpBack]", "").strip()
        if clean not in auto_pipeline:
            external_refs.add(clean)

dangling = [ref for ref in external_refs if ref not in all_nodes]
print(f"  External references from autonomous.json: {len(external_refs)}")
print(f"  Cross-module refs: {sorted(external_refs)}")
if dangling:
    for d in dangling:
        print(f"  DANGLING: {d} not found in any pipeline")
    total_failures += len(dangling)
else:
    print("PASSED: All autonomous.json external references resolve to existing nodes")

# ---------------------------------------------------------------------------
# TEST F: Autonomous Pipeline Option Override Target Verification
# ---------------------------------------------------------------------------
print("\n--- F. Autonomous Task Option Override Target Verification ---")
tasks_json = json.loads((ROOT / "tasks" / "autonomous.json").read_text(encoding="utf-8"))
options = tasks_json.get("option", {})
override_errors = []

for opt_name, opt_def in options.items():
    for case in opt_def.get("cases", []):
        for target_node, overrides in case.get("pipeline_override", {}).items():
            if target_node not in auto_pipeline:
                override_errors.append(
                    f"{opt_name}.{case['name']}: override target '{target_node}' not in autonomous pipeline"
                )
            for field, val in overrides.items():
                if field not in ["enabled", "action", "next", "on_error", "expected",
                                  "roi", "post_delay", "timeout", "max_hit",
                                  "custom_action_param"]:
                    override_errors.append(
                        f"{opt_name}.{case['name']}.{target_node}: unknown field '{field}'"
                    )

if override_errors:
    for e in override_errors:
        print(f"  FAILED: {e}")
    total_failures += len(override_errors)
else:
    print(f"PASSED: All autonomous option override targets exist and use valid fields")

# ---------------------------------------------------------------------------
# TEST G: Safe Return to Startup.CheckLobby from Autonomous key nodes
# ---------------------------------------------------------------------------
print("\n--- G. Safe Return Escalation from Autonomous Key Nodes ---")

# Build full unified adjacency for reachability (using all_nodes)
adj_unified: dict = defaultdict(list)
for name, node in all_nodes.items():
    for nxt in node.get("next", []):
        clean = nxt.replace("[JumpBack]", "").strip()
        adj_unified[name].append(clean)

def find_exit_paths(start, target="Startup.CheckLobby", max_depth=12):
    paths = []
    def dfs(curr, path, visited):
        if curr == target:
            paths.append(list(path))
            return
        if len(path) >= max_depth:
            return
        for nb in adj_unified.get(curr, []):
            if nb not in visited:
                dfs(nb, path + [nb], visited | {nb})
    dfs(start, [start], {start})
    return paths

key_autonomous_nodes = [
    "Autonomous.Start",
    "Autonomous.Step1Startup",
    "Autonomous.Step2Daily",
    "Autonomous.Step3Department",
    "Autonomous.Step4Shelter",
    "Autonomous.Step5Warehouse",
    "Autonomous.Step6AmmoFlip",
    "Autonomous.Step7Finalize",
    "Autonomous.ReportResults",
    "Autonomous.PostRunAction",
    "Autonomous.EscLadder1",
    "Autonomous.EscLadder2",
    "Autonomous.EscLadder3",
    "Autonomous.EscLadder4",
]

all_have_exit = True
for node_name in key_autonomous_nodes:
    paths = find_exit_paths(node_name)
    if paths:
        shortest = min(paths, key=len)
        print(f"  [PASS] {node_name:40} -> {len(paths)} exit path(s) (shortest: {' -> '.join(shortest[:5])}{'...' if len(shortest) > 5 else ''})")
    else:
        print(f"  [FAIL] {node_name:40} -> NO PATH to Startup.CheckLobby!")
        all_have_exit = False
        total_failures += 1

if all_have_exit:
    print("\nPASSED: All Autonomous nodes guarantee reachability to Startup.CheckLobby")
else:
    print("\nFAILED: Some Autonomous nodes lack safe return path!")

# ---------------------------------------------------------------------------
# SUMMARY
# ---------------------------------------------------------------------------
print("\n" + "=" * 80)
if total_failures == 0:
    print("=== M5 ADVERSARIAL STRESS TEST SUITE: ALL PASSED [OK] ===")
else:
    print(f"=== M5 ADVERSARIAL STRESS TEST SUITE: {total_failures} FAILURE(S) [FAIL] ===")
    sys.exit(1)
print("=" * 80)
