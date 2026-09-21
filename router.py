# -*- coding: utf-8 -*-
"""칸 0.1 — 층 폴더 자동 발견 — 등록 배선이 없다 (CH6 6.1).

층을 추가하는 일이 "layers/ 아래 폴더 하나 + config.json 하나"로 끝나야
config-only가 성립한다. 여기에 층 이름을 적는 순간 그것이 배선이 된다.

**자리는 상태 루트다**(B79 ① · `$ONTO_HOME/layers/`) — 층 자산은 사내가 고치는
②등록 단이라 코드 폴더에 살면 코드 교체가 사내 골격을 되돌린다. 자리는 묻고
(`core/paths.layers()`) 여기서 조립하지 않는다.
"""


def discover():
    from core import paths              # 함수 안 import — 모듈 수준 순환을 만들지 않는다
    root = paths.layers()
    if not root.exists():
        return []
    return sorted(p.name for p in root.iterdir()
                  if (p / "config.json").exists())
