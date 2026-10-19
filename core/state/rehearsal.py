# -*- coding: utf-8 -*-
"""칸 1.7 · 3.3 — **리허설 산출 자리** — 등록 검수의 리허설이 남긴 LLM 산출을 doc_id · 새 doc_type으로 두고 그 종류로 인입할 때 쓴다 (B116 ②).

리허설은 임시 상태 루트에서 돈다(`cli/register/rehearsal.py` — 운영은 읽기만). 끝에 남는 것은 여기 하나다:

  `work/extract/rehearsal/<doc_type>/<doc_id>/` (④ — 추출 폴더 안이라 기본 fresh가 남긴다 · 클린 `--all`이 지운다)
    · `extract/<doc_id>[@렌즈].json` — 추출 체크포인트
    · `outline/<doc_id>[@렌즈].json` — 문서 개요 체크포인트(추출 재사용 조건이 그 대상 제목을 본다 — 함께 다닌다)
    · `struct_map.json` — 구조 지도 · 계층 규칙 선언 · 이미지 요약 보존분(파서의 한 파일)
    · `coord_learned.json` — 리허설이 새로 배운 좌표 표기(운영 기록에 없던 것만 · 적중 횟수는 싣지 않는다)
    · `meta.json` — 어느 등록 · 언제 · 어느 원본

**쓰는 때 = 그 doc_type으로 그 문서를 인입할 때** — 쓰는 자리에서 **지금의 재사용 조건이 같을 때만** 운영 자리로
옮긴다(조건은 그 산출의 주인 모듈이 지금처럼 판정한다 — 여기는 옮기기만): 파싱 앞(`take_parse` — 구조 지도 · 좌표
학습) · 개요(`outline.run`) · 추출(`extract.extract`). 다르면 쓰지 않고 지운다(그 사실은 화면 줄). 원래 종류로 다시
넣으면 이 자리를 보지 않는다 — 자리의 키가 doc_type이다. 부분 리허설 · 실패 · 중단은 여기에 쓰지 않는다.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from core import paths
from core.state import log, store

_LOG = log.get(__name__)

#: 묶음 안의 이름 — 추출 · 개요 체크포인트 폴더 · 구조 지도 · 좌표 학습 · 머리
EXTRACT, OUTLINE, STRUCT, LEARNED, META = "extract", "outline", "struct_map.json", "coord_learned.json", "meta.json"


def place(doc_type, doc_id, *parts):
    """그 등록 · 그 문서의 묶음 자리(조립은 `paths.rehearsal`)."""
    return paths.rehearsal(str(doc_type), str(doc_id), *parts)


def carried(doc_type, doc_id, kind, name):
    """묶음 안의 체크포인트 하나 — 있으면 경로 · 없으면 None(`kind` = `extract` | `outline`)."""
    if not doc_type or not doc_id:
        return None
    p = place(doc_type, doc_id, kind, name)
    return p if p.exists() else None


def bundles(doc_id=None):
    """남은 묶음 `[(doc_type, doc_id, 자리)]` — 화면 · 시험이 읽는다."""
    root = paths.rehearsal()
    out = []
    for d in sorted(root.glob("*/*")) if root.exists() else []:
        if d.is_dir() and (doc_id is None or d.name == doc_id):
            out.append((d.parent.name, d.name, d))
    return out


def named(d, doc_id):
    """폴더 `d`의 그 문서 체크포인트 — 기본 + 렌즈판(부분 파일 · 다른 문서는 빼고)."""
    d = Path(d)
    if not d.exists():
        return []
    return [p for p in [d / f"{doc_id}.json"] if p.exists()] + sorted(d.glob(f"{doc_id}@*.json"))


def _put(dst, blob):
    paths.ensure(dst)
    store.atomic_write_bytes(dst, blob)


def _prune(doc_type, doc_id):
    """머리(`meta.json`)만 남은 묶음은 지운다 — 빈 폴더도(그 등록 폴더 · 리허설 폴더까지)."""
    d = place(doc_type, doc_id)
    if not d.exists():
        return
    left = [p for p in d.rglob("*") if p.is_file() and p.name != META and not p.name.endswith(".lock")]
    if not left:
        shutil.rmtree(d, ignore_errors=True)
        for up in (d.parent, paths.rehearsal()):            # 빈 등록 폴더 · 빈 리허설 폴더까지
            try:
                up.rmdir()
            except OSError:
                break


def save(doc_type, doc_id, tmp_home, *, learned=None, meta=None):
    """임시 상태 루트 → 묶음(그 doc_type · doc_id의 옛 묶음은 갈아 끼운다). **운영과 바이트가 같은 것은 싣지 않는다**
    (임시 루트가 운영에서 읽어 둔 사본 — 리허설이 새로 만든 것만 다닌다). 돌려주는 것은 실은 이름 목록."""
    from core.build import extract as EX
    from core.build import outline as OL
    shutil.rmtree(place(doc_type, doc_id), ignore_errors=True)
    got = []
    for kind, opdir in ((EXTRACT, EX.EXTRACT_DIR), (OUTLINE, OL.checkpoint_path(doc_id).parent)):
        for src in named(paths.mirror(opdir, tmp_home), doc_id):
            blob, op = src.read_bytes(), opdir / src.name
            if op.exists() and op.read_bytes() == blob:
                continue
            _put(place(doc_type, doc_id, kind, src.name), blob)
            got.append((kind, src.name))
    op_sm = paths.struct_maps(f"{doc_id}.json")     # 운영 자리(파서 주입은 리허설 중 임시 루트를 가리킨다)
    sm = paths.mirror(op_sm, tmp_home)
    if sm.exists() and not (op_sm.exists() and op_sm.read_bytes() == sm.read_bytes()):
        _put(place(doc_type, doc_id, STRUCT), sm.read_bytes())
        got.append(("", STRUCT))
    if learned and (learned.get("채택") or learned.get("목록밖")):
        _put(place(doc_type, doc_id, LEARNED), json.dumps(learned, ensure_ascii=False, indent=2).encode("utf-8"))
        got.append(("", LEARNED))
    if got:
        _put(place(doc_type, doc_id, META), json.dumps(
            {"doc_type": doc_type, "doc_id": doc_id, "at": store._now(), **(meta or {}),
             "files": [f"{k}/{n}" if k else n for k, n in got]}, ensure_ascii=False, indent=2).encode("utf-8"))
    _LOG.info("리허설 산출 — %s · %s → %s %s", doc_type, doc_id, paths.show(place(doc_type, doc_id)), got)
    return got


def take(carry, dst):
    """묶음의 체크포인트 하나를 운영 자리로 옮긴다(`dst`) — `dst`가 None이면(조건이 다르다) 쓰지 않고 지운다."""
    parts = Path(carry).resolve().relative_to(paths.rehearsal().resolve()).parts
    if dst is not None:
        _put(Path(dst), Path(carry).read_bytes())
    Path(carry).unlink(missing_ok=True)
    _prune(parts[0], parts[1])


def take_parse(doc_type, doc_id, src_hash):
    """**파싱 앞** — 구조 지도 · 좌표 학습을 운영 자리로(그 doc_type의 묶음이 있을 때만). 돌려주는 것은 화면 줄 목록.

    구조 지도는 **원본 해시가 같을 때만** — 운영 보존분과 해시가 같으면 프레임 지도 · 규칙 · 이미지 요약을 더하고
    (묶음이 이긴다 — 리허설이 운영 사본에서 시작했다), 운영에 없거나 해시가 다르면 묶음으로 갈아 끼운다. 원본이 바뀌었으면
    쓰지 않고 지운다. 좌표 학습은 **운영 기록에 없는 표기만** 더한다(사람이 거둔 기록 · 적중 횟수는 건드리지 않는다)."""
    from parser import struct_map
    lines = []
    if not doc_type or not place(doc_type, doc_id).exists():
        return lines
    sm = place(doc_type, doc_id, STRUCT)
    if sm.exists():
        m = json.loads(sm.read_text(encoding="utf-8"))
        if m.get("source_hash") != src_hash:
            lines.append(f"리허설 산출({doc_type}) — 구조 지도를 쓰지 않는다: 원본 해시가 다르다(파일이 바뀌었다)")
        else:
            op = struct_map.load_kept(doc_id, src_hash) or {}
            merged = {**op, **m}
            for k in ("maps", "rules", "image_summaries", "structure"):     # 문서 구조도 프레임마다 (B119 ①)
                if op.get(k) or m.get(k):
                    merged[k] = {**(op.get(k) or {}), **(m.get(k) or {})}
            merged.pop("source_hash", None)
            struct_map.keep(doc_id, merged, src_hash)
            lines.append(f"리허설 산출({doc_type}) — 구조 지도를 옮겼다 → {paths.show(struct_map.keep_path(doc_id))}")
        sm.unlink()
    lp = place(doc_type, doc_id, LEARNED)
    if lp.exists():
        add = json.loads(lp.read_text(encoding="utf-8"))
        book = store.read(store.COORD_LEARNED, {})
        have = set(book.get("채택") or {}) | set(book.get("목록밖") or {})
        n = 0
        for sec in ("채택", "목록밖"):
            for k, v in (add.get(sec) or {}).items():
                if k not in have:
                    book.setdefault(sec, {})[k] = v
                    n += 1
        if n:
            store.write(store.COORD_LEARNED, book)
        lines.append(f"리허설 산출({doc_type}) — 좌표 학습 {n:,}표기를 옮겼다(운영 기록에 없던 것만)")
        lp.unlink()
    _prune(doc_type, doc_id)
    return lines
