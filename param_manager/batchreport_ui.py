"""Tkinter adapter. Background code receives snapshots, never Tk variables."""
from __future__ import annotations

import copy
import tkinter as tk
import webbrowser
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import batchreport, batchreport_service, batchreport_store, watcher, wph


class BatchReportMixin:
    def _batch_save(self):
        from .equip_app import save_config
        save_config(self._cfg)

    def _batch_controls(self, parent):
        bar = ttk.Frame(parent)
        bar.pack(fill='x', padx=8, pady=8)
        ttk.Button(bar, text='지금 업데이트 (마지막 조사 조건)', command=self._batch_update).pack(side='left', padx=4)
        ttk.Button(bar, text='가동률 대시보드 열기', command=self._batch_open_dashboard).pack(side='left', padx=4)
        ttk.Button(bar, text='추가 Report 폴더', command=self._batch_extra_folders).pack(side='left', padx=4)
        self._batch_auto_var = tk.BooleanVar(value=bool(self._cfg.get('batch_auto', False)))

        def toggle():
            self._cfg['batch_auto'] = self._batch_auto_var.get()
            self._batch_save()

        ttk.Checkbutton(parent, text='앱 실행 중 하루 1회 자동 (마지막 조사 조건 · 기본 꺼짐)', variable=self._batch_auto_var, command=toggle).pack(anchor='w', padx=12, pady=(0, 8))

    def _batch_extra_folders(self):
        win = tk.Toplevel(self)
        win.title('호기별 추가/백업 Report 폴더 (읽기 전용)')
        win.geometry('720x410')
        frame = ttk.Frame(win, padding=16)
        frame.pack(fill='both', expand=True)
        machines = self._all_machines()
        machine = tk.StringVar(value=machines[0] if machines else '')
        picker = ttk.Combobox(frame, textvariable=machine, values=machines, state='readonly')
        picker.pack(fill='x')
        paths = copy.deepcopy(self._cfg.get('batch_extra_paths', {}))
        listing = tk.Listbox(frame)
        listing.pack(fill='both', expand=True, pady=10)

        def refresh(*_):
            listing.delete(0, 'end')
            for path in paths.get(machine.get(), []):
                listing.insert('end', path)

        def add():
            folder = filedialog.askdirectory(parent=win, title='추가 Report 폴더 선택')
            if folder and machine.get():
                entries = paths.setdefault(machine.get(), [])
                if folder not in entries:
                    entries.append(folder)
                refresh()

        def remove():
            if listing.curselection():
                del paths[machine.get()][listing.curselection()[0]]
                refresh()

        def save():
            self._cfg['batch_extra_paths'] = paths
            self._batch_save()
            win.destroy()

        picker.bind('<<ComboboxSelected>>', refresh)
        refresh()
        ttk.Label(frame, text='다음 조사 시작부터 적용합니다. 같은 호기의 동일 내용은 한 번만 집계합니다.\n이름이 같아도 내용이 다르면 별도 Report로 보존합니다.', wraplength=650).pack(anchor='w')
        bar = ttk.Frame(frame)
        bar.pack(fill='x', pady=8)
        for label, command in [('폴더 추가', add), ('목록에서 제거', remove), ('저장', save)]:
            ttk.Button(bar, text=label, command=command).pack(side='left', padx=5)

    def _batch_open_dashboard(self):
        path = Path(self.local_dir) / '배치분석' / '대시보드' / '가동률_대시보드.html'
        if path.is_file():
            webbrowser.open(path.resolve().as_uri())
        else:
            messagebox.showinfo('대시보드', '스캔 가동률 지표를 선택해 한 번 조사하세요.', parent=self)

    def _wph_run(self):
        try:
            valid = int(self._wph_valid.get().strip())
            if valid < 1:
                raise ValueError('유효 Lot 매수는 1 이상이어야 합니다')
            targets = []
            for machine, row in getattr(self, '_wph_rows', {}).items():
                if not row['inc'].get():
                    continue
                folder = self._wph_paths().get(machine)
                if not folder:
                    raise ValueError(machine + ' Report 폴더를 지정하세요')
                # Selecting every search result includes new reports on later refresh.
                names = sorted(row['selected']) if row['all_names'] and set(row['selected']) != set(row['all_names']) else None
                period = row.get('mode') is not None and row['mode'].get() == 'period'
                target = {'machine': machine, 'folder': folder, 'names': names,
                          'mode': 'period' if period else 'query',
                          'query': '' if period else row['pref'].get().strip(),
                          'start': row['start'].get().strip() if period else '',
                          'end': row['end'].get().strip() if period else ''}
                signature = (folder, target['query'], target['start'], target['end'])
                if row.get('search_signature') == signature:
                    if row['all_names'] and not row['selected']:
                        continue
                else:
                    # A selection from an older search must not limit new criteria.
                    previous = next((t for t in self._cfg.get('batch_last', {}).get('targets', []) if t['machine'] == machine), {})
                    previous_signature = tuple(previous.get(k, '') for k in ('folder', 'query', 'start', 'end'))
                    target['names'] = previous.get('names') if previous_signature == signature and not row.get('search_signature') else None
                batchreport_store.dates(target)
                targets.append(target)
                for extra in self._cfg.get('batch_extra_paths', {}).get(machine, []):
                    if Path(extra) != Path(folder):
                        targets.append(dict(target, folder=extra))
            if not targets:
                raise ValueError('조사할 호기와 Report를 선택하세요')
            batchreport_store.local_root(self.local_dir, [t['folder'] for t in targets])
        except (ValueError, TypeError) as exc:
            messagebox.showwarning('조사 조건 확인', str(exc), parent=self)
            return
        self._batch_options(targets, valid)

    def _batch_options(self, targets, valid):
        saved = self._cfg.get('batch_last', {}).get('options', {})
        win = tk.Toplevel(self)
        win.title('배치 리포트 분석 · 지표 선택')
        win.geometry('700x660')
        win.transient(self)
        win.grab_set()
        outer = ttk.Frame(win, padding=16)
        outer.pack(fill='both', expand=True)
        ttk.Label(outer, text='분석할 지표를 선택하세요. 유효 Lot 매수는 WPH에만 적용합니다.', wraplength=630).pack(anchor='w', pady=8)
        variables = {}
        for key, title in batchreport.METRICS.items():
            variables[key] = tk.BooleanVar(value=key in saved.get('metrics', batchreport.METRICS))
            ttk.Checkbutton(outer, text=f'{key}  {title}', variable=variables[key]).pack(anchor='w', pady=3)
        baseline = tk.StringVar(value=str(saved.get('min_baseline', 20)))
        drop = tk.StringVar(value=str(saved.get('yield_drop', 5)))
        for label, var in [('이상 후보 최소 과거 Pass 표본 (2 이상)', baseline), ('Yield 하락 기준 (percentage points)', drop)]:
            line = ttk.Frame(outer)
            line.pack(fill='x', pady=5)
            ttk.Label(line, text=label).pack(side='left')
            ttk.Entry(line, textvariable=var, width=9).pack(side='right')
        ttk.Label(outer, text='Aborted·복구·품질 지표는 추정/후보입니다. 장비 설정이나 자동 Hold를 변경하지 않습니다.\n전체 선택 상태는 이후 신규 Report도 포함하며, 일부 파일 선택은 선택 목록을 유지합니다.', wraplength=630).pack(anchor='w', pady=10)

        def start():
            import math
            try:
                selected = [k for k, v in variables.items() if v.get()]
                n, d = int(baseline.get()), float(drop.get())
                if not selected or n < 2 or not math.isfinite(d) or d < 0:
                    raise ValueError
            except ValueError:
                messagebox.showwarning('설정 확인', '지표를 하나 이상 선택하고 유효한 기준을 입력하세요.', parent=win)
                return
            options = {'metrics': selected, 'valid_wafers': valid, 'min_baseline': n, 'yield_drop': d,
                       'by_recipe': bool(self._wph_byrecipe.get())}
            win.destroy()
            self._batch_launch(targets, options)

        ttk.Button(outer, text='선택 지표로 조사 시작', command=start).pack(side='bottom', fill='x', pady=8)

    def _batch_launch(self, targets, options, automatic=False):
        if getattr(self, '_batch_busy', False) or getattr(self, '_watch_busy', False) or getattr(self, '_cmw_busy', False):
            if not automatic:
                messagebox.showinfo('조사 대기', '배치 분석 또는 자동 수집이 진행 중입니다. 완료 후 다시 실행하세요.', parent=self)
            return
        self._batch_busy = True
        targets, options = copy.deepcopy(targets), copy.deepcopy(options)
        root = self.local_dir
        self._cfg['batch_last'] = {'targets': targets, 'options': options}
        wph.remember_investigation(self._cfg, [(t['machine'], t['folder'], t.get('query', ''), t.get('names'), '') for t in targets], options['valid_wafers'])
        self._batch_save()

        def work(report=None):
            return batchreport_service.run(root, targets, options, progress=report)

        def done(ok, result):
            self._batch_busy = False
            old = self._cfg.get('batch_schedule', {})
            partial = ok and (result['collection']['errors'] or result['dashboard_error'])
            self._cfg['batch_schedule'] = {'last_run': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                           'fail_count': 0 if ok and not partial else min(int(old.get('fail_count', 0)) + 1, 4),
                                           'last_result': '완료' if ok and not partial else '일부 오류' if ok else str(result)}
            self._batch_save()
            if not ok:
                if automatic:
                    self._set_status('배치 분석 자동 갱신 실패 (설정에 사유 기록): ' + str(result))
                else:
                    self._err('E194', '배치 리포트 분석 실패', result)
                return
            summary = result['result']['summary']
            self._set_status(f"배치 분석 {'일부 오류' if partial else '완료'} — Report {summary['Batch 수']}건 / {result['outdir']}")
            if not automatic:
                self._batch_done(result, options)

        if automatic:
            self._run_bg(work, done)
        else:
            self._run_busy('배치 리포트 분석 (증분 수집·분석·출력)', work, done)

    def _batch_done(self, result, options):
        win = tk.Toplevel(self)
        win.title('배치 리포트 분석 완료')
        win.geometry('880x560')
        body = ttk.Frame(win, padding=16)
        body.pack(fill='both', expand=True)
        collection = result['collection']
        ttk.Label(body, text=f"신규/변경 {collection['parsed']} · 재사용 {collection['reused']} · 읽기 오류 {len(collection['errors'])}\n{result['outdir']}", wraplength=810).pack(anchor='w', pady=8)
        if result['dashboard_error']:
            ttk.Label(body, text='대시보드 저장 실패: ' + result['dashboard_error'], wraplength=810).pack(anchor='w')
        tree = ttk.Treeview(body, columns=('metric', 'count'), show='headings', height=14)
        tree.heading('metric', text='생성된 분석 표')
        tree.heading('count', text='결과 행 수')
        tree.column('metric', width=610)
        tree.column('count', width=100)
        scroll = ttk.Scrollbar(body, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        tree.pack(fill='both', expand=True)
        for index, table in enumerate(result['result']['tables']):
            tree.insert('', 'end', iid=str(index), values=(table['title'], len(table['rows'])))
        tree.bind('<Double-1>', lambda _: self._batch_preview(result['result']['tables'][int(tree.selection()[0])]) if tree.selection() else None)
        ttk.Label(body, text='표를 더블클릭하면 결과 값을 페이지별로 확인할 수 있습니다.').pack(anchor='w')
        bar = ttk.Frame(body)
        bar.pack(fill='x', pady=12)
        for label, path in [('분석 HTML', result['html']), ('분석 Excel', result['xlsx']), ('결과 폴더', result['outdir']), ('대시보드', result['dashboard'])]:
            if path:
                ttk.Button(bar, text=label, command=lambda p=path: self._open_path(p)).pack(side='left', padx=4)
        if 'M01' in options['metrics']:
            ttk.Button(bar, text='기존 WPH HTML 구성', command=lambda: self._wph_html_dialog(result['outdir'], result['rows'], collection['errors'],
                       sorted({b['machine'] for b in result['result']['batches']}), options['valid_wafers'], options.get('by_recipe', True))).pack(side='left', padx=4)

    def _batch_preview(self, table):
        from .batchreport_output import display
        win = tk.Toplevel(self)
        win.title(table['title'])
        win.geometry('1050x600')
        frame = ttk.Frame(win, padding=12)
        frame.pack(fill='both', expand=True)
        columns = [f'c{i}' for i in range(len(table['headers']))]
        grid = ttk.Treeview(frame, columns=columns, show='headings')
        for key, header in zip(columns, table['headers']):
            grid.heading(key, text=header)
            grid.column(key, width=190, minwidth=100, stretch=False)
        ybar = ttk.Scrollbar(frame, orient='vertical', command=grid.yview)
        xbar = ttk.Scrollbar(frame, orient='horizontal', command=grid.xview)
        grid.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        grid.grid(row=0, column=0, sticky='nsew')
        ybar.grid(row=0, column=1, sticky='ns')
        xbar.grid(row=1, column=0, sticky='ew')
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        bar = ttk.Frame(frame)
        bar.grid(row=2, column=0, sticky='ew', pady=8)
        label = ttk.Label(bar)
        page = [0]
        pages = max(1, (len(table['rows']) + 199) // 200)

        def render(delta=0):
            page[0] = min(pages - 1, max(0, page[0] + delta))
            grid.delete(*grid.get_children())
            for row in table['rows'][page[0] * 200:(page[0] + 1) * 200]:
                grid.insert('', 'end', values=[display(value) for value in row])
            label.config(text=f"{page[0] + 1} / {pages} 페이지 · 전체 {len(table['rows'])}행")

        ttk.Button(bar, text='이전 200행', command=lambda: render(-1)).pack(side='left')
        label.pack(side='left', padx=15)
        ttk.Button(bar, text='다음 200행', command=lambda: render(1)).pack(side='left')
        render()

    def _batch_update(self):
        saved = self._cfg.get('batch_last')
        if not saved:
            messagebox.showinfo('조사 설정 없음', '먼저 호기와 분석 지표를 선택해 한 번 조사하세요.', parent=self)
            return
        self._batch_launch(saved['targets'], saved['options'])

    def _batch_tick(self):
        try:
            saved = self._cfg.get('batch_last')
            settings = watcher.WatchSettings(enabled=bool(self._cfg.get('batch_auto')), interval_hours=24)
            state = watcher.WatchState.from_dict(self._cfg.get('batch_schedule', {}))
            if saved and watcher.should_run(datetime.now(), settings, state):
                self._batch_launch(saved['targets'], saved['options'], automatic=True)
        except Exception as exc:
            self._logerr('E197', exc)
        finally:
            self.after(60_000, self._batch_tick)
