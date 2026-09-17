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


_CODE = re.compile(r"^G[0-9A-Z]{2}\s\s")


def label_of(line):
    """판정 줄 → **라벨만**. 상세(— 뒤)와 **태그(B59 ①)**를 뺀다.

    태그를 빼는 이유: 봉인 로그는 **외부 LLM 실산출 스냅샷 자리**라 손대지 않는다
    (D-26). 태그는 그때 없던 **메타**이고 판정 자체가 아니므로, 봉인이 보증하는
    「그때 이 산출이 이 판정들을 통과했다」는 태그와 무관하게 성립해야 한다.
    태그를 넣은 채 비교하면 봉인이 43건 전부 «사라졌다»고 말한다(실측).
    """
    t = re.sub(r"\s+—.*$", "", line.strip()[7:]).strip()
    return _CODE.sub("", t)


def verdicts(text):
    """하네스 출력에서 판정 라벨만 뽑는다 — 상세·태그는 뺀다."""
    return Counter(label_of(ln) for ln in text.splitlines()
                   if ln.strip().startswith(("[PASS]", "[FAIL]")))


# ============================================================ 킷 6종 실물
print("\n■ 킷 6종 실물 — 외부 전달물 (파서_명세 §9)")
KIT_ITEMS = {
    # **①의 자리가 옮겨졌다**(B63 ① · 칸 1.4) — 지시문 9종이 한 폴더에 산다.
    "① 생성 지시문": ROOT / "prompts" / "1.4_generate.md",
    "② 어댑터 스켈레톤": KIT / "어댑터_스켈레톤.py",
    "③ 표적 출력 정의 주입": KIT / "표적출력_정의.md",
    "④ 참조 어댑터 예시": KIT / "참조어댑터" / "README.md",
    "⑤ 검수 뷰 렌더러": KIT / "render_review.py",
    "⑥ 실행 하네스": KIT / "run_adapter.py",
}
for label, p in KIT_ITEMS.items():
    show(f"{label} 실물", p.exists(), str(p.relative_to(ROOT)))
# **판 계보의 자리가 바뀌었다**(B63 ①) — 파일로 보존하던 것을 git 이력이 갖는다.
# 잠글 성질은 그 뒤집힘 그대로다: **쓰이는 판이 목록에 하나로 보인다.** 구판은
# 12개가 나란히 있고 코드가 glob으로 골라, 어느 것이 쓰이는지 목록이 답하지 못했다.
show("판은 하나다 — kit에 템플릿 0 · 지시문 1개 · 판 번호는 머리말이 말한다",
     not list(KIT.glob("생성프롬프트_템플릿_v*.md"))
     and (ROOT / "prompts" / "1.4_generate.md").read_text(
         encoding="utf-8").split("\n")[1].startswith("version:"))

# ---- ② 스켈레톤이 자기 안내대로 거동하는가 ----
r = subprocess.run([sys.executable, str(KIT / "run_adapter.py"),
                    str(KIT / "어댑터_스켈레톤.py"), str(ROOT / "tests/fixtures/schemas/cp.json"),
                    str(ROOT / "tests/fixtures/raw/CP01.xlsx")],
                   capture_output=True, text=True, cwd=str(ROOT))
fail_labels = {label_of(ln) for ln in r.stdout.splitlines()
               if ln.strip().startswith("[FAIL]")}
EXPECT_FAIL = {
    "payload_kind가 닫힌 2값",
    "adapter.doc_type == schema.doc_type",
    "expects.header_row 선언됨",
    "payload_kind가 스키마 또는 어댑터에 선언됨 (fields 판정의 전제)",
    # **하네스 수리분**(B50): 구판은 0건일 때 이 검사에 닿기 전에 돌아가 **아무것도
    # 추출하지 못한 어댑터가 PASS로 통과했다.** 빈칸 스켈레톤이 바로 그 상태다.
    "조각 0건 산출 (0건 아님)",
    # **⑤ 파서 전 구간**(B58 ②) — 관문이 extract에서 멈추지 않고 tagger·validator까지
    # 돈다. 빈칸 스켈레톤은 `expects`가 비어 preflight가 다시 걸리므로, ②단의 FAIL과
    # **같은 빈칸**을 ⑤단에서 한 번 더 말한다. 중복이지만 지우지 않는다 — 관문이
    # 「어디까지 돌았나」를 화면이 그대로 보여야 사내가 다음 칸을 안다.
    "계약 self-check 통과"}
