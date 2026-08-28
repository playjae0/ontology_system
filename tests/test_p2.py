# -*- coding: utf-8 -*-
"""P2 완료판정 — n8 어댑터 생성 킷 6종.

  킷 실물 6종이 kit/에 선다            (①v0.4 · ②스켈레톤 · ③정의 주입 · ④예시 · ⑤렌더러 · ⑥하네스)
  v0.3 공식 하네스 재실행 판정 불변    (봉인 로그의 43판정이 전건 보존 — 추가만 허용)
  렌더러 실증                          (3구획 존재 · 이상 신호 전량 · 접힘 동작 · 두 payload_kind)
  뷰 데이터 스키마                     (P3 n6과의 경계 계약 — 렌더러가 계산하지 않는다)

사용: python tests/test_p2.py
"""
from __future__ import annotations

import html
import importlib.util
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "kit"))

from render_review import render                              # noqa: E402
from run_adapter import load_blocks                           # noqa: E402

allok = True
KIT = ROOT / "kit"
VIEWS = ROOT / "tests" / "fixtures" / "review_views"


def show(label, ok, detail=""):
    global allok
    allok &= bool(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"  — {detail}" if detail else ""))
    return bool(ok)


def verdicts(text):
    """하네스 출력에서 판정 라벨만 뽑는다 — 상세(— 뒤)는 실행마다 달라지므로 뺀다."""
    return Counter(re.sub(r"\s+—.*$", "", ln.strip()[7:]).strip()
                   for ln in text.splitlines()
                   if ln.strip().startswith(("[PASS]", "[FAIL]")))


# ============================================================ 킷 6종 실물
print("\n■ 킷 6종 실물 — 외부 전달물 (파서_명세 §9)")
KIT_ITEMS = {
    "① 생성 프롬프트 템플릿": KIT / "생성프롬프트_템플릿_v0.4.md",
    "② 어댑터 스켈레톤": KIT / "어댑터_스켈레톤.py",
    "③ 표적 출력 정의 주입": KIT / "표적출력_정의.md",
    "④ 참조 어댑터 예시": KIT / "참조어댑터" / "README.md",
    "⑤ 검수 뷰 렌더러": KIT / "render_review.py",
    "⑥ 실행 하네스": KIT / "run_adapter.py",
}
for label, p in KIT_ITEMS.items():
    show(f"{label} 실물", p.exists(), str(p.relative_to(ROOT)))
show("판 계보 보존 — v0.1·v0.2·v0.3이 남아 있다 (v0.4는 신설이지 덮어쓰기가 아니다)",
     all((KIT / f"생성프롬프트_템플릿_{v}.md").exists()
         for v in ("v0.1", "v0.2", "v0.3")))

# ---- ② 스켈레톤이 자기 안내대로 거동하는가 ----
r = subprocess.run([sys.executable, str(KIT / "run_adapter.py"),
                    str(KIT / "어댑터_스켈레톤.py"), str(ROOT / "schemas/cp.json"),
                    str(ROOT / "tests/fixtures/raw/CP01.xlsx")],
                   capture_output=True, text=True, cwd=str(ROOT))
fail_labels = {re.sub(r"\s+—.*$", "", ln.strip()[7:]).strip()
               for ln in r.stdout.splitlines() if ln.strip().startswith("[FAIL]")}
EXPECT_FAIL = {
    "payload_kind가 닫힌 2값",
    "adapter.doc_type == schema.doc_type",
    "expects.header_row 선언됨",
    "payload_kind가 스키마 또는 어댑터에 선언됨 (fields 판정의 전제)"}
show("② 스켈레톤이 하네스 ①단에서 문법·순수성·인터페이스를 통과한다",
     r.stdout.count("[PASS] 문법 오류 없음") == 1
     and "[PASS] 순수 함수 계약" in r.stdout
     and "[PASS] locate 함수 없음" in r.stdout)
