import requests
from decouple import AutoConfig
from django.conf import settings

DEFAULT_TIMEOUT = 3


class SystemUnavailable(Exception):
    """The other system is not configured, could not be reached, or refused the call."""


class System:
    """Calls another system. URL and key come from NAME_API_URL and NAME_API_KEY, in the environment or .env."""

    def __init__(self, name):
        prefix = name.upper().replace('-', '_')
        config = AutoConfig(search_path=settings.BASE_DIR)
        self.name = name
        self.url = config(f'{prefix}_API_URL', default='').rstrip('/')
        self.key = config(f'{prefix}_API_KEY', default='')

    @property
    def configured(self):
        return bool(self.url and self.key)

    def _call(self, method, path, timeout=DEFAULT_TIMEOUT, **kwargs):
        if not self.configured:
            raise SystemUnavailable(f'{self.name} has no API URL or key set.')
        headers = {'Authorization': f'Api-Key {self.key}'}
        try:
            response = requests.request(method, f'{self.url}{path}', headers=headers, timeout=timeout, **kwargs)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            # The message never includes the key, which travels only in the header.
            raise SystemUnavailable(f'{self.name} call failed: {type(exc).__name__}') from exc

    def get(self, path, params=None, timeout=DEFAULT_TIMEOUT):
        return self._call('GET', path, timeout=timeout, params=params)

    def post(self, path, json=None, timeout=DEFAULT_TIMEOUT):
        return self._call('POST', path, timeout=timeout, json=json)


def system(name):
    return System(name)
