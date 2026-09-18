# -*- coding: utf-8 -*-
"""칸 1.3 — **문답 로그와 배치**: 라운드 전문·결정 이력을 `review/<dt>/`에 남긴다."""

from __future__ import annotations

from cli.prompt import (  # noqa: F401
    KIT_NOTE, VOCAB_SECTIONS, _dir, _strip_kit_notes, _dump_prompt, _strip_module_doc,
    _reference_adapter, generate_template, _render_template, _vocab_excerpt, _sent_size)
from pathlib import Path
import json
from cli.register import REVIEW, ROOT


INTERVIEW_LOG = "interview_log.json"     # `review/<doc_type>/` 안 — 라운드 전문의 자리


def _batch_at():
    """묶음의 시각 — **짝을 맞추는 키라 초 해상도로는 모자란다** (B62 ②).

    `store._now()`는 초까지다(적재 시각의 규격이다). 그 값을 묶음 키로 쓰면 **같은
    초에 만들어진 두 묶음이 한 키가 되고**, 로그가 같은 키의 앞 묶음을 치환해
    **사람의 답이 조용히 사라진다**(실측: 한 번의 검사에서 세 묶음이 한 묶음으로
    접혔다). 시각을 위조하는 것이 아니라 **같은 실제 시각을 더 잘게 읽는다.**
    """
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def log_path(doc_type):
    return _dir(doc_type) / INTERVIEW_LOG


