def extract_workflow_nodes(md_content):
    import re
    nodes = []
    # Match backticked content
    for match in re.finditer(r'`([A-Za-z0-9_-]+)`', md_content):
        val = match.group(1)
        if val.startswith("mcp_") or val.startswith("create_") or val == "notify_user" or val == "task_boundary":
            if val not in [n["name"] for n in nodes]:
                nodes.append({"type": "tool", "name": val})
        elif val.startswith(("mat-", "chem-", "ml-", "drug-", "general-")):
            if val not in [n["name"] for n in nodes]:
                nodes.append({"type": "skill", "name": val})
    return nodes

