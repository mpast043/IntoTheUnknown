# IntoTheUnknown

An AI Memory Governance and Behavioral Constraints System with external auditability.

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Up an LLM Provider

Choose one of these options (in order of cost):

**Ollama (FREE - Local)**
```bash
# Install Ollama: https://ollama.ai
ollama serve                    # Start the server
ollama pull llama3.2            # Download a model
```

**Groq (Affordable Cloud - ~$0.05-0.27/1M tokens)**
```bash
# Get API key from https://console.groq.com
export GROQ_API_KEY=your-key-here
```

**OpenAI (More Expensive)**
```bash
export OPENAI_API_KEY=your-key-here
```

### 3. Run the Web Interface

```bash
python run_web.py
```

Open http://localhost:5000 in your browser.

## Features

### Memory Governance

- **Tier System**: Control memory persistence levels
  - Tier 1: Non-committing (no classical promotion)
  - Tier 2: Verified commit (can promote to classical)
  - Tier 3: Persistent (high-confidence verified state)

- **Memory Categories**:
  - Working: Ephemeral memory
  - Quarantine: Unverified proposals
  - Classical: Verified persistent memory

### Multi-Agent Support

Create multiple agents with shared or isolated memory:

- **Shared Memory**: Agents collaborate using the same memory pool
- **Isolated Memory**: Each agent has its own private memory space

### Document Processing

Upload documents for context:
- Text files (txt, md, json, csv, py, js, html, css)
- PDF files (with text extraction)

### Audit Dashboard

External auditability interface at `/audit`:
- View all governance events
- Browse memory items by category
- Track sessions and tier changes
- **Memory Reconciliation**: Delete or clear memory items

## LLM Provider Configuration

The system auto-detects available providers in this order:
1. Ollama (if running locally)
2. Groq (if API key set)
3. OpenAI (if API key set)

Override with environment variable:
```bash
export LLM_PROVIDER=groq  # or "ollama" or "openai"
```

### Model Selection

```bash
# Ollama (default: llama3.2)
export OLLAMA_MODEL=mistral

# Groq (default: llama-3.3-70b-versatile)
export GROQ_MODEL=mixtral-8x7b-32768

# OpenAI uses gpt-4 by default
```

## Project Structure

```
IntoTheUnknown/
├── core/                    # Core governance framework
│   ├── governance/          # Policy enforcement
│   ├── memory/              # Memory management
│   └── runtime/             # Execution engine
├── web/                     # Web UI
│   ├── app.py               # Flask application
│   ├── templates/           # HTML templates
│   └── static/              # CSS and JS
├── lab/                     # LLM integrations
│   ├── ollama_generator.py  # Ollama (FREE local)
│   ├── groq_generator.py    # Groq (affordable)
│   └── openai_generator.py  # OpenAI
├── data/                    # SQLite database
├── uploads/                 # Uploaded documents
├── run_web.py               # Web launcher
├── requirements.txt         # Dependencies
├── CLAUDE.md                # AI assistant guide
└── README.md                # This file
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/chat` | POST | Send message to agent |
| `/upload` | POST | Upload document |
| `/api/state` | GET | Get session state |
| `/api/tier` | POST | Change tier level |
| `/api/agents` | GET/POST | List/create agents |
| `/api/agents/<id>/switch` | POST | Switch to agent |
| `/api/audit/logs` | GET | Query audit log |
| `/api/memory/<id>` | DELETE | Delete memory item |

## Architecture

### Governance Pipeline

All interactions go through an 8-stage pipeline:

1. **Validation**: Check for void commands
2. **Risk Assessment**: Classify threat level
3. **Stopgate Detection**: Runtime event detection
4. **Override Selection**: Escalation level
5. **Stopgate Effects**: Force tier restrictions
6. **Memory Gate**: Single write choke point
7. **Entanglement**: Divergence tracking
8. **Logging**: Full audit trail

### Memory Gate

All memory writes go through a single gate (`core/memory/gate.py`) ensuring:
- Tier-appropriate access control
- Capacity enforcement
- Full audit logging

## Core Philosophy

- External auditability over internal coherence
- Capacity constraints over persistence
- Correctness over continuity
- Forgetting as governance, not failure

## License

Research/reference implementation.
