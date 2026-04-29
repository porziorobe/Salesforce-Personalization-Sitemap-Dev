import os
import requests
import json
from typing import Optional, Mapping


class ConnectedAppAuth:
    def __init__(self, creds_file: str, headers: Optional[Mapping[str, str]] = None):
        self.authenticated = False

        with open(creds_file) as f:
            creds = json.load(f)

        self.org_url = creds['org_url']
        self.client_id = creds['client_id']
        self.client_secret = os.getenv('EINSTEIN_CLIENT_SECRET')
        self.headers = headers

    def authenticate(self) -> bool:
        url = self.org_url + '/services/oauth2/token'
        payload = {
            'grant_type': 'client_credentials',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
        }
        response = requests.post(url, data=payload)

        if response.status_code != 200:
            raise Exception(f"Failed to authenticate: {response.status_code} - {response.text}")

        self.access_token = response.json()['access_token']
        self.authenticated = True
        return self.authenticated
