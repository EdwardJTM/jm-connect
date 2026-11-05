import os

from django.core.management.base import BaseCommand, CommandError

from jm_connect.models import SystemAPIKey


class Command(BaseCommand):
    help = 'Creates an API key for a calling system. The key is printed once and cannot be shown again.'

    def add_arguments(self, parser):
        parser.add_argument('name', help='Who will use this key, for example jm-hub.')
        parser.add_argument('--scopes', required=True, help='Comma-separated, for example handoff,summary.')
        parser.add_argument(
            '--from-env',
            help='Use the key in this environment variable, for builds with no shell. Safe to run on every deploy.',
        )

    def handle(self, *args, name, scopes, from_env=None, **options):
        scope_list = [scope.strip() for scope in scopes.split(',') if scope.strip()]
        if from_env:
            self._from_env(name, scope_list, from_env)
            return
        _, key = SystemAPIKey.objects.create_key(name=name, scopes=scope_list)
        self.stdout.write(key)

    def _from_env(self, name, scopes, variable):
        key = os.environ.get(variable, '')
        if not key:
            self.stdout.write(f'{variable} is not set, so no key was created.')
            return
        prefix, _, secret = key.partition('.')
        if len(prefix) != 8 or len(secret) < 32:
            raise CommandError(f'{variable} must look like prefix.secret, with exactly 8 and at least 32 characters.')
        hashed = SystemAPIKey.objects.key_generator.hash(key)
        SystemAPIKey.objects.update_or_create(
            prefix=prefix,
            defaults={'id': f'{prefix}.{hashed}', 'name': name, 'scopes': scopes, 'hashed_key': hashed, 'revoked': False},
        )
        self.stdout.write(f'Key {prefix} is ready for {name}.')
