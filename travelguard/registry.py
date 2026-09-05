"""Loader and query interface for the machine-readable Business Journey Registry."""

from pathlib import Path
from typing import Dict, List, Optional
import yaml

from travelguard.models import BusinessJourney, JourneyCriticality


class JourneyRegistry:
    """Registry containing all registered SkyBook business journeys."""

    def __init__(self, journeys: Optional[Dict[str, BusinessJourney]] = None):
        self._journeys: Dict[str, BusinessJourney] = journeys or {}

    @classmethod
    def load_from_file(cls, yaml_path: Optional[Path] = None) -> "JourneyRegistry":
        """Load business journeys from a YAML definition file."""
        if yaml_path is None:
            yaml_path = Path(__file__).parent / "journeys.yaml"

        if not yaml_path.exists():
            raise FileNotFoundError(f"Journey definition file not found: {yaml_path}")

        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        journeys: Dict[str, BusinessJourney] = {}
        for j_id, j_data in data.get("journeys", {}).items():
            criticality = JourneyCriticality(j_data.get("criticality", "medium").lower())
            journeys[j_id] = BusinessJourney(
                id=j_id,
                name=j_data.get("name", j_id),
                description=j_data.get("description", ""),
                criticality=criticality,
                workflow_stage=j_data.get("workflow_stage", 1),
                components=j_data.get("components", []),
                frontend_paths=j_data.get("frontend_paths", []),
                api_paths=j_data.get("api_paths", []),
                tests=j_data.get("tests", []),
            )
        return cls(journeys)

    def get_journey(self, journey_id: str) -> Optional[BusinessJourney]:
        """Retrieve a journey by its unique identifier."""
        return self._journeys.get(journey_id)

    def list_journeys(self) -> List[BusinessJourney]:
        """Return all registered journeys sorted by workflow stage."""
        return sorted(self._journeys.values(), key=lambda j: j.workflow_stage)

    def find_journeys_by_path(self, file_path: str) -> List[BusinessJourney]:
        """Find all journeys associated with a given file path."""
        norm_path = file_path.replace("\\", "/").strip().lower()
        matched: List[BusinessJourney] = []
        for journey in self._journeys.values():
            for fp in journey.frontend_paths:
                if norm_path == fp.lower() or norm_path.endswith(fp.lower()) or fp.lower().endswith(norm_path):
                    matched.append(journey)
                    break
            else:
                for ap in journey.api_paths:
                    if norm_path == ap.lower() or norm_path.endswith(ap.lower()) or ap.lower() in norm_path:
                        matched.append(journey)
                        break
        return matched

    def find_journeys_by_component(self, component_name: str) -> List[BusinessJourney]:
        """Find journeys referencing a specific component name."""
        comp_norm = component_name.strip().lower()
        matched: List[BusinessJourney] = []
        for journey in self._journeys.values():
            if any(comp_norm == c.lower() or comp_norm in c.lower() for c in journey.components):
                matched.append(journey)
        return matched


_default_registry: Optional[JourneyRegistry] = None


def get_journey_registry() -> JourneyRegistry:
    """Get the singleton default journey registry."""
    global _default_registry
    if _default_registry is None:
        _default_registry = JourneyRegistry.load_from_file()
    return _default_registry
