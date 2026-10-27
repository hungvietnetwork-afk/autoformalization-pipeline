"""Generate the chart/diagram widget modules of the report from results/*.csv|json.

Each function returns the module source (one line, single quotes inside) for a Claude Docs widget.
Rows are embedded as inline `sources` so every number in a chart comes from the experiment files.
"""
from __future__ import annotations

import csv
import json
import os

ROOT = os.environ.get("AFP_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results", "figures")


def _res(name: str) -> str:
    """results/figures (script-generated tables) first, then results/raw (raw measurements)."""
    for d in ("figures", "raw"):
        p = os.path.join(ROOT, "results", d, name)
        if os.path.exists(p):
            return p
    return _res(name)


def _js(rows: list[dict]) -> str:
    """JS array literal with single-quoted strings."""
    def val(v):
        if isinstance(v, str):
            return "'" + v.replace("\\", "\\\\").replace("'", "\\'") + "'"
        if v is None:
            return "null"
        if isinstance(v, bool):
            return "true" if v else "false"
        return repr(round(v, 4)) if isinstance(v, float) else str(v)
    return "[" + ",".join("{" + ", ".join(f"{k}:{val(v)}" for k, v in r.items()) + "}" for r in rows) + "]"


def _read(name):
    with open(_res(name)) as f:
        return list(csv.DictReader(f))


# --------------------------------------------------------------------------- 1. matrix throughput
def matrix_throughput(title: str) -> str:
    rows = []
    lab = {"T100": "100 bài", "T1K": "1.000 bài", "T10K": "10.000 bài (replay)"}
    cfgl = {"A": "A · 1 worker, batch 1", "B": "B · 2 worker, batch 8", "C": "C · 4 worker, batch 32"}
    med = _read("matrix_median.csv")
    for t in ("T100", "T1K", "T10K"):
        for c in ("A", "B", "C"):
            r = next(x for x in med if x["tier"] == t and x["config"] == c)
            rows.append({"tier": lab[t], "config": cfgl[c], "cfg": c, "thr": float(r["throughput_problems_per_s"]),
                         "lo": float(r["throughput_problems_per_s_min"]), "hi": float(r["throughput_problems_per_s_max"])})
    return ("export default () => <claude.Visualize data-claude-component='matrix-throughput' sources={{rows:{kind:'data', data:"
            + _js(rows) + "}}}>{({rows, datum}) => { const tiers = [...new Set(rows.map(r => r.tier))], cfgs = [...new Set(rows.map(r => r.config))]; "
            "const peak = Math.max(...rows.map(r => r.hi)); const left = 40, base = 330, h = 230, gw = 680 / tiers.length, bw = 40, gap = 10; "
            "const y = v => base - v / peak * h; const op = c => c === 'A' ? 0.35 : c === 'B' ? 0.65 : 1; "
            "const gx = t => left + tiers.indexOf(t) * gw + (gw - (3 * bw + 2 * gap)) / 2; const bx = r => gx(r.tier) + cfgs.indexOf(r.config) * (bw + gap); "
            "const ink = 'var(--cds-text-primary)', quiet = 'var(--cds-text-secondary)', acc = 'var(--cds-chart-categorical-1)'; "
            "return <svg viewBox='0 0 760 378' role='img' aria-label='" + title + "' fontSize='12'>"
            "<text data-claude-text-id='title' x='24' y='28' fontSize='15' fontWeight='600' fill={ink}>" + title + "</text>"
            "<text data-claude-text-id='subtitle' x='24' y='48' fontSize='11.5' fill={quiet}>Bài toán hoàn tất mỗi giây, median 3 lần chạy; vạch mảnh = min–max</text>"
            "<g data-claude-anchor='legend'>{cfgs.map((c, i) => <g key={c}><rect x={24 + i * 236} y='62' width='12' height='12' rx='2' fill={acc} fillOpacity={op(rows.find(r => r.config === c).cfg)}/><text x={42 + i * 236} y='72' fontSize='11.5' fill={quiet}>{c}</text></g>)}</g>"
            "<line x1={left} x2='720' y1={base} y2={base} stroke='var(--cds-chart-axis)'/>"
            "<g data-claude-anchor='bars'>{rows.map(r => <g key={r.tier + r.cfg}><rect x={bx(r)} y={y(r.thr)} width={bw} height={base - y(r.thr)} rx='3' fill={acc} fillOpacity={op(r.cfg)} {...datum(r, 'thr')}><title>{`${r.tier}, ${r.config}: ${r.thr.toFixed(2).replace('.', ',')} bài/s`}</title></rect>"
            "<line x1={bx(r) + bw / 2} x2={bx(r) + bw / 2} y1={y(r.hi)} y2={y(r.lo)} stroke={ink} strokeOpacity='0.5'/>"
            "<text x={bx(r) + bw / 2} y={y(r.hi) - 6} textAnchor='middle' fontSize='11.5' fill={ink} {...datum(r, 'thr')}>{r.thr.toFixed(1).replace('.', ',')}</text></g>)}</g>"
            "<g data-claude-anchor='tiers'>{tiers.map(t => <text key={t} x={gx(t) + (3 * bw + 2 * gap) / 2} y={base + 22} textAnchor='middle' fill={ink}>{t}</text>)}</g>"
            "</svg>; }}</claude.Visualize>;")


