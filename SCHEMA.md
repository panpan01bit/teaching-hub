# 数据 Schema

三个文件，全部是 JSON，全部放在 `--data` 目录下。没有数据库。

---

## 1 `workspace.json` — 课程结构（人写 / 前端改）

```json
{
  "version": 1,
  "seededAt": "2026-09-18",
  "projects": [
    {
      "id": "econ101",                    // 唯一，URL 里用它
      "type": "course",                   // 自由字符串：course / competition / camp ...
      "name": "示例课程 A",
      "subtitle": "6 节次 · 项目制",
      "level": "高中",
      "status": "active",                 // active | done | paused
      "progress": 60,                     // 0-100
      "notes": "备注",
      "tags": ["demo"],
      "goals":   [ {"id": "g-1", "text": "6 节次资料齐备", "done": true} ],
      "sections": [
        {
          "id": "s-1",                    // 节次 id，错项画像按它聚合
          "title": "节次1 供需与价格",
          "order": 1,
          "path": "courses/econ101/week1",// 资料子目录（相对资料根目录）
          "status": "taught",             // draft | ready | taught
          "notes": "产出：……",
          "blocks": [
            {
              "id": "b-1",
              "kind": "knowledge",        // knowledge | case | activity | video | website | file | note
              "title": "需求曲线与移动",
              "body": "要点文本",
              "refs": ["courses/econ101/week1/case_banana.md"]   // 资料库相对路径
            }
          ]
        }
      ]
    }
  ],
  "links": [ {"id": "l-1", "title": "外部链接", "url": "https://…", "tags": []} ],
  "plans": [ {"id": "pl-1", "name": "备课板", "items": [{"ref": "b-1", "note": "Hook 5 分钟"}]} ]
}
```

约定：
- `section.path` 与 `block.refs` 都是**相对资料根目录**的相对路径，前端直接拼到站点根上打开。
- 批改时把 `project` + `section` 一起传进来，错项画像才知道该算到哪一节。

---

## 2 `index.json` — 资料索引（自动生成）

`POST /api/scan` 或启动时 `--scan` 生成。搜索只读这个文件，不碰磁盘。

```json
{
  "generated": "2026-09-18T10:39:15",
  "root": "/abs/path/to/material-root",
  "total": 3,
  "files": [
    {
      "p": "courses/econ101/week1/case_banana.md",  // 相对路径
      "n": "case_banana.md",                        // 文件名
      "e": "md",                                    // 扩展名（小写，无点）
      "s": 337,                                     // 字节数
      "m": 1789699000,                              // mtime（unix 秒）
      "x": "文件正文前 20000 字符"                   // 只对文本类文件抽取，其余为空串
    }
  ]
}
```

抽取正文的扩展名：`.md .txt .csv .json .html .htm .py .js .css`。
跳过目录：`.git .venv __pycache__ node_modules data` 及任何以 `.` 开头的目录。

---

## 3 `attempts.json` — 批改记录（自动生成，权限 600）

每次 `/api/mark` 追加一条。错项画像就是把它按 `project` + `section` 聚合。

```json
{
  "attempts": [
    {
      "id": "a-1789699320264",
      "ts": "2026-09-18T10:42:00",
      "project": "econ101",
      "section": "s-2",
      "student": "李四",              // 可空
      "judge": "deepseek/deepseek-v4-pro",
      "total": 9,
      "out_of": 10,
      "parts": {
        "第3题": {"marks": 3, "errors": ["未指出边界条件"]}
      }
    }
  ]
}
```

`/api/diagnostics` 的聚合口径：

| 字段 | 含义 |
|---|---|
| `score_rate` | 该节次累计得分 ÷ 累计满分，**升序排**（越低越该重讲） |
| `lost_parts` | 该节次里"没拿满分或被标记错误"的小问 → 出现次数，降序 |
| `attempts` | 该节次被批改的次数 |

弱项判定：某个小问**有 errors 条目**，或**得分低于该小问满分**（满分从 `parts` 里的
`[N]` 解析）。只靠 errors 会漏掉"评语里说了扣分但没填 errors"的情况——实测踩过。

---

## 学生数据与版本控制

`attempts.json` 含学生答案与姓名：默认 `.gitignore` 已排除 `data/`，落盘权限 600。
要长期留存请自行备份；要对外展示只导出聚合后的画像（`/api/diagnostics`），不要导出原文。
