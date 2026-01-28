
import sys
import os
import json
import django

# Setup Django environment
repo_path = "/home/hojechun/ssd_mnt/repos/htvs"
sys.path.append(repo_path)
sys.path.append(os.path.join(repo_path, "djangochem"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "djangochem.settings.orgel")
try:
    django.setup()
except Exception as e:
    print(json.dumps({"error": f"Django setup failed: {e}"}))
    sys.exit(1)

from pgmols.models import Crystal, Group

group_name = "perovskite"
limit = 10

try:
    group = Group.objects.get(name=group_name)
except Group.DoesNotExist:
    # Try finding any group to show it works, or just report error
    print(json.dumps({"error": f"Group '{group_name}' not found in DB"}))
    sys.exit(0)
except Exception as e:
    print(json.dumps({"error": f"DB Error: {e}"}))
    sys.exit(1)

from django.db.models import Q

results = []
# Filter by species__group OR parentjob__group
qs = Crystal.objects.filter(Q(species__group=group) | Q(parentjob__group=group))[:limit]
for obj in qs:
    formula = obj.stoichiometry.formula if obj.stoichiometry else "Unknown"
    sg = obj.spacegroup.symbol if obj.spacegroup else "Unknown"
    results.append({
        "id": obj.id,
        "type": "Crystal",
        "formula": formula,
        "spacegroup": sg,
        "parentjob_id": obj.parentjob.id if (hasattr(obj, 'parentjob') and obj.parentjob) else None
    })

print(json.dumps(results, indent=2))
