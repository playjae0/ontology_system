#!/usr/bin/env python3
"""점검_미러 — 검사기(문서 1) 조항과 본문 소유 절의 미러 쌍이 같은 말을 하는지.

왜 있나: [정정] 37의 재발 방지. B17이 문서 3 §3.7을 「LLM 초안 허용」으로 개정했는데
문서 1의 미러 I14가 구판 문면과 해소된 근거를 유지했다 — 검사 5종 어느 것도 못
잡았다: 수치·참조 무결만 보고 **미러가 본문과 같은 말을 하는지는 안 본다.**

방식 — 문면 해시 봉인:
  미러 쌍마다 양쪽 문면의 해시를 `미러쌍.json`에 봉인한다. 어느 쪽이든 바뀌면
  이 검사가 붉는다. 사람이 양쪽을 다시 대조해 같은 말임을 확인하면 `--seal`로
  재봉인한다 — **봉인 갱신이 곧 재확인 행위이고, 그 커밋이 확인 기록이다.**
  자동으로 「같은 말인가」를 판정하지 않는다(자연어 동치 판정은 이 검사의 능력
  밖이다) — 검사의 몫은 「한쪽만 바뀐 채 지나가는 일이 없게」까지다.

쌍 등재 규칙: 개정이 미러를 건드릴 때마다 그 쌍을 여기 추가한다. 전수 등재를
목표로 하지 않는다 — 실제로 어긋났던 자리부터.

실행: python3 점검_미러.py [--seal]   (REFINED_DIR로 정제본 위치 지정)
"""
import hashlib, json, os, re, sys

BASE = os.environ.get("REFINED_DIR", os.path.join(os.path.dirname(__file__), "..", "spec"))
PAIRS_FILE = os.path.join(os.path.dirname(__file__), "미러쌍.json")


def _read(name):
    p = os.path.join(BASE, name)
    with open(p, encoding="utf-8") as f:
        return f.read()


def _extract(doc, pattern, kind):
    """kind='row': 그 문자열로 시작하는 표 행 한 줄. kind='para': 그 문자열로 시작해
    다음 굵은 머리(**…**로 시작하는 줄) 직전까지의 문단."""
    text = _read(doc)
    i = text.find(pattern)
    if i < 0:
        return None
    if kind == "row":
        return text[i:text.index("\n", i)]
    j = i + len(pattern)
    m = re.search(r"\n\*\*|\n## |\n\| ", text[j:])
    return text[i:j + (m.start() if m else len(text) - j)]


def _h(s):
    return hashlib.sha256(re.sub(r"\s+", " ", s).strip().encode()).hexdigest()[:16]


def main():
    pairs = json.load(open(PAIRS_FILE, encoding="utf-8"))
    seal = "--seal" in sys.argv
    bad = 0
    for p in pairs:
        sides = {}
        for side in ("mirror", "body"):
            got = _extract(p[side]["doc"], p[side]["anchor"], p[side]["kind"])
            if got is None:
                print(f"  ✗ {p['id']} — {p[side]['doc']}에서 앵커를 못 찾음: {p[side]['anchor'][:40]}…")
                bad += 1
                sides = None
                break
            sides[side] = _h(got)
        if sides is None:
            continue
        if seal:
            p["sealed"] = sides
            continue
        prev = p.get("sealed", {})
        for side, h in sides.items():
            if prev.get(side) != h:
                print(f"  ✗ {p['id']} — {side} 쪽 문면이 봉인과 다르다"
                      f" ({p[side]['doc']}). 양쪽을 다시 대조하고 같은 말이면 --seal")
                bad += 1
    if seal:
        json.dump(pairs, open(PAIRS_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"봉인 갱신 — {len(pairs)}쌍")
        return 0
    _candidates(pairs)
    print(f"\n미러 쌍 {len(pairs)} · 위반 {bad}건 — " + ("판정 대상" if bad else "통과"))
    return 1 if bad else 0


# ── 미등재 미러 후보 ([개정] B56-6) ───────────────────────────────────────
# **판정은 사람이 한다.** 자동 봉인하지 않고 목록만 낸다 — 어휘가 겹친다는 것과
# 「같은 말을 한다」는 것은 다르고, 후자는 이 검사의 능력 밖이다(머리말 참조).
# 쌍 등재는 「실제로 어긋났던 자리부터」가 규칙이라, 이 목록은 **다음 개정 때
# 어디를 볼지**를 알려 주는 것이지 등재 지시가 아니다.
_STOP = set("그 이 저 것 수 등 및 또는 때 곳 안 밖 위 아래 전 후 중 시 은 는 이 가 을 를 의 에 와 과 로 으로 도 만 며 고 다 한 할 하는 하지 않는다 아니다 있다 없다 대한 대해 따라 위해 통해 문서 규약 조항 절 항 카드".split())
_MIN_OVERLAP = 0.34          # 어휘 자카드 — 이 이상이면 사람이 볼 값어치가 있다


def _tok(text):
    return {w for w in re.findall(r"[가-힣A-Za-z_][가-힣A-Za-z0-9_]{1,}", text or "")
            if w not in _STOP and len(w) > 1}


def _candidates(pairs, top=6):
    """문서 1 조항 행 ↔ 본문 문단의 어휘 겹침이 높은데 **미등재**인 쌍."""
    try:
        checker = _read("1_금지와불변.md")
    except OSError:
        return
    sealed = {(p["mirror"]["anchor"], p["body"]["doc"]) for p in pairs}
    sealed_anchors = {p["mirror"]["anchor"] for p in pairs}
    rows = [ln for ln in checker.split("\n")
            if ln.startswith("| ") and ln.count("|") >= 3 and len(ln) > 120]
    bodies = []
    for doc in ("3_구조.md", "4_쓰기절차.md", "5_읽기절차.md",
                "6_파서와구축모드.md", "7_구현규격과검증.md", "2_계약.md"):
        try:
            txt = _read(doc)
        except OSError:
            continue
        for para in txt.split("\n\n"):
            if len(para) > 200:
                bodies.append((doc, para))
    out = []
    for row in rows:
        rid = row.split("|")[1].strip()
        if any(a.startswith("| " + rid) or a.strip().startswith(rid)
               for a in sealed_anchors):
            continue
        rt = _tok(row)
        if len(rt) < 8:
            continue
        best = max(((len(rt & _tok(b)) / len(rt | _tok(b)), doc, b)
                    for doc, b in bodies), default=(0, None, None))
        if best[0] >= _MIN_OVERLAP:
            out.append((round(best[0], 2), rid, best[1], best[2][:56].replace("\n", " ")))
    if not out:
        print("\n  미등재 미러 후보 0건")
        return
    out.sort(reverse=True)
    print(f"\n  미등재 미러 후보 {len(out)}건 — **판정은 사람이 한다**(자동 봉인 없음):")
    for sc, rid, doc, head in out[:top]:
        print(f"    {sc:.2f}  문서1 [{rid}] ↔ {doc} — {head}…")
    if len(out) > top:
        print(f"    … 외 {len(out) - top}건")


if __name__ == "__main__":
    sys.exit(main())
