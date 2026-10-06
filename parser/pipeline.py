# -*- coding: utf-8 -*-
"""칸 2.5·2.9 — 파서 진입점 — 코어 6종을 순서대로 엮는다 (파서_명세 §3 · D-2 확정 배열).

    reader → preflight → [struct-map] → adapter → normalizer → tagger → validator

**실패는 문서 단위 단일이다**(C14). 어느 단계에서 걸리든 그 문서는 통째로 나가지
않고 사유가 붙은 결과가 나온다 — 에이전트 측 인입은 그 결과를 받아 큐에 싣는다.
파서는 큐 파일을 직접 쓰지 않는다: 파서는 별도 프로그램이고 결합은 JSON뿐이다(D-9).

돌려주는 것: `ParseResult(ok, envelope, failures, report)`.
`failures`는 `[{kind, reason, detail}]`이고 kind는 **닫힌 20종 안**이다 —
`parse_failure` · `adapter_mismatch` · `hierarchy_unresolved` 셋만 쓴다(신설 0).
"""
from __future__ import annotations

import logging

import inspect
import sys

from . import normalizer, preflight, struct_map, struct_rule, tagger, validator
from .reader import head, read

_LOG = logging.getLogger("onto.parser.pipeline")

PARSER_VERSION = "p1-1.0"


class ParseResult:
    def __init__(self, doc_id):
        self.doc_id = doc_id
        self.ok = False
        self.envelope = None
        self.failures: list[dict] = []
        self.report: dict = {}

    def fail(self, kind, reason, detail=None):
        self.failures.append({"kind": kind, "reason": reason, "detail": detail or {}})
        return self

    def __repr__(self):
        return (f"<Parse {self.doc_id} {'ok' if self.ok else 'fail'} "
                f"failures={[f['kind'] for f in self.failures]}>")


def _mock_log(doc_id, point, detail):
    """대체 갈래가 실제로 도는 자리를 **로그로 남긴다**(문서 7 §7.8 3종 중 하나).

    표준출력으로만 나가면 자동 점검이 세지 못해 비어 있는 지점이 구현된 것으로
    보고된다. **조건은 「함수가 없다」이지 「모드가 mock이다」가 아니다**(B48) —
    파서는 모드를 읽지 않는다.
    """
    logging.getLogger("onto.parser").info("MOCK %s [%s] — %s", point, doc_id, detail)


def _map_basis(smap):
    """지도 경로의 `분할_기준` — 어느 지도로 잘랐나 (B68 ①)."""
    if smap.get("unavailable"):
        return "구조 지도 없음 — 평면 폴백"
    if smap.get("source") == "heuristic":
        return "구조 지도(heuristic)"
    return f"구조 지도(LLM · 판본 {smap.get('prompt_version') or '미상'})"


