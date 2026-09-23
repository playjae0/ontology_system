# -*- coding: utf-8 -*-
"""칸 1.6 — **검수 뷰**: 리허설 · 뷰 데이터 산출 · `register review`·`status` 화면."""

from __future__ import annotations

from core.state.bootstrap import coord_layer
from cli.parse import injections
from cli.prompt import (  # noqa: F401
    KIT_NOTE, VOCAB_SECTIONS, _dir, _strip_kit_notes, _dump_prompt, _strip_module_doc,
    _reference_adapter, generate_template, _render_template, _vocab_excerpt, _sent_size)
from core import paths
from core.llm import check, gateway, points
from core.state import fixtures, log, registry, store
from kit.render_review import render
from parser import form
from parser import pipeline, preflight, profile, reader, tagger
from pathlib import Path
import json
import sys
from cli.register import draft as draft_mod
from cli.register import gate
from cli.register import interview as ivlog
from cli.register import ledger
from cli.register import EXCERPT, REVIEW, ROOT, SOLO_WARNING, _load, _save_state, _state


def _form_of_sample(sample):
    """표본 하나의 형태 판정 — 격자 포맷이 아니면 `None`.

    **판정기는 한 자리다**(`parser/form.py`) — 여기서 다시 세면 등록 화면과 인입
    기록이 다른 답을 낼 수 있고, 그때 어느 쪽이 근거인지 아무도 모른다.
    """
    if Path(sample).suffix.lower() not in reader.GRID_EXT:
        return None
    try:
        j = form.judge(reader.read(str(sample)))
    except Exception as e:                       # 판정 실패가 검수를 막지 않는다
        return {"signals": {}, "votes": {}, "verdict": None, "auto": False,
                "why": f"형태 판정 불가 — {type(e).__name__}: {e}"}
    return {k: j[k] for k in ("signals", "votes", "verdict", "auto", "why")}


def _build_view_anomalies(st, results, harness_ok, harness_out, schema, mod):
    """뷰의 **이상 신호**와 리허설 요약 — `(anomalies, reh)`.

    `build_view`에서 단계로 떼어냈다(B78 2c). 사람이 보는 「무엇이 이상한가」는
    한 자리에서 모인다 — 흩어지면 화면마다 다른 기준이 선다.
    """
    anomalies = []
    # **부분 리허설은 숨기지 않는다** — 이 화면이 승인 근거다. 앞 200행만 보고
    # 승인했는데 그 사실이 화면에 없으면, 승인자는 전량을 봤다고 믿는다.
    reh = {}
    for r in results:
        d = r.report.get("rehearsal") or {}
        if d.get("truncated"):
            reh = d
            anomalies.append({
                "kind": "warning",
                "message": (f"부분 리허설 — 전 {d['full_rows']:,}행 중 앞 "
                            f"{d['max_rows']:,}행만 파싱했다. 뒤 구간의 변형은 "
                            f"관찰되지 않았다"),
                "where": r.doc_id,
                "detail": {"full_rows": d["full_rows"], "rehearsed_rows": d["max_rows"],
                           "note": "전량은 `--rows all`"}})
            break

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
    # **셋을 갈라 낸다**(B49) — 판정된 제외는 질문이 아니고, 대장에 없는 열은 결함이다.
    excluded, undecided, orphan = ledger.unmappable_of(schema, mod)
    for u in undecided:
        anomalies.append({"kind": "question",
                          "message": f"'{u['field']}' 열은 role 5종 어디에 배정합니까 — "
                                     f"생성이 판단하지 못했다: "
                                     f"{u.get('reason') or '사유 없음'}",
                          "where": st["doc_type"]})
    for u in orphan:
        anomalies.append({"kind": "failure",
                          "message": f"'{u['field']}' 열이 스키마 대장에 없다 — "
                                     f"생성이 빠뜨렸거나 문서 양식이 바뀌었다",
                          "where": st["doc_type"]})

    # **형태 판정을 화면에 싣는다**(B58 ⑤ · 문서 1 C37) — 격자 포맷 표본만.
    # 사람에게 올라온 문서는 **이상 신호로도** 뜬다: 「이상 신호는 전량 필수
    return anomalies, reh, excluded


