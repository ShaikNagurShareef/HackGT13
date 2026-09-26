"""Fastest vs lower-risk walking routes on the pedestrian graph (PRD RTE-01..03, EC-10..13).

Candidates come from Dijkstra with cost = time * (1 + lambda * density / density_at_score_75)
over a fixed lambda ladder. Density (not the 0-100 score) drives cost because risk is heavy-
tailed: a 99th-percentile street is ~14x denser than a 75th-percentile one, a gap the score
compresses. Each candidate is re-scored at its true traversal times, and the one with the
lowest exposure (expected crashes along the path) within the detour budget wins.

Optional "lit_and_busy" preference (after dark only): the same ladder is re-run with each
edge's time also multiplied by a lighting / foot-traffic penalty (domain/safety.py), and
the candidate with the least unlit-or-quiet length wins, under the same detour budget and
without adding more than 10% traffic exposure over the fastest route. Reported crime is
never an input here.

The same router serves the ride network (bike / e-bike / scooter): a TravelProfile sets the
speed used for durations, the detour budget, and traversal-hour re-scoring.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree

from app.domain.route_metrics import RouteMetrics, measure_route
from app.domain.safety import EdgeSignals, day_part_at, is_after_dark, signal_penalty
from app.domain.timeutil import cell_at
from app.repositories.artifacts import Bundle

WALK_SPEED_MPS = 1.3
LAMBDA_LADDER = (0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 4.0)
DETOUR_RATIO, DETOUR_EXTRA_S = 1.25, 360.0
MIN_RISK_GAIN = 10
MIN_EXPOSURE_GAIN = 0.15
HIGH_SCORE_QUANTILE = 750
MIN_SEARCH_PAD_M = 1200.0
SEARCH_PAD_RATIO = 0.6  # index into the 1001-point quantile table
MIN_TRIP_M = 60.0
LONG_TRIP_M, LONG_TRIP_S = 5000.0, 3600.0
M_PER_DEG = 111_320.0
DEFAULT_PREFERENCE, LIT_AND_BUSY = "lower_traffic_risk", "lit_and_busy"
MIN_SIGNAL_GAIN = 0.15  # the lit route must cut unlit/quiet length by 15%...
MAX_EXTRA_EXPOSURE = 0.10  # ...without more than 10% extra traffic exposure


@dataclass(frozen=True)
class TravelProfile:
    speed_mps: float = WALK_SPEED_MPS
    long_trip_m: float = LONG_TRIP_M
    long_trip_s: float = LONG_TRIP_S


WALKING = TravelProfile()


class RoutingError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class RoutePlan:
    fastest: RouteMetrics
    pathpro: RouteMetrics | None
    message_code: str
    tradeoff_extra_s: float | None
    unavoidable: tuple[str, ...]


def away_log_density(bundle: Bundle) -> float:
    """Paths away from any road (campus quads, park trails) score at the citywide median."""
    return float(bundle.quantiles[500])


def _meaningfully_lower(fastest: RouteMetrics, best: RouteMetrics) -> bool:
    """PRD RTE-03 (amended): >= 10 score points OR >= 15% less exposure.

    Whole-route scores compress in dense areas where every street is top-quartile, so a
    relative exposure test is needed to surface real reductions there.
    """
    if best.nodes == fastest.nodes:
        return False
    score_gain = fastest.risk_score - best.risk_score >= MIN_RISK_GAIN
    exposure_gain = best.exposure <= fastest.exposure * (1 - MIN_EXPOSURE_GAIN)
    return score_gain or exposure_gain


def _is_long(fastest: RouteMetrics, profile: TravelProfile = WALKING) -> bool:
    return fastest.distance_m > profile.long_trip_m or fastest.duration_s > profile.long_trip_s


def _signal_length(route: RouteMetrics, penalty: np.ndarray) -> float:
    """Penalty-weighted metres of unlit or quiet street along a route."""
    return float(sum(s.length_m * (penalty[s.edge] - 1.0) for s in route.edges))


def choose_lit_plan(
    default: RoutePlan,
    candidates: list[RouteMetrics],
    penalty: np.ndarray,
    budget: float,
    profile: TravelProfile = WALKING,
) -> RoutePlan:
    """The lit-and-busy pick, or `default` unless it is meaningfully better lit or busier.

    Candidates must fit the detour budget and add at most 10% traffic exposure over the
    fastest route; the one with the least unlit-or-quiet length wins, and it must cut that
    length by 15% against the route the default plan would show.
    """
    fastest = default.fastest
    shown = default.pathpro or fastest
    cap = fastest.exposure * (1 + MAX_EXTRA_EXPOSURE)
    ok = [c for c in candidates if c.duration_s <= budget + 1e-6 and c.exposure <= cap]
    best = min(
        ok, key=lambda c: (_signal_length(c, penalty), c.exposure, c.duration_s), default=None
    )
    if best is None or best.nodes in (fastest.nodes, shown.nodes):
        return default
    base = _signal_length(shown, penalty)
    if base <= 0 or _signal_length(best, penalty) > base * (1 - MIN_SIGNAL_GAIN):
        return default
    unavoidable = tuple(sorted(fastest.high_risk_names & best.high_risk_names))
    code = "long_trip" if _is_long(fastest, profile) else "ok"
    return RoutePlan(fastest, best, code, None, unavoidable)


def _node_pairs(src: np.ndarray, dst: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Per directed edge: an id for its (src, dst) pair, and whether that pair has parallels."""
    order = np.lexsort((dst, src))
    s, d = src[order], dst[order]
    starts = np.ones(len(order), bool)
    starts[1:] = (s[1:] != s[:-1]) | (d[1:] != d[:-1])
    pair = np.empty(len(order), np.int64)
    pair[order] = np.cumsum(starts) - 1
    return pair, np.bincount(pair)[pair] > 1