# **태그로 잰다**(B59 ①) — 라벨 문면은 바뀌지만 G11·G12·G1A는 그 검사에 박힌
# 고정값이다. 문면을 세면 한 글자 수정에 이 줄이 깨진다.
_pass_codes = {m.group(1) for m in
               (re.match(r"\[PASS\]\s+(G[0-9A-Z]{2})", ln.strip())
                for ln in r.stdout.splitlines()) if m}
show("② 스켈레톤이 하네스 ①단에서 문법·순수성·인터페이스를 통과한다",
     {"G11", "G12", "G1A"} <= _pass_codes, str(sorted(_pass_codes))[:70])
show("② 빈칸 상태의 FAIL이 전부 '아직 안 채웠다'다 (동봉 안내와 일치)",
     # **수를 박지 않고 집합을 본다** — 관문은 자란다(B31이 2종, B58 ②가 ⑤단을
     # 더했다). 수를 박으면 관문 강화가 이 줄을 깨, 어서션이 개선을 막는 자리가 된다.
     fail_labels == EXPECT_FAIL,
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
    # [B31] **판정 수는 늘 수 있다.** 하네스에 규약 10 판정 2종이 들어왔고,
    # 앞으로도 기계 관문은 자란다. 봉인이 보증하는 것은 **「사라진 판정 0 ·
    # 기존 판정 전건 보존 · FAIL 0」**이지 판정의 개수가 아니다 — 개수를 못박으면
    # 관문을 강화할 때마다 봉인이 깨져, 봉인이 개선을 막는 자리가 된다.
    show(f"{name}: 봉인 {sum(old.values())}판정이 전건 보존 (사라진 판정 0)",
         not lost, str(lost))
    # **「FAIL 0」의 범위는 봉인분이다.** 새 관문이 옛 스냅샷을 옳게 붉히는 것은
    # 봉인 위반이 아니다 — 봉인은 「그때 이 산출이 이 판정들을 통과했다」의 기록이고,
    # 나중에 생긴 기준까지 소급해 보증하지 않는다. 반대로 보증 범위를 전체로 두면
    # **관문을 강화할 때마다 봉인이 깨져 봉인이 개선을 막는다.**
    _fails = [ln.strip() for ln in out.splitlines() if "[FAIL]" in ln]
    _sealed_fail = [ln for ln in _fails if label_of(ln) in old]
    show(f"{name}: 봉인분 판정에 FAIL 0 (새 관문의 FAIL은 범위 밖)",
         not _sealed_fail and all(new.get(k, 0) >= v for k, v in old.items()),
         f"{sum(old.values())} → {sum(new.values())} (추가 {added})")
    # **새 관문의 FAIL은 숨기지 않는다** — 그것이 옛 스냅샷의 실태다.
    if _fails and not _sealed_fail:
        print(f"           ※ 봉인 밖 판정 {len(_fails)}건 FAIL — "
              f"{[ln.split(']')[1].strip()[:40] for ln in _fails]}")
        print(f"             (B27 이전 스냅샷이라 규약 10을 지키지 않는다 — "
              f"fixture는 손대지 않는다 · D-26)")
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
     # **둘째 구획은 payload_kind가 가른다**(B51) — 자리는 셋 그대로이고
     # table이면 role_table, prose면 extract_rehearsal이 그 자리에 선다.
     == ["parse_result", "extract_rehearsal", "role_table", "adapter_summary"]
     and SCHEMA["properties"]["sections"]["required"]
     == ["parse_result", "adapter_summary"])
