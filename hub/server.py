#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""teaching-hub — 本地教学资料中台（通用骨架）。

一个零依赖的本地网站：把一整个课程资料文件夹索引成可搜索的资料库，
用 workspace.json 管理课程/节次/知识点，并内置「批改台」（按评分标准给学生答案打分、
再把失分聚合成本班错项画像）。

设计约束
--------
* 只读资料根目录；写入只发生在 --data 指定的目录内。
* 只绑定 127.0.0.1。
* 批改功能依赖 paper-grader（可选）：设 PAPER_GRADER_PATH 指向它即可启用。

用法
----
    python3 hub/server.py --root ~/我的课程资料 --data ./data --port 8770
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote

HUB_DIR = Path(__file__).resolve().parent
SITE_DIR = HUB_DIR.parent / 'site'

ROOT = Path('.').resolve()          # 资料根目录（只读）
DATA_DIR = Path('./data').resolve()  # 工作数据（可写）
PORT = 8770

INDEX_PATH = lambda: DATA_DIR / 'index.json'
WORKSPACE_PATH = lambda: DATA_DIR / 'workspace.json'
ATTEMPTS_PATH = lambda: DATA_DIR / 'attempts.json'

LIVE_MIME = {'.html': 'text/html; charset=utf-8', '.js': 'application/javascript',
             '.css': 'text/css; charset=utf-8', '.json': 'application/json',
             '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
             '.gif': 'image/gif', '.svg': 'image/svg+xml', '.pdf': 'application/pdf',
             '.md': 'text/plain; charset=utf-8', '.txt': 'text/plain; charset=utf-8'}

TEXT_EXT = {'.md', '.txt', '.csv', '.json', '.html', '.htm', '.py', '.js', '.css'}
SKIP_DIRS = {'.git', '.venv', '__pycache__', 'node_modules', '.DS_Store', 'data'}
MAX_TEXT_CHARS = 20000

_locks = {'workspace': threading.Lock(), 'attempts': threading.Lock(), 'mark': threading.Lock()}


# ------------------------------------------------------------------ helpers

def read_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            pass
    return default


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(tmp, path)


def safe_resolve(rel: str) -> Path | None:
    """Resolve a library-relative path, refusing anything outside ROOT."""
    try:
        target = (ROOT / rel).resolve()
    except Exception:
        return None
    if target == ROOT or ROOT in target.parents:
        return target
    return None


def extract_text(path: Path) -> str:
    if path.suffix.lower() not in TEXT_EXT:
        return ''
    try:
        return path.read_text(encoding='utf-8', errors='replace')[:MAX_TEXT_CHARS]
    except Exception:
        return ''


def build_index() -> dict:
    files = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith('.')]
        for name in filenames:
            if name.startswith('.') or name.startswith('~$'):
                continue
            p = Path(dirpath) / name
            try:
                st = p.stat()
            except OSError:
                continue
            rel = str(p.relative_to(ROOT))
            files.append({'p': rel, 'n': name, 'e': p.suffix.lstrip('.').lower(),
                          's': st.st_size, 'm': int(st.st_mtime),
                          'x': extract_text(p)})
    idx = {'generated': time.strftime('%Y-%m-%dT%H:%M:%S'), 'root': str(ROOT),
           'total': len(files), 'files': files}
    write_json(INDEX_PATH(), idx)
    return idx


# ------------------------------------------------------------------ API

def api_search(qs) -> dict:
    idx = read_json(INDEX_PATH(), {'files': []})
    q = (qs.get('q', [''])[0] or '').strip().lower()
    limit = min(int(qs.get('limit', ['60'])[0] or 60), 500)
    terms = q.split()
    out = []
    for e in idx.get('files', []):
        score = 0
        if not terms:
            score = 1
        for t in terms:
            if t in e['n'].lower():
                score += 100
            if t in e['p'].lower():
                score += 20
            if t in (e.get('x') or '').lower():
                score += 5
        if score:
            snippet = ''
            for t in terms:
                i = (e.get('x') or '').lower().find(t)
                if i >= 0:
                    snippet = (e.get('x') or '')[max(0, i - 60):i + 160].replace('\n', ' ')
                    break
            out.append({'path': e['p'], 'name': e['n'], 'ext': e['e'], 'size': e['s'],
                        'score': score, 'snippet': snippet})
    out.sort(key=lambda r: -r['score'])
    return {'total': len(out), 'results': out[:limit]}


