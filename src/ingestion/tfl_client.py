"""Shared HTTP extraction for local ETL and Lambda, without filesystem effects."""
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

API_URL = "https://api.tfl.gov.uk/Line/Mode/tube/Status"


class BoundedRetry(Retry):
    """Cap Retry-After so an upstream response cannot exhaust Lambda time."""
    def get_retry_after(self, response):
        delay = super().get_retry_after(response)
        return min(delay, 5) if delay is not None else None


def fetch_tube_status(api_key=None, timeout=(5, 30), cloud=False):
    retry_class = BoundedRetry if cloud else Retry
    strategy = retry_class(
        total=3, connect=3, read=3, backoff_factor=0.5 if cloud else 1,
        status_forcelist=[429, 500, 502, 503, 504], allowed_methods={"GET"},
        respect_retry_after_header=True,
    )
    with requests.Session() as session:
        session.mount("https://", HTTPAdapter(max_retries=strategy))
        response = session.get(API_URL, params={"app_key": api_key} if api_key else {}, timeout=timeout)
        response.raise_for_status()
        data = response.json()
    if not isinstance(data, list) or not data:
        raise ValueError("Invalid TfL API response: expected a non-empty list.")
    return data
