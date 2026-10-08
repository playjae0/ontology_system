# -*- coding: utf-8 -*-
"""칸 3.1 — **일괄 투입** — 문서 여럿을 `ingest_file` 하나로 잇는다: 폴더(`ingest-dir`)와 재구축(B106 ①).

`cli/ingest.py`에서 떼어냈다(B106 ① — §7 파일 상한 800행 · 재구축이 같은 고리를 쓴다). 고리는
`ingest_list` 하나다 — 한 실행 한 사전 점검(B98 ①) · 문서마다 `ingest_file`(마무리 없이 · 묻지 않음) ·
마무리(미러 · 재시도) 1회 · 결과표 · 총계 줄. 폴더 투입은 문서마다 같은 옵션이고, 재구축은 문서마다
그 문서의 옵션(doc_type · 그림 뺌 · 중복 허용)을 준다. 이름들은 `cli.ingest`에서도 그대로 보인다
(호출 계약 유지).
"""
from __future__ import annotations

from pathlib import Path

from cli import _screen
from cli.parse import COORD_CAP
from core import paths
from core.llm import gateway
from core.state import log

# reader가 여는 포맷 — **목록은 리더가 소유한다**(B53)
from parser.reader import LEGACY_BINARY, SUPPORTED   # noqa: E402


def ingest_list(items, *, dry_run=False, adapter_paths=None, coord_cap=COORD_CAP,
                progress_every=None, sheets=None, revise=False):
    """문서 여럿 — `items`는 `[(경로, {doc_type, no_images, allow_duplicate})]`. 돌려주는 것은 결과 행들."""
    from cli import ingest as IN
    from cli.preflight import has_images
    rows = []
    u0 = gateway.usage_total()
    # **사전 점검은 실행당 1회**(B98 ①) — 그림은 묶음 안 어느 문서에라도 있으면 본다
    pf = {"ok": None, "images": any(not o.get("no_images") and has_images(f) for f, o in items)}
    for f, o in items:
        rows.append(IN.ingest_file(f, o.get("doc_type"), dry_run, adapter_paths,
                                   finalize_after=False, coord_cap=coord_cap,
                                   progress_every=progress_every, ask=False,
                                   no_images=bool(o.get("no_images")), sheets=sheets, preflight=pf,
                                   revise=revise, allow_duplicate=bool(o.get("allow_duplicate"))))
        if rows[-1].get("preflight_fail"):
            break                                  # 같은 실행의 나머지도 같은 자리에서 막힌다
    if not dry_run and any(r["status"] == IN.OK for r in rows):
        IN._finalize_screen()                   # 빌드 말미 패스는 전 문서 뒤 1회
    print(summary(rows))
    from cli import result_screen
    result_screen.batch(rows)                   # 문서별 한 줄 + 전체 합 (B99 ⑤)
    if not dry_run:
        # **총계 한 줄**(B73 ①) — 문서마다의 요약은 위에 있고, 배치의 비용은
        # 여기서만 보인다. 사람이 「이 폴더를 넣으면 얼마」를 알 자리다.
        u = gateway.usage_total()
        print(_screen.banner(
            f"  전체 — 문서 {len(rows):,} · LLM 호출 {u['calls'] - u0['calls']:,} · "
            f"{_screen.tokens(u, u0)}"))
        if log.LOG_PATH:
            print(f"  로그 {log.LOG_PATH}  (INFO 전량 · 화면은 판단이 갈린 값만)")
    return rows


def ingest_dir(path, doc_type=None, dry_run=False, adapter_paths=None,
               coord_cap=COORD_CAP, recurse=False, progress_every=None, no_images=False,
               sheets=None, revise=False):
    """경로의 문서를 **하위 폴더 없이** 순회한다(D-110 — 하위 폴더는 별도 투입).

    `--doc-type`을 주면 그 경로 전부를 그것으로 본다(비정형 폴더 단위 지정 — B46).

    `recurse`는 **원본 자리(⓪)를 돌 때만** 참이다(B79 ②): 그 폴더는 사람이 제
    분류로 하위 폴더를 만들어 넣는 자리라 한 겹만 보면 대부분을 지나친다. 경로를
    직접 준 경우는 D-110 그대로다 — 사람이 적은 범위를 넓히지 않는다.
    """
    p = Path(path)
    if not p.is_dir():
        raise SystemExit(f"[투입] 경로가 아니다: {p} — "                          # [상태]
                         f"폴더가 아니거나 없다\n"
                         f"  ▶ 다음 줄 — 문서 한 건이면:\n"
                         f"     python run.py ingest-file {p}")
    _it = p.rglob("*") if recurse else p.iterdir()
    files = sorted(x for x in _it if x.is_file()
                   and not x.name.startswith(("~", "."))
                   and "__pycache__" not in x.parts)
    opts = {"doc_type": doc_type, "no_images": no_images}
    return ingest_list([(f, opts) for f in files], dry_run=dry_run, adapter_paths=adapter_paths,
                       coord_cap=coord_cap, progress_every=progress_every, sheets=sheets,
                       revise=revise)


