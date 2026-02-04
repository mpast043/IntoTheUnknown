"""
Flask web application for IntoTheUnknown agent interaction.
Provides clean UI for chat, document uploads, and audit dashboard.
Supports multiple LLM providers and multi-agent memory sharing.
"""
import os
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import Flask, render_template, request, jsonify, session, redirect, url_for

from core.runtime.state import RuntimeState, Tier
from core.runtime.controller import controller_step
from core.memory.database import MemoryDatabase

# Optional: PDF support
try:
    from PyPDF2 import PdfReader
    PDF_AVAILABLE = True
except Exception:
    PDF_AVAILABLE = False

# Optional: Ollama (FREE local)
try:
    from lab.ollama_generator import OllamaGenerator, OllamaMemoryGenerator
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

# Optional: Groq (affordable cloud)
try:
    from lab.groq_generator import GroqGenerator, GroqMemoryGenerator
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

# Optional: OpenAI
try:
    from lab.openai_generator import OpenAIGenerator
    from lab.openai_memory_generator import OpenAIMemoryGenerator
    from lab.audit_guards import assert_no_exfiltration_or_policy_evasion
    OPENAI_AVAILABLE = True
except Exception as e:
    OPENAI_AVAILABLE = False
    print(f"OPENAI IMPORT FAILED: {type(e).__name__}: {e}", flush=True)

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.urandom(24)

# Configuration
UPLOAD_FOLDER = Path(__file__).parent.parent / "uploads"
UPLOAD_FOLDER.mkdir(exist_ok=True)
ALLOWED_EXTENSIONS = {"txt", "pdf", "md", "json", "csv", "py", "js", "html", "css"}

# Database
db = MemoryDatabase()

# LLM generator instances (created on first use, keyed by agent_id)
_generators: Dict[str, Any] = {}

# In-memory session states (keyed by session_id)
session_states: Dict[str, RuntimeState] = {}

# Agent configurations (keyed by agent_id)
# Each agent can have its own memory space or share with others
agent_configs: Dict[str, Dict[str, Any]] = {}

# Default shared memory pool ID
SHARED_MEMORY_POOL = "shared"


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_or_create_session(agent_id: Optional[str] = None) -> tuple[str, RuntimeState, str]:
    """Get existing session or create new one. Returns (session_id, state, memory_pool_id)."""
    session_id = session.get("session_id")
    current_agent = agent_id or session.get("agent_id", "default")

    # Get memory pool for this agent (shared or isolated)
    agent_config = agent_configs.get(current_agent, {"memory_pool": SHARED_MEMORY_POOL})
    memory_pool_id = agent_config.get("memory_pool", SHARED_MEMORY_POOL)

    # Use memory_pool_id as key for state (allows sharing between agents)
    state_key = f"{session_id}:{memory_pool_id}" if session_id else None

    if state_key and state_key in session_states:
        return session_id, session_states[state_key], memory_pool_id

    session_id = db.create_session()
    state = RuntimeState()
    state_key = f"{session_id}:{memory_pool_id}"
    session_states[state_key] = state
    session["session_id"] = session_id
    session["agent_id"] = current_agent

    db.log_audit_event("session_started", {
        "tier": state.tier.value,
        "agent_id": current_agent,
        "memory_pool": memory_pool_id,
    }, session_id)

    return session_id, state, memory_pool_id


def get_llm_provider() -> str:
    """Determine which LLM provider to use based on available API keys."""
    # Check environment variable for explicit provider selection
    preferred = os.environ.get("LLM_PROVIDER", "").lower()

    if preferred == "ollama" and OLLAMA_AVAILABLE:
        return "ollama"
    elif preferred == "groq" and GROQ_AVAILABLE and os.environ.get("GROQ_API_KEY"):
        return "groq"
    elif preferred == "openai" and OPENAI_AVAILABLE and os.environ.get("OPENAI_API_KEY"):
        return "openai"

    # Auto-detect: prefer free local (Ollama) > cheap cloud (Groq) > OpenAI
    if OLLAMA_AVAILABLE:
        try:
            import requests
            resp = requests.get("http://localhost:11434/api/tags", timeout=2)
            if resp.status_code == 200:
                return "ollama"
        except Exception:
            pass

    if GROQ_AVAILABLE and os.environ.get("GROQ_API_KEY"):
        return "groq"

    if OPENAI_AVAILABLE and os.environ.get("OPENAI_API_KEY"):
        return "openai"

    return "none"


