import re
from dataclasses import dataclass

import requests

from core.integrations.hue_auth import (
    HueAuthError,
    get_credentials_from_env,
    validate_credentials,
)
from core.skills.base import BaseSkill, SkillContext
from core.skills.result import SkillResult


_REQUEST_TIMEOUT_SECONDS = 5
_SUPPORTED_COLORS_XY = {
    "red": {"x": 0.675, "y": 0.322},
    "orange": {"x": 0.556, "y": 0.408},
    "yellow": {"x": 0.444, "y": 0.517},
    "green": {"x": 0.409, "y": 0.518},
    "cyan": {"x": 0.17, "y": 0.34},
    "blue": {"x": 0.167, "y": 0.04},
    "purple": {"x": 0.272, "y": 0.109},
    "pink": {"x": 0.382, "y": 0.159},
    "white": {"x": 0.3227, "y": 0.329},
    "warm white": {"x": 0.458, "y": 0.41},
    "cool white": {"x": 0.313, "y": 0.329},
}


@dataclass(frozen=True)
class _HueTarget:
    resource_type: str
    resource_id: str
    name: str


class HueLightsSkill(BaseSkill):
    def __init__(self, manifest) -> None:
        super().__init__(manifest)
        self._credentials_checked = False

    def execute(self, context: SkillContext) -> SkillResult:
        if self._is_pairing_help_intent(context.text):
            return self._build_pairing_help_result()

        try:
            credentials = get_credentials_from_env()
            if not self._credentials_checked:
                validate_credentials(credentials)
                self._credentials_checked = True
        except HueAuthError as exc:
            return SkillResult(
                ok=False,
                message=exc.user_message,
                skill_id=self.skill_id,
                error=exc.code,
            )

        bridge_ip = credentials.bridge_ip
        app_key = credentials.app_key

        brightness_level = self._parse_brightness_level(context.text)
        color_name = self._parse_color_name(context.text)
        intent_on = self._parse_power_intent(context.text)

        action: str | None = None
        action_payload: dict | None = None
        target_text: str | None = None
        success_message: str | None = None
        action_data: dict = {}

        if brightness_level is not None:
            action = "brightness"
            action_payload = {"on": {"on": True}, "dimming": {"brightness": float(brightness_level)}}
            target_text = self._extract_brightness_target_text(context.text)
            success_message = f"Set {{target}} brightness to {brightness_level} percent."
            action_data["brightness"] = brightness_level
        elif color_name is not None:
            action = "color"
            action_payload = {"on": {"on": True}, "color": {"xy": _SUPPORTED_COLORS_XY[color_name]}}
            target_text = self._extract_color_target_text(context.text)
            success_message = f"Set {{target}} to {color_name}."
            action_data["color"] = color_name
        elif intent_on is not None:
            action = "power"
            action_payload = {"on": {"on": intent_on}}
            target_text = self._extract_power_target_text(context.text)
            state_word = "on" if intent_on else "off"
            success_message = f"Turned {{target}} {state_word}."
            action_data["is_on"] = intent_on

        if action_payload is None or action is None or success_message is None:
            return SkillResult(
                ok=False,
                message=(
                    "I support Hue power, brightness, and named colors. "
                    "Try turn on office light, set office light to 40 percent, or set office light to blue."
                ),
                skill_id=self.skill_id,
                error="unsupported_hue_intent",
            )

        try:
            if target_text is None:
                if not self._is_all_lights_request(context.text):
                    return SkillResult(
                        ok=False,
                        message=(
                            "Please specify which light, room, or zone to control. "
                            "You can also say all lights."
                        ),
                        skill_id=self.skill_id,
                        error="hue_target_required",
                    )
                changed = self._set_all_lights_payload(
                    bridge_ip=bridge_ip,
                    app_key=app_key,
                    payload=action_payload,
                )
                return SkillResult(
                    ok=True,
                    message=f"Updated {changed} Hue lights.",
                    skill_id=self.skill_id,
                    data={"count": changed, "target": "all", "action": action, **action_data},
                )

            candidates = self._resolve_target(
                bridge_ip=bridge_ip,
                app_key=app_key,
                target_text=target_text,
            )
            if not candidates:
                return SkillResult(
                    ok=False,
                    message=f"I could not find a Hue light, room, or zone named {target_text}.",
                    skill_id=self.skill_id,
                    error="hue_target_not_found",
                    data={"target_text": target_text},
                )
            if len(candidates) > 1:
                names = ", ".join(sorted({c.name for c in candidates})[:4])
                return SkillResult(
                    ok=False,
                    message=f"I found multiple Hue targets for {target_text}: {names}. Please be more specific.",
                    skill_id=self.skill_id,
                    error="hue_target_ambiguous",
                    data={"target_text": target_text, "match_count": len(candidates)},
                )

            chosen = candidates[0]
            self._set_target_payload(
                bridge_ip=bridge_ip,
                app_key=app_key,
                target=chosen,
                payload=action_payload,
            )
            return SkillResult(
                ok=True,
                message=success_message.format(target=chosen.name),
                skill_id=self.skill_id,
                data={
                    "target": chosen.name,
                    "target_type": chosen.resource_type,
                    "action": action,
                    **action_data,
                },
            )
        except requests.RequestException as exc:
            return SkillResult(
                ok=False,
                message=(
                    "I could not reach the Hue Bridge. Check bridge IP, app key, and that the bridge is online."
                ),
                skill_id=self.skill_id,
                error="hue_bridge_unreachable",
                data={"details": str(exc)},
            )
        except RuntimeError as exc:
            return SkillResult(
                ok=False,
                message=f"Hue command failed: {exc}",
                skill_id=self.skill_id,
                error="hue_api_error",
            )

    def _api_base(self, bridge_ip: str) -> str:
        return f"https://{bridge_ip}/clip/v2/resource"

    def _headers(self, app_key: str) -> dict[str, str]:
        return {
            "hue-application-key": app_key,
            "Content-Type": "application/json",
        }

    def _parse_power_intent(self, text: str) -> bool | None:
        normalized = self._normalize_text(text)
        if any(token in normalized for token in ("turn on", "switch on", "power on", "lights on", "on lights")):
            return True
        if any(
            token in normalized for token in ("turn off", "switch off", "power off", "lights off", "off lights")
        ):
            return False
        return None

    def _extract_power_target_text(self, text: str) -> str | None:
        normalized = self._normalize_text(text)
        if self._is_all_lights_request(normalized):
            return None

        target = ""
        patterns = [
            r"\b(?:turn|switch|power)\s+on\b(?P<target>.*)",
            r"\b(?:turn|switch|power)\s+off\b(?P<target>.*)",
            r"\b(?:turn|switch|power)\b(?P<target>.*?)\bon\b",
            r"\b(?:turn|switch|power)\b(?P<target>.*?)\boff\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, normalized)
            if match:
                target = (match.group("target") or "").strip()
                break

        if not target:
            suffix_match = re.search(
                r"(?P<target>.*)\b(light|lights|lamp|lamps)\s+(on|off)\b",
                normalized,
            )
            if suffix_match:
                target = (suffix_match.group("target") or "").strip()

        target = re.sub(
            r"\b(the|please|in|at|my|hue|light|lights|lamp|lamps|turn|switch|power)\b",
            " ",
            target,
        )
        return self._clean_target_text(target)

    def _extract_brightness_target_text(self, text: str) -> str | None:
        normalized = self._normalize_text(text)
        if self._is_all_lights_request(normalized):
            return None

        target = ""
        patterns = [
            r"\bset\b(?P<target>.*?)\b(?:brightness|light level)\b(?:\s*to)?\s*\d{1,3}\s*%?\b",
            r"\bdim\b(?P<target>.*?)\bto\b\s*\d{1,3}\s*%?\b",
            r"\bset\b(?P<target>.*?)\bto\b\s*\d{1,3}\s*%\b",
            r"(?P<target>.*?)\b(light|lights|lamp|lamps)\s+\d{1,3}\s*%\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, normalized)
            if match:
                target = (match.group("target") or "").strip()
                break

        target = re.sub(
            r"\b(the|please|in|at|my|hue|light|lights|lamp|lamps|set|to|brightness|light level|dim|percent)\b",
            " ",
            target,
        )
        target = re.sub(r"\b\d{1,3}\b", " ", target)
        return self._clean_target_text(target)

    def _extract_color_target_text(self, text: str) -> str | None:
        normalized = self._normalize_text(text)
        if self._is_all_lights_request(normalized):
            return None

        color_regex = "|".join(
            sorted((re.escape(name) for name in _SUPPORTED_COLORS_XY.keys()), key=len, reverse=True)
        )
        target = ""
        patterns = [
            rf"\bset\b(?P<target>.*?)\bto\b(?P<color>{color_regex})\b",
            rf"\bmake\b(?P<target>.*?)\b(?P<color>{color_regex})\b",
            rf"(?P<target>.*?)\b(light|lights|lamp|lamps)\s+(?P<color>{color_regex})\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, normalized)
            if match:
                target = (match.group("target") or "").strip()
                break

        target = re.sub(
            r"\b(the|please|in|at|my|hue|light|lights|lamp|lamps|set|to|make|color|colour)\b",
            " ",
            target,
        )
        return self._clean_target_text(target)

    def _clean_target_text(self, target: str) -> str | None:
        target = re.sub(r"\s+", " ", target).strip()
        return target or None

    def _normalize_text(self, text: str) -> str:
        lowered = text.lower().strip()
        lowered = re.sub(r"[^a-z0-9\s]", " ", lowered)
        lowered = re.sub(r"\s+", " ", lowered)
        return lowered

    def _parse_brightness_level(self, text: str) -> int | None:
        normalized = self._normalize_text(text)
        number_match = re.search(r"\b(\d{1,3})\b", normalized)
        has_set_style_brightness = (
            "set" in normalized
            and number_match is not None
            and any(token in normalized for token in ("light", "lights", "lamp", "lamps"))
        )
        if not any(token in normalized for token in ("brightness", "percent", "dim", "dimmer")):
            if not has_set_style_brightness:
                return None

        match = number_match
        if not match:
            return None
        value = int(match.group(1))
        if value < 1:
            return 1
        if value > 100:
            return 100
        return value

    def _parse_color_name(self, text: str) -> str | None:
        normalized = self._normalize_text(text)
        for color_name in sorted(_SUPPORTED_COLORS_XY.keys(), key=len, reverse=True):
            if re.search(rf"\b{re.escape(color_name)}\b", normalized):
                return color_name
        return None

    def _is_all_lights_request(self, text: str) -> bool:
        normalized = self._normalize_text(text)
        all_lights_phrases = (
            "all lights",
            "all the lights",
            "every light",
            "every lamp",
            "all lamps",
        )
        return any(phrase in normalized for phrase in all_lights_phrases)

    def _is_pairing_help_intent(self, text: str) -> bool:
        normalized = self._normalize_text(text)
        pairing_phrases = (
            "pair hue bridge",
            "connect hue bridge",
            "setup hue bridge",
            "set up hue bridge",
            "pair hue",
            "connect hue",
        )
        return any(phrase in normalized for phrase in pairing_phrases)

    def _build_pairing_help_result(self) -> SkillResult:
        command = "python -m core.tools.hue_pair --bridge-ip <bridge-ip>"
        message = (
            "To pair Hue Bridge, press the bridge button, then run "
            f"{command}. Copy the printed HUE_APP_KEY and set HUE_BRIDGE_IP and HUE_APP_KEY before restarting Core."
        )
        return SkillResult(
            ok=True,
            message=message,
            skill_id=self.skill_id,
            data={"pair_command": command},
        )

    def _set_all_lights_payload(self, bridge_ip: str, app_key: str, payload: dict) -> int:
        lights = self._get_resource_list(bridge_ip=bridge_ip, app_key=app_key, resource_name="light")
        count = 0
        failed = 0
        for item in lights:
            light_id = str(item.get("id", "")).strip()
            if not light_id:
                continue
            try:
                self._put_resource(
                    bridge_ip=bridge_ip,
                    app_key=app_key,
                    resource_name="light",
                    resource_id=light_id,
                    payload=payload,
                )
                count += 1
            except RuntimeError:
                failed += 1
        if count == 0:
            if failed > 0:
                raise RuntimeError("No Hue lights accepted that setting.")
            raise RuntimeError("No Hue lights were found on the bridge.")
        return count

    def _resolve_target(self, bridge_ip: str, app_key: str, target_text: str) -> list[_HueTarget]:
        normalized_target = self._normalize_text(target_text)
        lights = self._get_resource_list(bridge_ip=bridge_ip, app_key=app_key, resource_name="light")
        rooms = self._get_resource_list(bridge_ip=bridge_ip, app_key=app_key, resource_name="room")
        zones = self._get_resource_list(bridge_ip=bridge_ip, app_key=app_key, resource_name="zone")

        candidates: list[_HueTarget] = []

        for light in lights:
            name = str(light.get("metadata", {}).get("name", "")).strip()
            resource_id = str(light.get("id", "")).strip()
            if not name or not resource_id:
                continue
            if self._name_matches_target(name=name, target=normalized_target):
                candidates.append(_HueTarget(resource_type="light", resource_id=resource_id, name=name))

        grouped_targets = self._collect_grouped_targets(rooms) + self._collect_grouped_targets(zones)
        for grouped in grouped_targets:
            if self._name_matches_target(name=grouped.name, target=normalized_target):
                candidates.append(grouped)

        exact = [candidate for candidate in candidates if self._normalize_text(candidate.name) == normalized_target]
        if exact:
            return exact
        return candidates

    def _collect_grouped_targets(self, records: list[dict]) -> list[_HueTarget]:
        targets: list[_HueTarget] = []
        for record in records:
            name = str(record.get("metadata", {}).get("name", "")).strip()
            if not name:
                continue
            services = record.get("services", [])
            if not isinstance(services, list):
                continue
            grouped_id = None
            for service in services:
                if not isinstance(service, dict):
                    continue
                if service.get("rtype") == "grouped_light":
                    grouped_id = str(service.get("rid", "")).strip()
                    if grouped_id:
                        break
            if not grouped_id:
                continue
            targets.append(_HueTarget(resource_type="grouped_light", resource_id=grouped_id, name=name))
        return targets

    def _set_target_payload(
        self,
        bridge_ip: str,
        app_key: str,
        target: _HueTarget,
        payload: dict,
    ) -> None:
        self._put_resource(
            bridge_ip=bridge_ip,
            app_key=app_key,
            resource_name=target.resource_type,
            resource_id=target.resource_id,
            payload=payload,
        )

    def _name_matches_target(self, name: str, target: str) -> bool:
        normalized_name = self._normalize_text(name)
        return target in normalized_name or normalized_name in target

    def _get_resource_list(self, bridge_ip: str, app_key: str, resource_name: str) -> list[dict]:
        url = f"{self._api_base(bridge_ip)}/{resource_name}"
        response = requests.get(
            url,
            headers=self._headers(app_key),
            timeout=_REQUEST_TIMEOUT_SECONDS,
            verify=False,
        )
        if response.status_code >= 400:
            raise RuntimeError(self._build_api_error(response, f"GET {resource_name}"))
        payload = response.json()
        data = payload.get("data", [])
        if not isinstance(data, list):
            raise RuntimeError(f"Hue API returned unexpected {resource_name} payload.")
        return data

    def _put_resource(
        self,
        bridge_ip: str,
        app_key: str,
        resource_name: str,
        resource_id: str,
        payload: dict,
    ) -> None:
        url = f"{self._api_base(bridge_ip)}/{resource_name}/{resource_id}"
        response = requests.put(
            url,
            headers=self._headers(app_key),
            json=payload,
            timeout=_REQUEST_TIMEOUT_SECONDS,
            verify=False,
        )
        if response.status_code >= 400:
            raise RuntimeError(self._build_api_error(response, f"PUT {resource_name}/{resource_id}"))

    def _build_api_error(self, response: requests.Response, operation: str) -> str:
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        errors = payload.get("errors") if isinstance(payload, dict) else None
        if isinstance(errors, list) and errors:
            first = errors[0] if isinstance(errors[0], dict) else {}
            description = str(first.get("description", "")).strip()
            if description:
                return f"{operation} failed ({response.status_code}): {description}"
        return f"{operation} failed with status {response.status_code}."