# --------------------------------------------------------------------------- 2. worker scaling
def scaling(title: str) -> str:
    med = sorted(_read("scaling_median.csv"), key=lambda r: int(r["workers"]))
    rows = []
    for r in med:
        rows.append({"workers": int(r["workers"]), "series": "steady", "label": "ổn định (sau khởi động)",
                     "v": float(r["steady_throughput_candidates_per_s"])})
        rows.append({"workers": int(r["workers"]), "series": "e2e", "label": "gồm khởi động REPL",
                     "v": float(r["throughput_candidates_per_s"])})
    return ("export default () => <claude.Visualize data-claude-component='worker-scaling' sources={{rows:{kind:'data', data:"
            + _js(rows) + "}, cpu:{kind:'data', data:[{label:'2 vCPU', workers:2}]}}}>{({rows, cpu, datum}) => { "
            "const ws = [...new Set(rows.map(r => r.workers))]; const s1 = rows.filter(r => r.series === 'steady'), s2 = rows.filter(r => r.series === 'e2e'); "
            "const base1 = s1.at(0).v; const peak = Math.ceil(Math.max(...rows.map(r => r.v)) * 1.3 / 10) * 10; "
            "const left = 70, right = 700, y0 = 96, base = 340; const X = w => left + Math.log2(w) / Math.log2(ws.at(-1)) * (right - left); "
            "const Y = v => base - Math.min(v, peak) / peak * (base - y0); "
            "const path = ss => ss.map((r, i) => `${i ? 'L' : 'M'}${X(r.workers)} ${Y(r.v)}`).join(''); "
            "const idealPts = ws.filter(w => base1 * w <= peak); const wEnd = peak / base1; "
            "const ideal = idealPts.map((w, i) => `${i ? 'L' : 'M'}${X(w)} ${Y(base1 * w)}`).join('') + `L${left + Math.log2(wEnd) / Math.log2(ws.at(-1)) * (right - left)} ${Y(peak)}`; "
            "const ticks = [0, 1, 2, 3, 4, 5, 6, 7, 8].map(k => k * 20).filter(t => t <= peak); "
            "const ink = 'var(--cds-text-primary)', quiet = 'var(--cds-text-secondary)', acc = 'var(--cds-chart-categorical-1)', grey = 'var(--cds-chart-muted)'; "
            "return <svg viewBox='0 0 760 396' role='img' aria-label='" + title + "' fontSize='12'>"
            "<text data-claude-text-id='title' x='24' y='28' fontSize='15' fontWeight='600' fill={ink}>" + title + "</text>"
            "<text data-claude-text-id='subtitle' x='24' y='48' fontSize='11.5' fill={quiet}>Ứng viên kiểm chứng mỗi giây · 10.000 task, batch 8, wall timeout 30 s · median 2 lần (1–2 worker), 1 lần (4, 8 worker)</text>"
            "<g data-claude-anchor='legend'><line x1='24' x2='44' y1='68' y2='68' stroke={acc} strokeWidth='2'/><text x='50' y='72' fontSize='11.5' fill={quiet} {...datum(s1.at(0), 'label')}>{s1.at(0).label}</text>"
            "<line x1='224' x2='244' y1='68' y2='68' stroke={grey} strokeWidth='2'/><text x='250' y='72' fontSize='11.5' fill={quiet} {...datum(s2.at(0), 'label')}>{s2.at(0).label}</text>"
            "<line x1='404' x2='424' y1='68' y2='68' stroke={grey} strokeWidth='1.25' strokeDasharray='2 4'/><text data-claude-text-id='ideal-label' x='430' y='72' fontSize='11.5' fill={quiet}>tuyến tính lý tưởng</text></g>"
            "<g data-claude-anchor='y-axis'>{ticks.map(t => <g key={t}><line x1={left} x2={right} y1={Y(t)} y2={Y(t)} stroke='var(--cds-chart-grid)'/><text x={left - 8} y={Y(t) + 4} textAnchor='end' fontSize='11.5' fill={quiet}>{t}</text></g>)}</g>"
            "<g data-claude-anchor='x-axis'>{ws.map(w => <text key={w} x={X(w)} y={base + 20} textAnchor='middle' fill={quiet}>{w}</text>)}<text data-claude-text-id='x-title' x={(left + right) / 2} y={base + 42} textAnchor='middle' fontSize='11.5' fill={quiet}>Số Lean worker (thang log₂)</text></g>"
            "<g data-claude-anchor='cpu-limit'>{cpu.map(c => <g key={c.label}><line x1={X(c.workers)} x2={X(c.workers)} y1={y0} y2={base} stroke='var(--cds-chart-reference)' strokeDasharray='4 4' {...datum(c, 'workers')}/><text x={X(c.workers) + 6} y={base - 8} fontSize='11.5' fill={quiet} {...datum(c, 'label')}>{c.label}</text></g>)}</g>"
            "<g data-claude-anchor='ideal'><path d={ideal} fill='none' stroke={grey} strokeWidth='1.25' strokeDasharray='2 4'/></g>"
            "<g data-claude-anchor='series-e2e'><path d={path(s2)} fill='none' stroke={grey} strokeWidth='2'/>{s2.map(r => <circle key={r.workers} cx={X(r.workers)} cy={Y(r.v)} r='4.5' fill={grey} {...datum(r, 'v')}><title>{`${r.workers} worker, ${r.label}: ${r.v.toFixed(1).replace('.', ',')}/s`}</title></circle>)}</g>"
            "<g data-claude-anchor='series-steady'><path d={path(s1)} fill='none' stroke={acc} strokeWidth='2'/>{s1.map(r => <circle key={r.workers} cx={X(r.workers)} cy={Y(r.v)} r='4.5' fill={acc} {...datum(r, 'v')}><title>{`${r.workers} worker, ${r.label}: ${r.v.toFixed(1).replace('.', ',')}/s`}</title></circle>)}"
            "{s1.map(r => <text key={'v' + r.workers} x={r.workers === 2 ? X(r.workers) + 8 : X(r.workers)} y={Y(r.v) - (r.workers === 2 ? 6 : 10)} textAnchor={r.workers === 2 ? 'start' : 'middle'} fontSize='11.5' fill={ink} {...datum(r, 'v')}>{r.v.toFixed(0)}</text>)}</g>"
            "</svg>; }}</claude.Visualize>;")


# --------------------------------------------------------------------------- 3. memory vs workers
def memory(title: str, ram_gb: float) -> str:
    med = sorted(_read("scaling_median.csv"), key=lambda r: int(r["workers"]))
    rows = []
    for r in med:
        w = int(r["workers"])
        rows.append({"workers": w, "series": "rss", "label": "Σ RSS (đếm trùng trang chung)", "gb": float(r["peak_rss_sum_mb"]) / 1024})
        rows.append({"workers": w, "series": "pool", "label": "footprint thực của pool", "gb": float(r["peak_pool_mb"]) / 1024})
        rows.append({"workers": w, "series": "anon", "label": "chỉ heap riêng", "gb": float(r["peak_pool_anon_mb"]) / 1024})
    return ("export default () => <claude.Visualize data-claude-component='pool-memory' sources={{rows:{kind:'data', data:"
            + _js(rows) + "}, ram:{kind:'data', data:[{label:'RAM của máy', gb:" + str(round(float(ram_gb), 2)) + "}]}}}>{({rows, ram, datum}) => { "
            "const ws = [...new Set(rows.map(r => r.workers))]; const ser = [...new Set(rows.map(r => r.series))]; "
            "const peak = Math.max(...rows.map(r => r.gb), ram.at(0).gb) * 1.08; const left = 60, right = 560, y0 = 80, base = 330; "
            "const X = w => left + Math.log2(w) / Math.log2(ws.at(-1)) * (right - left), Y = v => base - v / peak * (base - y0); "
            "const col = s => s === 'pool' ? 'var(--cds-chart-categorical-1)' : 'var(--cds-chart-muted)'; const dash = s => s === 'rss' ? '5 4' : 'none'; "
            "const ticks = [0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40].filter(t => t <= peak); "
            "const ink = 'var(--cds-text-primary)', quiet = 'var(--cds-text-secondary)'; "
            "return <svg viewBox='0 0 760 390' role='img' aria-label='" + title + "' fontSize='12'>"
            "<text data-claude-text-id='title' x='24' y='28' fontSize='15' fontWeight='600' fill={ink}>" + title + "</text>"
            "<text data-claude-text-id='subtitle' x='24' y='48' fontSize='11.5' fill={quiet}>Đỉnh bộ nhớ (GB) theo số Lean worker, 10.000 task</text>"
            "<g data-claude-anchor='y-axis'>{ticks.map(t => <g key={t}><line x1={left} x2={right} y1={Y(t)} y2={Y(t)} stroke='var(--cds-chart-grid)'/><text x={left - 8} y={Y(t) + 4} textAnchor='end' fontSize='11.5' fill={quiet}>{t}</text></g>)}</g>"
            "<g data-claude-anchor='x-axis'>{ws.map(w => <text key={w} x={X(w)} y={base + 20} textAnchor='middle' fill={quiet}>{w}</text>)}<text data-claude-text-id='x-title' x={(left + right) / 2} y={base + 42} textAnchor='middle' fontSize='11.5' fill={quiet}>Số Lean worker</text></g>"
            "<g data-claude-anchor='ram-limit'>{ram.map(m => <g key={m.label}><line x1={left} x2={right} y1={Y(m.gb)} y2={Y(m.gb)} stroke='var(--cds-chart-reference)' strokeDasharray='4 4' {...datum(m, 'gb')}/><text x={right - 6} y={Y(m.gb) - 6} textAnchor='end' fontSize='11.5' fill={quiet} {...datum(m, 'label')}>{`${m.label} ≈ ${m.gb.toFixed(1)} GB`}</text></g>)}</g>"
            "{ser.map(s => { const ss = rows.filter(r => r.series === s); return <g key={s} data-claude-anchor={`series-${s}`}><path d={ss.map((r, i) => `${i ? 'L' : 'M'}${X(r.workers)} ${Y(r.gb)}`).join('')} fill='none' stroke={col(s)} strokeWidth='2' strokeDasharray={dash(s)}/>{ss.map(r => <circle key={r.workers} cx={X(r.workers)} cy={Y(r.gb)} r='4.5' fill={col(s)} {...datum(r, 'gb')}><title>{`${r.workers} worker, ${r.label}: ${r.gb.toFixed(2)} GB`}</title></circle>)}<text x={right + 12} y={Y(ss.at(-1).gb) + 4} fontSize='11.5' fill={s === 'pool' ? ink : quiet} {...datum(ss.at(-1), 'label')}>{`${ss.at(-1).label}: ${ss.at(-1).gb.toFixed(1)}`}</text></g>; })}"
            "</svg>; }}</claude.Visualize>;")