def _map_hook(doc_id, kept=None, made=None, seen=None, ask=None, src_hash=None):
    """어댑터에 주입할 지도 패스 — **코어가 소유한다**(어댑터는 LLM을 부르지 않는다).

    `kept`는 보존분의 프레임별 지도(`{key: smap}`), `made`는 이번 인입에서 새로
    산출된 것을 담을 자리다. **한 문서가 여러 프레임(시트·슬라이드)을 가지므로 지도는
    프레임 키로 갈라 담는다** — 보존 파일은 문서 하나에 하나이고(§6.3), 그 안에서
    `maps[key]`로 나뉜다. 재사용은 호출부가 `source_hash`로 이미 판정한 뒤이므로
    여기서는 «있으면 쓴다»만 한다.
    """
    kept = kept or {}
    def hook(key, lines, locator):
        hit = kept.get(key)
        if hit is not None:
            return hit
        # `apply()`는 **3짝**을 돌려준다 — 어댑터가 그대로 풀어 쓴다.
        # **프레임 키는 인자다** — 구판은 `f"{doc_id}:{key}"`를 doc_id 자리에 넣어
        # 별도 파일 `{doc_id}:{key}.json`을 만들었고, 그 경로가 `src_hash` 없이
        # 재사용돼 원본이 바뀌어도 옛 지도가 살아났다(B55 ④). 지도는 문서 파일
        # 하나 안에서 프레임 키로 갈린다(B16).
        out = struct_map.apply(doc_id, lines, locator, ask=ask,
                               src_hash=src_hash, frame=key)
        _chunks, smap, _reasons = out
        # **사유 지도는 보존분에 담지 않는다**(문서 6 §6.3 · [정정] 39). `propose`가
        # 프레임 단위로 안 담아도, 여기서 담으면 문서 단위 보존 파일에 실려 재인입이
        # 그것을 재사용한다 — 한도를 올려도 **영영 평면**이다.
        if made is not None and not smap.get("unavailable"):
            made[key] = out
        if seen is not None:
            # **선택 레벨과 레벨별 분포를 밖으로 흘린다**(B45) — 검수 뷰가 그리려면
            # 값이 뷰 데이터에 있어야 하고, 렌더러는 계산하지 않는다(§6.6-3).
            # **출처와 지시문 판본도 함께 흘린다**(B48 ②-7) — 휴리스틱 지도는
            # 보존하지 않으므로, 이 값이 없으면 «어느 지도가 실호출이었나»가
            # 디스크 어디에도 남지 않는다. 검수 뷰와 재인입 판정이 그것을 본다.
            seen.append({"프레임": key, "분할_레벨": smap.get("분할_레벨"),
                         "분할_레벨_사유": smap.get("분할_레벨_사유"),
                         "레벨_분포": smap.get("레벨_분포"),
                         "지도_출처": smap.get("source"),
                         # **한 필드 이름, 두 경로**(B68 ①) — 어댑터 경로의
                         # `분할_기준`과 같은 자리·같은 이름이다.
                         "분할_기준": _map_basis(smap),
                         "지시문_판본": smap.get("prompt_version"),
                         "지도_없음": smap.get("unavailable")})
        return out
    return hook



def _page_map(path, raw):
    """슬라이드/페이지 index → 쪽 렌더 PNG. **숨김이 쪽 번호를 민다.**

    LibreOffice는 PPTX를 PDF로 낼 때 **숨긴 슬라이드를 빼고** 찍는다(실측: 10장
    중 1장 숨김 → 9쪽). 그래서 `pages[10]`이 10번 슬라이드가 아니다 — 보이는
    슬라이드만 세어 이어 붙여야 그림과 쪽이 어긋나지 않는다. 어긋나면 ④가
    **다른 슬라이드를 보고** 요약하고, 그 문장이 근거로 실린다.

    렌더가 없으면 빈 dict다 — 호출부가 `slide_render="none"`을 데이터에 남긴다.
    """
    try:
        from . import render
        got = render.render_pages(path)
    except Exception as e:                                  # noqa: BLE001
        _LOG.warning("쪽 렌더 실패 — %s: %s", type(e).__name__, e)
        return {}
    if not got:
        return {}
    slides = raw.get("slides")
    if slides is None:                                      # PDF — 쪽이 곧 index
        return got
    visible = [s["index"] for s in slides if not s.get("hidden")]
    if len(visible) != len(got):
        # **셈이 안 맞으면 붙이지 않는다** — 틀린 쪽을 보내느니 없는 편이 낫다.
        _LOG.warning("쪽 렌더 %d장 · 보이는 슬라이드 %d장 — 대응이 서지 않아 "
                     "쪽 그림을 붙이지 않는다", len(got), len(visible))
        return {}
    return {idx: got[n] for n, idx in enumerate(visible, start=1)}


