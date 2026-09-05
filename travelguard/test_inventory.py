"""Machine-readable test inventory registry."""

from pathlib import Path
from typing import Dict, List, Optional
import yaml

from travelguard.models import TestItem, TestPriority


class TestInventoryRegistry:
    """Registry providing access to the machine-readable test inventory."""

    def __init__(self, inventory_path: Optional[Path] = None):
        if inventory_path is None:
            inventory_path = Path(__file__).parent / "test_inventory.yaml"
        self.inventory_path = inventory_path
        self._tests: Dict[str, TestItem] = {}
        self.load()

    def load(self) -> None:
        """Load test definitions from YAML."""
        if not self.inventory_path.exists():
            raise FileNotFoundError(f"Test inventory file not found: {self.inventory_path}")

        with open(self.inventory_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        raw_tests = data.get("tests", [])
        self._tests.clear()
        for raw in raw_tests:
            item = TestItem(
                id=raw["id"],
                name=raw["name"],
                file=raw["file"],
                description=raw["description"],
                business_journeys=raw.get("business_journeys", []),
                criticality=raw.get("criticality", "high"),
                priority_tier=TestPriority(raw.get("priority_tier", "P1")),
                tags=raw.get("tags", []),
                expected_duration_ms=raw.get("expected_duration_ms", 1000),
            )
            self._tests[item.id] = item

    def get_all(self) -> List[TestItem]:
        """Return all registered tests."""
        return list(self._tests.values())

    def get_by_id(self, test_id: str) -> Optional[TestItem]:
        """Look up test by unique ID."""
        return self._tests.get(test_id)

    def get_by_journey(self, journey_id: str) -> List[TestItem]:
        """Return tests associated with a specific business user journey."""
        return [t for t in self._tests.values() if journey_id in t.business_journeys]

    def get_by_criticality(self, criticality: str) -> List[TestItem]:
        """Return tests matching a criticality level."""
        return [t for t in self._tests.values() if t.criticality == criticality.lower()]


_registry_instance: Optional[TestInventoryRegistry] = None


def get_test_inventory() -> TestInventoryRegistry:
    """Singleton getter for test inventory."""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = TestInventoryRegistry()
    return _registry_instance