# --------------------------------------------------------------------------- 4. pass@k vs tokens
def passk(title: str) -> str:
    rows = [{"setting": r["setting"], "k": int(r["k"]), "pass": float(r["pass_at_k"]), "tok": float(r["tokens_per_problem"])}
            for r in _read("passk_vs_cost.csv")]
    return ("export default () => <claude.Visualize data-claude-component='passk-tokens' sources={{rows:{kind:'data', data:"
            + _js(rows) + "}}}>{({rows, datum}) => { const few = rows.filter(r => r.setting === 'few-shot'), zero = rows.filter(r => r.setting === 'zero-shot'); "
            "const tmax = Math.ceil(Math.max(...rows.map(r => r.tok)) * 1.1 / 500) * 500, lo = Math.floor(Math.min(...rows.map(r => r.pass)) * 20) / 20, hi = 1; "
            "const left = 70, right = 620, y0 = 80, base = 320; const X = t => left + t / tmax * (right - left), Y = p => base - (p - lo) / (hi - lo) * (base - y0); "
            "const ticks = [0, 1, 2, 3, 4, 5].map(k => lo + k * (hi - lo) / 5); const xt = [0, 1, 2, 3, 4, 5, 6, 7, 8].map(k => k * 500).filter(t => t <= tmax); "
            "const ink = 'var(--cds-text-primary)', quiet = 'var(--cds-text-secondary)', acc = 'var(--cds-chart-categorical-1)', grey = 'var(--cds-chart-muted)'; "
            "return <svg viewBox='0 0 760 380' role='img' aria-label='" + title + "' fontSize='12'>"
            "<text data-claude-text-id='title' x='24' y='28' fontSize='15' fontWeight='600' fill={ink}>" + title + "</text>"
            "<text data-claude-text-id='subtitle' x='24' y='48' fontSize='11.5' fill={quiet}>Cùng 100 bài (T100): tỷ lệ bài có ≥ 1 ứng viên compile, theo token ước tính mỗi bài</text>"
            "<g data-claude-anchor='y-axis'>{ticks.map(t => <g key={t}><line x1={left} x2={right} y1={Y(t)} y2={Y(t)} stroke='var(--cds-chart-grid)'/><text x={left - 8} y={Y(t) + 4} textAnchor='end' fontSize='11.5' fill={quiet}>{`${Math.round(t * 100)} %`}</text></g>)}</g>"
            "<g data-claude-anchor='x-axis'>{xt.map(t => <text key={t} x={X(t)} y={base + 20} textAnchor='middle' fontSize='11.5' fill={quiet}>{t.toLocaleString('vi-VN')}</text>)}<text data-claude-text-id='x-title' x={(left + right) / 2} y={base + 42} textAnchor='middle' fontSize='11.5' fill={quiet}>Token ước tính mỗi bài (prompt + output, k mẫu)</text></g>"
            "<g data-claude-anchor='series-few-shot'><path d={few.map((r, i) => `${i ? 'L' : 'M'}${X(r.tok)} ${Y(r.pass)}`).join('')} fill='none' stroke={acc} strokeWidth='2'/>{few.map(r => <g key={r.k}><circle cx={X(r.tok)} cy={Y(r.pass)} r='5' fill={acc} {...datum(r, 'pass')}><title>{`few-shot, k=${r.k}: ${(r.pass * 100).toFixed(1).replace('.', ',')} % với ${Math.round(r.tok)} token/bài`}</title></circle><text x={X(r.tok)} y={Y(r.pass) + (r.k === 1 ? 22 : -12)} textAnchor='middle' fontSize='11.5' fill={ink} {...datum(r, 'pass')}>{`k=${r.k}: ${(r.pass * 100).toFixed(1).replace('.', ',')} %`}</text></g>)}</g>"
            "<g data-claude-anchor='series-zero-shot'>{zero.map(r => <g key={r.k}><circle cx={X(r.tok)} cy={Y(r.pass)} r='5' fill={grey} {...datum(r, 'pass')}><title>{`zero-shot, k=1: ${(r.pass * 100).toFixed(1).replace('.', ',')} %`}</title></circle><text x={X(r.tok)} y={Y(r.pass) - 12} textAnchor='middle' fontSize='11.5' fill={quiet} {...datum(r, 'pass')}>{`zero-shot: ${(r.pass * 100).toFixed(1).replace('.', ',')} %`}</text></g>)}</g>"
            "</svg>; }}</claude.Visualize>;")


# --------------------------------------------------------------------------- 5. error taxonomy
def taxonomy(title: str, run_name: str = "q_T1K_zeroshot") -> str:
    tx = json.load(open(_res(f"taxonomy_{run_name}.json")))
    order = ["COMPILE_OK", "PARSE_ERROR", "UNKNOWN_IDENTIFIER", "TYPE_MISMATCH", "OTHER_ERROR", "TIMEOUT", "EMPTY_OUTPUT"]
    label = {"proofnet": "ProofNet", "minif2f": "miniF2F", "math": "MATH", "gsm8k": "GSM8K"}
    rows = []
    for s in ["proofnet", "minif2f", "math", "gsm8k"]:
        d = tx["by_source"].get(s, {})
        n = sum(d.values())
        for st in order:
            if d.get(st):
                rows.append({"source": label[s], "status": st, "n": d[st], "total": n})
    return ("export default () => <claude.Visualize data-claude-component='error-taxonomy' sources={{rows:{kind:'data', data:"
            + _js(rows) + "}}}>{({rows, datum}) => { const srcs = [...new Set(rows.map(r => r.source))], sts = [...new Set(rows.map(r => r.status))]; "
            "const tone = s => s === 'COMPILE_OK' ? 'var(--cds-chart-categorical-1)' : s === 'PARSE_ERROR' ? 'var(--cds-chart-categorical-2)' : s === 'UNKNOWN_IDENTIFIER' ? 'var(--cds-chart-categorical-3)' : s === 'TYPE_MISMATCH' ? 'var(--cds-chart-categorical-4)' : s === 'OTHER_ERROR' ? 'var(--cds-chart-categorical-5)' : s === 'TIMEOUT' ? 'var(--cds-chart-categorical-7)' : 'var(--cds-chart-muted)'; "
            "const left = 100, wide = 560, y0 = 100, rowh = 46, bh = 24; const start = r => rows.filter(x => x.source === r.source && sts.indexOf(x.status) < sts.indexOf(r.status)).reduce((a, x) => a + x.n, 0) / r.total; "
            "const ink = 'var(--cds-text-primary)', quiet = 'var(--cds-text-secondary)'; "
            "return <svg viewBox='0 0 760 " + str(100 + 46 * 4 + 40) + "' role='img' aria-label='" + title + "' fontSize='12'>"
            "<text data-claude-text-id='title' x='24' y='28' fontSize='15' fontWeight='600' fill={ink}>" + title + "</text>"
            "<g data-claude-anchor='legend'>{sts.map((s, i) => <g key={s}><rect x={24 + (i % 4) * 180} y={44 + Math.floor(i / 4) * 18} width='11' height='11' rx='2' fill={tone(s)}/><text x={40 + (i % 4) * 180} y={54 + Math.floor(i / 4) * 18} fontSize='11' fill={quiet}>{s}</text></g>)}</g>"
            "{srcs.map((s, j) => <g key={s} data-claude-anchor={`source-${j}`}><text x={left - 10} y={y0 + j * rowh + bh / 2 + 4} textAnchor='end' fill={ink}>{s}</text>{rows.filter(r => r.source === s).map(r => <rect key={r.status} x={left + start(r) * wide} y={y0 + j * rowh} width={Math.max(0, r.n / r.total * wide - 2)} height={bh} fill={tone(r.status)} {...datum(r, 'n')}><title>{`${r.source} · ${r.status}: ${r.n}/${r.total} (${(100 * r.n / r.total).toFixed(0)}%)`}</title></rect>)}{rows.filter(r => r.source === s && r.status === 'COMPILE_OK').map(r => <text key='ok' x={left + wide + 8} y={y0 + j * rowh + bh / 2 + 4} fontSize='11.5' fontWeight='600' fill={ink} {...datum(r, 'n')}>{`${(100 * r.n / r.total).toFixed(0)}% OK`}</text>)}</g>)}"
            "</svg>; }}</claude.Visualize>;")


# --------------------------------------------------------------------------- 5b. failure root causes
CAUSE_LABEL = {"sanitizer_let_cut": "Sanitizer v1 cắt nhầm let … :=", "types_coercions_instances": "Kiểu, coercion, instance",
               "lean4_syntax": "Cú pháp Lean 4", "missing_namespace_or_notation": "Thiếu namespace hoặc notation",
               "timeout": "Quá hạn 10 s", "header_notation": "Header mở Nat: φ thành ký hiệu",
               "empty_output": "Không có khai báo", "other": "Khác"}
