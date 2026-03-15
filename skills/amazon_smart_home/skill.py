import json
import re
from dataclasses import dataclass
from typing import Any

import requests

from core.integrations.amazon_alexa_auth import (
    AmazonAlexaAuthError,
    AmazonAlexaCredentials,
    build_auth_headers,
    get_credentials_from_env,
    validate_credentials,
)
from core.skills.base import BaseSkill, SkillContext
from core.skills.result import SkillResult

_REQUEST_TIMEOUT_SECONDS = 8


@dataclass(frozen=True)
class _PlugTarget:
    entity_id: str
    name: str
    entity_type: str


@dataclass(frozen=True)
class _RoomTarget:
    name: str
    plugs: tuple[_PlugTarget, ...]


class AmazonSmartHomeSkill(BaseSkill):
    def __init__(self, manifest) -> None:
        super().__init__(manifest)
        self._credentials_checked = False

    def execute(self, context: SkillContext) -> SkillResult:
        if self._is_setup_help_intent(context.text):
            return self._build_setup_help_result()

        try:
            credentials = get_credentials_from_env()
            if not self._credentials_checked:
                validate_credentials(credentials)
                self._credentials_checked = True
        except AmazonAlexaAuthError as exc:
            return SkillResult(
                ok=False,
                message=exc.user_message,
                skill_id=self.skill_id,
                error=exc.code,
            )

        intent_on = self._parse_power_intent(context.text)
        if intent_on is None:
            return SkillResult(
                ok=False,
                message=(
                    "I support Amazon smart plug power control. Try turn on office plug or turn off desk outlet."
                ),
                skill_id=self.skill_id,
                error="unsupported_amazon_smart_home_intent",
            )

        target_text = self._extract_power_target_text(context.text)
        try:
            plugs, rooms = self._load_target_catalog(credentials)
            if not plugs:
                return SkillResult(
                    ok=False,
                    message="I could not find any Amazon smart plugs on this Alexa account.",
                    skill_id=self.skill_id,
                    error="amazon_smart_plugs_not_found",
                )

            if target_text is None:
                if not self._is_all_plugs_request(context.text):
                    return SkillResult(
                        ok=False,
                        message="Please specify which smart plug to control, or say all plugs.",
                        skill_id=self.skill_id,
                        error="amazon_plug_target_required",
                    )
                changed = self._set_all_plugs(credentials=credentials, plugs=plugs, is_on=intent_on)
                state_word = "on" if intent_on else "off"
                return SkillResult(
                    ok=True,
                    message=f"Turned {state_word} {changed} smart plugs.",
                    skill_id=self.skill_id,
                    data={"target": "all", "count": changed, "is_on": intent_on},
                )

            matches = self._match_plugs_by_name(plugs, target_text)
            if not matches:
                room_matches = self._match_rooms_by_name(rooms, target_text)
                if not room_matches:
                    return SkillResult(
                        ok=False,
                        message=f"I could not find a smart plug or room named {target_text}.",
                        skill_id=self.skill_id,
                        error="amazon_plug_target_not_found",
                        data={"target_text": target_text},
                    )
                if len(room_matches) > 1:
                    options = ", ".join(sorted({room.name for room in room_matches})[:4])
                    return SkillResult(
                        ok=False,
                        message=f"I found multiple rooms for {target_text}: {options}. Please be more specific.",
                        skill_id=self.skill_id,
                        error="amazon_room_target_ambiguous",
                        data={"target_text": target_text, "match_count": len(room_matches)},
                    )
                chosen_room = room_matches[0]
                changed = self._set_all_plugs(
                    credentials=credentials,
                    plugs=list(chosen_room.plugs),
                    is_on=intent_on,
                )
                state_word = "on" if intent_on else "off"
                return SkillResult(
                    ok=True,
                    message=f"Turned {state_word} {changed} smart plugs in {chosen_room.name}.",
                    skill_id=self.skill_id,
                    data={
                        "target": chosen_room.name,
                        "target_type": "room",
                        "count": changed,
                        "is_on": intent_on,
                    },
                )
            if len(matches) > 1:
                options = ", ".join(sorted({plug.name for plug in matches})[:4])
                return SkillResult(
                    ok=False,
                    message=f"I found multiple smart plugs for {target_text}: {options}. Please be more specific.",
                    skill_id=self.skill_id,
                    error="amazon_plug_target_ambiguous",
                    data={"target_text": target_text, "match_count": len(matches)},
                )

            chosen = matches[0]
            self._set_plug_power(credentials=credentials, plug=chosen, is_on=intent_on)
            state_word = "on" if intent_on else "off"
            return SkillResult(
                ok=True,
                message=f"Turned {chosen.name} {state_word}.",
                skill_id=self.skill_id,
                data={
                    "target": chosen.name,
                    "target_entity_id": chosen.entity_id,
                    "target_type": chosen.entity_type,
                    "is_on": intent_on,
                },
            )
        except requests.RequestException as exc:
            return SkillResult(
                ok=False,
                message="I could not reach the Alexa Smart Home API. Check network connectivity and credentials.",
                skill_id=self.skill_id,
                error="amazon_alexa_unreachable",
                data={"details": str(exc)},
            )
        except RuntimeError as exc:
            return SkillResult(
                ok=False,
                message=f"Amazon smart plug command failed: {exc}",
                skill_id=self.skill_id,
                error="amazon_smart_home_api_error",
            )

    def _api_url(self, credentials: AmazonAlexaCredentials, path: str) -> str:
        return f"{credentials.base_url}{path}"

    def _normalize_text(self, text: str) -> str:
        lowered = text.lower().strip()
        lowered = re.sub(r"[^a-z0-9\s]", " ", lowered)
        lowered = re.sub(r"\s+", " ", lowered)
        return lowered

    def _parse_power_intent(self, text: str) -> bool | None:
        normalized = self._normalize_text(text)
        if any(token in normalized for token in ("turn on", "switch on", "power on", "enable", "start")):
            return True
        if any(token in normalized for token in ("turn off", "switch off", "power off", "disable", "stop")):
            return False
        direct_suffix = re.search(
            r"\b(?:light|lights|plug|plugs|outlet|outlets)\s+(on|off)\b",
            normalized,
        )
        if direct_suffix:
            return direct_suffix.group(1) == "on"
        return None

    def _extract_power_target_text(self, text: str) -> str | None:
        normalized = self._normalize_text(text)
        if self._is_all_plugs_request(normalized):
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
                r"(?P<target>.*)\b(light|lights|plug|plugs|outlet|outlets)\s+(on|off)\b",
                normalized,
            )
            if suffix_match:
                target = (suffix_match.group("target") or "").strip()

        target = re.sub(
            r"\b(the|please|in|at|my|amazon|alexa|smart|home|plug|plugs|outlet|outlets|turn|switch|power)\b",
            " ",
            target,
        )
        target = re.sub(r"\s+", " ", target).strip()
        return target or None

    def _is_setup_help_intent(self, text: str) -> bool:
        normalized = self._normalize_text(text)
        return any(
            phrase in normalized
            for phrase in (
                "setup amazon plugs",
                "set up amazon plugs",
                "pair amazon plugs",
                "connect amazon plugs",
                "setup alexa plugs",
                "set up alexa plugs",
            )
        )

    def _build_setup_help_result(self) -> SkillResult:
        message = (
            "To enable Amazon smart plug control, set AMAZON_ALEXA_COOKIE and AMAZON_ALEXA_CSRF from a logged-in "
            "Alexa browser session. Optionally set AMAZON_ALEXA_BASE_URL for your region "
            "(for example https://alexa.amazon.co.uk), then restart Core."
        )
        return SkillResult(
            ok=True,
            message=message,
            skill_id=self.skill_id,
            data={
                "required_env": ["AMAZON_ALEXA_COOKIE", "AMAZON_ALEXA_CSRF"],
                "optional_env": ["AMAZON_ALEXA_BASE_URL"],
            },
        )

    def _is_all_plugs_request(self, text: str) -> bool:
        normalized = self._normalize_text(text)
        return any(
            phrase in normalized
            for phrase in (
                "all plugs",
                "all smart plugs",
                "all outlets",
                "every plug",
                "every smart plug",
                "all of the plugs",
            )
        )

    def _set_all_plugs(self, credentials: AmazonAlexaCredentials, plugs: list[_PlugTarget], is_on: bool) -> int:
        changed = 0
        failed = 0
        for plug in plugs:
            try:
                self._set_plug_power(credentials=credentials, plug=plug, is_on=is_on)
                changed += 1
            except RuntimeError:
                failed += 1
        if changed == 0:
            if failed > 0:
                raise RuntimeError("No smart plugs accepted the requested power command.")
            raise RuntimeError("No smart plugs were available to control.")
        return changed

    def _match_plugs_by_name(self, plugs: list[_PlugTarget], target_text: str) -> list[_PlugTarget]:
        normalized_target = self._normalize_text(target_text)
        candidates = [
            plug
            for plug in plugs
            if (
                normalized_target in self._normalize_text(plug.name)
                or self._normalize_text(plug.name) in normalized_target
            )
        ]
        exact = [plug for plug in candidates if self._normalize_text(plug.name) == normalized_target]
        return exact or candidates

    def _match_rooms_by_name(self, rooms: list[_RoomTarget], target_text: str) -> list[_RoomTarget]:
        normalized_target = self._normalize_text(target_text)
        candidates = [
            room
            for room in rooms
            if (
                normalized_target in self._normalize_text(room.name)
                or self._normalize_text(room.name) in normalized_target
            )
        ]
        exact = [room for room in candidates if self._normalize_text(room.name) == normalized_target]
        return exact or candidates

    def _load_target_catalog(self, credentials: AmazonAlexaCredentials) -> tuple[list[_PlugTarget], list[_RoomTarget]]:
        payload = self._get_phoenix_payload(credentials)
        sources = self._build_payload_sources(payload)
        plugs = self._extract_smart_plugs_from_sources(sources)
        rooms = self._extract_room_targets_from_sources(sources=sources, plugs=plugs)
        return plugs, rooms

    def _build_payload_sources(self, payload: dict[str, Any]) -> list[Any]:
        sources: list[Any] = [payload]
        network_detail = payload.get("networkDetail") if isinstance(payload, dict) else None
        if isinstance(network_detail, str) and network_detail.strip():
            try:
                sources.append(json.loads(network_detail))
            except ValueError:
                pass
        elif isinstance(network_detail, (dict, list)):
            sources.append(network_detail)
        return sources

    def _extract_smart_plugs_from_sources(self, sources: list[Any]) -> list[_PlugTarget]:
        plugs_by_id: dict[str, _PlugTarget] = {}
        for source in sources:
            for node in self._walk_dict_nodes(source):
                if not self._looks_like_plug_entity(node):
                    continue
                entity_id = self._extract_entity_id(node)
                name = self._extract_friendly_name(node)
                if not entity_id or not name:
                    continue
                entity_type = str(node.get("entityType", "APPLIANCE")).strip() or "APPLIANCE"
                plugs_by_id[entity_id] = _PlugTarget(
                    entity_id=entity_id,
                    name=name,
                    entity_type=entity_type,
                )
        return sorted(plugs_by_id.values(), key=lambda item: item.name.lower())

    def _extract_room_targets_from_sources(
        self, sources: list[Any], plugs: list[_PlugTarget]
    ) -> list[_RoomTarget]:
        plugs_by_id = {plug.entity_id: plug for plug in plugs}
        room_entries: dict[str, dict[str, Any]] = {}
        for source in sources:
            for node in self._walk_dict_nodes(source):
                room_name = self._extract_room_name(node)
                if not room_name:
                    continue
                member_ids = self._extract_related_entity_ids(node)
                matched_plugs = [plugs_by_id[entity_id] for entity_id in member_ids if entity_id in plugs_by_id]
                if not matched_plugs:
                    continue
                room_key = self._normalize_text(room_name)
                if room_key not in room_entries:
                    room_entries[room_key] = {"name": room_name, "plugs": {}}
                for plug in matched_plugs:
                    room_entries[room_key]["plugs"][plug.entity_id] = plug

        rooms: list[_RoomTarget] = []
        for entry in room_entries.values():
            entry_plugs = tuple(
                sorted(
                    entry["plugs"].values(),
                    key=lambda plug: self._normalize_text(plug.name),
                )
            )
            if entry_plugs:
                rooms.append(_RoomTarget(name=str(entry["name"]), plugs=entry_plugs))
        rooms.sort(key=lambda room: self._normalize_text(room.name))
        return rooms

    def _extract_room_name(self, node: dict[str, Any]) -> str | None:
        for key in ("roomName", "groupName"):
            value = node.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        type_hint = " ".join(
            str(node.get(key, "")).lower()
            for key in ("type", "entityType", "groupType", "category")
        )
        if "room" not in type_hint and "group" not in type_hint:
            return None
        return self._extract_friendly_name(node)

    def _extract_related_entity_ids(self, node: dict[str, Any]) -> set[str]:
        related_ids: set[str] = set()
        for key in (
            "memberEntityIds",
            "entityIds",
            "applianceIds",
            "endpointIds",
            "memberIds",
            "members",
            "children",
            "devices",
            "appliances",
            "endpoints",
            "entities",
            "relationships",
            "connectedDevices",
        ):
            if key in node:
                related_ids.update(self._collect_entity_ids(node.get(key)))
        return related_ids

    def _collect_entity_ids(self, value: Any) -> set[str]:
        entity_ids: set[str] = set()
        if isinstance(value, dict):
            for key, item in value.items():
                key_lower = key.lower()
                if "id" in key_lower:
                    if isinstance(item, str) and item.strip():
                        entity_ids.add(item.strip())
                    elif isinstance(item, list):
                        for entry in item:
                            if isinstance(entry, str) and entry.strip():
                                entity_ids.add(entry.strip())
                entity_ids.update(self._collect_entity_ids(item))
        elif isinstance(value, list):
            for item in value:
                entity_ids.update(self._collect_entity_ids(item))
        return entity_ids

    def _walk_dict_nodes(self, value: Any):
        if isinstance(value, dict):
            yield value
            for child in value.values():
                yield from self._walk_dict_nodes(child)
        elif isinstance(value, list):
            for child in value:
                yield from self._walk_dict_nodes(child)

    def _extract_entity_id(self, node: dict[str, Any]) -> str | None:
        for key in ("entityId", "applianceId", "endpointId", "id"):
            value = node.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def _extract_friendly_name(self, node: dict[str, Any]) -> str | None:
        for key in ("friendlyName", "name", "label", "applianceName"):
            value = node.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def _looks_like_plug_entity(self, node: dict[str, Any]) -> bool:
        flattened = self._flatten_text_values(node)
        if "smartplug" in flattened or "smart plug" in flattened:
            return True

        has_power_capability = any(
            token in flattened
            for token in (
                "turnon",
                "turnoff",
                "powercontroller",
                "toggle",
                "setpowerstate",
            )
        )
        name_value = self._extract_friendly_name(node)
        normalized_name = self._normalize_text(name_value) if name_value else ""
        is_named_plug = "plug" in normalized_name or "outlet" in normalized_name
        return bool(has_power_capability and is_named_plug)

    def _flatten_text_values(self, value: Any) -> str:
        pieces: list[str] = []
        if isinstance(value, dict):
            for item in value.values():
                pieces.append(self._flatten_text_values(item))
        elif isinstance(value, list):
            for item in value:
                pieces.append(self._flatten_text_values(item))
        elif isinstance(value, str):
            pieces.append(value.lower())
        return " ".join(piece for piece in pieces if piece)

    def _get_phoenix_payload(self, credentials: AmazonAlexaCredentials) -> dict[str, Any]:
        response = requests.get(
            self._api_url(credentials, "/api/phoenix?includeRelationships=true"),
            headers=build_auth_headers(credentials),
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
        if response.status_code >= 400:
            raise RuntimeError(self._build_api_error(response, "GET /api/phoenix"))
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("Alexa API returned an unexpected smart home payload.")
        return payload

    def _set_plug_power(self, credentials: AmazonAlexaCredentials, plug: _PlugTarget, is_on: bool) -> None:
        action = "turnOn" if is_on else "turnOff"
        payload = {
            "controlRequests": [
                {
                    "entityId": plug.entity_id,
                    "entityType": plug.entity_type,
                    "parameters": {"action": action},
                }
            ]
        }
        response = requests.post(
            self._api_url(credentials, "/api/phoenix/state"),
            headers=build_auth_headers(credentials),
            json=payload,
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
        if response.status_code >= 400:
            raise RuntimeError(self._build_api_error(response, f"POST /api/phoenix/state ({plug.name})"))

        try:
            body = response.json()
        except ValueError:
            body = {}
        responses = body.get("controlResponses") if isinstance(body, dict) else None
        if not isinstance(responses, list) or not responses:
            return

        first = responses[0]
        if not isinstance(first, dict):
            return
        code = str(first.get("code", "")).strip().lower()
        if code and code not in ("success", "ok", "200"):
            message = str(first.get("message", "")).strip() or code
            raise RuntimeError(f"{plug.name}: {message}")

    def _build_api_error(self, response: requests.Response, operation: str) -> str:
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        message = ""
        if isinstance(payload, dict):
            for key in ("message", "error", "errorMessage"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    message = value.strip()
                    break
        if message:
            return f"{operation} failed ({response.status_code}): {message}"
        return f"{operation} failed with status {response.status_code}."