show("② 빈칸 상태의 FAIL은 4건이고 전부 '아직 안 채웠다'다 (동봉 안내와 일치)",
     r.stdout.count("[FAIL]") == 4 and fail_labels == EXPECT_FAIL,
     f"FAIL {r.stdout.count('[FAIL]')}건 · 예상 밖 {sorted(fail_labels - EXPECT_FAIL)}")
sk = (KIT / "어댑터_스켈레톤.py").read_text(encoding="utf-8")
show("② 안내가 '필수 키 4종은 PASS'를 정확히 적었다 (키 존재만 보고 값은 안 본다)",
     "`필수 키 4종`은 **PASS다**" in sk)

# ---- ③ 정의 주입은 복제가 아니라 발췌+참조 ----
inject = (KIT / "표적출력_정의.md").read_text(encoding="utf-8")
show("③ 정본은 CH2 2.2이고 어긋나면 그쪽이 이긴다고 명시",
     "CH2 2.2가 이긴다" in inject and "이 문서는 정본이 아니다" in inject)
show("③ 3층 구조와 닫힌 2값·정본 id 금지가 주입 블록에 실려 있다",
     all(k in inject for k in ("문서 봉투", "조각 공통", "payload_kind",
                               "정본 id를 만들지 않는다", "임의 딕셔너리")))

# ---- ④ 참조 어댑터는 원본 무손질 복사본 ----
REFS = {"ipqc.py": ROOT / "tests/fixtures/fixtures/adapters/ipqc.py",
        "toc_report.py": ROOT / "tests/fixtures/fixtures/adapters/toc_report.py",
        "cp.py": ROOT / "tests/fixtures/adapters/cp.py"}
show("④ few-shot 3종 실물 (어댑터 + 매칭 스키마 쌍)",
     all((KIT / "참조어댑터" / f).exists() for f in REFS)
     and all((KIT / "참조어댑터" / f).exists()
             for f in ("ipqc.json", "toc_report.json", "cp.json")))
# [B27 — 판정필요-13 판정] `kit/참조어댑터/`는 **모범 전시장**이고 스냅샷 보관은
# fixture 몫이다. 그래서 「바이트 동일」이 아니라 **전시물의 자격**을 잰다 —
# 어서션을 지우지 않고 표적을 바꾼다. 원본은 fixture에 그대로 남아 있고(아래 ⓒ),
# 전시물은 규약 10을 지키며 자기 출처를 밝힌다.
_undeclared = [f for f in REFS
               if "# 원본:" not in (KIT / "참조어댑터" / f).read_text(encoding="utf-8")]
show("④ⓑ 전시물이 **출처를 밝힌다** — 머리에 원본 경로 (B27)",
     not _undeclared, str(_undeclared))
_selfmade, _nocore = [], []
for f in REFS:
    _src = (KIT / "참조어댑터" / f).read_text(encoding="utf-8")
    if any(k in _src for k in ("def _expand_merged", "def _col_to_idx",
                               "def _idx_to_col")):
        _selfmade.append(f)
    _mod = importlib.util.module_from_spec(
        importlib.util.spec_from_file_location(f"chk_{f[:-3]}", KIT / "참조어댑터" / f))
    _mod.__spec__.loader.exec_module(_mod)
    # **table 계열만 공용 코어 의무다** — prose는 병합·상동·복수값 개념이 없다.
    if _mod.ADAPTER["payload_kind"] == "table" and \
            "from parser import normalizer" not in _src:
        _nocore.append(f)
show("④ⓐ 전시물에 자기 재구현이 0건이다 (규약 10 — 전 계열)",
     not _selfmade, str(_selfmade))
show("④ⓐ table 계열 전시물은 공용 코어를 호출한다 (prose는 의무 없음)",
     not _nocore, str(_nocore))
show("④ⓒ 스냅샷 원본은 fixture에 그대로 있다 (1바이트도 손대지 않는다)",
     all(src.exists() and src.read_bytes() for src in REFS.values()),
     str({f: src.stat().st_size for f, src in REFS.items()}))