def _convert_images(res, pieces, imgs, kept_img):
    """모델이 받지 않는 형식(WMF·EMF …)을 PNG로 — 못 바꾸면 **그 그림만** 건너뛰고 사유를 싣는다.

    보존된 요약이 있는 그림은 바꾸지 않는다(부를 일이 없다). 건너뛴 수는
    `report["read_warnings"]`에 형식별로 남고 화면이 한 줄로 낸다(B86 ④의 그 줄 · B88 ①).
    """
    from . import render
    out, dropped, why = [], {}, set()
    for p in pieces:
        ref = p.get("image_ref")
        blob, mime = imgs.get(ref, (None, None)) if ref else (None, None)
        if not ref or blob is None or mime in render.MODEL_MIMES or ref in kept_img:
            out.append(p)
            continue
        png, reason = render.to_png(blob, mime)
        if png is None:
            kind = (mime or "?").rsplit("/", 1)[-1].replace("x-", "").upper()
            dropped[kind] = dropped.get(kind, 0) + 1
            why.add(reason)
            continue
        imgs[ref] = (png, "image/png")
        out.append({**p, "meta": {**(p.get("meta") or {}), "image_converted_from": mime}})
    if dropped:
        res.report["read_warnings"] = {**res.report.get("read_warnings", {}),
                                       "images_dropped": dropped, "why": sorted(why)}
    return out


def _drop_images(res, pieces, no_images):
    """`ref` 시트의 그림은 조각 0(참조 = LLM 0 · B83) · `--no-images`면 그림 전부 — **기록한다**."""
    out = [p for p in pieces if not (p.get("image_ref")
                                     and (p.get("meta") or {}).get("sheet_role") == "ref")]
    if no_images:
        n = sum(1 for p in out if p.get("image_ref"))
        out = [p for p in out if not p.get("image_ref")]
        if n:
            res.report["images"] = {"요약_안_함": n, "사유": "--no-images"}
    return out


def _parse_images(res, pieces, raw, path, doc_id, summarize, kept_map, kept_maps,
                  made_maps, map_picks, src_hash, made_rules=None, image_notice=None):
    """④ 이미지 요약 — 보존분 재사용과 새로 받은 것의 저장. 돌려주는 것은 조각이다.

    `parse`에서 단계로 떼어냈다(B78 2c) — 지도·요약의 보존 규칙이 한 자리에 모인다.
    """
    # 부르면 text가 흔들려 그 문서의 chunk_id가 전량 이동한다.
    # **원본 파일 바이트 해시**로 재사용을 판정한다 — `doc_hash`는 에이전트 소유라
    # 파싱 시점에는 아직 없다(2A P-D 허브 판정 · §2.7-①).
    kept_img = dict(kept_map.get("image_summaries") or {})
    if summarize is None:
        _mock_log(doc_id, "④이미지 요약",
                  "고정 문자열 + meta.image_summary_source=mock")
    # **바이트와 쪽 그림은 여기서 붙인다**(B53) — 리더 raw가 이 함수의 손에 있고,
    # 어댑터는 순수 함수라 원본 파일을 다시 열 수 없다(§6.4-2).
    imgs = dict(raw.get("_images") or {})
    pieces = _convert_images(res, pieces, imgs, kept_img)
    _refs = [p["image_ref"] for p in pieces if p.get("image_ref") and not p.get("text")]
    if image_notice and summarize is not None and _refs:
        # **부르기 전에** 몇 장인지 말한다(B88 ① · B69 ②의 결) — 보존분은 호출 0이다.
        image_notice({"새": sum(1 for r in _refs if r not in kept_img),
                      "재사용": sum(1 for r in _refs if r in kept_img)})
    # **쪽 전체 렌더는 쪽이 있는 포맷만**(PPT·PDF) — 엑셀·Word에는 쪽이 없다(B88 ①).
    has_pages = raw.get("slides") is not None or raw.get("pages") is not None
    pages = _page_map(path, raw) if (imgs and summarize is not None and has_pages) else {}
    pieces = tagger.complete_images(pieces, summarize, kept=kept_img,
                                    images=imgs, pages=pages)          # ⑤ tagger
    # 보존은 **새로 산출된 것이 있을 때만** 쓴다 — 매번 쓰면 재사용 갈래에서도 파일
    # mtime이 흔들려 «재사용했나»가 파일로 판정되지 않는다.
    fresh = {}
    if made_maps:
        fresh["maps"] = {**kept_maps, **made_maps}
    if made_rules:
        # **계층 규칙 선언도 같은 파일·같은 원본 해시**(B87 ②) — 같은 파일이면 같은 경계다.
        fresh["rules"] = {**(kept_map.get("rules") or {}), **made_rules}
    if kept_img and kept_img != (kept_map.get("image_summaries") or {}):
        fresh["image_summaries"] = kept_img
    if fresh:
        struct_map.keep(doc_id, {**kept_map, "doc_id": doc_id, **fresh}, src_hash)
    # **section에서 좌표를 먼저 세운다**(B43 ④) — 산문의 헤딩 경로가 골격 이름이면
    # 그것이 좌표다. 태깅보다 앞에 두는 이유: 태깅은 좌표가 **있는** 조각을 다듬고,
    # 이것은 좌표가 **없는** 조각에 세운다. 순서가 바뀌면 pick이 헛돈다.
    return pieces


