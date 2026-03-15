import os
from dataclasses import dataclass

import requests

_REQUEST_TIMEOUT_SECONDS = 8


@dataclass(frozen=True)
class AmazonAlexaCredentials:
    cookie: str
    csrf: str
    base_url: str


class AmazonAlexaAuthError(RuntimeError):
    def __init__(self, code: str, user_message: str):
        super().__init__(user_message)
        self.code = code
        self.user_message = user_message


def get_credentials_from_env() -> AmazonAlexaCredentials:
    cookie = os.getenv("AMAZON_ALEXA_COOKIE", "").strip()
    csrf = os.getenv("AMAZON_ALEXA_CSRF", "").strip()
    base_url = os.getenv("AMAZON_ALEXA_BASE_URL", "https://alexa.amazon.com").strip()

    if not cookie:
        raise AmazonAlexaAuthError(
            code="missing_amazon_alexa_cookie",
            user_message=(
                "Amazon Alexa cookie is missing. Set AMAZON_ALEXA_COOKIE with an authenticated "
                "Alexa web session cookie."
            ),
        )
    if not csrf:
        raise AmazonAlexaAuthError(
            code="missing_amazon_alexa_csrf",
            user_message=(
                "Amazon Alexa CSRF token is missing. Set AMAZON_ALEXA_CSRF from your Alexa web session."
            ),
        )
    if not base_url:
        raise AmazonAlexaAuthError(
            code="missing_amazon_alexa_base_url",
            user_message="Amazon Alexa base URL is missing. Set AMAZON_ALEXA_BASE_URL.",
        )
    if not base_url.startswith("https://"):
        raise AmazonAlexaAuthError(
            code="invalid_amazon_alexa_base_url",
            user_message="AMAZON_ALEXA_BASE_URL must start with https://",
        )

    return AmazonAlexaCredentials(cookie=cookie, csrf=csrf, base_url=base_url.rstrip("/"))


def validate_credentials(credentials: AmazonAlexaCredentials) -> None:
    url = f"{credentials.base_url}/api/phoenix?includeRelationships=true"
    try:
        response = requests.get(
            url,
            headers=build_auth_headers(credentials),
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise AmazonAlexaAuthError(
            code="amazon_alexa_unreachable",
            user_message=(
                "I could not reach the Alexa Smart Home API. Check AMAZON_ALEXA_BASE_URL and your network."
            ),
        ) from exc

    if response.status_code in (401, 403):
        raise AmazonAlexaAuthError(
            code="invalid_amazon_alexa_auth",
            user_message=(
                "Amazon Alexa authentication was rejected. Refresh AMAZON_ALEXA_COOKIE and AMAZON_ALEXA_CSRF."
            ),
        )
    if response.status_code >= 400:
        raise AmazonAlexaAuthError(
            code="amazon_alexa_auth_validation_failed",
            user_message=f"Could not validate Amazon Alexa credentials (status {response.status_code}).",
        )


def build_auth_headers(credentials: AmazonAlexaCredentials) -> dict[str, str]:
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Cookie": credentials.cookie,
        "csrf": credentials.csrf,
        "Origin": credentials.base_url,
        "Referer": f"{credentials.base_url}/spa/index.html",
        "x-amz-alexa-app": "alexa-web-app",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
    }