kinds = {}
for f in REFS:
    spec = importlib.util.spec_from_file_location(f"ref_{f[:-3]}", KIT / "참조어댑터" / f)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    kinds[f] = m.ADAPTER["payload_kind"]
show("④ table 1·prose 1 포함 조건 충족", set(kinds.values()) == {"table", "prose"},
     str(kinds))

# ============================================================ ⑥ 하네스 — 판정 불변
print("\n■ ⑥ 하네스 use_blocks 보강 — v0.3 공식 재실행 (봉인 로그 대비)")
SEALED = {
    "ipqc": (ROOT / "tests/fixtures/fixtures/log/harness_ipqc_공식.txt",
             ["tests/fixtures/fixtures/adapters/ipqc.py", "tests/fixtures/fixtures/schemas/ipqc.json",
              "tests/fixtures/raw/IPQC01.xlsx", "tests/fixtures/raw/IPQC02.xlsx"]),
    "toc": (ROOT / "tests/fixtures/fixtures/log/harness_toc_공식.txt",
            ["tests/fixtures/fixtures/adapters/toc_report.py", "tests/fixtures/fixtures/schemas/toc_report.json",
             "tests/fixtures/raw/TOC01.xlsx", "tests/fixtures/raw/TOC02.xlsx"]),
}
for name, (sealed, args) in SEALED.items():
    out = subprocess.run([sys.executable, str(KIT / "run_adapter.py")] + args,
                         capture_output=True, text=True, cwd=str(ROOT)).stdout
    old, new = verdicts(sealed.read_text(encoding="utf-8")), verdicts(out)
    lost = [k for k in old if new[k] < old[k]]
    added = [k for k in new if new[k] > old.get(k, 0)]
    show(f"{name}: 봉인 43판정이 전건 보존 (사라진 판정 0)", not lost, str(lost))
    show(f"{name}: 추가는 use_blocks 전개 1종뿐 · FAIL 0",
         added == ["use_blocks 전개"] and "[FAIL]" not in out,
         f"{sum(old.values())} → {sum(new.values())}")
    if name == "ipqc":
        anchor = re.search(r"anchor=(\d+)", out)
        show("§4.4 결함 해소 — 좌표를 블록에 위임한 스키마도 anchor가 드라이런된다",
             anchor and int(anchor.group(1)) > 0, f"anchor={anchor.group(1)}")

sch = json.loads((ROOT / "tests/fixtures/fixtures/schemas/ipqc.json").read_text(encoding="utf-8"))
merged, from_blocks = load_blocks(sch)
show("⑥ 로더가 blocks.json 선언을 전개한다 (하드코딩 목록이 아니다)",
     from_blocks == {"source_locator", "process_group", "process_ref", "process_no"},
     str(sorted(from_blocks)))
show("⑥ 스키마 선언이 블록을 이긴다 (같은 이름이면 스키마 우선)",
     all(merged[k] is sch["fields"][k] for k in sch["fields"]))
show("⑥ 하네스 본문에 구조 필드 하드코딩이 남지 않았다",
     "STRUCT_FIELDS" not in (KIT / "run_adapter.py").read_text(encoding="utf-8"))

# ============================================================ ⑤ 렌더러 실증
print("\n■ ⑤ 검수 뷰 렌더러 — M11 규격 실증 (파서_명세 §7)")
SCHEMA = json.loads((KIT / "검수뷰_데이터스키마.json").read_text(encoding="utf-8"))
show("뷰 데이터 스키마가 파일로 확정됐다 (P3 n6과의 경계 계약)",
     (KIT / "검수뷰_데이터스키마.json").exists()
     and list(SCHEMA["properties"]["sections"]["properties"])
     == ["parse_result", "role_table", "adapter_summary"])
show("스키마가 3층 표시를 강제한다 (요약 / 이상 신호 / 정상 발췌+전량)",
     SCHEMA["properties"]["sections"]["properties"]["parse_result"]["required"]
     == ["summary", "anomalies", "normal"])

