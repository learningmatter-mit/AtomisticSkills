
import os
import sys
import django
import json

# Setup Django with TOY settings
sys.path.append(os.path.abspath("/home/hojechun/ssd_mnt/repos/htvs/djangochem"))
sys.path.append(os.path.abspath("/home/hojechun/ssd_mnt/repos/htvs"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "djangochem.settings.toy")
django.setup()

from django.contrib.auth.models import Group

group_name = "agent"
group, created = Group.objects.get_or_create(name=group_name)

if created:
    print(f"Group '{group_name}' created successfully.")
else:
    print(f"Group '{group_name}' already exists.")
