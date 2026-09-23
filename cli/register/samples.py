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


def _kind_of(st, sample):
    """갈래 — **초안 스키마가 있으면 그것**, 없으면(생성 입구) 표본의 형태 판정이다.

    생성 입구에서 묻는 이유: 초안(LLM)을 받기 **전에** 정해야 비용이 헛되지 않는다.
    그 자리에는 스키마가 아직 없어 형태 판정으로 가른다 — 표로 판정된 표본만 관문을
    건너뛴다(기권은 산문 쪽으로 — 시트 전부를 도는 갈래일 수 있다 · D-164 ①의 결).
    """
    sc = (st or {}).get("schema")
    if sc and draft_mod._at(sc).exists():
        return json.loads(draft_mod._at(sc).read_text(encoding="utf-8")).get("payload_kind")
    from parser import form as form_mod, reader as reader_mod
    try:
        verdict = form_mod.judge(reader_mod.read(str(sample)))["verdict"]
    except reader_mod.MissingDependency:
        raise
    except Exception:                                   # noqa: BLE001 — 판정 불가는 산문 쪽
        verdict = None
    return "table" if verdict == "table" else "prose"


def sample_roles(doc_type, st, samples, *, spec=None, layer=None):
    """표본마다 관문을 걸고 `{표본 절대 경로: 역할}`을 돌려준다(역할 없는 표본은 빠진다).

    `--sheets`는 **표본이 하나일 때만** 받는다 — 번호는 문서마다 다른 시트를 가리킨다
    (D-164 ③과 같은 이유). 비대화형이면 인입과 같이 **상태 거부**다.
    """
    from cli.ingest import doc_id_of              # 리허설도 운영 doc_id다 (B55 ⑤)
    if spec and len(samples) > 1:
        raise SystemExit("[등록] --sheets는 표본이 하나일 때만 준다 — 표본이 여럿이면 "  # [사용법]
                         "표본마다 관문이 뜬다(문서마다 시트 자리가 다르다)")
    lay = layer or (st or {}).get("layer") or "<층>"
    out = {}
    for s in samples:
        roles, stop = SG.gate(
            s, doc_id_of(s), _kind_of(st, s), spec=spec, ask=True,
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

