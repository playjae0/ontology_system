# IPQC 정답표 (봉인 — 블라인드 판정 전 작성)

> 이 문서는 IPQC01/02.xlsx를 **만든 쪽**이 의도한 role 배정이다.
> 블라인드 서브에이전트에게 제시되지 않으며, 판정 결과 대조에만 쓴다.
> "정답"이라 부르지만 실제로는 **설계 의도**다 — 서브에이전트가 다르게 판정했다고
> 자동으로 틀린 것이 아니라, 갈린 지점이 프롬프트 템플릿의 개선 지점이다.

## 필드 role 배정 (16열)

| # | 열 이름 | 의도한 role | 속성 | 근거 |
|---|---|---|---|---|
| A | 대공정 | `anchor` | (process_group) | 골격 조회. 해소만 하고 부착엔 쓰지 않음 |
| B | 공정No | `meta` | (process_no) | 사내 번호는 비표준·가변이라 조회 키가 아님 (CH2 2.2 경계) |
| C | 공정명 | `anchor` | (process_ref) | 세부공정 골격. 부착의 기본 대상 |
| D | 극성 | **role 배정 대상 아님** | (electrode_type 구조 필드) | 가결정 D-1 — role 핸들러가 아니라 entity 해소 코드가 직접 읽음 |
| E | 검사설비 | `entity` | category=Unit | |
| F | 검사항목 | `entity` | category=Property | |
| G | 규격 | `attribute` | attr_name=spec, contextual=true, attach_to=검사항목, optional | 구조체 통째 저장 |
| H | 측정방법 | `attribute` | attach_to=검사항목, optional | |
| I | 판정기준 | `attribute` | attach_to=검사항목, optional | **관찰 포인트** — content로 볼 여지 있음 |
| J | 부적합 조치 | `content` | attach_to=검사항목, optional | 자유 서술 |
| K | 적용모델 | **role 배정 대상 아님** | (context 구조 필드) | CH2 2.5 규약 3 — 맥락 상속 처리의 입력 |
| L | 검사자 | `meta` | | 내용 바깥의 관리 정보 |
| M | 검사일시 | `meta` | | |
| N | 성적서번호 | `meta` | | |
| O | 최근 불량 이력 | **`UNMAPPABLE`** | | 미래 층(불량이력층) 소관 · 시점 종속 값 → **L4 신호** |
| P | 관련 표준문서 | **`UNMAPPABLE`** | | 다른 문서를 가리키는 참조 성격 → **L3 `reference` role 신호**(CH2 2.7 규약 3의 예시 그대로) |

## edges 선언

| from | relation | to | optional |
|---|---|---|---|
| 검사설비 | part_of | @process_ref | |
| 검사설비 | has_property | 검사항목 | |

## 관찰 상수 (ADAPTER.expects)

- `header_row`: 3
- 병합: A열 전체 / B·C열 공정 단위 세로 병합
- 상동 기호: `〃` (검사설비 열)
- 복수값 구분자: `,` (검사항목 열, I11)

## 미리 예상한 갈림 지점 (3건)

1. **극성(D)** — LLM은 `attribute`로 배정할 가능성이 높다. 실제로는 구조 필드라 role 대상이 아니다. 이 갈림은 원천(정의서 §5.1 vs 명세 §6.2)이 아직 불일치인 지점과 같다(CH2 2.5 남은 미결).
2. **적용모델(K)** — `attribute` 또는 `meta`로 배정할 가능성. 실제로는 context 구조 필드.
3. **판정기준(I)** — `attribute` vs `content`. 짧은 정형 문구라 attribute로 봤으나 문장 형태라 content 여지가 있다.

## 어서션

- O·P 두 열에 대해 **`UNMAPPABLE`이 나오는가** — 이것이 6지선다 6번째 경로의 실증이다.
- 억지로 `meta`나 `attribute`에 끼워 넣으면 프롬프트의 "맞지 않으면 UNMAPPABLE" 지시가 약한 것이다.
