"""
Dependency Resolver
===================

Topological sorting for feature dependencies using Kahn's algorithm.
Handles cycle detection and provides intelligent ordering based on
dependencies and priority.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional, Protocol, TypeVar, Generic


class DependencyCycleError(Exception):
    """Raised when a dependency cycle is detected."""

    def __init__(self, cycle: list[int]):
        self.cycle = cycle
        super().__init__(f"Dependency cycle detected: {' → '.join(map(str, cycle))}")


class FeatureProtocol(Protocol):
    """Protocol for feature objects that can be dependency-sorted."""
    id: int
    priority: int
    passes: bool
    in_progress: bool
    dependencies: Optional[list[int]]


T = TypeVar("T", bound=FeatureProtocol)


@dataclass
class DependencyResolver(Generic[T]):
    """
    Resolves feature dependencies using topological sorting.

    Supports:
    - Dependency ordering (features with dependencies come after their deps)
    - Priority ordering (lower priority number = higher importance)
    - Cycle detection with clear error messages
    - Skipping completed/in-progress features
    """

    features: dict[int, T] = field(default_factory=dict)
    _graph: dict[int, list[int]] = field(default_factory=lambda: defaultdict(list))
    _reverse_graph: dict[int, list[int]] = field(default_factory=lambda: defaultdict(list))
    _in_degree: dict[int, int] = field(default_factory=lambda: defaultdict(int))

    def __init__(self, features: list[T]):
        """
        Initialize resolver with list of features.

        Args:
            features: List of feature objects with id, priority, dependencies
        """
        self.features = {f.id: f for f in features}
        self._graph = defaultdict(list)
        self._reverse_graph = defaultdict(list)
        self._in_degree = defaultdict(int)
        self._build_graph()

    def _build_graph(self) -> None:
        """Build dependency graph from features."""
        # Initialize all features with zero in-degree
        for fid in self.features:
            self._in_degree[fid] = 0

        # Build adjacency lists
        for fid, feature in self.features.items():
            deps = getattr(feature, "dependencies", None) or []
            for dep_id in deps:
                if dep_id in self.features:
                    # dep_id → fid (feature depends on dep)
                    self._graph[dep_id].append(fid)
                    self._reverse_graph[fid].append(dep_id)
                    self._in_degree[fid] += 1

    def get_sorted_features(self) -> list[T]:
        """
        Get all features in dependency order.

        Returns:
            List of features sorted by: dependencies first, then priority

        Raises:
            DependencyCycleError: If a dependency cycle is detected
        """
        # Kahn's algorithm
        result = []
        in_degree = dict(self._in_degree)

        # Start with features that have no dependencies
        queue = []
        for fid, degree in in_degree.items():
            if degree == 0:
                queue.append(fid)

        # Sort by priority (lower = higher importance)
        queue.sort(key=lambda fid: self.features[fid].priority)

        while queue:
            # Take feature with highest priority (lowest number)
            fid = queue.pop(0)
            result.append(self.features[fid])

            # Reduce in-degree of dependent features
            for dependent_id in self._graph[fid]:
                in_degree[dependent_id] -= 1
                if in_degree[dependent_id] == 0:
                    queue.append(dependent_id)
                    # Re-sort to maintain priority order
                    queue.sort(key=lambda x: self.features[x].priority)

        # Check for cycles (features not in result have cycles)
        if len(result) != len(self.features):
            cycle = self._find_cycle()
            raise DependencyCycleError(cycle)

        return result

    def _find_cycle(self) -> list[int]:
        """Find a cycle in the graph using DFS."""
        visited = set()
        rec_stack = set()
        path = []

        def dfs(node: int) -> Optional[list[int]]:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in self._graph[node]:
                if neighbor not in visited:
                    result = dfs(neighbor)
                    if result:
                        return result
                elif neighbor in rec_stack:
                    # Found cycle
                    cycle_start = path.index(neighbor)
                    return path[cycle_start:] + [neighbor]

            path.pop()
            rec_stack.remove(node)
            return None

        for node in self.features:
            if node not in visited:
                cycle = dfs(node)
                if cycle:
                    return cycle

        return []

    def get_next_ready(
        self,
        completed: Optional[set[int]] = None,
        in_progress: Optional[set[int]] = None,
    ) -> Optional[T]:
        """
        Get next feature that is ready to work on.

        A feature is ready if:
        - It's not completed (passes=True)
        - It's not in progress
        - All its dependencies are completed

        Args:
            completed: Set of completed feature IDs (overrides feature.passes)
            in_progress: Set of in-progress feature IDs (overrides feature.in_progress)

        Returns:
            Next ready feature or None if no features are ready
        """
        if completed is None:
            completed = {fid for fid, f in self.features.items() if f.passes}
        if in_progress is None:
            in_progress = {fid for fid, f in self.features.items() if f.in_progress}

        # Get sorted features
        try:
            sorted_features = self.get_sorted_features()
        except DependencyCycleError:
            # If there's a cycle, fall back to priority-only sorting
            sorted_features = sorted(
                self.features.values(),
                key=lambda f: f.priority
            )

        for feature in sorted_features:
            # Skip completed or in-progress
            if feature.id in completed or feature.id in in_progress:
                continue

            # Check dependencies
            deps = getattr(feature, "dependencies", None) or []
            if all(dep_id in completed for dep_id in deps if dep_id in self.features):
                return feature

        return None

    def get_blocking_dependencies(self, feature_id: int) -> list[T]:
        """
        Get features that are blocking a given feature.

        Args:
            feature_id: The feature to check

        Returns:
            List of incomplete features that this feature depends on
        """
        if feature_id not in self.features:
            return []

        feature = self.features[feature_id]
        deps = getattr(feature, "dependencies", None) or []

        blocking = []
        for dep_id in deps:
            if dep_id in self.features:
                dep_feature = self.features[dep_id]
                if not dep_feature.passes:
                    blocking.append(dep_feature)

        return blocking

    def are_dependencies_satisfied(self, feature_id: int) -> bool:
        """
        Check if all dependencies for a feature are satisfied (completed).

        Args:
            feature_id: The feature to check

        Returns:
            True if all dependencies are completed
        """
        return len(self.get_blocking_dependencies(feature_id)) == 0

    def get_dependents(self, feature_id: int) -> list[T]:
        """
        Get features that depend on a given feature.

        Args:
            feature_id: The feature to check

        Returns:
            List of features that depend on this feature
        """
        if feature_id not in self.features:
            return []

        return [self.features[fid] for fid in self._graph[feature_id]]

    def detect_cycles(self) -> list[list[int]]:
        """
        Detect all cycles in the dependency graph.

        Returns:
            List of cycles (each cycle is a list of feature IDs)
        """
        cycles = []
        visited = set()
        rec_stack = set()

        def dfs(node: int, path: list[int]) -> None:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in self._graph[node]:
                if neighbor not in visited:
                    dfs(neighbor, path)
                elif neighbor in rec_stack:
                    # Found cycle
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    if cycle not in cycles:
                        cycles.append(cycle)

            path.pop()
            rec_stack.remove(node)

        for node in self.features:
            if node not in visited:
                dfs(node, [])

        return cycles