def _parse_coord(res, pieces, a, layer, nodes, pick_coord, coord_cap,
                 coord_notice, progress):
    """⑨ 좌표 태깅 — 닫힌 목록에서 고르고, 못 고른 것은 그 사실을 보고에 남긴다.

    `parse`에서 단계로 떼어냈다(B78 2c).
    """
    # 「몇 종을 물어 몇을 채택했나」가 남아야 한다. 같은 그릇이 두 번 온다(예고·끝).
    _coord = {}

    def _note(info):
        _coord.update(info)
        if coord_notice is not None:
            coord_notice(info)

    pieces = tagger.tag(pieces, layer=layer, nodes=nodes, pick=pick_coord,
                        doc_type=a["doc_type"], progress=progress,
                        notice=_note, cap=coord_cap, doc_id=res.doc_id)
    res.report["coord_tag"] = dict(_coord)

    # 지도 폴백은 실패가 아니라 **표시**다(D-5) — 문서는 들어가고 큐가 뜬다.
    unresolved = [p["source_locator"] for p in pieces
                  if (p.get("meta") or {}).get("hierarchy_unresolved")]
    if unresolved:
        res.fail("hierarchy_unresolved",
                 f"구조 미확정 {len(unresolved)}건 — 평면 폴백으로 실었다",
                 {"locators": unresolved[:10]})
    return pieces


def drop_skipped(raw, sheet_roles):
    """`skip` 시트를 **어댑터가 보기 전에** 뺀다 (B83 ①).

    자르는 자리가 어댑터 안이면 어댑터마다 규칙이 생긴다 — 여기서 한 번 빼면
    어댑터는 「받은 시트 전부」를 지금처럼 돌면 된다(어댑터 코드 변경 0).
    """
    if not sheet_roles or not (raw or {}).get("sheets"):
        return raw
    keep = [s for s in raw["sheets"] if sheet_roles.get(s.get("name")) != "skip"]
    if len(keep) == len(raw["sheets"]):
        return raw
    return {**raw, "sheets": keep}


def mark_roles(pieces, sheet_roles):
    """`ref` 시트에서 온 조각에 `meta.sheet_role`을 단다 (B83 ①·④).

    표시는 **조각이 지고 다니는 사실**이다 — 추출이 부를지, 구축이 결함으로 볼지,
    열람이 보일지를 하류가 이 한 값으로 가른다. `prose` 시트에는 키를 달지 않는다:
    없는 것이 기본이고 있는 것이 예외다(옛 산출과 바이트가 갈리지 않는다).
    """
    if not sheet_roles:
        return pieces
    refs = {n for n, r in sheet_roles.items() if r == "ref"}
    if not refs:
        return pieces
    for p in pieces:
        if (p.get("meta") or {}).get("frame") in refs:
            p["meta"]["sheet_role"] = "ref"
    return pieces


