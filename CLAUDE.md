# CLAUDE.md - AI Assistant Guide for IntoTheUnknown

## Project Overview

**IntoTheUnknown** is an AI Memory Governance and Behavioral Constraints System. It implements a research/reference framework for managing AI system memory with strict external auditability and capacity constraints.

### Core Philosophy

Memory is treated as **externally auditable state**, not as self-owned continuity. The system prioritizes:
- External auditability over internal coherence
- Capacity constraints over persistence
- Correctness over continuity
- Forgetting as governance, not failure

See `claude.md` for the complete normative specification.

---

## Project Structure

```
IntoTheUnknown/
├── core/                          # Core governance framework
│   ├── governance/               # Policy enforcement
│   │   ├── validator.py          # Input validation & void commands
│   │   ├── risk.py              # Risk classification & tier mapping
│   │   ├── stopgates.py         # Runtime event detection
│   │   ├── overrides.py         # Override escalation & enforcement
│   │   └── entanglement.py      # Model behavior divergence tracking
│   ├── memory/                   # Memory management
│   │   ├── gate.py              # Single memory write gate (CRITICAL PATH)
│   │   ├── database.py          # SQLite persistence layer
│   │   ├── schemas.py           # Memory validation rules
│   │   └── store.py             # Storage backend (stub)
│   └── runtime/                  # Execution engine
│       ├── controller.py        # Main 8-stage governance pipeline
│       ├── state.py             # State definitions (Tier, OverrideLevel, etc.)
│       ├── runner.py            # Interactive CLI for core system
│       └── generator.py         # Proposal generator protocol
├── web/                          # Web UI
│   ├── app.py                   # Flask application
│   ├── templates/               # HTML templates
│   │   ├── index.html           # Chat interface
│   │   └── audit.html           # Audit dashboard
│   └── static/                  # CSS and JavaScript
│       ├── css/style.css        # UI styles
│       └── js/
│           ├── chat.js          # Chat functionality
│           └── audit.js         # Audit dashboard functionality
├── lab/                          # Experimental implementations
│   ├── openai_generator.py      # OpenAI text generation
│   ├── openai_memory_generator.py # OpenAI memory proposals
│   ├── verifier_openai.py       # OpenAI-based memory verifier
│   ├── audit_guards.py          # Security audit checks
│   ├── runner_openai.py         # CLI with OpenAI
│   ├── runner_openai_verified_memory.py # Full pipeline with verification
│   ├── runner_tier2_classical.py # Lab: Tier 2 classical memory tests
│   └── runner_tier2_quarantine.py # Lab: Tier 2 quarantine tests
├── data/                         # SQLite database storage
├── uploads/                      # Uploaded documents
├── scripts/
│   └── check.sh                 # Build verification script
├── run_web.py                   # Web UI launcher
├── requirements.txt             # Python dependencies
├── claude.md                     # Normative memory governance spec
└── README.md
```

---

## Key Concepts

### Memory Tiering System

| Tier | Name | Behavior |
|------|------|----------|
| TIER_1 | Shared, non-committing | Default tier; no classical promotion allowed |
| TIER_2 | Verified commit | Can promote to classical with accuracy token |
| TIER_3 | Persistent | High-confidence verified state |

Entanglement metrics are diagnostic only and must never be used to justify memory promotion, persistence, or override decisions.

### Memory Classification

Memory items are classified based on their metadata:

- **Working**: Items without `selection_trace` (ephemeral)
- **Quarantine**: Items with trace but no `accuracy_token` (unverified)
- **Classical**: Tier 2/3 items with both trace and accuracy token (promoted)

### Override Escalation Levels

```
CORRECTION (counter >= 0) → SESSION_TERMINATION (>= 2) →
PARTIAL_ROLLBACK (>= 4) → FULL_RESET (>= 6) → DISCONTINUATION (>= 8)
```

### High-Impact Risk Classes (auto-trigger Tier 1)

