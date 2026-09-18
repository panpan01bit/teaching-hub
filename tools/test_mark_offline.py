#!/usr/bin/env python3
"""离线测试 mark_script 的落盘与弱项判定（monkeypatch 掉模型调用，不花钱不联网）。

覆盖：
- part_max 从 "[N]" 解析
- weak 判定：有 errors 或得分低于满分
- weak_points 返回值与落盘记录一致（曾经不一致：实时说 (b) 弱，存档里没有）
- attempts.json 落盘
"""
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('hub_server2', HERE / 'hub' / 'server.py')
hub = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hub)

tmp = Path(tempfile.mkdtemp())
hub.DATA_DIR = tmp
hub.ATTEMPTS_PATH = lambda: tmp / 'attempts.json'

# --- 假造一个 paper_grader.mark_answer，返回固定结果 ---------------------------------
fake = type(sys)('paper_grader')


def fake_mark_answer(question, markscheme, answer, parts, out_of, provider, model, paper_id):
    assert out_of == 10, out_of
    return {'parts': {'(a)': {'marks': 1, 'justification': 'ok', 'errors': []},
                      '(b)': {'marks': 3, 'justification': '缺少一个要点', 'errors': []},
                      '(c)': {'marks': 1, 'justification': '事实错误', 'errors': ['不实陈述']}},
            'total': 5, 'out_of': out_of, 'raw': 'x' * 100}


fake.mark_answer = fake_mark_answer
sys.modules['paper_grader'] = fake

result = hub.mark_script({
    'answer': 'x' * 50,
    'question_text': 'Q', 'markscheme_text': 'MS',
    'parts': ['(a) [1]', '(b) [4]', '(c) [4]'], 'out_of': 10,
    'project': 'p', 'section': 's',
    'judge': {'provider': 'fake', 'model': 'fake-1'},
})

print('weak_points:', result['weak_points'])
print('total:', result['total'], '/', result['out_of'])

record = json.load(open(tmp / 'attempts.json', encoding='utf-8'))['attempts'][0]
print('存档 parts:', json.dumps(record['parts'], ensure_ascii=False))
print('存档 part_max:', record['part_max'])

assert result['weak_points'] == ['(b)', '(c)'], result['weak_points']
assert record['part_max'] == {'(a)': 1, '(b)': 4, '(c)': 4}, record['part_max']
assert record['parts']['(a)']['weak'] is False           # 满分且无 errors
assert record['parts']['(b)']['weak'] is True            # 没满分但 errors 为空 —— 关键用例
assert record['parts']['(c)']['weak'] is True            # 有 errors
assert 'raw' not in result, 'raw 不该返回给前端'
print('\n✓ 全部断言通过：满分小问不标弱，未满分小问标弱，存档与实时结果一致')
