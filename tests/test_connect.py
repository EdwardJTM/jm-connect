import json
from datetime import timedelta
from io import StringIO
from unittest import mock

import requests
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from jm_connect.client import SystemUnavailable, system
from jm_connect.models import HandoffToken, SystemAPIKey

User = get_user_model()


class HandoffTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('edward', password='a-long-test-password')
        _, self.key = SystemAPIKey.objects.create_key(name='jm-hub', scopes=['handoff'])

    def ask(self, username='edward', key=None):
        return self.client.post(
            '/api/v1/handoff/',
            data=json.dumps({'username': username}),
            content_type='application/json',
            headers={'Authorization': f'Api-Key {key or self.key}'},
        )

    def link(self):
        return self.ask().json()['url'].replace('http://testserver', '')


class KeyTests(HandoffTestCase):
    def test_valid_key_gets_a_link_and_records_use(self):
        response = self.ask()
        self.assertEqual(response.status_code, 200)
        self.assertIn('/jm/enter/', response.json()['url'])
        self.assertIsNotNone(SystemAPIKey.objects.get(name='jm-hub').last_used_at)

    def test_missing_key_is_refused(self):
        response = self.client.post('/api/v1/handoff/', {'username': 'edward'})
        self.assertIn(response.status_code, (401, 403))

    def test_wrong_key_is_refused(self):
        self.assertIn(self.ask(key='wrong.key').status_code, (401, 403))

    def test_key_without_the_scope_is_refused(self):
        _, other = SystemAPIKey.objects.create_key(name='other', scopes=['summary'])
        self.assertEqual(self.ask(key=other).status_code, 403)

    def test_revoked_key_is_refused(self):
        SystemAPIKey.objects.filter(name='jm-hub').update(revoked=True)
        self.assertIn(self.ask().status_code, (401, 403))

    def test_key_is_stored_only_as_a_hash(self):
        self.assertNotIn(self.key.split('.')[1], SystemAPIKey.objects.get(name='jm-hub').hashed_key)

    def test_command_creates_a_working_key(self):
        out = StringIO()
        call_command('create_system_key', 'jm-hub-2', '--scopes', 'handoff, summary', stdout=out)
        self.assertEqual(self.ask(key=out.getvalue().strip()).status_code, 200)
        self.assertEqual(SystemAPIKey.objects.get(name='jm-hub-2').scopes, ['handoff', 'summary'])


class KeyFromEnvTests(HandoffTestCase):
    VALUE = 'abcd1234.' + 'x' * 32

    def run_command(self, value=VALUE):
        with mock.patch.dict('os.environ', {'JM_HUB_KEY': value}):
            call_command('create_system_key', 'hub', '--scopes', 'handoff', '--from-env', 'JM_HUB_KEY', stdout=StringIO())

    def test_key_from_env_works_and_repeats_safely(self):
        self.run_command()
        self.run_command()
        self.assertEqual(SystemAPIKey.objects.filter(name='hub').count(), 1)
        self.assertEqual(self.ask(key=self.VALUE).status_code, 200)

    def test_empty_env_creates_nothing(self):
        self.run_command(value='')
        self.assertFalse(SystemAPIKey.objects.filter(name='hub').exists())

    def test_short_key_is_refused(self):
        with self.assertRaises(CommandError):
            self.run_command(value='a.b')

    def test_prefix_longer_than_the_database_column_is_refused(self):
        with self.assertRaises(CommandError):
            self.run_command(value='abcdefghijk.' + 'x' * 32)


class SignInTests(HandoffTestCase):
    def test_link_signs_the_person_in_and_goes_home(self):
        response = self.client.get(self.link())
        self.assertRedirects(response, '/home/', fetch_redirect_response=False)
        self.assertEqual(self.client.get('/home/').content.decode(), 'edward')

    def test_link_works_only_once(self):
        link = self.link()
        self.client.get(link)
        self.client.logout()
        self.assertEqual(self.client.get(link).status_code, 410)
        self.assertEqual(self.client.get('/home/').content.decode(), '')

    def test_expired_link_is_refused(self):
        link = self.link()
        HandoffToken.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.client.get(link).status_code, 410)

    def test_made_up_link_is_refused(self):
        self.assertEqual(self.client.get('/jm/enter/made-up/').status_code, 410)

    def test_unknown_or_inactive_user_gets_no_link(self):
        self.assertEqual(self.ask(username='nobody').status_code, 404)
        self.user.is_active = False
        self.user.save()
        self.assertEqual(self.ask().status_code, 404)

    def test_user_deactivated_after_the_link_cannot_enter(self):
        link = self.link()
        self.user.is_active = False
        self.user.save()
        self.assertEqual(self.client.get(link).status_code, 410)

    def test_raw_token_is_not_stored(self):
        token = self.link().rstrip('/').split('/')[-1]
        self.assertFalse(HandoffToken.objects.filter(token_hash=token).exists())

    def test_expired_rows_are_cleared(self):
        self.link()
        HandoffToken.objects.update(expires_at=timezone.now() - timedelta(days=1))
        self.link()
        self.assertEqual(HandoffToken.objects.count(), 1)


class ClientTests(SimpleTestCase):
    ENV = {'DRIVING_SCHOOL_API_URL': 'https://driving.example.com/', 'DRIVING_SCHOOL_API_KEY': 'secret-key'}

    def test_not_configured(self):
        with mock.patch.dict('os.environ', {}, clear=True):
            self.assertFalse(system('driving-school').configured)
            with self.assertRaises(SystemUnavailable):
                system('driving-school').get('/x/')

    def test_sends_key_in_header_with_a_timeout(self):
        with mock.patch.dict('os.environ', self.ENV), mock.patch('jm_connect.client.requests.request') as request:
            request.return_value.json.return_value = {'url': 'x'}
            self.assertEqual(system('driving-school').post('/api/v1/handoff/', json={'username': 'a'}), {'url': 'x'})
        args, kwargs = request.call_args
        self.assertEqual(args, ('POST', 'https://driving.example.com/api/v1/handoff/'))
        self.assertEqual(kwargs['headers'], {'Authorization': 'Api-Key secret-key'})
        self.assertEqual(kwargs['timeout'], 3)

    def test_failures_become_system_unavailable_without_the_key(self):
        with mock.patch.dict('os.environ', self.ENV), mock.patch('jm_connect.client.requests.request', side_effect=requests.ConnectionError('secret-key')):
            with self.assertRaises(SystemUnavailable) as caught:
                system('driving-school').get('/x/')
        self.assertNotIn('secret-key', str(caught.exception))
