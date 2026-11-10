# 층 config 팩 — `layers/<층>/config.json` (+ 공통 config에 더할 줄 제안)

> **사람**: 이 폴더의 다섯 파일(`층config_팩.md` · 예시 넷)과 함께 ①그 층의 대표 문서 1 ~ 2부 ②골격 층이면 골격 팩으로 받은 `skeleton.json`(확정은 이 config를 놓고 `bootstrap`한 뒤 — 「받은 뒤 확인」) ③이미 세운 층이 있으면 지금 `$ONTO_HOME/layers/common.json`과 그 층들의 `config.json`을 사내 LLM에 넘긴다. **한 번에 한 층** — 골격 층(설비층)부터. 받은 뒤는 맨 끝 「받은 뒤 확인」.

## 1. 할 일

당신은 지식 그래프의 **층 하나**의 config.json을 만든다. 출력은 셋이다.

1. `config.json` — JSON 하나. 키 구조는 예시를 따른다.
2. **「공통 config에 더할 줄」** — 아래 §10의 칸만 · JSON 조각 하나.
3. **「확인 필요:」 목록** — 판단이 갈린 자리마다 한 줄(키 · 왜 갈리는지).

## 2. 원칙 — 층의 결정은 그 층 config에

- 시스템 규칙은 카테고리 이름을 모른다. **층마다 다른 선택**(어느 카테고리를 쓰나 · 어느 관계를 허용하나 · 극성을 어디에 묶나)은 그 층 config의 키나 `_<키>_note` 주석에 적는다.
- 그 층에서만 맞는 예시(「이 층에서는 ○○이 △△의 소속이다」)는 **층 힌트 `prompts.<자리>`**에 적는다 — 시스템 지시문에 넣지 않는다.
- 예시 넷의 이름(공정 · 유닛 · 부품 · 불량)은 **지은 것**이라 출력의 근거가 아니다 — 이름은 첨부 문서 · 골격에서만 온다(첨부에 같은 이름이 있으면 첨부를 근거로 쓴다). 예시에서는 키 구조와 값의 꼴만 따른다.

## 3. 사내 층 모델 — 예시가 보이는 모양

| 층(예시 폴더 이름) | home 카테고리(정의문을 이 층이 쓴다) | `uses`(이름만) | 극성 |
|---|---|---|---|
| 설비층 `equipment` — **골격 층** | `Process`(골격) · `Unit` · `Component` | `Property`(설비 문서가 사양 항목의 이름을 말할 때) | `Unit` · `Component` |
| 공정층 `process` | `Property` | `Process` · `Unit` · `Component` | `Property` |
| 품질층 `quality` | `Failure` · `FailureEffect`(닫힌 목록) | `Process` · `Unit` · `Property` | 없음 |

- **같은 이름이면 층이 달라도 노드 하나**다. 정의문은 그 카테고리의 home 층 한 곳에만 쓰고, 다른 층은 `uses`에 이름만 적는다.
- 골격 카테고리(`Process`)는 골격 층만 선언한다. 다른 층 문서의 공정 이름은 개체가 아니라 **좌표**다(표의 상위 공정 열 → `process_group` · 하위 공정 열 → `process_ref` — 열 이름이 무엇이든).

## 4. 키 — 아는 키 19개 밖은 거부된다

이 19개와 `_`로 시작하는 주석 키 밖의 키는 `bootstrap`이 「모르는 키」로 거부한다.

