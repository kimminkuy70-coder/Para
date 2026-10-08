"""양식 만들기 — new form from equipment or local copies (tkinter `_form_new` →
`_scales_then_build` → `_form_build_and_edit`).

Collection reuses the value-update collector steps (Job/Setup questions, local
temp copies only). After the user confirms per-variant coefficients the Lots
are parsed and loaded into the shared `DesktopForm`, so the existing page /
edit / scales / confirm protocol (and screen) finishes the form.

하위 레시피 선택(이슈 #20): 수집 뒤 `collect` 가 하위 레시피(변형)마다 어느 호기에서
읽혔는지 함께 돌려주고, `parse(variants=)` 는 고른 하위 레시피만 양식에 넣는다
(같은 상위 레시피라도 호기마다 하위 레시피가 달라, 공통된 것만 보려는 목적).
"""
import re
from pathlib import Path

from . import coef_detector, coefstore, editor_model, engine, formbuilder, ini_parser, namestore, workdirs
from .desktop_update import DesktopUpdate


class DesktopFormNew:
    def __init__(self, form, config_path=None):
        self.form = form
        self.collector = DesktopUpdate(config_path)
        self.sources = None
        self.recipe = ""
        self.variants = []

    @property
    def config_path(self):
        return self.collector.config_path

    @config_path.setter
    def config_path(self, value):
        self.collector.config_path = Path(value)
        self.form.config_path = Path(value)

    def prepare(self, params):
        out = self.collector.prepare(params)
        save = self.collector._cfg()["save_dir"]
        out["existing"] = workdirs.list_recipes(save)
        return out

    def collect(self, params):
        if set(params) - {"recipe", "machines", "source", "answers"}:
            raise ValueError("양식 만들기 요청을 확인하세요")
        recipe = params.get("recipe")
        if (not isinstance(recipe, str) or not recipe.strip() or len(recipe.strip()) > 64
                or re.search(r'[<>:"/\\|?*]', recipe) or recipe.strip() in (".", "..")):
            raise ValueError("레시피 이름을 확인하세요(파일 이름에 쓸 수 없는 문자 제외)")
        recipe = recipe.strip()
        out = self.collector.gather(dict(recipes=[recipe], machines=params.get("machines"),
                                         source=params.get("source"), answers=params.get("answers") or {}),
                                    allow_new=True, hold=False)
        if out["stage"] == "question":
            return out
        self.recipe, self.sources = recipe, out["sources"]
        variants, dirs, where = [], {}, {}
        for root, kw, machine in self.sources:
            for c in ini_parser.scan_tree(root, default_level=recipe or kw, default_equipment=machine):
                if not ini_parser.config_valid(c):
                    continue
                v = c.mag or ""
                if v not in variants:
                    variants.append(v)
                    dirs[v] = c.config_dir
                where.setdefault(v, [])
                if machine not in where[v]:
                    where[v].append(machine)
        if not variants:
            raise ValueError("인식된 설정(config) 폴더가 없습니다. GlobalRTP.ini/OpticPreset.ini/Zones 구조를 확인하세요.")
        scales = []
        for v in variants:
            try:
                reco = coef_detector.detect_from_dir(dirs[v])
            except Exception:  # noqa: BLE001 - the RTP estimate is only a suggestion
                reco = None
            value = (reco or {}).get("Coefficient")
            scales.append(dict(variant=v, coef=value if value is not None else ini_parser.DEFAULT_SCALE,
                               source="RTP 추정" if value is not None else "기본값",
                               confidence=(reco or {}).get("Confidence", ""), reason=(reco or {}).get("Reason", ""),
                               machines=where.get(v, [])))
        self.variants = variants
        state = self.collector.state
        return dict(stage="scales", recipe=recipe, scales=scales,
                    collected=[m for m in out["machines"] if m in state["sources"]],
                    errors=[dict(machine=m, error=e) for m, e in state["errors"].items()])

    def parse(self, params):
        if (not {"scales", "base_form"} <= set(params) <= {"scales", "base_form", "variants"}
                or not isinstance(params["scales"], dict)):
            raise ValueError("변환계수를 확인하세요")
        if not self.sources:
            raise ValueError("먼저 장비 또는 로컬에서 수집하세요")
        # 하위 레시피 선택 — 없으면(구 화면) 수집한 하위 레시피 전부.
        picked = params.get("variants")
        if picked is None:
            picked = list(self.variants)
        if (not isinstance(picked, list) or not picked
                or any(not isinstance(v, str) or v not in self.variants for v in picked)):
            raise ValueError("양식에 넣을 하위 레시피를 한 개 이상 고르세요")
        picked = set(picked)
        scales = {}
        for key, value in params["scales"].items():
            if not isinstance(key, str) or type(value) not in (int, float) or not 0 < value <= 1e6:
                raise ValueError("변환계수는 0보다 큰 숫자여야 합니다")
            scales[key] = float(value)
        save = self.collector._cfg()["save_dir"]
        path = coefstore.coef_path(save)
        rows = coefstore.load(path) if Path(path).is_file() else []
        configs = []
        for root, kw, machine in self.sources:
            configs += ini_parser.scan_tree(root, default_level=self.recipe or kw, default_equipment=machine,
                                            scales=scales, coef_lookup=coefstore.make_lookup(rows))
        pivot, _machines = ini_parser.build_pivot([c for c in configs
                                                   if ini_parser.config_valid(c) and (c.mag or "") in picked])
        if not pivot:
            raise ValueError("읽힌 파라미터가 없습니다. 수집된 설정 파일을 확인하세요.")
        from .formcache import similar_forms
        from .desktop_batch import DesktopBatch
        # Cached per form file (local): unchanged forms are not re-opened on OneDrive.
        forms = similar_forms(save, str(DesktopBatch(self.config_path).configuration()[2]), exclude=self.recipe) if save else {}
        ranked = formbuilder.rank_similar_forms(formbuilder.pivot_param_keys(pivot), forms)
        base = params["base_form"]
        if not isinstance(base, str) or (base and base not in forms):
            raise ValueError("기반 레시피를 확인하세요")
        try:
            names = namestore.load(namestore.name_path(save))
        except (OSError, ValueError):
            names = []
        entries = editor_model.build_entries(pivot, base_keys=forms[base] if base else None,
                                             name_lookup=namestore.make_lookup(names),
                                             use_lookup=namestore.make_use_lookup(names))
        self.form.root = self.form._load_root()
        opened = self.form.load_entries(entries, level=self.recipe, recipe=self.recipe,
                                        source=f"수집: {', '.join(sorted({m for _, _, m in self.sources}))}")
        # 확정 호기 = 수집한 호기(여러 대면 처음 고른 호기). 사람에게 다시 묻지 않는다.
        collected = list(dict.fromkeys(m for _, _, m in self.sources))
        opened["machine"] = collected[0] if collected else ""
        return dict(form=opened, similar=[dict(recipe=r, match=n, total=t) for r, n, t in ranked[:8]],
                    base_form=base, machines=sorted({m for _, _, m in self.sources}))

    def cancel(self, params):
        if params:
            raise ValueError("요청을 확인하세요")
        self.sources = None
        self.variants = []
        return self.collector.cancel({})
