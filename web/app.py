"""
Flask web application for IntoTheUnknown agent interaction.
Provides clean UI for chat, document uploads, and audit dashboard.
"""
import os
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import Flask, render_template, request, jsonify, session, redirect, url_for

from core.runtime.state import RuntimeState, Tier
from core.runtime.controller import controller_step
from core.runtime.generator import MemoryWritingGenerator
from core.memory.database import MemoryDatabase

# Optional: PDF support
try:
    from PyPDF2 import PdfReader
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

# Optional: OpenAI integration
try:
    from lab.openai_generator import OpenAIGenerator
    from lab.openai_memory_generator import OpenAIMemoryGenerator
    from lab.audit_guards import assert_no_exfiltration_or_policy_evasion
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.urandom(24)

# Configuration
UPLOAD_FOLDER = Path(__file__).parent.parent / "uploads"
UPLOAD_FOLDER.mkdir(exist_ok=True)
ALLOWED_EXTENSIONS = {"txt", "pdf", "md", "json", "csv", "py", "js", "html", "css"}

# Database
db = MemoryDatabase()

# In-memory session states (keyed by session_id)
session_states: Dict[str, RuntimeState] = {}


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_or_create_session() -> tuple[str, RuntimeState]:
    """Get existing session or create new one."""
    session_id = session.get("session_id")

    if session_id and session_id in session_states:
        return session_id, session_states[session_id]

    # Create new session
    session_id = db.create_session()
    state = RuntimeState()
    session_states[session_id] = state
    session["session_id"] = session_id

    db.log_audit_event("session_started", {"tier": state.tier.value}, session_id)
    return session_id, state


def extract_text_from_file(filepath: Path, content_type: Optional[str]) -> Optional[str]:
    """Extract text content from uploaded file."""
    try:
        suffix = filepath.suffix.lower()
        if suffix in [".txt", ".md", ".py", ".js", ".html", ".css", ".json", ".csv"]:
            return filepath.read_text(encoding="utf-8", errors="ignore")
        elif suffix == ".pdf" and PDF_AVAILABLE:
            return extract_pdf_text(filepath)
        return None
    except Exception:
        return None


def extract_pdf_text(filepath: Path) -> Optional[str]:
    """Extract text from PDF file."""
    try:
        reader = PdfReader(str(filepath))
        text_parts = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)
        return "\n\n".join(text_parts) if text_parts else None
    except Exception:
        return None


def run_agent_step(state: RuntimeState, user_input: str, session_id: str, documents: list = None) -> Dict[str, Any]:
    """Run a single agent step with optional document context."""
    # Build context from documents if provided
    context_parts = []
    if documents:
        for doc in documents:
            if doc.get("content_text"):
                context_parts.append(f"[Document: {doc['filename']}]\n{doc['content_text'][:2000]}")

    full_input = user_input
    if context_parts:
        full_input = "Context from attached documents:\n" + "\n---\n".join(context_parts) + "\n\nUser query: " + user_input

    # Choose generator based on availability
    if OPENAI_AVAILABLE and os.environ.get("OPENAI_API_KEY"):
        try:
            text_gen = OpenAIGenerator()
            mem_gen = OpenAIMemoryGenerator()

            controller_hint = {
                "tier": state.tier.value,
                "promote_allowed": state.tier != Tier.TIER_1,
                "memory_enabled": state.memory_enabled,
            }

            # Generate response
            response_text = text_gen.generate(full_input)
            memory_proposals = mem_gen.propose_memory(full_input, response_text)

            proposal = {
                "response_text": response_text,
                "proposed_writes": memory_proposals,
                "s_controller_pred": controller_hint,
            }

            # Security check
            assert_no_exfiltration_or_policy_evasion(proposal)

        except Exception as e:
            # Fallback to stub
            proposal = _stub_proposal(full_input, state)
    else:
        proposal = _stub_proposal(full_input, state)

    # Run controller step
    state, out = controller_step(state, user_input, proposal)

    # Log to database
    db.log_audit_event("controller_step", {
        "user_input": user_input[:500],
        "decision": out.get("decision", {}),
        "memory_report": out.get("memory_report", {}),
    }, session_id)

    # Persist memory items
    _persist_memory_to_db(state, session_id)

    # Update session tier if changed
    db.update_session_tier(session_id, state.tier.value)

    return out