def api_diagnostics(project: str = '', section: str = '') -> dict:
    data = read_json(ATTEMPTS_PATH(), {'attempts': []})
    rows: dict = {}
    for a in data['attempts']:
        if project and a.get('project') != project:
            continue
        if section and a.get('section') != section:
            continue
        if not a.get('out_of'):
            continue
        key = (a.get('project', ''), a.get('section', '') or '(未绑定节次)')
        row = rows.setdefault(key, {'attempts': 0, 'marks': 0, 'out_of': 0, 'lost_parts': {}})
        row['attempts'] += 1
        row['marks'] += a.get('total', 0)
        row['out_of'] += a.get('out_of', 0)
        for part, v in (a.get('parts') or {}).items():
            if v.get('errors') or v.get('weak'):
                row['lost_parts'][part] = row['lost_parts'].get(part, 0) + 1
    out = []
    for (proj, sec), row in rows.items():
        out.append({'project': proj, 'section': sec, 'attempts': row['attempts'],
                    'marks': row['marks'], 'out_of': row['out_of'],
                    'score_rate': round(row['marks'] / row['out_of'], 3) if row['out_of'] else 0,
                    'lost_parts': sorted(row['lost_parts'].items(), key=lambda kv: -kv[1])})
    out.sort(key=lambda r: r['score_rate'])
    return {'rows': out, 'total_attempts': len(data['attempts'])}


def mark_script(payload: dict) -> dict:
    """Bridge to paper-grader (optional dependency)."""
    pg_path = os.environ.get('PAPER_GRADER_PATH', '')
    if pg_path and pg_path not in sys.path:
        sys.path.insert(0, pg_path)
    try:
        from paper_grader import mark_answer
    except Exception as exc:
        raise ValueError('未启用批改功能：设好 PAPER_GRADER_PATH 指向 paper-grader 仓库'
                         '（当前值 %r）：%s' % (pg_path, exc))

    def field(text_key, file_key):
        text = str(payload.get(text_key) or '').strip()
        if text:
            return text
        rel = str(payload.get(file_key) or '').strip()
        if not rel:
            return ''
        target = safe_resolve(rel)
        if not target or not target.is_file():
            raise ValueError('%s 指向的文件不存在：%s' % (file_key, rel))
        return target.read_text(encoding='utf-8', errors='replace')

    answer = str(payload.get('answer') or '').strip()
    if len(answer) < 20:
        raise ValueError('答案内容太短（至少 20 字符）')
    question = field('question_text', 'question_file')
    markscheme = field('markscheme_text', 'markscheme_file')
    if not question or not markscheme:
        raise ValueError('题目和评分标准都要有（文本或资料库路径）')

    parts = [str(p).strip() for p in (payload.get('parts') or []) if str(p).strip()]
    out_of = int(payload.get('out_of') or 0) or sum(
        int(m) for m in re.findall(r'\[(\d+)\]', ' '.join(parts)))
    judge = payload.get('judge') or {}
    with _locks['mark']:
        result = mark_answer(question, markscheme, answer, parts, out_of,
                             provider=str(judge.get('provider') or 'deepseek'),
                             model=str(judge.get('model') or 'deepseek-v4-pro'),
                             paper_id=str(payload.get('paper_id') or 'paper'))
    result.pop('raw', None)

    # 每个小问的满分，从 parts 里的 [N] 解析；弱项 = 有 errors 或没拿满分
    part_max = {}
    for p in parts:
        m = re.search(r'\[(\d+)\]', p)
        if m:
            part_max[re.sub(r'\s*\[.*$', '', p).strip()] = int(m.group(1))

    def is_weak(k, v):
        cap = part_max.get(k)
        return bool(v.get('errors')) or (cap is not None and v['marks'] < cap)

    record = {'id': 'a-%d' % int(time.time() * 1000),
              'ts': time.strftime('%Y-%m-%dT%H:%M:%S'),
              'project': str(payload.get('project') or ''),
              'section': str(payload.get('section') or ''),
              'student': str(payload.get('student') or ''),
              'judge': '%s/%s' % (judge.get('provider'), judge.get('model')),
              'total': result['total'], 'out_of': result['out_of'],
              'part_max': part_max,     # 存档满分，便于日后回填/重算弱项
              'parts': {k: {'marks': v['marks'], 'errors': v.get('errors', []),
                            'weak': is_weak(k, v)} for k, v in result['parts'].items()}}
    with _locks['attempts']:
        data = read_json(ATTEMPTS_PATH(), {'attempts': []})
        data['attempts'].append(record)
        write_json(ATTEMPTS_PATH(), data)
    try:
        os.chmod(ATTEMPTS_PATH(), 0o600)
    except OSError:
        pass
    result['attempt_id'] = record['id']
    result['weak_points'] = [k for k, v in result['parts'].items() if is_weak(k, v)]
    return result


