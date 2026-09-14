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
    print(f"\n미러 쌍 {len(pairs)} · 위반 {bad}건 — " + ("판정 대상" if bad else "통과"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
