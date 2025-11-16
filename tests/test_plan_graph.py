"""
Test suite for plan graph and spatial topology module.
Tests room graph construction, connectivity analysis, and pathfinding.
"""

import pytest
from app.plan_graph import (
    Node,
    Edge,
    PlanGraph,
    build_room_graph,
    _classify_rooms,
    analyze_connectivity,
    find_path_between_rooms,
    identify_clusters,
)


class TestGraphNodes:
    """Tests for Node dataclass."""

    def test_node_creation(self):
        node = Node(id="room_001", node_type="room", name="Woonkamer", area_m2=25.5)

        assert node.id == "room_001"
        assert node.node_type == "room"
        assert node.name == "Woonkamer"
        assert node.area_m2 == 25.5

    def test_node_defaults(self):
        node = Node(id="room_002", node_type="space")

        assert node.name is None
        assert node.area_m2 is None
        assert node.properties == {}

    def test_node_with_properties(self):
        props = {"floor": 1, "color": "blue"}
        node = Node(
            id="room_003", node_type="area", name="Hall", properties=props
        )

        assert node.properties == props
        assert node.properties["floor"] == 1


class TestGraphEdges:
    """Tests for Edge dataclass."""

    def test_edge_creation(self):
        edge = Edge(
            from_node="room_001",
            to_node="room_002",
            edge_type="door",
            door_type="single",
            bidirectional=True,
        )

        assert edge.from_node == "room_001"
        assert edge.to_node == "room_002"
        assert edge.edge_type == "door"
        assert edge.door_type == "single"
        assert edge.bidirectional is True

    def test_edge_adjacency(self):
        edge = Edge(
            from_node="room_001",
            to_node="room_002",
            edge_type="opening",
            bidirectional=False,
        )

        assert edge.bidirectional is False
        assert edge.door_type is None

    def test_edge_with_properties(self):
        props = {"width_mm": 800, "material": "wood"}
        edge = Edge(
            from_node="room_001",
            to_node="room_002",
            edge_type="door",
            properties=props,
        )

        assert edge.properties == props


class TestPlanGraph:
    """Tests for PlanGraph structure."""

    def test_graph_creation(self):
        graph = PlanGraph()

        assert graph.nodes == {}
        assert graph.edges == []
        assert graph.properties == {}

    def test_add_node(self):
        graph = PlanGraph()
        node = Node(id="room_001", node_type="room", name="Woonkamer")

        graph.add_node(node)

        assert "room_001" in graph.nodes
        assert graph.nodes["room_001"].name == "Woonkamer"

    def test_add_multiple_nodes(self):
        graph = PlanGraph()
        nodes = [
            Node(id="room_001", node_type="room", name="Woonkamer"),
            Node(id="room_002", node_type="room", name="Keuken"),
            Node(id="room_003", node_type="room", name="Slaapkamer"),
        ]

        for node in nodes:
            graph.add_node(node)

        assert len(graph.nodes) == 3
        assert all(f"room_{i:03d}" in graph.nodes for i in range(1, 4))

    def test_add_edge(self):
        graph = PlanGraph()
        graph.add_node(Node(id="room_001", node_type="room"))
        graph.add_node(Node(id="room_002", node_type="room"))

        edge = Edge(
            from_node="room_001", to_node="room_002", edge_type="door"
        )
        graph.add_edge(edge)

        assert len(graph.edges) == 1
        assert graph.edges[0].from_node == "room_001"

    def test_add_edge_unknown_node_warning(self):
        """Test that adding edge to unknown node produces warning."""
        graph = PlanGraph()
        graph.add_node(Node(id="room_001", node_type="room"))

        edge = Edge(
            from_node="room_001", to_node="room_999", edge_type="door"
        )
        # Should still add edge, but log warning
        graph.add_edge(edge)

        assert len(graph.edges) == 1

    def test_graph_to_dict(self):
        """Test converting graph to serializable dict."""
        graph = PlanGraph()
        graph.add_node(Node(id="room_001", node_type="room", name="Woonkamer", area_m2=25.5))
        graph.add_node(Node(id="room_002", node_type="room", name="Keuken", area_m2=12.0))
        graph.add_edge(Edge(
            from_node="room_001",
            to_node="room_002",
            edge_type="door",
            door_type="single",
        ))

        result = graph.to_dict()

        assert len(result["nodes"]) == 2
        assert len(result["edges"]) == 1
        assert result["nodes"][0]["id"] == "room_001"
        assert result["edges"][0]["from"] == "room_001"