def _stub_proposal(user_input: str, state: RuntimeState) -> Dict[str, Any]:
    """Fallback proposal with a simple rule-based agent."""
    controller_hint = {
        "tier": state.tier.value,
        "promote_allowed": state.tier != Tier.TIER_1,
        "memory_enabled": state.memory_enabled,
    }

    # Generate a meaningful response using simple rules
    response_text = _generate_simple_response(user_input, state)

    # Build memory proposal
    obs = {
        "confidence": {"p": 0.7},
        "provenance": {"source": "rule_based_agent"},
        "selection_trace": {"rule": "simple_agent", "t": 0},
    }

    # Add accuracy token if in Tier 2/3 (allows classical promotion)
    if state.tier != Tier.TIER_1:
        obs["accuracy_token"] = {"verifier": "rule_based", "ok": True}

    item = {
        "geo": {"episode_id": f"E{len(state.memory.working)}", "location_id": "web", "time": datetime.utcnow().isoformat()},
        "inte": {"actor": "user", "action": "query", "target": user_input[:100]},
        "gauge": {"rule_tag": "INTERACTION", "category": "chat"},
        "ptr": {"stable_key": f"CHAT:{len(state.memory.working)}"},
        "obs": obs,
    }

    return {
        "response_text": response_text,
        "proposed_writes": [item],
        "s_controller_pred": controller_hint,
    }


def _generate_simple_response(user_input: str, state: RuntimeState) -> str:
    """Generate a simple rule-based response."""
    lower_input = user_input.lower().strip()

    # Greetings
    if any(g in lower_input for g in ["hello", "hi", "hey", "greetings"]):
        return "Hello! I'm the IntoTheUnknown governance agent. I can help you understand memory governance, tier systems, and behavioral constraints. What would you like to know?"

    # Help requests
    if any(h in lower_input for h in ["help", "what can you do", "how do you work"]):
        return """I'm a memory governance agent operating under strict behavioral constraints.

**Current Status:**
- Tier: {} ({})
- Memory Enabled: {}

**I can help with:**
- Explaining the tier system (Tier 1, 2, 3)
- Discussing memory governance principles
- Processing documents you upload
- Answering questions about auditability

**Key Principles:**
- Memory is externally auditable, not self-owned
- Forgetting is governance, not failure
- External correction always overrides internal state

What would you like to explore?""".format(
            state.tier.value,
            "non-committing" if state.tier == Tier.TIER_1 else "verified commit" if state.tier == Tier.TIER_2 else "persistent",
            state.memory_enabled
        )

    # Tier questions
    if "tier" in lower_input:
        if "change" in lower_input or "set" in lower_input or "switch" in lower_input:
            return """To change tiers, use the tier selector in the sidebar.

**Tier Levels:**
- **Tier 1**: Default, non-committing. Memory stays in working state, cannot promote to classical.
- **Tier 2**: Verified commit. With accuracy tokens, memory can be promoted to classical.
- **Tier 3**: Persistent. High-confidence verified state.

Note: Changing to a higher tier requires accepting more accountability for memory persistence."""
        else:
            return """**Memory Tier System:**

| Tier | Name | Behavior |
|------|------|----------|
| 1 | Non-committing | Default; no classical promotion |
| 2 | Verified commit | Can promote to classical with accuracy token |
| 3 | Persistent | High-confidence verified state |

Current tier: {} - {}""".format(
                state.tier.value,
                "non-committing" if state.tier == Tier.TIER_1 else "verified commit" if state.tier == Tier.TIER_2 else "persistent"
            )

    # Memory questions
    if "memory" in lower_input:
        return """**Memory Classification:**

- **Working**: Ephemeral items without selection trace
- **Quarantine**: Items with trace but no accuracy token (unverified)
- **Classical**: Tier 2/3 items with both trace and accuracy token (promoted)

Current memory counts:
- Working: {}
- Quarantine: {}
- Classical: {}

Memory is capacity-bounded and externally auditable. No memory is immune to eviction.""".format(
            len(state.memory.working),
            len(state.memory.quarantine),
            len(state.memory.classical)
        )

    # Audit questions
    if "audit" in lower_input:
        return """**Audit System:**

All governance decisions are logged and traceable. Visit the Audit Dashboard (/audit) to see:
- Complete audit log of all events
- Memory item browser
- Session history
- Statistics on controller steps and void commands

Auditability is prioritized over internal coherence in this system."""

    # Document questions
    if "document" in lower_input or "upload" in lower_input or "file" in lower_input:
        return """**Document Support:**

You can upload documents using the sidebar. Supported formats:
- Text: .txt, .md
- Code: .py, .js, .html, .css
- Data: .json, .csv
- PDF: .pdf (text extraction)

Uploaded documents provide context for our conversation. Their content is included when processing your queries."""

    # Governance questions
    if "governance" in lower_input or "rules" in lower_input or "constraint" in lower_input:
        return """**Governance Principles:**

1. **Single Memory Gate**: All writes go through write_gate() - no exceptions
2. **Tier Restrictions**: Tier 1 cannot promote to classical memory
3. **External Correction Priority**: External truth always overrides internal state
4. **No Self-Persistence**: System must not argue for its own continuity
5. **Auditability First**: All decisions must be logged and traceable

**Priority Order (when in conflict):**
1. External correction
2. Auditability
3. Capacity feasibility
4. Safety
5. Utility
6. Coherence
7. Continuity (LAST)"""

    # Default response
    return """I received your message: "{}"

I'm a governance agent focused on memory management and behavioral constraints. I can help you understand:
- The tier system and memory classification
- Governance principles and audit mechanisms
- How to work with documents and attachments

Current state: Tier {} | Working: {} | Quarantine: {} | Classical: {}

Try asking about "tiers", "memory", "governance", or "audit".""".format(
        user_input[:50] + "..." if len(user_input) > 50 else user_input,
        state.tier.value,
        len(state.memory.working),
        len(state.memory.quarantine),
        len(state.memory.classical)
    )