| 키 | 필수 | 꼴 · 규칙 |
|---|---|---|
| `layer` | 필수 | 폴더 이름과 같은 글 — **첫 인입 전에 정한다**(바꾸면 그 층 그래프를 다시 쌓는다) · 이미 세운 층의 config를 다시 쓸 때는 폴더 이름을 그대로 둔다(등록한 문서 종류가 그 층 이름을 가리킨다) |
| `config_version` | 선택 | 기록용 글(`"<층>-1"`) |
| `registration` | 선택 | `"builtin"`(골격 층) · `"registered"`(나머지) |
| `categories` | 필수 | `{카테고리: 정의문}` — home이 이 층인 것만(§5) |
| `uses` | 다른 층 카테고리를 쓰면 필수 | 이름 목록(골격 카테고리 포함) |
| `relations` | 필수 | 관계 이름 목록(§6) |
| `relation_patterns` | 필수 | 삼항 목록(§6) |
| `skeleton` | 골격 층 · 닫힌 목록을 가진 층 | §8 |
| `skeleton_version` | 골격 층만 | 기록용 글(`"<층>-1"`) |
| `polarity` | 극성을 묶는 층만 | §7 |
| `mirrors` | 선택 | `{"enabled": true\|false, "relation": "mirrors"}` |
| `query_traverse` | 선택 | 3단(§9) |
| `cross_layer_traverse` | 다른 층으로 가는 엣지를 만드는 층만 | 1단(§9) |
| `fact_templates` | 선택 | 관계마다 문장 틀(§9) |
| `query_intents` | 선택 | 예시 그대로 베낀다 |
| `prompts` | 선택 | 층 힌트(§11) |
| `extract_patterns` | 선택 | `[]` |
| `relevance_terms` | 선택 | 노드 이름이 아니라 **그 층 문서를 알아보게 하는 문서 단어**(사양서 · 도면 · Spec — 두 언어면 둘 다) · 모르면 뺀다(사전 어휘만 본다) |
| `value_categories` | 선택 | `{"<카테고리>": "<값을 싣는 속성 이름>"}` — 그 층의 **산문**이 값(「권취 속도 1.2 m/s」의 `1.2 m/s`)을 말할 때만 · **키는 이 층의 home 카테고리만**(`uses`의 카테고리는 안 된다 — `bootstrap`이 멈춘다) · 속성 이름은 표 규격 이름(`spec`)과 다르게(예: `설비사양`) · 사양 값이 담긴 설비 문서는 사양 항목의 home 층(사내 모델에서는 공정층)에 등록해야 값이 실린다 |

표의 열 → 속성 이름(규격 · 측정방법 같은 것)은 층 config가 아니라 **문서 종류 등록(스키마)**이 정한다 — 이 팩 밖이다. 문서를 어느 층에 등록할지도 등록 때 사람이 정한다(`python -m cli.register generate <doc_type> <층> <표본>`).

## 5. 카테고리와 정의문

- **카테고리는 2 ~ 5개**가 정상이다. 후보마다 묻는다: ①이름으로 다른 문서가 같은 것을 가리킬 수 있나 ②다른 정보로 가는 경유지인가 ③개수가 문서 수에 비례하나 — **시간에 비례하면(측정값 · 로그 · 건수) 카테고리가 아니다.** 값 · 수치 · 판정결과는 카테고리가 아니라 attribute다.
- **같은 뜻이면 이미 있는 이름**을 쓴다(첨부한 `common.json`의 카테고리) — 다른 이름으로 선언하면 두 종류로 갈려 층 사이가 끊긴다.
- **정의문은 판정 규칙이다** — 추출 · 판정 LLM이 그대로 읽는다. 한 카테고리에 ①무엇인가(그래프에서 노드인가 · 무엇에 매달리나) ②실물 예 3 ~ 5(첨부 문서 · 골격에 실재하는 이름만) ③경계 — 이웃 카테고리마다 「X처럼 보이지만 Y다」 판별 하나 ④아닌 것(이웃을 이름으로)을 담는다. 「대체로」보다 「X면 Y다, 단 Z는 예외」로 쓴다.
- 공정층 `Property` 정의문에는 「공정 · 설비 단위의 이름은 제외 — 그것은 좌표」를 넣는다.
- 골격 노드를 겸하는 카테고리(`Unit` — 골격의 상위 · 하위 공정은 Unit이기도 하다)는 정의문에 「골격의 공정 · unit 이름이나 그 별칭이면 그 공정 자신으로 풀린다」를 넣고, 예로 골격의 unit 이름을 써도 된다. 정의문은 「무엇인가」(설비 · 유닛의 이름)로 시작한다 — 「골격에 없는 것」으로 정의하지 않는다(판정 LLM이 보는 골격 이름은 그 청크 좌표 아래 일부뿐이다).

## 6. 관계 — 한 묶음으로 쓴다

- `relations` — **이름 목록일 뿐**이다(대칭 표시를 넣지 않는다). 이 층 문서의 엣지가 쓰는 관계 이름을 전부 적는다(공통 `parent_pairs`의 관계 이름 포함 — 예: 공정층의 `part_of`).
- `relation_patterns` — 게이트가 대조하는 삼항 `{"src", "rel", "dst", "symmetric": true|false, "정의문"}`. **삼항마다 정의문**을 적는다. 삼항의 카테고리는 전부 이 층의 `categories` ∪ `uses` 안에 있어야 한다(아니면 거부).
- 적지 않는 삼항 둘: **골격 삼항**(`Process part_of Process` · `Process precedes Process` — 골격이 소유한다) · **공통 `parent_pairs`의 삼항**(게이트가 더한다).
- 이 층 config에 없는 삼항은 게이트가 버린다 — 가장 자주 빠지는 자리다.

## 7. 극성 — 그 카테고리의 home 층에