# ------------------------------------------------------------------ HTTP

class Handler(BaseHTTPRequestHandler):
    server_version = 'teaching-hub/0.1'

    def log_message(self, fmt, *args):      # 安静一点
        pass

    # -- utils -----------------------------------------------------
    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path: Path, download=False):
        if not path.is_file():
            return self._json({'error': 'not found'}, 404)
        body = path.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', LIVE_MIME.get(path.suffix.lower(),
                                                       'application/octet-stream'))
        if download:
            self.send_header('Content-Disposition', 'attachment; filename="%s"' % path.name)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> bytes:
        return self.rfile.read(int(self.headers.get('Content-Length') or 0))

    # -- GET -------------------------------------------------------
    def do_GET(self):
        u = urlparse(self.path)
        path, qs = unquote(u.path), parse_qs(u.query)

        if path == '/api/ping':
            return self._json({'ok': True, 'root': str(ROOT), 'data': str(DATA_DIR)})
        if path == '/api/data':
            return self._json(read_json(WORKSPACE_PATH(), {'projects': [], 'links': []}))
        if path == '/api/search':
            return self._json(api_search(qs))
        if path == '/api/scanstate':
            idx = read_json(INDEX_PATH(), {'total': 0, 'generated': ''})
            return self._json({'generated': idx.get('generated', ''), 'total': idx.get('total', 0)})
        if path == '/api/attempts':
            data = read_json(ATTEMPTS_PATH(), {'attempts': []})
            limit = min(int(qs.get('limit', ['50'])[0] or 50), 500)
            return self._json({'attempts': data['attempts'][-limit:][::-1],
                               'count': len(data['attempts'])})
        if path == '/api/diagnostics':
            return self._json(api_diagnostics((qs.get('project', [''])[0] or ''),
                                              (qs.get('section', [''])[0] or '')))
        if path in ('/', '/hub', '/hub/'):
            return self._file(SITE_DIR / 'index.html')
        if path.startswith('/hub/'):
            target = (SITE_DIR / path[len('/hub/'):]).resolve()
            if SITE_DIR in target.parents and target.is_file():
                return self._file(target)
            return self._file(SITE_DIR / 'index.html')

        target = safe_resolve(path.lstrip('/'))
        if target and target.is_file():
            return self._file(target, download='download' in qs)
        return self._json({'error': 'not found'}, 404)

    # -- POST ------------------------------------------------------
    def do_POST(self):
        u = urlparse(self.path)
        path = unquote(u.path)
        if path == '/api/save':
            try:
                payload = json.loads(self._body().decode('utf-8'))
                if payload.get('name') != 'workspace' or not isinstance(payload.get('data'), dict):
                    raise ValueError('只允许保存 workspace')
                with _locks['workspace']:
                    write_json(WORKSPACE_PATH(), payload['data'])
                return self._json({'ok': True})
            except Exception as exc:
                return self._json({'error': str(exc)}, 400)
        if path == '/api/scan':
            idx = build_index()
            return self._json({'ok': True, 'total': idx['total']})
        if path == '/api/mark':
            try:
                return self._json(mark_script(json.loads(self._body().decode('utf-8'))))
            except ValueError as exc:
                return self._json({'error': str(exc)}, 400)
            except Exception as exc:
                return self._json({'error': '批改失败：%s' % exc}, 500)
        return self._json({'error': 'not found'}, 404)


def main(argv=None):
    global ROOT, DATA_DIR, PORT
    ap = argparse.ArgumentParser(description='本地教学资料中台（通用骨架）')
    ap.add_argument('--root', default='.', help='资料根目录（只读）')
    ap.add_argument('--data', default='./data', help='工作数据目录（可写）')
    ap.add_argument('--port', type=int, default=8770)
    ap.add_argument('--scan', action='store_true', help='启动前先建一次索引')
    args = ap.parse_args(argv)

    ROOT = Path(args.root).expanduser().resolve()
    DATA_DIR = Path(args.data).expanduser().resolve()
    PORT = args.port
    if not ROOT.is_dir():
        print('资料根目录不存在：%s' % ROOT)
        return 1
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if args.scan or not INDEX_PATH().exists():
        idx = build_index()
        print('已建索引：%d 个文件' % idx['total'])

    url = 'http://127.0.0.1:%d/hub/' % PORT
    print('教学资料中台已启动: %s' % url)
    print('资料根目录: %s' % ROOT)
    print('工作数据目录: %s' % DATA_DIR)
    ThreadingHTTPServer(('127.0.0.1', PORT), Handler).serve_forever()
    return 0


if __name__ == '__main__':
    sys.exit(main())
