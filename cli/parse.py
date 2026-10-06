# -*- coding: utf-8 -*-
"""칸 2.1~2.9 — 파서 CLI — 운영 파싱 + 구축 모드 3단 배선 (파서_명세 §6 · 증분0 §3 P1).

모든 단계는 **CLI 진입점 + 파일 입출력**이다(§16.1 계약 1) — 플랫폼이 subprocess로
부른다. 파서는 별도 프로그램이고 에이전트와의 결합은 **계약 JSON 하나**다(D-9).

  python cli/parse.py run   <어댑터.py> <문서> [출력.json] [--doc-id X]  운영 파싱 1회
       └ `--coord-llm off|<종수>` — 좌표 태깅에서 **묻는 표기 종수**의 상한(기본 100)
       └ `--sheets "2-3:prose 4:ref *:ref"` — 시트 역할(B83 ③ · 기록은 `ingest-file`과 같다 · `auto`면 자동 모드)
       └ `--no-images` — 그림을 요약하지 않는다(B88 ① · 게이트웨이가 그림을 못 받을 때 — 기록에 남는다)
       └ doc_id는 생략하면 **파일명에서 파생**한다 — `ingest-file`과 같은 함수(D-110)
         구형 `<어댑터.py> <doc_id> <문서> [출력.json]`도 그대로 받는다
  python cli/parse.py head  <문서> [N]                                관찰 재료(등록 세션 공급)
  python cli/parse.py build <어댑터.py> <doc_type> <표본...>          구축 모드 3단 배선

**구축 모드 3단의 경계**: 여기는 **배선**까지다 — 생성(어댑터 초안)·검수 뷰 렌더·
등록부 등재는 P2·P3의 몫이다. 이 자리가 하는 일은 "세 단계가 실제로 이어지는가"를
파일로 드러내는 것이고, 각 단계의 산출을 `review/{doc_type}/`에 남긴다.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

from cli import _screen
from cli._gate import require_live_or_allow    # mock 관문 (B48)
from cli.prompt import _dir as review_dir      # 폴더를 만드는 자리는 하나다 (B77 ④)
from core.state.bootstrap import coord_layer
from core import paths
from core.llm import gateway, points, struct_map_pass
from parser import pipeline, preflight, reader, validator

PARSED_DIR = paths.parsed()    # 운영 산출 자리 (문서 7 §7.8 — 파일 존재 = 파싱 완료)
REVIEW = paths.review()


def injections():
    """파서에 내려보낼 **LLM 함수 3종을 한 번에 만든다** (문서 7 §7.6-B-1 · B48).

    **모드는 여기서 한 번 정하고 아래로 내려간다.** 파서에는 「지금 mock인가」라는
    질문이 없으므로(파서 무판독), 「실호출 모드인데 함수가 안 왔다」를 잡을 수 있는
    자리는 **만드는 쪽**뿐이다. 그 검사가 아래 assert이고, 그것이 곧
    「진입점이 한 번 정해 전부 내려보낸다」의 기계 판정이다(§7.6-B-2 도달 가능성).

    팩토리는 실호출 모드에서 미설정이면 `require()`로 이미 멈춘다 — 그래서 여기
    None은 **mock 모드에서만** 온다. 배선이 하나 빠지면(팩토리가 없거나 주입을
    빠뜨리면) 실호출 모드에서 None이 남아 이 자리가 붉는다.
    """
    fns = {"summarize": points.image_summarizer(),
           "pick_coord": points.coord_picker(),
           "map_structure": struct_map_pass.struct_mapper(),
           # ⑦ 안의 계층 규칙 선언(B87 ②) — 고정 규칙으로 안 선 시트에서만 파서가 부른다
           "infer_rules": struct_map_pass.rule_inferrer()}
    if not gateway.use_mock():
        missing = [k for k, v in fns.items() if v is None]
        if missing:
            raise gateway.NotConfigured(
                f"실호출 모드인데 파서 주입 함수가 비어 있다: {missing} — "
                f"휴리스틱으로 조용히 떨어지면 그 지도가 청크 경계를 정하고, "
                f"바뀐 경계는 chunk_id를 바꿔 재인입 멱등까지 흔든다 (문서 7 §7.6-B-2)")
    return fns


def load_adapter(path):
    spec = importlib.util.spec_from_file_location(f"ad_{Path(path).stem}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# 좌표 태깅 상한의 **정본**(B69 ③) — 묻는 **표기 종수**의 기본 상한.
# 행 수가 아니다: 같은 표기를 여러 행이 써도 묻는 것은 한 번이다(B69 ①).
# `--coord-llm off | <종수>`로 덮는다. 기본을 0(끔)으로 두지 않는 이유: 골격 표기가
# 조금만 달라도 전 문서가 목록 밖이 되고, 그러면 인입이 orphan_anchor만 쌓는다.
COORD_CAP = 100


def coord_cap_of(args):
    """`--coord-llm off|<종수>`를 args에서 떼어 `(남은 args, 상한)`.

    **`off`는 0이다** — None(무제한)과 다르다. 값이 숫자가 아니면 사용법 오류다:
    조용히 기본값으로 떨어지면 사람은 상한을 준 줄 안다.
    """
    args = list(args)
    if "--coord-llm" not in args:
        return args, COORD_CAP
    i = args.index("--coord-llm")
    v = args[i + 1] if i + 1 < len(args) else None
    del args[i:i + 2]
    if v == "off":
        return args, 0
    try:
        return args, max(0, int(v))
    except (TypeError, ValueError):
        raise SystemExit(f"[parse] --coord-llm 값이 종수나 off가 아니다: {v!r}\n"   # [사용법]
                         f"  예: --coord-llm 200 · --coord-llm off")


def print_read_warnings(report):
    """**읽다가 버린 그림 한 줄**(B86 ④) — 원문 경고는 로그 파일로 갔다.

    `그림 n개를 읽지 못해 건너뜀(WMF k)` — 그 그림이 이미지 요약에서 빠진다는 사실이
    사람이 알 정보다. 경고가 없으면 줄도 없다.
    """
    rw = (report or {}).get("read_warnings") or {}
    dropped = rw.get("images_dropped") or {}
    if dropped:
        n = sum(dropped.values())
        kinds = " · ".join(f"{k} {v}" for k, v in sorted(dropped.items()))
        why = " · ".join(rw.get("why") or [])
        print(f"   그림 {n}개를 읽지 못해 건너뜀({kinds}" + (f" — {why}" if why else "")
              + ") — 이미지 요약에서 빠진다")


def image_screen():
    """그림 요약의 **예고** 줄 — 부르기 전에(B88 ①). 보존된 요약은 호출 0이다."""
    def notice(info):
        print(f"   그림 요약 — 새 {info['새']}장 → LLM ≤ {info['새']}회"
              f"(보존 재사용 {info['재사용']})")
    return notice


def rule_screen():
    """계층 규칙 선언의 **예고** 줄 — 부르기 전에 낸다(B87 ② · B69 ②의 결)."""
    def notice(info):
        if info.get("단계") == "예고":
            _screen.say(f"   계층 규칙 — 고정 규칙으로 안 선 시트 {info['대상']}장 → "
                        f"LLM ≤ {info['호출_상한']}회(재사용 {info['재사용']})", "head")
    return notice


def print_split_notes(report):
    """분할 끝 줄 둘(B87) — 규칙 선언의 결과 · 글자 상한. 해당이 없으면 줄도 없다."""
    sr = (report or {}).get("struct_rule") or {}
    if sr.get("주입") and sr.get("대상"):
        tail = f" · 선언 버림 {len(sr['버림'])}" if sr.get("버림") else ""
        _screen.say(f"   계층 규칙 — 선언 적용 {sr['적용']}시트 · 여전히 통째 {sr['통째']}시트"
                    f" (호출 {sr['호출']} · 재사용 {sr['재사용']}{tail})", "head")
    cap = ((report or {}).get("split") or {}).get("글자_상한") or {}
    if cap:
        print(f"   글자 상한 초과 {cap['초과_청크']}청크 → 행 경계로 {cap['조각']}조각"
              f" (상한 {cap['상한']:,}자"
              + (f" · 혼자 넘는 행 {cap['혼자_넘는_행']}" if cap.get("혼자_넘는_행") else "")
              + ")")


def _coord_diag(info):
    """**좌표 진단**(B99 ⑧) — 목록 밖 표기 상위 표 + 다음 줄(골격 파일 · `ALIASES` · `bootstrap`). LLM 전."""
    from core import paths
    t = _screen.Table([("목록 밖 표기", 40, False), ("행 수", 6, True)], flex=0)
    for ref, n in info["목록밖_상위"]:
        t.row([ref, n], [None, "aux"])
    t.end()
    lay = coord_layer()
    print(f"   ▶ 다음 줄 — 같은 공정이면 {paths.show(paths.layers(lay, 'skeleton.json'))}의 "
          f"`ALIASES`에 표기를 더하고 python run.py bootstrap (fresh 없이) → 같은 인입"
          + (f" · 목록 밖 {info['표기_종수']:,}종 중 상위 {len(info['목록밖_상위'])}" if
             info["표기_종수"] > len(info["목록밖_상위"]) else ""))


def coord_screen():
    """좌표 태깅의 예고·진행·끝 줄 — `(notice, progress)` (B69 ② · B22의 정신).

    **비용은 화면에 오른다.** 예고는 호출 **전에** 무LLM으로 센 숫자다: 사람이
    「무한」으로 읽고 끄는 일이 없게 몇 번 부를지를 먼저 말한다(사내 실측 아홉째).
    진행은 **표기 단위**이고, 끝 줄은 채택·목록 밖을 센다.
    """
    def notice(info):
        if info.get("단계") == "행":
            return row(info)
        if info.get("단계") == "예고" and info.get("목록밖_상위"):
            _coord_diag(info)
        if info.get("단계") == "예고":
            head = (f"   좌표 태깅 — 조각 {info['조각']:,} · "
                    f"정확 일치 {info['정확_일치']:,} · "
                    f"목록 밖 표기 {info['표기_종수']:,}종(행 {info['미스_행']:,})"
                    # 좌표 학습 적중(B101 ②) — 사람 보증 다음 · LLM 앞 · LLM 0
                    + (f" · 학습 적중 {info['학습_적중']:,}종(행 {info.get('학습_적중_행', 0):,} · LLM 0)"
                       if info.get("학습_적중") else ""))
            if not info.get("LLM"):
                _screen.say(f"{head} → LLM 0회 — 정확 일치만", "head")
                return
            _screen.say(f"{head} → LLM 최대 {info['묻는_종수']:,}회"
                        + (f" (상한 {info['상한']:,})" if info.get("상한") is not None else ""),
                        "head")
            if info.get("상한") == 0:
                # **사람이 끈 것과 상한에 걸린 것은 다른 일이다** — 끈 자리에
                # 「초과」를 찍으면 자기가 준 값이 사고처럼 읽힌다.
                print(f"   좌표 보조 끔(--coord-llm off) — 목록 밖 "
                      f"{info['표기_종수']:,}종은 그대로(orphan_anchor)")
                return
            if info["묻는_종수"] < info["표기_종수"]:
                # **막지 않는다 — 말한다**(B61 계약: 원인 + 그대로 칠 수 있는 다음 줄).
                print(f"   상한 초과 — {info['표기_종수']:,}종 중 "
                      f"{info['묻는_종수']:,}종만 묻는다 · 나머지 "
                      f"{info['표기_종수'] - info['묻는_종수']:,}종은 목록 밖 "
                      f"그대로(orphan_anchor)")
                print(f"     다음: --coord-llm {max(info['표기_종수'], 1)} "
                      f"또는 사전 alias 등록")
            return
        if info.get("호출"):
            _screen.close()
            print(f"   좌표 태깅 끝 — 호출 {info['호출']:,} · 채택 {info['채택']:,} · "
                  f"목록 밖 {info['목록밖']:,}(orphan_anchor 후보 · `show learned`의 새 공정 후보)"
                  + (f" · 학습 새로 {info['학습_새로']:,}" if info.get("학습_새로") else ""))

    box = {"t": None}

    def row(info):
        # **표기마다 한 행 — 이어지는 표**(B98 ⑥) · 표기 하나가 LLM 호출 하나다
        if box["t"] is None:
            box["t"] = _screen.Table([("번호", 9, True), ("표기", 40, False),
                                      ("행 수", 5, True), ("결과", 24, False)], flex=1)
        box["t"].row([f"{info['i']}/{info['총']}", info["표기"], info["행_수"],
                      info["결과"] or "목록 밖(orphan_anchor 후보)"],
                     ["prog", None, "aux", "match" if info["결과"] else "aux"])

    def progress(done, total, adopted):
        # 보폭 진행 줄 — 표가 이어지는 중이면 그 표의 구분 행이다(B69 ② · B98 ⑥)
        stride = max(1, total // 10)
        if done == 1 or done == total or done % stride == 0:
            _screen.inline(f"[좌표 태깅] 표기 {done:,}/{total:,} · 채택 {adopted:,} · "
                           f"목록 밖 {done - adopted:,}", "prog")
        if done == total and box["t"] is not None:
            box["t"].end()
            box["t"] = None

    return notice, progress


def run_parse(adapter_path, doc_id, doc, out=None, coord_cap=COORD_CAP,
              sheet_roles=None, no_images=False):
    """운영 파싱 1회 — **출력 경로는 인자이고, 운영 산출 자리는 `parsed/{doc_id}.json`이다**
    (문서 7 §7.1 진입점 계약 · §7.8). **파일 존재 = 파싱 완료**이므로 자리가 정해져
    있어야 플랫폼이 그 상태를 파일로 판정할 수 있다.

    `parse run`과 일괄 투입(`ingest-file`·`ingest-dir`)이 **같은 함수**를 부른다 —
    두 벌이면 주입(이미지 요약·좌표)이 한쪽에서 빠지는 날이 온다.
    돌려주는 것은 `(ParseResult, 쓴 경로 또는 None)`이다.
    """
    out = out or str(PARSED_DIR / f"{doc_id}.json")
    # LLM 3지점(④·⑦·⑨)의 실호출 경로는 **주입**한다 — 파서는 core를 import하지
    # 않는다(A1). mock이면 None이 오고 파서가 §7.1 대체를 쓴다.
    _notice, _progress = coord_screen()
    _rule_notice = rule_screen()
    # **좌표 층도 주입이다**(B85 ②) — 파서는 어느 층이 좌표 층인지 모른다.
    # 묻는 자리는 하나(`coord_layer()` = `Process`를 선언한 층)이고, 폴더 이름이
    # 무엇이든 그 답을 쓴다.
    # **누적 줄**(B97 ②) — 계층 규칙 · 그림 요약 · 좌표 태깅이 이 안에서 LLM을 부른다
    with _screen.ticker("파싱(계층 규칙·그림 요약·좌표)"):
        res = pipeline.parse(load_adapter(adapter_path), doc_id, doc, **injections(),
                             layer=coord_layer(),
                             coord_notice=_notice, coord_cap=coord_cap,
                             progress=_progress, sheet_roles=sheet_roles,
                             rule_notice=_rule_notice, no_images=no_images,
                             image_notice=image_screen())
    print_read_warnings(res.report)
    print_split_notes(res.report)
    _skip = res.report.get("images")
    if _skip and res.ok:
        # **명시적으로 뺀 그림은 기록에 남는다**(B88 ①) — 계약 JSON의 context(임의 dict)에
        # 실어 인입 기록(doc_registry)과 `show doc`이 읽는다. 조용한 건너뜀은 없다.
        res.envelope.setdefault("context", {})["images_skipped"] = {
            "n": _skip["요약_안_함"], "why": _skip["사유"]}
        print(f"   그림 {_skip['요약_안_함']}장 요약 안 함({_skip['사유']})")
    # **그때 쓴 손잡이 값과 출처**(B91 ⑤) — 손잡이 파일이 있을 때만 싣는다(없으면 기록 모양
    # 불변). 같은 문서가 전과 다르게 잘린 이유를 사내가 인입 기록에서 추적한다.
    from core.state import knobs as _knobs
    _kr = _knobs.record(_knobs.PARSE_RECORD)
    if _kr and res.ok:
        res.envelope.setdefault("context", {})["knobs"] = _kr
    written = None
    if res.ok and out:
        paths.ensure(Path(out))
        Path(out).write_text(json.dumps(res.envelope, ensure_ascii=False, indent=2)
                             + "\n", encoding="utf-8")
        written = out
    return res, written


def cmd_run(args):
    """운영 파싱 1회 — `doc_id`는 **선택**이다(§7.1 · B51).

    **파생 규칙을 여기서 다시 쓰지 않는다** — `ingest-file`이 쓰는 함수를 그대로
    부른다. 규칙이 둘이면 같은 문서가 명령에 따라 다른 `doc_id`를 받고, 그 순간
    재인입이 개정이 아니라 신규가 된다(D-110).

    구형(`<어댑터> <doc_id> <문서>`)도 받는다. 가르는 기준은 **둘째 인자가 존재하는
    파일인가**다 — 파일이면 새 형이고 그 자리가 문서다.
    """
    from cli.ingest import doc_id_of          # 파생은 한 곳이다 (복제 금지)
    args = list(args)
    given = None
    if "--doc-id" in args:
        i = args.index("--doc-id")
        given = args[i + 1] if i + 1 < len(args) else None
        del args[i:i + 2]
    adapter_path = args[0]
    if len(args) > 1 and Path(args[1]).is_file():        # 새 형 — 둘째가 문서다
        doc, rest = args[1], args[2:]
        doc_id, how = (given, "지정") if given else (doc_id_of(doc), "파일명 파생")
    else:                                                # 구형 4인자
        doc_id, doc, rest = (given or args[1]), args[2], args[3:]
        how = "지정" if given else "인자"
    print(f"[parse] doc_id = {doc_id} ({how})")
    rest, cap = coord_cap_of(rest)
    no_img = "--no-images" in rest                # 그림 없이 — 명시적으로만 (B88 ①)
    rest = [a for a in rest if a != "--no-images"]
    # **시트 역할은 같은 문법·같은 기록이다**(B83 ③) — `ingest-file`과 두 벌이면
    # 같은 문서가 명령에 따라 다른 시트를 읽는다.
    from cli import sheet_gate as SG             # 관문 한 벌 (B86 ⑤)
    rest, _spec = SG.flag(rest)
    _roles = SG.by_flag(doc, doc_id, _spec) if _spec else None
    res, out = run_parse(adapter_path, doc_id, doc, rest[0] if rest else None,
                         coord_cap=cap, sheet_roles=_roles, no_images=no_img)
    print(f"[parse] {res}")
    for f in res.failures:
        print(f"   [{f['kind']}] {f['reason']}")
        if f["detail"]:
            print(f"      {json.dumps(f['detail'], ensure_ascii=False)[:300]}")
    if res.report:
        print(f"   report: {json.dumps(res.report, ensure_ascii=False)}")
    if out:
        print(f"   → {out}")
    from cli import _screen
    print(f"   {_screen.usage_line()}")                     # 파싱 안 LLM(좌표·그림·규칙) (B96 ③)
    return 0 if res.ok else 1


def cmd_head(args):
    """등록 세션에 공급하는 관찰 재료 — **reader는 두 모드에서 같은 코드다**(§3 규약 4)."""
    n = int(args[1]) if len(args) > 1 else 12
    print(json.dumps(reader.head(reader.read(args[0]), n), ensure_ascii=False,
                     indent=2)[:4000])


def cmd_build(args):
    """구축 모드 3단 — **생성 → 검수 → 확정**의 배선 (파서_명세 §6).

    ①생성: 표본의 관찰 재료(reader head)를 모아 어댑터 초안의 입력 패키지를 만든다.
      USE_MOCK에서 초안 자체는 fixture가 대신한다(D-10·D-26) — 여기서는 인자로 받는다.
    ②검수: 실행 하네스에 해당하는 **기계 관문**을 통과시킨다 — preflight + 파싱 +
      계약 self-check를 표본 전부에 대해 돌리고 결과를 뷰 데이터로 남긴다.
    ③확정: 승인 기록을 남긴다. **registry 등재는 P3의 몫**이라 여기서는 하지 않는다.

    표본 1부면 경고를 뷰 데이터에 싣는다(D-22 확장 문구) — 변형을 관찰하지 못했다는
    사실 자체가 검수자의 판단 재료다.
    """
    adapter_path, doc_type, samples = args[0], args[1], args[2:]
    mod = load_adapter(adapter_path)
    outdir = review_dir(doc_type)

    view = {"doc_type": doc_type, "adapter": str(adapter_path),
            "adapter_version": mod.ADAPTER.get("adapter_version"),
            "payload_kind": mod.ADAPTER.get("payload_kind"),
            "samples": [], "warnings": []}

    if len(samples) < 2:
        view["warnings"].append(
            "표본 1부 · 변형 미관찰 — **선언된 관계는 근거 1건일 수 있음** (D-22). "
            "1부 등록의 선언 edges는 특별 확인 대상이다")

    print(f"■ 구축 모드 — {doc_type} · 표본 {len(samples)}부")
    print("\n① 생성 — 관찰 재료 수집 (reader head · 두 모드 공용 코어)")
    pkg = {"doc_type": doc_type, "samples": []}
    for s in samples:
        raw = reader.read(s)
        pkg["samples"].append({"path": s, "head": reader.head(raw)})
        print(f"   {Path(s).name}: {raw['format']} · "
              f"{len(raw.get('sheets') or raw.get('slides') or [])} 단위")
    (outdir / "input_package.json").write_text(
        json.dumps(pkg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("\n② 검수 — 기계 관문 (preflight → 파싱 → 계약 self-check)")
    allok = True
    for i, s in enumerate(samples, 1):
        raw = reader.read(s)
        pf_ok, pf_detail = preflight.check(mod, raw)
        res = pipeline.parse(mod, f"{doc_type.upper()}{i:02d}", s,
                             layer=coord_layer(),
                             **{**injections(), "infer_rules": None})   # 구축은 파악만 (B87 ②)
        allok &= bool(pf_ok and res.ok)
        print(f"   {Path(s).name}: preflight {'OK' if pf_ok else 'MISMATCH'} · "
              f"파싱 {'OK' if res.ok else 'FAIL'} · 조각 {res.report.get('pieces', 0)}")
        for f in res.failures:
            print(f"      [{f['kind']}] {f['reason']}")
        view["samples"].append({
            "path": s, "preflight": pf_ok, "preflight_detail": pf_detail,
            "parsed": res.ok, "failures": res.failures, "report": res.report,
            # 검수 뷰 3층 표시의 데이터 — **렌더는 P2 몫**이다(경계)
            "envelope_head": ({k: v for k, v in (res.envelope or {}).items()
                               if k not in ("records", "chunks")} if res.ok else None),
            "pieces_head": ((res.envelope.get("records")
                             or res.envelope.get("chunks"))[:3] if res.ok else []),
        })
    (outdir / "view.json").write_text(
        json.dumps(view, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"   → {outdir / 'view.json'}  (검수 뷰 **데이터** — HTML 렌더는 P2)")
    for w in view["warnings"]:
        print(f"   ⚠ {w}")

    print("\n③ 확정 — 승인 기록 (registry 등재는 P3의 몫이다)")
    approval = {"doc_type": doc_type, "adapter_version": mod.ADAPTER.get("adapter_version"),
                "machine_gate": "PASS" if allok else "FAIL",
                "approved_by": None, "approved_at": None,
                "instructions": [],
                "note": "승인자·시점은 사람이 채운다. 기계 관문 통과가 승인의 전제다"}
    (outdir / "approval.json").write_text(
        json.dumps(approval, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"   → {outdir / 'approval.json'}  (기계 관문 {approval['machine_gate']})")
    return 0 if allok else 1


def main(argv):
    if not argv:
        raise SystemExit(__doc__)                                         # [사용법]
    cmd, rest = argv[0], list(argv[1:])
    if cmd == "run":                       # 운영 파싱 — mock 관문 대상(B48)
        rest = require_live_or_allow(rest, command="parse run")
    return {"run": cmd_run, "head": cmd_head, "build": cmd_build}[cmd](rest) or 0


if __name__ == "__main__":
    # **공통 진입 함수 하나**(B99 ③) — 로그 설정 · 화면 전체를 명령 로그로 · 실행 머리/끝 줄
    from cli import _entry
    sys.exit(_entry.main_module("cli.parse", main))
