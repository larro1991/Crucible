# Crucible

**AI Development Verification Infrastructure**

Crucible provides Claude with a dedicated environment to execute, verify, and test code before delivering it to users - eliminating "vibe coding" problems.

## The Problem

When AI writes code it cannot run:
- Syntax errors hide until runtime
- Import issues go unnoticed
- Logic bugs aren't caught
- Platform assumptions are untested

## The Solution

Crucible gives Claude:
- **Execution environment** - Actually run code before delivery
- **Verification pipeline** - Check syntax, imports, types, security
- **Fixture capture** - Real command outputs for testing
- **Persistent memory** - Learn from past sessions

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
│                    ┌──────────────┐                             │
│                    │  Fixtures    │                             │
│                    │  Learnings   │                             │
│                    └──────────────┘                             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## MCP Tools

| Tool | Purpose |
|------|---------|
| `crucible_execute` | Run code in isolated environment |
| `crucible_verify` | Check syntax, imports, types, lint, security |
| `crucible_capture` | Capture command output as fixture |
| `crucible_fixture` | Retrieve stored fixture |
| `crucible_note` | Store learning for future reference |
| `crucible_recall` | Retrieve learnings by topic/tag/search |
| `crucible_list_fixtures` | List available fixtures |

## Quick Start

### On the VM (Linux)

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

Add to MCP configuration:

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

## Directory Structure

```
Crucible/
├── server/              # MCP Server
│   ├── main.py          # Entry point
│   ├── tools/           # Tool implementations
│   │   ├── execute.py   # Code execution
│   │   ├── verify.py    # Verification pipeline
│   │   ├── capture.py   # Fixture capture
│   │   └── learn.py     # Learnings management
│   ├── verification/    # Verification modules
│   └── persistence/     # Storage layer
├── fixtures/            # Stored test data
├── learnings/           # Persistent knowledge
├── vm/                  # VM setup files
├── docs/                # Documentation
└── tests/               # Test suite
```

## Documentation

- [VM Setup Guide](docs/VM_SETUP.md) - TrueNAS Scale VM setup
- [Architecture](docs/CLAUDE_CONTEXT.md) - Technical details
- [Progress Log](docs/PROGRESS.md) - Development status

## How It Changes Workflow

**Before:**
```
Claude writes code → User runs it → Errors found → Fix → Repeat
```

**After:**
```
Claude writes code → Crucible verifies → Crucible tests → User receives working code
```

## Related Projects

- **EMBER** - AI orchestration system
- **CINDER** - Fleet management system
- **Intuitive OS** - Minimal AI-native operating system

## License

MIT
