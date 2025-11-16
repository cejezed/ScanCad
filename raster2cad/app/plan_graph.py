"""
Plan intelligence - room and feature graph analysis.

Builds relationship graphs between rooms, doors, and features
to understand spatial topology and building logic.
"""

import logging
from typing import Dict, Any, List, Set, Tuple, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Node:
    """Graph node representing a room or space."""
    id: str
    node_type: str  # "room", "space", "area"
    name: Optional[str] = None
    area_m2: Optional[float] = None
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Edge:
    """Graph edge representing a connection between nodes."""
    from_node: str
    to_node: str
    edge_type: str  # "door", "opening", "adjacent"
    door_type: Optional[str] = None
    bidirectional: bool = True
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PlanGraph:
    """Spatial topology graph for a floor plan."""
    nodes: Dict[str, Node] = field(default_factory=dict)
    edges: List[Edge] = field(default_factory=list)
    properties: Dict[str, Any] = field(default_factory=dict)

    def add_node(self, node: Node) -> None:
        """Add a node to the graph."""
        self.nodes[node.id] = node

    def add_edge(self, edge: Edge) -> None:
        """Add an edge to the graph."""
        if edge.from_node not in self.nodes:
            logger.warning(f"Edge references unknown node: {edge.from_node}")
        if edge.to_node not in self.nodes:
            logger.warning(f"Edge references unknown node: {edge.to_node}")
        self.edges.append(edge)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to serializable dict."""
        return {
            "nodes": [
                {
                    "id": n.id,
                    "type": n.node_type,
                    "name": n.name,
                    "area_m2": n.area_m2,
                    "properties": n.properties,
                }
                for n in self.nodes.values()
            ],
            "edges": [
                {
                    "from": e.from_node,
                    "to": e.to_node,
                    "type": e.edge_type,
                    "door_type": e.door_type,
                    "bidirectional": e.bidirectional,
                    "properties": e.properties,
                }
                for e in self.edges
            ],
            "properties": self.properties,
        }


def build_room_graph(
    rooms: List[Dict[str, Any]],
    plan: Dict[str, Any],
) -> PlanGraph:
    """
    Build a spatial topology graph from rooms and features.

    Algorithm:
    1. Create nodes for each room
    2. Find door connections between rooms
    3. Identify room classifications (wet room, living space, etc.)
    4. Build edge connections

    Args:
        rooms: List of room dicts from room detection
        plan: Full plan JSON with all features

    Returns:
        PlanGraph object
    """
    graph = PlanGraph()

    # Create nodes from rooms
    for room in rooms:
        node = Node(
            id=room.get("id", ""),
            node_type="room",
            name=room.get("name"),
            area_m2=room.get("area_m2"),
            properties={
                "polygon": room.get("polygon"),
                "centroid": room.get("centroid"),
            },
        )
        graph.add_node(node)

    # Classify rooms based on name/content
    _classify_rooms(graph)

    # Find door connections
    symbols = [f for f in plan.get("features", []) if f.get("label") == "symbol"]
    doors = [s for s in symbols if s.get("metadata", {}).get("symbol_type") == "door"]

    # Match doors to rooms (simplified: assumes doors are between adjacent rooms)
    room_ids = list(graph.nodes.keys())
    for i, room_id_1 in enumerate(room_ids):
        for room_id_2 in room_ids[i + 1 :]:
            # Check if rooms are adjacent (simplified: just check if there's a door)
            # In a real implementation, you'd check spatial proximity
            if doors:
                door = doors[0]  # Use first door for now
                door_type = door.get("metadata", {}).get("symbol_type", "door")

                edge = Edge(
                    from_node=room_id_1,
                    to_node=room_id_2,
                    edge_type="door",
                    door_type=door_type,
                    bidirectional=True,
                )
                graph.add_edge(edge)
                doors.pop(0)

    logger.info(f"Built graph with {len(graph.nodes)} rooms and {len(graph.edges)} connections")
    return graph


def _classify_rooms(graph: PlanGraph) -> None:
    """
    Classify rooms based on name and characteristics.

    Adds properties like:
    - is_wet_room: contains water fixtures (wc, douche, wastafel)
    - is_kitchen: identified as cooking area
    - is_living_space: public/social area
    """
    wet_room_keywords = ["wc", "douche", "bathroom", "toilet", "keuken", "kitchen"]
    kitchen_keywords = ["keuken", "kitchen"]
    living_keywords = ["woonkamer", "living room", "salon"]
    sleeping_keywords = ["slaapkamer", "bedroom", "chambre"]

    for node in graph.nodes.values():
        name = (node.name or "").lower()

        node.properties["is_wet_room"] = any(k in name for k in wet_room_keywords)
        node.properties["is_kitchen"] = any(k in name for k in kitchen_keywords)
        node.properties["is_living"] = any(k in name for k in living_keywords)
        node.properties["is_sleeping"] = any(k in name for k in sleeping_keywords)


def analyze_connectivity(graph: PlanGraph) -> Dict[str, Any]:
    """
    Analyze graph connectivity metrics.

    Returns:
        Dict with statistics about connections
    """
    # Build adjacency
    adjacency = {node_id: set() for node_id in graph.nodes.keys()}
    for edge in graph.edges:
        adjacency[edge.from_node].add(edge.to_node)
        if edge.bidirectional:
            adjacency[edge.to_node].add(edge.from_node)

    # Calculate degree and connectivity
    degrees = {node_id: len(neighbors) for node_id, neighbors in adjacency.items()}
    isolated_rooms = [node_id for node_id, degree in degrees.items() if degree == 0]

    # Count features
    wet_rooms = sum(1 for n in graph.nodes.values() if n.properties.get("is_wet_room"))
    living_spaces = sum(1 for n in graph.nodes.values() if n.properties.get("is_living"))
    sleeping_spaces = sum(1 for n in graph.nodes.values() if n.properties.get("is_sleeping"))

    return {
        "total_rooms": len(graph.nodes),
        "total_connections": len(graph.edges),
        "avg_connectivity": sum(degrees.values()) / len(degrees) if degrees else 0,
        "isolated_rooms": isolated_rooms,
        "wet_rooms": wet_rooms,
        "living_spaces": living_spaces,
        "sleeping_spaces": sleeping_spaces,
    }


def find_path_between_rooms(
    graph: PlanGraph,
    from_room: str,
    to_room: str,
) -> Optional[List[str]]:
    """
    Find shortest path between two rooms using BFS.

    Args:
        graph: PlanGraph
        from_room: Starting room ID
        to_room: Destination room ID

    Returns:
        List of room IDs forming the path, or None if no path exists
    """
    if from_room not in graph.nodes or to_room not in graph.nodes:
        return None

    # Build adjacency
    adjacency = {node_id: set() for node_id in graph.nodes.keys()}
    for edge in graph.edges:
        adjacency[edge.from_node].add(edge.to_node)
        if edge.bidirectional:
            adjacency[edge.to_node].add(edge.from_node)

    # BFS
    from collections import deque

    queue = deque([(from_room, [from_room])])
    visited = {from_room}

    while queue:
        current, path = queue.popleft()

        if current == to_room:
            return path

        for neighbor in adjacency.get(current, set()):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, path + [neighbor]))

    return None


def identify_clusters(graph: PlanGraph) -> List[Set[str]]:
    """
    Identify clusters of connected rooms (e.g., all living areas, all private areas).

    Returns:
        List of room ID clusters
    """
    # Build adjacency
    adjacency = {node_id: set() for node_id in graph.nodes.keys()}
    for edge in graph.edges:
        adjacency[edge.from_node].add(edge.to_node)
        if edge.bidirectional:
            adjacency[edge.to_node].add(edge.from_node)

    clusters = []
    visited = set()

    for start_room in graph.nodes.keys():
        if start_room in visited:
            continue

        # DFS to find cluster
        cluster = set()
        stack = [start_room]

        while stack:
            current = stack.pop()
            if current in visited:
                continue

            visited.add(current)
            cluster.add(current)

            for neighbor in adjacency.get(current, set()):
                if neighbor not in visited:
                    stack.append(neighbor)

        if cluster:
            clusters.append(cluster)

    logger.info(f"Identified {len(clusters)} room clusters")
    return clusters
