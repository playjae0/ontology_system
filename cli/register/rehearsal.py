# -*- coding: utf-8 -*-
"""칸 1.6 · 3.3 — **리허설의 임시 상태 루트** — 등록 검수의 리허설은 운영 상태를 바꾸지 않는다 (B116 ① · BLOCKERS 19 처분 c).

    with Session(doc_type, samples) as rs:     # 임시 루트를 만들어 운영에서 읽은 사본을 둔다 · 파서의 쓰기 자리를 그리로
        results = <표본 파싱>                    # 구조 지도 · 좌표 학습은 임시 루트에 쓴다(운영은 읽기만)
        res = rs.extract(envs, layer)           # 추출 — 하위 프로세스가 임시 루트에서(운영과 같은 함수 `cli.extract.run`)
    # 끝: 성공 · 전량이면 그 실행이 쓴 LLM 산출을 ④단 자리로(`core/state/rehearsal.save`) · 어느 끝이든 임시 루트를 지운다

**방법 = 하위 프로세스 + 임시 상태 루트**(D-198 ①): 상태 루트는 프로세스당 한 번 정해지고 모듈 상수가 그 자리를 잡는다
(`core/paths.home`) — 한 프로세스 안에서 루트를 갈아 끼우면 앞에서 잡은 자리와 뒤의 자리가 갈린다. 그래서 추출 · 청크 ·
문서 대장을 쓰는 단계는 **처음부터 임시 루트인 하위 프로세스**가 돈다. 부모에 남는 표본 파싱(대화 · 화면이 부모에 있다)은
파서가 받는 쓰기 자리(구조 지도 · 좌표 학습 — 함수 주입)만 임시 루트로 돌린다.

**같은 조건**: 모드는 강제하지 않는다(환경 그대로 — B111의 격리 함수를 쓰지 않는다) · 설정 파일은 부모가 읽은 **그 파일**을
`ONTO_CONFIG`로 명시한다(상태 루트의 `llm.json`이 임시 루트로 바뀌어 빠지지 않게) · 임시 루트에는 운영의 손잡이(`knobs.json`) ·
층 자산 · 골격 닫힌 목록 · 사전 · 별칭 대장 · 좌표 학습 · 층 등록부 사본 + 그 문서의 운영 체크포인트(추출 · 개요 — 렌즈판
포함)와 구조 지도 사본(같은 판이면 LLM 0) + 그 위에 같은 종류의 앞 리허설 산출. 운영의 그래프 · 문서 대장 · 청크 · 큐 ·
`parsed/`는 싣지 않는다(추출은 그것을 읽지 않는다 — 임시 루트에서 새로 선다).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from core import paths
from core.llm import gateway
from core.state import log, store

_LOG = log.get(__name__)
ROOT = paths.ROOT

#: 임시 루트에 사본으로 두는 ③진실 — 추출 · 개요 · 표본 파싱이 읽는 것(그래프 · 청크 · 문서 대장 · 큐는 아니다)
SEED_DATA = (store.SKELETON_LIST, store.DICTIONARY, store.ALIAS_BOOK, store.COORD_LEARNED, store.REGISTRY)
#: 하위 프로세스의 입출력(임시 루트 안 · 상태 단 밖)
IN_DIR, OUT_FILE = "rehearsal_in", "rehearsal_out.json"


def _copy(src, dst):
    paths.ensure(dst)
    shutil.copy2(src, dst)


def _write_json(p, d):
    """쓰기는 원자적 한 자리(`store.atomic_write_bytes`) — 등록 패키지의 규율 그대로(임시 루트 안이라도)."""
    store.atomic_write_bytes(Path(p), json.dumps(d, ensure_ascii=False).encode("utf-8"))


def _read_json(p, default):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8")) if Path(p).exists() else default
    except (OSError, ValueError):
        return default


class Session:
    """한 검수 실행의 임시 상태 루트 — `with`가 끝나면(성공 · 실패 · 중단 · Ctrl-C) 지운다."""

    def __init__(self, doc_type, samples):
        from cli.ingest import doc_id_of
        self.doc_type, self.ids = doc_type, [doc_id_of(s) for s in samples]
        self.home, self.truncated, self.failed = None, False, False

    # ------------------------------------------------------------ 시작 · 끝
    def __enter__(self):
        self.home = paths.temp_home("onto_rehearsal_")
        try:
            self._seed()
            self._bind()
        except BaseException:
            self._cleanup()
            raise
        print(f"   리허설 — 임시 상태 폴더 {paths.show(self.home)} (운영 상태는 읽기만 · 끝나면 지운다)")
        return self

    def __exit__(self, et, ev, tb):
        try:
            paths.bind_parser()                          # 파서의 쓰기 자리를 운영으로 되돌린다
            if et is None and not self.truncated and not self.failed:
                self._save()
        finally:
            self._cleanup()
        return False

    def _cleanup(self):
        if self.home is not None:
            shutil.rmtree(self.home, ignore_errors=True)
            _LOG.info("리허설 임시 상태 폴더를 지웠다 — %s (남음 %s)", self.home, self.home.exists())

    # ------------------------------------------------------------ 채우기 · 파서 자리
    def _seed(self):
        """운영에서 읽은 사본 — 손잡이 · 층 자산 · ③의 다섯 · 그 문서의 체크포인트와 구조 지도 · 앞 리허설 산출."""
        from core.build import extract as EX
        from core.build import outline as OL
        from core.state import rehearsal as RH
        if paths.layers().exists():
            shutil.copytree(paths.layers(), paths.mirror(paths.layers(), self.home),
                            ignore=shutil.ignore_patterns("__pycache__", ".*.lock"))
        for p in [paths.knobs()] + [store.path(n) for n in SEED_DATA]:
            if Path(p).exists():
                _copy(p, paths.mirror(p, self.home))
        self.learned0 = _read_json(store.path(store.COORD_LEARNED), {})
        reg = store.read(store.DOC_REGISTRY, {})
        for did in self.ids:
            od = OL.checkpoint_path(did).parent
            # 추출 체크포인트는 **같은 종류로 들어간 것만**(문서 해시에 doc_type이 든다 — 다른 종류의 것은 맞을 수 없다) ·
            # 개요는 늘(조건이 제목 계층 · 지시문 · 층 config라 같은 판이면 LLM 0)
            same = (reg.get(did) or {}).get("doc_type") in (None, self.doc_type)
            for d in ((EX.EXTRACT_DIR, od) if same else (od,)):
                for p in RH.named(d, did):
                    _copy(p, paths.mirror(p, self.home))
            sm = paths.struct_maps(f"{did}.json")
            if sm.exists():
                _copy(sm, paths.mirror(sm, self.home))
            # 같은 종류의 앞 리허설 산출 — 운영 사본 위에(그 종류로는 이것이 더 가깝다)
            for kind, d in ((RH.EXTRACT, EX.EXTRACT_DIR), (RH.OUTLINE, od)):
                for p in RH.named(RH.place(self.doc_type, did, kind), did):
                    _copy(p, paths.mirror(d / p.name, self.home))
            if RH.place(self.doc_type, did, RH.STRUCT).exists():
                _copy(RH.place(self.doc_type, did, RH.STRUCT), paths.mirror(sm, self.home))
            lp = RH.place(self.doc_type, did, RH.LEARNED)
            if lp.exists():
                self._merge_learned(_read_json(lp, {}))

    def _learned_path(self):
        return paths.mirror(store.path(store.COORD_LEARNED), self.home)

    def _merge_learned(self, add):
        book = _read_json(self._learned_path(), {})
        have = set(book.get("채택") or {}) | set(book.get("목록밖") or {})
        for sec in ("채택", "목록밖"):
            for k, v in (add.get(sec) or {}).items():
                if k not in have:
                    book.setdefault(sec, {})[k] = v
        self._write_learned(book)

    def _write_learned(self, d):
        store.atomic_write_bytes(self._learned_path(),
                                 (json.dumps(d, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))

    def _bind(self):
        """표본 파싱의 쓰기 자리 — 구조 지도 보존 · 좌표 학습을 임시 루트로(읽기는 그 사본에서)."""
        from parser import struct_map, tagger
        sm_dir = paths.mirror(paths.struct_maps(), self.home)
        struct_map.use_dir(lambda: sm_dir)
        tagger.use_learned(lambda: _read_json(self._learned_path(), {}), self._write_learned)

    # ------------------------------------------------------------ 추출(하위 프로세스)
    def env(self):
        """하위 프로세스 환경 — 지금 환경 그대로 + 상태 루트 = 임시 루트 + **부모가 읽은 설정 파일**(있으면)."""
        e = dict(os.environ)
        e[paths.HOME_ENV] = e[paths.MOCK_HOME_ENV] = str(self.home)
        cf = gateway.config_file()
        if cf:
            e[gateway.CONFIG_ENV] = os.path.abspath(cf)
        e["PYTHONUNBUFFERED"] = "1"
        return e

    def extract(self, envs, layer):
        """추출 — `cli.extract.run`을 임시 루트의 하위 프로세스가 돈다. 돌려주는 것은 결과(`OUT_FILE`) 또는 실패 dict."""
        ind = self.home / IN_DIR
        made = []
        for env in envs:
            p = ind / f"{env['doc_id']}.json"
            _write_json(p, env)
            made.append(str(p))
        man = ind / "manifest.json"
        _write_json(man, {"envelopes": made, "layer": layer, "out": str(self.home / OUT_FILE)})
        print(f"   ── 추출 리허설 — 하위 실행 · 아래 줄의 자리는 임시 상태 폴더 {paths.show(self.home)} 기준이다")
        proc = subprocess.Popen([sys.executable, "-m", "cli.register.rehearsal", str(man)], cwd=str(ROOT),
                                env=self.env(), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        try:
            for line in proc.stdout:                    # 같은 화면 · 같은 명령 로그(부모의 화면 복사가 받는다)
                print(line, end="", flush=True)
            rc = proc.wait()
        except BaseException:                           # Ctrl-C · 화면 닫힘 — 하위 프로세스를 멈추고 올린다
            self.failed = True
            _stop(proc)
            raise
        out = _read_json(self.home / OUT_FILE, None)
        if rc != 0 or out is None:
            self.failed = True
            return {"rc": rc}
        return out

    # ------------------------------------------------------------ 남기기
    def _save(self):
        """그 실행이 쓴 LLM 산출 → ④단 자리(문서마다 · 운영 사본과 같은 것은 빼고) · 좌표 학습은 새 표기만."""
        from core.state import rehearsal as RH
        now = _read_json(self._learned_path(), {})
        have = set(self.learned0.get("채택") or {}) | set(self.learned0.get("목록밖") or {})
        new = {sec: {k: v for k, v in (now.get(sec) or {}).items() if k not in have} for sec in ("채택", "목록밖")}
        for did in self.ids:
            got = RH.save(self.doc_type, did, self.home, learned=new, meta={"from": "register review"})
            if got:
                print(f"   리허설 산출 → {paths.show(RH.place(self.doc_type, did))} "
                      f"({' · '.join(f'{k}/{n}' if k else n for k, n in got)}) — {self.doc_type}로 인입할 때 쓴다"
                      f"(조건이 같으면 LLM 0)")


def _stop(proc):
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


def knobs_now():
    """파일에서 온 손잡이 값 `{이름: 값}` — 조건 대조의 재료(부모 · 하위 프로세스가 같은 함수)."""
    from core.state import knobs
    return {r["name"]: r["value"] for r in knobs.rows() if r["from"] == "file"}


# ---------------------------------------------------------------- 하위 프로세스 쪽
def main(argv):
    """임시 루트에서 — 추출(운영과 같은 함수) → 청크 · 체크포인트 요약을 결과 파일로."""
    from cli.extract import run as extract_run
    from core.build import extract as EX
    from core.build.ingest import ingest
    man = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    try:
        rc = extract_run(man["envelopes"], layer=man["layer"])
    except Exception as e:                    # noqa: BLE001 — 한 줄(파일:줄) · 부모가 「리허설 실패」로 받는다
        print("   " + log.defect(e, stage="추출 리허설(임시 상태 폴더)"))
        return 1
    out = {"rc": rc, "source": "mock" if gateway.use_mock() else "live", "home": str(paths.home()),
           "config_file": gateway.config_file(), "knobs": knobs_now(), "docs": {}}
    for p in man["envelopes"]:
        env = json.loads(Path(p).read_text(encoding="utf-8"))
        did = env["doc_id"]
        ch = store.read(store.CHUNKS, {"chunks": {}})["chunks"]
        if env.get("payload_kind") == "prose" and not any(c.get("doc_id") == did for c in ch.values()):
            ingest(env)                       # 재사용이면 추출 진입이 인입을 건너뛰었다 — 뷰의 본문은 이 루트의 청크에서
            ch = store.read(store.CHUNKS, {"chunks": {}})["chunks"]
        cp = (json.loads(EX.checkpoint_path(did).read_text(encoding="utf-8")) if EX.has_checkpoint(did) else None)
        out["docs"][did] = {"checkpoint": cp,
                            "chunks": {cid: {"section": c.get("section") or "", "text": (c.get("text") or "")[:60]}
                                       for cid, c in ch.items() if c.get("doc_id") == did}}
    _write_json(man["out"], out)
    return rc


if __name__ == "__main__":
    from cli import _entry
    sys.exit(_entry.main_module("cli.register.rehearsal", main))