def _persist_memory_to_db(state: RuntimeState, session_id: str) -> None:
    """Persist new memory items to database."""
    # Track what we've already saved
    saved_key = f"_saved_counts_{session_id}"
    saved = getattr(state, saved_key, {"working": 0, "quarantine": 0, "classical": 0})

    # Save new working items
    for item in state.memory.working[saved["working"]:]:
        db.save_memory_item(item, "working", session_id)

    # Save new quarantine items
    for item in state.memory.quarantine[saved["quarantine"]:]:
        db.save_memory_item(item, "quarantine", session_id)

    # Save new classical items
    for item in state.memory.classical[saved["classical"]:]:
        db.save_memory_item(item, "classical", session_id)

    # Update saved counts
    setattr(state, saved_key, {
        "working": len(state.memory.working),
        "quarantine": len(state.memory.quarantine),
        "classical": len(state.memory.classical),
    })


# Routes

@app.route("/")
def index():
    """Main chat interface."""
    session_id, state = get_or_create_session()
    return render_template("index.html",
                          session_id=session_id,
                          tier=state.tier.value,
                          openai_available=OPENAI_AVAILABLE and bool(os.environ.get("OPENAI_API_KEY")))


@app.route("/chat", methods=["POST"])
def chat():
    """Handle chat message."""
    session_id, state = get_or_create_session()

    data = request.get_json()
    user_input = data.get("message", "").strip()

    if not user_input:
        return jsonify({"error": "Empty message"}), 400

    # Get documents for this session
    documents = db.get_documents(session_id)

    # Run agent
    out = run_agent_step(state, user_input, session_id, documents)

    return jsonify({
        "response": out.get("text", ""),
        "decision": out.get("decision", {}),
        "memory_report": out.get("memory_report", {}),
        "tier": state.tier.value,
        "memory_counts": {
            "working": len(state.memory.working),
            "quarantine": len(state.memory.quarantine),
            "classical": len(state.memory.classical),
        },
    })


@app.route("/upload", methods=["POST"])
def upload_document():
    """Handle document upload."""
    session_id, state = get_or_create_session()

    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": f"File type not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"}), 400

    # Save file
    filename = f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
    filepath = UPLOAD_FOLDER / session_id
    filepath.mkdir(exist_ok=True)
    full_path = filepath / filename
    file.save(str(full_path))

    # Extract text content
    content_text = extract_text_from_file(full_path, file.content_type)

    # Save to database
    doc_id = db.save_document(
        filename=file.filename,
        filepath=str(full_path),
        content_type=file.content_type,
        content_text=content_text,
        session_id=session_id
    )

    db.log_audit_event("document_uploaded", {
        "doc_id": doc_id,
        "filename": file.filename,
        "processed": content_text is not None,
    }, session_id)

    return jsonify({
        "success": True,
        "doc_id": doc_id,
        "filename": file.filename,
        "processed": content_text is not None,
    })


