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

        intent_on = self._parse_power_intent(context.text)
        if intent_on is None:
            return SkillResult(
                ok=False,
                message="I can only control Hue power state right now. Say turn lights on or off.",
                skill_id=self.skill_id,
                error="unsupported_hue_intent",
            )

        target_text = self._extract_target_text(context.text)
        try:
            if target_text is None:
                changed = self._set_all_lights_power(bridge_ip=bridge_ip, app_key=app_key, is_on=intent_on)
                state_word = "on" if intent_on else "off"
                return SkillResult(
                    ok=True,
                    message=f"Set {changed} Hue lights {state_word}.",
                    skill_id=self.skill_id,
                    data={"count": changed, "target": "all", "is_on": intent_on},
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
            self._set_target_power(
                bridge_ip=bridge_ip,
                app_key=app_key,
                target=chosen,
                is_on=intent_on,
            )
            state_word = "on" if intent_on else "off"
            return SkillResult(
                ok=True,
                message=f"Turned {chosen.name} {state_word}.",
                skill_id=self.skill_id,
                data={
                    "target": chosen.name,
                    "target_type": chosen.resource_type,
                    "is_on": intent_on,
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

    def _extract_target_text(self, text: str) -> str | None:
        normalized = self._normalize_text(text)
        if "all lights" in normalized:
            return None

        target = ""
        on_patterns = [
            r"\bturn on\b(?P<target>.*)",
            r"\bswitch on\b(?P<target>.*)",
            r"\bpower on\b(?P<target>.*)",
        ]
        off_patterns = [
            r"\bturn off\b(?P<target>.*)",
            r"\bswitch off\b(?P<target>.*)",
            r"\bpower off\b(?P<target>.*)",
        ]
        for pattern in on_patterns + off_patterns:
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

        target = re.sub(r"\b(the|please|in|at|my|hue|light|lights|lamp|lamps)\b", " ", target)
        target = re.sub(r"\s+", " ", target).strip()
        return target or None

    def _normalize_text(self, text: str) -> str:
        lowered = text.lower().strip()
        lowered = re.sub(r"[^a-z0-9\s]", " ", lowered)
        lowered = re.sub(r"\s+", " ", lowered)
        return lowered

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

    def _set_all_lights_power(self, bridge_ip: str, app_key: str, is_on: bool) -> int:
        lights = self._get_resource_list(bridge_ip=bridge_ip, app_key=app_key, resource_name="light")
        count = 0
        for item in lights:
            light_id = str(item.get("id", "")).strip()
            if not light_id:
                continue
            self._put_resource(
                bridge_ip=bridge_ip,
                app_key=app_key,
                resource_name="light",
                resource_id=light_id,
                payload={"on": {"on": is_on}},
            )
            count += 1
        if count == 0:
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

    def _set_target_power(
        self,
        bridge_ip: str,
        app_key: str,
        target: _HueTarget,
        is_on: bool,
    ) -> None:
        self._put_resource(
            bridge_ip=bridge_ip,
            app_key=app_key,
            resource_name=target.resource_type,
            resource_id=target.resource_id,
            payload={"on": {"on": is_on}},
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
