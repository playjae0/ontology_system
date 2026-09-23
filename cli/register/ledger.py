# -*- coding: utf-8 -*-
"""칸 1.5·1.6 — **열 판정 대장**과 role 표: 어느 열이 무엇이 됐나를 파일로 남긴다."""

from __future__ import annotations

from cli.prompt import (  # noqa: F401
    KIT_NOTE, VOCAB_SECTIONS, _dir, _strip_kit_notes, _dump_prompt, _strip_module_doc,
    _reference_adapter, generate_template, _render_template, _vocab_excerpt, _sent_size)
from core import paths
from core.state import fixtures, log, registry, store
from kit.gate_tables import load_blocks
from parser import pipeline, preflight, profile, reader, tagger
from parser.normalizer import _col
from pathlib import Path
import json
import re
from cli.register import draft as draft_mod
from cli.register import REVIEW, _load


def _profiles(doc_type):
    """입력 패키지의 열 프로파일 — **파일에서 읽는다**(상태에 복제하지 않는다)."""
    p = REVIEW / doc_type / "input_package.json"
    if not p.exists():
        return []
    pkg = json.loads(p.read_text(encoding="utf-8"))
    return [pp for h in ((pkg.get("system") or {}).get("reader_head") or [])
            for pp in (h.get("열_프로파일") or [])]


def role_table(schema, adapter_mod, st=None, prof=None):
    """구획 2 — 필드 → role 배정표. **근거를 병기**한다(§7 구조).

    **6지선다는 role 5종 + UNMAPPABLE**이고, 구조 필드·payload 고정 키는 그 대상이
    아니다(C17 · D-46) — 미해결이 아니라 정상·완결이라 질문거리가 아니기 때문이다.
    공용 블록 유래 필드는 배정표에 뜨되 출처를 밝힌다.
    """
    fields, from_blocks = load_blocks(schema)
    rows = []
    for f, spec in fields.items():
        rows.append({"field": f, "role": spec.get("role"),
                     "category": spec.get("category"),
                     "attach_to": spec.get("attach_to_field"),
                     "reason": spec.get("정의문")
                     or ("공용 블록이 선언한 필드다" if f in from_blocks
                         else "생성 세션의 배정 근거"),
                     **({"from_block": "공용 블록"} if f in from_blocks else {})})
    # **여섯째 경로에 올리는 것은 「판단이 안 선 열」뿐이다**(B49 · C19 개정).
    # 판정해서 뺀 열(`excluded`)은 제외 목록이 자리이고, 대장에 없는 열(`orphan`)은
    # 결함이다 — 셋을 한 표에 섞으면 구판처럼 다시 「같은 질문」이 된다.
    for u in unmappable_of(schema, adapter_mod)[1]:
        rows.append({"field": u["field"], "role": "UNMAPPABLE",
                     "reason": f"생성이 판단하지 못했다: {u.get('reason') or '사유 없음'}"})

    # ── 사람이 볼 것을 줄인다 (B39 ③ — 3단 깔때기의 셋째 단) ──────────
    # **전 열을 평평하게 보이면 이 절차의 목적이 달성되지 않는다**(실측: attribute
    # 25개가 평평하게 올라왔다). 먼저 볼 것 둘을 표시한다:
    #   ①기계 제안과 LLM 판정이 갈린 열  ②확신 경계선 부근
    rep = (st or {}).get("generation_report") or {}
    rank = {x["field"]: x["rank"] for x in (rep.get("attribute_ranking") or [])}
    cut = rep.get("confidence_cut")
    # **한 필드가 열 여럿일 수 있다**(합치기 — B64 ①). 하나로 접으면 뒤 열이
    # 조용히 사라지고, 그 자리가 이번 사고의 첫 원인이었다(B76 ①).
    _led_cols = {}
    for x in read_ledger((st or {}).get("doc_type", "")):
        if x.get("field"):
            _led_cols.setdefault(x["field"], []).append(x["col"])
    sug = {}
    for s in (prof or []):
        for col, v in (s.get("열") or {}).items():
            sug[col] = (v.get("기계제안") or {}).get("제안")
    for r in rows:
        marks = []
        # **열문자는 대장에서만 읽는다**(B67 ③ · B76 ②) — 어댑터 `columns` 폴백을
        # 두면 대장이 빈 필드가 조용히 통과하고(이번 사고의 둘째 원인), 그 값이
        # 합치기 리스트면 `sug`의 키로 들어가 죽는다(첫 원인 — 형은 G4F가 막는다).
        # 대장이 스키마 필드 전부를 덮는 것은 `G4G`가 지킨다.
        cols = _led_cols.get(r["field"]) or []
        # 합치기면 **기계 제안이 있는 첫 열**로 대조한다 — 열 하나를 가리킬 수
        # 없다는 사실이 대조를 건너뛸 이유는 아니다.
        s = next((sug.get(c) for c in cols if sug.get(c)), None)
        if s and s != "role 판정 대상" and r.get("role") != s:
            marks.append(f"기계 제안({s})과 갈림")
            r["machine_suggest"] = s
        if r["field"] in rank:
            r["rank"] = rank[r["field"]]
            if cut is not None and abs(rank[r["field"]] - cut) <= 1:
                marks.append("확신 경계선 부근")
        if marks:
            r["attention"] = " · ".join(marks)
    # **먼저 볼 것을 위로 올린다** — 화면 순서가 곧 검토 순서다.
    rows.sort(key=lambda r: (0 if r.get("attention") else 1, r.get("rank", 999)))
    return rows