- `polarity`는 `{"bind_categories": [카테고리…], "values": [축값…]}`이다.
- **결합 규칙은 그 카테고리의 home 층 config만 본다** — 문서가 어느 층이든 같다. 다른 층 config에 같은 카테고리를 묶어도 효과가 없고 `bootstrap`이 경고한다.
- `values`는 골격 `AXIS_LABELS`의 키와 같고 **모든 층이 같다**. 극성을 묶지 않는 층은 `polarity`를 뺀다.
- `values`는 **골격 층 config의 `polarity.values`를 그대로 옮긴다**(= 골격 `AXIS_LABELS`의 키).
- 극성이 갈리는 카테고리는 같은 층에 `mirrors` 삼항(`{"src": X, "rel": "mirrors", "dst": X, "symmetric": true}`)과 `"mirrors": {"enabled": true, "relation": "mirrors"}`를 둔다 — 골격 카테고리(`Process`)는 뺀다: 골격의 극성 짝은 골격이 만든다(골격 삼항은 패턴에 적지 않는다 — §6).

## 8. 골격 · 닫힌 목록

- **골격 층**: `"skeleton": {"type": "tree-v3.2", "category": "Process", "source": "skeleton.json", "relations": {"child": "part_of", "sibling": "precedes"}}` · `"skeleton_version": "<층>-1"` · `"registration": "builtin"`. 트리는 골격 팩으로 만든다.
- **닫힌 목록을 가진 층**(품질층의 영향 분류): `"skeleton": {"type": "flat", "category": "<카테고리>", "data": [이름…]}` — 파일 없이 config 안에. 목록 밖 이름은 노드가 되지 않는다.
- 골격 카테고리는 한 층만 가진다 — 두 층의 골격이 같은 카테고리면 `bootstrap`이 멈춘다.

## 9. 질의 칸

- `query_traverse` — **3단**: `{관계: {규칙 이름: {"direction": "out"|"in"|"both", "recursive": true|false}}}`. `direction`은 이 셋뿐이다. `precedes`는 넣지 않는다.
- `cross_layer_traverse` — **1단**: `{관계: {"direction", "recursive"}}`. 다른 층 노드로 가는 엣지를 **만드는 층에만** 둔다(품질층의 `occurs_in` · `controlled_by`). 없으면 그 다리는 꺼진 것이다.
- `fact_templates` — 관계마다 `"{src} … {dst} …"` 문장 틀. 틀이 없는 관계는 답에 문장으로 나오지 못한다. **같은 관계의 틀은 층마다 같게** 쓴다. 값의 틀 `"attr:<속성>": "{node}의 …: {value} (출처: {prov})"`은 속성 이름을 알 때만(표 규격 `spec` · 이 층 `value_categories`의 이름) — 모르면 두지 않고 문서 종류를 등록한 뒤 더한다.

## 10. 공통 config에 더할 줄 — 제안만 한다

공통 config(`layers/common.json`)는 층 config가 아니다. `home` · `used_by` · `common_version`은 `bootstrap`이 쓴다 — **제안하지 않는다.** 사람이 쓰는 칸만 제안한다(꼴은 `common_사람줄_예시.json`).

| 칸 | 언제 |
|---|---|
| `categories.Process.also` | 골격 층 — 설비이기도 한 단: `{"Unit": ["sub", "detail"]}`(상위 · 하위 공정) |
| `categories.<카테고리>.no_path` | 여러 공정이 함께 쓰는 공용 분류만 — 값은 사유 한 줄(골격 카테고리 · 닫힌 목록 카테고리는 적지 않는다). 적지 않으면 이름에 그 행 · 청크의 좌표(공정)가 붙는다(`<공정>::<이름>` — `parent_pairs`가 없어도 붙는다 · 소속이 골격 밖 노드면 그 아래) |
| `parent_pairs` | 다른 카테고리 사이의 소속 `{"lower", "upper", "rel", "src": "lower"\|"upper", "정의문"}` — `src`는 엣지가 떠나는 끝. 위가 골격이 아닌 노드면 아래 이름이 그 아래로 선다(`<공정>::<유닛>::<부품>`) |
| `null_markers` | 선택 — 빈 값으로 읽을 표기 목록(「-」 · 「N/A」 · 「해당 없음」) |
| `sep` | `"::"` 그대로 — 바꾸지 않는다 |

겸 노드(골격 unit — Process이자 Unit)에서는 `Component → Process`와 `Component → Unit`처럼 두 쌍이 함께 맞을 수 있다 — 관계가 같으면 엣지는 하나다. 같은 아래 · 위 사이에 관계를 다르게 두지 않는다.

## 11. 층 힌트 `prompts`

