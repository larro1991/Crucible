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

**Core Problem Solved**: "Vibe coding" - AI writes code it can't run, leading to errors discovered only when the user tries it.

**Solution**: Give Claude a workshop where code is tested *before* delivery.

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
│   │              (runs on TrueNAS VM)                         │  │
│   │                                                           │  │
│   │   Tools:                                                  │  │
│   │   • crucible.execute    - Run code/commands               │  │
│   │   • crucible.verify     - Run verification pipeline       │  │
│   │   • crucible.capture    - Capture command output          │  │
│   │   • crucible.fixture    - Manage test fixtures            │  │
│   │   • crucible.note       - Store learnings                 │  │
│   │   • crucible.recall     - Retrieve learnings              │  │
│   │   • crucible.container  - Manage Docker containers        │  │
│   │   • crucible.vm         - Manage VMs (future)             │  │
│   │                                                           │  │
│   └──────────────────────────────────────────────────────────┘  │
│                             │                                    │
│                             ▼                                    │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │                  Execution Layer                          │  │
│   │   • Docker containers (isolated execution)                │  │
│   │   • Direct execution (trusted code)                       │  │
│   │   • VM management (future)                                │  │
│   └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │                  Persistence Layer                        │  │
│   │   • fixtures/    - Captured real-world data               │  │
│   │   • learnings/   - Knowledge across sessions              │  │
│   └──────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Directory Structure

```
Crucible/
├── docs/                    # Documentation
│   ├── CLAUDE_CONTEXT.md    # THIS FILE
│   ├── ARCHITECTURE.md      # Technical details
│   ├── VM_SETUP.md          # TrueNAS VM setup guide
│   └── PROGRESS.md          # Development log
├── server/                  # MCP Server
│   ├── __init__.py
│   ├── main.py              # Server entry point
│   ├── tools/               # MCP tool implementations
│   │   ├── execute.py       # Code execution
│   │   ├── verify.py        # Verification pipeline
│   │   ├── capture.py       # Fixture capture
│   │   └── learn.py         # Learnings persistence
│   ├── verification/        # Verification modules
│   │   ├── syntax.py
│   │   ├── imports.py
│   │   ├── types.py
│   │   ├── lint.py
│   │   └── security.py
│   └── persistence/         # Storage layer
│       ├── fixtures.py
│       └── learnings.py
├── vm/                      # VM configuration
│   ├── setup/               # Setup scripts
│   └── templates/           # VM templates
├── fixtures/                # Stored test data
│   ├── linux/               # Linux system captures
│   ├── commands/            # Command output captures
│   └── apis/                # API response captures
├── learnings/               # Persistent knowledge
├── tests/                   # Test suite
└── docker/                  # Docker configurations
```

---

## Key Decisions

1. **MCP Server**: Integrates directly with Claude Code
2. **TrueNAS Scale VM**: Primary host for the server
3. **Docker for isolation**: Run untrusted code safely
4. **Persistent storage**: Fixtures and learnings survive restarts
5. **Future VM management**: Ability to spin up test VMs on demand

---

## Development Phases

### Phase 1: Foundation (Current)
- [ ] Project structure
- [ ] MCP server skeleton
- [ ] Basic execution tools
- [ ] VM setup documentation

### Phase 2: Verification
- [ ] Syntax checking
- [ ] Import verification
- [ ] Type checking
- [ ] Linting
- [ ] Security scanning

### Phase 3: Persistence
- [ ] Fixture management
- [ ] Learnings system
- [ ] Cross-session memory

### Phase 4: Advanced (Future)
- [ ] VM lifecycle management
- [ ] Multi-platform containers
- [ ] GPU passthrough testing
- [ ] Dedicated hardware

---

## Related Projects

- **EMBER**: AI orchestration (C:\github\ember) - potential brain integration
- **CINDER**: Fleet management (C:\github\cinder) - could use Crucible for testing
- **Intuitive OS**: Minimal OS (C:\github\intuitive-os) - primary use case for Crucible

---

## How Crucible Changes Workflow

**Before Crucible:**
```
Claude writes code → User runs it → Errors found → Claude fixes → Repeat
```

**After Crucible:**
```
Claude writes code → Crucible verifies → Crucible tests → Passes? → User receives working code
                                                      → Fails? → Claude fixes internally
```

---

## How To Resume Work

1. Read this document
2. Check docs/PROGRESS.md for latest status
3. Review server/main.py for current implementation
4. Continue from last documented state

---

## VM Access (Once Configured)

```
Host: [TrueNAS VM IP]
Port: 8080 (MCP Server)
SSH: 22 (for setup/maintenance)
```

---

## Commands Reference

```bash
# Start MCP server (on VM)
python -m server.main

# Run verification manually
python -m server.tools.verify /path/to/code.py

# Capture fixture
python -m server.tools.capture "lspci -mm" --name lspci_output
```
