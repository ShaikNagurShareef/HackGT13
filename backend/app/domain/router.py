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


def _is_long(fastest: RouteMetrics) -> bool:
    return fastest.distance_m > LONG_TRIP_M or fastest.duration_s > LONG_TRIP_S


def _signal_length(route: RouteMetrics, penalty: np.ndarray) -> float:
    """Penalty-weighted metres of unlit or quiet street along a route."""
    return float(sum(s.length_m * (penalty[s.edge] - 1.0) for s in route.edges))


def choose_lit_plan(
    default: RoutePlan, candidates: list[RouteMetrics], penalty: np.ndarray, budget: float
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
    code = "long_trip" if _is_long(fastest) else "ok"
    return RoutePlan(fastest, best, code, None, unavoidable)


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
        self.time_s = np.concatenate([g.edge_len, g.edge_len]).astype(float) / WALK_SPEED_MPS
        self.n_nodes = len(g.node_lon)
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

    def _shortest(
        self, origin: int, dest: int, cost: np.ndarray, area: np.ndarray | None = None
    ) -> list[int]:
        """Directed-edge ids of the cheapest path (parallel edges resolved by min cost)."""
        candidates = np.flatnonzero(area) if area is not None else np.arange(len(cost))
        sub = np.lexsort((cost[candidates], self.dst[candidates], self.src[candidates]))
        order = candidates[sub]
        s, d = self.src[order], self.dst[order]
        first = np.ones(len(order), bool)
        first[1:] = (s[1:] != s[:-1]) | (d[1:] != d[:-1])
        keep = order[first]
        shape = (self.n_nodes, self.n_nodes)
        weights = csr_matrix((cost[keep] + 1e-9, (self.src[keep], self.dst[keep])), shape=shape)
        ids = csr_matrix((keep + 1, (self.src[keep], self.dst[keep])), shape=shape)
        _, pred = dijkstra(weights, indices=origin, return_predecessors=True)
        if pred[dest] < 0:
            raise RoutingError(
                "NO_CONNECTION", "No walkable connection found between these points."
            )
        path, node = [], dest
        while node != origin:
            prev = int(pred[node])
            path.append(int(ids[prev, node]) - 1)
            node = prev
        return path[::-1]

    def _relative_density(self, depart: datetime, wet: bool) -> np.ndarray:
        """Per directed edge: risk density at departure, relative to a score-75 street."""
        cell = cell_at(depart, wet)
        seg = self.bundle.graph.edge_seg[self.edge_of]
        log_d = np.full(len(seg), away_log_density(self.bundle))
        has = seg >= 0
        log_d[has] = self.bundle.log_density(seg[has], cell)
        return np.exp(log_d - self.bundle.quantiles[HIGH_SCORE_QUANTILE])

    def _measure(self, path: list[int], depart: datetime, wet: bool) -> RouteMetrics:
        return measure_route(
            self.bundle, path, self.edge_of, self.reversed, self.time_s, self.dst, depart, wet
        )

    def plan(
        self,
        origin: int,
        dest: int,
        depart: datetime,
        wet: bool,
        prefer: str = DEFAULT_PREFERENCE,
    ) -> RoutePlan:
        if origin == dest or self.node_distance_m(origin, dest) < MIN_TRIP_M:
            raise RoutingError("TOO_CLOSE", "You're already there — here's the risk on this block.")
        area = self._search_area(origin, dest)
        try:
            fast_path = self._shortest(origin, dest, self.time_s, area)
        except RoutingError:
            area = None  # the box cut the only connection; search everything
            fast_path = self._shortest(origin, dest, self.time_s)
        fastest = self._measure(fast_path, depart, wet)
        budget = min(fastest.duration_s * DETOUR_RATIO, fastest.duration_s + DETOUR_EXTRA_S)
        density = self._relative_density(depart, wet)
        candidates = []
        for lam in LAMBDA_LADDER:
            path = self._shortest(origin, dest, self.time_s * (1 + lam * density), area)
            candidates.append(self._measure(path, depart, wet))
        within = [c for c in candidates if c.duration_s <= budget + 1e-6]
        best = min(within, key=lambda c: (c.exposure, c.duration_s), default=fastest)
        overall = min(candidates, key=lambda c: (c.exposure, c.duration_s))
        default = self._decide(fastest, best, overall)
        penalty = self._penalty(depart, prefer)
        if penalty is None:
            return default
        lit = self._lit_candidates(origin, dest, area, density, penalty, depart, wet)
        return choose_lit_plan(default, lit, penalty, budget)

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
    ) -> list[RouteMetrics]:
        directed = penalty[self.edge_of]
        return [
            self._measure(
                self._shortest(origin, dest, self.time_s * (1 + lam * density) * directed, area),
                depart,
                wet,
            )
            for lam in (0.0, *LAMBDA_LADDER)
        ]

    def _decide(
        self, fastest: RouteMetrics, best: RouteMetrics, overall: RouteMetrics
    ) -> RoutePlan:
        long_trip = _is_long(fastest)
        tradeoff = None
        if overall.exposure <= best.exposure * (1 - MIN_EXPOSURE_GAIN):
            tradeoff = overall.duration_s - fastest.duration_s
        unavoidable = tuple(sorted(fastest.high_risk_names & best.high_risk_names))
        if not _meaningfully_lower(fastest, best):
            code = "long_trip" if long_trip else "fastest_is_lower_risk"
            return RoutePlan(fastest, None, code, tradeoff, unavoidable)
        code = "long_trip" if long_trip else ("tradeoff_exists" if tradeoff else "ok")
        return RoutePlan(fastest, best, code, tradeoff, unavoidable)
