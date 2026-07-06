"""공용 파일 값 갱신 — 미리보기(계획)와 적용을 분리.

rtp_parser.refresh_values 의 매칭 규칙을 계승하되,
  1) 소스를 피벗 행 목록으로 받아 파서(ini/RTP) 비의존
  2) 적용 전 변경 목록(diff)을 돌려줘 GUI 미리보기 가능
매칭 키 = (PI(레벨), Recipe(변형), norm(Zone), norm(Alg), norm(Parameter)).
빈 값은 덮어쓰지 않고, 매칭 실패 행은 건드리지 않는다(기존 정책 유지).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import engine
from .rtp_parser import norm_key


@dataclass
class Change:
    row_id: str
    pi: str          # 레시피 레벨
    recipe: str      # 변형
    zone: str
    alg: str
    param: str
    machine: str
    old: str
    new: str


@dataclass
class RefreshPlan:
    changes: list[Change] = field(default_factory=list)
    new_machines: list[str] = field(default_factory=list)
    matched_rows: int = 0
    unmatched_rows: int = 0
    folder_items: int = 0


def _row_key(pi, recipe, zone, alg, param) -> tuple:
    return (engine._s(pi), engine._s(recipe),
            norm_key(zone), norm_key(alg), norm_key(param))


def plan_refresh(repo, pivot_rows: list[dict], machines: list[str]) -> RefreshPlan:
    """적용 없이 변경 계획만 계산. pivot_rows 는 ini_parser/rtp_parser 의
    build_pivot 결과({recipe, mag, zone, alg, param, values{호기: 값}})."""
    idx = {}
    for r in pivot_rows:
        idx[_row_key(r["recipe"], r["mag"], r["zone"], r["alg"], r["param"])] = r

    plan = RefreshPlan(folder_items=len(idx))
    plan.new_machines = [m for m in machines if m and m not in repo.aoi_units]

    for pr in repo.rows:
        k = _row_key(pr.get("PI"), pr.get("Recipe"),
                     pr.get("Zone"), pr.get("Alg"), pr.get("Parameter"))
        r = idx.get(k)
        if not r:
            plan.unmatched_rows += 1
            continue
        plan.matched_rows += 1
        for m, v in r["values"].items():
            if not m or engine._s(v) == "":
                continue                     # 빈 값은 덮어쓰지 않음
            old = engine._s(pr.get(m)) if m in repo.aoi_units else ""
            if old != engine._s(v):
                plan.changes.append(Change(
                    row_id=pr.row_id, pi=engine._s(pr.get("PI")),
                    recipe=engine._s(pr.get("Recipe")), zone=engine._s(pr.get("Zone")),
                    alg=engine._s(pr.get("Alg")), param=engine._s(pr.get("Parameter")),
                    machine=m, old=old, new=engine._s(v)))
    return plan


def apply_refresh(repo, plan: RefreshPlan) -> dict:
    """계획을 repo(메모리)에 적용. 저장(save)·백업은 호출측 책임."""
    for m in plan.new_machines:
        if m not in repo.aoi_units:
            repo.aoi_units.append(m)
            for pr in repo.rows:
                pr.aoi_units = list(repo.aoi_units)
                pr.values.setdefault(m, None)
    by_id = {pr.row_id: pr for pr in repo.rows}
    rows_touched = set()
    for c in plan.changes:
        pr = by_id.get(c.row_id)
        if pr is None:
            continue
        pr.set(c.machine, c.new)
        rows_touched.add(c.row_id)
    return {"updated_rows": len(rows_touched), "updated_cells": len(plan.changes),
            "unmatched_rows": plan.unmatched_rows,
            "new_machines": list(plan.new_machines)}
