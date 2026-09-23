# -*- coding: utf-8 -*-
"""칸 1.5 — **관문의 닫힌 표**: 허용 role·금지 import·자기완결 연산·형 표.

표와 기계를 가른다 — 무엇을 허용하는가는 **표 하나가 정본**이고(06 대장 1.5),
그것을 어떻게 재는가는 옆 파일들이다. 표가 코드에 섞여 있으면 「무엇이 규격인가」를
사람이 코드를 읽어 추려야 한다.

**킷은 `core`를 import하지 않는다**(문서 6 §6.7) — 여기도 같다.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# 레포 루트를 import 경로에 넣는다 — 킷은 독립 실행 스크립트다(sys.path 조작 허용 자리).
import sys                                                  # noqa: E402
sys.path.insert(0, str(ROOT))

ROLES = {"anchor", "entity", "attribute", "content", "meta"}
BANNED_IMPORTS = {"requests", "urllib", "httpx", "openai", "anthropic", "socket"}

# 규약 10(B31) — 자기완결 연산을 어댑터가 재구현하면 여기서 잡는다.
# **AST로 함수 정의를 본다**(문자열 검색이 아니다): 주석·docstring에 이름이 나오는
# 것과 실제로 정의한 것은 다르고, 이 프로젝트는 문자열을 세어 있는 것처럼 보고한
# 실사고를 겪었다.
SELFMADE = {"_expand_merged", "_col_to_idx", "_idx_to_col", "_col", "_resolve_ditto",
            "_split_multi", "_ditto", "_expand_multi"}

# 구조 필드 — role 배정 대상이 아닌 것들(C17). 공용 블록이 선언하지 **않는** 것만 여기 둔다.
# `process_group`·`process_ref`·`process_no`·`source_locator`는 `schemas/blocks.json`이
# 소유하므로 아래에 중복해 적지 않는다 — 적어 두면 블록 파일이 바뀌어도 하네스가 모른다.
STRUCT_ONLY = {"electrode_type", "context", "doc_type", "section"}
BLOCKS_PATH = ROOT / "schemas" / "blocks.json"   # 킷은 core를 import하지 않는다


def load_blocks(schema, path=None):
    """`use_blocks` 로더 — 스키마가 선언한 공용 블록을 **전개해서** 합친다.

    실행검증_1차 §4.4의 처방이다: 좌표 필드를 `process_coord`에 위임한 스키마는
    `fields`에 좌표가 없어 **role 루프 드라이런의 `anchor`가 0으로 찍혔다**. 스키마는
    옳고 하네스가 미완이었다 — 블록을 조립하지 않으면 anchor 경로가 검사되지 않는다.

    돌려주는 것은 `(합쳐진 fields, 블록 유래 필드명 집합)`이다. 블록 유래 필드는
    **선언된 필드**이므로 `unknown_field` 계산에서 빠지고, role 루프에는 **들어간다.**
    """
    p = Path(path or BLOCKS_PATH)
    blocks = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    merged, from_blocks = dict(schema.get("fields") or {}), set()
    for name in schema.get("use_blocks") or []:
        blk = blocks.get(name)
        if not isinstance(blk, dict):
            continue
        for f, spec in blk.items():
            if f.startswith("_") or not isinstance(spec, dict):
                continue
            from_blocks.add(f)
            merged.setdefault(f, spec)          # 스키마 선언이 블록을 이긴다
    return merged, from_blocks

# **공개 API는 모듈이 정본이다**(B65 ①) — 목록을 여기 베끼면 normalizer가 자랄 때
# 관문이 옛 목록으로 판정하고, 그 거짓 검출을 지우려 다시 베끼게 된다.
from parser import normalizer as normalizer_mod            # noqa: E402

NORMALIZER_API = tuple(x for x in dir(normalizer_mod) if not x.startswith("_")
                       and callable(getattr(normalizer_mod, x)))


# ---------------------------------------------------------------- ① 형 검사 (B76 ①)
# **LLM 산출의 키마다 허용 형** — 닫힌 표 하나가 정본이다(06 대장 1.5).
#
# 왜 있나: 관문 G4A~G4E는 **키의 존재·어휘**만 재고 **값의 형**은 재지 않았다.
# 그래서 「리스트가 와도 되는 자리」와 「안 되는 자리」가 코드에만 암묵으로 있었고,
# 관문 PASS 뒤의 코드가 형을 가정하다 죽었다(사내 실측 열다섯째:
# `TypeError: unhashable type: 'list'` — 합치기 리스트를 dict 키로 넣었다).
#
# 경로 문법: `a.b` 키 · `*` 딕셔너리의 값 전부 · `[]` 리스트의 원소 전부.
# 형: `str` · `int` · `str[]`(문자열 리스트) · `str|str[]`(합치기 허용 — B64 ①).
SHAPE_SCHEMA = {
    "fields.*.role": "str",
    "fields.*.category": "str",
    "fields.*.attach_to_field": "str",
    "fields.*.attr_name": "str",
    "fields.*.정의문": "str",
    "edges[].from": "str",
    # **실물 키는 `relation`이다** — 요청문의 `rel`은 같은 자리의 별명이고,
    # 스키마·G4D·G48이 전부 `relation`을 읽는다(D-155 ①).
    "edges[].relation": "str",
    "edges[].to": "str",
    "unmappable[].field": "str",
    "unmappable[].kind": "str",
    "unmappable[].reason": "str",
}
SHAPE_SCHEMA_ENUM = {"unmappable[].kind": ("excluded", "undecided")}

SHAPE_ADAPTER = {
    "doc_type": "str",
    "payload_kind": "str",
    "adapter_version": "str",
    "expects.columns.*": "str|str[]",       # 합치기 리스트는 **허용**이다(B64 ①)
    "expects.header_labels": "str[]",
    "expects.header_row": "int",
    "expects.sample_path": "str",
}

# 표에 없는 키를 세는 자리 — 「모양이 늘었다」는 판정이 아니라 보고다.
SHAPE_KNOWN_SCHEMA = ("doc_type", "schema_version", "layer", "use_blocks",
                      "fields", "edges", "unmappable")
SHAPE_KNOWN_ADAPTER = ("doc_type", "adapter_version", "payload_kind", "expects",
                       "SAMPLE")


# **구조 필드의 정본은 `core/build/loop.py::STRUCTURAL`이다** — 여기 베끼지 않는다.
# import하지 않는 이유: `core.build`가 `core.llm`을 끌고 오고, 관문은 스스로
# 「LLM 미적재」를 판정한다(G54). 그래서 `_kit_line_re`와 같은 결로 **소스에서
# 상수만 뽑는다** — 못 찾으면 조용히 넘기지 않고 그 판정을 붉게 한다.
_STRUCTURAL_SRC = Path(__file__).resolve().parent.parent / "core" / "build" / "loop.py"
G39 = "G39  어댑터가 내는 키가 전부 스키마 fields에 있다"
# **라벨 한 자리**(B59 ①) — G26은 한 태그·한 라벨이고 원인은 상세가 가른다.
G26 = "G26  columns 값이 header_row의 헤더로 확정된다"


def structural_fields():
    """`{구조 필드…}` 또는 빈 집합(못 읽었다는 뜻)."""
    try:
        tree = ast.parse(_STRUCTURAL_SRC.read_text(encoding="utf-8"))
    except OSError:
        return set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
                getattr(t, "id", "") == "STRUCTURAL" for t in node.targets):
            try:
                v = ast.literal_eval(node.value)
            except ValueError:
                return set()
            return set(v) if isinstance(v, (set, list, tuple)) else set()
    return set()


# ── 관문 입력의 자리 — 부가 자료는 CLI가 주고 **여러 곳이 읽는다**(B78 2c).
# 값이 실행기 안에만 있으면 검사 쪽이 그것을 못 본다(모듈이 갈렸다).
PKG_FLAG = "--package"
PACKAGE = None

# 층 자산의 자리 — **킷은 `core`를 import하지 않는다**(문서 6 §6.7). 그래서
# `paths.layers()`를 부를 수 없고, 하네스는 subprocess라 함수 주입도 닿지 않는다.
# 등록 흐름은 CLI가 `--layers <자리>`로 건네주고(상태 루트), 단독 실행은 레포
# `layers/`를 본다 — 킷은 레포 자산이고 그 기준은 레포다(B79 ①).
LAYERS_FLAG = "--layers"
LAYERS_DIR = None


def layers_dir():
    """층 자산 폴더 — 건네받은 자리가 있으면 그것, 없으면 레포 seed."""
    return Path(LAYERS_DIR) if LAYERS_DIR else (ROOT / "layers")


# 좌표 층의 **이름도 건네받는다**(B85 ② — `--layers`와 같은 결). 좌표 층은
# 「`Process` 카테고리를 선언한 층」이고 그 판정은 `core`가 한다 — 킷은 core를
# 모르므로 CLI가 답을 넘긴다. 단독 실행이면 스키마의 층으로 떨어진다.
COORD_FLAG = "--coord-layer"
COORD_LAYER = None

# 골격 닫힌 목록 **파일**도 건네받는다(B86 ② — `--layers`와 같은 결). 파서의
# 주입 전 기본값이 없으므로 킷이 받지 못하면 좌표 대조를 **생략하고 그렇게 말한다**.
CLOSED_FLAG = "--closed-list"
CLOSED_LIST = None

# 표본의 **시트 역할 표**(B86 ⑤) — `{표본 절대 경로: {시트: 역할}}`. 킷은 doc_id
# 규칙을 모르므로 경로가 키다. 없으면 시트 전부를 돈다(단독 실행 · 시트 하나).
SHEET_ROLES_FLAG = "--sheet-roles"
SHEET_ROLES = None


# 열 판정 대장의 자리 — **관문은 그것을 계산하지 않고 읽는다**(B76 ②).
# 없으면 커버리지 검사를 돌리지 않는다: 킷은 등록 흐름 밖에서도 단독으로 돈다.
LEDGER_FLAG = "--ledger"
LEDGER = None
