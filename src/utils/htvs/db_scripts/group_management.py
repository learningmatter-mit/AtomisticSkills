import os
import json
from pgmols.models import Group

# Load payload
payload_str = os.environ.get("HTVS_PAYLOAD")
if not payload_str:
    print(json.dumps({"error": "No HTVS_PAYLOAD found"}))
    exit(1)

try:
    payload = json.loads(payload_str)
except Exception as e:
    print(json.dumps({"error": f"Parse error: {str(e)}"}))
    exit(1)

action = payload.get("action")
group_name = payload.get("group_name")

def handle_create_group():
    if not group_name:
        return {"error": "group_name required for create_group"}
    group, created = Group.objects.get_or_create(name=group_name)
    return {
        "group_name": group_name,
        "group_id": group.id,
        "created": created
    }

try:
    if action == "create_group":
        res = handle_create_group()
    else:
        res = {"error": f"Unknown action: {action}"}
    print(json.dumps(res))
except Exception as e:
    print(json.dumps({"error": str(e)}))