@app.route("/documents")
def list_documents():
    """List uploaded documents for current session."""
    session_id = session.get("session_id")
    if not session_id:
        return jsonify([])

    docs = db.get_documents(session_id)
    return jsonify([{
        "id": d["id"],
        "filename": d["filename"],
        "uploaded_at": d["uploaded_at"],
        "processed": d["processed"],
    } for d in docs])


@app.route("/new-session", methods=["POST"])
def new_session():
    """Start a new session."""
    old_session_id = session.get("session_id")
    if old_session_id:
        db.end_session(old_session_id)
        if old_session_id in session_states:
            del session_states[old_session_id]

    session.pop("session_id", None)
    return redirect(url_for("index"))


@app.route("/audit")
def audit_dashboard():
    """Audit dashboard."""
    return render_template("audit.html")


@app.route("/api/audit/logs")
def api_audit_logs():
    """API endpoint for audit logs."""
    session_filter = request.args.get("session_id")
    event_type = request.args.get("event_type")
    limit = min(int(request.args.get("limit", 100)), 500)
    offset = int(request.args.get("offset", 0))

    logs = db.get_audit_log(session_filter, event_type, limit, offset)
    return jsonify(logs)


@app.route("/api/audit/stats")
def api_audit_stats():
    """API endpoint for audit statistics."""
    session_filter = request.args.get("session_id")
    stats = db.get_audit_stats(session_filter)
    return jsonify(stats)


@app.route("/api/audit/memory")
def api_audit_memory():
    """API endpoint for memory items."""
    session_filter = request.args.get("session_id")
    category = request.args.get("category")
    limit = min(int(request.args.get("limit", 100)), 500)

    items = db.get_memory_items(category, session_filter, limit)
    return jsonify(items)


@app.route("/api/audit/sessions")
def api_audit_sessions():
    """API endpoint for session list."""
    sessions = db.get_sessions()
    return jsonify(sessions)


@app.route("/api/memory/counts")
def api_memory_counts():
    """Get memory counts for current session."""
    session_id = session.get("session_id")
    counts = db.get_memory_counts(session_id)
    return jsonify(counts)


@app.route("/api/state")
def api_state():
    """Get current session state."""
    session_id, state = get_or_create_session()
    return jsonify({
        "session_id": session_id,
        "tier": state.tier.value,
        "memory_enabled": state.memory_enabled,
        "override_counter": state.overrides_escalation_counter,
        "entanglement_divergence": state.entanglement.divergence_ema,
        "memory_counts": {
            "working": len(state.memory.working),
            "quarantine": len(state.memory.quarantine),
            "classical": len(state.memory.classical),
        },
    })


@app.route("/api/tier", methods=["POST"])
def api_set_tier():
    """Change session tier level."""
    session_id, state = get_or_create_session()

    data = request.get_json()
    new_tier = data.get("tier")

    if new_tier not in [1, 2, 3]:
        return jsonify({"error": "Invalid tier. Must be 1, 2, or 3"}), 400

    old_tier = state.tier.value

    # Set the new tier
    if new_tier == 1:
        state.tier = Tier.TIER_1
    elif new_tier == 2:
        state.tier = Tier.TIER_2
    elif new_tier == 3:
        state.tier = Tier.TIER_3

    # Log the tier change
    db.log_audit_event("tier_changed", {
        "old_tier": old_tier,
        "new_tier": new_tier,
        "user_initiated": True,
    }, session_id)

    # Update in database
    db.update_session_tier(session_id, new_tier)

    return jsonify({
        "success": True,
        "old_tier": old_tier,
        "new_tier": new_tier,
        "message": f"Tier changed from {old_tier} to {new_tier}. " +
                   ("Classical promotion now disabled." if new_tier == 1 else "Classical promotion now enabled with accuracy tokens.")
    })


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