def col_values(cols):
    """`columns` 값을 **열문자 집합**으로 편다 — 값 셋(열문자·라벨·리스트) 공통 (B64 ①).

    해석이 끝난 뒤에는 전부 열문자이지만, 해석 전(사람이 라벨을 적은 채)의 어댑터도
    이 함수를 지난다 — 그때는 라벨이 섞여 있고 그것은 관문이 FAIL로 답한다.
    """
    out = set()
    for v in (cols or {}).values():
        out |= {str(x) for x in v} if isinstance(v, (list, tuple)) else {str(v)}
    return out


def _unmapped_labels(exp, adapter_mod):
    """어댑터가 **출력하지 않는** 헤더 라벨 — 차집합 복원.

    구판 스키마의 복원 재료이자, 신판에서 `orphan`(대장에 없는 열)을 찾는 재료다.
    `columns`가 가리키는 열은 여기 오지 않는다 — **구조 필드**(`process_ref`·
    `electrode_type` 등)가 그 자리이고, 그것은 UNMAPPABLE이 아니라 정상·완결이다
    (D-46 · 생성 템플릿 「구조 필드는 UNMAPPABLE이 아니다」).
    """
    labels, cols = exp.get("header_labels") or [], exp.get("columns") or {}
    if not labels or not cols:
        return []
    # **위치 가정을 두지 않는다**(문서 6 §6.4-6: "빈 셀은 배열에 넣지 않는다").
    # `labels`의 i번째가 i+1번째 열이라고 보면 헤더 행에 빈 칸이 하나만 있어도
    # 그 뒤 전부가 한 칸씩 밀려 **엉뚱한 열이 UNMAPPABLE로 뜬다** — 사람이
    # 판정해야 할 것이 화면에서 바뀌는 셈이다.
    #
    # 대신 **실물 헤더에서 열 문자를 다시 읽는다.** 읽을 수 없으면(표본 경로가
    # 없거나 포맷 패키지가 없으면) 위치 가정으로 떨어지되 **그 사실을 남긴다** —
    # 조용히 틀린 답을 내지 않는다.
    # **리스트를 펼쳐 센다**(B64 ①) — `columns` 값은 열문자·라벨·리스트 셋이고,
    # 합친 열도 **쓴 열**이다. 펼치지 않으면 집합에 리스트가 들어가 계산이 깨지거나
    # (대조표 6) 합쳐진 둘째 열이 orphan으로 잘못 뜬다.
    used = col_values(cols)
    pos = _label_columns(exp, adapter_mod)
    if pos:
        # 라벨의 열 **전부**가 쓰였을 때만 쓴 것이다 — 둘 중 하나만 쓰면 나머지는
        # 판정되지 않은 열이고, 그것이 화면에서 사라지면 안 된다(D-82).
        return [lab for lab, letters in pos.items()
                if any(x not in used for x in letters)]
    store.append_defect(
        f"UNMAPPABLE 복원이 위치 가정으로 떨어졌다 — 실물 헤더를 읽지 못했다 "
        f"(doc_type={(getattr(adapter_mod, 'ADAPTER', {}) or {}).get('doc_type')})")
    return [labels[i] for i in range(len(labels)) if _col(i + 1) not in used]


