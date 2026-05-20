"""
Small Caliber/FrontSteps API client for the Wynbrooke HOA utility.

The Caliber v2 API uses an Authorization header in this form:
    basic base64(APICode:APIUsername:APIPassword)
"""

import base64
import os

import requests
from dotenv import load_dotenv


class CaliberConfigError(RuntimeError):
    pass


class CaliberClient:
    def __init__(self, base_url, api_code, api_username, api_password):
        self.base_url = base_url.rstrip("/")
        self.api_code = api_code
        self.api_username = api_username
        self.api_password = api_password

    @classmethod
    def from_env(cls):
        load_dotenv()
        base_url = os.getenv("FRONTSTEPS_API_ENDPOINT", "")
        api_code = os.getenv("FRONTSTEPS_API_CODE", "")
        api_username = os.getenv("FRONTSTEPS_API_USERNAME") or os.getenv("FRONTSTEPS_USERNAME", "")
        api_password = os.getenv("FRONTSTEPS_API_PASSWORD") or os.getenv("FRONTSTEPS_PASSWORD", "")

        missing = [
            name
            for name, value in {
                "FRONTSTEPS_API_ENDPOINT": base_url,
                "FRONTSTEPS_API_CODE": api_code,
                "FRONTSTEPS_API_USERNAME": api_username,
                "FRONTSTEPS_API_PASSWORD": api_password,
            }.items()
            if not value
        ]
        if missing:
            raise CaliberConfigError(
                "Missing required Caliber env vars: " + ", ".join(missing)
            )

        return cls(base_url, api_code, api_username, api_password)

    def headers(self):
        security_string = f"{self.api_code}:{self.api_username}:{self.api_password}"
        encoded = base64.b64encode(security_string.encode("utf-8")).decode("ascii")
        return {
            "Accept": "application/json",
            "Authorization": f"basic {encoded}",
        }

    def get(self, path):
        url = f"{self.base_url}/api/v2/{path.lstrip('/')}"
        resp = requests.get(url, headers=self.headers(), timeout=30)
        resp.raise_for_status()
        return resp.json()

    def login(self):
        return self.get("login")

    def client_list(self):
        data = self.get("clientlist")
        return data if isinstance(data, list) else [data]

    def find_client(self, search_text):
        needle = search_text.lower()
        for client in self.client_list():
            names = [
                client.get("ClientName", ""),
                client.get("Name", ""),
                client.get("LegalName", ""),
            ]
            if any(needle in str(name).lower() for name in names):
                return client
        return None

    def units(self, client_id):
        data = self.get(f"client/{client_id}/units")
        return data if isinstance(data, list) else [data]

    def current_contacts(self, client_id):
        data = self.get(f"client/{client_id}/contacts/current")
        return data if isinstance(data, list) else [data]
