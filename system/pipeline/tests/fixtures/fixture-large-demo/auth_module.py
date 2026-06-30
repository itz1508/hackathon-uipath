"""Auth with internal SDK."""

from internal_auth_provider import TokenService

def authenticate():
    return TokenService().get_token()
