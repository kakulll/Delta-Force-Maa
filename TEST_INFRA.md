# Department Module Testing Infrastructure (TEST_INFRA.md)

## 1. Executive Summary

This document defines the automated test infrastructure and test harness designed for the **«部门每日物资兑换与福利自动领取» (Department Supplies & Welfare Redemption)** module of Delta-Force-Maa.

The testing architecture strictly implements the **4-Tier Testing Methodology** and provides continuous verification across all 12 functional features (F1 to F12), ROI coordinate boundaries, runtime option matrices, and end-to-end execution paths.

---

## 2. Infrastructure & Execution Environment

### 2.1 Technical Stack
- **Test Runner**: Python Standard Library `unittest` (Zero unpinned external dependencies).
- **Python Version**: Python 3.12 (64-bit on Windows).
- **Shell Environment**: PowerShell 7 Core (`pwsh`).
- **Target Game Resolution**: PC Win32 client at **2560 × 1600 native resolution** (16:10 aspect ratio).
- **MaaFramework Integration**: `maa` Python package with ONNX OCR and CustomController support.
- **Schema Validation Engine**: Node.js v24 + Ajv (Draft-07 & 2020-12) via `tools/validate-schema.mjs`.

### 2.2 Test Suite Location & Artifacts
| Artifact Path | Ownership | Description |
|---|---|---|
| `tests/test_department.py` | `test_writer_e2e_1` | Core 4-tier automated test suite (88 test cases) |
| `TEST_INFRA.md` | `test_writer_e2e_1` | Test architecture and harness specification |
| `TEST_READY.md` | `test_writer_e2e_1` | Test readiness and verification certification |
| `tools/validate-schema.mjs` | Shared Project Tool | Universal Pipeline and Interface JSON schema validator |
| `.agents/explorer_survey_3/` | Survey Baseline | 2560x1600 ground-truth screen captures and OCR dumps |

---

## 3. 4-Tier Testing Methodology

```
┌─────────────────────────────────────────────────────────────┐
│                 Tier 4: Real-World Scenarios                │
│ (Happy path traversal, DryRun abort, locked skips, recovery)│
├─────────────────────────────────────────────────────────────┤
│         Tier 3: Cross-Feature Combinations & Options        │
│   (FreeOnly vs FreeAndDiscounted, DryRun matrix, transitions)│
├─────────────────────────────────────────────────────────────┤
│              Tier 2: Boundary & Corner Cases                │
│    (2560x1600 ROI limits, missing fields, timeouts, locks)  │
├─────────────────────────────────────────────────────────────┤
│                Tier 1: Feature Coverage (F1-F12)            │
│       (>=5 test cases per feature across F1 to F12)         │
└─────────────────────────────────────────────────────────────┘
```

### Tier 1: Functional Feature Coverage (F1 to F12)
Every feature is validated by at least 5 isolated test cases:
1. **F1 (Lobby Navigation)**: Top navigation bar anchor detection, `[700, 30, 150, 70]` ROI verification, `Click` action type, `>=1000ms` post-delay, and `Department.CheckMainPage` next transition.
2. **F2 (Quartermaster Entry)**: Department main page recognition (`军需处`, `部门任务`), `[520, 110, 160, 60]` ROI button targeting `(605, 142)`, `Click` action, timeout limits, and transition to `Department.TabCombat`.
3. **F3 (5 Sector Tabs Traversal)**: Sequential coverage of 5 sub-departments (`战斗部门`, `医疗部门`, `后勤部门`, `战术部门`, `研发部门`) at $Y \approx 86$, coordinate bounds, and next-chain ordering.
4. **F4 (Free Pack Recognition)**: `免费` and `每日补给` keyword matching, items grid scanning ROI (`[100, 240, 1800, 1250]`), Click action, and execution prioritization over paid supplies.
5. **F5 (Discount & Quota Detection)**: `限购`, `限购1`, `限购2` badge detection, price extraction handling numbers with commas (`12,058` -> `12058`), and modal confirm routing.
6. **F6 (Confirmation Modal & DryRun)**: Modal prompt detection (`确认`, `兑换`, `购买`), `[900, 800, 760, 400]` dialog ROI, Esc cancel hook (`key: 27`), DryRun suppression (`enabled: false`), and RealRun execution (`enabled: true`).
7. **F7 (Settlement Dismissal)**: `获得道具` popup detection, blank space / confirm button dismissal, non-blocking jumpback, max hit limit (`<= 10`) loop prevention, and `>=500ms` animation delay.
8. **F8 (Safe Deadlock-Free Return)**: Primary return via `开始游戏` button `[180, 40, 160, 60]` (`center: (254, 71)`), Esc key fallback (`key: 27`), Esc counter limit (`max_hit: 3`), and `Startup.CheckLobby` verification.
9. **F9 (Declarative Pipeline Specification)**: Namespace compliance (`Department.*`), valid MaaFramework recognition types (`OCR`, `TemplateMatch`, etc.), valid action types (`Click`, `ClickKey`, etc.), and next-target referential integrity.
10. **F10 (Task Runtime Options)**: `Department` task definition with entry `Department.Start`, `DepartmentStrategyOption` cases (`FreeOnly`, `FreeAndDiscounted`), `DepartmentDryRunOption` cases (`DryRun`, `RealRun`), and option binding.
11. **F11 (Schema & Interface Registration)**: `interface.json` compliance, task schema compliance, pipeline schema compliance, and zero errors with `tools/validate-schema.mjs`.
12. **F12 (Automated Tests & Regressions)**: Fast test suite execution (`< 1.0s`), mock OCR token extraction fidelity, ground-truth OCR verification from live captures, and pure Python dependency isolation.

