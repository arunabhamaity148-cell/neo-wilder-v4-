"""Edge registry parser and validator for NEO-WILDER V4."""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import yaml

from neo_wilder.domain.enums import Archetype, Direction, EdgeStatus, EvidenceStatus, ScoringCluster


@dataclass(frozen=True)
class EdgeMetadata:
    """Canonical edge metadata representation."""

    id: str
    legacy: str | None
    name: str
    archetype: Archetype
    direction: Direction
    status: EdgeStatus
    evidence: EvidenceStatus
    cluster: ScoringCluster


class EdgeRegistry:
    """Loads and validates EDGE_REGISTRY.yaml."""

    def __init__(self, registry_path: Path):
        self.registry_path = registry_path
        self._edges: Dict[str, EdgeMetadata] = {}
        self._load()

    def _load(self):
        if not self.registry_path.exists():
            raise FileNotFoundError(f"Registry not found at {self.registry_path}")

        with open(self.registry_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        edges_data = data.get("edges", [])
        for e in edges_data:
            meta = EdgeMetadata(
                id=e["id"],
                legacy=e.get("legacy"),
                name=e["name"],
                archetype=Archetype(e["archetype"]),
                direction=Direction(e["direction"]),
                status=EdgeStatus(e["status"]),
                evidence=EvidenceStatus(e["evidence"]),
                cluster=ScoringCluster(e["cluster"]),
            )
            self._edges[meta.id] = meta

    def get(self, edge_id: str) -> EdgeMetadata:
        if edge_id not in self._edges:
            raise KeyError(f"Unknown edge ID: {edge_id}")
        return self._edges[edge_id]

    def all_edges(self) -> List[EdgeMetadata]:
        return list(self._edges.values())

    def active_edges(self) -> List[EdgeMetadata]:
        return [e for e in self._edges.values() if e.status == EdgeStatus.ACTIVE]

    def shadow_edges(self) -> List[EdgeMetadata]:
        return [e for e in self._edges.values() if e.status == EdgeStatus.SHADOW]