class TestRoomClassification:
    """Tests for room classification."""

    def test_classify_wet_rooms(self):
        graph = PlanGraph()
        graph.add_node(Node(id="room_001", node_type="room", name="Bathroom"))
        graph.add_node(Node(id="room_002", node_type="room", name="WC"))
        graph.add_node(Node(id="room_003", node_type="room", name="Woonkamer"))

        _classify_rooms(graph)

        assert graph.nodes["room_001"].properties["is_wet_room"] is True
        assert graph.nodes["room_002"].properties["is_wet_room"] is True
        assert graph.nodes["room_003"].properties["is_wet_room"] is False

    def test_classify_kitchens(self):
        graph = PlanGraph()
        graph.add_node(Node(id="room_001", node_type="room", name="Keuken"))
        graph.add_node(Node(id="room_002", node_type="room", name="Kitchen"))
        graph.add_node(Node(id="room_003", node_type="room", name="Woonkamer"))

        _classify_rooms(graph)

        assert graph.nodes["room_001"].properties["is_kitchen"] is True
        assert graph.nodes["room_002"].properties["is_kitchen"] is True
        assert graph.nodes["room_003"].properties["is_kitchen"] is False

    def test_classify_living_spaces(self):
        graph = PlanGraph()
        graph.add_node(Node(id="room_001", node_type="room", name="Woonkamer"))
        graph.add_node(Node(id="room_002", node_type="room", name="Living room"))
        graph.add_node(Node(id="room_003", node_type="room", name="Keuken"))

        _classify_rooms(graph)

        assert graph.nodes["room_001"].properties["is_living"] is True
        assert graph.nodes["room_002"].properties["is_living"] is True
        assert graph.nodes["room_003"].properties["is_living"] is False

    def test_classify_sleeping_spaces(self):
        graph = PlanGraph()
        graph.add_node(Node(id="room_001", node_type="room", name="Slaapkamer"))
        graph.add_node(Node(id="room_002", node_type="room", name="Bedroom"))
        graph.add_node(Node(id="room_003", node_type="room", name="Woonkamer"))

        _classify_rooms(graph)

        assert graph.nodes["room_001"].properties["is_sleeping"] is True
        assert graph.nodes["room_002"].properties["is_sleeping"] is True
        assert graph.nodes["room_003"].properties["is_sleeping"] is False

    def test_classify_no_name(self):
        """Test classification of rooms without names."""
        graph = PlanGraph()
        graph.add_node(Node(id="room_001", node_type="room"))

        _classify_rooms(graph)

        assert graph.nodes["room_001"].properties["is_wet_room"] is False
        assert graph.nodes["room_001"].properties["is_kitchen"] is False