OWNER_LABEL = {"pipeline": "Pipeline của nhóm", "model": "Model", "environment": "Môi trường Lean", "resource": "Giới hạn tài nguyên"}


def failure_causes(title: str, run_name: str = "q_T1K_zeroshot", subtitle: str = "") -> str:
    fc = json.load(open(_res(f"failure_causes_{run_name}.json")))
    rows = [{"cause": CAUSE_LABEL[c["cause"]], "owner": OWNER_LABEL[c["owner"]], "n": c["n"]} for c in fc["causes"]]
    owners = [OWNER_LABEL[o] for o in ("pipeline", "model", "environment", "resource")
              if any(r["owner"] == OWNER_LABEL[o] for r in rows)]
    height = 104 + 38 * len(rows) + 16
    return ("export default () => <claude.Visualize data-claude-component='failure-causes' sources={{rows:{kind:'data', data:"
            + _js(rows) + "}, owners:{kind:'data', data:" + _js([{"owner": o} for o in owners]) + "}}}>{({rows, owners, datum}) => { "
            "const own = owners.map(o => o.owner); const tone = o => `var(--cds-chart-categorical-${own.indexOf(o) + 1})`; "
            "const left = 268, wide = 400, y0 = 104, rowh = 38, bh = 22; const peak = Math.max(...rows.map(r => r.n)); "
            "const ink = 'var(--cds-text-primary)', quiet = 'var(--cds-text-secondary)'; "
            "return <svg viewBox='0 0 760 " + str(height) + "' role='img' aria-label='" + title + "' fontSize='12'>"
            "<text data-claude-text-id='title' x='24' y='28' fontSize='15' fontWeight='600' fill={ink}>" + title + "</text>"
            "<text data-claude-text-id='subtitle' x='24' y='48' fontSize='11.5' fill={quiet}>" + subtitle + "</text>"
            "<g data-claude-anchor='legend'>{own.map((o, i) => <g key={o}><rect x={24 + i * 170} y='64' width='11' height='11' rx='2' fill={tone(o)}/><text x={40 + i * 170} y='74' fontSize='11.5' fill={quiet}>{o}</text></g>)}</g>"
            "<line x1={left} x2={left} y1={y0 - 8} y2={y0 + rows.length * rowh - 8} stroke='var(--cds-chart-axis)'/>"
            "<g data-claude-anchor='bars'>{rows.map((r, j) => <g key={r.cause}><text x={left - 10} y={y0 + j * rowh + bh / 2 + 4} textAnchor='end' fill={ink}>{r.cause}</text>"
            "<rect x={left} y={y0 + j * rowh} width={r.n / peak * wide} height={bh} rx='3' fill={tone(r.owner)} {...datum(r, 'n')}><title>{`${r.cause} · ${r.owner}: ${r.n} ứng viên`}</title></rect>"
            "<text x={left + r.n / peak * wide + 8} y={y0 + j * rowh + bh / 2 + 4} fontSize='12' fontWeight='600' fill={ink} {...datum(r, 'n')}>{r.n}</text></g>)}</g>"
            "</svg>; }}</claude.Visualize>;")


# --------------------------------------------------------------------------- 5c. where the workers' time went
def time_budget(title: str, subtitle: str, groups: str) -> str:
    """groups = 'label=run_prefix;label=run_prefix' -> mean shares over the runs of each prefix (e.g. 3 repeats)."""
    import glob
    import sys as _s
    _s.path.insert(0, os.path.join(ROOT, "src"))
    from afp.analysis import time_budget as tb
    seg = [("useful_check_share", "Kiểm chứng (có ích)"), ("timeout_wait_share", "Chờ ứng viên quá hạn"),
           ("restart_share", "Khởi động lại REPL"), ("recycle_share", "Làm mới REPL định kỳ"), ("other_share", "Hàng đợi, IPC, chờ")]
    rows = []
    for g in groups.split(";"):
        label, prefix = g.split("=")
        runs = [tb(d) for d in sorted(glob.glob(os.path.join(ROOT, "results", "raw", "runs", prefix + "*")))
                if os.path.exists(os.path.join(d, "metrics.json"))]
        for key, name in seg:
            rows.append({"group": label, "part": name, "share": round(sum(r[key] for r in runs) / len(runs), 4),
                         "runs": len(runs)})
    return ("export default () => <claude.Visualize data-claude-component='time-budget' sources={{rows:{kind:'data', data:"
            + _js(rows) + "}}}>{({rows, datum}) => { const groups = [...new Set(rows.map(r => r.group))], parts = [...new Set(rows.map(r => r.part))]; "
            "const tone = p => p === parts.at(0) ? 'var(--cds-chart-categorical-1)' : p === parts.at(1) ? 'var(--cds-chart-categorical-2)' : p === parts.at(2) ? 'var(--cds-chart-categorical-3)' : p === parts.at(3) ? 'var(--cds-chart-categorical-4)' : 'var(--cds-chart-muted)'; "
            "const left = 170, wide = 480, y0 = 112, rowh = 44, bh = 26; "
            "const start = r => rows.filter(x => x.group === r.group && parts.indexOf(x.part) < parts.indexOf(r.part)).reduce((a, x) => a + x.share, 0); "
            "const ink = 'var(--cds-text-primary)', quiet = 'var(--cds-text-secondary)'; "
            "return <svg viewBox={`0 0 760 ${y0 + (groups.length - 1) * rowh + bh + 20}`} role='img' aria-label='" + title + "' fontSize='12'>"
            "<text data-claude-text-id='title' x='24' y='28' fontSize='15' fontWeight='600' fill={ink}>" + title + "</text>"
            "<text data-claude-text-id='subtitle' x='24' y='48' fontSize='11.5' fill={quiet}>" + subtitle + "</text>"
            "<g data-claude-anchor='legend'>{parts.map((p, i) => <g key={p}><rect x={24 + (i % 3) * 240} y={64 + Math.floor(i / 3) * 18} width='11' height='11' rx='2' fill={tone(p)}/><text x={40 + (i % 3) * 240} y={74 + Math.floor(i / 3) * 18} fontSize='11.5' fill={quiet}>{p}</text></g>)}</g>"
            "{groups.map((g, j) => <g key={g} data-claude-anchor={`group-${j}`}><text x={left - 10} y={y0 + j * rowh + bh / 2 + 4} textAnchor='end' fill={ink}>{g}</text>"
            "{rows.filter(r => r.group === g).map(r => <rect key={r.part} x={left + start(r) * wide} y={y0 + j * rowh} width={Math.max(0, r.share * wide - 2)} height={bh} fill={tone(r.part)} {...datum(r, 'share')}><title>{`${r.group} · ${r.part}: ${Math.round(r.share * 100)}% (trung bình ${r.runs} lần chạy)`}</title></rect>)}"
            "{rows.filter(r => r.group === g && r.part === parts.at(0)).map(r => <text key='u' x={left + wide + 8} y={y0 + j * rowh + bh / 2 + 4} fontSize='11.5' fontWeight='600' fill={ink} {...datum(r, 'share')}>{`${Math.round(r.share * 100)}% có ích`}</text>)}</g>)}"
            "</svg>; }}</claude.Visualize>;")