def build_view(st, results, harness_ok, harness_out, rehearsal=None):
    """뷰 데이터 산출 — **D-79 스키마가 계약**이고 여기가 산출자다.

    렌더러는 아무것도 계산하지 않으므로 **채움율·이상 신호 판정을 여기서 다 채운다.**
    """
    schema = json.loads((draft_mod._at(st["schema"])).read_text(encoding="utf-8"))
    mod = _load(draft_mod._at(st["adapter"]), f"reg_{st['doc_type']}")
    kind = mod.ADAPTER["payload_kind"]

    pieces = [p for r in results if r.ok
              for p in (r.envelope.get("records") or r.envelope.get("chunks"))]
    keys = sorted({k for p in pieces for k in p})
    fill = {k: round(sum(1 for p in pieces if p.get(k) not in (None, "")) / len(pieces), 3)
            for k in keys} if pieces else {}

    anomalies, reh, excluded = _build_view_anomalies(
        st, results, harness_ok, harness_out, schema, mod)
    # 표시」(§6.6-1)라 요약 표에만 두면 접힌 화면에서 사라진다.
    forms = []
    for smp in st["samples"]:
        j = _form_of_sample(smp)
        if j is None:
            continue
        forms.append({"doc": Path(smp).name, **j})
        if not j["auto"]:
            anomalies.append({
                "kind": "question",
                "message": (f"'{Path(smp).name}'의 형태 판정이 자동으로 서지 않는다 — "
                            f"table로 읽을지 prose로 읽을지 사람이 정한다: {j['why']}"),
                "where": Path(smp).name,
                "detail": {"signals": j["signals"], "votes": j["votes"],
                           "note": "신호값 다섯이 판단 재료다 — 문턱은 parser/form.py"}})
        elif j["verdict"] != kind:
            anomalies.append({
                "kind": "warning",
                "message": (f"'{Path(smp).name}'의 형태 판정({j['verdict']})이 "
                            f"이 어댑터의 payload_kind({kind})와 어긋난다 — "
                            f"지정대로 진행한다([정정] 48 ②)"),
                "where": Path(smp).name,
                "detail": {"signals": j["signals"], "votes": j["votes"]}})

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
                            "rehearsal": reh,
                            # **분할 크기 분포**(B45) — 값은 여기서 채우고 렌더러는
                            # 그리기만 한다(§6.6-3). **`summary` 안이다**: 구획 1은
                            # `summary·anomalies·normal` 3층으로 닫혀 있어(D-79)
                            # 네 번째 키를 만들면 스키마 계약이 깨진다.
                            # 두 경로(지도·어댑터) 모두 같은 자리에 실리고, 지도
                            # 경로면 고른 레벨과 분포가 `레벨_선택`에 함께 온다.
                            "split": [{"doc_id": r.doc_id,
                                       **(r.report.get("split") or {})}
                                      for r in results if r.report.get("split")],
                            # **형태 판정**(B58 ⑤) — `split`과 같은 자리다. 구획 1은
                            # `summary·anomalies·normal` 3층으로 닫혀 있어(D-79)
                            # 네 번째 키를 만들면 스키마 계약이 깨진다.
                            "form": forms,
                            "failures": sum(1 for a in anomalies if a["kind"] == "failure"),
                            "warnings": sum(1 for a in anomalies if a["kind"] == "warning"),
                            "fill_rate": fill},
                "anomalies": anomalies,
                # **제외 목록은 정상 구획이다** — 판정이 끝난 열이라 이상 신호가
                # 아니다. 다만 화면에서 사라지면 안 된다(무엇을 뺐는지가 승인 재료다).
                "normal": {"excluded": excluded,
                           "excerpt": pieces[:EXCERPT], "all": pieces,
                           "columns": keys if kind == "table" else [],
                           "tree": tree if kind == "prose" else []},
            },
            # **②구획은 payload_kind가 가른다**(문서 6 §6.6 · B51) — table은 role
            # 배정표, prose는 추출 리허설이 **그 자리에** 선다. 화면의 목적이 같다:
            # 「무엇이 개체·값이 되는가」를 승인 **전에** 본다.
            # **구획 수는 셋 그대로다**(D-79) — 자리를 더하지 않고 갈아 끼운다.
            **({"extract_rehearsal": rehearsal or {"source": "none"}}
               if kind == "prose" else
               {"role_table": ledger.role_table(schema, mod, st,
                                         ledger._profiles(st["doc_type"]))}),
            "adapter_summary": {
                "expects": mod.ADAPTER.get("expects") or {},
                "adapter_version": mod.ADAPTER.get("adapter_version"),
                "source": (draft_mod._at(st["adapter"])).read_text(encoding="utf-8"),
            },
        },
    }