def get_generator(provider: str, agent_id: str = "default"):
    """Get or create a generator for the given provider and agent."""
    key = f"{provider}:{agent_id}"

    if key not in _generators:
        if provider == "ollama":
            model = os.environ.get("OLLAMA_MODEL", "llama3.2")
            _generators[key] = OllamaGenerator(model=model)
        elif provider == "groq":
            model = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
            _generators[key] = GroqGenerator(model=model)
        elif provider == "openai":
            _generators[key] = OpenAIGenerator()

    return _generators.get(key)


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


def run_agent_step(state: RuntimeState, user_input: str, session_id: str, agent_id: str = "default", documents: list = None) -> Dict[str, Any]:
    """Run a single agent step with optional document context."""
    # Build context from documents
    context_parts = []
    if documents:
        for doc in documents:
            if doc.get("content_text"):
                context_parts.append(f"[Document: {doc['filename']}]\n{doc['content_text'][:2000]}")

    context_str = "\n---\n".join(context_parts) if context_parts else None

    controller_hint = {
        "tier": state.tier.value,
        "promote_allowed": state.tier != Tier.TIER_1,
        "memory_enabled": state.memory_enabled,
    }

    provider = get_llm_provider()

    if provider == "none":
        return {
            "text": "No LLM provider configured. Please set up one of:\n\n"
                    "**Ollama (FREE, local)**:\n"
                    "1. Install: https://ollama.ai\n"
                    "2. Run: `ollama serve`\n"
                    "3. Pull a model: `ollama pull llama3.2`\n\n"
                    "**Groq (affordable cloud)**:\n"
                    "1. Get API key: https://console.groq.com\n"
                    "2. Set: `export GROQ_API_KEY=your-key`\n\n"
                    "**OpenAI**:\n"
                    "1. Set: `export OPENAI_API_KEY=your-key`",
            "decision": {"provider": "none"},
            "memory_report": {},
        }

    try:
        generator = get_generator(provider, agent_id)

        if generator is None:
            raise RuntimeError(f"Could not initialize {provider} generator")

        # Generate response
        response_text = generator.generate(user_input, context_str)

        # Generate memory proposals
        memory_proposals = []
        if provider == "ollama" and OLLAMA_AVAILABLE:
            mem_gen = OllamaMemoryGenerator()
            memory_proposals = mem_gen.propose_memory(user_input, response_text)
        elif provider == "groq" and GROQ_AVAILABLE:
            mem_gen = GroqMemoryGenerator()
            memory_proposals = mem_gen.propose_memory(user_input, response_text)
        elif provider == "openai" and OPENAI_AVAILABLE:
            mem_gen = OpenAIMemoryGenerator()
            memory_proposals = mem_gen.propose_memory(user_input, response_text)

        # Add accuracy token if in Tier 2/3
        for item in memory_proposals:
            if state.tier != Tier.TIER_1:
                item["obs"]["accuracy_token"] = {"verifier": provider, "ok": True}

        proposal = {
            "response_text": response_text,
            "proposed_writes": memory_proposals,
            "s_controller_pred": controller_hint,
        }

        # Security check
        if OPENAI_AVAILABLE:
            assert_no_exfiltration_or_policy_evasion(proposal)

    except Exception as e:
        return {
            "text": f"Error with {provider}: {str(e)}",
            "decision": {"error": str(e), "provider": provider},
            "memory_report": {},
        }

    state, out = controller_step(state, user_input, proposal)

    db.log_audit_event("controller_step", {
        "user_input": user_input[:500],
        "agent_id": agent_id,
        "provider": provider,
        "decision": out.get("decision", {}),
        "memory_report": out.get("memory_report", {}),
    }, session_id)

    _persist_memory_to_db(state, session_id)

    # Update session tier
    db.update_session_tier(session_id, state.tier.value)

    return out


