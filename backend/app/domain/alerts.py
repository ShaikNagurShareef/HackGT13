"""Walk-mode alerts (VOX-02, EC-45) and avoided hotspots (RTE-06) from a measured route."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.route_metrics import UNNAMED, EdgeStep

SPOKEN_UNNAMED = "a side street"

ALERT_SCORE = 90
MERGE_WITHIN_M = 100.0
AVOID_SCORE = 75


@dataclass(frozen=True)
class Alert:
    start_m: float
    end_m: float
    names: tuple[str, ...]
    score: int
    stretches: int


def walk_alerts(steps: tuple[EdgeStep, ...], names: list[str]) -> list[Alert]:
    """Contiguous stretches scoring >= ALERT_SCORE, merged when they start within 100 m."""
    raw: list[Alert] = []
    walked = 0.0
    for step in steps:
        hot = step.seg_id >= 0 and step.score >= ALERT_SCORE
        if hot:
            name = names[step.seg_id]
            name = SPOKEN_UNNAMED if name == UNNAMED else name
            prev = raw[-1] if raw else None
            if prev and walked - prev.end_m < 1.0 and name in prev.names:
                raw[-1] = Alert(
                    prev.start_m,
                    walked + step.length_m,
                    prev.names,
                    max(prev.score, round(step.score)),
                    prev.stretches,
                )
            else:
                raw.append(Alert(walked, walked + step.length_m, (name,), round(step.score), 1))
        walked += step.length_m
    return _merge_close(raw)


def _merge_close(alerts: list[Alert]) -> list[Alert]:
    merged: list[Alert] = []
    for alert in alerts:
        prev = merged[-1] if merged else None
        if prev and alert.start_m - prev.end_m <= MERGE_WITHIN_M:
            names = prev.names + tuple(n for n in alert.names if n not in prev.names)
            merged[-1] = Alert(
                prev.start_m,
                alert.end_m,
                names,
                max(prev.score, alert.score),
                prev.stretches + alert.stretches,
            )
        else:
            merged.append(alert)
    return merged


def avoided_segments(
    fastest: tuple[EdgeStep, ...], chosen: tuple[EdgeStep, ...], names: list[str]
) -> list[int]:
    """High-risk streets on the fastest route that the PathPro route avoids entirely.

    One entry per street name (its riskiest segment), in walking order.
    """
    used_names = {names[s.seg_id] for s in chosen if s.seg_id >= 0}
    best: dict[str, EdgeStep] = {}
    for s in fastest:
        if s.seg_id < 0 or s.score < AVOID_SCORE:
            continue
        name = names[s.seg_id]
        if name in used_names or name == UNNAMED:
            continue
        if name not in best or s.score > best[name].score:
            best[name] = s
    return [s.seg_id for s in best.values()]