class TestConnectivityAnalysis:
    """Tests for connectivity analysis."""

    def test_analyze_single_room(self):
        """Test analyzing connectivity of a single room."""
        graph = PlanGraph()
        graph.add_node(Node(id="room_001", node_type="room"))

        analysis = analyze_connectivity(graph)

        assert analysis["total_rooms"] == 1
        assert analysis["total_connections"] == 0
        assert analysis["avg_connectivity"] == 0.0
        assert analysis["isolated_rooms"] == ["room_001"]

    def test_analyze_connected_rooms(self):
        """Test analyzing connected rooms."""
        graph = PlanGraph()
        graph.add_node(Node(id="room_001", node_type="room"))
        graph.add_node(Node(id="room_002", node_type="room"))
        graph.add_node(Node(id="room_003", node_type="room"))

        graph.add_edge(Edge(from_node="room_001", to_node="room_002", edge_type="door"))
        graph.add_edge(Edge(from_node="room_002", to_node="room_003", edge_type="door"))

        analysis = analyze_connectivity(graph)

        assert analysis["total_rooms"] == 3
        assert analysis["total_connections"] == 2
        assert "room_001" not in analysis["isolated_rooms"]

    def test_analyze_isolated_rooms(self):
        """Test identifying isolated rooms."""
        graph = PlanGraph()
        graph.add_node(Node(id="room_001", node_type="room"))
        graph.add_node(Node(id="room_002", node_type="room"))
        graph.add_node(Node(id="room_003", node_type="room"))

        # Only connect room 1 and 2
        graph.add_edge(Edge(from_node="room_001", to_node="room_002", edge_type="door"))

        analysis = analyze_connectivity(graph)

        assert "room_003" in analysis["isolated_rooms"]
        assert len(analysis["isolated_rooms"]) == 1

    def test_analyze_room_classifications(self):
        """Test analyzing classified rooms."""
        graph = PlanGraph()
        graph.add_node(Node(id="room_001", node_type="room", name="Woonkamer"))
        graph.add_node(Node(id="room_002", node_type="room", name="Keuken"))
        graph.add_node(Node(id="room_003", node_type="room", name="Bathroom"))

        _classify_rooms(graph)
        analysis = analyze_connectivity(graph)

        # Both Keuken and Bathroom are classified as wet_rooms
        assert analysis["wet_rooms"] == 2
        assert analysis["living_spaces"] == 1
        assert analysis["sleeping_spaces"] == 0


class TestPathfinding:
    """Tests for pathfinding between rooms."""

    def test_path_direct_connection(self):
        """Test finding path between directly connected rooms."""
        graph = PlanGraph()
        graph.add_node(Node(id="room_001", node_type="room"))
        graph.add_node(Node(id="room_002", node_type="room"))

        graph.add_edge(Edge(
            from_node="room_001", to_node="room_002", edge_type="door"
        ))

        path = find_path_between_rooms(graph, "room_001", "room_002")

        assert path == ["room_001", "room_002"]

    def test_path_indirect_connection(self):
        """Test finding path through multiple rooms."""
        graph = PlanGraph()
        graph.add_node(Node(id="room_001", node_type="room"))
        graph.add_node(Node(id="room_002", node_type="room"))
        graph.add_node(Node(id="room_003", node_type="room"))

        graph.add_edge(Edge(from_node="room_001", to_node="room_002", edge_type="door"))
        graph.add_edge(Edge(from_node="room_002", to_node="room_003", edge_type="door"))

        path = find_path_between_rooms(graph, "room_001", "room_003")

        assert path == ["room_001", "room_002", "room_003"]

    def test_path_no_connection(self):
        """Test when no path exists."""
        graph = PlanGraph()
        graph.add_node(Node(id="room_001", node_type="room"))
        graph.add_node(Node(id="room_002", node_type="room"))
        graph.add_node(Node(id="room_003", node_type="room"))

        graph.add_edge(Edge(from_node="room_001", to_node="room_002", edge_type="door"))

        path = find_path_between_rooms(graph, "room_001", "room_003")

        assert path is None

    def test_path_unknown_room(self):
        """Test pathfinding with unknown room IDs."""
        graph = PlanGraph()
        graph.add_node(Node(id="room_001", node_type="room"))
        graph.add_node(Node(id="room_002", node_type="room"))

        graph.add_edge(Edge(from_node="room_001", to_node="room_002", edge_type="door"))

        # From room doesn't exist
        path = find_path_between_rooms(graph, "room_999", "room_001")
        assert path is None

        # To room doesn't exist
        path = find_path_between_rooms(graph, "room_001", "room_999")
        assert path is None

    def test_path_unidirectional_edge(self):
        """Test pathfinding with unidirectional edges."""
        graph = PlanGraph()
        graph.add_node(Node(id="room_001", node_type="room"))
        graph.add_node(Node(id="room_002", node_type="room"))

        # Unidirectional edge
        graph.add_edge(Edge(
            from_node="room_001",
            to_node="room_002",
            edge_type="door",
            bidirectional=False,
        ))

        # Should find path from room_001 to room_002
        path = find_path_between_rooms(graph, "room_001", "room_002")
        assert path == ["room_001", "room_002"]

        # Should not find path from room_002 to room_001
        path = find_path_between_rooms(graph, "room_002", "room_001")
        assert path is None