REHEARSAL_ROWS = 200        # 부분 리허설 기본값 — `--rows all`이면 전량


def _gateway_ready():
    """리허설 파싱 **전에** 게이트웨이 왕복 1회. 실패면 그 자리에서 멈춘다(2B ⑥-1).

    이것이 없으면 사내에서 무슨 일이 나나: 리허설 파싱은 좌표 미스 행마다 실호출을
    한다 — 게이트웨이가 안 닿으면 **타임아웃 60초 × 재시도 × 미스 행 수**를 말없이
    기다린다. 사용자는 «멈췄다»고 읽고, 실제로 몇 시간을 기다렸다(실측).
    **판정은 `core/llm/gateway.py::probe()`가 한다** — llm-check가 쓰는 그 함수다.
    """
    if gateway.use_mock():
        return True
    print("   게이트웨이 확인 중… (리허설 전 왕복 1회)")
    stages = check.probe()
    bad = [s for s in stages if s["ok"] is False and s["fatal"]]
    if not bad:
        ok = [s for s in stages if s["ok"]]
        print(f"   게이트웨이 OK — {len(ok)}단계 통과")
        return True
    s = bad[0]
    print(f"   ✗ 게이트웨이 {s['id']} {s['label']} 실패")
    for ln in str(s["detail"]).split("\n"):
        if ln.strip():
            print(f"     {ln}")
    raise SystemExit("[뷰 확인] 게이트웨이가 준비되지 않았다 — "                          # [상태]
                     "`python run.py llm-check`로 단계별 원인을 본다. "
                     "USE_MOCK=1로 돌리면 LLM 없이 리허설만 볼 수 있다")


def _coord_misses(results, layer):
    """좌표가 **닫힌 목록과 정확히 일치하지 않는** 조각을 센다 — LLM을 부르지 않는다.

    **몇천 회 호출은 사람이 모르고 시작하면 안 된다** — 그래서 먼저 세고 물어본다.
    호출 수는 이 목록의 **길이가 아니라 종수**다(B69 ① — tagger가 표기마다 한 번
    묻는다). 목록을 그대로 돌려주는 것은 행 수와 종수를 **둘 다** 화면이 말해야
    하기 때문이다: 「3,000행이 12종이다」가 사람이 켤지 정하는 재료다.
    """
    idx = tagger.surfaces(tagger.closed_list(layer))
    miss = []
    for r in results:
        env = r.envelope or {}
        for p in (env.get("records") or env.get("chunks") or []):
            ref = p.get("process_ref")
            if ref and ref not in idx:
                miss.append(ref)
    return miss


