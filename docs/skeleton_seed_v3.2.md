# 조립 골격 seed v3.2 (확정본 — 2026-08-10 승인 · layers/process/skeleton.json으로 반입)

> 상태: **확정 (2026-08-10, M2 승인).** 판정문(안건/M2_판정문안_초안.md **r8**)과 세트 — 문법·규칙의 정본은 판정문 §2(A11)·§4 → 정본 반영본은 틀 v2.6 §4B-A11 / 카드 v13. 다음 단계: 허브 세션이 skeleton.json으로 반입 → n10 재실행(아래 기대값 대조) → G3 정합 + mock "실링" 행 교체(D-42).
> **v3.2**: skeleton_aliases.json 별도 파일 **폐지** — ALIASES는 skeleton.json 안의 분리 블록(트리와 나란한 최상위 키)으로 복귀. **지위: 이 블록은 사전이 아니라 seed(원천)다** — loader가 dictionary.json(전 층 공유 단일 장부·B4)에 `provenance: ["seed"]`로 등재하면 역할 종료. 운영 중 표기 축적은 매칭 경로(E5)로 같은 사전에 쌓이며, seed 유래와는 provenance 태그로 구분된다(구역 분리 아님). 소비처(anchor 해소·좌표 닫힌 목록·판정 후보·질의 링킹)는 전부 사전만 본다.
> v3.1: `~` → `@unordered` 래퍼, 마커 닫힌 7종. v3: FLOW 폐지 — 배열=대표 흐름. v2: 사용자 답변 6건.
> **음/양극 대응: cathode=양극, anode=음극** (POLARITY_LABELS).

## 문법 요약 (정본은 판정문 §4)

- **자식은 배열이며, 배열 순서 = 그 부모 아래 대표 흐름 선언이다.** 별도 FLOW 블록 없음.
- 항목 형태: `"이름"`(잎) / `{"이름": [자식배열]}`(중간 노드) / `{"이름": "@split"|"@cathode"|"@anode"}`(극성 스텝) / `"::cathode"`·`"::anode"`(자식 없는 주소 인스턴스) / `{"@unordered": <항목>}`(순서 비참여 래퍼) / 배열 첫 요소 `"@noflow"`(그 부모 아래 전체 무주장).
- **순서 비참여**: `::` 인스턴스(자동) · `@unordered` 래퍼(개별) · `@noflow`(레벨 전체). 체인은 참여 항목만 건너 잇는다. @split류의 **개념은 참여, 인스턴스는 비참여** — 극성 간 순서는 어디에도 생기지 않는다.
- **마커 어휘는 닫힌 7종**: `::cathode` `::anode` `@split` `@cathode` `@anode` `@unordered` `@noflow` — 그 외는 명시적 실패.
- **단극성 = `"@cathode"`/`"@anode"`**(개념+인스턴스 1). 리스트 표기(`["anode"]`) 금지. 반대 극성 판명 시 `@split`로 한 글자 수정(무개명). Tier1 단극성은 mirror_asymmetry 대상 아님.
- tier(main/sub/detail)·parent·canonical 접두·polarity는 loader 파생 — 수기 접두·이름 문자열 마크업 금지.
- **ALIASES 블록**: 사람 보증 초기 표기만(키: 짧은 이름 허용, 모호하면 접두 요구 — 명시적 실패). 인스턴스의 극성 수식 표기("양극 탭용접" 등)는 auto alias(`"{극성영문} {이름}"`·`"{극성한글} {이름}"`)가 생성하므로 불요.
- **loader는 로드 시 파생 대표 흐름을 사람이 읽는 형태로 출력한다**(순서 오선언의 안전망 — M9 결과 뷰 계보). 부분 순서·합류 표현은 이연(트리거: 실수요).

## layers/process/skeleton.json (단일 파일 — 구조·흐름·초기 표기)

