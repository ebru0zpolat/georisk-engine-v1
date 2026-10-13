"""GEO-193 static actor-graph loader (JSON fixture source)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.scoring.propagation import ActorEdge, ActorGraph
from app.services.asset_snapshot_store import AssetSnapshot

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ACTOR_GRAPH_PATH = REPO_ROOT / "data" / "graphs" / "actor_graph_default.json"


@dataclass(frozen=True)
class ActorGraphMetadata:
    version: str
    default_origin_node_id: str
    labels: dict[str, str]
    sectors: dict[str, str]
    baselines: dict[str, int]
    node_ids: frozenset[str]


@dataclass(frozen=True)
class LoadedActorGraph:
    graph: ActorGraph
    metadata: ActorGraphMetadata


def _parse_graph_document(raw: dict[str, Any]) -> LoadedActorGraph:
    version = str(raw.get("version", "1.0"))
    default_origin = str(raw["default_origin_node_id"])

    labels: dict[str, str] = {}
    sectors: dict[str, str] = {}
    baselines: dict[str, int] = {}
    node_ids: set[str] = set()

    for node in raw["nodes"]:
        node_id = str(node["id"])
        node_ids.add(node_id)
        labels[node_id] = str(node.get("label", node_id))
        sectors[node_id] = str(node.get("sector", "industrial"))
        if "baseline_score" in node:
            baselines[node_id] = int(node["baseline_score"])

    edges: list[ActorEdge] = []
    for edge in raw["edges"]:
        edges.append(
            ActorEdge(
                source_id=str(edge["source"]),
                target_id=str(edge["target"]),
                dependency_weight=float(edge["dependency_weight"]),
            )
        )

    metadata = ActorGraphMetadata(
        version=version,
        default_origin_node_id=default_origin,
        labels=labels,
        sectors=sectors,
        baselines=baselines,
        node_ids=frozenset(node_ids),
    )
    return LoadedActorGraph(graph=ActorGraph(edges=tuple(edges)), metadata=metadata)


def load_actor_graph(path: Path | None = None) -> LoadedActorGraph:
    graph_path = path or DEFAULT_ACTOR_GRAPH_PATH
    raw = json.loads(graph_path.read_text(encoding="utf-8"))
    loaded = _parse_graph_document(raw)

    unknown_nodes: set[str] = set()
    for edge in loaded.graph.edges:
        unknown_nodes.update({edge.source_id, edge.target_id})
    unknown_nodes -= loaded.metadata.node_ids
    if unknown_nodes:
        missing = ", ".join(sorted(unknown_nodes))
        raise ValueError(f"actor graph edges reference unknown nodes: {missing}")

    if loaded.metadata.default_origin_node_id not in loaded.metadata.node_ids:
        raise ValueError(
            "default_origin_node_id not present in nodes: "
            f"{loaded.metadata.default_origin_node_id}"
        )

    return loaded


@lru_cache(maxsize=1)
def get_default_actor_graph() -> LoadedActorGraph:
    return load_actor_graph()


def resolve_origin_node_id(
    snapshot: AssetSnapshot,
    metadata: ActorGraphMetadata,
    *,
    facility_slug: str,
) -> str:
    """Map facility slug to graph node when present; else default origin."""
    if facility_slug in metadata.node_ids:
        return facility_slug
    return metadata.default_origin_node_id
