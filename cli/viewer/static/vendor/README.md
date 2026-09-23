# 벤더링 — 렌더러 (B82 ②)

**CDN 0은 외부 내려받기 금지이지 라이브러리 금지가 아니다**(허브 판정 2026-09-22).
MIT 라이브러리를 **고정 버전으로 레포에 두고** 서버가 로컬로 내준다 —
사내망에서 화면이 비어 뜨면 검증 도구가 아니다(외부 URL 0을 회귀가 잰다).

받은 자리는 **npm 레지스트리의 배포 tarball**이고, 아래 해시가 그 실물이다.

| 파일 | 패키지 | 버전 | 라이선스 | sha256 | 바이트 |
|---|---|---|---|---|---:|
| `sigma-3.0.1.min.js` | sigma | 3.0.1 | MIT (`LICENSE.sigma.txt`) | `9ba1b304d35acd4361b86d474fc136bb4bf78fd45065da15f1c43ce2f7e52e3e` | 186,849 |
| `graphology-0.25.4.umd.min.js` | graphology | 0.25.4 | MIT (`LICENSE.graphology.txt`) | `641ea047e2f414dead999769d62567ce3c6f1ddc334f1e728bd5edb19d337977` | 74,221 |

출처:

- `sigma-3.0.1.min.js` ← https://registry.npmjs.org/sigma/-/sigma-3.0.1.tgz → package/dist/sigma.min.js
- `graphology-0.25.4.umd.min.js` ← https://registry.npmjs.org/graphology/-/graphology-0.25.4.tgz → package/dist/graphology.umd.min.js

## 힘 배치는 벤더링하지 않았다 (B84 ③ · D-165 ①)

요청문은 `graphology-layout-forceatlas2`를 같은 방식으로 벤더링하라고 했고, **실물을
받아 확인한 결과 브라우저 번들이 없다**:

```
$ curl -sO https://registry.npmjs.org/graphology-layout-forceatlas2/-/graphology-layout-forceatlas2-0.10.1.tgz
$ tar tzf … → package/{index,iterate,helpers,defaults,worker,webworker}.js
$ package.json → "main": "index.js" · browser/dist 없음 · "dependencies": {"graphology-utils": …}
$ head index.js → require('graphology-utils/is-graph') · require('./iterate.js') …
```

CommonJS + 외부 패키지 요구라 `<script src>`로 실을 수 없고, 실으려면 번들러(npm·webpack)를
들여야 한다 — **실행 시 외부 내려받기 0**과 **코어 필수 외부 의존 0**의 정신에서 멀어진다.
요청문이 준 대안대로 **직접 짠 결정적 힘 배치**를 `static/render.js::layoutForce`에 두었다
(난수 0 · 고정 반복 · 계층 좌표를 초기값으로). 그래서 **이 표에 파일이 늘지 않았다.**

**교체 절차**: 새 버전을 같은 방식으로 받아 파일명에 버전을 적고,
이 표의 해시를 갱신한 뒤 `static/index.html`의 `<script src>` 두 줄을 바꾼다.
렌더러는 인터페이스 하나(`render({nodes, edges, …})`) 뒤에 있어 교체가 화면 코드에
번지지 않는다.
