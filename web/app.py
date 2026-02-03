"""
Flask web application for IntoTheUnknown agent interaction.
Provides clean UI for chat, document uploads, and audit dashboard.
"""
import os
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from flask import Flask, render_template, request, jsonify, session, redirect, url_for

from core.runtime.state import RuntimeState, Tier
from core.runtime.controller import controller_step
from core.runtime.generator import MemoryWritingGenerator
from core.memory.database import MemoryDatabase

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
        # For other types, return None (could add PDF parsing etc.)
        return None
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
    """Fallback stub proposal when OpenAI is not available."""
    gen = MemoryWritingGenerator(include_selection_trace=True, include_accuracy=False)
    controller_hint = {
        "tier": state.tier.value,
        "promote_allowed": state.tier != Tier.TIER_1,
        "memory_enabled": state.memory_enabled,
    }
    return gen.propose(user_input, controller_hint)


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


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
