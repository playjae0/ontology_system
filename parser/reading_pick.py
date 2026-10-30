# -*- coding: utf-8 -*-
"""칸 2.4 — **판독 입력 고르기**(B168 ①② ③ — 쪽 판독의 입력 몫) — 쪽마다 상자 목록에 표시 · 조각 그룹을 합치고, 그림 원본은 필요한
것만 보낸다. 파서 안이다(LLM 0 · 쓰기 0) — 판독 훅(`parser/reading.hook`)이 부른다.

    pick(raw, bx, fixes, live)  → (쪽마다 `{boxes, images}`, 셈)
        boxes   봉투 상자 목록 + 표시(글 없는 도형 · 선 · 연결선 — `raw["_marks"]`) + 조각 그룹 하나(조각 상자 대신) — **판독 입력에만**
                (봉투 `boxes` · 분할 · 청크 · 추출 입력은 그대로 — B168 경계)
        images  그림 상자 id → 「원본」 또는 「캡처로 봄 — 사유」(받지 않는 그림만 판독 입력의 그림 상자 칸 `image` · 판독 결과에 남는다)

**고르는 규칙**(앞이 이긴다): 사람의 `자세히`(원본) · `빼기`(사람이 뺌) → 빼지 않는 예외(그 그림에 표시가 겹친다 · 연결선의 시작이나
끝이 그 그림이다 — 같은 그룹 안의 표시 · 연결선은 그림의 일부라 예외가 아니다) → 조각 그룹의 조각(그룹 상자가 범위 · 캡처가 본다)
→ **장식**(덱 쪽의 절반 이상 · 두 쪽 이상에 같은 그림 — 위치 무관) → **같은 꼴**(한 덱에 같은 그림 여럿 — 대표 하나만 · 덱 차례의
첫 장) → 원본. 같음은 바이트(sha256) · 실호출이고 Pillow가 있으면 축소 비교(16×16 회색조 · 16단계 — `THUMB` · `LEVELS`)로 —
Pillow가 없으면 바이트 비교만(셈의 `바이트만`). 모델이 받는 형식(PNG · JPEG) 밖의 그림은 「캡처로 봄 — 형식」.
문턱(`DECOR_SHARE` 절반)은 창작 기본값이다 — 사내 실측이 오면 조정한다([정정] 50).
"""
from __future__ import annotations

import hashlib
import io

#: 장식 — 그 그림이 놓인 쪽이 덱 쪽의 이 몫 이상(두 쪽 이상일 때)
DECOR_SHARE = 0.5
#: 축소 비교 — 한 변 · 밝기 단계
THUMB, LEVELS = 16, 16
SEND = ("image/png", "image/jpeg")
KEEP = "원본"
SAME, DECOR, GROUP, FORMAT, HUMAN = "같은 꼴", "장식", "그룹", "형식", "사람이 뺌"
SEEN = "캡처로 봄"


