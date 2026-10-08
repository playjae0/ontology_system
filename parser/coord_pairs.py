# -*- coding: utf-8 -*-
"""칸 2.8 — **좌표 쌍 대조** — 행의 상위(`process_group`) · 하위(`process_ref`) · 극성이 골격과 맞는가 (B105 ②③④).

**판정은 `verdict` 하나다** — 등록 리허설(킷 관문 G4I) · 인입 좌표 단계(판정 전 쌍 표) · 구축
(`Builder.coord_verdicts` → `coord_mismatch` 큐)이 같은 함수를 부른다(두 벌 금지). 판정은 셋이다:

  · **상위 어긋남** — 상위 표기가 골격 노드로 맞는데 그 노드가 하위 자신도 조상도 아니다 · 쌍 `(상위 표기, 하위 canonical)`
  · **상위 골격 밖** — 상위 표기가 골격에 없다 · 어긋남이 아니다(큐 없음 — 종수만 센다)
  · **극성 어긋남** — 행의 극성과 하위 노드의 극성이 **둘 다 확정**인데 다르다 · 쌍 `(극성, 하위 canonical)`

상위 표기가 골격 노드 여럿의 별칭이면(공유 별칭) 그중 하나라도 하위 자신이거나 조상이면 맞음이다 — 첫 노드를
고르지 않는다(B102 ②). 파서 자리라 core를 모른다: 표기를 노드로 푸는 일은 호출자 몫이고(구축 · 좌표 단계는
사전 — 구축과 같은 해소 · 등록은 닫힌 목록 `SnapView`), 여기는 풀린 canonical과 부모 사슬 · 극성 · 축값만 받는다.
"""
from __future__ import annotations

from parser import tagger

GROUP, OUTSIDE, POLARITY = "상위", "상위 골격 밖", "극성"
#: **문서 좌표를 상위로 삼은 대조**(B106 ⑤) — 행에 상위가 없고 문서 좌표가 있을 때. 판정은 `verdict` 그대로이고
#: 화면·큐가 출처를 가르는 표지다 — 쌍의 열쇠는 상위와 같다(`ack_kind` — `ops coord-ack`가 같은 쌍을 닫는다).
DOC_GROUP = "문서 좌표"


def ack_kind(kind):
    """확인 기록의 종류 — 문서 좌표 상위도 상위 쌍이다(같은 열쇠)."""
    return GROUP if kind == DOC_GROUP else kind

#: **좌표 쌍 관문 문턱**(B105 ② · 사내 손잡이 `coord_pair_pct`) — 상위·하위가 둘 다 골격에 맞은 행 중 상위
#: 어긋남이 이 백분율 이상이면 등록 관문 FAIL(G4I — 열이 뒤바뀌었거나 매핑이 틀렸다). 기본값은 가결정
#: (D-186) — 창작 표본 수치가 근거가 아니다([정정] 50). 사내 실측(관문 G4I 줄의 k/m)으로 조정한다.
COORD_PAIR_PCT = 50

#: 화면이 싣는 쌍 수 · 쌍마다 예시 위치 수
TOP, LOCS = 10, 3


def ancestors(canonical, parent_of):
    """하위 노드의 조상 canonical 집합 — 부모 사슬을 따라 올라간다(순환·깊이 방어 `tagger.MAX_UP`)."""
    out, cur = set(), canonical
    for _ in range(tagger.MAX_UP):
        nxt = parent_of(cur)
        if not nxt or nxt in out or nxt == canonical:
            break
        out.add(nxt)
        cur = nxt
    return out


def verdict(group, group_cs, ref_c, et, *, parent_of, polarity_of, axis):
    """**한 행의 좌표 쌍 판정** — `[(종류, 쌍)]`(비면 맞음).

    `group`은 상위 원 표기 · `group_cs`는 그 표기가 가리키는 골격 노드 canonical 목록(없으면 골격 밖) ·
    `ref_c`는 해소된 하위 canonical(하강 뒤 — 해소 못 했으면 None · 대조하지 않는다) · `et`는 행의 극성 ·
    `axis`는 확정 축값(층 config `polarity.values`)."""
    out = []
    if group and ref_c:
        if not group_cs:
            out.append((OUTSIDE, (group, None)))
        elif not any(c == ref_c or c in ancestors(ref_c, parent_of) for c in group_cs):
            out.append((GROUP, (group, ref_c)))
    if ref_c and et:
        pol = polarity_of(ref_c)
        if pol in axis and et in axis and pol != et:
            out.append((POLARITY, (et, ref_c)))
    return out


