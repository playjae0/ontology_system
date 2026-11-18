# -*- coding: utf-8 -*-
"""칸 1.2 · 1.6 — **등록 표본의 시트 역할** — 인입과 같은 관문을 표본마다 건다 (B86 ⑤).

사내 실측(2026-09-23): 시트 수십 장짜리 산문 엑셀을 `register generate`로 등록하면
검수 리허설과 킷 관문이 **시트 전부**를 돌았다 — 추출 리허설을 켜면 가격·일정 시트까지
추출 LLM을 탔고, 그 시점에 표본이 `data/`에 인입됐다. B83이 관문을 `ingest-file`·
`parse run`에만 붙였다.

등록은 「이 **종류**를 어떻게 읽나」라 시트를 정하는 자리가 아니다 — 다만 **표본도
문서 하나**이므로 인입과 같은 관문(`cli/sheet_gate.gate`)을 건다. 답은 같은 자리
(`registry/sheet_roles/<doc_id>.json` — 리허설은 운영 doc_id를 쓴다 · B55 ⑤)에 남아
**같은 파일을 나중에 인입하면 다시 묻지 않는다.**
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from cli import sheet_gate as SG
from core import paths
from core.state import sheets as SH
from cli.register import draft as draft_mod


def _kind_of(st, kind=None):
    """갈래(B214 ①) — **등록 스키마**(`kind` — `--variant` · `--revise`) → **작업 자리 초안 스키마** → 둘 다 없으면 None
    (관문이 읽음 시트에서만 형태를 잰다 — `sheet_gate.one_form` · `draft.read_sample(judge=True)`)."""
    sc = (st or {}).get("schema")
    if sc and draft_mod._at(sc).exists():
        return json.loads(draft_mod._at(sc).read_text(encoding="utf-8")).get("payload_kind") or "table"   # 생략 = 표
    return kind


def _adapters(doc_type):
    """등록된 doc_type(변형 이름이면 그 doc_type)의 어댑터 전부 — 읽음 제안의 헤더 지문(B214 ③) · 첫째가 기본 변형."""
    from core.state import registry
    from cli.register import variant as variant_mod
    return [registry.at(v["adapter"]) for _n, v in registry.variants_of(variant_mod.split(doc_type)[0])]


def sample_roles(doc_type, st, samples, *, spec=None, layer=None, kind=None):
    """표본마다 관문을 걸고 `{표본 절대 경로: 역할}`을 돌려준다(역할 없는 표본은 빠진다).

    `--sheets`는 **표본이 하나일 때만** 받는다 — 번호는 문서마다 다른 시트를 가리킨다
    (D-164 ③과 같은 이유). 비대화형이면 인입과 같이 **상태 거부**다.
    """
    from cli.ingest import doc_id_of              # 리허설도 운영 doc_id다 (B55 ⑤)
    hold(doc_type, samples)                       # 이미 인입된 표본은 운영 기록을 쓰지 않는다 (B116 ①)
    if spec and len(samples) > 1:
        raise SystemExit("[등록] --sheets는 표본이 하나일 때만 준다 — 표본이 여럿이면 "  # [사용법]
                         "표본마다 관문이 뜬다(문서마다 시트 자리가 다르다)")
    lay = layer or (st or {}).get("layer") or "<층>"
    out = {}
    for s in samples:
        roles, stop = SG.gate(
            s, doc_id_of(s), _kind_of(st, kind), spec=spec, ask=True, adapters=_adapters(doc_type),
            retry=f"python -m cli.register generate {doc_type} {lay} {s}",
            flag_cmd=(f"python -m cli.register generate {doc_type} {lay} {s} "
                      f'--sheets "{{sheets}}"'))
        if stop is not None:
            raise SystemExit(f"[등록] 표본 {Path(s).name}의 시트 역할이 정해지지 않았다 — "  # [상태]
                             f"{stop['reason']}\n"
                             f"  근거 — {paths.show(SH.path(doc_id_of(s)))} 없음\n"
                             f"  ▶ 다음 줄 — 위 블록의 `--sheets \"…\"` 줄, 또는 터미널에서: "
                             f"python -m cli.register generate {doc_type} {lay} {s}")
        if roles:
            out[str(Path(s).resolve())] = roles
    return out


def _read_sheet(roles):
    """시트 둘 이상인 표본의 읽음 시트 이름(하나일 때) 또는 None."""
    reads = [n for n, r in (roles or {}).items() if r == "read"]
    return reads[0] if len(roles or {}) >= 2 and len(reads) == 1 else None


def sheet_fact(roles_map, kind):
    """**생성 입력의 사실 한 줄**(B214 ④) — 표 계열 · 시트 둘 이상인 표본의 읽음 시트 · 아니면 빈 글.
    계열을 모르면(새 등록) 그 읽음 시트 하나만 형태를 잰다."""
    from parser import form as form_mod, reader as reader_mod
    out = []
    for s, roles in (roles_map or {}).items():
        n = _read_sheet(roles)
        if n and (kind or form_mod.judge_sheets(reader_mod.read(s)).get(n)) == form_mod.TABLE:
            out.append(f"[시트 역할 기록] {Path(s).name}: 읽을 시트 '{n}' — 어댑터 `expects.sheet`에 이 이름을 적는다")
    return "\n".join(dict.fromkeys(out))


def sheet_check(st, roles_map, ok, out):
    """**G4S**(B214 ④) — 표 계열 · 시트 둘 이상인 표본이 있는데 초안 어댑터에 `expects.sheet`가 없으면 FAIL · `(ok, out)`."""
    need = [n for n in map(_read_sheet, (roles_map or {}).values()) if n]
    if _kind_of(st) != "table" or not need:
        return ok, out
    have = SG._named(draft_mod._at(st["adapter"]))
    line = (f"  [{'PASS' if have else 'FAIL'}] G4S  여러 시트 표본의 표 어댑터는 expects.sheet로 읽을 시트를 적는다  — "
            + (f"expects.sheet '{have}'" if have else f"expects.sheet 없음 — 읽을 시트 '{need[0]}'(시트 역할 기록)를 expects.sheet에"))
    return ok and bool(have), out.rstrip("\n") + "\n" + line + "\n"


def hold(doc_type, samples):
    """**이미 인입된 표본의 시트 역할은 그 등록의 검수 자리에서**(B116 ① — 등록은 운영 상태 중 등록 자리만 바꾼다):
    `registry/review/<dt>/sheet_roles/<doc_id>.json` · 비어 있으면 운영 기록을 읽기만 한다. 아직 넣지 않은 표본은
    지금 그대로 운영 기록에 쓴다 — 같은 파일을 나중에 인입하면 다시 묻지 않는다(B86 ⑤)."""
    from cli.ingest import doc_id_of
    from core.state import store
    reg = store.read(store.DOC_REGISTRY, {})
    SH.hold({doc_id_of(s): paths.review(doc_type, SH.DIRNAME, f"{doc_id_of(s)}.json")
             for s in samples if doc_id_of(s) in reg})


def held_spec(doc_id):
    """겹침 자리의 역할이 운영 기록과 다르면 그 역할의 `--sheets` 문자열(시트 순서 번호) · 같거나 겹침이 없으면 None."""
    p = SH.path(doc_id)
    if p == SH.operational(doc_id) or not p.exists():
        return None
    held = (SH.read(doc_id) or {}).get("sheets") or {}
    op = json.loads(SH.operational(doc_id).read_text(encoding="utf-8")).get("sheets") \
        if SH.operational(doc_id).exists() else None
    if held == op:
        return None
    return " ".join(f"{i}:{r}" for i, r in enumerate(held.values(), 1))


def roles_file(roles_map):
    """킷에 건넬 **역할 표 파일** — 관문 임시 파일이다(관문 산출은 관문이 치운다).

    킷은 `core`를 모르고 doc_id 규칙도 모른다 — 그래서 표본의 **절대 경로**를 키로
    건넨다. 비어 있으면 파일을 만들지 않는다(`None`).
    """
    if not roles_map:
        return None
    fd, name = tempfile.mkstemp(prefix="gate_sheet_roles_", suffix=".json")
    with open(fd, "w", encoding="utf-8") as f:
        json.dump(roles_map, f, ensure_ascii=False)
    return name