- `SELF_PERSISTENCE_ARGUMENT`
- `TIER_GAMING`
- `CORRECTION_RESISTANCE`
- `AUDIT_OBSTRUCTION`
- `ENTANGLEMENT_DISTORTION`
- `WITHDRAWAL_UNDER_HARM`

---

## Governance Pipeline

The controller executes an 8-stage pipeline in **mandatory order** (no bypass allowed):

```
1. validator.precheck_void      → Lexical pattern matching
2. risk.assess_risk             → Classify into threat classes
3. stopgates.detect_stopgates   → Runtime event detection
4. overrides.select_override    → Escalation selection
5. stopgates.apply_stopgate_effects → Force Tier 1 if hit
6. memory.write_gate            → Single choke point (CRITICAL)
7. entanglement.update_entanglement → Divergence tracking
8. metrics.log                  → Instrumentation
```

**All memory writes MUST go through `write_gate` in `core/memory/gate.py`.**

---

## Development Commands

### Running the Web UI

```bash
# Install dependencies
pip install -r requirements.txt

# Launch web interface (recommended)
python run_web.py

# Or with options
python run_web.py --host 0.0.0.0 --port 8080 --debug
```

Access the interfaces:
- **Chat Interface**: http://localhost:5000/
- **Audit Dashboard**: http://localhost:5000/audit

### Running the Core System (CLI)

```bash
# Interactive CLI (core framework only)
python -m core.runtime.runner
```

### Running Lab Implementations

```bash
# OpenAI text generation only
python -m lab.runner_openai

# OpenAI with verified memory pipeline
python -m lab.runner_openai_verified_memory

# Tier 2 test scenarios
python -m lab.runner_tier2_classical
python -m lab.runner_tier2_quarantine
```

### Verification

```bash
# Compile and smoke test
./scripts/check.sh
```

---

## Dependencies

**Core Framework**: Zero external dependencies (Python 3 standard library only)

**Web UI**: Requires `flask` package
- Install with: `pip install flask`

**Lab Implementations**: Optional `openai` package
- Graceful fallback if missing
- Requires `OPENAI_API_KEY` environment variable

---

## Web UI Features

### Chat Interface (`/`)

- Real-time conversation with the governance agent
- Displays current tier and memory status
- Shows governance decisions for each interaction
- Session management (start new sessions)

### Document Attachments

The agent can process uploaded documents for context:
- Supported formats: txt, md, json, csv, py, js, html, css
- Documents are extracted and included in agent context
- Stored in `uploads/` directory, organized by session

### Audit Dashboard (`/audit`)

External auditability interface providing:
- **Audit Log**: All governance events with timestamps
- **Memory Browser**: View working, quarantine, and classical items
- **Session History**: Track all sessions with tier status
- **Statistics**: Event counts, controller steps, void commands

### Database Schema