# --------------------------------------------------------------------------- 3b. memory: what happens to the shared pages
def memory_pages(title: str, subtitle: str, ram_gb: float) -> str:
    """Per worker count (scaling runs): Σ private heap (peak), median resident .olean pages per REPL, ΣRSS (peak)."""
    import glob
    import statistics as st
    rows = []
    for w in (1, 2, 4, 8):
        files, anon, rss = [], [], []
        for d in sorted(glob.glob(os.path.join(ROOT, "results", "raw", "runs", f"sc_T10K_w{w}_r*"))):
            mp = os.path.join(d, "memory.csv")
            if not os.path.exists(mp):
                continue
            with open(mp) as f:
                m = [r for r in csv.DictReader(f) if float(r["n_repl"]) > 0]
            files.append(st.median(float(r["repl_file_mb"]) for r in m))
            anon.append(max(float(r["repl_anon_mb"]) for r in m))
            rss.append(max(float(r["repl_rss_sum_mb"]) for r in m))
        if not files:
            continue
        rows.append({"workers": w, "series": "rss", "label": "ΣRSS (đếm trùng)", "gb": round(st.median(rss) / 1024, 2)})
        rows.append({"workers": w, "series": "file", "label": "trang .olean còn trong RAM", "gb": round(st.median(files) / 1024, 2)})
        rows.append({"workers": w, "series": "anon", "label": "Σ heap riêng của các REPL", "gb": round(st.median(anon) / 1024, 2)})
    return ("export default () => <claude.Visualize data-claude-component='pool-memory' sources={{rows:{kind:'data', data:"
            + _js(rows) + "}, ram:{kind:'data', data:[{label:'RAM của máy', gb:" + str(round(float(ram_gb), 2)) + "}]}}}>{({rows, ram, datum}) => { "
            "const ws = [...new Set(rows.map(r => r.workers))]; const ser = [...new Set(rows.map(r => r.series))]; "
            "const peak = Math.max(...rows.map(r => r.gb), ram.at(0).gb) * 1.08; const left = 60, right = 520, y0 = 80, base = 330; "
            "const X = w => left + Math.log2(w) / Math.log2(ws.at(-1)) * (right - left), Y = v => base - v / peak * (base - y0); "
            "const col = s => s === 'file' ? 'var(--cds-chart-categorical-1)' : s === 'anon' ? 'var(--cds-chart-categorical-2)' : 'var(--cds-chart-muted)'; const dash = s => s === 'rss' ? '5 4' : 'none'; "
            "const ticks = [0, 5, 10, 15, 20, 25, 30, 35, 40].filter(t => t <= peak); "
            "const ink = 'var(--cds-text-primary)', quiet = 'var(--cds-text-secondary)'; "
            "return <svg viewBox='0 0 760 384' role='img' aria-label='" + title + "' fontSize='12'>"
            "<text data-claude-text-id='title' x='24' y='28' fontSize='15' fontWeight='600' fill={ink}>" + title + "</text>"
            "<text data-claude-text-id='subtitle' x='24' y='48' fontSize='11.5' fill={quiet}>" + subtitle + "</text>"
            "<g data-claude-anchor='y-axis'>{ticks.map(t => <g key={t}><line x1={left} x2={right} y1={Y(t)} y2={Y(t)} stroke='var(--cds-chart-grid)'/><text x={left - 8} y={Y(t) + 4} textAnchor='end' fontSize='11.5' fill={quiet}>{t}</text></g>)}<text data-claude-text-id='y-title' x={left - 8} y={y0 - 12} textAnchor='end' fontSize='11.5' fill={quiet}>GB</text></g>"
            "<g data-claude-anchor='x-axis'>{ws.map(w => <text key={w} x={X(w)} y={base + 20} textAnchor='middle' fill={quiet}>{w}</text>)}<text data-claude-text-id='x-title' x={(left + right) / 2} y={base + 42} textAnchor='middle' fontSize='11.5' fill={quiet}>Số Lean worker</text></g>"
            "<g data-claude-anchor='ram-limit'>{ram.map(m => <g key={m.label}><line x1={left} x2={right} y1={Y(m.gb)} y2={Y(m.gb)} stroke='var(--cds-chart-reference)' strokeDasharray='4 4' {...datum(m, 'gb')}/><text x={right - 6} y={Y(m.gb) - 6} textAnchor='end' fontSize='11.5' fill={quiet} {...datum(m, 'label')}>{`${m.label} ≈ ${m.gb.toFixed(1).replace('.', ',')} GB`}</text></g>)}</g>"
            "{ser.map(s => { const ss = rows.filter(r => r.series === s); return <g key={s} data-claude-anchor={`series-${s}`}><path d={ss.map((r, i) => `${i ? 'L' : 'M'}${X(r.workers)} ${Y(r.gb)}`).join('')} fill='none' stroke={col(s)} strokeWidth='2' strokeDasharray={dash(s)}/>{ss.map(r => <circle key={r.workers} cx={X(r.workers)} cy={Y(r.gb)} r='4.5' fill={col(s)} {...datum(r, 'gb')}><title>{`${r.workers} worker, ${r.label}: ${r.gb.toFixed(1).replace('.', ',')} GB`}</title></circle>)}<text x={right + 12} y={Y(ss.at(-1).gb) + (s === 'anon' ? -6 : s === 'file' ? 14 : 4)} fontSize='11.5' fill={s === 'rss' ? quiet : ink} {...datum(ss.at(-1), 'label')}>{`${ss.at(-1).label}: ${ss.at(-1).gb.toFixed(1).replace('.', ',')}`}</text></g>; })}"
            "</svg>; }}</claude.Visualize>;")


# --------------------------------------------------------------------------- 5d. queue micro-benchmark
def queue_bench(title: str, subtitle: str) -> str:
    rows = []
    for r in json.load(open(_res("bench_queue.json"))):
        if r["batch"] == 1:
            rows.append({"depth": r["depth"], "series": "indexed" if r["indexed"] else "legacy",
                         "label": "index phủ + quét định kỳ" if r["indexed"] else "như trong thí nghiệm",
                         "ms": r["ms_per_lease_median"]})
    return ("export default () => <claude.Visualize data-claude-component='queue-bench' sources={{rows:{kind:'data', data:"
            + _js(rows) + "}}}>{({rows, datum}) => { const ds = [...new Set(rows.map(r => r.depth))]; const ser = [...new Set(rows.map(r => r.series))]; "
            "const left = 80, right = 560, y0 = 80, base = 320; const lo = -2, hi = 2.5; "
            "const X = d => left + (Math.log10(d) - Math.log10(ds.at(0))) / (Math.log10(ds.at(-1)) - Math.log10(ds.at(0))) * (right - left); "
            "const Y = v => base - (Math.log10(v) - lo) / (hi - lo) * (base - y0); "
            "const col = s => s === 'legacy' ? 'var(--cds-chart-categorical-2)' : 'var(--cds-chart-categorical-1)'; "
            "const ticks = [0.01, 0.1, 1, 10, 100]; const fmt = v => v >= 1 ? v.toFixed(0) : v.toFixed(v >= 0.1 ? 1 : 2).replace('.', ','); "
            "const ink = 'var(--cds-text-primary)', quiet = 'var(--cds-text-secondary)'; "
            "return <svg viewBox='0 0 760 376' role='img' aria-label='" + title + "' fontSize='12'>"
            "<text data-claude-text-id='title' x='24' y='28' fontSize='15' fontWeight='600' fill={ink}>" + title + "</text>"
            "<text data-claude-text-id='subtitle' x='24' y='48' fontSize='11.5' fill={quiet}>" + subtitle + "</text>"
            "<g data-claude-anchor='y-axis'>{ticks.map(t => <g key={t}><line x1={left} x2={right} y1={Y(t)} y2={Y(t)} stroke='var(--cds-chart-grid)'/><text x={left - 8} y={Y(t) + 4} textAnchor='end' fontSize='11.5' fill={quiet}>{fmt(t)}</text></g>)}<text data-claude-text-id='y-title' x={left - 8} y={y0 - 14} textAnchor='end' fontSize='11.5' fill={quiet}>ms / lease</text></g>"
            "<g data-claude-anchor='x-axis'>{ds.map(d => <text key={d} x={X(d)} y={base + 20} textAnchor='middle' fill={quiet}>{d.toLocaleString('vi-VN')}</text>)}<text data-claude-text-id='x-title' x={(left + right) / 2} y={base + 42} textAnchor='middle' fontSize='11.5' fill={quiet}>Số task đang chờ trong hàng đợi (thang log)</text></g>"
            "{ser.map(s => { const ss = rows.filter(r => r.series === s); return <g key={s} data-claude-anchor={`series-${s}`}><path d={ss.map((r, i) => `${i ? 'L' : 'M'}${X(r.depth)} ${Y(r.ms)}`).join('')} fill='none' stroke={col(s)} strokeWidth='2'/>{ss.map(r => <g key={r.depth}><circle cx={X(r.depth)} cy={Y(r.ms)} r='4.5' fill={col(s)} {...datum(r, 'ms')}><title>{`${r.label}, ${r.depth.toLocaleString('vi-VN')} task: ${String(r.ms).replace('.', ',')} ms mỗi lease`}</title></circle><text x={X(r.depth)} y={Y(r.ms) + (s === 'legacy' ? -10 : 18)} textAnchor='middle' fontSize='11.5' fill={ink} {...datum(r, 'ms')}>{fmt(r.ms)}</text></g>)}<text x={right + 14} y={Y(ss.at(-1).ms) + 4} fontSize='11.5' fill={ink} {...datum(ss.at(-1), 'label')}>{ss.at(-1).label}</text></g>; })}"
            "</svg>; }}</claude.Visualize>;")