def _read_doc(res, path, sheet_roles, max_rows):
    """① 판독 — 읽고, 버린 그림을 싣고, `skip` 시트를 빼고, 리허설이면 앞 N행으로 자른다.

    `parse`에서 떼어냈다(B86 ④ — 읽기 경고를 싣다가 함수 상한 120행을 넘었다).
    """
    raw = read(path)
    if raw.get("read_warnings"):
        # **읽다가 버린 그림을 리포트에 싣는다**(B86 ④) — 이미지 요약에서 빠지는 것을
        # 사람이 알아야 한다. 화면 한 줄은 호출자가 이 값으로 낸다.
        res.report["read_warnings"] = raw["read_warnings"]
    raw = drop_skipped(raw, sheet_roles)        # `skip` 시트는 어댑터가 보지 않는다
    # **부분 리허설** — 등록 검수의 리허설 파싱을 앞 N행으로 제한한다(2B ⑥-2).
    # 전량 파싱은 좌표 미스 행마다 LLM을 부르므로 수천 행이면 몇 시간이다.
    # `reader.head`가 이미 「앞 N행」의 정의를 갖고 있어 그것을 그대로 쓴다 —
    # 자르는 규칙이 둘이면 「앞 200행」이 자리마다 다른 뜻이 된다.
    # **봉투에 잘랐다는 사실을 싣는다**: 검수 뷰가 그것을 승인 근거로 표시한다.
    full_rows = max((s.get("max_row") or 0) for s in raw["sheets"]) if raw.get("sheets") \
        else len(raw.get("slides") or [])
    truncated = False
    if max_rows and full_rows > max_rows:
        # 바이트(`_images`)는 관찰 재료가 아니라 `head`가 떼어낸다 — ④에는 필요하다
        raw = {**head(raw, max_rows), **{k: v for k, v in raw.items() if k.startswith("_")}}
        truncated = True
    res.report["rehearsal"] = {"max_rows": max_rows, "full_rows": full_rows,
                               "truncated": truncated}
    return raw


def _extract(adapter, raw, doc_id, kept_maps, made_maps, map_picks, map_structure,
             src_hash, rule_fn):
    """③ extract — prose면 지도 훅(⑦)과 **받는 어댑터에만** 규칙 선언 훅(B87 ②)을 건넨다.

    `struct_rule_fn`을 모든 어댑터에 넘기지 않는 이유: 생성 어댑터·다른 기본 어댑터의
    서명은 `extract(raw, struct_map_fn=None)`이고, 모르는 인자를 넘기면 `TypeError`가
    **어댑터 결함처럼** 보인다. 서명을 보고 건넨다.
    """
    if adapter.ADAPTER.get("payload_kind") != "prose":
        return adapter.extract(raw)
    kw = {"struct_map_fn": _map_hook(doc_id, kept_maps, made_maps, map_picks,
                                     ask=map_structure, src_hash=src_hash)}
    if rule_fn is not None and "struct_rule_fn" in _params(adapter.extract):
        kw["struct_rule_fn"] = rule_fn
    try:
        return adapter.extract(raw, **kw)
    except TypeError:
        return adapter.extract(raw)                              # 지도 훅 없는 어댑터


def _params(fn):
    try:
        return inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return {}


def _adapter_attr(adapter, name):
    """어댑터의 이름 — **위임 래퍼면 `extract`의 주인 모듈에서** 찾는다.

    이미 등록된 산문 엑셀 doc_type은 `extract`·`level_report`만 다시 내보내는 래퍼다
    (`registry/review/<dt>/adapter.py` — 사내 등록부에 이미 있다). 래퍼를 다시 만들게 하지
    않고 기본 어댑터의 새 함수(B87 `rule_frames`)가 닿게 한다.
    """
    got = getattr(adapter, name, None)
    if got is None:
        owner = sys.modules.get(getattr(getattr(adapter, "extract", None), "__module__", ""))
        got = getattr(owner, name, None)
    return got


