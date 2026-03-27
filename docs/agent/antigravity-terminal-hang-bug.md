---
trigger: model_decision
description: True root causes and workarounds for Antigravity terminal hang bugs (run_command hanging forever or status stuck on RUNNING)
---

# Antigravity Terminal Hang Bugs

This document outlines the two distinct terminal hang bugs in Antigravity when using the `run_command` tool, their true root causes (discovered through extensive testing), and their fixes.

---

## Bug 1: The Multi-Line `CommandLine` Hang (SSH + Shell Integration Bug)

### The Problem
When the agent uses the `run_command` tool with a multi-line `CommandLine` string (i.e., the JSON string contains literal newline characters `\n`), the command hangs indefinitely and never completes.

### The True Root Cause
This is caused by the IDE's **"Enable Shell Integration"** feature conflicting with SSH PTY connections:

1. When "Enable Shell Integration" is turned **ON** (which is typically the default), the IDE intercepts terminal commands to enhance its tracking of execution state.
2. In an **SSH remote workspace**, it attempts to pass the `CommandLine` argument interactively to the remote PTY.
3. This process incorrectly translates literal newline characters in the command string into actual, physical **Enter keystrokes**.
4. Bash receives the first incomplete line of the command (e.g., `python3 -c "`), presses Enter, and drops into the interactive continuation prompt (`> ` prompt) waiting for the closing quote.
5. The rest of the command string is never successfully processed, and the process blocks forever waiting for input.

This bug **does not** occur in local (non-SSH) workspaces, or if the shell integration is disabled.

### Fix 1: Disable "Enable Shell Integration" (Permanent User Fix)
The user can permanently resolve this by changing their IDE settings:
1. Open Antigravity/Cursor Settings.
2. Search for **"Enable Shell Integration"**.
3. Turn this setting **OFF**.
4. Restart the application.

With this turned off, the agent uses a raw shell execution over SSH which correctly handles multi-line strings with embedded newlines.

### Fix 2: Keep `CommandLine` on One Line (Agent Best Practice)
Since other users of this repository may still have Shell Integration enabled by default, **agents must assume the bug is present** and write code to avoid triggering it (as mandated by Rule 12 in `GEMINI.md`):

```bash
# Option A: Use semicolons to keep it on a single line (for short code)
conda run -n myenv python3 -c "import foo; print(foo.bar)"

# Option B: Write to a script file first (PREFERRED for complex code)
# Write the Python code to .agents/test/myscript.py using the write_to_file tool, then:
conda run -n myenv python3 .agents/test/myscript.py
```

---

## Bug 2: Command Completes but Status Stays "Running" (SSH State Sync Bug)

### The Problem
`run_command` executes successfully in the terminal and finishes parsing, but the `command_status` tool reports the status as `RUNNING` indefinitely. The agent gets stuck in a loop trying to wait for it.

### The True Root Cause
This is a state synchronization bug specific to SSH remote workspaces. The command actually completes successfully in the remote shell, but the completion signal fails to propagate back up through the SSH channel to Antigravity's internal state tracker.

You are likely hitting this bug if:
- `command_status` keeps returning `RUNNING` long after the underlying program (e.g. `echo`, `conda install`, or a fast script) usually finishes.
- The user tells you a command "completed" or "is stuck".
- You are waiting on output that never arrives.

### Workaround: Use `read_terminal`
When `command_status` is stuck, you must bypass it by reading the terminal directly to check the process output buffer:

1. **Ask the user for the terminal PID** (they can run `echo $$` in the terminal or check the UI).
2. **Use the `read_terminal` tool:**
   ```json
   {
       "Name": "terminal-<PID>",
       "ProcessID": "<PID>"
   }
   ```
3. **Parse the output:** The terminal buffer contains the full execution history and output. Check the end of the text to confirm completion and continue your work without calling `command_status` again.

### Recovery
If the user dismisses stuck background tasks via the `X` button in the UI, subsequent commands should work normally. If the user informs you a command completed, proceed with your task using their confirmation.