#!/usr/bin/env python3
"""Hit the hub's /api/mark endpoint with the demo task + markscheme + a sample answer."""
import json, sys, urllib.error, urllib.request

HUB = 'http://127.0.0.1:8770'
DATA = '/Users/2/Desktop/AI_Root/teaching-hub/data'

payload = {
    'project': 'econ101',
    'section': 's-2',
    'student': '示例学生-李四',
    'question_file': 'courses/econ101/week2/task.md',        # 相对资料根目录
    'markscheme_file': 'courses/econ101/week2/markscheme.md',
    'parts': ['第1题 [3]', '第2题 [3]', '第3题 [4]'],
    'out_of': 10,
    'answer': open('/Users/2/Desktop/AI_Root/teaching-hub/examples/demo/student_answer.md',
                   encoding='utf-8').read(),
    'judge': {'provider': 'deepseek', 'model': 'deepseek-v4-pro'},
}

req = urllib.request.Request(HUB + '/api/mark', data=json.dumps(payload).encode('utf-8'),
                             headers={'Content-Type': 'application/json'})
try:
    with urllib.request.urlopen(req, timeout=600) as r:
        out = json.load(r)
except urllib.error.HTTPError as exc:
    print('HTTP', exc.code, exc.read().decode('utf-8', 'replace')[:400])
    sys.exit(1)

print('总分 %s/%s  attempt=%s' % (out.get('total'), out.get('out_of'), out.get('attempt_id')))
for k, v in (out.get('parts') or {}).items():
    print('  %-10s %s  %s' % (k, v['marks'], v['justification'][:80]))
    for e in v.get('errors') or []:
        print('      ! ' + e[:110])
print('需重点讲:', out.get('weak_points'))
print('错项画像:', json.dumps(json.load(urllib.request.urlopen(
    HUB + '/api/diagnostics', timeout=30)), ensure_ascii=False)[:300])