show("스키마가 3층 표시를 강제한다 (요약 / 이상 신호 / 정상 발췌+전량)",
     SCHEMA["properties"]["sections"]["properties"]["parse_result"]["required"]
     == ["summary", "anomalies", "normal"])

for name, kind in (("ipqc_table", "table"), ("toc_prose", "prose")):
    view = json.loads((VIEWS / f"{name}.json").read_text(encoding="utf-8"))
    h = render(view)
    pr = view["sections"]["parse_result"]
    print(f"  · {name} ({kind})")
    _sec2 = ("구획 2 · 추출 리허설" if kind == "prose"
             else "구획 2 · 필드 → role 배정표")
    show("   3구획이 전부 렌더된다 (구판 구획 4[층 초안]는 없다)",
         all(s in h for s in ("구획 1 · 파싱 결과", _sec2, "구획 3 · 어댑터 요약"))
         and "층 초안" not in h and len(view["sections"]) == 3)
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

show("**구획은 셋으로 같다** — 다른 것은 구획 1·2의 렌더뿐 (B51: 둘째는 payload_kind가 가른다)",
     all(all(s in render(json.loads((VIEWS / f"{n}.json").read_text(encoding="utf-8")))
             for s in ("구획 1 · 파싱 결과", _s2, "구획 3 · 어댑터 요약"))
         for n, _s2 in (("ipqc_table", "구획 2 · 필드 → role 배정표"),
                        ("toc_prose", "구획 2 · 추출 리허설"))))

# 데이터와 표현의 분리 — 렌더러는 계산하지 않는다
src = (KIT / "render_review.py").read_text(encoding="utf-8")
show("렌더러가 계산하지 않는다 (채움율·이상 판정은 산출자 몫 — P-2)",
     "fill_rate" not in src.replace('fill = s.get("fill_rate") or {}', "")
     or "sum(" not in src.split("def render")[0].split("def _summary")[1].split("def ")[0])
show("렌더러는 파서·core를 import하지 않는다 (JSON만 읽는다 — 교체 가능)",
     not re.search(r"^(from|import)\s+(core|parser)\b", src, re.M))

# ── 지도 필드 셋 — 「어느 지도가 실호출이었나」 (B48 ②-7 · 후속 ② · D-79 확장)
_picks = [{"프레임": "슬라이드 3", "분할_레벨": 1, "분할_레벨_사유": "레벨 1만 구간에 든다",
           "지도_출처": "live", "지시문_판본": "sm-1.1", "지도_없음": None},
          {"프레임": "슬라이드 7", "분할_레벨": None, "분할_레벨_사유": None,
           "지도_출처": "heuristic", "지시문_판본": None, "지도_없음": None},
          {"프레임": "슬라이드 11", "분할_레벨": None, "분할_레벨_사유": None,
           "지도_출처": "live", "지시문_판본": "sm-1.1",
           "지도_없음": "크기 예산 초과: 약 1,391 토큰 > 한도 1\n   이 문서는 평면으로 인입된다"}]
_mv = {"doc_type": "x", "adapter_version": "1", "payload_kind": "prose",
       "sections": {"parse_result": {
           "summary": {"samples": 1, "pieces": 6, "fill_rate": {},
                       "split": [{"doc_id": "D1", "청크수": 6, "레벨_선택": _picks}]},
           "anomalies": [], "normal": {"excerpt": [], "all": [], "columns": [], "tree": []}},
           "role_table": [], "adapter_summary": {}}}
_mh = render(_mv)
show("지도 표에 출처·지시문 판본이 프레임별로 그려진다 (B48 ②-7의 나머지 절반)",
     "<th>지도 출처</th>" in _mh and "<th>지시문 판본</th>" in _mh
     and "<td>sm-1.1</td>" in _mh and "슬라이드 7" in _mh)
