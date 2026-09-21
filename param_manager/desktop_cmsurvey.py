"""New Commonality investigation — plan preflight.

Given a Lot plan supplied as structured rows (never a file path) and a machine
whose Scanresult root is already configured (config `commonality_roots`, the same
per-machine roots the tkinter Commonality tab stores), resolve which lot folders
actually exist under that root and report found / missing / variants. This is the
gating step the tkinter flow performs before any safe copy. Reads are read-only
traversal of the configured root; the UI supplies no paths.

Safe copy → parse → collate → result (the heavy execution) is a separate, larger
increment; this adapter stops at resolution so it stays offline and testable.
"""
from pathlib import Path

from . import commonality as cm
from .desktop_batch import read_json

MAX_PLAN_ROWS = 500
PLAN_KEYS = {"디바이스명", "공정번호", "S/M", "AOI호기", "fail여부"}


class DesktopCmSurvey:
    def __init__(self, config_path=None):
        self.config_path = Path(config_path) if config_path else Path.home() / ".pi_param_manager.json"

    def _roots(self):
        cfg = read_json(self.config_path)
        roots = cfg.get("commonality_roots") or {}
        if not isinstance(roots, dict):
            raise ValueError("Commonality 루트 설정을 확인하세요")
        return {m: r for m, r in roots.items() if isinstance(m, str) and isinstance(r, str) and r.strip()}

    def config(self):
        roots = self._roots()
        return dict(machines=[dict(id=m, root=r) for m, r in sorted(roots.items())])

    def _validate_plan(self, plan):
        if not isinstance(plan, list) or not 1 <= len(plan) <= MAX_PLAN_ROWS:
            raise ValueError("조사 계획 행을 1개 이상 입력하세요")
        rows = []
        for item in plan:
            if not isinstance(item, dict) or set(item) - PLAN_KEYS:
                raise ValueError("계획 행 항목을 확인하세요")
            row = {}
            for key in PLAN_KEYS:
                value = item.get(key, "")
                if not isinstance(value, str) or len(value) > 256:
                    raise ValueError("계획 값(디바이스/공정/S·M/호기)을 확인하세요")
                row[key] = value.strip()
            if not row["디바이스명"] or not row["공정번호"] or not row["S/M"]:
                raise ValueError("디바이스명·공정번호·S/M 은 필수입니다")
            rows.append(row)
        return rows

    def preflight(self, params):
        if set(params) - {"machine", "plan"}:
            raise ValueError("호기와 계획을 확인하세요")
        machine = params.get("machine")
        roots = self._roots()
        if not isinstance(machine, str) or machine not in roots:
            raise ValueError("Scanresult 루트가 설정된 호기를 선택하세요")
        plan = self._validate_plan(params.get("plan"))
        mine = cm.filter_plan_for_machine(plan, machine)
        if not mine:
            raise ValueError("이 호기에 해당하는 계획 행이 없습니다. AOI호기를 확인하세요.")
        scan_roots = cm.scanresult_roots(roots[machine], machine)
        lots = cm.resolve_plan(scan_roots, mine)
        rows = [dict(label=l.label, device=l.device, lot=l.lot, sm=l.sm,
                     exists=bool(l.exists), fail=bool(l.fail),
                     scan_time=l.scan_time, created=l.created,
                     wafer=(l.wafer_dir.name if l.wafer_dir is not None else ""),
                     reason=l.reason) for l in lots]
        return dict(machine=machine, roots=[str(r) for r in scan_roots],
                    total=len(rows), found=sum(1 for r in rows if r["exists"]),
                    missing=sum(1 for r in rows if not r["exists"]), rows=rows)
