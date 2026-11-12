# -*- coding: utf-8 -*-
"""칸 3.2·3.5 — 1c′·1d′ 구축 — 계약 JSON을 그래프로 (계약 v2 정합).

변경점 닫힌 목록 5항 (증분0 §3 G3):
  ① 조각 공통 `chunk_id` → **`source_locator`**(role=meta)
  ② 봉투 `payload_kind`·`adapter_version` 소비 (에이전트가 청크에 복사)
     — `classification`은 소비 대상이 **아니다**(D-37: 자리만 있고 아무도 읽지 않는다)
  ③ process_group·process_ref 둘 다 anchor이나 **부착은 process_ref 하나**.
     process_group은 해소 후 **골격 조상 대조만** 하고, 어긋나면 `coord_mismatch` 큐(C3)
  ④ `electrode_type`은 블록에 넣지 않고 **구조 필드**로 유지 — 극성은 이름 · 판정에 들지 않고 값 · 엣지 · 노드의
     한정어로 시스템이 옮겨 적는다(B198 · `core/build/polarity` — role 핸들러 · LLM이 쓰지 않는다)
  ⑤ 큐 kind 목록 확장 (§6-5, 계 20종)

**코드에 층 어휘 0**(B1) — 카테고리 이름·관계 이름·극성 값이 이 파일에 없다.
전부 `layers/*/config.json`과 `schemas/*.json`이 값으로 준다.
"""
from __future__ import annotations

import weakref

from core.build import gate
from core.state import store
from core.dictionary import Dictionary
from core.state import alias_book
from core.state.ids import norm
from core.matcher import MATCH, NEW, UNCERTAIN, gated, resolve

#: 골격 밖 반복 판정 기억(B100 ⑤) — 한 실행(프로세스) 안 · 열쇠에 골격·사전의 판이 들어 있다.
_MEMO = {}
#: 이번 문서 실행이 사전·노드에 더한 **LLM 매칭** 별칭(B101 ④ — 결과표의 수) · 문서 시작에 비운다.
ADDED = []
#: 값 싣기의 결과(`put_attribute` — 표 · 산문 한 함수 · B120 ①): 새 항목 · 같은 값(출처만 더함) · 같은 맥락 다른 값(spec_conflict)
ATTR_ADDED, ATTR_SAME, ATTR_CONFLICT = "added", "same", "conflict"
from core import matcher as _matcher              # noqa: E402 — 2차 판정 · 문장 폭
from core.state.status import is_live
from core.build.build_coord import CoordMixin              # 좌표 계보 · 공정 목록 (B125 ④ — 800행 상한으로 나눴다)
from core.build.naming import scope_categories, scope_canonical, scope_of, base_name_of

def entity_key(surface, category, cfg, *, parent_canonical=None):
    """**판정이 사전을 여는 키** — 예고와 판정이 이 함수 하나를 부른다 (B74 ①).

    돌려주는 것은 `(canonical, scoped, 스코프_카테고리인가)`다. 키 조립이
    두 곳에 복제되면 예고가 판정과 **다른 키로 사전을 보게 되고**, 그 순간 예고는
    비용을 잘못 말한다(허브 실측 열셋째: 예고 「사전 히트 31종」 · 판정 「사전 0」).
    **극성은 키에 들지 않는다**(B198 — 같은 이름 · 같은 자리 · 다른 극성은 노드 하나).
    """
    scoped_category = category in scope_categories(cfg)
    canonical, scoped = scope_canonical(surface, category, parent_canonical, cfg)
    return canonical, scoped, scoped_category


ROLE_HANDLERS = ("anchor", "entity", "attribute", "content", "meta")


def _name_of(ref):
    """`(노드 id, 그 그래프)` → 그 노드의 canonical(없으면 None) — 값의 경로의 이름 재료."""
    nid, g = ref if ref else (None, None)
    return ((g.get(nid) or {}).get("canonical") if nid and g is not None else None)


