# -*- coding: utf-8 -*-
"""칸 0.3 — **골격 칸의 사람 말 — LLM이 읽는다**(B202 ② · 연결 처분 · 해석 고침 둘 다 · 확인 없이 쓰지 않는다).

입력 = 사람 말 + 그 줄(①의 판단 · 후보) + 같은 골격 목록 + 그 층 카테고리 닫힌 목록 + 위 공정이 될 수 있는 골격 노드. 출력은 둘 중 하나:

| 갈래 | 칸 | 코드의 검사 |
|---|---|---|
| 연결 처분 | 처분 넷(같다 · 새로 · 버림 · 위로) + 쌍 줄의 맞다 · 대상 · 확실도 · 까닭 | 처분이 그 줄에 쓸 수 있는 것인가 · 대상이 목록 안인가 |
| 해석 고침 | 고칠 칸(카테고리 · 위 공정) · 값 · 까닭 | 카테고리는 닫힌 목록 안 · 위 공정은 골격 안 · 카테고리는 겸 값 줄만 |

검사를 못 지나면 `None`과 까닭(화면은 「다시 말하기」). 쓰기는 여기 없다 — 화면이 해석을 보이고 Enter 뒤에 처분 손(`provisional_ask.decide` ·
`provisional_hand.reread`)이 쓴다. LLM 지점은 ②개체 동일성 판정의 호출 태그 `gate_say`(닫힌 12 그대로) · 지시문
`prompts/0.3_gate_say.md` · mock은 픽스처 `gate_say.json`(말 → 답 · 없으면 「모름」). 코드에 층 어휘 0.
"""
from __future__ import annotations


PROMPT, TAG = "gate_say", "gate_say"
LINK, REREAD, UNKNOWN = "처분", "해석", "모름"
#: 처분 이름 → 글쇠(처분 넷 + 쌍 줄의 맞다)
KEYS = {"같다": "m", "새로": "k", "버림": "d", "위로": "u", "맞다": "a"}
FIELDS = ("카테고리", "위 공정")
SCHEMA = {"type": "object", "properties": {
    "kind": {"type": "string", "enum": [LINK, REREAD, UNKNOWN]},
    "disposition": {"type": ["string", "null"], "enum": list(KEYS) + [None]},
    "target": {"type": ["string", "null"]}, "reason": {"type": ["string", "null"]},
    "field": {"type": ["string", "null"], "enum": list(FIELDS) + [None]}, "value": {"type": ["string", "null"]},
    "confidence": {"type": "number"}, "why": {"type": "string"}},
    "required": ["kind", "disposition", "target", "reason", "field", "value", "confidence", "why"],
    "additionalProperties": False}                     # 엄격 규칙(B200 ⓪ — 쓰지 않는 칸은 null · `gateway.strict_issues`)
CALLS = {"말 해석": 0}


def allowed(row):
    """그 줄에 쓸 수 있는 글쇠 — 문 줄 `m k d`(+ 겸 값 줄 `u`) · 쌍 줄 `m a d`."""
    if row.get("kind") == "pair":
        return ("m", "a", "d")
    return ("m", "k", "d", "u") if row.get("also") else ("m", "k", "d")


def categories():
    """좌표 층의 카테고리 닫힌 목록(categories + uses)."""
    from core.state.bootstrap import coord_layer, load_config
    cfg = load_config(coord_layer())
    return sorted(set(cfg.get("categories") or {}) | set(cfg.get("uses") or []))


def ups(sk=None):
    """위 공정이 될 수 있는 골격 노드 — 아래에 골격 자식이 있는 것(canonical)."""
    from core.build import skeleton_review as SR
    sk = sk or SR._Sk()
    return [sk.g.get(i)["canonical"] for i in sk.g.nodes if i in sk.sk and sk.kids(i)]


def payload(text, row, cats, up_list):
    lm = row.get("llm") or {}
    return {"사람 말": text, "줄": {"표기": row.get("surface"), "종류": "쌍" if row.get("kind") == "pair" else "문",
                                 "카테고리": row.get("also") or "좌표", "위 공정": row.get("up_name") or row.get("up") or "미정",
                                 "판단": lm.get("verdict"), "후보": [c["canonical"] for c in lm.get("candidates") or []]},
            "쓸 수 있는 처분": [k for k, v in KEYS.items() if v in allowed(row)],
            "골격": [{"번호": x["no"], "이름": x["name"], "경로": x["path"]} for x in row.get("skeleton") or []],
            "카테고리 목록": cats, "위 공정 목록": up_list}


def _mock(text):
    from core.llm import gateway
    from core.state import fixtures
    gateway.mock(TAG, text)
    return fixtures.answers("gate_say").get(text.strip()) or {"kind": UNKNOWN, "confidence": 0.0, "why": "mock — 창작 답 없음"}


def _ask(text, row, cats, up_list):
    from core.llm import gateway
    CALLS["말 해석"] += 1
    return gateway.ask(TAG, PROMPT, payload(text, row, cats, up_list), SCHEMA, mock=lambda: _mock(text))


def read(text, row):
    """**사람 말 한 줄 → 해석**(검사까지 · 쓰기 0) — `({kind, key?, target?, reason?, field?, value?, confidence, why}, None)` 또는
    `(None, 까닭)`."""
    from core.state import gate_judge as GJ
    cats, up_list = categories(), ups()
    a = _ask(text, row, cats, up_list) or {}
    try:
        conf = max(0.0, min(1.0, float(a.get("confidence") or 0)))
    except (TypeError, ValueError):
        conf = 0.0
    out = {"kind": a.get("kind"), "confidence": conf, "why": str(a.get("why") or "")[:200]}
    if a.get("kind") == LINK:
        k = KEYS.get(a.get("disposition") or "")
        if k not in allowed(row):
            return None, f"해석이 이 줄에 쓸 수 없는 처분 — {a.get('disposition')}"
        out["key"] = k
        if k == "m":
            hit = GJ.find(a.get("target"), row.get("skeleton") or [])
            if len(hit) != 1:
                return None, f"해석의 대상이 골격 목록 밖 — {a.get('target')}"
            out["target"] = hit[0]
        if k == "d":
            out["reason"] = str(a.get("reason") or text).strip()
        return out, None
    if a.get("kind") == REREAD:
        f, v = a.get("field"), str(a.get("value") or "").strip()
        if f == "카테고리":
            if not row.get("also"):
                return None, "카테고리 고침은 겸 값 줄만 — 이 줄은 좌표 표기(처분 넷으로)"
            hit = [c for c in cats if c.lower() == v.lower()]
            if not hit:
                return None, f"카테고리 '{v}'가 닫힌 목록 밖 — {' · '.join(cats)}"
            out.update(field=f, value=hit[0])
            return out, None
        if f == "위 공정":
            from core.state import catalog
            hit = GJ.find(v, [{"canonical": c, "name": c.rsplit(catalog.sep(), 1)[-1]} for c in up_list])
            if len(hit) != 1:
                return None, f"위 공정 '{v}'가 골격 밖이거나 여럿"
            out.update(field=f, value=hit[0])
            return out, None
        return None, f"고칠 칸이 둘 밖 — {f}"
    return None, out["why"] or "해석 못 함"