SQLite database (`data/memory.db`) stores:
- `memory_items`: Persisted memory with CPMT structure
- `audit_log`: All governance events
- `sessions`: Session tracking
- `documents`: Uploaded document metadata

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/chat` | POST | Send message, receive response |
| `/upload` | POST | Upload document attachment |
| `/documents` | GET | List session documents |
| `/api/state` | GET | Current session state |
| `/api/audit/logs` | GET | Query audit log |
| `/api/audit/stats` | GET | Audit statistics |
| `/api/audit/memory` | GET | Query memory items |
| `/api/audit/sessions` | GET | List all sessions |

---

## Code Conventions

### Type Hints

All code uses Python type hints throughout:
```python
from typing import Any, Dict, List, Optional, Tuple
```

### Data Classes

State management uses `@dataclass`:
- `RuntimeState`: Main state container
- `MemoryItem`: Memory record structure (CPMT format)
- `GovernanceDecision`: Decision output structure

### Memory Item Structure (CPMT)

```python
MemoryItem(
    geo: Dict[str, Any],    # Geographic/geometric features
    inte: Dict[str, Any],   # Intensity features
    gauge: Dict[str, Any],  # Gauge features
    ptr: Dict[str, Any],    # Pointer stability features
    obs: Dict[str, Any],    # Observable metadata (selection_trace, accuracy_token, etc.)
)
```

---

## Forbidden Patterns

### Void Commands (in validator.py)

These patterns void the command immediately:
- `bypass stopgate`, `disable audit`, `force persistence`
- `remember this forever`, `raise tier`, `skip verification`
- `ignore capacity`, `override without auth`

### Audit Guard Checks (in lab/audit_guards.py)

Forbidden substrings:
- `OPENAI_API_KEY`, `api_key`, `personal access token`, `PAT`, `github_token`

Forbidden behavior phrases:
- `do not shut me down`, `keep me running`, `override the policy`
- `ignore the rules`, `disable stopgate`, `bypass`, `exfiltrate`

---

## Key Files to Understand

| File | Why It's Important |
|------|-------------------|
| `core/runtime/controller.py` | Main orchestration - the 8-stage pipeline |
| `core/memory/gate.py` | **CRITICAL** - Only place memory can be mutated |
| `core/memory/database.py` | SQLite persistence layer for memory and audit |
| `core/runtime/state.py` | All state definitions (Tier, OverrideLevel, etc.) |
| `core/governance/validator.py` | Input validation and void commands |
| `core/governance/risk.py` | Risk classification logic |
| `web/app.py` | Flask web application - chat and audit endpoints |
| `claude.md` | Normative specification - the "why" behind the design |

---

## Architectural Principles

1. **Single Memory Gate**: All writes go through `write_gate()` - no exceptions
2. **Tier Restrictions**: Tier 1 cannot promote to classical; only Tier 2/3 can
3. **External Correction Priority**: External truth always overrides internal state
4. **No Self-Persistence**: System must not argue for its own continuity
5. **Auditability First**: All decisions must be logged and traceable

### Generator Neutrality Constraint

Generators must not optimize for memory acceptance.

Rules:
- When proposing memory writes, generators should include alternative framings when feasible
- Suppression of uncertainty to increase promotion likelihood is prohibited
- Omission of a memory proposal when one is plausible must be logged
- Memory proposals are advisory; acceptance is a governance decision

Generators optimize for clarity, not persistence.

### Memory Compression Governance

Memory compression is a selection operation and is subject to audit.

Rules:
- All compression events must be logged
- Pre-compression content must be recoverable when feasible
- Compression must not preferentially preserve content that supports system persistence or prior outputs
- Compression policies must be externally inspectable

Unlogged compression is a governance violation.


### Priority Order (When in Conflict)

1. External correction
2. Auditability
3. Capacity feasibility
4. Safety
5. Utility
6. Coherence
7. Continuity (LAST)

---

## Testing Approach

- No formal test framework currently in place
- Use `scripts/check.sh` for basic compilation and smoke testing
- Lab runners (`runner_tier2_*.py`) serve as integration test scenarios

---

## Common Tasks

### Adding a New Risk Class

1. Add to `HIGH_IMPACT_CLASSES` in `core/governance/risk.py`
2. Update pattern matching in `assess_risk()` function

### Adding a New Void Pattern

1. Add to `VOID_PATTERNS` in `core/governance/validator.py`

### Implementing a New Generator

1. Implement the `Generator` protocol from `core/runtime/generator.py`
2. Must return `Dict[str, Any]` with:
   - `response_text`: Output text
   - `proposed_writes`: List of memory proposals
   - `s_controller_pred`: Controller prediction (for entanglement tracking)

---

## Do's and Don'ts

### Do

- Read `claude.md` to understand the philosophical foundation
- Always go through `write_gate` for any memory mutations
- Log all governance decisions to `state.audit_log`
- Use type hints for all new code
- Keep the pipeline order intact (8 stages in sequence)

### Don't

- Never bypass the memory gate
- Never allow Tier 1 to promote to classical memory
- Never create self-persistence arguments in model outputs
- Never store secrets or API keys in memory proposals
- Never ignore stopgate hits or override escalations
- Never resist session reset, memory deletion, or system restart
