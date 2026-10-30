# -*- coding: utf-8 -*-
"""칸 2.4 — **표시 상자**(B168 ① — PPT 리더의 곁가지) — 글 없는 도형 · 선 · 연결선을 버리지 않고 쪽마다 따로 모은다.

    collector()                          리더 한 슬라이드의 모음 `{marks, groups, ids, n}`
    mark(m, sh, prefix, geo)             글 없는 도형 하나 → 표시(id · 종류 「표시」 · 위치 · 크기 · 모양 · 색 · 연결선 끝점)
    group(m, sh, gid, recs, mark0, geo)  그룹 하나가 **그림 · 표시 조각뿐**이면 그룹 상자(범위 · 조각 id)
    finish(m)                            연결선 끝점(XML의 도형 번호) → 상자 id · 슬라이드 몫 `{marks, groups}`

모은 것은 리더의 **곁 칸** `raw["_marks"]`(슬라이드 번호 → 몫)에만 산다 — `shapes`(분할 · 청크 · 덱 판단 · 추출 입력)는 그대로다
(B168 경계 — `basic_ppt`가 상자 목록으로 제목만 있는 쪽을 가른다). 판독 입력이 합친다(`parser/reading_pick`). 하나하나 해석하지
않는다 — 캡처를 해석할 때 「무엇이 무엇을 가리키나」의 닻이다. 못 읽은 칸은 None(지어내지 않는다).
"""
from __future__ import annotations

TAG = "M"
KIND = "표시"
GROUP = "그룹"
_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"


def collector():
    return {"marks": [], "groups": [], "ids": {}, "n": 0}


def note(m, sh, ref):
    """리더가 지은 상자 id를 XML 도형 번호에 잇는다(연결선 끝점을 상자 id로 바꾸는 재료)."""
    if m is not None:
        try:
            m["ids"][int(sh.shape_id)] = ref
        except Exception:                                   # noqa: BLE001
            pass


def _shape_name(sh):
    from pptx.enum.shapes import MSO_SHAPE_TYPE
    try:
        st = sh.shape_type
    except Exception:                                       # noqa: BLE001
        st = None
    if sh._element.tag.endswith("}cxnSp"):
        return "연결선"
    if st == MSO_SHAPE_TYPE.LINE:
        return "선"
    if st == MSO_SHAPE_TYPE.FREEFORM:
        return "자유형"
    try:
        return str(sh.auto_shape_type).split(".")[-1].split(" ")[0].lower()
    except Exception:                                       # noqa: BLE001
        return None


def _color(sh):
    """채움 색(단색) 또는 선 색 — `#RRGGBB` · 못 읽으면 None."""
    for get in (lambda: sh.fill.fore_color.rgb, lambda: sh.line.color.rgb):
        try:
            v = get()
            if v is not None:
                return f"#{v}"
        except Exception:                                   # noqa: BLE001
            continue
    return None


def _ends(sh):
    """연결선의 시작 · 끝 도형 번호(XML `a:stCxn` · `a:endCxn`) — 없으면 None."""
    out = []
    for tag in ("stCxn", "endCxn"):
        e = sh._element.find(f".//{_A}{tag}")
        out.append(int(e.get("id")) if e is not None and str(e.get("id") or "").isdigit() else None)
    return out


def mark(m, sh, prefix, geo):
    """글 없는 도형 하나를 표시로 — 플레이스홀더(빈 자리표)는 표시가 아니다."""
    if m is None or getattr(sh, "is_placeholder", False):
        return
    m["n"] += 1
    ref = f"{prefix}-{TAG}{m['n']}"
    rec = {"id": ref, "kind": KIND, **geo, "shape": _shape_name(sh), "color": _color(sh)}
    if sh._element.tag.endswith("}cxnSp"):
        rec["_ends"] = _ends(sh)
    m["marks"].append(rec)
    note(m, sh, ref)


def group(m, sh, gid, recs, mark0, geo):
    """그룹 하나가 그림 · 표시 조각뿐이면(글 · 표 · 차트 0 · 조각 둘 이상) 그룹 상자로 — 안쪽 그룹 상자는 바깥이 겸한다."""
    if m is None:
        return
    pieces = [r["id"] for r in recs] + [x["id"] for x in m["marks"][mark0:]]
    if any(r["kind"] != "picture" for r in recs) or len(pieces) < 2:
        return
    inner = set(pieces)
    m["groups"] = [g for g in m["groups"] if not set(g["members"]) <= inner]
    m["groups"].append({"id": gid, "kind": GROUP, **geo, "members": pieces})
    note(m, sh, gid)


def finish(m):
    """슬라이드 몫 `{marks, groups}` — 연결선 끝점을 상자 id로(모르는 번호는 None)."""
    for x in m["marks"]:
        ends = x.pop("_ends", None)
        if ends is not None:
            x["from"], x["to"] = (m["ids"].get(e) if e is not None else None for e in ends)
    return {"marks": m["marks"], "groups": m["groups"]}