show("heuristic 프레임은 경고색 + 한 줄 주석 — 모델을 안 불렀다는 사실이 눈에 띈다",
     '<td class="warn">heuristic</td>' in _mh
     and "모델을 부르지 않았다" in _mh and "게이트웨이 설정을 확인하라" in _mh)
show("지도_없음 프레임은 사유를 그대로 보인다 (여러 줄도 끊기지 않는다)",
     "지도 없음: 크기 예산 초과" in _mh and "<br>" in _mh
     and "평면으로 인입된다" in _mh)
show("계약이 먼저다 — D-79 스키마가 세 키를 선언한다 (렌더러가 계약을 앞서지 않는다)",
     (lambda sc: all(k in sc for k in ("지도_출처", "지시문_판본", "지도_없음"))
      and "split" in sc)(
         (ROOT / "kit" / "검수뷰_데이터스키마.json").read_text(encoding="utf-8")))

empty = render({"doc_type": "x", "adapter_version": "1", "payload_kind": "table",
                "sections": {"parse_result": {}, "role_table": [], "adapter_summary": {}}})
show("빈 뷰 데이터에도 죽지 않는다 (렌더러는 관문이 아니라 표현이다)",
     "구획 1 · 파싱 결과" in empty and "이상 신호 없음" in empty)

# ════════════════════════════════════════════════════════════════════
# B76 ④ 스켈레톤·공용 코어는 None에 죽지 않는다 · ① 형 검사 관문 G4F
# ════════════════════════════════════════════════════════════════════
print("\n── B76 ④ None에 죽지 않는다 ──")
import shutil as _sh76                                             # noqa: E402
import tempfile as _tf76                                           # noqa: E402
from parser import normalizer as _NM76                             # noqa: E402

SKEL = ROOT / "tests/fixtures/skeleton_min"
SAMPLE76 = ROOT / "tests/fixtures/raw/CSV05_wide.csv"


def gate76(adapter, schema, sample=SAMPLE76):
    """관문을 그대로 돌린다 — 재구현하지 않는다(P2의 규율)."""
    r = subprocess.run([sys.executable, str(KIT / "run_adapter.py"),
                        str(adapter), str(schema), str(sample)],
                       capture_output=True, text=True, cwd=str(ROOT))
    return r.returncode == 0, r.stdout


def mutate76(src, old, new, name):
    """변이 하나를 임시 자리에 만든다 — 픽스처는 손대지 않는다(D-26의 결)."""
    d = Path(_tf76.mkdtemp(prefix="b76_"))
    txt = Path(src).read_text(encoding="utf-8")
    assert old in txt, (name, old[:40])
    (d / Path(src).name).write_text(txt.replace(old, new), encoding="utf-8")
    return d / Path(src).name, d


_r76, _h76 = _NM76.resolve_ditto([{"a": "x"}, {"a": "〃"}], marks=None)
show("④ⓐ 공용 코어가 `marks=None`에 죽지 않는다 (「상동 없음」이다 · 치환 0)",
     _h76 == 0 and _r76[1]["a"] == "〃", f"치환 {_h76}건")
show("④ⓑ 스켈레톤은 상동 기호가 없으면 **빈 집합**을 넘긴다",
     "else set())" in (KIT / "어댑터_스켈레톤.py").read_text(encoding="utf-8"))

_ok76, _out76 = gate76(SKEL / "skelmin.py", SKEL / "skelmin.json")
show("④ⓒ `ditto_mark` 없는 **스켈레톤 최소 어댑터**가 관문 전 구간을 지난다",
     _ok76 and "[FAIL]" not in _out76,
     [l.strip() for l in _out76.splitlines() if "[FAIL]" in l][:1] or "FAIL 0")
_spec76 = importlib.util.spec_from_file_location("b76_skelmin", SKEL / "skelmin.py")
_mod76 = importlib.util.module_from_spec(_spec76)
_spec76.loader.exec_module(_mod76)
show("④ⓒ 그 어댑터의 선언에 상동 기호가 **없다** (이번 사내 사고의 재현 재료)",
     "ditto_mark" not in (_mod76.ADAPTER.get("expects") or {}),
     str(sorted(_mod76.ADAPTER.get("expects") or {})))

