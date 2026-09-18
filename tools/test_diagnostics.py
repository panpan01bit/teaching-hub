#!/usr/bin/env python3
"""错项画像的单元测试（不需要调模型）。

验证两件事：
1. 只带 `weak: true`（没有 errors 条目）的小问也要算进 lost_parts —— 这是实测踩过的坑：
   评语里写了扣分理由但 errors 为空时，旧逻辑会把它漏掉。
2. score_rate 按累计得分 ÷ 累计满分算，且升序排列（越低越该重讲）。
"""
import importlib.util
import json
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('hub_server', HERE / 'hub' / 'server.py')
hub = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hub)

tmp = Path(tempfile.mkdtemp())
hub.DATA_DIR = tmp
hub.ATTEMPTS_PATH = lambda: tmp / 'attempts.json'

records = [
    {'ts': '2026-09-18T10:00:00', 'project': 'p1', 'section': 's-1',
     'total': 8, 'out_of': 10,
     'parts': {'(b)': {'marks': 3, 'errors': [], 'weak': True},      # 只靠 weak 命中
               '(c)': {'marks': 2, 'errors': ['事实错误'], 'weak': True}}},
    {'ts': '2026-09-18T10:10:00', 'project': 'p1', 'section': 's-1',
     'total': 7, 'out_of': 10,
     'parts': {'(b)': {'marks': 4, 'errors': []},                    # 满分，不算弱项
               '(c)': {'marks': 2, 'errors': [], 'weak': True}}},
    {'ts': '2026-09-18T10:20:00', 'project': 'p2', 'section': 's-9',
     'total': 5, 'out_of': 10, 'parts': {'x': {'marks': 5, 'errors': []}}},
]
(tmp / 'attempts.json').write_text(json.dumps({'attempts': records}), encoding='utf-8')

out = hub.api_diagnostics()
print(json.dumps(out, ensure_ascii=False, indent=2))

rows = {r['section']: r for r in out['rows']}
assert rows['s-1']['attempts'] == 2, rows['s-1']
assert rows['s-1']['marks'] == 15 and rows['s-1']['out_of'] == 20
assert dict(rows['s-1']['lost_parts']) == {'(c)': 2, '(b)': 1}, rows['s-1']['lost_parts']
assert out['rows'][0]['section'] == 's-9', '得分率低的应排前面'
print('\n✓ 全部断言通过：weak-only 的小问被计入，满分小问不计入，排序正确')
