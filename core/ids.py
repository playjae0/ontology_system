# -*- coding: utf-8 -*-
"""두 축 id — CH6 6.1 규약 2가 산식의 소유처다 (틀 A4·A7, 카드 N1~N4·C7).

**의미 축**(Process·Unit·Property·Failure …) = **발급**, 발급 후 불변(P4).
  개명·alias가 있는 축이라 해시로 만들 수 없다. 방식은 **ULID**(틀 A8-4).
  중앙 카운터가 없으므로 `data/id_seq.json`을 만들지 않는다 — A0 계수 ②가
  0지점이라 마이그레이션 대상도 없다(사용자 판정 08-07로 발효 확정).

**근거 축**(문서·청크·레코드) = **내용에서 계산.**
    doc_id    = 파서 봉투 부여 (해시 아님 — 재인입 단위, 개정 구분은 revision)
    chunk_id  = f"{doc_id}:{sha256(norm(text)+NUL+section+NUL+str(occ))[:12]}"
    record_id = f"{doc_id}:{sha256(norm(join(values,US))+NUL+str(occ))[:12]}"
    occ       = 그 문서 내 동일 (section, norm(text)) 조합의 출현 순번 (0부터)

**계산 주체는 에이전트다**(틀 A7-1). 파서가 내는 것은 doc_id와 source_locator
(문서 내 위치 표기, role=meta)뿐이다. 멱등성의 근거를 사내 파서 구현에 위임하지
않기 위한 배치다.

조절점 **없음** — 산식·절단 길이·norm 규칙은 틀 A4 확정 계약이며 조정 대상이
아니다. 아래 금지 사항은 전부 계약이다:
  - 문서 내 위치(seq)를 해시 입력에 넣지 않는다. 앞 문단이 하나 추가되면
    뒤 전부의 id가 바뀌어 인덱스가 전량 무효가 된다.
  - 충돌 접미(-1, -2 …)를 붙이지 않는다. 처리 순서에 의존하게 되어
    멱등성이 깨진다 — occ가 그 자리를 대신한다.
  - 계산된 id가 이미 존재하면 조용히 덮지 않고 결함 로그를 남긴다.
"""
from __future__ import annotations

import hashlib
import os
import re
import time

NUL = "\x00"    # 구분자 필수 — 없으면 필드 경계가 뭉개져 다른 내용이 같은 해시가 된다
US = "\x1f"     # record의 값 join 구분자
_WS = re.compile(r"\s+")

# ULID (Crockford Base32) — 앞 10자 = 시각(ms), 뒤 16자 = 난수
_B32 = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def new_ulid() -> str:
    """의미 축 id. 시각 접두라 사전순 = 발급순이며 중앙 카운터가 필요 없다."""
    ms = int(time.time() * 1000)
    rnd = int.from_bytes(os.urandom(10), "big")
    n = (ms << 80) | rnd
    return "".join(_B32[(n >> (5 * i)) & 31] for i in range(25, -1, -1))


def is_ulid(s: str) -> bool:
    return isinstance(s, str) and len(s) == 26 and all(c in _B32 for c in s)


def norm(text) -> str:
    """연속 공백 정리 + 앞뒤 공백 제거**까지만**.

    원문은 정규화 없이 그대로 저장한다 — norm은 해시 계산에만 쓴다(카드 C8).
    더 손대면(소문자화·기호 제거 등) 다른 문서가 같은 id를 갖게 된다.
    """
    return _WS.sub(" ", str(text)).strip()


def _h12(s: str) -> str:
    """절단 12자(48비트). 충돌 공간이 doc_id 하나라 유일성에 충분하다."""
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:12]


def chunk_id(doc_id: str, text, section, occ: int) -> str:
    return f"{doc_id}:{_h12(norm(text) + NUL + norm(section) + NUL + str(occ))}"


def record_id(doc_id: str, values, occ: int) -> str:
    """values = 매칭 스키마 `fields`에 선언된 필드의 값들을 **선언 순서로**.

    순서가 산식의 일부다(D-14) — 산식이 "field_values"의 순서를 미지정으로
    두면 처리 순서에 따라 id가 달라진다.
    """
    joined = US.join("" if v is None else norm(v) for v in values)
    return f"{doc_id}:{_h12(norm(joined) + NUL + str(occ))}"


def doc_hash(envelope: dict) -> str:
    """문서 전체 내용 해시 — 중복 문서 차단용(카드 N8, 틀 A6).

    판정 기준은 내용 단일이다. **doc_id·source_path·parsed_at은 제외한다** —
    같은 내용을 다른 파일명으로 넣은 것을 잡아내는 것이 목적이므로, 그것들을
    넣으면 차단이 성립하지 않는다. 파일명·크기는 화면 표시용 참고일 뿐이다(N8).
    """
    payload = envelope.get("records") or envelope.get("chunks") or []
    parts = [norm(envelope.get("doc_type", "")), norm(envelope.get("revision", ""))]
    for frag in payload:
        for k in sorted(frag):
            if k == "source_locator":       # 위치 표기는 내용이 아니다
                continue
            parts.append(f"{k}={norm(frag[k])}")
        parts.append(NUL)
    return hashlib.sha256(US.join(parts).encode("utf-8")).hexdigest()


class OccCounter:
    """문서 하나 안에서 (section, norm(text)) 조합의 출현 순번을 센다.

    같은 텍스트가 같은 섹션에 두 번 나오면 0·1이 되어 id가 갈린다.
    충돌 접미 대신 이것을 쓰는 이유는 **처리 순서와 무관하게 같은 답**이
    나와야 하기 때문이다(조각 순서를 셔플해도 id 집합이 같아야 한다).
    """

    def __init__(self):
        self._seen: dict[tuple, int] = {}

    def next(self, *key) -> int:
        k = tuple(norm(x) for x in key)
        n = self._seen.get(k, 0)
        self._seen[k] = n + 1
        return n