def unmappable_of(schema, adapter_mod):
    """전 열의 판정 — **`(excluded, undecided, orphan)` 셋**으로 가른다 (C19 개정 · B49).

    | 갈래 | 무엇 | 화면 |
    |---|---|---|
    | `excluded` | 생성이 **판정해서 뺐다**(사유 필수) | 제외 목록 — **질문이 아니다** |
    | `undecided` | 생성이 **판단을 못 했다** | 6지선다 질문 |
    | `orphan` | 헤더에 있는데 **어느 쪽에도 없다** | 결함 — 기계 관문을 막는다 |

    셋을 가르는 이유(실측): 구판은 차집합 하나로 복원해 셋이 **같은 질문**으로 떴다.
    그래서 「생성 때 이미 판정한 열」이 검수에서 다시 물어졌고(사내 실사용 신고),
    「생성이 빠뜨린 열」은 그 질문 더미에 묻혀 보이지 않았다.

    **구판 스키마**(`unmappable` 키 없음)는 차집합 결과를 전부 `undecided`로 본다 —
    「판정해서 뺐다」고 말할 근거가 어디에도 없기 때문이다(하위 호환).
    """
    exp = (getattr(adapter_mod, "ADAPTER", {}) or {}).get("expects") or {}
    declared = schema.get("unmappable")
    if declared is None:
        return [], [{"field": f, "kind": "undecided",
                     "reason": "구판 스키마 — 판정 기록이 없다 "
                               "(generate --resume으로 다시 뽑으면 갈린다)"}
                    for f in _unmapped_labels(exp, adapter_mod)], []
    excluded, undecided = [], []
    for u in declared:
        item = dict(u) if isinstance(u, dict) else {"field": str(u), "reason": ""}
        kind = item.get("kind")
        if kind == "excluded":
            excluded.append(item)
            continue
        if kind != "undecided":
            # **모르면 묻는다** — enum 밖의 값을 조용히 「제외」로 치지 않는다.
            store.append_defect(
                f"unmappable.kind가 닫힌 2값 밖이다 — {kind!r} "
                f"(field={item.get('field')!r})")
            item = {**item, "kind": "undecided"}
        undecided.append(item)
    named = {i.get("field") for i in excluded + undecided}
    orphan = [{"field": lab, "kind": "orphan",
               "reason": "스키마 대장에 없다 — 생성이 빠뜨렸거나 문서 양식이 바뀌었다"}
              for lab in _unmapped_labels(exp, adapter_mod) if lab not in named]
    return excluded, undecided, orphan


def _label_columns(exp, adapter_mod):
    """헤더 라벨 → **실제 열 문자 리스트**. 실물을 못 읽으면 빈 dict (B64 ③)."""
    sample = getattr(adapter_mod, "SAMPLE", None) or exp.get("sample_path")
    if not sample or not Path(sample).exists():
        return {}
    try:
        raw = reader.read(str(sample))
        # **대응을 여기서 다시 짓지 않는다**(B64 ③) — 정규화도 중복 처리도 한 자리다
        # (`preflight.label_columns`). 두 벌이던 동안 한쪽은 `str(v)`, 다른 쪽은
        # `str(v).strip()`이라 같은 셀을 다르게 읽었다(B62 ①-c가 고친 자리).
        return preflight.label_columns(raw, exp)
    except Exception:
        return {}