- 자리는 넷: `structure`(목차 노드화) · `extract`(추출) · `reinforce`(연결 보강) · `judge`(같은지 판단). 시스템 지시문 끝에 「## 층 어휘 — <층>」으로 붙는다.
- 내용은 **이 층의 지식**만 — 이 층에서 어떤 항목이 어떤 카테고리인가 · 소속을 어디서 찾는가. 글 읽는 법(번호 줄 · 들여쓰기)은 넣지 않는다.
- 비우면 지시문 그대로 돈다.

## 12. 연결 점검 일곱 — 출력 전에 스스로 확인한다

1. 이 층이 쓰는 다른 층 카테고리(골격 카테고리 포함)가 전부 `uses`에 있다.
2. 정의문은 home이 이 층인 카테고리만 · 골격 카테고리는 골격 층만 선언했다.
3. `relation_patterns`의 카테고리가 전부 `categories` ∪ `uses` 안에 있고, 삼항마다 정의문이 있다.
4. 골격 삼항과 `parent_pairs` 삼항을 `relation_patterns`에 다시 적지 않았다.
5. 이 층 문서의 **소속**(아래가 위의 일부 · 위의 항목 — 이름의 부모가 되는 관계: 부품 → 유닛 · 관리항목 → 유닛)은 `parent_pairs` 제안에 있고(불량 → 공정 같은 사실 관계는 `relation_patterns`), 그 두 카테고리를 이 층이 다 말한다(`categories` ∪ `uses`) — 아니면 소속 엣지가 서지 않고 그 노드는 「엣지 없는 노드」로 남는다. 그 관계 이름은 `relations`에 있다.
6. 극성은 그 카테고리의 home 층 config에만 있고, `values`가 골격 층 config의 `polarity.values`와 같다.
7. 질의가 이 층 엣지를 따라 다른 층 노드로 건너가는 길이 있다 — 소속 관계(`has_property` 같은 것)는 이 층 `query_traverse`에 두면 다른 층 노드에서도 이 층 규칙으로 뻗고, 불량 → 공정 같은 사실 관계의 다리는 이 층 `cross_layer_traverse`에 둔다. 그 관계마다 `fact_templates`가 있다.

## 13. 규율

- 예시 넷과 첨부에 없는 키를 만들지 않는다(§4의 19개뿐).
- 첨부 문서 · 골격에 없는 이름을 정의문 예로 쓰지 않는다.
- 판단이 갈린 자리는 「확인 필요:」에 적는다. 추측으로 채우지 않는다.

## 예시 넷 읽는 법

- `설비층_config_예시.json` — 골격 층: `skeleton`(파일) · `registration: builtin` · 극성 `Unit` · `Component` · 설비 문서의 사양 항목 이름을 받으려고 `uses: ["Property"]`(값은 공정층에서) · `relevance_terms` · 층 힌트 `structure` · `extract`.
- `공정층_config_예시.json` — `Property` 하나를 정의하고 공정 · 설비 · 부품은 `uses` · `Property`의 극성과 값(`value_categories`)은 여기 · 소속 관계 이름 `part_of` · `has_property`.
- `품질층_config_예시.json` — 닫힌 목록(`flat`) · 다른 층으로 가는 관계(`occurs_in` · `controlled_by`)와 `cross_layer_traverse` · 극성 없음.
- `common_사람줄_예시.json` — 공통 config에서 사람이 쓰는 줄: 겸(`also`) · `parent_pairs`. `_parent_pairs_note`처럼 갈리는 결정은 주석과 「확인 필요」로 남긴다.

## 받은 뒤 확인 (사람)

```
1. config.json을 $ONTO_HOME/layers/<층>/config.json으로 · 「공통 config에 더할 줄」을 $ONTO_HOME/layers/common.json에 손으로 옮긴다
2. python run.py bootstrap --dry-run      ← 모르는 키 · 틀린 형 · 닫힌 값 밖 · 선언 없이 쓴 카테고리 · JSON 문법이면
                                           파일 · 키 · 가장 가까운 아는 키 · 다음 줄을 말하고 멈춘다(멈출 것 0이 될 때까지)
3. python run.py bootstrap                ← 끝 줄: 골격 겸 상태 · 등록 스키마 재대조(doc_type마다 PASS/FAIL) · config 영향
4. python run.py export config            ← 첫 줄 reject 0 · warn 0 · coord layer <골격 층> · 온톨로지 맵(export/config_map.html)
5. 골격 층이면 골격 팩 「받은 뒤 확인」 3 ~ 6(skeleton-status · 흐름 대조 · 노드 수 · skeleton-confirm)
```