def _thumb(blob):
    """축소 비교의 열쇠(실호출 · Pillow — 선택 의존 · 지연 import) · 못 하면 None."""
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(blob)).convert("L").resize((THUMB, THUMB))
        return "t" + hashlib.sha256(bytes(p * LEVELS // 256 for p in im.getdata())).hexdigest()[:16]
    except Exception:                                       # noqa: BLE001 — 그 그림은 바이트 비교로
        return None


def _can_thumb(live):
    if not live:
        return False                                        # mock은 선택 의존을 열지 않는다(문서 7 §7.1)
    try:
        import PIL  # noqa: F401
        return True
    except ImportError:
        return False


def _overlap(a, b):
    g = ("left", "top", "width", "height")
    if any(not isinstance(x.get(k), (int, float)) for x in (a, b) for k in g):
        return False
    return (a["left"] < b["left"] + b["width"] and b["left"] < a["left"] + a["width"]
            and a["top"] < b["top"] + b["height"] and b["top"] < a["top"] + a["height"])


def _side(raw, pg):
    """그 쪽의 곁 칸 `{marks, groups}`(PPT 리더 — B168 ①) · PDF · 옛 리더는 빈 몫."""
    m = (raw.get("_marks") or {}).get(pg.get("slide")) if pg.get("slide") is not None else None
    return m or {"marks": [], "groups": []}


def _box(r, w, h):
    from parser.reading import _box as box
    return box(r, w, h)


def _keys(bx, images, thumb):
    """그림마다 같음 열쇠 · 열쇠마다 놓인 쪽과 차례 — `({id: 열쇠}, {열쇠: [(쪽, id)]})`."""
    key, seen = {}, {}
    for pg in bx["pages"]:
        for b in pg["boxes"]:
            blob, mime = images.get(b["id"], (None, None)) if b["kind"] == "picture" else (None, None)
            if not blob:
                continue
            k = (_thumb(blob) if thumb else None) or "b" + hashlib.sha256(blob).hexdigest()[:16]
            key[b["id"]] = k
            seen.setdefault(k, []).append((pg["page"], b["id"]))
    return key, seen


def pick(raw, bx, fixes, live):
    """쪽마다 판독 입력의 상자 · 그림 원본 결정 — `({쪽: {boxes, images}}, 셈)`(LLM 0)."""
    from parser.reading import DETAIL, DROP                 # 고침 동사의 자리는 판독 훅 하나다
    images = raw.get("_images") or {}
    thumb = _can_thumb(live)
    key, seen = _keys(bx, images, thumb)
    n_pages = len(bx["pages"])
    decor = {k for k, at in seen.items() if len({p for p, _ in at}) >= 2 and len({p for p, _ in at}) >= DECOR_SHARE * n_pages}
    out, n = {}, {"원본": 0, SAME: 0, DECOR: 0, GROUP: 0, SEEN: 0, HUMAN: 0, "표시": 0, "바이트만": not thumb}
    rep = {}
    for pg in bx["pages"]:
        side, fx = _side(raw, pg), fixes.get(pg["page"]) or {}
        w, h = pg.get("width"), pg.get("height")
        member = {m: g["id"] for g in side["groups"] for m in g["members"]}
        decided, why = {}, {}
        for b in pg["boxes"]:
            if b["kind"] != "picture":
                continue
            pid, mime = b["id"], (images.get(b["id"]) or (None, None))[1]
            outside = [x for x in side["marks"] if member.get(x["id"]) is None or member.get(x["id"]) != member.get(pid)]
            hit = any(_overlap(x, b) for x in outside if x.get("from") is None and x.get("to") is None) \
                or any(pid in (x.get("from"), x.get("to")) for x in outside)
            k = key.get(pid)
            if pid in (fx.get(DETAIL) or ()):
                d = KEEP
            elif pid in (fx.get(DROP) or ()):
                d = HUMAN
            elif mime not in SEND:
                d = FORMAT
            elif hit:
                d = KEEP
                if k is not None:
                    rep.setdefault(k, pid)                  # 예외로 원본인 그림이 같은 꼴의 대표를 겸한다
            elif pid in member:
                d = GROUP
            elif k in decor:
                d = DECOR
            elif k is not None and len(seen.get(k) or ()) > 1 and rep.setdefault(k, pid) != pid:
                d = SAME
            else:
                d = KEEP
            decided[pid] = d
            why[pid] = KEEP if d == KEEP else f"{SEEN} — {d}" + (f"(대표 {rep[k]})" if d == SAME else "")
        keep = {g["id"] for g in side["groups"]}
        hidden = {m for g in side["groups"] for m in g["members"] if decided.get(m) != KEEP}
        # 원본을 받는 그림은 칸 그대로(표시 · 뺄 그림이 없는 쪽은 판독 입력이 B168 전과 같다 — 보존분 재사용) · 받지 않는 그림만 「캡처로 봄」
        boxes = [dict(b, image=why[b["id"]]) if why.get(b["id"], KEEP) != KEEP else b for b in pg["boxes"] if b["id"] not in hidden]
        boxes += [dict(_box(g, w, h), members=len(g["members"])) for g in side["groups"]]
        for x in side["marks"]:
            if x["id"] in hidden or member.get(x["id"]) in keep:
                continue
            boxes.append({**_box(x, w, h), **{k2: x[k2] for k2 in ("shape", "color", "from", "to") if x.get(k2) is not None}})
            n["표시"] += 1
        n[GROUP] += len(side["groups"])
        for d in decided.values():
            n["원본" if d == KEEP else SEEN] += 1
            if d in (SAME, DECOR, HUMAN):
                n[d] += 1
        out[pg["page"]] = {"boxes": boxes, "images": why}
    return out, n