# --------------------------------------------------------------------------- 5e. semantic verdicts by source
VERDICT_LABEL = {"EQUIV_GOLD": "Tương đương gold", "PROVED_CONSISTENT": "Lean suy ra đáp án", "NO_EVIDENCE_OF_ERROR": "Không thấy lỗi",
                 "ANSWER_MISSING": "Thiếu đáp án", "ARITHMETIC_ONLY": "Chỉ còn số học", "TRIVIAL": "Tầm thường",
                 "FALSE": "Bị phản chứng", "VACUOUS": "Giả thiết mâu thuẫn"}


def verdict_mix(title: str, subtitle: str, run_name: str = "q_T1K_zeroshot") -> str:
    sm = json.load(open(_res("semantic_summary.json")))[run_name]
    order = [v for v in VERDICT_LABEL if v in sm["verdicts"]]
    label = {"proofnet": "ProofNet", "minif2f": "miniF2F", "math": "MATH", "gsm8k": "GSM8K"}
    rows = []
    for src in ("proofnet", "minif2f", "math", "gsm8k"):
        d = sm["by_source"].get(src, {})
        n = sum(d.values())
        for v in order:
            if d.get(v):
                rows.append({"source": label[src], "verdict": VERDICT_LABEL[v], "n": d[v], "total": n})
    return ("export default () => <claude.Visualize data-claude-component='semantic-verdicts' sources={{rows:{kind:'data', data:"
            + _js(rows) + "}, verdicts:{kind:'data', data:" + _js([{"verdict": VERDICT_LABEL[v]} for v in order]) + "}}}>{({rows, verdicts, datum}) => { "
            "const vs = verdicts.map(v => v.verdict); const srcs = [...new Set(rows.map(r => r.source))]; "
            "const tone = v => v === vs.at(0) ? 'var(--cds-chart-categorical-1)' : v === vs.at(1) ? 'var(--cds-chart-categorical-3)' : v === vs.at(2) ? 'var(--cds-chart-muted)' : v === vs.at(3) ? 'var(--cds-chart-categorical-2)' : v === vs.at(4) ? 'var(--cds-chart-categorical-4)' : 'var(--cds-chart-categorical-5)'; "
            "const left = 110, wide = 520, y0 = 112, rowh = 44, bh = 26; "
            "const start = r => rows.filter(x => x.source === r.source && vs.indexOf(x.verdict) < vs.indexOf(r.verdict)).reduce((a, x) => a + x.n, 0) / r.total; "
            "const ink = 'var(--cds-text-primary)', quiet = 'var(--cds-text-secondary)'; "
            "return <svg viewBox={`0 0 760 ${y0 + (srcs.length - 1) * rowh + bh + 20}`} role='img' aria-label='" + title + "' fontSize='12'>"
            "<text data-claude-text-id='title' x='24' y='28' fontSize='15' fontWeight='600' fill={ink}>" + title + "</text>"
            "<text data-claude-text-id='subtitle' x='24' y='48' fontSize='11.5' fill={quiet}>" + subtitle + "</text>"
            "<g data-claude-anchor='legend'>{vs.map((v, i) => <g key={v}><rect x={24 + (i % 3) * 240} y={64 + Math.floor(i / 3) * 18} width='11' height='11' rx='2' fill={tone(v)}/><text x={40 + (i % 3) * 240} y={74 + Math.floor(i / 3) * 18} fontSize='11.5' fill={quiet}>{v}</text></g>)}</g>"
            "{srcs.map((s, j) => <g key={s} data-claude-anchor={`source-${j}`}><text x={left - 10} y={y0 + j * rowh + bh / 2 + 4} textAnchor='end' fill={ink}>{s}</text>"
            "{rows.filter(r => r.source === s).map(r => <rect key={r.verdict} x={left + start(r) * wide} y={y0 + j * rowh} width={Math.max(0, r.n / r.total * wide - 2)} height={bh} fill={tone(r.verdict)} {...datum(r, 'n')}><title>{`${r.source} · ${r.verdict}: ${r.n}/${r.total} (${Math.round(100 * r.n / r.total)} %)`}</title></rect>)}"
            "{rows.filter(r => r.source === s).slice(0, 1).map(r => <text key='t' x={left + wide + 8} y={y0 + j * rowh + bh / 2 + 4} fontSize='11.5' fill={quiet} {...datum(r, 'total')}>{`${r.total} ứng viên`}</text>)}</g>)}"
            "</svg>; }}</claude.Visualize>;")


# --------------------------------------------------------------------------- 5f. mutation test
MUT_LABEL = {"CONTROL": "Giữ nguyên (đối chứng)", "ANSWER_CHANGE": "Đổi đáp án", "DROP_HYP": "Bỏ một giả thiết",
             "FLIP_REL": "Đảo quan hệ", "VACUOUS": "Thêm giả thiết mâu thuẫn", "TRIVIAL": "Kết luận thành True"}


def mutation_chart(title: str, subtitle: str) -> str:
    ms = json.load(open(_res("mutation_summary.json")))
    rows = []
    for k in ("VACUOUS", "TRIVIAL", "ANSWER_CHANGE", "FLIP_REL", "DROP_HYP", "CONTROL"):
        v = ms[k]
        rows.append({"kind": MUT_LABEL[k], "test": "strong", "label": "Gắn cờ chắc chắn, không cần gold", "rate": v["strong_flag_rate"], "n": v["n"]})
        rows.append({"kind": MUT_LABEL[k], "test": "any", "label": "Kể cả mất tương đương với gold", "rate": v["flagged_any_rate"], "n": v["n"]})
    return ("export default () => <claude.Visualize data-claude-component='mutation-test' sources={{rows:{kind:'data', data:"
            + _js(rows) + "}}}>{({rows, datum}) => { const kinds = [...new Set(rows.map(r => r.kind))]; const tests = [...new Set(rows.map(r => r.test))]; "
            "const left = 200, wide = 430, y0 = 96, rowh = 46, bh = 15; const tone = t => t === 'strong' ? 'var(--cds-chart-categorical-2)' : 'var(--cds-chart-categorical-1)'; "
            "const ink = 'var(--cds-text-primary)', quiet = 'var(--cds-text-secondary)'; const first = t => rows.find(r => r.test === t); "
            "return <svg viewBox={`0 0 760 ${y0 + kinds.length * rowh + 8}`} role='img' aria-label='" + title + "' fontSize='12'>"
            "<text data-claude-text-id='title' x='24' y='28' fontSize='15' fontWeight='600' fill={ink}>" + title + "</text>"
            "<text data-claude-text-id='subtitle' x='24' y='48' fontSize='11.5' fill={quiet}>" + subtitle + "</text>"
            "<g data-claude-anchor='legend'>{tests.map((t, i) => <g key={t}><rect x={24 + i * 300} y='62' width='11' height='11' rx='2' fill={tone(t)}/><text x={40 + i * 300} y='72' fontSize='11.5' fill={quiet} {...datum(first(t), 'label')}>{first(t).label}</text></g>)}</g>"
            "<line x1={left} x2={left} y1={y0 - 6} y2={y0 + kinds.length * rowh - 10} stroke='var(--cds-chart-axis)'/>"
            "{kinds.map((k, j) => <g key={k} data-claude-anchor={`kind-${j}`}><text x={left - 10} y={y0 + j * rowh + bh + 4} textAnchor='end' fill={ink}>{k}</text>"
            "{rows.filter(r => r.kind === k).map((r, i) => <g key={r.test}><rect x={left} y={y0 + j * rowh + i * (bh + 3)} width={Math.max(1.5, r.rate * wide)} height={bh} rx='2' fill={tone(r.test)} {...datum(r, 'rate')}><title>{`${r.kind} · ${r.label}: ${Math.round(r.rate * 100)} % của ${r.n} bản`}</title></rect>"
            "<text x={left + Math.max(1.5, r.rate * wide) + 6} y={y0 + j * rowh + i * (bh + 3) + bh - 3} fontSize='11' fill={ink} {...datum(r, 'rate')}>{`${Math.round(r.rate * 100)} %`}</text></g>)}"
            "{rows.filter(r => r.kind === k).slice(0, 1).map(r => <text key='n' x={left + wide + 62} y={y0 + j * rowh + bh + 4} fontSize='11' fill={quiet} {...datum(r, 'n')}>{`${r.n} bản`}</text>)}</g>)}"
            "</svg>; }}</claude.Visualize>;")


