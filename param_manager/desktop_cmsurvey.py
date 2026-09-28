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
import os
from pathlib import Path

from . import commonality as cm, localdirs, workdirs
from .desktop_batch import DesktopBatch, read_json

MAX_PLAN_ROWS = 500
PLAN_KEYS = {"디바이스명", "공정번호", "S/M", "AOI호기", cm.ISSUE_KEY}
MAX_PLAN_FILE = 20 * 1024 * 1024


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

    # ---- plan Excel: new template / import ------------------------------------------
    def _plan_dir(self):
        root = str(DesktopBatch(self.config_path).configuration()[2])
        folder = os.path.join(localdirs.commonality_dir(localdirs.ensure(root)), "계획")
        os.makedirs(folder, exist_ok=True)
        return folder

    def plan_template(self, params):
        """새 Lot 계획 엑셀(현재 표의 행을 채워서, 없으면 빈 양식)을 로컬에 만든다."""
        if set(params) != {"rows"}:
            raise ValueError("계획 행을 확인하세요")
        rows = self._validate_plan(params["rows"], allow_empty=True)
        path = os.path.join(self._plan_dir(), f"Commonality_Lot계획_{workdirs.stamp()}.xlsx")
        cm.create_plan_template(path, rows)
        return dict(path=path, rows=len(rows))

    def read_plan(self, params):
        """사용자가 고른 Lot 계획 엑셀(.xlsx/.xlsm)을 읽는다(읽기 전용). 구 양식의
        'fail여부'·'생성일자' 열도 받아들인다('fail여부' → '이슈 Lot')."""
        if set(params) != {"path"} or not isinstance(params["path"], str) or not params["path"].strip():
            raise ValueError("계획 엑셀 파일을 고르세요")
        path = Path(params["path"].strip()).absolute()
        if path.suffix.lower() not in (".xlsx", ".xlsm") or not path.is_file():
            raise ValueError("엑셀(.xlsx) 계획 파일을 고르세요")
        if path.stat().st_size > MAX_PLAN_FILE:
            raise ValueError("계획 파일이 너무 큽니다")
        try:
            raw = cm.read_plan(str(path))
        except Exception as exc:  # noqa: BLE001 - a broken/foreign workbook
            raise ValueError(f"계획 엑셀을 읽지 못했습니다: {exc}") from exc
        if len(raw) > MAX_PLAN_ROWS:
            raise ValueError(f"계획 행이 너무 많습니다(최대 {MAX_PLAN_ROWS}행)")
        roots = self._roots()
        known = {cm._aoi_norm(m): m for m in roots}
        rows, unknown = [], []
        for r in raw:
            machine = (r.get("AOI호기") or "").strip()
            rows.append(dict(device=r.get("디바이스명", ""), process=r.get("공정번호", ""), sm=r.get("S/M", ""),
                             machine=machine, issue=cm.is_issue(r)))
            for m in _machines_in(machine):
                if cm._aoi_norm(m) not in known and m not in unknown:
                    unknown.append(m)
        return dict(path=str(path), rows=rows, unregistered=unknown)

    def _validate_plan(self, plan, allow_empty=False):
        if not isinstance(plan, list) or not (0 if allow_empty else 1) <= len(plan) <= MAX_PLAN_ROWS:
            raise ValueError("조사 계획 행을 1개 이상 입력하세요")
        rows = []
        for item in plan:
            if isinstance(item, dict) and "fail여부" in item and cm.ISSUE_KEY not in item:
                item = {(cm.ISSUE_KEY if k == "fail여부" else k): v for k, v in item.items()}   # 구 키
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


def _machines_in(text):
    """'AOI-4,6,9' / 'AOI-4, AOI-6' → ['AOI-4','AOI-6','AOI-9'] (표시·설정 이동용)."""
    import re
    text = str(text or "").strip()
    if not text:
        return []
    prefix = re.match(r"[^\d]*", text).group(0).strip(" ,/") or "AOI-"
    out = []
    for part in re.split(r"[,/;\s]+", text):
        m = re.search(r"(\d+)", part)
        if m:
            head = re.match(r"[^\d]*", part).group(0).strip() or prefix
            name = f"{head}{m.group(1)}"
            if name not in out:
                out.append(name)
    return out