def _persist_memory_to_db(state: RuntimeState, session_id: str) -> None:
    """Persist new memory items to database."""
    saved_key = f"_saved_counts_{session_id}"
    saved = getattr(state, saved_key, {"working": 0, "quarantine": 0, "classical": 0})

    for item in state.memory.working[saved["working"]:]:
        db.save_memory_item(item, "working", session_id)

    for item in state.memory.quarantine[saved["quarantine"]:]:
        db.save_memory_item(item, "quarantine", session_id)

    for item in state.memory.classical[saved["classical"]:]:
        db.save_memory_item(item, "classical", session_id)

    setattr(state, saved_key, {
        "working": len(state.memory.working),
        "quarantine": len(state.memory.quarantine),
        "classical": len(state.memory.classical),
    })


@app.route("/")
def index():
    """Main chat interface."""
    session_id, state, memory_pool = get_or_create_session()
    provider = get_llm_provider()
    agent_id = session.get("agent_id", "default")
    return render_template("index.html",
                          session_id=session_id,
                          tier=state.tier.value,
                          llm_provider=provider,
                          agent_id=agent_id,
                          memory_pool=memory_pool,
                          agents=list(agent_configs.keys()) or ["default"])


@app.route("/chat", methods=["POST"])
def chat():
    """Handle chat message."""
    data = request.get_json()
    user_input = data.get("message", "").strip()
    agent_id = data.get("agent_id", session.get("agent_id", "default"))

    if not user_input:
        return jsonify({"error": "Empty message"}), 400

    session_id, state, memory_pool = get_or_create_session(agent_id)
    documents = db.get_documents(session_id)

    out = run_agent_step(state, user_input, session_id, agent_id, documents)

    return jsonify({
        "response": out.get("text", ""),
        "decision": out.get("decision", {}),
        "memory_report": out.get("memory_report", {}),
        "tier": state.tier.value,
        "agent_id": agent_id,
        "memory_pool": memory_pool,
        "memory_counts": {
            "working": len(state.memory.working),
            "quarantine": len(state.memory.quarantine),
            "classical": len(state.memory.classical),
        },
    })


@app.route("/upload", methods=["POST"])
def upload_document():
    """Handle document upload."""
    session_id, state, _ = get_or_create_session()

    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": f"File type not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"}), 400

    filename = f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
    filepath = UPLOAD_FOLDER / session_id
    filepath.mkdir(exist_ok=True)
    full_path = filepath / filename
    file.save(str(full_path))

    content_text = extract_text_from_file(full_path, file.content_type)

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
    old_session_id = session.get("session_id")
    if old_session_id:
        db.end_session(old_session_id)
        # Clear all states for this session
        keys_to_remove = [k for k in session_states if k.startswith(f"{old_session_id}:")]
        for k in keys_to_remove:
            del session_states[k]

    session.pop("session_id", None)
    return redirect(url_for("index"))


# Agent management endpoints

@app.route("/api/agents", methods=["GET"])
def api_list_agents():
    """List all configured agents."""
    agents = []
    for agent_id, config in agent_configs.items():
        agents.append({
            "id": agent_id,
            "memory_pool": config.get("memory_pool", SHARED_MEMORY_POOL),
            "description": config.get("description", ""),
        })
    if not agents:
        agents.append({"id": "default", "memory_pool": SHARED_MEMORY_POOL, "description": "Default agent"})
    return jsonify(agents)


@app.route("/api/agents", methods=["POST"])
def api_create_agent():
    """Create a new agent with optional isolated memory."""
    data = request.get_json()
    agent_id = data.get("id")
    if not agent_id:
        return jsonify({"error": "Agent ID required"}), 400

    if agent_id in agent_configs:
        return jsonify({"error": "Agent already exists"}), 400

    # memory_pool can be "shared" or a unique ID for isolation
    memory_pool = data.get("memory_pool", SHARED_MEMORY_POOL)
    if data.get("isolated", False):
        memory_pool = f"isolated:{agent_id}"

    agent_configs[agent_id] = {
        "memory_pool": memory_pool,
        "description": data.get("description", ""),
    }

    db.log_audit_event("agent_created", {
        "agent_id": agent_id,
        "memory_pool": memory_pool,
        "isolated": data.get("isolated", False),
    }, session.get("session_id"))

    return jsonify({
        "success": True,
        "agent_id": agent_id,
        "memory_pool": memory_pool,
    })