```json
{
  "skeleton_version": 3,
  "POLARITY_LABELS": { "cathode": "양극", "anode": "음극" },
  "PROCESS_TREE": [
    { "조립": [
      { "노칭": ["::cathode", "::anode",
                 "전극 언와인딩", "노칭 타발", "비전검사", "전극 리와인딩"] },
      { "스태킹": [
          {"@unordered": "전극 시트 공급"},
          {"@unordered": "분리막 공급"},
          "적층", "비전검사", "스택 테이핑"] },
      { "탭용접": ["::cathode", "::anode",
                   {"pre용접": "@split"}, {"pre vision": "@split"}, {"cutting": "@split"},
                   {"탭공급": "@split"}, {"main용접": "@split"}, {"laser용접": "@split"},
                   "bead press", "cleaning", "탭 taping", "vision check", "barcode marking"] },
      { "패키징": ["파우치 포밍", "스택 삽입", "사이드 실링", "전해액 주액", "프리 실링"] }
    ]}
  ],
  "ALIASES": {
    "조립": ["assembly", "조립공정"],
    "노칭": ["notching", "NC"],
    "전극 언와인딩": ["unwinding", "언와인딩"],
    "노칭 타발": ["punching", "타발"],
    "노칭::비전검사": ["비전 검사", "노칭 검사", "vision inspection"],
    "전극 리와인딩": ["rewinding", "리와인딩"],
    "스태킹": ["stacking", "ST"],
    "전극 시트 공급": ["electrode feeding", "전극 투입"],
    "분리막 공급": ["separator feeding", "세퍼레이터 공급"],
    "적층": ["z-stacking", "z-folding", "스택 적층"],
    "스태킹::비전검사": ["비전 검사", "정렬 검사", "align inspection"],
    "스택 테이핑": ["스택 고정 테이핑"],
    "탭용접": ["tab welding", "탭 용접", "TW"],
    "탭용접::cathode": ["cathode tab welding"],
    "탭용접::anode": ["anode tab welding"],
    "pre용접": ["pre 용접", "pre welding", "예비 용접"],
    "pre vision": ["프리 비전"],
    "cutting": ["tab cutting", "탭 컷팅", "탭 절단"],
    "탭공급": ["탭 공급", "lead tab feeding", "리드탭 공급"],
    "main용접": ["main 용접", "main welding", "본 용접"],
    "laser용접": ["laser 용접", "laser welding", "레이저 용접"],
    "bead press": ["비드 프레스", "용접부 압착"],
    "cleaning": ["클리닝", "이물 제거", "파티클 제거"],
    "탭용접::탭 taping": ["탭 테이핑", "절연 테이핑"],
    "탭용접::vision check": ["비전 검사", "용접부 검사"],
    "barcode marking": ["바코드 마킹", "셀 ID 마킹", "marking"],
    "패키징": ["packaging", "PKG", "포장"],
    "파우치 포밍": ["forming", "pouch forming", "컵 성형"],
    "스택 삽입": ["inserting", "cell inserting", "폴딩"],
    "사이드 실링": ["side sealing", "3면 실링", "측면 실링"],
    "전해액 주액": ["electrolyte filling", "주액", "전해액주입"],
    "프리 실링": ["pre-sealing", "가실링", "1차 실링"]
  }
}
```

> 편집 판단 계류 1건: `"taping"` 표기가 스택 테이핑·탭 taping 양쪽에 걸려 모호하므로 **양쪽에서 제외**했다(운영 중 문서에서 관찰되면 사전이 판정·축적). 사내 관행상 한쪽만 가리키면 그쪽에 되살릴 것.
> 접두 키 사용 지점: `비전검사` 3곳(노칭·스태킹·탭용접 vision check)·`탭 taping` — 짧은 키가 모호한 항목만.

## alias의 흐름 (원천 → 장부 — 이중 기준 아님)

```
skeleton.json ALIASES (사람 원천, git)
   → loader(n10) → dictionary.json에 provenance=["seed"]로 등재   ← 여기가 유일한 조회 대상
   → 운영 축적분(E5 매칭 — provenance=문서)과 한 장부에서 공존
```
- 골격 노드가 seed 파일(원천)과 그래프(적재본)에 나란히 존재하는 것과 동일한 관계다(3.9).
- seed ALIASES를 개정하면 n10 재실행으로 사전의 seed 유래 엔트리가 갱신된다 — 운영 축적분은 불변(H2 보존 계열).

## loader 파생 흐름 출력 (로드 시 — 이 seed 기준 기대 출력)

```
[조립]   노칭 → 스태킹 → 탭용접 → 패키징
[노칭]   전극 언와인딩 → 노칭 타발 → 비전검사 → 전극 리와인딩
[스태킹] 적층 → 비전검사 → 스택 테이핑          (무주장: 전극 시트 공급, 분리막 공급)
[탭용접] pre용접 → pre vision → cutting → 탭공급 → main용접 → laser용접
         → bead press → cleaning → 탭 taping → vision check → barcode marking
[패키징] 파우치 포밍 → 스택 삽입 → 사이드 실링 → 전해액 주액 → 프리 실링
(순서 비참여: 인스턴스 16종 — 극성 간 순서 무주장)
```

## loader 기대값 (n10 완료판정 재료 — 이 seed 기준)

| 항목 | 수 | 산출 |
|---|---|---|
| 노드 | **46** | 조립 1 + sub 4 + 노칭(인스턴스2+detail4) 6 + 스태킹 5 + 탭용접(인스턴스2 + @split 개념6·인스턴스12 + 공통5) 25 + 패키징 5 |
| part_of | **45** | 루트 제외 전 노드 |
| precedes | **22** | 조립 3 + 노칭 3 + 스태킹 2 + 탭용접 10 + 패키징 4 |
| polarity ≠ none | **16** | 인스턴스 4(노칭2·탭용접2) + @split 인스턴스 12 |
| mirrors 쌍 | **8** | 노칭 1 + 탭용접 구간 1 + @split 6 |
| 사전 seed 엔트리 | canonical 46 + ALIASES 표기 + auto alias(인스턴스 16×2) — 전부 provenance=["seed"] | |

## mock raw 재매핑 (D-42 — 허브 전달)

- "노칭"·"스태킹"·"패키징" → 그대로(개념 노드 해소) / "cathode 탭용접"·"anode 탭용접" → auto alias로 인스턴스 해소 / "전해액주입" → alias로 `패키징::전해액 주액` 해소. **전부 파일 무수정.**
- **"실링" 행만 수정 필요** — 사이드 실링/프리 실링 중 행별로 허브가 판단해 공정명 교체(bare "실링"은 무배정 = 모호 유지가 의도).
- process_no(10~60)는 meta라 검증 무관 — 재부여 여부는 허브 재량.