def _rule_hook(adapter, raw, kept_map, made_rules, tally, infer_rules, sheet_roles,
               rule_notice):
    """규칙 선언 훅과 **예고** — 대상 = 고정 규칙으로 안 선 시트(`ref` 시트는 빼고 — LLM 0).

    예고는 **부르기 전에** 낸다: `계층 규칙 — 안 선 시트 n장 → LLM ≤ k회(재사용 m)`.
    돌려주는 것은 `(훅 또는 None, 대상 시트 목록)`이다.
    """
    frames = _adapter_attr(adapter, "rule_frames")
    if not callable(frames):
        return None, []
    skip = {n for n, r in (sheet_roles or {}).items() if r == "ref"}
    targets = [f for f in frames(raw) if f not in skip]
    if infer_rules is None:
        # **대상은 세되 부르지 않는다** — mock · 등록 리허설 · 킷 관문. 검수 화면이
        # 「인입 때 선언 필요」를 이 목록으로 말한다(generate는 파악만 — B87 ②).
        return None, targets
    kept = {f: d for f, d in (kept_map.get("rules") or {}).items() if f in targets}
    if rule_notice and targets:
        rule_notice({"단계": "예고", "대상": len(targets), "재사용": len(kept),
                     "호출_상한": len(targets) - len(kept)})
    return struct_rule.hook(infer_rules, kept=kept, made=made_rules, skip=skip,
                            tally=tally), targets