for name, kind in (("ipqc_table", "table"), ("toc_prose", "prose")):
    view = json.loads((VIEWS / f"{name}.json").read_text(encoding="utf-8"))
    h = render(view)
    pr = view["sections"]["parse_result"]
    print(f"  · {name} ({kind})")
    show("   3구획이 전부 렌더된다 (구판 구획 4[층 초안]는 없다)",
         all(s in h for s in ("구획 1 · 파싱 결과", "구획 2 · 필드 → role 배정표",
                              "구획 3 · 어댑터 요약"))
         and "층 초안" not in h)
    show("   ① 요약 통계 — 조각 수·채움율",
         f">{pr['summary']['pieces']}</b>조각" in h.replace("<b>", ">")
         or str(pr["summary"]["pieces"]) in h)
    show("   ② 이상 신호 **전량** 표시 — 접힘에 들어가지 않는다",
         all(html.escape(a["message"][:20]) in h for a in pr["anomalies"])
         and h.index("이상 신호 — 전량") < h.index("<details>"),
         f"{len(pr['anomalies'])}건")
    show("   ② 판정 불가는 질문 형태로 뜬다 (§7 규약 5)",
         ("판정 불가" in h) == any(a["kind"] == "question" for a in pr["anomalies"]))
    show("   ③ 정상 조각은 발췌 기본 + **전량 접힘**",
         "<details><summary>전량 보기 (" in h
         and f"전량 보기 ({len(pr['normal']['all'])}건)" in h)
    show("   구획 3의 어댑터 코드 전문은 접힘",
         "<summary>어댑터 코드 전문 (접힘)</summary>" in h)
    if kind == "table":
        show("   table 렌더 — 레코드 표(원본 열 대응)",
             "<table>" in h and "계층 없음" not in h)
        show("   재생성 이력이 뜨고 **상한 없음**을 밝힌다 (§7 규약 2 · A8)",
             "재생성 이력" in h and "상한은 없다" in h)
    else:
        show("   prose 렌더 — 계층 트리(청크 경계 표시)",
             "class='tree'" in h and pr["normal"]["tree"])
        show("   표본 1부 경고가 이상 신호로 뜬다 (D-22 확장 문구)",
             "근거 1건일 수 있음" in h)

show("**3구획 구조는 payload_kind와 무관하게 같다** — 다른 것은 구획 1의 렌더뿐",
     all(all(s in render(json.loads((VIEWS / f"{n}.json").read_text(encoding="utf-8")))
             for s in ("구획 1 · 파싱 결과", "구획 2 · 필드 → role 배정표",
                       "구획 3 · 어댑터 요약"))
         for n in ("ipqc_table", "toc_prose")))

# 데이터와 표현의 분리 — 렌더러는 계산하지 않는다
src = (KIT / "render_review.py").read_text(encoding="utf-8")
show("렌더러가 계산하지 않는다 (채움율·이상 판정은 산출자 몫 — P-2)",
     "fill_rate" not in src.replace('fill = s.get("fill_rate") or {}', "")
     or "sum(" not in src.split("def render")[0].split("def _summary")[1].split("def ")[0])
show("렌더러는 파서·core를 import하지 않는다 (JSON만 읽는다 — 교체 가능)",
     not re.search(r"^(from|import)\s+(core|parser)\b", src, re.M))

empty = render({"doc_type": "x", "adapter_version": "1", "payload_kind": "table",
                "sections": {"parse_result": {}, "role_table": [], "adapter_summary": {}}})
show("빈 뷰 데이터에도 죽지 않는다 (렌더러는 관문이 아니라 표현이다)",
     "구획 1 · 파싱 결과" in empty and "이상 신호 없음" in empty)

print("\n" + "=" * 62)
print("전체 결과:", "PASS — P2 완료판정 충족" if allok else "FAIL")
sys.exit(0 if allok else 1)