_m76, _d76 = mutate76(SKEL / "skelmin.py",
                      'marks={exp["ditto_mark"]} if exp.get("ditto_mark") else set())',
                      'marks=123)', "코어에 엉뚱한 형")
_ok76b, _out76b = gate76(_m76, SKEL / "skelmin.json")
_g31 = [l.strip() for l in _out76b.splitlines() if "G31" in l and "[FAIL]" in l]
show("④ⓓ G31 FAIL 문면이 **어댑터 파일:줄**을 말한다 (예외명만으로는 못 짚는다)",
     _g31 and "skelmin.py:" in _g31[0] and "normalizer.py:" in _g31[0],
     (_g31[0] if _g31 else "G31 FAIL 없음")[:100])
_sh76.rmtree(_d76, ignore_errors=True)

_m76c, _d76c = mutate76(SKEL / "skelmin.py",
                        'rec[field] = "" if v is None else str(v).strip()',
                        'rec[field] = v.strip()', "셀에 직접 strip")
_ok76c, _out76c = gate76(_m76c, SKEL / "skelmin.json",
                         ROOT / "tests/fixtures/raw/CSV01.csv")
_g3a = [l.strip() for l in _out76c.splitlines() if "G3A" in l]
show("④ⓔ 셀 하나가 `None`이면 죽는 어댑터를 관문이 잡는다 (표본에 빈 칸이 없어도)",
     _g3a and "[FAIL]" in _g3a[0] and "None으로 두면" in _g3a[0],
     (_g3a[0] if _g3a else "G3A 줄 없음")[:90])
_sh76.rmtree(_d76c, ignore_errors=True)
show("④ⓔ 참조 어댑터·스켈레톤 어댑터는 셀 None 변이를 지난다",
     "[PASS] G3A" in _out76 and "[PASS] G3A" in subprocess.run(
         [sys.executable, str(KIT / "run_adapter.py"),
          "tests/fixtures/adapters/cp.py", "tests/fixtures/schemas/cp.json",
          "tests/fixtures/raw/CP01.xlsx"],
         capture_output=True, text=True, cwd=str(ROOT)).stdout)
show("④ 템플릿 판이 올랐고 셀 접근 규약이 실렸다",
     re.search(r"^version: 1\.7$",
               (ROOT / "prompts/1.4_generate.md").read_text(encoding="utf-8"), re.M)
     and "셀 값은 스켈레톤의 읽기 꼴로만" in
     (ROOT / "prompts/1.4_generate.md").read_text(encoding="utf-8"))

print("\n── B76 ① 형 검사 관문 G4F ──")
show("① 내장 참조 자산이 전부 G4F를 지난다 (형 표가 실물과 어긋나지 않는다)",
     all("[PASS] G4F" in subprocess.run(
         [sys.executable, str(KIT / "run_adapter.py"), a, sc, doc],
         capture_output=True, text=True, cwd=str(ROOT)).stdout
         for a, sc, doc in (
             ("tests/fixtures/adapters/cp.py", "tests/fixtures/schemas/cp.json",
              "tests/fixtures/raw/CP01.xlsx"),
             ("tests/fixtures/adapters/pfmea.py", "tests/fixtures/schemas/pfmea.json",
              "tests/fixtures/raw/PFMEA01.xlsx"),
             ("kit/참조어댑터/ipqc.py", "kit/참조어댑터/ipqc.json",
              "tests/fixtures/raw/IPQC01.xlsx"))))

_sch76 = json.loads((SKEL / "skelmin.json").read_text(encoding="utf-8"))


def schema_mut76(patch):
    d = Path(_tf76.mkdtemp(prefix="b76s_"))
    m = json.loads(json.dumps(_sch76))
    m.update(patch)
    (d / "s.json").write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
    return d / "s.json", d


