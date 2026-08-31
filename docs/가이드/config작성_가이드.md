# config 작성 가이드 — 새 층을 세울 때 사람이 실제로 쓰는 것

> **결론 먼저**: config 문법 키는 **19종이 합집합**이고 — 한 층이 전부 갖지 않는다(실물: 공정층 **18종** · 품질층 **16종**) — 그중 **사람이 실제로 쓰는 것은 11종**이며, 그중 **절반은 비워도 돈다**(품질층 실물이 증거 — `canonical_scope`·`polarity`·`skeleton_version` 없이 돈다). 나머지 8종은 베끼거나 자동으로 따라온다.
> **골격 가이드와 짝이다** — 골격을 먼저 심으면 3종이 따라오고, 이 가이드는 그다음이다.
> 실물 예시는 전부 `layers/process/config.json`에서 그대로 가져왔다 — **자산이 정본이다.**

## -1. 먼저 — 자산의 두 축과 LLM 생성 경로 두 개

**config가 자산의 전부가 아니다.** 자산은 두 축으로 산다:

```
층 축 — 층마다 1벌                    doc_type 축 — 문서 종류마다 1쌍
├ layers/{층}/config.json  ← 이 가이드   ├ adapters/{doc_type}.py   (파싱 어댑터)
└ layers/{층}/skeleton.json ← 골격 가이드  └ schemas/{doc_type}.json  (매칭 스키마 — role 번역표)
  (skeleton은 source 쓰는 층만)
```

**role 매칭은 이 가이드에 없다 — `schemas/{doc_type}.json`의 몫이다.** 층 config는 층의 어휘·규칙(카테고리·관계·확장)을 정하고, 매칭 스키마는 **한 문서 종류의 열을 그 어휘로 번역**한다(`"설비": {"role": "entity", "category": "Unit"}`). 같은 층에 CP·PFMEA가 각자 스키마를 갖는다.

**LLM 생성 경로는 둘이고, 하나는 이미 완성돼 있다:**

| 경로 | 만드는 것 | 도구 | 상태 |
|---|---|---|---|
| **① 구축 모드** (doc_type 등록 — 문서 6 §6.5~6.7) | 어댑터 + 매칭 스키마 쌍 | **`kit/` 6종 — 이미 실물** (생성프롬프트 v0.4 · 스켈레톤 · 실행 하네스 · 검수 뷰). 3차 블라인드 통과 | ✅ 새로 만들 것 없음 — 표본 넣고 검수·승인 1회 |
| **② 층 등록** (문서 3 §3.7) | 층 config + 골격 | 골격 가이드 + **이 가이드**의 초안 절차 | 수동+LLM 초안 (R1 도구는 셋째 층 트리거) |

**즉 사내에서 새 문서 종류를 붙일 때는 이 가이드가 아니라 ①번이다** — `python -m cli.register generate <doc_type> <층> <표본>` → 검수 뷰 → 승인. 이 가이드는 **새 층을 세울 때만** 쓴다.

## 0. 19종의 실제 부담 분류

| 분류 | 키 | 작성법 |
|---|---|---|
| **베낀다 (2)** | `match_threshold` `query_intents` | 두 층이 완전 동일 — 기존 층 것을 복사 |
| **한 줄 (3)** | `layer` `config_version` `registration` | 이름표 — `"quality"` · `"quality-1"` · `"registered"` |
| **골격에서 따라옴 (3)** | `skeleton` `skeleton_version` `polarity` | 골격 가이드의 산출. 극성 없는 층은 뒤 둘 생략 |
| **사람이 쓴다 (11)** | 아래 §1~§6 | **이 가이드의 본문** |

> **19종은 합집합이다.** 실물은 공정층 18종·품질층 16종이고, **`_`로 시작하는 주석 키**(공정층 4·품질층 2)는 일람 **밖**이라 loader가 무시한다 — 세지 않는다.

## 1. 카테고리 — 층의 첫 작업 (§3.1 규약 2)

**`categories`** — 닫힌 목록 + 정의문. **정의문 규격: "무엇인가"만이 아니라 "무엇과 헷갈리는가"를 담는다.** **정의문은 5요소로 쓴다 — ①핵심 정의 한 문장 ②실물 예시 5~10(골격·문서에 실재하는 이름만) ③헷갈림 규칙 3~5(「X처럼 보이지만 Y다」) ④열 이름 패턴 ⑤이 카테고리가 아닌 것. 정의문이 곧 판정 프롬프트다 — 교과서 문장이면 판정도 교과서 수준이 된다(실측). 초안은 `정의문보강_프롬프트.md`로 사내 LLM에서 뽑고 사람이 골격 대조 후 확정.**

```json
"categories": {
  "Process": "제품을 만들기 위해 수행하는 작업 단계. 기능으로 정의되며 설비 기종이
              바뀌어도 존재한다(예: 노칭). 설비 이름이 아니라 '하는 일'의 이름.",
  "Unit":    "공정을 수행하는 물리 장비의 기종/표준 명칭(예: 노칭 프레스).
              지그·금형 등 도구류 포함. 호기·특정 공장 개체는 제외.",
  "Property":"공정/설비에서 관리·측정·통제되는 항목의 이름(예: 노칭 정밀도).
              규격값·측정값·판정결과는 제외 — 그것은 attribute."
}
```

