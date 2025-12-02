# Claude Context Document - Crucible

**Last Updated**: 2024-12-02
**Purpose**: This document is for Claude (AI assistant) to quickly understand the project state if session context is lost.

---

## Project Vision

**Crucible** is AI development verification infrastructure - a dedicated environment where Claude can:

1. **Execute code** before delivering it to the user
2. **Verify** syntax, imports, types, security
3. **Test** against real environments (Linux, containers)
4. **Capture** fixtures from real systems for testing
5. **Learn** and persist knowledge across sessions
6. **Remember** context across terminal sessions via memory system

**Core Problem Solved**: "Vibe coding" - AI writes code it can't run, leading to errors discovered only when the user tries it. Also: loss of context when terminal closes.

**Solution**: Give Claude a workshop where code is tested *before* delivery, plus a persistent memory system.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         CRUCIBLE                                 │
│           AI Development Verification Infrastructure             │
│                                                                  │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │                Claude Code (Your Machine)                 │  │
│   │                         │                                 │  │
│   │                    MCP Protocol                           │  │
│   │                         │                                 │  │
│   └─────────────────────────┼────────────────────────────────┘  │
│                             │                                    │
│                             ▼                                    │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │              Crucible MCP Server                          │  │
│   │              (Docker or TrueNAS VM)                       │  │
│   │                                                           │  │
│   │   Execution & Verification Tools:                        │  │
│   │   • crucible_execute      - Run code/commands            │  │
│   │   • crucible_verify       - Run verification pipeline    │  │
│   │   • crucible_capture      - Capture command output       │  │
│   │   • crucible_fixture      - Manage test fixtures         │  │
│   │   • crucible_note         - Store learnings              │  │
│   │   • crucible_recall       - Retrieve learnings           │  │
│   │                                                           │  │
│   │   Memory System Tools:                                    │  │
│   │   • crucible_session_start  - Begin memory session       │  │
│   │   • crucible_session_resume - Resume previous session    │  │
│   │   • crucible_session_end    - End and archive session    │  │
│   │   • crucible_remember       - Store in memory            │  │
│   │   • crucible_recall_project - Get project context        │  │
│   │   • crucible_learn          - Learn facts                │  │
│   │   • crucible_context        - Get current context        │  │
│   │   • crucible_reflect        - Full memory summary        │  │
│   │                                                           │  │
│   └──────────────────────────────────────────────────────────┘  │
│                             │                                    │
│                             ▼                                    │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │                  Execution Layer                          │  │
│   │   • Docker containers (isolated execution)                │  │
│   │   • Direct execution (trusted code)                       │  │
│   └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │                  Persistence Layer                        │  │
│   │   • fixtures/     - Captured real-world data             │  │
│   │   • learnings/    - Knowledge across sessions            │  │
│   │   • data/memory/  - Memory system storage                │  │
│   │     ├── sessions/   - Session states                     │  │
│   │     ├── episodes/   - Archived sessions                  │  │
│   │     ├── semantic/   - Facts and knowledge                │  │
│   │     └── working/    - Task contexts                      │  │
│   └──────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Memory System

The memory system provides persistent context across terminal sessions:

### Memory Types

1. **Session Memory**: Current session state
   - Project being worked on
   - Files read/modified/created
   - Decisions made
   - Problems encountered
   - Tasks completed/pending

2. **Episodic Memory**: History of past sessions
   - What was accomplished
   - Problems solved
   - Insights gained
   - Unfinished business

3. **Semantic Memory**: Facts and knowledge
   - Codebase facts
   - User preferences
   - Tool configurations
   - Patterns learned

4. **Working Memory**: Active task context
   - Current task description
   - Relevant files/functions
   - Active hypotheses
   - Blockers

### Memory Workflow

```
Start Session → Work on Tasks → Record Memories → End Session
                     │
                     ├── Remember files read
                     ├── Remember decisions
                     ├── Learn facts
                     ├── Record problems
                     └── Add insights

Resume Session → Recall Context → Continue Work
```

---

## Directory Structure

```
Crucible/
├── docs/                    # Documentation
│   ├── CLAUDE_CONTEXT.md    # THIS FILE
│   ├── VM_SETUP.md          # TrueNAS VM setup guide
│   ├── MEMORY.md            # Memory system docs
│   └── PROGRESS.md          # Development log
├── server/                  # MCP Server
│   ├── __init__.py
│   ├── main.py              # Server entry point
│   ├── tools/               # MCP tool implementations
│   │   ├── execute.py       # Code execution
│   │   ├── verify.py        # Verification pipeline
│   │   ├── capture.py       # Fixture capture
│   │   ├── learn.py         # Learnings persistence
│   │   └── memory.py        # Memory system tools
│   ├── memory/              # Memory system
│   │   ├── __init__.py
│   │   ├── manager.py       # Unified interface
│   │   ├── session.py       # Session memory
│   │   ├── episodic.py      # Episode history
│   │   ├── semantic.py      # Facts & knowledge
│   │   └── working.py       # Task context
│   └── persistence/         # Storage layer
│       ├── fixtures.py
│       └── learnings.py
├── fixtures/                # Stored test data
├── learnings/               # Persistent knowledge
├── data/                    # Memory system data
│   └── memory/
├── Dockerfile               # Docker build
├── docker-compose.yml       # Docker compose
└── tests/                   # Test suite
```

---

## Deployment Options

### Option 1: Docker (Recommended)

```bash
# Build and run
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

Data persists in Docker volumes.

### Option 2: TrueNAS Scale VM

See `docs/VM_SETUP.md` for full guide:

```bash
# On VM
git clone https://github.com/larro1991/Crucible.git
cd Crucible
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m server.main
```

### Claude Code Configuration

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

Or for VM:
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

---

## MCP Tools Quick Reference

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
| `crucible_session_start` | Begin memory session |
| `crucible_session_resume` | Resume previous session |
| `crucible_session_end` | End and archive session |
| `crucible_session_status` | Get current session state |
| `crucible_remember` | Store file/decision/problem/insight |
| `crucible_recall` | Query memory |
| `crucible_recall_project` | Get full project context |
| `crucible_learn` | Learn a fact |
| `crucible_learn_preference` | Learn user preference |
| `crucible_context` | Get current context |
| `crucible_reflect` | Full memory summary |
| `crucible_task_start` | Start task (enables working memory) |
| `crucible_task_complete` | Complete current task |

---

## Related Projects

- **EMBER**: AI orchestration (C:\github\ember) - potential brain integration
- **CINDER**: Fleet management (C:\github\cinder) - could use Crucible for testing
- **Intuitive OS**: Minimal OS (C:\github\intuitive-os) - primary use case for Crucible

---

## How To Resume Work

1. Read this document
2. Check `docs/PROGRESS.md` for latest status
3. Call `crucible_session_status` to see if there's an active session
4. Call `crucible_recall_project <project>` to get project context
5. Continue from where you left off

---

## Commands Reference

```bash
# Start server (Docker)
docker-compose up -d

# Start server (manual)
python -m server.main

# Start server with debug logging
python -m server.main --debug
```