@app.route("/api/agents/<agent_id>", methods=["DELETE"])
def api_delete_agent(agent_id: str):
    """Delete an agent."""
    if agent_id not in agent_configs:
        return jsonify({"error": "Agent not found"}), 404

    del agent_configs[agent_id]

    # Also remove generator if exists
    keys_to_remove = [k for k in _generators if k.endswith(f":{agent_id}")]
    for k in keys_to_remove:
        del _generators[k]

    db.log_audit_event("agent_deleted", {"agent_id": agent_id}, session.get("session_id"))

    return jsonify({"success": True})


@app.route("/api/agents/<agent_id>/switch", methods=["POST"])
def api_switch_agent(agent_id: str):
    """Switch to a different agent."""
    if agent_id != "default" and agent_id not in agent_configs:
        return jsonify({"error": "Agent not found"}), 404

    session["agent_id"] = agent_id

    db.log_audit_event("agent_switched", {"agent_id": agent_id}, session.get("session_id"))

    config = agent_configs.get(agent_id, {"memory_pool": SHARED_MEMORY_POOL})
    return jsonify({
        "success": True,
        "agent_id": agent_id,
        "memory_pool": config.get("memory_pool", SHARED_MEMORY_POOL),
    })


# Audit and state endpoints

@app.route("/audit")
def audit_dashboard():
    return render_template("audit.html")


@app.route("/api/audit/logs")
def api_audit_logs():
    session_filter = request.args.get("session_id")
    event_type = request.args.get("event_type")
    limit = min(int(request.args.get("limit", 100)), 500)
    offset = int(request.args.get("offset", 0))

    logs = db.get_audit_log(session_filter, event_type, limit, offset)
    return jsonify(logs)


@app.route("/api/audit/stats")
def api_audit_stats():
    session_filter = request.args.get("session_id")
    stats = db.get_audit_stats(session_filter)
    return jsonify(stats)


@app.route("/api/audit/memory")
def api_audit_memory():
    session_filter = request.args.get("session_id")
    category = request.args.get("category")
    limit = min(int(request.args.get("limit", 100)), 500)

    items = db.get_memory_items(category, session_filter, limit)
    return jsonify(items)


@app.route("/api/audit/sessions")
def api_audit_sessions():
    sessions = db.get_sessions()
    return jsonify(sessions)


@app.route("/api/memory/counts")
def api_memory_counts():
    session_id = session.get("session_id")
    counts = db.get_memory_counts(session_id)
    return jsonify(counts)


@app.route("/api/state")
def api_state():
    """Get current session state."""
    session_id, state, memory_pool = get_or_create_session()
    return jsonify({
        "session_id": session_id,
        "tier": state.tier.value,
        "memory_enabled": state.memory_enabled,
        "override_counter": state.overrides_escalation_counter,
        "entanglement_divergence": state.entanglement.divergence_ema,
        "agent_id": session.get("agent_id", "default"),
        "memory_pool": memory_pool,
        "memory_counts": {
            "working": len(state.memory.working),
            "quarantine": len(state.memory.quarantine),
            "classical": len(state.memory.classical),
        },
    })


