# MCP Standard I/O (STDIO) Redirection Guide

## The Challenge: Output Pollution in MCP

The Model Context Protocol (MCP) frequently utilizes Standard I/O (STDIO) as its transport layer for communication between the agentic interface (e.g., Antigravity, Cursor) and the underlying Python servers. The protocol explicitly expects well-formed JSON-RPC messages over standard output.

However, scientific computation ecosystems present a unique challenge:
- **Legacy Scientific Codes:** Many core utilities (such as those written in C, Fortran, or wrapped by packages like ASE) contain hardcoded `print` statements or log directly to standard output manifolds.
- **Protocol Breakage:** If an underlying scientific process leaks unstructured logging text or progress bars into standard output, it corrupts the JSON-RPC payload. This protocol breakage leads to failed tool calls, unparseable responses, or complete terminal hangs.
- **Noisy Endpoints:** Frameworks like PyTorch or specific simulation backends periodically emit deprecation warnings or verbose compiler logs, which must not intercept the MCP transport stream.

## Our Solution: Persistent File Descriptor Redirection

To overcome this infrastructural constraint, AtomisticSkills utilizes a centralized, persistent output redirection strategy at the server startup level. Rather than wrapping individual functions, we redirect STDIO for the entire FastMCP server via the utilities in `src/utils/mcp_utils.py`.

### How It Works

Our server-level interception (`setup_mcp_stdout()` and `run_fastmcp_server()`) leverages operating-system file-descriptor level patching to capture stubborn I/O from precompiled C/Fortran libraries that bypass Python's `sys.stdout`.

1. **Interception:** We duplicate the "real" stdout (File Descriptor 1) so the MCP JSON-RPC payload has a clean, protected pipe to write to.
2. **Redirection:** We redirect the system-level FD 1 to stderr (FD 2). Thus, any legacy binaries writing to hardcoded standard output will instead output to stderr, freeing FD 1 for protocol negotiation.
3. **Patching:** We patch Python's internal `sys.stdout` to point to `sys.stderr`.
4. **JSON-RPC Delivery:** We launch the FastMCP server with explicit, customized asynchronous streams (via `mcp_transport_manager`) bound specifically to the protected pipe from step 1. 

### Best Practices for Developers

Because standard output is globally redirected to standard error at server initialization, developers do not need to manually wrap noisy functions. However, adhere to the following rules:

*   **Never Use Raw Print for Returns:** Do NOT place `print()` statements inside MCP tool functions expecting the user to read them cleanly. Any `print()` calls will be pushed to standard error.
*   **Rely on Global Infrastructure:** Legacy code wrappers and verbose routines (e.g., DFT engines, torch trainers) can log safely without corrupting the MCP transport layer because the global runtime automatically routes their standard output away from the JSON-RPC pipe.

```python
# No manual stdout capturing is required inside tools!
@mcp.tool()
def run_noisy_simulation(params: dict) -> dict:
    # Safely execute legacy code. Outputs naturally flow to stderr.
    results = legacy_fortran_wrapper.run_simulation(params)
    return results
```

By strictly managing standard output trajectories, AtomisticSkills ensures that even the most chaotic legacy simulation codes can operate reliably within autonomous, agentic workflows without corrupting the underlying MCP transport layer.
