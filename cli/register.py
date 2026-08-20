# -*- coding: utf-8 -*-
"""n6 구축 모드 등록 파이프라인 — doc_type 등록의 3단 (파서_명세 §6·§7 · 틀 §2).

    ① 생성  입력 패키지(사람 4 + 시스템 5) → reader head 공급 → 어댑터·스키마 초안
    ② 검수  실행 하네스(기계 관문) → 뷰 데이터 JSON → 렌더러로 HTML → 재생성 루프
    ③ 확정  승인 1회 → doc_type 등록부 등재

**틀 §2가 정한 검수 수준**: 사람은 코드가 아니라 **결과 뷰**를 보고, 통과는 승인 1회다.
그래서 ②가 두 겹이다 — **기계가 먼저 거르고**(하네스), 사람은 그 뒤에 뷰를 본다.
기계 관문이 없으면 사람이 문법 오류를 읽는 자리로 내려앉는다.

**"무수정 = 자동 통과"는 금지다.** 승인자 없이는 등재하지 않는다.

경계:
  · 하네스는 `kit/run_adapter.py`를 **호출**한다 — 재작성하지 않는다.
  · 렌더러는 `kit/render_review.py`를 **호출**한다 — 뷰 데이터 스키마(D-79)가 계약이고
    여기는 산출자다. 스키마가 부족하면 고치는 것이 아니라 멈추고 보고할 자리다.
  · **층 초안 구획은 없다** — 층 등록(R1)은 국면 2 게이트이고 여기는 doc_type 전용이다.

사용:
  python cli/register.py generate <doc_type> <층> <표본...> [--hint "..."]
  python cli/register.py review   <doc_type> [--instruct "수정 지시"]
  python cli/register.py confirm  <doc_type> --by <승인자>
  python cli/register.py list
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "kit"))

from core import registry, store                            # noqa: E402
from parser import pipeline, preflight, reader              # noqa: E402
from render_review import render                            # noqa: E402
from run_adapter import load_blocks                         # noqa: E402
from router import discover                                 # noqa: E402

REVIEW = ROOT / "review"
KIT = ROOT / "kit"
FIXTURES = ROOT / "mock" / "fixtures"

# D-22 확장 문구 — 표본 1부 등록의 경고. **문면이 규격이다.**
SOLO_WARNING = ("표본 1부 · 변형 미관찰 — **선언된 관계는 근거 1건일 수 있음**. "
                "1부 등록의 선언 edges는 특별 확인 대상이다")
EXCERPT = 3                                   # 정상 조각 발췌 건수(전량은 접힘에 실린다)


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _dir(doc_type):
    d = REVIEW / doc_type
    d.mkdir(parents=True, exist_ok=True)
    return d


def _state(doc_type):
    p = _dir(doc_type) / "state.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _save_state(doc_type, st):
    (_dir(doc_type) / "state.json").write_text(
        json.dumps(st, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# ================================================================ ① 생성
def draft(doc_type, revision=0):
    """어댑터·매칭 스키마 **초안** — USE_MOCK은 fixture 반환이다 (D-10 · D-26).

    fixture는 "미리 만든 정답"이 아니라 **외부 세션에서 실제 LLM이 산출한 결과물의
    스냅샷**이다. 사람이 손으로 써서 넣으면 그 리허설은 아무것도 검증하지 않는다.
    재생성 지시가 오면 대안본(`…_rev1`)을 반환해 **루프 배선을 검증**한다.

    HOOK: 실물 경로는 여기서 생성 LLM에 입력 패키지를 넘긴다. 반환 형태는 같다 —
    (어댑터 경로, 스키마 경로). 소비 쪽은 출처를 몰라도 된다.
    """
    for stem in ([f"{doc_type}_rev{revision}"] if revision else []) + [doc_type]:
        ad, sc = FIXTURES / "adapters" / f"{stem}.py", FIXTURES / "schemas" / f"{stem}.json"
        if ad.exists() and sc.exists():
            return ad, sc
    return None, None


def basic_adapter_proposal(samples):
    """분할이 **자명한 계열**이면 기본 어댑터를 제안한다 (파서_명세 §5 규약 5 · C13).

    자명한 것을 매번 생성시키면 검수 비용만 늘고 산출은 같다. 다만 임계를 넘는
    슬라이드가 있으면 자명함이 조건부가 되므로(C13 v18) 그 사실도 함께 말한다.
    """
    if not all(str(s).lower().endswith(".pptx") for s in samples):
        return None
    over = 0
    for s in samples:
        for sl in reader.read(str(s)).get("slides", []):
            shapes = [x for x in sl.get("shapes", []) if x and x.strip()]
            if sum(len(x) for x in shapes) > 600 or len(shapes) > 5:
                over += 1
    return {"adapter": "parser/adapters/basic_ppt.py",
            "reason": "PPT는 분할이 자명하다 — 슬라이드가 청크다. 생성 세션이 필요 없다",
            "over_threshold_slides": over,
            "note": ("임계 초과 슬라이드가 있어 자명함이 조건부다 — shape 분할·지도 폴백이 "
                     "돈다(C13 v18)" if over else "전 슬라이드가 임계 이하다")}


def cmd_generate(doc_type, layer, samples, hint=""):
    """① 생성 — 입력 패키지를 세우고 초안을 받는다.

    **입력 패키지 = 사람 4 + 시스템 5**(증분0 §3 P3 · 카드 M10):
      사람 — 표본 · doc_type 이름 · 층 지정 · 힌트(자유 텍스트)
      시스템 — reader 원시 추출 · 골격 닫힌 목록 · 층 어휘 · 공용 블록 · 어댑터 스켈레톤
    """
    if registry.lookup(doc_type):
        raise SystemExit(f"[생성] doc_type 이름 중복 — '{doc_type}'은 이미 등록돼 있다")
    layers = discover()
    if layer not in layers:                       # ⑵-③ 층 선행 완결
        raise SystemExit(f"[생성] 존재하지 않는 층 '{layer}' — 층 등록(R1)은 국면 2다. "
                         f"현재 층: {layers}")

    snap = store.read(store.SKELETON_LIST, {}).get(layer) or {}
    cfg = json.loads((ROOT / "layers" / layer / "config.json").read_text(encoding="utf-8"))
    pkg = {
        "human": {"doc_type": doc_type, "layer": layer,
                  "samples": [str(s) for s in samples], "hint": hint},
        "system": {
            "reader_head": [{"path": str(s), "head": reader.head(reader.read(str(s)), 12)}
                            for s in samples],
            "skeleton_closed_list": {"skeleton_version": snap.get("skeleton_version"),
                                     "count": snap.get("count"),
                                     "surfaces": [n["canonical"] for n in
                                                  (snap.get("nodes") or [])]},
            "layer_vocabulary": {"categories": cfg.get("categories"),
                                 "relations": cfg.get("relations"),
                                 "relation_patterns": cfg.get("relation_patterns")},
            "blocks": json.loads((ROOT / "schemas" / "blocks.json")
                                 .read_text(encoding="utf-8")),
            "adapter_skeleton": str((KIT / "어댑터_스켈레톤.py").relative_to(ROOT)),
        },
    }
    d = _dir(doc_type)
    (d / "input_package.json").write_text(
        json.dumps(pkg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"■ ① 생성 — {doc_type} (층 {layer} · 표본 {len(samples)}부)")
    print(f"   입력 패키지: 사람 4 + 시스템 5 → {(d / 'input_package.json').relative_to(ROOT)}")
    proposal = basic_adapter_proposal(samples)
    if proposal:
        print(f"   ▶ 기본 어댑터 적용 제안 — {proposal['reason']}")
        print(f"     {proposal['note']}")
    ad, sc = draft(doc_type)
    if ad is None:
        raise SystemExit(f"[생성] 초안을 얻지 못했다 — USE_MOCK fixture "
                         f"'{doc_type}' 부재 (D-10). 실물 경로는 생성 LLM 훅이다")
    print(f"   초안 수령: {ad.relative_to(ROOT)} · {sc.relative_to(ROOT)}")
    _save_state(doc_type, {"doc_type": doc_type, "layer": layer,
                           "samples": [str(s) for s in samples], "hint": hint,
                           "adapter": str(ad.relative_to(ROOT)),
                           "schema": str(sc.relative_to(ROOT)),
                           "revision": 0, "instructions": [],
                           "basic_adapter_proposal": proposal})
    return 0


# ================================================================ ② 검수
def harness(adapter, schema, samples):
    """기계 관문 — **kit/run_adapter.py를 그대로 부른다**(재작성 아님)."""
    r = subprocess.run([sys.executable, str(KIT / "run_adapter.py"),
                        str(adapter), str(schema)] + [str(s) for s in samples],
                       capture_output=True, text=True, cwd=str(ROOT))
    return r.returncode == 0, r.stdout


def role_table(schema, adapter_mod):
    """구획 2 — 필드 → role 배정표. **근거를 병기**한다(§7 구조).

    **6지선다는 role 5종 + UNMAPPABLE**이고, 구조 필드·payload 고정 키는 그 대상이
    아니다(C17 · D-46) — 미해결이 아니라 정상·완결이라 질문거리가 아니기 때문이다.
    공용 블록 유래 필드는 배정표에 뜨되 출처를 밝힌다.
    """
    fields, from_blocks = load_blocks(schema)
    rows = []
    for f, spec in fields.items():
        rows.append({"field": f, "role": spec.get("role"),
                     "category": spec.get("category"),
                     "attach_to": spec.get("attach_to_field"),
                     "reason": spec.get("정의문")
                     or ("공용 블록이 선언한 필드다" if f in from_blocks
                         else "생성 세션의 배정 근거"),
                     **({"from_block": "공용 블록"} if f in from_blocks else {})})
    for f in unmappable_of(schema, adapter_mod):
        rows.append({"field": f, "role": "UNMAPPABLE",
                     "reason": "5종 어디에도 맞지 않는다 — 사람 판정 대기 (D-30)"})
    return rows


def _col(i):
    s = ""
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def unmappable_of(schema, adapter_mod):
    """UNMAPPABLE 열 — **어댑터가 스스로 밝힌 미매핑분**에서 판정한다.

    D-30은 "UNMAPPABLE 열은 스키마 fields에 넣지 않고 어댑터 출력에서도 제외"라고
    정한다. 그러면 그 열은 어디에도 이름이 남지 않아 배정표에서 사라지고, **6지선다의
    여섯째 경로가 화면에서 증발한다** — 사람이 판정해야 할 것이 판정 화면에 없다.

    복원 경로는 어댑터의 선언 둘의 차집합이다: `header_labels`(원본 헤더 전량 — D-29)
    에 있는데 `columns`(출력 필드명 매핑)가 가리키지 않는 열. 스키마가 `unmappable`을
    명시하면 그쪽이 이긴다 — 명시는 판정이고 차집합은 복원이다.
    """
    if schema.get("unmappable"):
        return list(schema["unmappable"])
    exp = (getattr(adapter_mod, "ADAPTER", {}) or {}).get("expects") or {}
    labels, cols = exp.get("header_labels") or [], exp.get("columns") or {}
    if not labels or not cols:
        return []
    used = set(cols.values())
    return [labels[i] for i in range(len(labels)) if _col(i + 1) not in used]


def build_view(st, results, harness_ok, harness_out):
    """뷰 데이터 산출 — **D-79 스키마가 계약**이고 여기가 산출자다.

    렌더러는 아무것도 계산하지 않으므로 **채움율·이상 신호 판정을 여기서 다 채운다.**
    """
    schema = json.loads((ROOT / st["schema"]).read_text(encoding="utf-8"))
    mod = _load(ROOT / st["adapter"], f"reg_{st['doc_type']}")
    kind = mod.ADAPTER["payload_kind"]

    pieces = [p for r in results if r.ok
              for p in (r.envelope.get("records") or r.envelope.get("chunks"))]
    keys = sorted({k for p in pieces for k in p})
    fill = {k: round(sum(1 for p in pieces if p.get(k) not in (None, "")) / len(pieces), 3)
            for k in keys} if pieces else {}

    anomalies = []
    if len(st["samples"]) < 2:                     # D-22 확장 문구 — **필수 표시**
        anomalies.append({"kind": "warning", "message": SOLO_WARNING,
                          "where": Path(st["samples"][0]).name,
                          "detail": {"declared_edges": schema.get("edges", []),
                                     "note": "위 선언 edges는 특별 확인 대상이다"}})
    if not harness_ok:
        anomalies.append({"kind": "failure", "message": "기계 관문(실행 하네스) 미통과",
                          "where": "kit/run_adapter.py",
                          "detail": {"fail_lines": [ln.strip() for ln in
                                                    harness_out.splitlines()
                                                    if "[FAIL]" in ln][:10]}})
    for r in results:
        for f in r.failures:
            anomalies.append({"kind": "failure", "message": f["reason"],
                              "where": r.doc_id, "detail": f.get("detail") or {}})
    for f in unmappable_of(schema, mod):
        anomalies.append({"kind": "question",
                          "message": f"'{f}' 열은 role 5종 어디에 배정합니까 — "
                                     f"생성 세션이 UNMAPPABLE로 올렸다",
                          "where": st["doc_type"]})

    tree = [{"section": p.get("section", ""), "locator": p["source_locator"],
             "excerpt": (p.get("text") or "")[:70],
             "depth": (p.get("section") or "").count(">")} for p in pieces]
    return {
        "doc_type": st["doc_type"],
        "adapter_version": mod.ADAPTER.get("adapter_version"),
        "payload_kind": kind,
        "regenerations": st.get("instructions") or [],
        "sections": {
            "parse_result": {
                "summary": {"samples": len(st["samples"]), "pieces": len(pieces),
                            "failures": sum(1 for a in anomalies if a["kind"] == "failure"),
                            "warnings": sum(1 for a in anomalies if a["kind"] == "warning"),
                            "fill_rate": fill},
                "anomalies": anomalies,
                "normal": {"excerpt": pieces[:EXCERPT], "all": pieces,
                           "columns": keys if kind == "table" else [],
                           "tree": tree if kind == "prose" else []},
            },
            "role_table": role_table(schema, mod),
            "adapter_summary": {
                "expects": mod.ADAPTER.get("expects") or {},
                "adapter_version": mod.ADAPTER.get("adapter_version"),
                "source": (ROOT / st["adapter"]).read_text(encoding="utf-8"),
            },
        },
    }


def cmd_review(doc_type, instruct=None):
    """② 검수 — 기계 관문 → 뷰 데이터 → HTML. 지시가 오면 **재생성 루프**를 돈다.

    **상한은 없다**(§7 규약 2 · A8 — 근거 없는 수치 금지). 매회 지시가 이력에 남고
    중단은 사람 판단이다. 화면에는 강제 없는 안내만 둔다.
    """
    st = _state(doc_type)
    if not st:
        raise SystemExit(f"[검수] '{doc_type}' 생성 단계가 먼저다")

    if instruct:                                   # 재생성 루프 1회
        st["revision"] += 1
        st.setdefault("instructions", []).append(
            {"n": st["revision"], "instruction": instruct, "at": _now()})
        ad, sc = draft(doc_type, st["revision"])
        if ad is None:
            print(f"   ⚠ 재생성 대안본 부재 — 초안을 유지한다 "
                  f"(USE_MOCK: fixture '{doc_type}_rev{st['revision']}' 없음)")
        else:
            st["adapter"], st["schema"] = (str(ad.relative_to(ROOT)),
                                           str(sc.relative_to(ROOT)))
            print(f"   재생성 {st['revision']}회째 → {ad.relative_to(ROOT)}")

    samples = st["samples"]
    print(f"■ ② 검수 — {doc_type} (표본 {len(samples)}부)")
    ok, out = harness(ROOT / st["adapter"], ROOT / st["schema"], samples)
    print(f"   기계 관문(하네스): {'PASS' if ok else 'FAIL'} — "
          f"{out.count('[PASS]')} PASS / {out.count('[FAIL]')} FAIL")

    mod = _load(ROOT / st["adapter"], f"reg_{doc_type}")
    results = [pipeline.parse(mod, f"{doc_type.upper()}{i:02d}", s, layer=st["layer"])
               for i, s in enumerate(samples, 1)]
    for r in results:
        print(f"   파싱 {r.doc_id}: {'OK' if r.ok else 'FAIL'} · "
              f"조각 {r.report.get('pieces', 0)}")

    view = build_view(st, results, ok, out)
    d = _dir(doc_type)
    (d / "view.json").write_text(json.dumps(view, ensure_ascii=False, indent=2) + "\n",
                                 encoding="utf-8")
    (d / "view.html").write_text(render(view), encoding="utf-8")   # kit 렌더러 호출
    st["machine_gate"] = "PASS" if (ok and all(r.ok for r in results)) else "FAIL"
    _save_state(doc_type, st)

    an = view["sections"]["parse_result"]["anomalies"]
    print(f"   뷰 데이터 → {(d / 'view.json').relative_to(ROOT)}  "
          f"(이상 신호 {len(an)}건 — 전량 표시)")
    print(f"   HTML     → {(d / 'view.html').relative_to(ROOT)}  (kit 렌더러)")
    for a in an:
        print(f"     [{a['kind']}] {a['message'][:70]}")
    if st.get("instructions"):
        print(f"   재생성 {len(st['instructions'])}회 — 상한 없음(중단은 사람 판단)")
    return 0 if st["machine_gate"] == "PASS" else 1


# ================================================================ ③ 확정
def cmd_confirm(doc_type, approved_by):
    """③ 확정 — 승인 1회로 등록부에 등재한다.

    **기계 관문 통과가 승인의 전제**다. "무수정 = 자동 통과"는 금지이므로 승인자가
    없으면 등재하지 않는다(틀 §2).
    """
    st = _state(doc_type)
    if not st:
        raise SystemExit(f"[확정] '{doc_type}' 생성·검수가 먼저다")
    if st.get("machine_gate") != "PASS":
        raise SystemExit(f"[확정] 기계 관문 미통과 — 검수를 먼저 통과시켜라 "
                         f"(현재 {st.get('machine_gate')})")
    if not approved_by:
        raise SystemExit("[확정] 승인자 미지정 — 무수정 자동 통과는 금지다 (틀 §2)")

    mod = _load(ROOT / st["adapter"], f"reg_{doc_type}")
    at = _now()
    entry = registry.register(
        doc_type, layer=st["layer"], adapter=st["adapter"], schema=st["schema"],
        adapter_version=mod.ADAPTER.get("adapter_version"),
        approved_by=approved_by, approved_at=at,
        instructions=st.get("instructions") or [])
    approval = {"doc_type": doc_type,
                "adapter_version": mod.ADAPTER.get("adapter_version"),
                "승인자": approved_by, "시점": at,
                "수정 지시 이력": st.get("instructions") or []}
    (_dir(doc_type) / "approval.json").write_text(
        json.dumps(approval, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"■ ③ 확정 — {doc_type} 등록부 등재 (승인 {approved_by} @ {at})")
    print(f"   어댑터·스키마 활성: {entry['adapter']} · {entry['schema']}")
    print(f"   승인 기록 → {(_dir(doc_type) / 'approval.json').relative_to(ROOT)}")
    return 0


def cmd_list():
    from cli.platform import cmd_doctypes
    return cmd_doctypes()


def main(argv):
    if not argv:
        raise SystemExit(__doc__)
    cmd, rest = argv[0], list(argv[1:])

    def opt(name, default=None):
        if name in rest:
            i = rest.index(name)
            v = rest[i + 1] if i + 1 < len(rest) else default
            del rest[i:i + 2]
            return v
        return default

    if cmd == "generate":
        hint = opt("--hint", "")
        return cmd_generate(rest[0], rest[1], rest[2:], hint)
    if cmd == "review":
        return cmd_review(rest[0], opt("--instruct"))
    if cmd == "confirm":
        return cmd_confirm(rest[0], opt("--by"))
    if cmd == "list":
        return cmd_list()
    raise SystemExit(f"알 수 없는 명령: {cmd}\n{__doc__}")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]) or 0)