class Router:
    PREFERENCES = (DEFAULT_PREFERENCE, LIT_AND_BUSY)

    def __init__(self, bundle: Bundle, signals: EdgeSignals | None = None) -> None:
        g = bundle.graph
        self.bundle = bundle
        self.signals = signals
        n_edges = len(g.edge_u)
        self.src = np.concatenate([g.edge_u, g.edge_v]).astype(np.int64)
        self.dst = np.concatenate([g.edge_v, g.edge_u]).astype(np.int64)
        self.edge_of = np.concatenate([np.arange(n_edges), np.arange(n_edges)])
        self.reversed = np.concatenate([np.zeros(n_edges, bool), np.ones(n_edges, bool)])
        self.length_m = np.concatenate([g.edge_len, g.edge_len]).astype(float)
        self.time_s = self.length_m / WALK_SPEED_MPS
        self.n_nodes = len(g.node_lon)
        self._pair, self._has_parallel = _node_pairs(self.src, self.dst)
        lat0 = float(np.mean(g.node_lat))
        self._kx = M_PER_DEG * np.cos(np.radians(lat0))
        self._tree = cKDTree(np.column_stack([g.node_lon * self._kx, g.node_lat * M_PER_DEG]))

    def snap(self, lon: float, lat: float) -> tuple[int, float]:
        dist, node = self._tree.query([lon * self._kx, lat * M_PER_DEG])
        return int(node), float(dist)

    def node_distance_m(self, a: int, b: int) -> float:
        pa, pb = self._tree.data[a], self._tree.data[b]
        return float(np.hypot(*(pa - pb)))

    def _search_area(self, origin: int, dest: int) -> np.ndarray:
        """Directed edges inside a padded box around the trip (citywide graphs stay fast).

        Any route within the 1.25x detour budget stays well inside this box.
        """
        xy = self._tree.data
        a, b = xy[origin], xy[dest]
        pad = max(MIN_SEARCH_PAD_M, SEARCH_PAD_RATIO * float(np.hypot(*(a - b))))
        lo, hi = np.minimum(a, b) - pad, np.maximum(a, b) + pad
        inside = np.all((xy >= lo) & (xy <= hi), axis=1)
        return inside[self.src] & inside[self.dst]

    def _cheapest_edges(self, cost: np.ndarray, area: np.ndarray | None) -> np.ndarray:
        """One directed edge per node pair: the cheapest of any parallel edges.

        Only the few pairs with parallel edges are sorted per call; ties keep the lower id.
        """
        inside = area if area is not None else np.ones(len(cost), bool)
        singles = np.flatnonzero(inside & ~self._has_parallel)
        multi = np.flatnonzero(inside & self._has_parallel)
        if len(multi) == 0:
            return singles
        ranked = multi[np.lexsort((cost[multi], self._pair[multi]))]
        pair = self._pair[ranked]
        first = np.ones(len(ranked), bool)
        first[1:] = pair[1:] != pair[:-1]
        return np.concatenate([singles, ranked[first]])

    def _shortest(
        self, origin: int, dest: int, cost: np.ndarray, area: np.ndarray | None = None
    ) -> list[int]:
        """Directed-edge ids of the cheapest path (parallel edges resolved by min cost)."""
        keep = self._cheapest_edges(cost, area)
        shape = (self.n_nodes, self.n_nodes)
        weights = csr_matrix((cost[keep] + 1e-9, (self.src[keep], self.dst[keep])), shape=shape)
        ids = csr_matrix((keep + 1, (self.src[keep], self.dst[keep])), shape=shape)
        _, pred = dijkstra(weights, indices=origin, return_predecessors=True)
        if pred[dest] < 0:
            raise RoutingError("NO_CONNECTION", "No connection found between these points.")
        nodes = [dest]
        while nodes[-1] != origin:
            nodes.append(int(pred[nodes[-1]]))
        nodes.reverse()
        edge_ids = np.asarray(ids[nodes[:-1], nodes[1:]]).ravel() - 1  # one vectorized lookup
        return [int(e) for e in edge_ids]

    def _relative_density(self, depart: datetime, wet: bool) -> np.ndarray:
        """Per directed edge: risk density at departure, relative to a score-75 street."""
        cell = cell_at(depart, wet)
        seg = self.bundle.graph.edge_seg[self.edge_of]
        log_d = np.full(len(seg), away_log_density(self.bundle))
        has = seg >= 0
        log_d[has] = self.bundle.log_density(seg[has], cell)
        return np.exp(log_d - self.bundle.quantiles[HIGH_SCORE_QUANTILE])

    def _measure(
        self,
        path: list[int],
        depart: datetime,
        wet: bool,
        time_s: np.ndarray,
        seen: dict[tuple[int, ...], RouteMetrics] | None = None,
    ) -> RouteMetrics:
        """Re-score a path at its traversal times; the lambda ladder often repeats paths."""
        key = tuple(path)
        if seen is not None and key in seen:
            return seen[key]
        metrics = measure_route(
            self.bundle, path, self.edge_of, self.reversed, time_s, self.dst, depart, wet
        )
        if seen is not None:
            seen[key] = metrics
        return metrics

    def plan(
        self,
        origin: int,
        dest: int,
        depart: datetime,
        wet: bool,
        prefer: str = DEFAULT_PREFERENCE,
        profile: TravelProfile = WALKING,
    ) -> RoutePlan:
        if origin == dest or self.node_distance_m(origin, dest) < MIN_TRIP_M:
            raise RoutingError("TOO_CLOSE", "You're already there — here's the risk on this block.")
        time_s = self.length_m / profile.speed_mps
        area = self._search_area(origin, dest)
        try:
            fast_path = self._shortest(origin, dest, time_s, area)
        except RoutingError:
            area = None  # the box cut the only connection; search everything
            fast_path = self._shortest(origin, dest, time_s)
        seen: dict[tuple[int, ...], RouteMetrics] = {}
        fastest = self._measure(fast_path, depart, wet, time_s, seen)
        budget = min(fastest.duration_s * DETOUR_RATIO, fastest.duration_s + DETOUR_EXTRA_S)
        density = self._relative_density(depart, wet)
        candidates = []
        for lam in LAMBDA_LADDER:
            path = self._shortest(origin, dest, time_s * (1 + lam * density), area)
            candidates.append(self._measure(path, depart, wet, time_s, seen))
        within = [c for c in candidates if c.duration_s <= budget + 1e-6]
        best = min(within, key=lambda c: (c.exposure, c.duration_s), default=fastest)
        overall = min(candidates, key=lambda c: (c.exposure, c.duration_s))
        default = self._decide(fastest, best, overall, profile)
        penalty = self._penalty(depart, prefer)
        if penalty is None:
            return default
        lit = self._lit_candidates(origin, dest, area, density, penalty, depart, wet, time_s)
        return choose_lit_plan(default, lit, penalty, budget, profile)

    def _penalty(self, depart: datetime, prefer: str) -> np.ndarray | None:
        """Per undirected edge penalty, only for the lit-and-busy preference after dark."""
        if prefer != LIT_AND_BUSY or self.signals is None or not is_after_dark(depart):
            return None
        return signal_penalty(self.signals, day_part_at(depart))

    def _lit_candidates(
        self,
        origin: int,
        dest: int,
        area: np.ndarray | None,
        density: np.ndarray,
        penalty: np.ndarray,
        depart: datetime,
        wet: bool,
        time_s: np.ndarray,
    ) -> list[RouteMetrics]:
        directed = penalty[self.edge_of]
        return [
            self._measure(
                self._shortest(origin, dest, time_s * (1 + lam * density) * directed, area),
                depart,
                wet,
                time_s,
            )
            for lam in (0.0, *LAMBDA_LADDER)
        ]

    def _decide(
        self,
        fastest: RouteMetrics,
        best: RouteMetrics,
        overall: RouteMetrics,
        profile: TravelProfile = WALKING,
    ) -> RoutePlan:
        long_trip = _is_long(fastest, profile)
        tradeoff = None
        if overall.exposure <= best.exposure * (1 - MIN_EXPOSURE_GAIN):
            tradeoff = overall.duration_s - fastest.duration_s
        unavoidable = tuple(sorted(fastest.high_risk_names & best.high_risk_names))
        if not _meaningfully_lower(fastest, best):
            code = "long_trip" if long_trip else "fastest_is_lower_risk"
            return RoutePlan(fastest, None, code, tradeoff, unavoidable)
        code = "long_trip" if long_trip else ("tradeoff_exists" if tradeoff else "ok")
        return RoutePlan(fastest, best, code, tradeoff, unavoidable)