def _ask_llm_coord(misses, assume=None):
    """LLM 좌표 보조를 켤지 **묻는다.** 기본은 끈다.

    미스를 그대로 두는 것은 오류가 아니다 — 인입에서 `orphan_anchor` 큐로 가는
    정상 경로가 있고(문서 4 §4.4), 사람이 자기 리듬으로 처리한다. 반면 켜면
    **표기 종수만큼 실호출**이다(B69 ① — 같은 표기가 여러 행에 있어도 한 번이다).
    켤지 묻는 자리이므로 **수가 맞아야 한다**: 구판은 행 수를 호출 수라고 말했고,
    그 수는 실제보다 훨씬 컸다.
    """
    n, kinds = len(misses), sorted(set(misses))
    if n == 0:
        return False
    sample = ", ".join(kinds[:5])
    print(f"   좌표 미스 {n:,}행 · 표기 {len(kinds):,}종 "
          f"(예: {sample}{' …' if len(kinds) > 5 else ''})")
    if assume is not None:
        print(f"   → LLM 보조 {'켬' if assume else '끔'} (인자로 지정됨)")
        return assume
    if gateway.use_mock():
        return False
    try:
        ans = input(f"   LLM 보조를 켜면 최대 {len(kinds):,}회 호출한다(표기 종수). "
                    f"켤까? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        ans = ""                       # 대화형이 아니면 **끄고 진행**한다
    on = ans in ("y", "yes")
    print(f"   → LLM 보조 {'켬' if on else '끔 (미스는 인입에서 orphan_anchor로 간다)'}")
    return on


def _progress(done, total, adopted, *, label=""):
    """진행 한 줄 — **주기 갱신**. 매 번 찍으면 그것이 잡음이 된다.

    **단위는 표기다**(B69 ① — 행이 아니다): 리허설에서 도는 것은 좌표 태깅의
    표기 루프이고, 그 루프가 곧 LLM 호출이다. 부르지 않으면(정확 일치만) 진행도
    없다 — 결정적 구간은 빠르고, 조용한 것이 맞다.

    보폭은 10회 안팎으로 갱신되게 잡는다. `\r` 덮어쓰기는 터미널일 때만 —
    파이프로 받으면 매 줄이 남는다.
    """
    stride = max(1, total // 10)
    if not (done == 1 or done == total or done % stride == 0):
        return
    tty = sys.stdout.isatty()
    print(f"   좌표 태깅 {label} · 표기 {done:,}/{total:,} · 채택 {adopted:,}",
          end="\r" if (tty and done < total) else "\n", flush=True)


def _extract_rehearsal(st, results, samples, want, truncated):
    """**prose ②구획 — 층 어휘가 이 문서에 적용된 결과** (문서 6 §6.6 · B51).

    table은 role 배정표(「이 열이 attribute가 된다」)를 보고 승인한다. prose는 청크
    분할만 보고 승인해 왔다 — **층 어휘가 이 문서에 어떻게 적용되는지를 한 번도 안
    본 채** 확정되고, 그 결과를 처음 보는 시점이 운영 인입 뒤 `show extract`였다.

    **리허설은 운영과 같은 함수·같은 파일이다** — `cli.extract.run()`을 부르고 그
    체크포인트를 그대로 싣는다. 그래서 `doc_id`도 **운영의 것**(파일명 파생)을 쓴다:
    리허설 id를 따로 쓰면 확정 뒤 운영 인입이 그 체크포인트를 못 찾아 같은 문서를
    다시 뽑는다 — LLM 호출이 두 배가 되고, 두 산출이 다를 수 있다.

    **부분 리허설이면 체크포인트를 남기지 않는다** — 앞 N행만 본 추출을 운영이
    재사용하면 뒷 구간이 영영 안 뽑힌다.
    """
    from cli.extract import run as extract_run
    from cli.ingest import doc_id_of
    from core.build import extract as EX
    if not want:
        return {"source": "none", "note": "추출 리허설 없음 — 끄고 진행했다"}
    made, ids = [], []
    for r, s in zip(results, samples):
        if not r.ok:
            continue
        env = dict(r.envelope)
        env["doc_id"] = doc_id_of(s)          # **운영의 doc_id** — 재사용의 조건이다
        ids.append(env["doc_id"])
        p = _dir(st["doc_type"]) / f"_rehearsal_{env['doc_id']}.json"
        p.write_text(json.dumps(env, ensure_ascii=False), encoding="utf-8")
        made.append(p)
    extract_run([str(p) for p in made], layer=st["layer"])
    for p in made:
        p.unlink(missing_ok=True)
    cps = [json.loads(EX.checkpoint_path(i).read_text(encoding="utf-8"))
           for i in ids if EX.has_checkpoint(i)]
    if truncated:
        for i in ids:
            EX.invalidate(i)                  # 부분 리허설분은 운영이 재사용하면 안 된다
    if not cps:
        return {"source": "none", "note": "추출 산출이 없다 (표본 파싱 실패 또는 청크 0)"}
    # **본문은 산출자가 채운다** — 체크포인트는 후보만 담고(§4.2) 렌더러는 계산하지
    # 않는다(D-79). 청크 저장소가 그 문서의 본문·구획을 갖고 있다.
    _ch = store.read(store.CHUNKS, {"chunks": {}})["chunks"]
    by_chunk, cats = [], {}
    for cp in cps:
        for c in cp.get("candidates") or []:
            for e in c.get("entities") or []:
                cats[e.get("category")] = cats.get(e.get("category"), 0) + 1
            src = _ch.get(c.get("chunk_id")) or {}
            by_chunk.append({"chunk_id": c.get("chunk_id"),
                             "section": src.get("section") or "",
                             "excerpt": (src.get("text") or "")[:60],
                             "entities": c.get("entities") or [],
                             "relations": c.get("relations") or [],
                             "attach": c.get("attach") or []})
    tot = {"chunks": len(by_chunk),
           "entities": sum(len(c["entities"]) for c in by_chunk),
           "relations": sum(len(c["relations"]) for c in by_chunk),
           "attach": sum(1 for c in by_chunk for a in c["attach"]
                         if a.get("attach_to")),
           "unresolved": sum(1 for c in by_chunk for a in c["attach"]
                             if not a.get("attach_to"))}
    return {"source": "mock" if gateway.use_mock() else "live",
            "prompt_version": cps[0].get("prompt_version"),
            "config_version": cps[0].get("config_version"),
            "kept": not truncated,
            "note": ("부분 리허설이라 체크포인트를 남기지 않았다 — 운영이 다시 뽑는다"
                     if truncated else None),
            "totals": tot, "by_chunk": by_chunk, "category_counts": cats}


def _cmd_review_instruct(doc_type, st, instruct):
    """② -a **재생성 루프 1회** — 지시가 오면 초안을 다시 받고 관문을 다시 지난다.

    `cmd_review`에서 단계로 떼어냈다(B78 2c). 관문이 막으면 **1을 돌려준다** —
    호출부는 그대로 돌려주고 뷰를 만들지 않는다(막힌 산출로 뷰를 덮지 않는다).
    """
    if instruct and st.get("use_basic"):
        # **고정 어댑터는 재생성하지 않는다**(B65 ④) — 여기서 막지 않으면 `draft_mod.draft`가
        # LLM으로 가고, 사람은 「지시를 줬다」고 믿는데 산출이 통째로 바뀐다.
        draft_mod.refuse_regenerate(doc_type, st, "뷰 확인")
    st["revision"] += 1
    st.setdefault("instructions", []).append(
        {"n": st["revision"], "instruction": instruct, "at": store._now(),
         "by": "사람(검수 지시)"})
    # **지시는 확정 사항을 갱신한다**(B60 ②) — draft가 패키지를 읽기 **전에**.
    # 지시와 결정이 따로 살면 이 재생성이 옛 결정을 다시 쓴다.
    _hit = ivlog.apply_instruction_to_decisions(doc_type, instruct, st["revision"])
    if _hit is not None:
        print(f"   확정 사항 갱신 — {'항목 ' + str(_hit) + '건 교체' if _hit else '새 항목 추가'}"
              f" (사람 지시 rev {st['revision']})")
    # **지시가 열을 이름으로 부르면 대장도 갱신한다**(B67 ②) — 못 부르면
    # 건드리지 않고 이력에만 남는다(추측으로 행을 고치지 않는다).
    _lh = ledger.apply_to_ledger(doc_type, instruct, f"instruct rev {st['revision']}")
    if _lh:
        print(f"   열 판정 대장 갱신 — {_lh}열 (instruct rev {st['revision']})")
    ad, sc = draft_mod.draft(doc_type, st["revision"], instruction=instruct,
                   history=st.get("instructions"))
    if ad is None:
        print(f"   ⚠ 재생성 대안본 부재 — 초안을 유지한다 "
              f"(USE_MOCK: fixture '{doc_type}_rev{st['revision']}' 없음)")
    else:
        st["adapter"], st["schema"] = (str(draft_mod._rel(ad)), str(draft_mod._rel(sc)))
        print(f"   재생성 {st['revision']}회째 → {draft_mod._rel(ad)}")
        # **지시는 사람 것이지만 산출은 LLM 것이다**([정정] 40 · M9). 관문을
        # 안 지난 산출이 확정되면 「통과분만 확정」(B50)이 검수 지시 한 번으로
        # 뚫린다 — 규약 10을 어긴 어댑터가 `--instruct` 한 줄로 등록부에 든다.
        # **생성 단계와 같은 함수·같은 해소 절차**(자동 1회 → 문답 → [y/N])다.
        _pkg_path = REVIEW / doc_type / "input_package.json"
        _pkg = (json.loads(_pkg_path.read_text(encoding="utf-8"))
                if _pkg_path.exists() else None)
        st["machine_gate"] = gate.machine_gate(doc_type, st, st["samples"], _pkg)
        _save_state(doc_type, st)
        if st["machine_gate"] != "PASS":
            print(f"   기계 관문 FAIL — **뷰를 만들지 않았다.** 산출은 "
                  f"{(REVIEW / doc_type).relative_to(ROOT)}에 남겼다\n")
            gate.gate_block(doc_type, st)
            return 1


def _cmd_review_rehearsal(doc_type, st, results, samples, mod, extract):
    """② -b **추출 리허설** — prose일 때만, 사람이 켜면 돈다. 돌려주는 것은 리허설 요약.

    `cmd_review`에서 단계로 떼어냈다(B78 2c).
    """
    kind = mod.ADAPTER.get("payload_kind")
    _trunc = any((r.report.get("rehearsal") or {}).get("truncated") for r in results)
    rehearsal = None
    if kind == "prose" and st.get("machine_gate") == "PASS":
        n = sum(r.report.get("pieces", 0) for r in results if r.ok)
        want = extract
        if want is None:
            print(f"   추출 리허설 {n:,}청크 → LLM {n:,}회.")
            try:
                want = input("   켤까? [Y/n] ").strip().lower() not in ("n", "no")
            except (EOFError, KeyboardInterrupt):
                # **비대화형이면 끄고 그 사실을 뷰에 남긴다** — 조용히 도는 구간을
                # 두지 않는다: 승인자는 「추출을 보고 승인했다」고 믿으면 안 된다.
                want = False
                print("   (비대화형 — 끄고 진행한다. 뷰에 「추출 리허설 없음」)")
        print(f"   → 추출 리허설 {'켬' if want else '끔'}")
        rehearsal = _extract_rehearsal(st, results, samples, want, _trunc)
        if rehearsal.get("totals"):
            t = rehearsal["totals"]
            print(f"   추출 리허설({rehearsal['source']}) — 청크 {t['chunks']} · "
                  f"개체 {t['entities']} · 관계 {t['relations']} · "
                  f"부착 {t['attach']} · 미해소 {t['unresolved']}")
            if rehearsal.get("note"):
                print(f"     {rehearsal['note']}")
    return rehearsal


def cmd_review(doc_type, instruct=None, rows=REHEARSAL_ROWS, llm_coord=None,
               extract=None):
    """② 검수 — 기계 관문 → 뷰 데이터 → HTML. 지시가 오면 **재생성 루프**를 돈다.

    **상한은 없다**(§7 규약 2 · A8 — 근거 없는 수치 금지). 매회 지시가 이력에 남고
    중단은 사람 판단이다. 화면에는 강제 없는 안내만 둔다.
    """
    st = _state(doc_type)
    if not st:
        raise SystemExit(f"[뷰 확인] '{doc_type}'의 생성이 먼저다 — "               # [상태]
                         f"근거 review/{doc_type}/state.json 없음\n"
                         f"  ▶ 다음 줄:\n"
                         f"     python -m cli.register generate {doc_type} "
                         f"<층> <표본...>")

    from cli.ingest import doc_id_of            # 리허설도 운영 doc_id다 (B51-2 · B55 ⑤)

    if instruct:                                   # 재생성 루프 1회
        _rc = _cmd_review_instruct(doc_type, st, instruct)
        if _rc:
            return _rc
        st = _state(doc_type)

    samples = st["samples"]
    print(f"  {gateway.mode_line()}")          # B42 ⑤
    if st.get("machine_gate") != "PASS":
        # **막는 이유와 다음 줄을 여기서도 준다**(B59 ①) — 세 명령이 같은 블록이다.
        # 뷰는 그래도 만든다: 이상 신호에 그 FAIL이 실려 있고, 사람이 **무엇이
        # 뽑혔는지**를 보고 지시를 쓸 재료가 그 화면이다. 확정은 관문이 막는다.
        gate.gate_block(doc_type, st)
        print("")
    print(f"■ ② 뷰 확인 — {doc_type} (표본 {len(samples)}부)")
    # **하네스는 여기서 돌지 않는다**(M9 개정 · B50) — 생성이 이미 돌려 통과분만
    # 넘겼다. 검수는 **내용 판단**이다: role 배정·제외 열·분할을 사람이 본다.
    ok = st.get("machine_gate") == "PASS"
    out = st.get("harness_out", "")
    print(f"   기계 관문: 생성 단계에서 {'PASS' if ok else 'FAIL'} "
          f"(하네스는 생성이 돌린다 — 검수는 내용을 본다)")

    mod = _load(draft_mod._at(st["adapter"]), f"reg_{doc_type}")

    _gateway_ready()          # ⑥-1 연결 확인이 먼저다 — 60초×N을 기다리게 하지 않는다

    # ⑥-3 **좌표 미스를 먼저 세고, LLM 보조는 물어보고 켠다.**
    #     1차는 무LLM(정확 일치 대조만) — 빠르고, 그 결과가 미스 계수의 재료다.
    # 이미지 요약(LLM 지점 ④)의 실호출 경로는 **주입**한다 — 파서는 core를
    # import하지 않는다(P1). 등록 리허설도 운영 파싱과 같은 배선을 탄다.
    def _run(pick):
        out = []
        for i, s in enumerate(samples, 1):
            lbl = f"{i}/{len(samples)} ({Path(s).name})"
            # **주입 조립은 한 자리다**(B48) — 좌표 보조만 사람이 끌 수 있으므로
            # 그 하나를 덮어쓴다. 나머지 둘은 진입점이 정한 그대로 내려간다.
            # **리허설 파싱도 운영의 doc_id를 쓴다**(문서 6 §6.6 B51-2 · B55 ⑤).
            # 구판은 `{DOC_TYPE}{i:02d}`라, 구조 지도·이미지 요약 보존분이 `CP01`
            # 대신 그 이름으로 남아 **운영 인입이 못 찾았다** — 체크포인트 키가
            # 같아야 재사용이 성립한다. `_extract_rehearsal`만 고쳐져 있었다.
            out.append(pipeline.parse(
                # **좌표 층이다**(B85 ② — doc_type의 층이 아니다): `process_ref`가
                # 가리키는 것은 좌표 층의 골격이라, 품질층 doc_type의 리허설이
                # 제 층의 닫힌 목록(빈 목록)을 읽으면 좌표가 전부 목록 밖이 된다.
                mod, doc_id_of(s), s, layer=coord_layer(),
                **{**injections(), "pick_coord": pick},
                max_rows=rows,
                progress=lambda a, b, c, _l=lbl: _progress(a, b, c, label=_l)))
        return out

    results = _run(None)
    misses = _coord_misses(results, coord_layer())
    if _ask_llm_coord(misses, llm_coord):
        results = _run(points.coord_picker())     # 사람이 켰을 때만 실호출이 돈다

    for r in results:
        reh = r.report.get("rehearsal") or {}
        part = (f" · **부분 리허설** 전 {reh['full_rows']:,}행 중 앞 {reh['max_rows']:,}행"
                if reh.get("truncated") else "")
        print(f"   파싱 {r.doc_id}: {'OK' if r.ok else 'FAIL'} · "
              f"조각 {r.report.get('pieces', 0)}{part}")

    # **prose ②구획 — 추출 리허설**(B51). 비용 관문은 좌표 보조와 동형이다.
    rehearsal = _cmd_review_rehearsal(doc_type, st, results, samples, mod, extract)

    view = build_view(st, results, ok, out, rehearsal)
    d = _dir(doc_type)
    (d / "view.json").write_text(json.dumps(view, ensure_ascii=False, indent=2) + "\n",
                                 encoding="utf-8")
    (d / "view.html").write_text(render(view), encoding="utf-8")   # kit 렌더러 호출
    # **판정되지 않은 열이 있는 채로 확정되면 그 열은 영영 안 보인다**(B49) —
    # orphan은 기계 관문을 막는다. 「사람이 판정할 것」이 아니라 「대장이 어긋났다」다.
    # **생성이 세운 값과 파싱 결과의 AND**(B50 ⑧) — 리허설이 깨지면 여전히 FAIL이다.
    _orphan = ledger.unmappable_of(
        json.loads((draft_mod._at(st["schema"])).read_text(encoding="utf-8")), mod)[2]
    if _orphan:
        print(f"   스키마 대장에 없는 열 {len(_orphan)}건 — "
              f"{[u['field'] for u in _orphan]} (기계 관문 FAIL)")
    st["machine_gate"] = ledger.gate_verdict(ok, all(r.ok for r in results), _orphan)
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


def _promote_paths(doc_type):
    """정본 자리의 경로 — **등재는 이 경로로 하고 복사는 그 뒤에 한다**."""
    return (f"adapters/{doc_type}.py", f"schemas/{doc_type}.json")


def _promote(doc_type, st):
    """확정 산출을 **검수 자리에서 정본 자리로 옮긴다** (문서 6 §6.5).

    어댑터는 `adapters/{doc_type}.py`, 매칭 스키마는 `schemas/{doc_type}.json`이고
    등록부 등재가 그 활성화다. `review/{doc_type}/`에 남는 것은 입력 패키지·뷰
    데이터·정적 HTML·**승인 기록**이지 정본 실물이 아니다.

    이행이 없으면 확정본이 검수 산출 디렉터리에 남는데, **그 디렉터리는 버전 추적
    대상이 아니라** 재생성 시 확정된 어댑터가 함께 사라진다.

    **원본은 지우지 않는다** — fixture(외부 LLM 실산출 스냅샷)가 원본인 경우가 있고
    그것은 손대지 않는 자리다(문서 7 §7.5-4). 복사로 이행한다.
    """
    a_rel, s_rel = _promote_paths(doc_type)
    src_a, src_s = draft_mod._at(st["adapter"]), draft_mod._at(st["schema"])
    dst_a, dst_s = paths.registry() / a_rel, paths.registry() / s_rel
    paths.ensure(dst_a)
    paths.ensure(dst_s)
    if src_a.resolve() != dst_a.resolve():
        dst_a.write_bytes(src_a.read_bytes())
    if src_s.resolve() != dst_s.resolve():
        dst_s.write_bytes(src_s.read_bytes())
    return (a_rel, s_rel)


def cmd_status(doc_type):
    """관문 상태 한 화면 (B59 ①) — **화면이 흘러간 뒤 다시 볼 자리.**

    찍는 것은 `gate.gate_block`과 같은 블록이다. 통과했으면 다음 두 줄을 말한다 —
    「무엇을 치면 되는지」가 통과 쪽에서도 화면에 있어야 대칭이 선다.
    """
    st = _state(doc_type)
    if not st:
        raise SystemExit(f"[상태] '{doc_type}' 생성이 먼저다 — "                  # [상태]
                         f"근거 review/{doc_type}/state.json 없음\n"
                         f"  ▶ 다음 줄:\n"
                         f"     python -m cli.register generate {doc_type} "
                         f"<층> <표본...>")
    if gate.regate(doc_type, st) != "PASS":          # 저장값이 아니라 지금 판정이다
        gate.gate_block(doc_type, st)
        return 1
    print(f"■ 기계 관문 PASS — {doc_type}")
    _vw = _dir(doc_type) / "view.html"
    print("")
    print("  ▶ 다음 줄:")
    if _vw.exists():
        print(f"     (뷰 확인) {_vw.relative_to(ROOT)}")
    print(f"     python -m cli.register confirm {doc_type} --by <승인자>")
    print(f"     python -m cli.register review {doc_type} --instruct \"…\""
          f"   (고칠 것이 있을 때만)")
    return 0