def read_log(doc_type):
    """`{at: [라운드…]}` — 없거나 깨졌으면 빈 dict.

    **묶음과 짝은 `at`으로 맞춘다**(B62 ②). 순서로 맞추면 묶음 하나가 지워지는 날
    전 묶음의 전문이 한 칸씩 밀려 다른 표본의 대화가 된다.
    """
    try:
        obj = json.loads(log_path(doc_type).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {b.get("at"): (b.get("rounds") or [])
            for b in (obj.get("batches") or []) if b.get("at")}


def write_rounds(doc_type, at, samples, rounds):
    """한 묶음의 라운드 전문을 로그에 쓴다 — **패키지에는 쓰지 않는다**(B62 ②).

    전문이 패키지에 살면 생성 user 메시지(패키지 원문 통째)에 그대로 실려 모델에
    간다 — 사내 실측 3천 줄이었다. B60 ②가 system 프롬프트의 힌트 자리만 요약으로
    바꿨고 **user 쪽은 그대로였다.** 보내는 쪽에서 걷어내지 않고 **패키지를
    깨끗하게** 한다: 걷어내는 방식은 잊을 자리를 하나 더 만든다.
    """
    d = _dir(doc_type)
    try:
        obj = json.loads(log_path(doc_type).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        obj = {}
    batches = [b for b in (obj.get("batches") or []) if b.get("at") != at]
    batches.append({"at": at, "samples": sorted(samples or []), "rounds": rounds})
    log_path(doc_type).write_text(
        json.dumps({"_읽는 법": "문답 라운드 전문 — **이력이다.** 판단은 입력 패키지의 "
                              "human.hint.interview[].decisions에 있고 생성은 그것만 읽는다",
                    "batches": batches}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")


def migrate_rounds(doc_type, pkg):
    """옛 패키지의 인라인 `rounds`를 **로그로 한 번 옮긴다** (B62 ②).

    `--resume`이 이 경로로 들어온다. 옮긴 뒤 패키지 묶음은
    `{samples, at, stale?, decisions[]}`만 남는다 — 돌려주는 것은 화면 한 줄이거나
    `None`이다. 옮기는 것이지 버리는 것이 아니다: 전문은 재현 근거다.
    """
    hint = ((pkg or {}).get("human") or {}).get("hint")
    batches = _hint_batches(hint)
    moved = [b for b in batches if b.get("rounds")]
    if not moved:
        return None
    n = 0
    for b in moved:
        at = b.get("at") or _batch_at()
        b["at"] = at
        write_rounds(doc_type, at, b.get("samples") or [], b["rounds"])
        n += len(b["rounds"])
        del b["rounds"]
    pkg.setdefault("human", {})["hint"] = _merge_hint(hint, batches)
    return (f"   문답 라운드 {n}건을 로그로 옮겼다 → "
            f"{log_path(doc_type).relative_to(ROOT)}  "
            f"(패키지에는 확정 사항만 남는다 — 생성이 읽는 것이 그것이다)")


def warn_no_decisions(doc_type, pkg):
    """묶음은 있는데 **확정 사항이 하나도 없다** — B60 이전 패키지다 (B62 ②ⓓ).

    죽이지 않는다. 진행은 되지만 **생성이 읽을 판단이 없다**는 사실을 말하고, 그것을
    세울 명령 둘을 함께 준다. 힌트만 준 패키지는 해당 없다(`hint_only_decisions`가
    이미 한 항목을 세웠다).
    """
    batches = _hint_batches(((pkg or {}).get("human") or {}).get("hint"))
    if not batches or any(b.get("decisions") for b in batches):
        return None
    return (f"   ⚠ 이 패키지에 **확정 사항이 없다** — 문답 묶음 {len(batches)}개는 "
            f"있는데 결정이 비어 있다(B60 이전 산출). 생성이 읽을 판단이 없다.\n"
            f"     python -m cli.register review {doc_type} "
            f"--instruct \"<결정 한 문장>\"\n"
            f"     python -m cli.register generate {doc_type} <층> <표본...> --interview")


def _keep_prior(prior, counts=None):
    """**멈추고 묻는다**(B55 ②-4) — 사람의 답은 다시 만들 수 없는 재료다.

    기본은 이어가기다: 비대화형에서 조용히 버리면 그것이 바로 이 회차가 고치는
    병이다(구판은 경고 한 줄 없이 덮어썼다). 버리려면 사람이 답하거나
    `--drop-interview`를 적어야 한다.
    """
    counts = counts or {}
    def _n(b):
        return len(counts.get(b.get("at")) or b.get("rounds") or [])
    n = sum(_n(b) for b in prior)
    print(f"\n   이 등록에 **이전 문답 {n}라운드**가 남아 있다 "
          f"(묶음 {len(prior)}개).")
    for b in prior[-3:]:
        print(f"     · {b.get('at', '?')[:19]} · 표본 "
              f"{[Path(x).name for x in (b.get('samples') or [])]} · "
              f"{_n(b)}라운드")
    try:
        ans = input("   이어갈까? [Y/n]  (n이면 버린다 · 사람의 답은 다시 못 만든다) "
                    ).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("   (비대화형 — **이어간다.** 버리려면 --drop-interview)")
        return True
    return ans not in ("n", "no")


def _new_batch(samples):
    # `decisions`가 **확정 요약의 자리**다(B60 ②) — 라운드 전문(`rounds`)은 이력으로
    # 남고, 생성 프롬프트에는 이것만 실린다. 자리는 항상 있다(빈 리스트라도).
    # **라운드 전문은 여기 없다**(B62 ②) — 로그(`interview_log.json`)로 간다.
    # 묶음이 패키지에 사는 이유는 `decisions`가 생성의 입력이기 때문이고,
    # 전문은 입력이 아니라 이력이다.
    return {"samples": sorted(samples), "at": _batch_at(), "decisions": []}


def hint_only_decisions(text):
    """문답 없이 `--hint`만 준 경우의 확정 사항 — **힌트 문장 그대로 한 항목**(B60 ②).

    자리는 항상 있어야 한다: 생성 프롬프트의 `[확정 사항]`이 「문답을 했나」에 따라
    있다 없다 하면, 모델이 없는 절을 찾거나 힌트를 결정보다 약하게 읽는다.
    """
    t = (text or "").strip()
    return [{"topic": "힌트", "decision": t, "reason": "사람 힌트(자유 텍스트)",
             "round": None}] if t else []


def apply_instruction_to_decisions(doc_type, instruction, rev):
    """`--instruct`가 **확정 사항을 갱신한다**(B60 ②) — LLM 0.

    지시와 결정이 따로 살면 다음 재생성이 옛 결정을 다시 쓴다. 규칙은 결정적이다:
    지시 문면에 **어느 항목의 `topic`이 그대로 들어 있으면** 그 항목의 `decision`을
    지시로 바꾸고 `reason`에 「사람 지시 (rev N)」를 붙인다. 어느 topic도 안 들어
    있으면 **새 항목**으로 붙인다 — 지시를 버리지 않는다(무엇에 대한 것인지 사람이
    topic을 안 적었을 뿐이다). 매칭에 LLM을 쓰지 않는 이유: 이 갱신이 판단이 되면
    「지시가 결정을 뒤집었다」가 사람 눈에 안 보이는 자리에서 일어난다.
    """
    path = REVIEW / doc_type / "input_package.json"
    if not path.exists() or not (instruction or "").strip():
        return None
    obj = json.loads(path.read_text(encoding="utf-8"))
    hint = (obj.get("human") or {}).get("hint")
    batches = _hint_batches(hint)
    live = [b for b in batches if not b.get("stale")]
    if not live:
        live = [_new_batch((obj.get("human") or {}).get("samples") or [])]
        batches = batches + live
    hit = 0
    for b in live:
        for d in b.get("decisions") or []:
            t = (d.get("topic") or "").strip()
            if t and t in instruction:
                d["decision"] = instruction.strip()
                d["reason"] = f"사람 지시 (rev {rev}) — 이전: {d.get('reason', '')}"
                hit += 1
    if not hit:
        live[-1].setdefault("decisions", []).append(
            {"topic": f"지시 (rev {rev})", "decision": instruction.strip(),
             "reason": f"사람 지시 (rev {rev})", "round": None})
    obj.setdefault("human", {})["hint"] = _merge_hint(hint, batches)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return hit


_BATCH_KEYS = ("decisions", "rounds", "samples")


def _hint_batches(hint):
    """`hint`가 어떤 꼴이든 문답 묶음 리스트를 돌려준다.

    옛 꼴 셋을 다 받는다 — ①문자열 힌트 ②`{text, interview: [라운드…]}`(B55 이전)
    ③`{text, interview: [묶음…]}`(지금). ②는 묶음 하나로 감싼다: **옛 패키지를
    읽지 못해 이전 문답을 잃는 것이 바로 이 회차가 고치는 병이다.**
    """
    if not isinstance(hint, dict):
        return []
    iv = hint.get("interview") or []
    # **묶음인가는 묶음 키로 가른다** — `rounds`만 보면 B62 ② 이후 묶음
    # (`{samples, at, decisions}`)을 통째로 못 읽어 확정 사항이 사라진다.
    if iv and isinstance(iv[0], dict) and not any(k in iv[0] for k in _BATCH_KEYS):
        return [{"samples": [], "at": None, "rounds": iv}]      # 옛 꼴 → 묶음 1개
    return [b for b in iv if isinstance(b, dict) and any(k in b for k in _BATCH_KEYS)]


def prior_interview(pkg_path):
    """기존 패키지의 문답 묶음. 파일이 없거나 깨졌으면 빈 리스트다."""
    try:
        old = json.loads(Path(pkg_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return _hint_batches(((old.get("human") or {}).get("hint")))


def _age_rounds(batches, samples):
    """표본이 바뀐 묶음에 `stale`을 단다. **지우지 않는다.**

    지우면 재현 조건이 사라지고(그 답으로 만들어진 산출이 왜 그렇게 됐는지 못
    되짚는다), 구분 없이 누적하면 **다른 문서에 대한 이해가 현재 판정에 섞인다.**
    그래서 남기되 표시한다 — 문답 세션은 이것을 「이전 표본에 대한 이해」로 따로 싣는다.
    """
    now = sorted(samples)
    out = []
    for b in batches:
        b = dict(b)
        if sorted(b.get("samples") or []) != now:
            b["stale"] = True
        else:
            b.pop("stale", None)
        out.append(b)
    return out


def _merge_hint(hint, batches):
    """묶음 리스트를 `hint` 그릇에 되돌린다 — **다른 키는 건드리지 않는다.**"""
    base = dict(hint) if isinstance(hint, dict) else {"text": hint or ""}
    base["interview"] = batches
    return base
