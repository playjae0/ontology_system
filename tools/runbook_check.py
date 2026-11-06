# -*- coding: utf-8 -*-
"""런북 「확인할 것」 대조 — 운영 런북의 화면 인용이 **지금 화면**인가를 mock 한 벌 실행으로 잰다 (B188 ②).

    python tools/runbook_check.py                     mock 한 벌 실행 → 대조 — 맞은 줄 n · 뺀 줄 m(표지별) · 없는 줄 목록
    python tools/runbook_check.py --runbook <파일>     다른 런북(바꾼 사본)을 같은 실행과 대조한다
    python tools/runbook_check.py --keep <파일>        실행 화면(단계마다 머리 `#### 단계 n · 명령`)을 파일로 남긴다
    python tools/runbook_check.py --screen <파일>      실행 대신 남긴 화면으로 대조한다(실행 0)

**한 벌 실행**(`SEQUENCE` — 런북의 칠 명령 그대로 · mock은 운영 명령에 `--allow-mock`): 빈 mock 상태 폴더(임시 · 레포 쓰기 0) →
`init`(층 seed `layers/`가 없으면 레포 seed 복사 — 런북 1의 「층 자산」) → 단계 0 `doctor` · `llm-check`(제 폴더) → 단계 1 `bootstrap --dry-run` · `bootstrap` ·
`export config` · `--json` 둘 → `--diff` · `skeleton-status` · `skeleton-confirm`(답 y) → 단계 3 표본 CP01 · PFMEA01을 `raw/`에 두고 `--dry-run` ·
`--step`(답 c) · `show report` → 단계 4 `ops review all`(비대화형 — 계획) · `platform queue`(전체 · `coord_mismatch`) · `show report --md` · `show learned` ·
`show summary` · `export config` 다시 —
`export config` 뒤에는 지도 `export/config_map.html`을 글 줄로 더한다(표 행 = 칸을 ` | `로 이은 한 줄 · 그림의 선 이름 한 줄씩).

**대조에 드는 줄** — `## n` 단계의 `**확인할 것**`부터 `**막히면**` 앞까지에서 ① 백틱 인용 중 화면 줄(빈칸이 있고 명령
(`python ` · `show ` · `ops ` …) · 옵션(`--`)으로 시작하지 않고 생략 표시 밖 글자가 있는 것) ② 그 안의 코드 울타리(```` ``` ```` — `bash` 울타리 밖)의 줄마다.
그 단계의 실행 화면(같은 단계 명령의 출력 전부)의 **한 줄** 안에 인용의 조각이 차례로 있으면 맞다 — `…` · `<자리>`는 생략
표시(앞뒤 조각만 본다) · 빈칸 여럿은 하나로 읽는다.

**뺀 줄 — 표지**(닫힌 목록 `MARKERS` · 모르는 표지는 rc 2): 글에 `〔표지〕`를 두면 그 자리부터 그 항목(`- ` 줄과 들여쓴 이음 ·
울타리 · 안쪽 항목) 끝까지의 인용을 대조에서 빼고 표지별로 센다(안쪽 항목의 표지는 그 안쪽 항목까지) · `**확인할 것**` 줄의 표지는 그 단계 전부.

종료 코드: 0 = 대조에 든 줄이 전부 실화면에 있다 · 1 = 없는 줄이 있다 · 2 = 못 돌았다(실행 실패 · 모르는 표지 · 런북 꼴).
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNBOOK = ROOT / "docs" / "가이드" / "운영_런북.md"

#: 표지 — 이 실행이 낼 수 없는 줄의 갈래(닫힌 목록)
MARKERS = {
    "실호출": "실호출(게이트웨이)에서만 보이는 줄",
    "사내": "사내 운영 상태 폴더의 줄(운영 루트 모양 연습 폴더 포함)",
    "산문": "산문 표본(RFQ01 · Word · 목차형 엑셀)의 줄 — 이 실행은 표 표본만 넣는다",
    "PPT": "PPT · PDF 표본의 줄",
    "다른 표본": "이 실행 밖 창작 표본(파일 이름이 다른 표본 · 따로 만든 표본)의 줄",
    "단계 밖": "이 실행이 치지 않는 명령의 줄(등록 · 회귀 · llm-check · relink · 질의 · 재구축 …)",
    "조건": "그 상황에서만 나오는 줄(멈춤 · 실패 · 경고 · 옛 config · 다른 층 config · 대장이 찬 상태 — 이 실행은 정상 한 벌)",
    "보기": "화면 줄이 아닌 인용(사람이 치는 답 · config 글 · 꼴 설명)",
}
#: 한 벌 실행 — `(단계, argv, pty 답)` · argv의 `{raw}`는 상태 폴더 `raw/` · `{home}`은 상태 폴더 · 답이 None이면 표준입력 없음
SEQUENCE = (
    (0, ("doctor.py",), None),
    (0, ("run.py", "llm-check"), None),
    (1, ("run.py", "bootstrap", "--dry-run"), None),
    (1, ("run.py", "bootstrap"), None),
    (1, ("run.py", "export", "config"), None),
    (1, ("run.py", "export", "config", "--json", "{home}/export/before.json"), None),
    (1, ("run.py", "export", "config", "--json", "{home}/export/after.json"), None),
    (1, ("run.py", "export", "config", "--diff", "{home}/export/before.json", "{home}/export/after.json"), None),
    (1, ("run.py", "skeleton-status", "process"), None),
    (1, ("run.py", "skeleton-confirm", "process", "--by", "연습"), "y\n"),
    (3, ("run.py", "ingest-file", "{raw}/CP01.xlsx", "--dry-run", "--allow-mock"), None),
    (3, ("run.py", "ingest-file", "{raw}/CP01.xlsx", "--step", "--allow-mock"), "c\n" * 20),
    (3, ("run.py", "ingest-file", "{raw}/PFMEA01.xlsx", "--doc-type", "pfmea", "--step", "--allow-mock"), "c\n" * 20),
    (3, ("run.py", "show", "report", "PFMEA01"), None),
    (4, ("run.py", "ops", "review", "all", "--actor", "연습"), None),
    (4, ("run.py", "platform", "queue"), None),
    (4, ("run.py", "platform", "queue", "coord_mismatch"), None),
    (4, ("run.py", "show", "report", "PFMEA01", "--md"), None),
    (4, ("run.py", "show", "learned"), None),
    (4, ("run.py", "show", "summary"), None),
    (4, ("run.py", "export", "config"), None),
)
SAMPLES = ("CP01.xlsx", "PFMEA01.xlsx")
#: 명령 · 옵션으로 시작하는 인용은 화면 줄이 아니다
COMMAND = re.compile(r"^(python |cp |export |cd |ls |\$|--|show |ops |platform |ingest-|rebuild|golden |vectors|bootstrap|skeleton-|"
                     r"init |register |llm-check|query )")
MARK = re.compile(r"〔([^〕]+)〕")
SPAN = re.compile(r"`([^`]+)`")
WILD = re.compile(r"…|<[^<>]*>")
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


# ---------------------------------------------------------------- 한 벌 실행
def _pty(cmd, env, answers):
    """pty로 돌린다(묻는 자리는 터미널에서만 산다) — 답을 먼저 넣고 끝까지 읽는다."""
    import pty
    pid, fd = pty.fork()
    if pid == 0:                                                     # pragma: no cover — 자식
        os.chdir(str(ROOT))
        os.execve(sys.executable, cmd, env)
    os.write(fd, answers.encode())
    out = b""
    try:
        while True:
            d = os.read(fd, 4096)
            if not d:
                break
            out += d
    except OSError:
        pass
    os.waitpid(pid, 0)
    return ANSI.sub("", out.decode("utf-8", "replace")).replace("\r", "")


def _root(prefix):
    """빈 mock 상태 폴더 하나 — `(임시 폴더, mock 루트, 하위 실행 환경)` · init · 층 seed · 표본 `raw/`."""
    from cli import doctor_run as DR
    tmp, home, env, _work = DR._temp_root(prefix, mock=True)
    env = dict(env, USE_MOCK="1")
    subprocess.run([sys.executable, str(ROOT / "run.py"), "init"], cwd=str(ROOT), env=env, capture_output=True,
                   stdin=subprocess.DEVNULL, check=True)
    if not (Path(home) / "layers").is_dir():                       # 층 자산 — init이 seed를 두지 않았으면 레포 seed
        shutil.copytree(ROOT / "layers", Path(home) / "layers", ignore=shutil.ignore_patterns("__pycache__"))
    raw = Path(home) / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    src = Path(env.get("ONTO_FIXTURES") or ROOT / "tests" / "fixtures") / "raw"
    for f in SAMPLES:
        shutil.copy2(src / f, raw / f)
    return tmp, raw, env


def run_sequence():
    """`SEQUENCE`를 친다 — `{단계: 화면 글}` · 단계 0(`doctor`)은 제 상태 폴더에서(점검의 미설치 모사가 mock 루트에 mock 세계를
    심는다 — 런북 0과 1 사이의 바닥이 갈린다) · 단계 1부터는 빈 상태 폴더 하나에서 이어 친다 · 임시 자리는 끝나면 지운다(레포 쓰기 0)."""
    sys.path.insert(0, str(ROOT))
    from core.llm import gateway
    gateway.isolate()
    screens, roots, tmps = {}, {}, []
    try:
        for step, argv, answers in SEQUENCE:
            key = step == 0
            if key not in roots:
                roots[key] = _root("onto_runbook_")
                tmps.append(roots[key][0])
            _tmp, raw, env = roots[key]
            cmd = [sys.executable, str(ROOT / argv[0]),
                   *(a.replace("{raw}", str(raw)).replace("{home}", str(raw.parent)) for a in argv[1:])]
            if answers is None:
                r = subprocess.run(cmd, cwd=str(ROOT), env=env, capture_output=True, text=True, stdin=subprocess.DEVNULL)
                out = r.stdout + r.stderr
            else:
                out = _pty(cmd, env, answers)
            screens[step] = screens.get(step, "") + f"#### 단계 {step} · {' '.join(argv)}\n{out}\n"
            if argv[1:] == ("export", "config"):                     # 지도는 그림 · 표로 본다 — HTML을 글 줄로
                page = raw.parent / "export" / "config_map.html"
                screens[step] += f"#### 단계 {step} · 지도 export/config_map.html\n{html_lines(page)}\n"
    finally:
        for t in tmps:
            shutil.rmtree(t, ignore_errors=True)
    return screens


def html_lines(path):
    """지도 HTML → 글 줄 — 표 행은 칸을 ` | `로 이은 한 줄 · 그림의 선 이름(`<text>`) · 문단 · 머리는 한 줄씩(사람이 보는 그대로)."""
    import html as H
    t = Path(path).read_text(encoding="utf-8") if Path(path).is_file() else ""
    t = re.sub(r"<style.*?</style>", "", t, flags=re.S)
    t = re.sub(r"</t[dh]>", " | ", t)
    t = re.sub(r"</(tr|p|h[1-6]|text|div|dt|dd|li)>|<br\s*/?>", "\n", t)
    t = H.unescape(re.sub(r"<[^>]+>", "", t))
    return "\n".join(ln.strip().rstrip("|").strip() for ln in t.splitlines() if ln.strip())


def read_screen(path):
    """`--keep`이 남긴 화면 파일 → `{단계: 글}`."""
    screens, step = {}, None
    for ln in Path(path).read_text(encoding="utf-8").splitlines(keepends=True):
        m = re.match(r"#### 단계 (\d+) · ", ln)
        if m:
            step = int(m.group(1))
        if step is not None:
            screens[step] = screens.get(step, "") + ln
    return screens


# ---------------------------------------------------------------- 런북의 인용
def _flat(s):
    return re.sub(r"\s+", " ", s).strip()


def quotes(text):
    """런북 글 → 인용 `[(단계, 줄 번호, 인용, 표지 또는 None)]` — 「확인할 것」 자리만 · 모르는 표지는 ValueError."""
    out, step, inside, region_mark, mark, fence, stack = [], None, False, None, None, None, []
    for no, ln in enumerate(text.splitlines(), 1):
        h = re.match(r"## (\d+) ", ln)
        if h:
            step, inside, fence = int(h.group(1)), False, None
            continue
        if step is None:
            continue
        if fence is not None:                                        # 울타리 안
            if ln.strip().startswith("```"):
                fence = None
            elif fence != "bash" and ln.strip():
                out.append((step, no, ln.strip(), mark))
            continue
        if ln.startswith("**확인할 것**"):
            inside, region_mark, stack = True, None, []
            mark = region_mark = _mark(ln, None, ln)
            continue
        if ln.startswith("**막히면**") or ln.startswith("---") or ln.startswith("## "):
            inside = False
            continue
        if not inside:
            continue
        if ln.strip().startswith("```"):
            fence = ln.strip()[3:].strip() or "text"
            continue
        b = re.match(r"( *)- ", ln)
        if b or (ln.strip() and not ln.startswith(" ")):            # 새 항목 — 표지는 바깥 항목(없으면 그 단계)의 것으로
            depth = len(b.group(1)) if b else -1
            while stack and stack[-1][0] >= depth:
                stack.pop()
            mark = stack[-1][1] if stack else region_mark
            if b:
                stack.append([depth, mark])
        for piece in re.split(r"(〔[^〕]+〕)", ln):
            if MARK.fullmatch(piece):
                mark = _mark(piece, mark, ln)
                if stack:
                    stack[-1][1] = mark
                continue
            for s in SPAN.findall(piece):
                if " " in s.strip() and not COMMAND.match(s.strip()) and re.search(r"\w", WILD.sub("", s)):
                    out.append((step, no, s, mark))
    return out


def _mark(piece, cur, ln):
    m = MARK.search(piece)
    if not m:
        return cur
    if m.group(1) not in MARKERS:
        raise ValueError(f"모르는 표지 〔{m.group(1)}〕 — 닫힌 목록 {list(MARKERS)} · {ln.strip()[:60]}")
    return m.group(1)


def found(quote, screen_lines):
    """인용이 화면의 한 줄에 있나 — `…` · `<자리>`는 생략(앞뒤 조각이 그 줄에 차례로)."""
    parts = [p.strip() for p in WILD.split(_flat(quote)) if p.strip()]
    for ln in screen_lines:
        at = 0
        for p in parts:
            i = ln.find(p, at)
            if i < 0:
                break
            at = i + len(p)
        else:
            return True
    return False


def check(text, screens):
    """대조 — `{"ok": [...], "missing": [...], "excluded": Counter(표지), "steps": {단계: (맞음, 대조)}}`."""
    flat = {s: [_flat(ln) for ln in t.splitlines() if ln.strip()] for s, t in screens.items()}
    res = {"ok": [], "missing": [], "excluded": Counter(), "steps": {}}
    for step, no, q, mark in quotes(text):
        if mark:
            res["excluded"][mark] += 1
            continue
        hit = found(q, flat.get(step, []))
        res["ok" if hit else "missing"].append((step, no, q))
        ok, n = res["steps"].get(step, (0, 0))
        res["steps"][step] = (ok + hit, n + 1)
    return res


def report(res):
    """화면 줄 — 머리 한 줄 · 단계마다 · 표지마다 · 없는 줄."""
    n, ok = len(res["ok"]) + len(res["missing"]), len(res["ok"])
    m = sum(res["excluded"].values())
    out = [f"[runbook] 「확인할 것」 대조 — 대조 {n} · 맞음 {ok} · 없음 {n - ok} · 뺀 줄 {m}"
           + ("(" + " · ".join(f"{k} {v}" for k, v in sorted(res["excluded"].items())) + ")" if m else "")]
    out.append("  단계마다 — " + " · ".join(f"{s} {a}/{b}" for s, (a, b) in sorted(res["steps"].items())))
    for step, no, q in res["missing"]:
        out.append(f"  없음 — 단계 {step} · 런북 {no}행 · {q[:110]}")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="런북 「확인할 것」 대조 (B188 ②)")
    ap.add_argument("--runbook", default=str(RUNBOOK))
    ap.add_argument("--keep")
    ap.add_argument("--screen")
    a = ap.parse_args(argv)
    try:
        text = Path(a.runbook).read_text(encoding="utf-8")
        quotes(text)
        screens = read_screen(a.screen) if a.screen else run_sequence()
    except (ValueError, OSError, subprocess.CalledProcessError) as e:
        print(f"[runbook] 못 돌았다 — {e}")
        return 2
    if a.keep:
        Path(a.keep).write_text("".join(screens[s] for s in sorted(screens)), encoding="utf-8")
    res = check(text, screens)
    for ln in report(res):
        print(ln)
    return 1 if res["missing"] else 0


if __name__ == "__main__":
    sys.exit(main())