def reason(kind, pair, node_pol=None):
    """큐 문면 — 구축이 싣는 그 말(쌍 하나 = 문면 하나 · 화면이 쌍으로 묶는 열쇠는 payload다)."""
    if kind == GROUP:
        return f"'{pair[0]}'는 골격에 실존하나 '{pair[1]}'의 조상이 아니다"
    if kind == DOC_GROUP:
        return f"문서 좌표 '{pair[0]}'가 '{pair[1]}'의 조상이 아니다(행에 상위가 없어 문서 좌표로 대조했다)"
    return f"record의 극성 '{pair[0]}'과 좌표 '{pair[1]}'의 극성 '{node_pol}'이 다르다"


def payload(kind, pair, prov, node_pol=None):
    """큐 payload — 구판과 같은 모양(상위: `process_group`·`process_ref` · 극성: `process_ref`·`node_polarity`·
    `electrode_type`) + `provenance`. 쌍의 열쇠는 이 모양에서 다시 읽는다(`pair_of`)."""
    if kind in (GROUP, DOC_GROUP):
        # 문서 좌표 상위는 출처를 payload에 적는다(B106 ⑤) — 쌍의 열쇠(`pair_of`)는 상위와 같다
        return {"process_group": pair[0], "process_ref": pair[1], "provenance": prov,
                **({"upper": DOC_GROUP} if kind == DOC_GROUP else {})}
    return {"process_ref": pair[1], "node_polarity": node_pol, "electrode_type": pair[0],
            "provenance": prov}


def pair_of(pl):
    """큐 payload → `(종류, 쌍)` — 화면의 묶음 · 확인 기록의 열쇠."""
    if "process_group" in (pl or {}):
        return GROUP, (pl.get("process_group"), pl.get("process_ref"))
    return POLARITY, ((pl or {}).get("electrode_type"), (pl or {}).get("process_ref"))


class SnapView:
    """**닫힌 목록 스냅샷 위의 해소** — 등록 리허설(킷 · core를 모른다)이 쓴다.

    하위는 이름·별칭 정확(라틴 대소문자 2차) · **노드 하나일 때만** · 공유 별칭이면 행의 상위 범위 안에서 하나일
    때만(태깅의 범위 안 해소와 같은 함수 `tagger.scope_rows` — 맞바꿔 보기도 같은 길) · 극성 하강은 구축과 같은
    규칙(부모가 그 노드이고 극성이 행의 극성인 자식 · 노드 극성이 확정이면 하강하지 않는다). 상위는 그 표기를
    가진 노드 전부(공유 별칭 포함)."""

    def __init__(self, nodes, axis=()):
        self.nodes = list(nodes)
        self.by = {n["canonical"]: n for n in nodes}
        self.idx, self.shared, _a = tagger.scoped_index(nodes)
        self.owners = {}
        for n in nodes:
            for k in [n["canonical"]] + list(n.get("aliases") or []):
                self.owners.setdefault(k, set()).add(n["canonical"])
        self.axis = tuple(axis or ())

    def parent_of(self, c):
        return (self.by.get(c) or {}).get("parent")

    def polarity_of(self, c):
        return (self.by.get(c) or {}).get("polarity")

    def ref(self, surface, et=None, group=None):
        n = (self.idx.get(surface) or tagger.fold_hit(surface, self.idx)) if surface else None
        if n is None and surface and group:
            sc = tagger.scope_rows([{"process_group": group}], [surface], self.nodes,
                                   idx=self.idx, shared=self.shared)[0]
            n = sc[0] if sc else None
        if n is None:
            return None
        c = n["canonical"]
        if et in self.axis and self.polarity_of(c) not in self.axis:
            kid = next((k for k, m in sorted(self.by.items())
                        if m.get("parent") == c and m.get("polarity") == et), None)
            c = kid or c
        return c

    def groups(self, surface):
        if not surface:
            return []
        got = self.owners.get(surface)
        if got is None:
            f = tagger._fold(surface)
            got = set().union(*[v for k, v in self.owners.items() if tagger._fold(k) == f] or [set()])
        return sorted(got)

    def judge(self, piece):
        g, et = piece.get("process_group"), piece.get("electrode_type")
        r = piece.get("process_ref")
        rc = self.ref(r, et, g) if r else (self.ref(g, et) if g else None)   # 하위가 비면 상위로(저해상도 — 구축과 같다)
        return verdict(g, self.groups(g), rc, et, parent_of=self.parent_of,
                       polarity_of=self.polarity_of, axis=self.axis), rc