**이 정의문이 그대로 추출·판정 LLM의 프롬프트에 주입된다** — 정의의 경계 서술이 오분류를 거른다. 카테고리 후보마다 **그래프 입주 3테스트**(§3.7)를 통과해야 한다: ①이름이 있어 다른 문서가 같은 것을 가리킬 수 있나 ②다른 정보로 가는 경유지가 되나(아니면 attribute) ③개수가 문서 비례인가 시간 비례인가(시간 비례면 T3 참조).

## 2. 관계 — 이름·패턴·방향 (한 묶음으로 쓴다)

```json
"relations": ["part_of", "precedes", "has_property", "mirrors"],

"relation_patterns": [
  {"src": "Unit",    "rel": "part_of",      "dst": "Process",
   "symmetric": false, "정의문": "설비가 그 공정에 속한다"},
  {"src": "Process", "rel": "has_property", "dst": "Property",
   "symmetric": false, "정의문": "공정이 그 관리항목을 갖는다"}
],

"category_pair_map": {
  "Unit,Process": "part_of", "Process,Property": "has_property"
}
```

| 키 | 규칙 |
|---|---|
| `relations` | **이름 배열일 뿐** — 대칭 표시를 여기 심지 않는다(게이트가 못 읽는다 · §3.1 규약 4) |
| `relation_patterns` | 게이트가 대조하는 **삼항 표.** 정의문 없는 관계를 올리지 않는다. **골격 삼항(`Process part_of Process` 등)은 넣지 않되 `Unit part_of Process`는 넣는다** — 이름 단위로 빼면 설비 부착이 죽는다(D-52 실측) |
| `category_pair_map` | 이종 쌍의 방향 함의. **동종 쌍은 여기로 방향을 못 정한다** — seed·edges 선언만 |

## 3. 질의 확장 — `query_traverse` (형태 주의: 3단 중첩)

```json
"query_traverse": {
  "part_of":      { "down": {"direction": "in",  "recursive": true },
                    "up":   {"direction": "out", "recursive": false} },
  "has_property": { "both": {"direction": "both","recursive": false} }
}
```

**관계 → 규칙이름 → `{direction, recursive}` 3단이다** — 1단으로 쓰면 순회기가 키를 못 찾는다(모순-30 실측). `recursive: false`는 "같은 관계를 연달아 재추적하지 않음"일 뿐 — 다른 관계로 도달한 노드에는 적용된다(2홉의 근거). **`precedes`는 넣지 않는다** — 쓰기에서 seed로 심기지만 읽기 확장에서는 제외(§3.1 규약 1).

## 4. 층간 브리지 — `cross_layer_traverse` (선언층에만)

```json
"cross_layer_traverse": {
  "occurs_in":     {"direction": "both", "recursive": false},
  "controlled_by": {"direction": "both", "recursive": false}
}
```

**cross 엣지를 생성·저장하는 층(가리키는 층)에만 선언한다** — 공정층에는 없는 것이 정상이다. **1단 dict**다(3단 아님 — 브리지는 1홉·비재귀라 관계당 규칙 하나). 키가 없거나 비면 그 층으로의 브리지는 꺼진 것.

## 5. 이름·문장화 — `canonical_scope` · `mirrors` · `fact_templates`

```json
"canonical_scope": {"bind_categories": ["Property"], "sep": "::"},
"mirrors":         {"enabled": true, "relation": "mirrors"},
"fact_templates": {
  "part_of":       "{src}는 {dst}의 하위 요소이다",
  "has_property":  "{src}의 관리인자: {dst}",
  "attr:spec":     "{node}의 규격: {value} (출처: {prov})"
}
```

`canonical_scope.bind_categories` — 어느 카테고리에 좌표 스코프(`노칭::노칭 정밀도`)를 붙이나. **B14의 판정 기준이 이 키다**(좌표가 canonical에 들어가는 카테고리는 좌표 미해소 시 노드를 만들지 않는다). `fact_templates` — 질의 답변의 문장 틀. **템플릿 없는 관계는 답변에 문장으로 나오지 못한다.**

## 6. 추출·판정 프롬프트 — `extract_patterns` · `prompts`

```json
"extract_patterns": [],
"prompts": {"extract": "…", "judge": "…"}
```

`prompts`의 실물은 **파일이 정본**이다(§7.6-B-5 — P-D에서 파일화 완료). config에는 지시 요지만 남는다. `extract_patterns`는 USE_MOCK 문형 규칙 — 실 연결 후에는 프롬프트가 대신한다.

## 7. LLM 초안 절차 — 층 등록 세션의 축소판

골격과 같은 원리다: **초안은 LLM, 확정은 사람** (§3.7). 순서가 중요하다 —