# --------------------------------------------------------------------------- 7. problems per LLM request
def inference_batching(title: str, subtitle: str) -> str:
    """Two small panels on one x (problems per request): tokens per problem (dots, log scale) and the share of
    requests that failed or came back incomplete (bars from zero). Accent on the 20-26 class (the operating point)."""
    d = json.load(open(_res("inference_batching.json")))["by_problems_per_request"]
    lab = {"1": "1 bài", "9": "9 bài", "20-26": "20–26 bài", "100-142": "100–142 bài"}
    rows = [{"size": c, "slug": "s" + c.replace("-", "_"), "label": lab[c], "tok": d[c]["zeroshot_tokens_per_problem"],
             "fail": round(d[c].get("request_failure_share", 0.0), 4), "req": d[c]["requests"], "focus": c == "20-26"}
            for c in ("1", "9", "20-26", "100-142") if c in d]
    return ("export default () => <claude.Visualize data-claude-component='inference-batching' sources={{rows:{kind:'data', data:"
            + _js(rows) + "}}}>{({rows, datum}) => { "
            "const ink = 'var(--cds-text-primary)', quiet = 'var(--cds-text-secondary)', acc = 'var(--cds-chart-categorical-1)', grey = 'var(--cds-chart-muted)'; "
            "const col = r => r.focus ? acc : grey; const lx0 = 64, lx1 = 372, rx0 = 420, rx1 = 736, y0 = 110, base = 300; "
            "const band = (lx1 - lx0) / rows.length, cx = (i, x0) => x0 + band * (i + 0.5); "
            "const lo = 3, hi = 5, Y = v => base - (Math.log10(v) - lo) / (hi - lo) * (base - y0); const ticks = [1000, 10000, 100000]; "
            "const fmax = 0.7, YF = f => base - f / fmax * (base - y0); "
            "const pct = f => `${(f * 100).toFixed(1).replace('.', ',').replace(',0', '')} %`; "
            "return <svg viewBox='0 0 760 362' role='img' aria-label='" + title + "' fontSize='12'>"
            "<text data-claude-text-id='title' x='24' y='28' fontSize='15' fontWeight='600' fill={ink}>" + title + "</text>"
            "<text data-claude-text-id='subtitle' x='24' y='48' fontSize='11.5' fill={quiet}>" + subtitle + "</text>"
            "<text data-claude-text-id='left-title' x={lx0} y='86' fontSize='12.5' fontWeight='600' fill={ink}>Token mỗi bài (thang log)</text>"
            "<text data-claude-text-id='right-title' x={rx0} y='86' fontSize='12.5' fontWeight='600' fill={ink}>Request hỏng hoặc thiếu bài</text>"
            "<g data-claude-anchor='y-axis-tokens'>{ticks.map(t => <g key={t}><line x1={lx0} x2={lx1} y1={Y(t)} y2={Y(t)} stroke='var(--cds-chart-grid)'/><text x={lx0 - 6} y={Y(t) + 4} textAnchor='end' fontSize='11' fill={quiet}>{t.toLocaleString('vi-VN')}</text></g>)}</g>"
            "<g data-claude-anchor='tokens'>{rows.map((r, i) => <g key={r.slug}><line x1={cx(i, lx0)} x2={cx(i, lx0)} y1={base} y2={Y(r.tok)} stroke={col(r)} strokeOpacity='0.4' strokeWidth='2'/><circle cx={cx(i, lx0)} cy={Y(r.tok)} r='6' fill={col(r)} {...datum(r, 'tok')}><title>{`${r.label} mỗi request: ${r.tok.toLocaleString('vi-VN')} token mỗi bài (${r.req} request)`}</title></circle><text x={cx(i, lx0)} y={Y(r.tok) - 12} textAnchor='middle' fontSize='11.5' fill={ink} {...datum(r, 'tok')}>{r.tok.toLocaleString('vi-VN')}</text><text x={cx(i, lx0)} y={base + 20} textAnchor='middle' fontSize='11.5' fill={quiet}>{r.label}</text></g>)}</g>"
            "<line x1={rx0} x2={rx1} y1={base} y2={base} stroke='var(--cds-chart-axis)'/>"
            "<g data-claude-anchor='failures'>{rows.map((r, i) => <g key={r.slug}><rect x={cx(i, rx0) - 18} y={YF(r.fail)} width='36' height={Math.max(base - YF(r.fail), 0)} rx='3' fill={col(r)} {...datum(r, 'fail')}><title>{`${r.label} mỗi request: ${pct(r.fail)} request hỏng hoặc thiếu (${r.req} request)`}</title></rect><text x={cx(i, rx0)} y={YF(r.fail) - 8} textAnchor='middle' fontSize='11.5' fill={ink} {...datum(r, 'fail')}>{pct(r.fail)}</text><text x={cx(i, rx0)} y={base + 20} textAnchor='middle' fontSize='11.5' fill={quiet}>{r.label}</text></g>)}</g>"
            "<text data-claude-text-id='x-title' x='400' y={base + 48} textAnchor='middle' fontSize='11.5' fill={quiet}>Số bài trong một request tới mô hình</text>"
            "</svg>; }}</claude.Visualize>;")


# --------------------------------------------------------------------------- 8. verification batch size
BATCH_LABEL = {"b1": "lô 1", "b1_idx": "lô 1 + index", "b8": "lô 8", "b32": "lô 32"}
BATCH_SHORT = {"b1": "1", "b1_idx": "1+i", "b8": "8", "b32": "32"}


def batch_sweep(title: str, subtitle: str, focus: str = "b8") -> str:
    """One panel per tier (own scale, bars from zero), one bar per batch configuration: end-to-end problems/s,
    median of 3 runs, thin line = min-max. Accent on `focus`."""
    med = _read("batch_median.csv")
    tl = {"T100": "100 bài", "T1K": "1.000 bài", "T10K": "10.000 task (replay)"}
    rows = []
    for t in ("T100", "T1K", "T10K"):
        for c in ("b1", "b1_idx", "b8", "b32"):
            r = next((x for x in med if x["tier"] == t and x["config"] == c), None)
            if r:
                v = float(r["throughput_problems_per_s"])
                rows.append({"tier": t, "tierLabel": tl[t], "cfg": c, "label": BATCH_LABEL[c], "short": BATCH_SHORT[c], "thr": v,
                             "lo": float(r.get("throughput_problems_per_s_min") or v),
                             "hi": float(r.get("throughput_problems_per_s_max") or v),
                             "steady": float(r["steady_throughput_candidates_per_s"]), "focus": focus == "all" or c == focus})
    return ("export default () => <claude.Visualize data-claude-component='batch-sweep' sources={{rows:{kind:'data', data:"
            + _js(rows) + "}}}>{({rows, datum}) => { "
            "const ink = 'var(--cds-text-primary)', quiet = 'var(--cds-text-secondary)', acc = 'var(--cds-chart-categorical-1)', grey = 'var(--cds-chart-muted)'; "
            "const tiers = [...new Set(rows.map(r => r.tier))]; const pw = 236, gapP = 14, left = 24, y0 = 112, base = 300, bw = 34, gap = 14; "
            "const px = t => left + tiers.indexOf(t) * (pw + gapP); const cfgs = [...new Set(rows.map(r => r.cfg))]; "
            "const bx = r => px(r.tier) + (pw - (cfgs.length * bw + (cfgs.length - 1) * gap)) / 2 + cfgs.indexOf(r.cfg) * (bw + gap); "
            "const peak = t => Math.max(...rows.filter(r => r.tier === t).map(r => r.hi)) * 1.12; "
            "const Y = r => base - r.thr / peak(r.tier) * (base - y0), YV = (r, v) => base - v / peak(r.tier) * (base - y0); "
            "const f1 = v => v.toFixed(1).replace('.', ','); "
            "return <svg viewBox='0 0 760 372' role='img' aria-label='" + title + "' fontSize='12'>"
            "<text data-claude-text-id='title' x='24' y='28' fontSize='15' fontWeight='600' fill={ink}>" + title + "</text>"
            "<text data-claude-text-id='subtitle' x='24' y='48' fontSize='11.5' fill={quiet}>" + subtitle + "</text>"
            "{tiers.map(t => <g key={t} data-claude-anchor={`panel-${t}`}><text x={px(t) + pw / 2} y='88' textAnchor='middle' fontSize='12.5' fontWeight='600' fill={ink}>{rows.find(r => r.tier === t).tierLabel}</text><line x1={px(t)} x2={px(t) + pw} y1={base} y2={base} stroke='var(--cds-chart-axis)'/></g>)}"
            "<g data-claude-anchor='bars'>{rows.map(r => <g key={r.tier + r.cfg}><rect x={bx(r)} y={Y(r)} width={bw} height={base - Y(r)} rx='3' fill={r.focus ? acc : grey} {...datum(r, 'thr')}><title>{`${r.tierLabel}, ${r.label}: ${f1(r.thr)} bài/s (min ${f1(r.lo)}, max ${f1(r.hi)}); ổn định ${f1(r.steady)} ứng viên/s`}</title></rect>"
            "<line x1={bx(r) + bw / 2} x2={bx(r) + bw / 2} y1={YV(r, r.hi)} y2={YV(r, r.lo)} stroke={ink} strokeOpacity='0.45'/>"
            "<text x={bx(r) + bw / 2} y={YV(r, r.hi) - 6} textAnchor='middle' fontSize='11' fill={ink} {...datum(r, 'thr')}>{f1(r.thr)}</text>"
            "<text x={bx(r) + bw / 2} y={base + 18} textAnchor='middle' fontSize='11.5' fill={quiet}>{r.short}</text></g>)}</g>"
            "<text data-claude-text-id='x-title' x='24' y={base + 46} fontSize='11.5' fill={quiet}>Số task mỗi lần worker lấy việc: 1 · 1+i (lô 1, hàng đợi có index) · 8 · 32. Mỗi ô một thang riêng.</text>"
            "</svg>; }}</claude.Visualize>;")


