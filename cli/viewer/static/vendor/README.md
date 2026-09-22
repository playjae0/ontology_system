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

**교체 절차**: 새 버전을 같은 방식으로 받아 파일명에 버전을 적고,
이 표의 해시를 갱신한 뒤 `static/index.html`의 `<script src>` 두 줄을 바꾼다.
렌더러는 인터페이스 하나(`render({nodes, edges, …})`) 뒤에 있어 교체가 화면 코드에
번지지 않는다.
