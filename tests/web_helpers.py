import re


def csrf_token(client,path='/login'):
    # DB fixtures hold an outer app context; production requests have fresh g.
    # Do not reuse a signed CSRF rendering token across different test sessions.
    from flask import g, has_app_context
    if has_app_context(): g.pop("csrf_token", None)
    response=client.get(path)
    match=re.search(r'name="csrf-token" content="([^"]+)"',response.get_data(as_text=True))
    assert match is not None
    return match.group(1)


def login(client,username='security-admin',password='public-test-password',next_value=None):
    from urllib.parse import urlencode
    token=csrf_token(client)
    target='/login'+('?' + urlencode({'next':next_value}) if next_value is not None else '')
    return client.post(target,data={'username':username,'password':password,'csrf_token':token})


def headers(client):
    return {'X-CSRFToken':csrf_token(client,'/')}
