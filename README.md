# jm-connect

The small Django app every Junior Marima system installs. It gives a system:

- **API keys with scopes**: `SystemAPIKey` and the `HasScope` permission.
- **A client** for calling another system: `system('requisitions').get('/api/v1/summary/')`.
- **One-time sign-in**: the hub asks a system for a sign-in link for a username, then sends the person's browser to it.

## Install in a system

```
jm-connect @ git+https://github.com/EdwardJTM/jm-connect.git@v0.1.0
```

```python
INSTALLED_APPS += ['rest_framework', 'rest_framework_api_key', 'jm_connect']
```

```python
urlpatterns += [path('', include('jm_connect.urls'))]
```

Run `python manage.py migrate`. Give each system its own `SESSION_COOKIE_NAME` and `CSRF_COOKIE_NAME`.

## Keys

The system receiving the calls creates the key. It is printed once and stored only as a hash.

```bash
python manage.py create_system_key jm-hub --scopes handoff
```

On a host with no shell, such as Render's free plan, generate a value and set it as an environment variable on both
systems. Then have the receiving system's build run the command below, which is safe on every deploy:

```bash
python -c "import secrets; print(secrets.token_urlsafe(8) + '.' + secrets.token_urlsafe(32))"
python manage.py create_system_key jm-hub --scopes handoff --from-env JM_HUB_KEY
```

The caller keeps it in `.env`. The name comes from `system('requisitions')`, in capitals with dashes as underscores:

```bash
REQUISITIONS_API_URL=http://localhost:8001
REQUISITIONS_API_KEY=paste-the-key-here
```

Test it. A good key returns a link, and a missing or wrong key is refused.

```bash
curl -X POST -H "Authorization: Api-Key $REQUISITIONS_API_KEY" -H "Content-Type: application/json" -d "{\"username\": \"edward\"}" "$REQUISITIONS_API_URL/api/v1/handoff/"
```

To replace a key, create a new one, update the caller's `.env`, restart the caller, then revoke the old key in admin.

Keys stay on servers: never in JavaScript, templates or git. Outside your own computer, use HTTPS. A key with the
`handoff` scope can sign in as any active user of that system, so treat it like an admin password.

## Protect an endpoint

```python
class SummaryView(APIView):
    authentication_classes = []
    permission_classes = [HasScope]
    required_scope = 'summary'
```

## Tests

```bash
python -m django test --settings=tests.settings --pythonpath=.
```
