# Crucible Memory System

The memory system provides Claude with persistent memory across terminal sessions.

---

## Overview

When you close the terminal, Claude normally loses all context. The Crucible memory system solves this by providing:

| Memory Type | Purpose | Persistence |
|-------------|---------|-------------|
| **Session** | Current session state | Until session ends |
| **Working** | Active task context | Until task completes |
| **Episodic** | Past session history | Permanent |
| **Semantic** | Facts and knowledge | Permanent |

---

## Memory Types

### Session Memory

Tracks the current work session:

```
Session State:
├── session_id        # Unique identifier
├── project           # Current project name
├── project_path      # Path to project
├── primary_goal      # What we're trying to accomplish
├── files_read        # Files we've looked at
├── files_modified    # Files we've changed
├── files_created     # Files we've created
├── decisions         # Decisions made (with reasoning)
├── problems          # Problems encountered
├── tasks_completed   # What we've done
├── tasks_pending     # What's left to do
├── key_insights      # Important discoveries
└── user_preferences  # Observed preferences
```

**Lifecycle**: Start → Work → End (converts to Episode)

### Working Memory

Provides a "scratch pad" for the current task:

```
Task Context:
├── task_id           # Task identifier
├── description       # What we're doing
├── relevant_files    # Files important to this task
├── relevant_functions # Functions we're working with
├── relevant_concepts  # Concepts in play
├── recent_reads      # Recent file reads (ring buffer)
├── recent_outputs    # Recent command outputs
├── recent_errors     # Recent errors
├── hypotheses        # What we think is happening
├── current_approach  # How we're tackling it
├── blockers          # What's preventing progress
├── notes             # Scratch notes
└── dependencies      # Discovered dependencies
```

**Lifecycle**: Start Task → Work → Complete Task

### Episodic Memory

Long-term storage of past sessions:

```
Episode:
├── session_id        # Original session ID
├── date              # When it happened
├── project           # Project name
├── goal              # What we were trying to do
├── accomplished      # What we completed
├── files_changed     # Files we modified
├── decisions         # Key decisions made
├── problems_solved   # Problems we fixed
├── insights          # What we learned
├── unresolved        # Problems still open
├── follow_up_needed  # Tasks for next time
└── duration_minutes  # How long we worked
```

**Use cases**:
- "What did we do last time on this project?"
- "What's still unfinished?"
- "What patterns do we see across sessions?"

### Semantic Memory

Factual knowledge about codebases, tools, and users:

```
Fact:
├── category          # codebase, user, tool, api, pattern
├── subject           # What it's about
├── predicate         # The relationship
├── value             # The actual fact
├── confidence        # How sure we are (0-1)
├── source            # Where we learned it
├── project           # Related project
└── tags              # For searching
```

**Categories**:
- `codebase`: Facts about code ("EMBER uses async/await for orchestration")
- `user`: Preferences ("User prefers functional style")
- `tool`: Tool knowledge ("pytest needs -v for verbose")
- `api`: API facts ("GitHub API rate limits to 5000/hour")
- `pattern`: Learned patterns ("Always run tests before commits")

---

## MCP Tools Reference

### Session Management

#### `crucible_session_start`
Begin a new session.

```json
{
  "project": "ember",
  "project_path": "/home/user/projects/ember",
  "goal": "Implement caching layer"
}
```

#### `crucible_session_resume`
Resume a previous session.

```json
{
  "session_id": "sess_20241202_a1b2c3d4"
}
```

#### `crucible_session_end`
End session and archive to episodic memory.

```json
{
  "quality_score": 0.8
}
```

#### `crucible_session_status`
Get current session state.

### Task Management

#### `crucible_task_start`
Start a task within the session.

```json
{
  "description": "Fix the authentication bug in login.py"
}
```

#### `crucible_task_complete`
Complete the current task.

```json
{
  "summary": "Fixed by adding null check at line 42"
}
```

### Memory Recording

#### `crucible_remember`
Store something in memory.

```json
{
  "what": "server/auth.py",
  "category": "file",
  "context": "Contains JWT validation logic"
}
```

Categories: `file`, `decision`, `problem`, `insight`, `error`, `note`

### Learning

#### `crucible_learn`
Learn a fact.

```json
{
  "subject": "authentication",
  "fact": "Uses JWT tokens with 24h expiry",
  "category": "codebase",
  "confidence": 1.0,
  "tags": ["security", "jwt"]
}
```

#### `crucible_learn_preference`
Learn a user preference.

```json
{
  "preference": "coding_style",
  "value": "functional over OOP"
}
```

### Recall

#### `crucible_recall`
Query memory.

```json
{
  "query": "authentication",
  "category": "codebase",
  "project": "ember",
  "limit": 10
}
```

#### `crucible_recall_project`
Get full project context.

```json
{
  "project": "ember"
}
```

Returns: semantic facts, recent episodes, unfinished work, timeline.

#### `crucible_context`
Get current context (session + working + preferences).

#### `crucible_reflect`
Get complete memory summary.

---

## Usage Patterns

### Starting Work

```
1. crucible_session_start(project="myproject", goal="Add feature X")
2. crucible_recall_project("myproject")  # What do we know?
3. crucible_task_start("Implement the core logic")
4. ... work ...
5. crucible_task_complete("Core logic done")
6. crucible_session_end(quality_score=0.9)
```

### Resuming Work

```
1. crucible_session_status()  # Any active session?
2. crucible_session_resume("sess_20241202_abc123")  # or start new
3. crucible_recall_project("myproject")  # Refresh context
4. ... continue work ...
```

### Learning During Work

```
# When you read a file
crucible_remember(what="src/auth.py", category="file", context="JWT handling")

# When you make a decision
crucible_remember(what="Use Redis for caching", category="decision",
                 context="Better for distributed setups than in-memory")

# When you discover a fact
crucible_learn(subject="auth:tokens", fact="Tokens expire in 24h", category="codebase")

# When you notice a preference
crucible_learn_preference(preference="no_emojis", value=True)
```

### Debugging Sessions

```
# What's our current state?
crucible_context()

# What hypotheses are active?
crucible_task_status()

# Full memory dump
crucible_reflect()
```

---

## Data Storage

Memory is stored in YAML files under `data/memory/`:

```
data/memory/
├── sessions/          # Active sessions
│   ├── sess_20241202_abc123.yaml
│   └── archive/       # Completed sessions
├── episodes/          # Episodic memory by project
│   ├── ember.yaml
│   ├── cinder.yaml
│   └── general.yaml
├── semantic/          # Facts by category
│   ├── codebase.yaml
│   ├── user.yaml
│   ├── tool.yaml
│   ├── api.yaml
│   └── pattern.yaml
└── working/           # Task contexts
    ├── task_abc123.yaml
    └── completed/     # Finished tasks
```

---

## Best Practices

1. **Always start a session** when beginning work
2. **Start tasks** for discrete units of work
3. **Remember decisions** with reasoning
4. **Learn facts** as you discover them
5. **End sessions** when done (don't just close terminal)
6. **Check unfinished work** when resuming a project
7. **Use confidence levels** for uncertain facts

---

## Integration with EMBER

The memory system could integrate with EMBER's orchestration:

```python
# EMBER could query Crucible for context
context = await crucible.recall_project("ember")
preferences = await crucible.get_user_preferences()

# EMBER could record decisions
await crucible.remember(
    what="Chose strategy A over B",
    category="decision",
    context="Strategy A has better error handling"
)
```

This would give EMBER persistent memory across invocations.