```
1. 카테고리 먼저 — 층 설명 1문단 + 표본 문서를 주고 categories 초안
   → 후보마다 3테스트 판정표 → 사람 확정      ★ 이게 끝나기 전에 다음으로 가지 않는다
2. 관계 묶음 — 확정된 카테고리를 주고 relations/patterns/pair_map 초안
   → 정의문 있는지·골격 삼항 뺐는지 확인 → 사람 확정
3. 나머지 — traverse·templates·scope는 기존 층을 베이스로 이름만 수정
4. 검증 — python3 run.py init --fresh && run.py all
   → 부팅 실패 = config 문법 오류 (명시적 실패가 어느 키인지 말해 준다)
   → 점검_자산.py — 명세·자산 대조
```

### 초안 프롬프트 — **실물 파일을 함께 붙인다**

**양식을 프롬프트에 베껴 쓰지 않는다.** 자산이 정본이므로(README 「복제 금지」), 기존 층의 **실물 파일을 그대로 첨부**하고 그 구조를 따르게 한다. 프롬프트에 양식을 적으면 자산과 어긋나는 순간 프롬프트가 자산을 이기게 되고, 그것이 이미 세 번 실측된 실패다.

**붙일 것 넷** (전부 레포에 있다):

| # | 파일 | 왜 |
|---|---|---|
| 1 | `layers/process/config.json` (5.9KB) | **양식 그 자체** — 문법 키 18종 + 주석 키 4종의 실제 형태 |
| 2 | `layers/quality/config.json` (4.6KB · 문법 키 16종) | **두 번째 예** — 무엇이 층마다 다르고 무엇이 같은지 보인다. 그리고 **비워도 되는 키**(canonical_scope·polarity·skeleton_version 없음)를 실물로 보여준다 |
| 3 | 새 층의 **골격 seed** (이미 만든 것) | 카테고리·관계가 골격과 맞아야 한다 |
| 4 | 새 층의 **대표 문서 1~2부** | 무엇을 담는 층인지의 실체 |

```
당신은 지식 그래프 층의 config.json을 만든다. 출력은 JSON 하나뿐이다.

[첨부] ①기존 공정층 config.json ②기존 품질층 config.json
       ③이 층의 골격 seed ④이 층의 대표 문서

[출력] 새 층의 config.json — **첨부 ①의 키 구조를 그대로 따른다.**
       ②를 보면 어느 키를 비워도 되는지 알 수 있다(그 층에 없는 키가 답이다).

[먼저 할 것 — 카테고리]
categories를 먼저 확정한다. 2~5종이 정상이고, 많으면 잘못 갈랐다.
- 정의문은 "무엇인가" + **"무엇과 헷갈리는가"(제외 서술)**를 반드시 담는다.
  첨부 ①의 Property 정의문이 그 본보기다("규격값·측정값·판정결과는 제외").
- 후보마다 자문한다: ①이름으로 지칭 가능한가 ②다른 정보로 가는 경유지인가
  ③개수가 문서 비례인가 — **시간 비례(측정값·로그)면 카테고리가 아니다.**
- 값·수치·판정결과는 카테고리가 아니다 — attribute다.

[그다음 — 관계 묶음]
relations · relation_patterns · category_pair_map을 **한 묶음으로** 만든다.
- relations는 **이름 배열일 뿐**이다. 대칭 표시를 여기 심지 않는다.
- relation_patterns의 각 항목에 **정의문을 병기**한다 — 정의문 없는 관계는 올리지 않는다.
- **골격 소유 관계의 삼항**(Process part_of Process 등)은 패턴표에 넣지 않는다.
  단 Unit part_of Process는 넣는다 — 이름 단위로 빼면 설비 부착이 죽는다.

[나머지]
query_traverse · fact_templates · canonical_scope 등은 첨부 ①②를 베이스로
이 층의 카테고리·관계 이름으로만 바꾼다. **구조는 바꾸지 않는다.**
query_traverse는 관계→규칙이름→{direction,recursive}의 **3단 중첩**이다.

[규율]
- 첨부에 없는 키를 만들지 않는다. 19종이 전부다.
- 판단이 갈린 자리는 JSON 뒤 "확인 필요:"에 적는다. 추측으로 채우지 않는다.
```

**확정 절차**: 출력을 `layers/{층}/config.json`으로 저장 → `python run.py init --fresh && python run.py all` → 부팅 실패면 **명시적 실패가 어느 키인지 말해 준다** → 통과하면 `점검_자산.py`로 명세·자산 대조.

## 8. R1 도구 판단 — 결론: 지금은 만들지 않는다

이 가이드가 있으면 **층 하나는 손 + LLM 초안으로 하루 안**이다(품질층 실물 config가 18키·3KB). R1 도구(층 등록 6단계 자동화)가 값을 하는 시점은 **셋째 층부터**다 — Rule of Three(B5)의 그 기준 그대로. 2B는 공정층·품질층 두 층으로 시작하므로 **R1은 트리거 미도달**. 미결 등록부의 자리 그대로 둔다.
