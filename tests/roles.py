from django.contrib.auth.models import Group

from jm_connect.views import UnknownRole

ROLES = {'clerk', 'manager'}


def apply_role(user, role):
    if role not in ROLES:
        raise UnknownRole(role)
    user.groups.set([Group.objects.get_or_create(name=role)[0]])