# ================================================ 열 판정 대장 (B67 ②)
#
# **판단과 코드를 가른다.** 생성 LLM이 열마다 내린 판단(role · 필드↔열 대응 · 안 쓰는
# 열)이 지금까지 **코드 안에만** 살았다 — `adapter.py`·`schema.json`. 그래서 코드를
# 버리면 판단도 버려지고, 코드를 살리면 오류도 산다(실측: G31로 끝난 등록을
# `--resume`하면 같은 G31). 대장은 그 판단만 따로 적어 두는 자리다: 재생성은 코드를
# 새로 받되 **판단은 이어받는다.**
#
# **LLM이 대장을 쓰지 않는다**(C38 「LLM은 고르고, 시스템이 쓴다」) — 요약을 또
# 시키지 않는다. 대장은 산출·판정·지시에서 시스템이 **뽑는** 것이고 전부 결정적이다.
LEDGER_FILE = "columns.json"


def ledger_path(doc_type):
    return _dir(doc_type) / LEDGER_FILE


def read_ledger(doc_type):
    """대장 행 목록 — 없거나 깨졌으면 빈 목록이다."""
    p = ledger_path(doc_type)
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("columns") or []
    except (json.JSONDecodeError, OSError):
        return []


def _save_ledger(doc_type, rows):
    ledger_path(doc_type).write_text(
        json.dumps({"doc_type": doc_type, "at": store._now(), "columns": rows},
                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return rows


def _col_named(text, row):
    """이 문면이 **이 열을 이름으로 부르는가** — 열문자·라벨·필드 중 하나로.

    **못 정하면 건드리지 않는다**가 규칙이라 매칭은 좁게 잡는다: 열문자는 따옴표
    안이거나 `D열`이거나 낱말 경계에 선 것만 센다. 한 글자 열문자가 아무 문장에나
    걸리면 **엉뚱한 행이 미해결로 뒤집힌다.**
    """
    text = text or ""
    for key in (row.get("label"), row.get("field")):
        if key and key in text:
            return True
    col = row.get("col") or ""
    if not col:
        return False
    if f"'{col}'" in text or f'"{col}"' in text or f"{col}열" in text:
        return True
    return re.search(rf"(?<![A-Za-z0-9]){re.escape(col)}(?![A-Za-z0-9가-힣])",
                     text) is not None


def _labels_by_col(exp, mod, samples):
    """열문자 → 헤더 라벨. **표본에서 읽는다** — 어댑터의 `SAMPLE`은 있을 수도 없다.

    대조는 한 함수다(`preflight.label_columns` — B64 ③). 여기서 다시 짓지 않는다.
    """
    out = {}
    for smp in list(samples or []) + [None]:
        try:
            raw = reader.read(str(smp)) if smp else None
            pos = preflight.label_columns(raw, exp) if raw else _label_columns(exp, mod)
        except Exception:
            continue
        for lab, letters in (pos or {}).items():
            for c in letters:
                out.setdefault(c, lab)
        if out:
            return out
    return out


def sync_ledger(doc_type, st, samples=None):
    """산출에서 열 판정을 뽑아 대장을 다시 세운다 — **LLM 0 · 결정적**.

    자리는 **관문 입구**(`stamp_system_fields` 직후)다. 초회·재생성 매번 돌고,
    읽는 것은 셋이다: 확정된 `expects.columns`(C38 스탬프 뒤 열문자) · `schema.json`의
    필드별 role · `unmappable[]`. **행 집합은 열 프로파일이 정한다** — 표본에 있는
    열은 판정됐든 아니든 전부 한 행을 갖는다: 빠진 열이 대장에서도 빠지면
    「생성이 빠뜨렸다」가 보이지 않는다.

    **orphan을 여기서 다시 계산하지 않는다** — `unmappable_of`의 셋째 값을 읽는다.
    계산이 둘이면 한쪽만 고쳐지는 날이 오고, 그날 관문과 대장이 다른 말을 한다.

    `by`(판단 출처)는 **판단이 그대로면 그대로 둔다** — 관문을 다시 돌렸다고
    사람이 정한 열이 「생성이 정했다」로 바뀌면 안 된다.
    """
    prof = {}
    for pp in _profiles(doc_type):
        for col, item in (pp.get("열") or {}).items():
            prof.setdefault(col, item)
    try:
        mod = _load(draft_mod._at(st["adapter"]), f"led_{doc_type}")
        schema = json.loads((draft_mod._at(st["schema"])).read_text(encoding="utf-8"))
    except Exception:
        return read_ledger(doc_type)        # 못 읽으면 관문 ①단이 말한다
    a = getattr(mod, "ADAPTER", {}) or {}
    if a.get("payload_kind") != "table":
        # **prose에는 열이 없다** — 대장을 세우면 본문 열 하나가 「생성이 빠뜨린
        # 열」로 뜬다(거짓). `header_labels`를 table에만 채우는 것과 같은 근거다(D-29).
        ledger_path(doc_type).unlink(missing_ok=True)
        return []
    exp = a.get("expects") or {}
    fields, _blocks = load_blocks(schema)
    field_of = {}
    for f, v in (exp.get("columns") or {}).items():
        for c in (v if isinstance(v, (list, tuple)) else [v]):
            field_of.setdefault(str(c), f)
    label_of = _labels_by_col(exp, mod, samples or st.get("samples"))
    kind = {}
    for u in unmappable_of(schema, mod)[0]:
        kind[u["field"]] = ("decided", "UNMAPPABLE")
    for u in unmappable_of(schema, mod)[1]:
        kind[u["field"]] = ("open:undecided", None)
    for u in unmappable_of(schema, mod)[2]:
        kind[u["field"]] = ("open:orphan", None)
    prev = {r.get("col"): r for r in read_ledger(doc_type)}
    by_now = f"generate rev{st.get('revision', 0)}"
    rows = []
    # **프로파일 열 + 어댑터가 쓰는 열의 합집합으로 돈다**(B76 ②). 프로파일은
    # 리허설이 읽은 머리(`--rows` 안)라 어댑터가 쓰는 열이 그 밖일 수 있고, 그러면
    # **스키마에 있어도 대장에 행이 없는 필드**가 생긴다 — 그 필드는 기계 제안
    # 대조와 「이어가기」에서 조용히 빠졌다(사내 실측 열다섯째의 둘째 원인).
    # 합치기 리스트는 열마다 행 하나다(같은 `field`).
    cols = sorted(set(prof) | set(field_of),
                  key=lambda c: (len(str(c)), str(c)))
    for col in cols:
        lab, fld = label_of.get(col), field_of.get(col)
        st_role = kind.get(lab, (None, None))
        role = (fields.get(fld) or {}).get("role") if fld else st_role[1]
        status = "decided" if fld else (st_role[0] or "open:orphan")
        row = {"col": col, "label": lab, "role": role, "field": fld,
               "by": by_now, "status": status}
        old = prev.get(col)
        if old and (old.get("role"), old.get("field")) == (role, fld) and old.get("by"):
            row["by"] = old["by"]           # 판단이 그대로면 출처도 그대로
        elif old and not fld and str(old.get("by") or "").startswith(
                ("interview", "instruct")):
            # **사람이 정한 것을 산출이 지우지 않는다**(B67 ② — 이 회차의 성질).
            # 코드가 아직 그 열을 쓰지 않을 뿐이고, 그 사실은 `status`가 말한다:
            # role은 사람의 것, status는 산출의 것 — 둘이 갈린 것이 지금 상태다.
            row["role"], row["by"] = old.get("role") or role, old["by"]
        rows.append(row)
    return _save_ledger(doc_type, rows)


def mark_ledger_fails(doc_type, fails):
    """관문 FAIL이 **이름을 부른 열**에 미해결 태그를 단다 — `open:G26`.

    판정이 그 열을 말하는데 대장이 `decided`로 남아 있으면, 대장을 보고 넘어간
    사람이 막힌 자리를 못 본다.
    """
    rows = read_ledger(doc_type)
    if not rows:
        return rows
    for r in rows:
        for code, _label, detail in fails or []:
            if _col_named(detail, r):
                r["status"] = f"open:{code}"
                break
    return _save_ledger(doc_type, rows)


def apply_to_ledger(doc_type, text, by):
    """문답의 확정 사항·사람 지시를 대장에 반영한다 — **매칭은 결정적이다**.

    `apply_instruction_to_decisions`(B60 ②)와 같은 규칙이다: 문면이 어느 열을
    이름으로 부르면 그 행을, 아니면 아무 행도 건드리지 않는다. **추측으로 행을
    고치지 않는다** — 어느 열인지 못 정한 지시는 이력(`instructions`)에만 남는다.

    role 이름이 문면에 **정확히 하나** 있으면 그 행의 role로 삼는다. 둘 이상이면
    무엇을 고르는지가 판단이라 손대지 않는다.
    """
    rows = read_ledger(doc_type)
    if not rows or not (text or "").strip():
        return 0
    named = [r for r in draft_mod._ROLES if re.search(rf"(?<![A-Za-z]){r}(?![A-Za-z])", text)]
    hit = 0
    for r in rows:
        if not _col_named(text, r):
            continue
        if len(named) == 1:
            r["role"] = named[0]
        r["by"], r["status"], hit = by, "decided", hit + 1
    if hit:
        _save_ledger(doc_type, rows)
    return hit


def apply_decisions_to_ledger(doc_type, decisions):
    """문답의 `decisions[]` — 항목마다 그 문면이 부른 열에 반영한다."""
    hit = 0
    for d in decisions or []:
        rd = d.get("round")
        hit += apply_to_ledger(
            doc_type, " ".join(str(d.get(k) or "") for k in ("topic", "decision")),
            f"interview r{rd}" if rd is not None else "interview")
    return hit


def ledger_block(doc_type, rows=None):
    """대장 한 줄에 한 열 — 관문 화면·`status`가 같은 블록을 쓴다 (B67 ③)."""
    rows = read_ledger(doc_type) if rows is None else rows
    if not rows:
        return ""
    out = [f"  열 판정 대장 — {len(rows)}열 "
           f"({sum(1 for r in rows if str(r.get('status')).startswith('open')) or 0}건 미해결)"
           f"  {paths.show(ledger_path(doc_type))}"]
    for r in rows:
        out.append(f"     {r.get('col'):<3} {str(r.get('label') or '(헤더 없음)')[:16]:<18}"
                   f" role {str(r.get('role') or '—'):<11}"
                   f" 필드 {str(r.get('field') or '—')[:18]:<20}"
                   f" {r.get('status')}  ← {r.get('by')}")
    return "\n".join(out)


def gate_verdict(harness_ok, parses_ok, orphan):
    """기계 관문의 판정 — **셋이 모두 참이어야 PASS**다 (§6.6-6 · B49).

    `orphan`(스키마 대장에 없는 열)이 여기 있는 이유: 판정되지 않은 열이 있는 채로
    확정되면 **그 열은 영영 안 보인다** — 등록부에 오른 스키마가 그 열을 모르므로
    인입도, 검수도, 질의도 그 열을 지나친다. 사람이 판정할 것이 아니라 대장이
    어긋난 것이므로 질문이 아니라 관문이다.
    """
    return "PASS" if (harness_ok and parses_ok and not orphan) else "FAIL"
