
import os
import sys
import django
import json

# Setup Django
sys.path.append(os.path.abspath("/home/hojechun/ssd_mnt/repos/htvs/djangochem"))
sys.path.append(os.path.abspath("/home/hojechun/ssd_mnt/repos/htvs")) # parent dir
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "djangochem.settings.orgel")
django.setup()

from django.contrib.auth.models import Group

groups = list(Group.objects.all().values_list('name', flat=True))
print(json.dumps(groups, indent=2))