def swapped(pieces, view):
    """**맞바꿔 보기** — 상위·하위를 바꿔 대조하면 맞는 행 `(맞음, 대조됨)`(둘 다 골격에 맞은 행만 센다)."""
    ok = n = 0
    for p in pieces:
        g, r = p.get("process_group"), p.get("process_ref")
        if not (g and r):
            continue
        vs, rc = view.judge(dict(p, process_group=r, process_ref=g))
        if rc and view.groups(r):
            n += 1
            ok += 0 if any(k == GROUP for k, _p in vs) else 1
    return ok, n


def judge_all(pieces, view):
    """조각마다 `(위치, 판정, 대조됨)` — 등록 관문의 표 재료(`tally`)."""
    out = []
    for p in pieces:
        vs, rc = view.judge(p)
        out.append((p.get("source_locator"), vs,
                    bool(rc and p.get("process_group") and view.groups(p.get("process_group")))))
    return out


def tally(rows):
    """`[(위치, [(종류, 쌍)], 대조됨)]` → 쌍 표 — `{"pairs": {(종류, 쌍): {"rows", "locs"}}, "outside": {표기: 행},
    "checked": 상위·하위가 둘 다 골격에 맞은 행, "group_rows": 그중 상위 어긋남 행}`."""
    pairs, outside, checked, group_rows = {}, {}, 0, 0
    for loc, vs, both in rows:
        checked += 1 if both else 0
        for kind, pair in vs:
            if kind == OUTSIDE:
                outside[pair[0]] = outside.get(pair[0], 0) + 1
                continue
            group_rows += 1 if kind in (GROUP, DOC_GROUP) else 0
            e = pairs.setdefault((kind, pair), {"rows": 0, "locs": []})
            e["rows"] += 1
            if loc and len(e["locs"]) < LOCS:
                e["locs"].append(loc)
    return {"pairs": pairs, "outside": outside, "checked": checked, "group_rows": group_rows}


def ordered(t):
    """쌍을 행 수 내림 · 종류 · 쌍 순으로."""
    return sorted(t["pairs"].items(), key=lambda kv: (-kv[1]["rows"], kv[0][0], str(kv[0][1])))


def head_line(t, acked=()):
    """한 줄 — `좌표 쌍 — 어긋남 k쌍(n행) · 상위 이름 골격 밖 m종` (+ 확인된 쌍은 따로 센다)."""
    live = [(k, e) for k, e in t["pairs"].items() if k not in acked]
    done = [(k, e) for k, e in t["pairs"].items() if k in acked]
    return (f"좌표 쌍 — 어긋남 {len(live):,}쌍({sum(e['rows'] for _k, e in live):,}행) · "
            f"상위 이름 골격 밖 {len(t['outside']):,}종"
            + (f" · 확인된 쌍 {len(done):,}({sum(e['rows'] for _k, e in done):,}행)" if done else ""))


def describe(kind, pair):
    """쌍 하나의 말 — 상위 · 문서 좌표 상위(B106 ⑤) · 극성."""
    a, b = pair
    if kind == GROUP:
        return f"상위 '{a}' ↛ 하위 '{b}'"
    if kind == DOC_GROUP:
        return f"문서 좌표 '{a}' ↛ 하위 '{b}'"
    return f"극성 '{a}' ↛ 노드 '{b}'(극성 다름)"


def pair_lines(t, acked=(), top=TOP):
    """쌍 표의 줄들 — `(상위 · 하위 · 행 수 · 예시 위치)` 또는 `(극성 · 노드 …)` · 확인된 쌍은 표시."""
    out = []
    for (kind, pair), e in ordered(t)[:top]:
        what = describe(kind, pair)
        out.append(f"{what} · {e['rows']:,}행 · 예 {', '.join(e['locs'])}"
                   + ("  [확인됨]" if (kind, pair) in acked else ""))
    if len(t["pairs"]) > top:
        out.append(f"… 쌍 {len(t['pairs']) - top:,}개 더")
    if t["outside"]:
        out.append("상위 이름 골격 밖: " + " · ".join(
            f"'{g}' {n:,}행" for g, n in sorted(t["outside"].items(), key=lambda x: (-x[1], x[0]))[:top]))
    return out
