import importlib.util
import json
from dataclasses import dataclass
from pathlib import Path

from core.skills.base import BaseSkill
from core.skills.manifest import SkillManifest


@dataclass(frozen=True)
class LoadedSkill:
    manifest: SkillManifest
    instance: BaseSkill
    path: Path


class SkillRegistry:
    def __init__(self, skills_root: Path) -> None:
        self.skills_root = skills_root
        self._skills: list[LoadedSkill] = []

    @property
    def skills(self) -> tuple[LoadedSkill, ...]:
        return tuple(self._skills)

    def load(self) -> None:
        loaded: list[LoadedSkill] = []
        if not self.skills_root.exists():
            self._skills = loaded
            return

        for skill_dir in sorted(self.skills_root.iterdir(), key=lambda p: p.name):
            if not skill_dir.is_dir():
                continue
            manifest_path = skill_dir / "manifest.json"
            skill_path = skill_dir / "skill.py"
            if not manifest_path.is_file() or not skill_path.is_file():
                continue
            try:
                manifest = self._load_manifest(manifest_path)
                if not manifest.enabled:
                    continue
                skill_instance = self._load_skill(skill_path, manifest)
                loaded.append(LoadedSkill(manifest=manifest, instance=skill_instance, path=skill_dir))
            except Exception as exc:
                print(f"Skipping skill '{skill_dir.name}': {exc}")

        self._skills = loaded

    def _load_manifest(self, manifest_path: Path) -> SkillManifest:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        return SkillManifest.from_dict(payload)

    def _load_skill(self, skill_path: Path, manifest: SkillManifest) -> BaseSkill:
        module_name = f"jarvis_skill_{manifest.skill_id.replace('-', '_')}"
        spec = importlib.util.spec_from_file_location(module_name, skill_path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Unable to create import spec for {skill_path}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        skill_cls = getattr(module, manifest.entry_class, None)
        if skill_cls is None:
            raise RuntimeError(
                f"entry_class '{manifest.entry_class}' not found in {skill_path.name}"
            )

        skill_instance = skill_cls(manifest)
        if not isinstance(skill_instance, BaseSkill):
            raise TypeError(f"{manifest.entry_class} must inherit from BaseSkill")
        return skill_instance