if __name__ == "__main__":
    import sys
    fn = {"matrix": matrix_throughput, "scaling": scaling, "memory": memory, "passk": passk, "taxonomy": taxonomy,
          "causes": failure_causes, "budget": time_budget, "pages": memory_pages, "queue": queue_bench, "verdicts": verdict_mix,
          "mutation": mutation_chart, "inference": inference_batching, "batch": batch_sweep}[sys.argv[1]]
    print(fn(*sys.argv[2:]))


# --------------------------------------------------------------------------- 6. architecture diagram
def architecture() -> str:
    W, Hb, y0, gap, left = 166, 104, 76, 20, 18
    xs = [left + i * (W + gap) for i in range(4)]
    def box(i, slug, name_id, name, lines, main=False):
        x = xs[i]
        stroke = "acc" if main else "edge"
        out = (f"<g data-claude-anchor='{slug}'><rect x='{x}' y='{y0}' width='{W}' height='{Hb}' rx='8' "
               f"fill={{{'acc' if main else chr(39) + 'none' + chr(39)}}} fillOpacity='{0.12 if main else 1}' stroke={{{stroke}}} strokeWidth='{2 if main else 1.25}'/>"
               f"<text data-claude-text-id='{name_id}' x='{x + 12}' y='{y0 + 24}' fontSize='13' fontWeight='600' fill={{ink}}>{name}</text>")
        for j, (lid, txt) in enumerate(lines):
            out += f"<text data-claude-text-id='{lid}' x='{x + 12}' y='{y0 + 44 + 16 * j}' fontSize='11.5' fill={{quiet}}>{txt}</text>"
        return out + "</g>"
    b1 = box(0, "stage-queue", "queue-name", "Queue problems",
             [("q1", "SHA256(id) mod R, R=16"), ("q2", "lease, ack, retry ≤ 3"), ("q3", "dead-letter sau 3 lần"), ("q4", "idempotent enqueue")])
    b2 = box(1, "stage-inference", "inf-name", "Batch Inference",
             [("i1", "gom batch bài / lô"), ("i2", "k ứng viên mỗi bài"), ("i3", "cache theo TaskHash"), ("i4", "LLM: batch job / API")])
    b3 = box(2, "stage-lean", "lean-name", "Lean Verify Pool",
             [("l1", "N worker, REPL nóng"), ("l2", "import Mathlib 1 lần"), ("l3", "timeout cứng 10 s"), ("l4", "work stealing")], main=True)
    b4 = box(3, "stage-store", "store-name", "Store / Aggregator",
             [("s1", "UPSERT theo TaskHash"), ("s2", "Pass@k, best-of-k"), ("s3", "Parquet source/domain"), ("s4", "log thô, metrics")])
    ay = y0 + Hb // 2
    arrows = "".join(f"<path d='M{xs[i] + W} {ay}H{xs[i + 1] - 2}' markerEnd='url(#arch-arrow)'/>" for i in range(3))
    alab = (f"<text data-claude-text-id='e1' x='{xs[1] - gap // 2}' y='{y0 - 8}' textAnchor='middle' fontSize='11' fill={{quiet}}>DataUnit</text>"
            f"<text data-claude-text-id='e2' x='{xs[2] - gap // 2}' y='{y0 - 8}' textAnchor='middle' fontSize='11' fill={{quiet}}>q_verify</text>"
            f"<text data-claude-text-id='e3' x='{xs[3] - gap // 2}' y='{y0 - 8}' textAnchor='middle' fontSize='11' fill={{quiet}}>VerifyResult</text>")
    by = y0 + Hb + 28
    band = (f"<g data-claude-anchor='broker'><rect x='{left}' y='{by}' width='{4 * W + 3 * gap}' height='56' rx='8' fill='var(--cds-chart-reference-tint)' stroke={{edge}} strokeWidth='1.25'/>"
            f"<text data-claude-text-id='broker-1' x='{left + 12}' y='{by + 22}' fontSize='12' fontWeight='600' fill={{ink}}>Broker dùng chung: SQLite WAL (một máy) hoặc Redis Streams (nhiều máy)</text>"
            f"<text data-claude-text-id='broker-2' x='{left + 12}' y='{by + 42}' fontSize='11.5' fill={{quiet}}>TaskHash = SHA256(problem_id ‖ prompt_version ‖ candidate_index) là khoá của cache, hàng đợi và kết quả</text></g>")
    links = "".join(f"<path d='M{xs[i] + W // 2} {y0 + Hb}V{by}' strokeDasharray='3 3'/>" for i in range(4))
    fy = by + 56 + 30
    fail = (f"<g data-claude-anchor='failure-path'><text data-claude-text-id='f1' x='{left}' y='{fy}' fontSize='12' fontWeight='600' fill={{ink}}>Khi worker hoặc REPL chết</text>"
            f"<text data-claude-text-id='f2' x='{left}' y='{fy + 18}' fontSize='11.5' fill={{quiet}}>lease hết hạn → task tự quay lại hàng đợi → worker khác làm lại (tối đa 3 lần) → UPSERT ghi đè đúng dòng cũ:</text>"
            f"<text data-claude-text-id='f3' x='{left}' y='{fy + 34}' fontSize='11.5' fill={{quiet}}>không mất task, không trùng kết quả, không gọi lại model (cache theo TaskHash).</text></g>")
    H = fy + 34 + 22
    title = "Bốn tầng tách rời qua hàng đợi phân vùng; tầng Lean là nơi tốn tài nguyên nhất"
    return ("export default () => { const edge = 'var(--cds-chart-axis)', acc = 'var(--cds-chart-categorical-1)', ink = 'var(--cds-text-primary)', quiet = 'var(--cds-text-secondary)'; "
            f"return <svg viewBox='0 0 760 {H}' role='img' aria-label='{title}' fontSize='12'>"
            "<defs><marker id='arch-arrow' viewBox='0 0 10 10' refX='9' refY='5' markerWidth='6' markerHeight='6' orient='auto-start-reverse'><path d='M0 0L10 5L0 10z' fill={edge}/></marker></defs>"
            f"<text data-claude-text-id='title' x='{left}' y='30' fontSize='15' fontWeight='600' fill={{ink}}>{title}</text>"
            f"{b1}{b2}{b3}{b4}<g data-claude-anchor='connectors' fill='none' stroke={{edge}} strokeWidth='1.25'>{arrows}{links}</g>{alab}{band}{fail}"
            "</svg>; };")