def parse(adapter, doc_id, path, *, layer=None, revision="R1",
          context=None, closed_list=None, parsed_at="2026-01-05T00:00:00",
          summarize=None, pick_coord=None, map_structure=None,
          max_rows=None, progress=None, coord_notice=None, coord_cap=None,
          sheet_roles=None, infer_rules=None, rule_notice=None, no_images=False,
          image_notice=None):
    """문서 하나를 계약 JSON으로. 어댑터는 모듈(또는 ADAPTER+extract를 가진 객체).

    **LLM 3지점은 함수로 온다**(B48 · 문서 7 §7.6-B-1) — 파서는 모드를 읽지 않는다:

    | 인자 | 지점 | 오면 | 안 오면(§7.1 대체) |
    |---|---|---|---|
    | `summarize(ref, image=, mime=, context=, page=)` | ④이미지 요약 | 실호출 | 고정 문자열 |
    | `map_structure(doc_id, lines)` | ⑦구조 지도 | 실호출 | 번호 패턴 휴리스틱 |
    | `pick_coord(surface, choices)` | ⑨좌표 태깅 | 실호출 | 닫힌 목록 정확 일치 |
    | `infer_rules(frame, sample)` | ⑦ 안의 계층 규칙 선언(B87 ②) | 안 선 시트만 실호출 | 구판과 같다(통째 + 큐) |

    만드는 것은 CLI 진입점이다(`cli.parse.injections()`) — 모드는 거기서 한 번 정해
    아래로 내려온다. 「함수 없이 실호출 모드」는 그 조립 지점이 막는다.

    **`sheet_roles`도 같은 결이다**(B83 ①): `{시트 이름: "prose"|"ref"|"skip"}`을 **데이터로**
    받아 `skip`은 어댑터에 넘기지 않고 `ref` 시트의 조각에 `meta.sheet_role`을 단다.
    파서는 그 값이 어디서 왔는지(사람의 답인지 플래그인지) 모르고 기록도 읽지 않는다 —
    묻는 자리는 CLI의 관문 하나다(「파싱에 대화 없음」 그대로).
    """
    res = ParseResult(doc_id)
    a = adapter.ADAPTER
    exp = a.get("expects") or {}

    raw = _read_doc(res, path, sheet_roles, max_rows)

    # 지도와 이미지 요약은 **같은 보존 규칙**을 탄다(문서 6 §6.3) — 매 인입 새로
    # 부르면 text가 흔들려 그 문서의 chunk_id가 전량 이동한다.
    # **원본 파일 바이트 해시**로 재사용을 판정한다 — `doc_hash`는 에이전트 소유라
    # 파싱 시점에는 아직 없다(2A P-D 허브 판정 · §2.7-①).
    src_hash = struct_map.source_hash(path)
    kept_map = struct_map.load_kept(doc_id, src_hash) or {}
    kept_maps = dict(kept_map.get("maps") or {})
    made_maps, map_picks = {}, []

    ok, detail = preflight.check(adapter, raw)                       # ② preflight
    if not ok:
        return res.fail("adapter_mismatch",
                        f"양식 표류 — 어댑터 '{a['doc_type']}' v{a.get('adapter_version')}",
                        detail)

    made_rules, tally = {}, {}
    rule_fn, targets = _rule_hook(adapter, raw, kept_map, made_rules, tally, infer_rules,
                                  sheet_roles, rule_notice)
    try:                                                             # ③ extract
        pieces = _extract(adapter, raw, doc_id, kept_maps, made_maps, map_picks,
                          map_structure, src_hash, rule_fn)
    except Exception as e:                                           # C14 — 통째 실패
        return res.fail("parse_failure", f"{type(e).__name__}: {e}")
    if targets:
        res.report["struct_rule"] = {**struct_rule.summary(pieces, tally, targets),
                                     "주입": rule_fn is not None}

    pieces, rep = normalizer.normalize(                               # ④ normalizer
        pieces,
        multi_fields=[exp["multi_value_field"]] if exp.get("multi_value_field")
        else list(exp.get("multi_value_fields") or []),
        seps=exp.get("multi_value_seps") or (
            [exp["multi_value_sep"]] if exp.get("multi_value_sep") else None))
    res.report["normalizer"] = rep
    pieces = mark_roles(pieces, sheet_roles)    # `ref` 시트의 조각에 표시를 단다
    pieces = _drop_images(res, pieces, no_images)

    # **층은 호출자가 준다**(B85 ②) — 닫힌 목록을 직접 받은 경우만 층 없이 돈다.
    nodes = closed_list if closed_list is not None else tagger.closed_list(layer)
    # 지도와 이미지 요약은 **같은 보존 규칙**을 탄다(문서 6 §6.3) — 매 인입 새로
    pieces = _parse_images(res, pieces, raw, path, doc_id, summarize, kept_map,
                           kept_maps, made_maps, map_picks, src_hash, made_rules,
                           image_notice)
    pieces = tagger.coord_from_section(pieces, layer=layer, nodes=nodes)
    # **좌표 태깅의 계획과 결과를 리포트에 남긴다**(B69 ②) — 화면이 흘러간 뒤에도
    pieces = _parse_coord(res, pieces, a, layer, nodes, pick_coord, coord_cap,
                          coord_notice, progress)

    env = tagger.envelope(adapter, doc_id, path, pieces, revision=revision,
                          parsed_at=parsed_at, parser_version=PARSER_VERSION,
                          context=context)
    ok, defects = validator.check(env)                               # ⑥ validator
    if not ok:
        return res.fail("parse_failure", "계약 self-check 실패 (문서 단위 — C14)",
                        {"defects": defects})
    # 좌표의 목록 대조는 **보고**다 — 목록 밖 이름의 판정은 인입 소관(orphan_anchor).
    res.report["coords"] = validator.coord_report(env, nodes)

    res.ok, res.envelope = True, env
    res.report["pieces"] = len(pieces)
    # **분할 크기 분포**(B45) — 자르는 규칙은 건드리지 않고 결과만 잰다.
    # **어댑터 경로에도 레벨별 분포를 낸다**(B45 정정 ④) — 사람이 상수를 고를
    # 재료다. 지도 경로가 이미 내는 그 형태를 쓴다: 새 형태를 만들면 화면이 둘로
    # 갈린다. `split_level`을 선언한 어댑터면 고른 값도 함께 보인다.
    if not map_picks and a.get("payload_kind") == "prose":
        # **어댑터가 제 계산을 내놓으면 그것이 정본이다**(B58 ③) — 고정 산문
        # 어댑터는 신호 넷(번호·굵게·들여쓰기·가로병합)으로 계층을 읽는데,
        # `adapter_level_picks`는 번호 패턴 하나만 본다. 두 벌이 다른 답을 내면
        # 화면의 레벨과 실제로 자른 레벨이 갈린다.
        rep = getattr(adapter, "level_report", None)
        picks = rep(raw) if callable(rep) else struct_map.adapter_level_picks(a, raw)
        if picks:
            map_picks = picks
    res.report["split"] = struct_map.split_stats(pieces, map_picks)
    return res