### Tier 2: Boundary & Corner Cases
- **Resolution Strictness**: Every ROI must satisfy $x \ge 0, y \ge 0, x+w \le 2560, y+h \le 1600$.
- **Click Target Sanity**: Calculated center coordinates $(x + w/2, y + h/2)$ must fall inside client screen.
- **Structural Integrity**: Rejection of malformed ROIs (length $\ne 4$), floating-point coordinates, and nodes missing required actions.
- **Protocol Conformance**: Rejection of unauthorized recognition algorithms (e.g. `TextMatch`) and unauthorized action types (e.g. `Press`).
- **Account Lock Handling**: Graceful handling of level/reputation locks (`等级解锁`, `暂未开放`) via routing to `Department.SkipLockedSector`.
- **Operational Guardrails**: Enforcing minimum and maximum bounds for timeouts ($500\text{ms} \le t \le 30000\text{ms}$), post-delays ($0 \le d \le 5000\text{ms}$), and max hit counts ($1 \le \text{max\_hit} \le 50$).

### Tier 3: Cross-Feature Combinations & Options
- **Mode E Pipeline Override**: Deep-merging runtime options without Python glue code:
  - `FreeOnly`: Sets `Department.ScanQuotaItem` to `enabled: false`.
  - `FreeAndDiscounted`: Sets `Department.ScanQuotaItem` to `enabled: true`.
  - `DryRun`: Sets `Department.ConfirmExchangeDialog` to `enabled: false`.
  - `RealRun`: Sets `Department.ConfirmExchangeDialog` to `enabled: true`.
- **Combination Matrix**:
  1. `FreeOnly + DryRun`: Scans only free gifts, skips paid goods, suppresses modal confirm.
  2. `FreeOnly + RealRun`: Claims free gifts, confirms modal, skips paid goods.
  3. `FreeAndDiscounted + DryRun`: Scans free and quota goods, opens modal, suppresses confirm.
  4. `FreeAndDiscounted + RealRun`: Full automatic purchase of free and quota items.
- **Target Node Existence Guarantee**: Asserts that every node referenced in `pipeline_override` exists in the base pipeline definition to prevent silent failures.

### Tier 4: Real-World Scenarios
- **Simulated Execution Engine**: `simulate_pipeline_run` simulates the pipeline graph state transitions based on mock OCR screens:
  - Scenario 4.1: Full Happy Path from Lobby -> Department -> Quartermaster -> 5 Sectors -> Free Item -> Confirm -> Settlement -> Return -> Lobby.
  - Scenario 4.2: DryRun Abort Path confirming that purchase is blocked and returns safely.
  - Scenario 4.3: Locked Sector Bypass skipping locked tabs without stalling.
  - Scenario 4.4: Successive settlement popup dismissal without loop locks.
  - Scenario 4.5: Deadlock recovery fallback via Esc key loop returning to `Startup.CheckLobby`.

---

## 4. Verification Commands

### Execute Department Test Suite:
```pwsh
python -m unittest tests/test_department.py
```
*Current Result*: `Ran 88 tests in 0.704s ... OK (skipped=3)`

### Execute Entire Project Test Suite:
```pwsh
python -m unittest discover tests
```
*Current Result*: `Ran 94 tests in 0.565s ... OK (skipped=3)`

### Execute Schema Validator:
```pwsh
node tools/validate-schema.mjs
```
*Current Result*: `[OK] local project schema is valid` (Exit code 0)
