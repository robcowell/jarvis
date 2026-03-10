import os
import time
from dataclasses import dataclass
from typing import Any

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_REQUEST_TIMEOUT_SECONDS = 5
_LINK_BUTTON_ERROR_TYPE = 101


@dataclass(frozen=True)
class HueCredentials:
    bridge_ip: str
    app_key: str


@dataclass(frozen=True)
class HueProvisionResult:
    ok: bool
    app_key: str | None = None
    error: str | None = None
    message: str | None = None


class HueAuthError(RuntimeError):
    def __init__(self, code: str, user_message: str):
        super().__init__(user_message)
        self.code = code
        self.user_message = user_message


def get_credentials_from_env() -> HueCredentials:
    bridge_ip = os.getenv("HUE_BRIDGE_IP", "").strip()
    app_key = os.getenv("HUE_APP_KEY", "").strip()

    if not bridge_ip:
        raise HueAuthError(
            code="missing_hue_bridge_ip",
            user_message=(
                "Hue Bridge IP is missing. Set HUE_BRIDGE_IP and run "
                "`python -m core.tools.hue_pair --bridge-ip <bridge-ip>` to pair."
            ),
        )
    if not app_key:
        raise HueAuthError(
            code="missing_hue_app_key",
            user_message=(
                "Hue app key is missing. Press the bridge button, run "
                "`python -m core.tools.hue_pair --bridge-ip <bridge-ip>`, then set HUE_APP_KEY."
            ),
        )

    return HueCredentials(bridge_ip=bridge_ip, app_key=app_key)


def validate_credentials(credentials: HueCredentials) -> None:
    url = f"https://{credentials.bridge_ip}/clip/v2/resource/bridge"
    try:
        response = requests.get(
            url,
            headers={"hue-application-key": credentials.app_key},
            timeout=_REQUEST_TIMEOUT_SECONDS,
            verify=False,
        )
    except requests.RequestException as exc:
        raise HueAuthError(
            code="hue_bridge_unreachable",
            user_message=(
                "I could not reach the Hue Bridge. Check HUE_BRIDGE_IP and ensure the bridge is online."
            ),
        ) from exc

    if response.status_code in (401, 403):
        raise HueAuthError(
            code="invalid_hue_app_key",
            user_message=(
                "Hue app key was rejected by the bridge. Press the bridge button and run "
                "`python -m core.tools.hue_pair --bridge-ip <bridge-ip>` to generate a new key."
            ),
        )
    if response.status_code >= 400:
        raise HueAuthError(
            code="hue_auth_validation_failed",
            user_message=f"Could not validate Hue credentials (status {response.status_code}).",
        )


def provision_app_key(
    bridge_ip: str,
    device_type: str = "jarvis#core",
    timeout_seconds: int = 45,
    retry_interval_seconds: int = 2,
) -> HueProvisionResult:
    bridge_ip = bridge_ip.strip()
    if not bridge_ip:
        return HueProvisionResult(
            ok=False,
            error="missing_bridge_ip",
            message="Bridge IP is required.",
        )

    deadline = time.monotonic() + max(1, timeout_seconds)
    payload = {"devicetype": device_type}
    url = f"https://{bridge_ip}/api"

    while True:
        try:
            response = requests.post(
                url,
                json=payload,
                timeout=_REQUEST_TIMEOUT_SECONDS,
                verify=False,
            )
        except requests.RequestException as exc:
            return HueProvisionResult(
                ok=False,
                error="hue_bridge_unreachable",
                message=f"Could not reach Hue Bridge: {exc}",
            )

        result = _parse_provision_response(response)
        if result.ok:
            return result

        if result.error != "link_button_not_pressed":
            return result

        if time.monotonic() >= deadline:
            return HueProvisionResult(
                ok=False,
                error="link_button_timeout",
                message=(
                    "Bridge link button was not detected in time. Press the button and run the pairing command again."
                ),
            )
        time.sleep(max(1, retry_interval_seconds))


def _parse_provision_response(response: requests.Response) -> HueProvisionResult:
    if response.status_code >= 400:
        return HueProvisionResult(
            ok=False,
            error="hue_api_error",
            message=f"Hue Bridge returned status {response.status_code}.",
        )

    try:
        payload = response.json()
    except ValueError:
        return HueProvisionResult(
            ok=False,
            error="invalid_hue_response",
            message="Hue Bridge returned non-JSON response while provisioning key.",
        )

    if not isinstance(payload, list) or not payload:
        return HueProvisionResult(
            ok=False,
            error="invalid_hue_response",
            message="Hue Bridge returned unexpected key provisioning payload.",
        )

    first = payload[0]
    if not isinstance(first, dict):
        return HueProvisionResult(
            ok=False,
            error="invalid_hue_response",
            message="Hue Bridge returned malformed key provisioning payload.",
        )

    success = first.get("success")
    if isinstance(success, dict):
        app_key = str(success.get("username", "")).strip()
        if app_key:
            return HueProvisionResult(ok=True, app_key=app_key)

    error = first.get("error")
    if isinstance(error, dict):
        error_type = int(error.get("type", 0))
        description = str(error.get("description", "")).strip()
        if error_type == _LINK_BUTTON_ERROR_TYPE:
            return HueProvisionResult(
                ok=False,
                error="link_button_not_pressed",
                message="Link button not pressed yet.",
            )
        return HueProvisionResult(
            ok=False,
            error=f"hue_error_{error_type or 'unknown'}",
            message=description or "Hue Bridge key provisioning failed.",
        )

    return HueProvisionResult(
        ok=False,
        error="invalid_hue_response",
        message="Hue Bridge key provisioning did not return success or error payload.",
    )