def summary(rows):
    """끝에 모아 보이는 목록 — 성공 · 실패 · 미선택 (dry-run은 선택만)."""
    from cli.ingest import FAIL, OK, SKIP
    groups = {}
    for r in rows:
        groups.setdefault(r["status"], []).append(r)
    lines = [f"■ 일괄 투입 결과 — {len(rows)}건: " + " · ".join(
        f"{k} {len(v)}" for k, v in groups.items())]
    for k in (OK, "선택만", FAIL, SKIP):
        for r in groups.get(k, []):
            lines.append(f"  [{k}] {Path(r['doc']).name:<24} doc_id {r['doc_id']:<18} "
                         f"{('doc_type ' + r['doc_type']) if r.get('doc_type') else '':<20} "
                         f"{r.get('reason') or ''}")
    # **선택 의존 부재는 끝에 한 번 모은다**(B86 ④) — 문서마다 같은 설치 줄이 흘러가면
    # 무엇을 치면 되는지가 목록 속에 묻힌다.
    need = sorted({r["missing_dep"] for r in rows if r.get("missing_dep")})
    if need:
        lines.append(f"  ▶ 선택 의존이 없다 — 문서 "
                     f"{sum(1 for r in rows if r.get('missing_dep'))}건이 그 때문에 멈췄다:")
        lines += [f"     {m}" for m in need]
    return "\n".join(lines)


def _is_doc(p):
    """파서가 읽는 포맷의 파일인가 — **기준은 `reader.SUPPORTED` 하나다**(B80 ②).

    ⓪원본 자리에는 사람이 자기 분류로 아무것이나 넣는다(메모·이미지·엑셀 임시파일).
    선별 기준을 여기서 새로 쓰면 파서가 여는 목록과 갈린다 — 그래서 그 목록을 묻는다.
    """
    # 옛 이진 형식(`.doc` 등)도 **집는다** — 조용히 건너뛰면 사람은 넣은 줄 안다.
    # 선택이 그것을 거부 행으로 내고 문면이 「`.docx`로 저장해 다시」를 말한다(B88 ②).
    return (p.is_file() and p.suffix.lower() in (*SUPPORTED, *LEGACY_BINARY)
            and not p.name.startswith(("~", ".")))


def _raw_target():
    """인자 없는 `ingest-dir`의 대상 — ⓪원본 자리 (B80 ②).

    두 가지를 말한다. ①자리가 비면 **빈 배치로 조용히 끝내지 않는다** ②옛 이름
    (`docs/`)에 문서가 있으면 **상태 거부**다 — 이름이 `raw/`로 바뀐 것을 모르는
    사람에게 「0건」만 보여 주면 자기 문서가 왜 안 들어가는지 알 길이 없다.
    """
    raw = paths.raw()
    old = paths.legacy_raw()          # 옛 이름도 자리 소유자가 안다(B80 ②)
    if not raw.is_dir() or not any(_is_doc(p) for p in raw.rglob("*")):
        if old.is_dir() and any(_is_doc(p) for p in old.rglob("*")):
            raise SystemExit(                                             # [상태]
                f"[투입] 원본 자리가 `raw/`로 바뀌었다 — 옛 이름에 문서가 있다"
                f"(B80 ②)\n"
                f"  지금 잰 것 — {old} 문서 "
                f"{sum(1 for p in old.rglob('*') if _is_doc(p))}건 · "
                f"{raw} {'비어 있다' if raw.is_dir() else '없다'}\n"
                f"  근거 — 인자 없는 ingest-dir는 `<상태>/raw/`를 돈다"
                f"(`core/paths.raw()`) · 레포의 `docs/`는 명세 폴더라 이름이 갈렸다\n"
                f"  ▶ 다음 줄 — 옮기고 다시 돌린다:\n"
                f"     mv {old} {raw}\n"
                f"     python run.py ingest-dir")
        raise SystemExit(                                                 # [상태]
            f"[투입] 넣을 문서가 없다 — {raw}가 "
            f"{'비어 있다' if raw.is_dir() else '없다'}\n"
            f"  지금 잰 것 — 원본 자리(⓪) {raw} · 파서가 읽는 포맷 "
            f"{' '.join(SUPPORTED)}\n"
            f"  근거 — 인자 없는 ingest-dir는 원본 자리 전체를 돈다"
            f"(`core/paths.raw()`)\n"
            f"  ▶ 다음 줄 — 원본을 넣고 다시 돌린다:\n"
            f"     mkdir -p {raw} && cp <문서...> {raw}\n"
            f"     python run.py ingest-dir            (또는 경로를 직접 적는다)")
    return raw