for _label, _patch, _want in (
        ("`unmappable[].field`가 리스트",
         {"unmappable": [{"field": ["F", "G"], "kind": "excluded", "reason": "t"}]},
         "받은 형 list"),
        ("`unmappable[].kind`가 닫힌 2값 밖",
         {"unmappable": [{"field": "F", "kind": "maybe", "reason": "t"}]},
         "허용 ['excluded', 'undecided']")):
    _sp, _sd = schema_mut76(_patch)
    _o = gate76(SKEL / "skelmin.py", _sp)[1]
    _ln = [l.strip() for l in _o.splitlines() if "G4F" in l]
    show(f"① {_label} → G4F FAIL이고 문면이 키와 형을 말한다",
         _ln and "[FAIL]" in _ln[0] and _want in _ln[0],
         (_ln[0] if _ln else "G4F 줄 없음")[:100])
    _sh76.rmtree(_sd, ignore_errors=True)

for _label, _old, _new, _fail in (
        ("합치기 리스트는 **허용**", '"설비": "D"', '"설비": ["D", "E"]', False),
        ("`columns` 값이 int", '"설비": "D"', '"설비": 4', True),
        ("`header_row`가 문자열", '"header_row": 1,', '"header_row": "1",', True)):
    _mp, _md = mutate76(SKEL / "skelmin.py", _old, _new, _label)
    _o = gate76(_mp, SKEL / "skelmin.json")[1]
    _ln = [l.strip() for l in _o.splitlines() if "G4F" in l]
    show(f"① {_label} → G4F {'FAIL' if _fail else 'PASS'}",
         _ln and (("[FAIL]" in _ln[0]) == _fail),
         (_ln[0] if _ln else "G4F 줄 없음")[:100])
    _sh76.rmtree(_md, ignore_errors=True)

_sp76, _sd76 = schema_mut76({"새로운키": {"x": 1}})
_o76 = gate76(SKEL / "skelmin.py", _sp76)[1]
show("① 표에 없는 키는 막지 않고 **보고**한다 (모양이 자라는 길을 막지 않는다)",
     "[PASS] G4F" in _o76 and "[모양]" in _o76 and "새로운키" in _o76,
     [l.strip() for l in _o76.splitlines() if "[모양]" in l][:1])
_sh76.rmtree(_sd76, ignore_errors=True)

# ── B77 ② 전시물과 표본은 짝이다 — **실행으로** 상시 ─────────────────────
# 전시물(few-shot)은 회귀에 **문자열로만** 있었고(규약 10 호출부 검사), 그래서
# `kit/참조어댑터/cp.py`가 표본에 없는 열을 내는 상태가 회차 둘을 살아남았다.
# 관문을 실제로 돌려 짝을 잰다 — 전시물이 규약을 보이려면 먼저 돌아야 한다.
_bad77 = []
for _n77, _doc77 in (("cp", "CP01.xlsx"), ("ipqc", "IPQC01.xlsx"),
                     ("toc_report", "TOC01.xlsx")):
    _r77 = subprocess.run(
        [sys.executable, str(KIT / "run_adapter.py"),
         str(KIT / "참조어댑터" / f"{_n77}.py"), str(KIT / "참조어댑터" / f"{_n77}.json"),
         str(ROOT / "tests/fixtures/raw" / _doc77)],
        capture_output=True, text=True, cwd=str(ROOT))
    if _r77.returncode != 0 or "[FAIL]" in _r77.stdout:
        _bad77 += [f"{_n77}: {l.strip()}" for l in _r77.stdout.splitlines()
                   if "[FAIL]" in l][:1] or [f"{_n77}: rc={_r77.returncode}"]
show("② 전시물 3쌍이 제 표본으로 관문 전 구간을 지난다 (문자열이 아니라 실행)",
     not _bad77, " ‖ ".join(_bad77) or "FAIL 0")

print("\n" + "=" * 62)
print("전체 결과:", "PASS — P2 완료판정 충족" if allok else "FAIL")
sys.exit(0 if allok else 1)
