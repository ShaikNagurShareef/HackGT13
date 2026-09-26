"""A tiny in-memory stand-in for pymongo's AsyncCollection.

It implements only the operators the reports and shared-walks repositories use ($inc/$set/
$setOnInsert upserts, insert_one/find_one, $in/$gt/$geoWithin filters, and a $match/$group/$sort
pipeline) and records every call so
tests can assert query shapes. Set `fail` to an exception to simulate Atlas being down.
"""

from __future__ import annotations

import copy
from typing import Any

from pymongo import IndexModel


def _in_polygon(point: list[float], polygon: dict[str, Any]) -> bool:
    ring = polygon["coordinates"][0]
    lons = [p[0] for p in ring]
    lats = [p[1] for p in ring]
    return min(lons) <= point[0] <= max(lons) and min(lats) <= point[1] <= max(lats)


def _matches_op(value: Any, op: str, arg: Any) -> bool:
    if op == "$in":
        return value in arg
    if op == "$gt":
        return value is not None and value > arg
    if op == "$geoWithin":
        return value is not None and _in_polygon(value["coordinates"], arg["$geometry"])
    raise NotImplementedError(op)


def matches(doc: dict[str, Any], query: dict[str, Any]) -> bool:
    for field, cond in query.items():
        value = doc.get(field)
        if isinstance(cond, dict) and all(k.startswith("$") for k in cond):
            if not all(_matches_op(value, op, arg) for op, arg in cond.items()):
                return False
        elif value != cond:
            return False
    return True


def _project(doc: dict[str, Any]) -> dict[str, Any]:
    return {k: copy.deepcopy(v) for k, v in doc.items() if k != "_id"}


class FakeCursor:
    def __init__(
        self, owner: FakeCollection, docs: list[dict[str, Any]], *, drop_id: bool = True
    ) -> None:
        self._owner = owner
        self._docs = docs
        self._drop_id = drop_id
        self.sort_spec: tuple[str, int] | None = None
        self.limit_n: int | None = None

    def sort(self, key: str, direction: int = 1) -> FakeCursor:
        self.sort_spec = (key, direction)
        self._owner.cursors.append(self)
        return self

    def limit(self, n: int) -> FakeCursor:
        self.limit_n = n
        return self

    async def to_list(self, length: int | None = None) -> list[dict[str, Any]]:
        self._owner.check()
        docs = list(self._docs)
        if self.sort_spec:
            key, direction = self.sort_spec
            docs.sort(key=lambda d: d.get(key, 0), reverse=direction < 0)
        if self.limit_n:
            docs = docs[: self.limit_n]
        return [_project(d) if self._drop_id else copy.deepcopy(d) for d in docs]


class FakeDatabase:
    def __init__(self, owner: FakeCollection) -> None:
        self._owner = owner

    async def command(self, name: str) -> dict[str, Any]:
        self._owner.check()
        return {"ok": 1.0}


class FakeCollection:
    def __init__(self) -> None:
        self.docs: list[dict[str, Any]] = []
        self.calls: list[tuple[str, Any]] = []
        self.cursors: list[FakeCursor] = []
        self.indexes: dict[str, dict[str, Any]] = {}
        self.fail: Exception | None = None
        self.fail_once: Exception | None = None
        self.database = FakeDatabase(self)

    def check(self) -> None:
        if self.fail_once is not None:
            exc, self.fail_once = self.fail_once, None
            raise exc
        if self.fail is not None:
            raise self.fail

    async def find_one_and_update(
        self,
        query: dict[str, Any],
        update: dict[str, Any],
        *,
        upsert: bool = False,
        return_document: bool = False,
        projection: dict[str, int] | None = None,
    ) -> dict[str, Any] | None:
        self.calls.append(("find_one_and_update", (query, update, upsert)))
        self.check()
        doc = next((d for d in self.docs if matches(d, query)), None)
        if doc is None:
            if not upsert:
                return None
            doc = {"_id": len(self.docs) + 1, **query, **update.get("$setOnInsert", {})}
            self.docs.append(doc)
        doc.update(update.get("$set", {}))
        for field, step in update.get("$inc", {}).items():
            doc[field] = doc.get(field, 0) + step
        return _project(doc)

    async def insert_one(self, doc: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(("insert_one", doc))
        self.check()
        stored = {"_id": len(self.docs) + 1, **copy.deepcopy(doc)}
        self.docs.append(stored)
        return {"inserted_id": stored["_id"]}

    async def find_one(
        self, query: dict[str, Any], projection: dict[str, int] | None = None
    ) -> dict[str, Any] | None:
        self.calls.append(("find_one", query))
        self.check()
        doc = next((d for d in self.docs if matches(d, query)), None)
        return _project(doc) if doc is not None else None

    def find(self, query: dict[str, Any], projection: dict[str, int] | None = None) -> FakeCursor:
        self.calls.append(("find", query))
        return FakeCursor(self, [d for d in self.docs if matches(d, query)])

    async def aggregate(self, pipeline: list[dict[str, Any]]) -> FakeCursor:
        self.calls.append(("aggregate", pipeline))
        self.check()
        rows = [d for d in self.docs]
        cursor = FakeCursor(self, rows, drop_id=False)
        for stage in pipeline:
            if "$match" in stage:
                rows = [d for d in rows if matches(d, stage["$match"])]
            elif "$group" in stage:
                rows = _group(rows, stage["$group"])
            elif "$sort" in stage:
                for key, direction in reversed(list(stage["$sort"].items())):
                    rows.sort(key=lambda d, k=key: d[k], reverse=direction < 0)
        cursor._docs = rows
        return cursor

    async def create_indexes(self, models: list[IndexModel]) -> list[str]:
        self.check()
        for model in models:
            spec = dict(model.document)
            self.indexes[spec["name"]] = spec
        return list(self.indexes)

    async def index_information(self) -> dict[str, dict[str, Any]]:
        self.check()
        return {"_id_": {"key": [("_id", 1)]}, **self.indexes}


def _group(rows: list[dict[str, Any]], spec: dict[str, Any]) -> list[dict[str, Any]]:
    key_field = spec["_id"].lstrip("$")
    out: dict[Any, dict[str, Any]] = {}
    for row in rows:
        key = row.get(key_field)
        acc = out.setdefault(key, {"_id": key, **{f: 0 for f in spec if f != "_id"}})
        for field, op in spec.items():
            if field == "_id":
                continue
            arg = op["$sum"]
            acc[field] += arg if isinstance(arg, int) else row.get(arg.lstrip("$"), 0)
    return list(out.values())