class Builder(CoordMixin):
    def __init__(self, graph, cfg, schema, doc_id, layer):
        self.anchor_hold = None                   # 마지막 좌표 해소의 보류 사유(B104 ①)
        self.g = graph
        self.cfg = cfg
        self.schema = schema
        self.doc_id = doc_id
        self.layer = layer
        self.dict = Dictionary.open()      # 사전 접근은 관문 경유로만 (문서 7 §7.1)
        self.book = alias_book.AliasBook.open()   # 표기 대장 별칭 갈래 — 사전과 같이 열고 같이 쓴다 (B108 ①)
        self.buffer: dict[str, str] = {}     # 문서 해소 버퍼 (2-pass Pass 1)
        # 걸침 층별 하위 빌더 — 아래 for_layer. **뿌리도 제 층 이름으로 든다**(B99 ①): 하위 빌더가
        # 뿌리 층을 물으면 새로 열지 않고 뿌리를 돌려준다(같은 그래프 사본 둘 = 덮어쓰기 소실).
        self.subs: dict[str, "Builder"] = {layer: self}
        # 마지막 entity 해소의 사실 — **대장이 읽는 자리**다(B74 ②). 판정이 아는
        # 것(경로·점수·큐)을 호출부가 다시 계산하지 않게 여기 실어 올린다.
        self.last: dict = {}
        # 판정 대장 — 문서 하나에 하나이고 걸침 하위 빌더와 **공유한다**(B74 ②).
        self.ledger = None
        self.doc_coord = None                # 문서 좌표 — 판단 재료의 값의 경로(B181 ② · 구축 입구가 봉투에서 싣는다)
        self._pmaps = {}                     # 골격 부모 표 — 좌표 쌍 판정(B105 · `_parent_map`)
        # 잠정 골격 노드(B182 — `core/build/provisional`): 앞 패스가 정한 행의 자리 · 보류 사유 · 이 문서가 세운 것(하위 빌더와 공유)
        self.coord_at, self.coord_hold, self.made = {}, {}, {}
        self.coord_gate = {}                      # 문에 걸린 행의 재료(B196 ① — 자리 · 판단 · 후보 · `(prov, 표기)`)
        self.coord_pair, self.pair_off = {}, False   # 쌍 어긋남의 문(B196 ② — 확인 전 보류 행 · 대조 중에는 끈다)
        # 골격 단의 문(B197 ① — `core/build/also_gate`): 문에 걸린 값 · 걸린 제목 · 표 행의 말미 적재 자루 · 사람 답(하위 빌더와 공유)
        self.also = {"held": {}, "heads": {}, "landed": {}, "defer": None, "field": None, "book": None}
        # 다른 층의 같은 엣지에 출처를 더할 때 그 층을 **이 빌드가 저장하는 그래프**로 연다(B180 ② · `gate.bind` — 먼저 건 손이 이긴다)
        gate.bind([graph], lambda lay, me=weakref.ref(self): me().for_layer(lay).g if me() is not None else None)

    # ---------------------------------------------------------------- 걸침
    def for_layer(self, layer):
        """다른 층에 쓰는 하위 빌더. **층당 하나로 캐시한다.**

        캐시가 없으면 레코드마다 `open_graph`가 새 인스턴스를 물어 와서 **앞 레코드가
        쓴 것이 뒤 레코드에게 보이지 않고**, 어느 것도 저장되지 않는다(외부 그래프
        증발 — R2-9 실측). 사전과 문서 버퍼는 **공유**한다: 장부는 하나이고(B4),
        버퍼는 문서 하나의 것이지 층의 것이 아니다.
        """
        if layer == self.layer:
            return self
        if layer not in self.subs:
            from core.state.bootstrap import load_config, open_graph
            # **같은 층 그래프는 한 빌드에서 한 번만 연다**(B99 ①) — 이미 연 그래프가 그 층이면 결함
            if any(s.g.layer == layer for s in self.subs.values()):
                raise RuntimeError(f"[결함] 한 빌드에서 층 '{layer}' 그래프를 두 번 열려 한다 — "
                                   f"하위 빌더 키가 폴더 이름과 어긋났다(core/build/build.py::for_layer)")
            sub = Builder(open_graph(layer), load_config(layer), self.schema,
                          self.doc_id, layer)
            sub.dict = self.dict
            sub.book = self.book
            sub.buffer = self.buffer
            sub.ledger = self.ledger
            sub.doc_coord = self.doc_coord
            sub.coord_at, sub.coord_hold, sub.made = self.coord_at, self.coord_hold, self.made
            sub.coord_gate, sub.coord_pair = self.coord_gate, self.coord_pair
            sub.also = self.also
            sub.subs = self.subs
            self.subs[layer] = sub
        return self.subs[layer]

    def graphs(self):
        """이 빌드가 만진 그래프 전부 — 자기 층 + 걸침 층. 저장 대상이다."""
        return [self.g] + [s.g for s in self.subs.values() if s is not self]

    # ---------------------------------------------------------------- home (B90 ②)
    def home_of(self, category):
        """카테고리의 **home** 층 — 공통 config의 `home`. 카탈로그 밖이면 자기 층."""
        from core.state.bootstrap import layer_of_category
        return layer_of_category(category) or self.layer

    def for_category(self, category):
        """카테고리의 home 빌더 — **해소의 라우팅 한 자리**다(table·prose가 같이 부른다).

        노드는 home 그래프에 산다: 여러 층이 같은 카테고리를 선언해도 매칭·생성은
        home 하나에서 한다 — 같은 뜻이면 노드 하나(두 벌로 만든 뒤 합치지 않는다).
        """
        return self.for_layer(self.home_of(category))

    def canonical_of(self, nid):
        """그 노드의 canonical — home 그래프에서(B102 ⑦ 대장 `target` · 없으면 None)."""
        if not nid:
            return None
        return ((self.graph_of(nid) or self.g).get(nid) or {}).get("canonical")

    def resolve_at_home(self, surface, category, prov, *, coord=None, coords=None, **kw):
        """개체 하나를 **home 빌더에서** 해소한다 — `(node_id, 그 빌더)`.

        판정의 사실(`last` — 경로·층·큐)은 돌려준 빌더에 실린다. 대장·큐의 `layer`가
        home이 되는 것은 그래서다(종결 명령이 그 층을 가리켜야 한다).

        `coord`(`(좌표 노드 id, 그 그래프)`)가 있으면 **자기 좌표 규칙을 먼저 본다**
        (B90 ③) — 이름 규칙(`X::…`)으로 키를 만들기 **전**이어야 한다.

        그보다 앞에 **다른 공정 이름 가드**(B113 ①) — 표기가 좌표 계보 밖 골격 노드의 이름이면 노드를 만들지
        않고 그 공정으로 관련 링크(`mentions` — 구축 끝에 청크의 `about`)만 남긴다(`(None, self)`). `coords`(청크 공정
        목록의 해소 `[(id, 그래프)]` — B125 ④)가 오면 계보는 목록 **전체**다(없으면 `coord` 하나).
        """
        if self.also is not None:                      # 사람이 고친 해석(B202 ② — 카테고리 · 위 공정)이 먼저
            from core.build import also_gate
            category, coord = also_gate.reread(self, surface, category, coord)
        other = self.other_process(surface, coord, coords)
        if other is not None:
            return self._mention(surface, category, prov, other), self
        hit = self._self_coord(surface, category, coord)
        if hit:
            return hit
        eb = self.for_category(category)
        return eb.resolve_entity(surface, category, prov, coord=coord, **kw), eb

    def graph_of(self, nid):
        """그 노드가 사는 그래프 — 이 빌드가 연 그래프 중에서. 없으면 `None`."""
        for g in self.graphs():
            if nid and g.get(nid):
                return g
        return None

    # ---------------------------------------------------------------- 사전
    def _register(self, surface, nid, prov, key=None, by=None):
        """사전 등재는 관문이 한다 — **provenance 필수 강제가 그쪽에 있다**(§7.1).

        alias 항목(`{surface, provenance}`)은 노드 레코드에 살므로(§7.2) 그
        붙이기만 여기 남는다 — 사전이 그래프를 쓰면 저장 계층 경계가 무너진다.

        **키 둘을 등재한다**(B74 ①): 원 표기와 **조회 키**(`key` — 해소가 사전을
        열 때 쓴 스코프 canonical)다.

        · 원 표기는 질의 링킹의 표면형 스캔이 쓴다(문서 5) — 그래서 남긴다.
        · 조회 키가 없으면 **사전은 영영 히트하지 않는다**: 등재는 `노칭 프레스`로
          하고 조회는 `노칭::노칭 프레스`로 하던 것이 허브 실측 열셋째의 결함이다.
        · 판정이 **다른 노드에** 붙였을 때도 키는 그 표기의 것이다 — 그래야 다음
          문서에서 같은 표기가 같은 부모 아래 다시 나올 때 판정을 다시 부르지 않는다.
          (`key`를 안 주면 그 노드의 canonical을 쓴다 — 조회 키를 모르는 호출용.)

        스코프 없는 카테고리는 표기와 키가 같으므로 등재는 1건이다.

        **별칭은 쓰는 손 하나를 지난다**(B108 ① · `alias_book.attach`) — 대장에 이름으로 남는다(출처: 판정 표지가
        있으면 LLM 매칭 · `ops alias`면 사람 · 그 밖은 문서). 사람이 거둔(거부) 표기는 다시 붙이지 않는다 —
        사전에도 싣지 않는다(노드 자신의 이름 키만). 판정은 그대로다(값은 판정대로 이 노드에 이어진다).
        """
        n = self.g.get(nid)
        key = key or n["canonical"]
        if self.book.rejected(surface, n):
            if norm(key) == norm(n["canonical"]):
                self.dict.register(key, nid, provenance=prov)
            return
        self.dict.register(surface, nid, provenance=prov)
        if norm(key) != norm(surface):
            self.dict.register(key, nid, provenance=prov)
        if norm(surface) != norm(n["canonical"]):
            src = "LLM 매칭" if by else ("사람" if str(prov).startswith("op:alias:") else "문서")
            if alias_book.attach(self.book, n, {"surface": surface, "provenance": [prov], **(by or {})},
                                 source=src, doc=self.doc_id, key=key) and by:
                ADDED.append({"surface": surface, "node_id": nid, **by})

    def flush(self):
        self.dict.save()
        self.book.save()                     # 표기 대장 별칭 갈래은 사전과 같은 때 — 되돌림 경계도 같다 (B108 ①)

    def coord_verdicts(self, group_surface, ref_id, g=None):
        """**좌표 쌍 판정**(B105) — `(판정 목록, 상위가 가리키는 골격 노드들)`.

        판정은 `parser.coord_pairs.verdict` **하나**다 — 등록 리허설 · 인입 좌표 단계 · 구축이 같은 함수(두 벌 금지).
        여기는 구축의 해소만 한다: 상위 표기 → 사전 조회 중 하위와 같은 카테고리 노드 **전부**(공유 별칭이면 여럿 —
        첫 노드를 고르지 않는다 · 그중 하나라도 조상이면 맞음) · 부모 사슬은 그 카테고리를 선언한 층의 골격 관계.
        상위가 골격 밖이면 어긋남이 아니다(D3·A5 — 큐 없음 · 화면이 센다).
        큐에 싣는 자리는 `core/build/coord_scan.enqueue` 하나다(구축 말미 — 표·산문·렌즈 같이).
        """
        from parser import coord_pairs as CP
        if not ref_id:
            return [], []
        g = g or self.g
        node = g.get(ref_id) or {}
        cat, rc = node.get("category"), node.get("canonical")
        gcs = sorted({g.get(nid)["canonical"] for nid in self.dict.lookup(group_surface)
                      if (g.get(nid) or {}).get("category") == cat}) if group_surface else []
        return CP.verdict(group_surface, gcs, rc, parent_of=self._parent_map(g, cat).get), gcs

    def _parent_map(self, g, cat):
        """그 그래프 골격의 부모 표 `{canonical: 부모 canonical}` — 그 카테고리를 선언한 층의 골격 자식 관계 ·
        한 빌더에서 한 번(골격은 구축 중에 바뀌지 않는다). 같은 노드의 부모 엣지가 여럿이면 앞의 것(구판 그대로)."""
        key = (id(g), cat)
        if key not in self._pmaps:
            from core.state.bootstrap import layer_of_category, load_config
            owner = load_config(layer_of_category(cat) or self.layer)
            child_rel = ((owner.get("skeleton") or {}).get("relations") or {}).get("child")
            pm = {}
            for e in g.edges:
                if e["rel"] == child_rel:
                    s_, d_ = g.get(e["src"]), g.get(e["dst"])
                    if s_ and d_ and s_["canonical"] not in pm:
                        pm[s_["canonical"]] = d_["canonical"]
            self._pmaps[key] = pm
        return self._pmaps[key]

    # ---------------------------------------------------------------- entity
    def _judge(self, surface, category, canonical, scoped, parent_canonical, at, row, place=None, where=None,
               field=None):
        """판정 한 번 — `((분기, node_id, 점수, 판정 dict), 재생하지 못한 사유)`.

        **판정 재생**(B106 ②) — 판정 없이 붙지 않는 값만(사전 · 경로 호환 같은 이름이 답하지 않았다 — `matcher.gated` ·
        후보 조립과 같은 함수) · `at`(위치 · 열)의 지난 판정이 있으면 그 결과를 바꿔 끼우고
        좁히기 + LLM을 건너뛴다. 아니면 `matcher.resolve` — `row`(그 값이 나온 청크 · 행)의 원문이 2차 판정의
        문장이다(B123 ③ — 1차가 불확실일 때만 · 청크는 그 표기 앞뒤 · 표는 같은 행의 다른 칸 — B181 ③ `extract_ctx.source_of`) ·
        `where`는 값의 경로(B181 ② — 이름 규칙 카테고리 밖). 그 뒤(노드 · 사전 · 큐 · 대장)는 호출부 그대로다.
        판정에 오른 값은 **근거 지문**(B167 ② — `replay.basis`)을 판정 dict에 싣는다 — 대장 행이 옮기고 재생이 다시 잰 것과 견준다."""
        rp = why = fp = None
        pre = gated(canonical, category, self.layer, self.g, self.dict, scoped=scoped,
                    parent=parent_canonical, cfg=self.cfg, place=place)
        if not pre[0]:
            from core.build import replay as _rp
            fp = _rp.basis(canonical, pre, self.cfg)
            rp, why = _rp.pick(self, at, surface, category, canonical, basis_now=fp)
        got = self._judged(surface, category, canonical, scoped, parent_canonical, row, place, pre, rp, where, field)
        if fp is not None:
            got[3]["basis"] = fp
        return got, why

    def _judged(self, surface, category, canonical, scoped, parent_canonical, row, place, pre, rp, where=None,
                field=None):
        """재생(`rp`) 또는 판정 — `(분기, node_id, 점수, 판정 dict)`(위 `_judge`의 몸)."""
        sent = None
        if row and (rp is None or rp[3].get("second_due")):
            from core.build.extract_ctx import source_of
            sent = source_of(row, surface, field, _matcher.context_chars())
        if rp is not None:
            if rp[3].get("second_due") and sent:       # 재생의 불확실 · 2차 기록 없음 → 2차 한 번(B127 ①)
                got = _matcher.second_at(canonical, category, self.layer, self.g, self.dict, rp[3], scoped=scoped,
                                         parent=parent_canonical, sentence=sent, place=place, pre=pre)
                if got is not None:
                    from core.build import replay as _rp
                    _rp.note_second(got[0] == "match")
                    return got
            return rp
        return resolve(canonical, category, self.layer, self.g, self.dict, scoped=scoped,
                       parent=parent_canonical, sentence=sent, place=place, pre=pre, where=where)

    def resolve_entity(self, surface, category, prov, *, electrode_type=None,
                       parent_canonical=None, coord_surface=None,
                       belongs=None, at=None, row=None, field=None, coord=None, owner=None):
        """3분기 — 매칭 / 신규 / 불확실(신규+표시). `coord` · `owner`(산문 소속 대상 · 표 행의 소유 엣지 개체 · 위 제목 개체)는
        판정의 **자리**다(B142 — `scope_path.place` · 관문은 카테고리 · 공정 줄기 · 경로는 증거 · 이름 부모는 호출부가 `naming.name_parent`로 · B144 ②).

        `row`(그 표기가 나온 청크 · 표의 행 — B181 ②)는 판단 재료다 — 값의 경로(이름 규칙 카테고리 밖 — `extract_ctx.value_path`) ·
        1차가 불확실이면 그 원문으로 2차를 묻는다(B123 ③ — `matcher.second` · 청크는 그 표기 앞뒤 글).

        **극성은 이름 · 후보 · 판정 기억에 들지 않는다**(B198) — `electrode_type`은 자리 추정의 재료로만 넘기고, 극성은 문서 끝
        한 자리(`polarity.stamp_graphs`)가 노드 · 엣지의 출처별 칸에 옮겨 적는다.
        """
        from core.state.bootstrap import layer_of_category
        if layer_of_category(category) is None:
            return self._invalid_category(surface, category, prov)
        # **좌표 없는 스코프 개체 0**(B102 ⑤ · 문서 4 §4.4) — 노드를 만들지 않는다 · 자리를 아예 말하지 않은 값만 자리 추정(B183) · 재료는 큐
        if category in scope_categories(self.cfg) and not parent_canonical:
            return self._no_coord(surface, category, prov, coord_surface, belongs,
                                  guess=dict(electrode_type=electrode_type, row=row, field=field, at=at))
        canonical, scoped, scoped_category = entity_key(surface, category, self.cfg, parent_canonical=parent_canonical)
        # **부모 좌표를 넘긴다**(B73 ①) — 후보를 상한 안으로 좁힐 때 「같은 공정
        # 아래」가 첫 기준이고, 그 정보는 여기에만 있다.
        # **골격 밖 반복 판정 기억**(B100 ⑤) — 노드를 만들지 않고 끝난 판정은 한 실행 안에서
        # 같은 열쇠면 다시 묻지 않는다(후보·LLM 0) · 대장 행은 매 행 남는다(경로 `memo`).
        from core.build import also_gate
        gate_at = also_gate.pre(self, surface, category, prov, coord)     # 골격 단의 문(B197 ① — 겸 값은 골격 노드로만)
        if isinstance(gate_at, tuple):
            return gate_at[1]
        mkey = self._memo_key(surface, canonical, category, parent_canonical)
        if mkey in _MEMO:
            return self._memo_replay(surface, category, canonical, prov, _MEMO[mkey], coord=coord)
        from core.llm import gateway as _llm
        from core.build import scope_path
        _u0 = _llm.usage_total()
        place = scope_path.place(self, category, coord, owner, surface, parent_canonical)
        where = None
        if place is None:                       # 값의 경로(B181 ② — 이름 규칙 카테고리는 `place.names()` 그대로)
            from core.build.extract_ctx import value_path
            where = value_path(row, field, self.doc_coord, coord=_name_of(coord), owner=_name_of(owner))
        (verdict, nid, conf, v), why = self._judge(surface, category, canonical, scoped,
                                                   parent_canonical, at, row, place=place, where=where, field=field)
        _u1 = _llm.usage_total()
        # **이 값 하나가 얼마를 썼나** — 대장이 적는다(B74 ②). 재는 자리가 쓰는
        # 자리와 같아야 화면과 실물이 갈리지 않는다(B73 ①과 같은 결).
        self.last = {"canonical": canonical, "verdict": verdict,
                     "path": v.get("path"), "confidence": conf,
                     # 판정 근거(B99 ⑨) — 좁힘 · 임베딩 최고 점수 · 불확실의 가장 가까운 후보
                     "narrow": v.get("narrow"), "emb_top": v.get("emb_top"),
                     "nearest": v.get("nearest"),
                     "layer": self.layer, "queue_kind": None,
                     "candidates_n": v.get("candidates_n", 0),
                     # 판정 재생의 키 몫(B106 ②) — 대장 행이 옮긴다
                     "category": category, "scope": parent_canonical if scoped_category else None,
                     "replay": why,                       # 재생하지 못한 사유 — 재판정 행의 표지(B106 ②)
                     "judge2": v.get("second"), "basis": v.get("basis"),   # 2차 판정(B123 ③ · 불렀을 때만) · 근거 지문(B167 ② — 판정에 오른 값만)
                     "apart": v.get("apart"),             # 같은 이름 · 같은 공정 줄기 · 다른 소유자 아래 노드(B142 ⑥)
                     "llm": {"calls": _u1["calls"] - _u0["calls"],
                             "in_tokens": _u1["prompt_tokens"] - _u0["prompt_tokens"],
                             "out_tokens": (_u1["completion_tokens"]
                                            - _u0["completion_tokens"])}}
        if gate_at is not None and not also_gate.same(gate_at, verdict, nid):
            return also_gate.miss(self, surface, category, prov, gate_at, verdict, v, nid)   # 문(B197 ①) — 세우지 않는다
        if verdict == MATCH:
            # 판정으로 붙은 표기는 **출처 LLM 매칭**으로 남는다(B101 ④) — 사전 히트·기억은 아니다
            _by = (None if (v.get("replayed_path") or v.get("path")) in ("dictionary", "memo", "self_coord", "path_compat",
                                                                         "none")
                   else {"by": "LLM 매칭", "confidence": round(float(conf or 0), 4),
                         "doc": self.doc_id})
            self._register(surface, nid, prov, key=canonical, by=_by)
            if prov not in self.g.get(nid)["provenance"]:
                self.g.get(nid)["provenance"].append(prov)
            self.buffer[norm(surface)] = nid
            self.last["node_id"] = nid
            return nid
        if self._skeleton_category(category):
            _MEMO[mkey] = verdict
            return self._skeleton_miss(surface, category, canonical, prov, verdict, coord=coord)

        extra = {"_scoped": True} if scoped and category in scope_categories(self.cfg) else {}
        # **부모 경로**(`scope`)와 **맨 이름**(`base_name` — 주소 접두를 뺀 자기 이름부)이다(B142 ⑤ — 옛 칸 `mirror_scope` ·
        # `mirror_name`). canonical을 되 파싱하지 않기 위해(A11-8) 조립 시점에 적어 둔다 — 판정의 경로 · 별칭 검사가
        # 읽는다(`naming.scope_of` · `base_name_of`). 스코프가 없는 카테고리는 부모가 이름에 실리지 않으므로 부모 경로도 없다.
        extra["scope"] = parent_canonical if scoped_category else None
        extra["base_name"] = norm(surface)
        nid = self.g.add_node(canonical, category, "auto", provenance=[prov], **extra)
        self._register(surface, nid, prov, key=canonical)
        self.last["queue_kind"] = "auto_node" if verdict == NEW else "uncertain_match"
        store.enqueue("auto_node" if verdict == NEW else "uncertain_match",
                      f"{'자동 생성' if verdict == NEW else '판정 불확실 — 신규로 생성'}"
                      f": {canonical} ({category})",
                      self.doc_id, {"node_id": nid, "canonical": canonical,
                                    "surface": surface, "provenance": prov,
                                    **({"nearest": self.last["nearest"]}
                                       if self.last.get("nearest") else {}),
                                    # 종결 명령이 층을 요구한다(B73 ④) — 자리표시자를
                                    # 남기면 사람이 그 줄을 그대로 칠 수 없다.
                                    "layer": self.layer})
        self.buffer[norm(surface)] = nid
        self.last["node_id"] = nid
        return nid

    def _invalid_category(self, surface, category, prov):
        """카테고리는 **운영 중에 발명되지 않는다**(카드 I3 · CH2 2.9 금지 목록) — 추출→구축의 신뢰 경계에서 이것이 유일한 강제
        지점이다(프롬프트 계약만으로는 층 어휘가 아닌 이름이 그래프에 심긴다) · 노드 0 · `invalid_category`."""
        store.enqueue("invalid_category", f"층이 선언하지 않은 카테고리 '{category}' — 노드를 만들지 않는다",
                      self.doc_id, {"surface": surface, "category": category, "provenance": prov})
        self.last = {"canonical": surface, "verdict": "gate_reject", "path": "none", "confidence": 0.0,
                     "layer": self.layer, "queue_kind": "invalid_category", "node_id": None}
        return None

    def _no_coord(self, surface, category, prov, coord_surface, belongs, guess=None):
        """좌표 없는 스코프 개체의 재료를 큐에 — 좌표가 비었으면 먼저 자리 추정(B183 — `place_guess.attach` · 표와 같은 함수 ·
        붙으면 그 노드 id) · 못 붙으면 `missing_field`(키 `process_ref` · 재료의 표지 `guess`) · 목록 밖 좌표 이름이면 그 표기의
        `orphan_anchor` 항목에 행으로(새 kind 0 · B56)."""
        from core.state.bootstrap import COORD_CATEGORY
        # 재료의 모양은 표의 연쇄 드롭과 같다(재시도 `_land_anchor_entry`가 같은 손으로 되살린다)
        item = {"surface": surface, "category": category, "target_layer": self.layer,
                **({"belongs_to": belongs} if belongs else {})}
        loc = (prov or "").split("#")[-1] or None
        from parser.normalizer import coord_refs
        many = coord_refs(coord_surface)
        if len(many) > 1:
            # 공정 목록(B125 ④) — 개체가 제 공정(`parent`)을 고르지 않았다 · 지어내지 않는다(같은 kind · 같은 재료 꼴)
            kind = "missing_field"
            store.enqueue_rows(kind, f"청크 공정이 둘 이상({' · '.join(many)})인데 '{surface}'({category})가 제 공정을 "
                                     f"고르지 않아 만들지 않았다 — 구조 표의 공정 고침 또는 추출의 parent",
                               self.doc_id, "process_ref",
                               {"field": "process_ref", "provenance": prov, "processes": many,
                                "dropped_entities": [item]}, locator=loc)
        elif many:
            coord_surface = many[0]
            kind = "orphan_anchor"
            # **실제 사유를 말한다**(B104 ①) — 표기 모호(골격 노드 여럿)와 목록 밖은 처방이 다르다
            why, cands = self.anchor_hold_of(coord_surface, prov=prov)
            store.enqueue_rows(kind, (f"좌표 '{coord_surface}'가 {why}" + (f"(— {' · '.join(cands)})" if cands else "")
                                      + f"라 '{surface}'를 만들지 않았다"
                                      if why else f"좌표 '{coord_surface}'가 골격 목록 밖이라 '{surface}'를 만들지 않았다"),
                               self.doc_id, norm(coord_surface),
                               {"surface": coord_surface, "category": COORD_CATEGORY,
                                "provenance": prov, "layer": self.layer,
                                **({"candidates": cands} if why else {}),
                                "dropped_entities": [item]}, locator=loc)
        else:
            from core.build import place_guess
            nid = place_guess.attach(self, surface, category, prov, **(guess or {}))
            if nid:
                return nid
            place_guess.hold(self.doc_id, prov, dict(item, guess=place_guess.mark(self.last)))
            return None
        self.last = {"canonical": surface, "verdict": "pending", "path": "none", "confidence": 0.0,
                     "layer": self.layer, "queue_kind": kind, "candidates_n": 0, "node_id": None,
                     "llm": {"calls": 0, "in_tokens": 0, "out_tokens": 0}}
        return None

    def _skeleton_category(self, category):
        """골격 카테고리인가(B94 ③) — 층 config `skeleton.category`(tree·flat). 빌더당 한 번 센다."""
        if not hasattr(self, "_sk_cats"):
            from core.state.catalog_sync import skeleton_layers
            self._sk_cats = set(skeleton_layers())
        return category in self._sk_cats

    def _memo_key(self, surface, canonical, category, parent):
        """기억의 열쇠 — (표기 · 카테고리 · 부모 스코프) + **판정 재료의 판**(골격 스냅샷 · 이 표기의 사전 항목) · 극성은 들지
        않는다(B198). 골격·사전이 바뀌면 열쇠가 달라져 기억을 쓰지 않는다(B100 ⑤)."""
        from core.state import store as _st
        sk = _st.path(_st.SKELETON_LIST)
        return (norm(canonical), category, parent, self.layer,
                sk.stat().st_mtime_ns if sk.exists() else None,
                tuple(sorted(set(self.dict.lookup(surface)) | set(self.dict.lookup(canonical)))))

    def _memo_replay(self, surface, category, canonical, prov, verdict, coord=None):
        """기억한 판정을 그대로 낸다 — 큐는 지금처럼 문서 × 표기 1건(행만 붙는다) · 대장 경로 `memo`."""
        self.last = {"canonical": canonical, "verdict": verdict, "path": "memo",
                     "confidence": 0.0, "layer": self.layer, "queue_kind": None,
                     "candidates_n": 0, "llm": {"calls": 0, "in_tokens": 0, "out_tokens": 0}}
        return self._skeleton_miss(surface, category, canonical, prov, verdict, coord=coord)

    def _skeleton_miss(self, surface, category, canonical, prov, verdict, coord=None):
        """**골격 카테고리 개체가 매칭이 아니다**(B94 ③ · B182 ①) — 좌표 골격 카테고리면 잠정 골격 노드(`provisional.from_entity` —
        세우는 손 하나 · 다르다 `auto_node` · 애매 합칠 후보 + `uncertain_match` · 부모 = 그 자리의 좌표) · 닫힌 분류(좌표 층 밖
        골격)와 세우지 못한 자리(골격 아래 새 단 등)는 노드 0 · `orphan_anchor`(골격에 별칭이 생기면 재시도 · 재인입이 붙인다).
        """
        from core.state.bootstrap import COORD_CATEGORY
        why = None
        if category == COORD_CATEGORY:
            from core.build import provisional
            nid, why = provisional.from_entity(self, surface, prov, verdict, self.last.get("nearest"), coord)
            if nid:
                self.buffer[norm(surface)] = nid
                m = self.made[nid]
                self.last.update(node_id=nid, canonical=self.g.get(nid)["canonical"], queue_kind=m["queue"],
                                 made={k: m[k] for k in ("answer", "parent", "queue")})
                return nid
        reason = (f"골격 카테고리 '{category}'로 뽑힌 '{surface}'가 " + (f"{why}라 세우지 않았다" if why else
                  "골격에 없다 — 노드를 만들지 않는다(닫힌 분류 · 같은 것이면 골격 ALIASES에)"))
        store.enqueue_rows("orphan_anchor", reason, self.doc_id, norm(surface),
                           {"surface": surface, "category": category, "provenance": prov,
                            "role": "entity", "verdict": verdict,
                            **({"gate": self.coord_gate[(prov, surface)]} if (prov, surface) in self.coord_gate else {})},
                           locator=(prov or "").split("#")[-1] or None)
        self.last.update(verdict="orphan", queue_kind="orphan_anchor", node_id=None,
                         canonical=canonical, **({"hold": why} if why else {}))
        return None

    # ---------------------------------------------------------------- attribute
    def put_attribute(self, node_id, name, value, context, prov, contextual):
        """맥락형은 `[{context, value, provenance}]`로 **병렬 저장**한다.

        충돌 판정은 **같은 context 그룹 안에서만** — deep-equal로 달라야 spec_conflict다.
        context가 다르면 충돌이 아니라 병렬 항목이고, 완전 동일이면 무시한다. **극성은 context의 한 열쇠다**(B198) — 출처
        행 · 청크의 `electrode_type`이 축 값이면 `context.polarity`(`polarity.of_prov` — 시스템이 쓴다 · 비면 넣지 않는다 = 공통) ·
        anode 규격과 cathode 규격은 충돌이 아니다.
        돌려주는 것은 결과 하나 — `ATTR_ADDED` · `ATTR_SAME` · `ATTR_CONFLICT` · None(노드 없음) — 산문 값이 센다(B120 ①).
        """
        n = self.g.get(node_id)
        if n is None:
            return None
        attrs = n.setdefault("attrs", {})
        if not contextual:
            # **단순형은 빈 context 그룹 하나로 취급한다**(3.6 규약 5) — 분기가 아니라
            # 특수 사례다. 구판은 deep-equal 없이 덮어써서 교차 출처의 다른 주장이
            # provenance째 소멸했다("충돌은 정보다" — 규약 6).
            context = {}
        from core.build import polarity as _pol
        pol = _pol.of_prov(prov)
        if pol:
            context = {**(context or {}), _pol.CTX: pol}
        items = attrs.setdefault(name, [])
        if not isinstance(items, list):                  # 구판 단순형 값의 승격
            items = attrs[name] = [items]
        for it in items:
            if it.get("context") == context:
                if it.get("value") == value:
                    if prov not in it["provenance"]:
                        it["provenance"].append(prov)
                    return ATTR_SAME
                store.enqueue("spec_conflict",
                              f"{n['canonical']}의 {name}: 같은 맥락에 다른 값",
                              self.doc_id,
                              {"node_id": node_id, "attr": name, "context": context,
                               "existing": it["value"], "incoming": value,
                               "provenance": prov})
                return ATTR_CONFLICT
        items.append({"context": context, "value": value, "provenance": [prov]})
        return ATTR_ADDED
