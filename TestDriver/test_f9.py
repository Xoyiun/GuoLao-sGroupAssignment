import pytest

import CampusPath as campusPath
from Constants import INVALID_LOCATION, NO_PATH_FOUND, OK

pytestmark = pytest.mark.f9


@pytest.fixture
def graph():
    return {
        "nodes": [{"node_id": "A"}, {"node_id": "B"}, {"node_id": "C"}, {"node_id": "D"}],
        "edges": [
            {"from": "A", "to": "B", "weight": 100},
            {"from": "B", "to": "C", "weight": 80},
            {"from": "A", "to": "C", "weight": 300},
        ],
    }


def test_dijkstra_find_shortest_weighted_path(graph):
    ok, code, info = campusPath.FindShortestPath(graph, "A", "C")
    assert (ok, code) == (True, OK)
    assert info["path"] == ["A", "B", "C"]
    assert info["total_distance"] == 180


def test_bfs_is_supported(graph):
    ok, code, info = campusPath.FindShortestPath(graph, "A", "C", "bfs")
    assert (ok, code) == (True, OK)
    assert info["path"] == ["A", "C"]


def test_unknown_location_and_no_path():
    graph = {"nodes": [{"node_id": "A"}], "edges": []}
    assert campusPath.FindShortestPath(graph, "A", "Z")[1] == INVALID_LOCATION
    graph["nodes"].append({"node_id": "B"})
    assert campusPath.FindShortestPath(graph, "A", "B")[1] == NO_PATH_FOUND