class TestClusterIdentification:
    """Tests for cluster identification."""

    def test_identify_single_cluster(self):
        """Test identifying connected components."""
        graph = PlanGraph()
        graph.add_node(Node(id="room_001", node_type="room"))
        graph.add_node(Node(id="room_002", node_type="room"))
        graph.add_node(Node(id="room_003", node_type="room"))

        graph.add_edge(Edge(from_node="room_001", to_node="room_002", edge_type="door"))
        graph.add_edge(Edge(from_node="room_002", to_node="room_003", edge_type="door"))

        clusters = identify_clusters(graph)

        assert len(clusters) == 1
        assert clusters[0] == {"room_001", "room_002", "room_003"}

    def test_identify_multiple_clusters(self):
        """Test identifying multiple disconnected clusters."""
        graph = PlanGraph()
        graph.add_node(Node(id="room_001", node_type="room"))
        graph.add_node(Node(id="room_002", node_type="room"))
        graph.add_node(Node(id="room_003", node_type="room"))
        graph.add_node(Node(id="room_004", node_type="room"))

        # Cluster 1: room_001 <-> room_002
        graph.add_edge(Edge(from_node="room_001", to_node="room_002", edge_type="door"))

        # Cluster 2: room_003 <-> room_004
        graph.add_edge(Edge(from_node="room_003", to_node="room_004", edge_type="door"))

        clusters = identify_clusters(graph)

        assert len(clusters) == 2
        assert {"room_001", "room_002"} in clusters
        assert {"room_003", "room_004"} in clusters

    def test_identify_isolated_rooms_as_clusters(self):
        """Test that isolated rooms form single-room clusters."""
        graph = PlanGraph()
        graph.add_node(Node(id="room_001", node_type="room"))
        graph.add_node(Node(id="room_002", node_type="room"))

        # No edges, both rooms isolated

        clusters = identify_clusters(graph)

        assert len(clusters) == 2
        assert {"room_001"} in clusters
        assert {"room_002"} in clusters

    def test_identify_clusters_complex_topology(self):
        """Test cluster identification on complex topology."""
        graph = PlanGraph()
        # Cluster 1: star topology
        for i in range(2, 5):
            graph.add_node(Node(id=f"room_{i:03d}", node_type="room"))
        graph.add_node(Node(id="room_001", node_type="room"))

        graph.add_edge(Edge(from_node="room_001", to_node="room_002", edge_type="door"))
        graph.add_edge(Edge(from_node="room_001", to_node="room_003", edge_type="door"))
        graph.add_edge(Edge(from_node="room_001", to_node="room_004", edge_type="door"))

        clusters = identify_clusters(graph)

        assert len(clusters) == 1
        assert clusters[0] == {"room_001", "room_002", "room_003", "room_004"}


class TestBuildRoomGraph:
    """Tests for building room graphs from raw data."""

    def test_build_simple_graph(self):
        """Test building a simple room graph."""
        rooms = [
            {"id": "room_001", "name": "Woonkamer", "area_m2": 25.5},
            {"id": "room_002", "name": "Keuken", "area_m2": 12.0},
        ]
        plan = {"features": []}

        graph = build_room_graph(rooms, plan)

        assert len(graph.nodes) == 2
        assert "room_001" in graph.nodes
        assert "room_002" in graph.nodes

    def test_build_graph_with_doors(self):
        """Test building graph with door connections."""
        rooms = [
            {"id": "room_001", "name": "Woonkamer", "area_m2": 25.5},
            {"id": "room_002", "name": "Keuken", "area_m2": 12.0},
        ]
        plan = {
            "features": [
                {
                    "label": "symbol",
                    "metadata": {"symbol_type": "door"},
                }
            ]
        }

        graph = build_room_graph(rooms, plan)

        assert len(graph.edges) > 0

    def test_build_graph_empty_rooms(self):
        """Test building graph with no rooms."""
        graph = build_room_graph([], {"features": []})

        assert len(graph.nodes) == 0
        assert len(graph.edges) == 0
