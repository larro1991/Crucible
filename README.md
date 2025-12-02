# Crucible

**AI Development Verification Infrastructure**

Crucible provides Claude with a dedicated environment to execute, verify, and test code before delivering it to users - eliminating "vibe coding" problems. Also includes a persistent memory system so Claude can remember context across terminal sessions.

## The Problem

When AI writes code it cannot run:
- Syntax errors hide until runtime
- Import issues go unnoticed
- Logic bugs aren't caught
- Platform assumptions are untested
- Context is lost when terminal closes

## The Solution

Crucible gives Claude:
- **Execution environment** - Actually run code before delivery
- **Verification pipeline** - Check syntax, imports, types, security
- **Fixture capture** - Real command outputs for testing
- **Persistent memory** - Remember context across sessions
- **Session management** - Track progress and decisions

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         CRUCIBLE                                 │
│                                                                  │
│   Claude Code ──────► MCP Server ──────► Execution Layer        │
│                           │                    │                 │
│                           │              ┌─────┴─────┐          │
│                           │              │  Docker   │          │
│                           │              │ Containers│          │
│                           │              └───────────┘          │
│                           │                                      │
│                           ▼                                      │
│                    Persistence Layer                             │
│                    ┌──────────────────────────────┐             │
│                    │  Fixtures    │  Learnings    │             │
│                    ├──────────────┴───────────────┤             │
│                    │         Memory System        │             │
│                    │  Session │ Episodic │ Facts  │             │
│                    └──────────────────────────────┘             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### Option 1: Docker (Recommended)

```bash
# Clone
git clone https://github.com/larro1991/Crucible.git
cd Crucible

# Start with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f
```

### Option 2: Direct Installation

```bash
# Clone
git clone https://github.com/larro1991/Crucible.git
cd Crucible

# Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run
python -m server.main
```

### Claude Code Configuration

For Docker:
```json
{
  "mcpServers": {
    "crucible": {
      "command": "docker",
      "args": ["exec", "-i", "crucible", "python", "-m", "server.main"]
    }
  }
}
```

For SSH to VM:
```json
{
  "mcpServers": {
    "crucible": {
      "command": "ssh",
      "args": ["crucible@<VM_IP>", "cd ~/Crucible && ./venv/bin/python -m server.main"]
    }
  }
}
```

## MCP Tools

### Execution & Verification

| Tool | Purpose |
|------|---------|
| `crucible_execute` | Run code in isolated environment |
| `crucible_verify` | Check syntax, imports, types, lint, security |
| `crucible_capture` | Capture command output as fixture |
| `crucible_fixture` | Retrieve stored fixture |
| `crucible_note` | Store learning for future reference |
| `crucible_recall` | Retrieve learnings by topic/tag/search |

### Memory System

| Tool | Purpose |
|------|---------|
| `crucible_session_start` | Begin a memory session |
| `crucible_session_resume` | Resume a previous session |
| `crucible_session_end` | End and archive session |
| `crucible_remember` | Store file/decision/problem/insight |
| `crucible_learn` | Learn a fact about code or preferences |
| `crucible_recall_project` | Get full project context |
| `crucible_context` | Get current working context |
| `crucible_reflect` | Full memory system summary |

### System Maintenance

| Tool | Purpose |
|------|---------|
| `crucible_cleanup` | Run cleanup (quick/deep/full modes) |
| `crucible_cleanup_docker` | Docker cleanup (containers, images, volumes) |
| `crucible_cleanup_filesystem` | Filesystem cleanup (temp, logs, cache) |
| `crucible_system_status` | Get complete system status |
| `crucible_disk_usage` | Get Crucible disk usage |
| `crucible_docker_status` | Get Docker resource status |

## Memory System

The memory system provides Claude with persistent context:

| Memory Type | Purpose |
|-------------|---------|
| **Session** | Current session state (project, files, decisions) |
| **Working** | Active task context (hypotheses, blockers) |
| **Episodic** | Past session history (what happened before) |
| **Semantic** | Facts and knowledge (codebase info, preferences) |

See [docs/MEMORY.md](docs/MEMORY.md) for full documentation.

## Directory Structure

```
Crucible/
├── server/              # MCP Server
│   ├── main.py          # Entry point
│   ├── tools/           # Tool implementations
│   │   ├── execute.py   # Code execution
│   │   ├── verify.py    # Verification pipeline
│   │   ├── capture.py   # Fixture capture
│   │   ├── learn.py     # Learnings management
│   │   └── memory.py    # Memory system tools
│   ├── memory/          # Memory system
│   │   ├── manager.py   # Unified interface
│   │   ├── session.py   # Session memory
│   │   ├── episodic.py  # Episode history
│   │   ├── semantic.py  # Facts & knowledge
│   │   └── working.py   # Task context
│   └── persistence/     # Storage layer
├── fixtures/            # Stored test data
├── learnings/           # Persistent knowledge
├── data/                # Memory system data
├── docs/                # Documentation
├── Dockerfile           # Docker build
├── docker-compose.yml   # Docker compose
└── tests/               # Test suite
```

## Documentation

- [VM Setup Guide](docs/VM_SETUP.md) - TrueNAS Scale VM setup
- [Memory System](docs/MEMORY.md) - Memory system documentation
- [Architecture](docs/CLAUDE_CONTEXT.md) - Technical details
- [Progress Log](docs/PROGRESS.md) - Development status

## How It Changes Workflow

**Before:**
```
Claude writes code → User runs it → Errors found → Fix → Repeat
Terminal closes → Context lost → Start over
```

**After:**
```
Claude writes code → Crucible verifies → Crucible tests → User receives working code
Terminal closes → Resume session → Continue with full context
```

## Related Projects

- **EMBER** - AI orchestration system
- **CINDER** - Fleet management system
- **Intuitive OS** - Minimal AI-native operating system

## License

MIT
