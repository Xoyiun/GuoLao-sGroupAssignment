"""F9 校園移動路徑規劃模組 (Campus Path Planner)。

本副程式負責校園建築與節點間的最短移動路徑計算 (Dijkstra / BFS)：
- 計算兩節點間的最短步行距離與預估時間

介面規範：
- 輸入參數皆有明確之型別與規格。
- 回傳值一律為狀態與錯誤代碼 (ok, code, ...)，不回傳介面顯示文字。
"""

import heapq
from Constants import INVALID_LOCATION, NO_PATH_FOUND, OK


def FindShortestPath(campusGraph: dict, startNode: str, endNode: str,
                       algorithm: str = "dijkstra") -> tuple[bool, str, dict]:
    """計算校園兩建築/節點間之最短移動路徑與預估步行時間。

    輸入：
        campus_graph: 校園圖字典 {"nodes": [...], "edges": [...]}
        start_node: 起點節點代號 (例如 "TR")
        end_node: 終點節點代號 (例如 "IB")
        algorithm: 演算法選擇 ("dijkstra" 或 "bfs")
    回傳：
        (ok, code, path_info):
        - 成功：(True, OK, {
            "path": [start, ..., end],
            "total_distance": float,
            "estimated_minutes": float
          })
        - 節點不存在：(False, INVALID_LOCATION, {})
        - 無可行路徑：(False, NO_PATH_FOUND, {})
    """
    if not isinstance(campusGraph, dict):
        return False, INVALID_LOCATION, {}

    nodes = {node.get("node_id") for node in campusGraph.get("nodes", []) if isinstance(node, dict)}
    if startNode not in nodes or endNode not in nodes:
        return False, INVALID_LOCATION, {}

    if startNode == endNode:
        return True, OK, {"path": [startNode], "total_distance": 0.0, "estimated_minutes": 0.0}

    adjacencyList = {node: [] for node in nodes}
    for edge in campusGraph.get("edges", []):
        sourceNode, destinationNode = edge.get("from"), edge.get("to")
        edgeWeight = float(edge.get("weight", edge.get("distance", 1.0)))
        if sourceNode in adjacencyList and destinationNode in adjacencyList:
            adjacencyList[sourceNode].append((destinationNode, edgeWeight))
            adjacencyList[destinationNode].append((sourceNode, edgeWeight))

    distances = {node: float("inf") for node in nodes}
    previousNodes = {node: None for node in nodes}
    distances[startNode] = 0.0
    priorityQueue = [(0.0, startNode)]

    while priorityQueue:
        currentDistance, currentNode = heapq.heappop(priorityQueue)
        if currentDistance > distances[currentNode]:
            continue
        if currentNode == endNode:
            break
        for nextNode, weight in adjacencyList.get(currentNode, []):
            if distances[currentNode] + weight < distances[nextNode]:
                distances[nextNode] = distances[currentNode] + weight
                previousNodes[nextNode] = currentNode
                heapq.heappush(priorityQueue, (distances[nextNode], nextNode))

    if distances[endNode] == float("inf"):
        return False, NO_PATH_FOUND, {}

    currentNode = endNode
    path = []
    while currentNode:
        path.append(currentNode)
        currentNode = previousNodes[currentNode]
    path.reverse()

    return True, OK, {
        "path": path,
        "total_distance": distances[endNode],
        "estimated_minutes": round(distances[endNode] / 80.0, 1),
    }
