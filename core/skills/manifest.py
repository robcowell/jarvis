from dataclasses import dataclass


@dataclass(frozen=True)
class SkillManifest:
    skill_id: str
    name: str
    description: str
    entry_class: str
    trigger_phrases: tuple[str, ...]
    priority: int = 100
    enabled: bool = True

    @classmethod
    def from_dict(cls, payload: dict) -> "SkillManifest":
        skill_id = str(payload.get("id", "")).strip()
        name = str(payload.get("name", "")).strip()
        description = str(payload.get("description", "")).strip()
        entry_class = str(payload.get("entry_class", "")).strip()
        trigger_phrases = tuple(
            phrase.strip().lower()
            for phrase in payload.get("trigger_phrases", [])
            if isinstance(phrase, str) and phrase.strip()
        )
        priority = int(payload.get("priority", 100))
        enabled = bool(payload.get("enabled", True))

        if not skill_id:
            raise ValueError("manifest is missing required field: id")
        if not name:
            raise ValueError(f"manifest '{skill_id}' is missing required field: name")
        if not entry_class:
            raise ValueError(f"manifest '{skill_id}' is missing required field: entry_class")

        return cls(
            skill_id=skill_id,
            name=name,
            description=description,
            entry_class=entry_class,
            trigger_phrases=trigger_phrases,
            priority=priority,
            enabled=enabled,
        )