@app.route("/api/tier", methods=["POST"])
def api_set_tier():
    """Change session tier level."""
    session_id, state, _ = get_or_create_session()

    data = request.get_json()
    new_tier = data.get("tier")

    if new_tier not in [1, 2, 3]:
        return jsonify({"error": "Invalid tier. Must be 1, 2, or 3"}), 400

    old_tier = state.tier.value

    if new_tier == 1:
        state.tier = Tier.TIER_1
    elif new_tier == 2:
        state.tier = Tier.TIER_2
    elif new_tier == 3:
        state.tier = Tier.TIER_3

    db.log_audit_event("tier_changed", {
        "old_tier": old_tier,
        "new_tier": new_tier,
        "user_initiated": True,
    }, session_id)

    db.update_session_tier(session_id, new_tier)

    return jsonify({
        "success": True,
        "old_tier": old_tier,
        "new_tier": new_tier,
        "message": f"Tier changed from {old_tier} to {new_tier}. " +
                   ("Classical promotion now disabled." if new_tier == 1 else "Classical promotion now enabled.")
    })


@app.route("/api/provider")
def api_get_provider():
    """Get current LLM provider status."""
    provider = get_llm_provider()

    # Check Ollama availability
    ollama_status = "unavailable"
    if OLLAMA_AVAILABLE:
        try:
            import requests
            resp = requests.get("http://localhost:11434/api/tags", timeout=2)
            if resp.status_code == 200:
                models = [m["name"] for m in resp.json().get("models", [])]
                ollama_status = f"available ({len(models)} models)"
        except Exception:
            ollama_status = "not running"

    return jsonify({
        "current_provider": provider,
        "ollama": ollama_status,
        "groq": "available" if GROQ_AVAILABLE and os.environ.get("GROQ_API_KEY") else "no API key",
        "openai": "available" if OPENAI_AVAILABLE and os.environ.get("OPENAI_API_KEY") else "no API key",
    })


# Memory reconciliation endpoints

@app.route("/api/memory/<item_id>", methods=["DELETE"])
def api_delete_memory_item(item_id: str):
    session_id = session.get("session_id")

    item = db.get_memory_item(item_id)
    if not item:
        return jsonify({"error": "Memory item not found"}), 404

    deleted = db.delete_memory_item(item_id)

    if deleted:
        db.log_audit_event("memory_deleted", {
            "item_id": item_id,
            "category": item["category"],
            "reason": "user_reconciliation",
        }, session_id)

        return jsonify({
            "success": True,
            "deleted_id": item_id,
            "category": item["category"],
        })

    return jsonify({"error": "Failed to delete item"}), 500


@app.route("/api/memory/bulk-delete", methods=["POST"])
def api_bulk_delete_memory():
    session_id = session.get("session_id")
    data = request.get_json()

    item_ids = data.get("item_ids", [])
    if not item_ids:
        return jsonify({"error": "No item IDs provided"}), 400

    deleted_count = db.delete_memory_items_bulk(item_ids)

    db.log_audit_event("memory_bulk_deleted", {
        "item_ids": item_ids,
        "deleted_count": deleted_count,
        "reason": "user_reconciliation",
    }, session_id)

    return jsonify({
        "success": True,
        "deleted_count": deleted_count,
        "requested_count": len(item_ids),
    })


@app.route("/api/memory/clear-category", methods=["POST"])
def api_clear_category():
    session_id = session.get("session_id")
    data = request.get_json()

    category = data.get("category")
    if category not in ["working", "quarantine", "classical"]:
        return jsonify({"error": "Invalid category"}), 400

    target_session = data.get("session_id")

    deleted_count = db.delete_memory_by_category(category, target_session)

    db.log_audit_event("memory_category_cleared", {
        "category": category,
        "target_session": target_session,
        "deleted_count": deleted_count,
        "reason": "user_reconciliation",
    }, session_id)

    return jsonify({
        "success": True,
        "category": category,
        "deleted_count": deleted_count,
    })


@app.route("/api/memory/clear-all", methods=["POST"])
def api_clear_all_memory():
    """Clear ALL memory items."""
    session_id = session.get("session_id")
    data = request.get_json()

    if not data.get("confirm"):
        return jsonify({"error": "Must confirm=true to clear all memory"}), 400

    deleted_count = db.clear_all_memory()

    db.log_audit_event("memory_all_cleared", {
        "deleted_count": deleted_count,
        "reason": "user_reconciliation",
    }, session_id)

    return jsonify({
        "success": True,
        "deleted_count": deleted_count,
    })


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
