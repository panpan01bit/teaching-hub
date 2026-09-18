# teaching-hub · 教学资料中台（通用骨架）

[English](#english) | 中文

一个**零依赖、纯本地**的教学资料中台：把一个课程资料文件夹索引成可搜索的资料库，用
`workspace.json` 管理课程/节次/知识点，并内置「✍️ 批改台」——按评分标准给学生答案打分，
再把失分聚合成本班错项画像，告诉你下一节该重讲什么。

从真实的备课工作台里抽出的**通用骨架**：不含任何真实课程、学生或受版权保护的考试材料，
只带一份自造的示例数据，克隆下来就能跑。

## 它解决什么问题

老师的资料散在几十个文件夹里，检索靠记忆；作业批完就丢了，看不出班级共性弱项。
这个中台把两件事接在一起：**资料索引** + **批改记录** → **按节次的弱项排行**。

## 快速开始

```bash
git clone <this repo> && cd teaching-hub

# 用仓库自带的示例数据启动（示例资料在 examples/demo/files）
mkdir -p data && cp examples/demo/workspace.json data/workspace.json
python3 hub/server.py --root examples/demo/files --data ./data --port 8770 --scan
# 打开 http://127.0.0.1:8770/hub/
```

指向你自己的资料目录：

```bash
python3 hub/server.py --root ~/我的课程资料 --data ./data --port 8770 --scan
```

### 启用批改台（可选）

批改依赖 [paper-grader](https://github.com/)——那是一个独立的评分/评测工具包，
用 Hermes CLI 调用各家模型。装好它之后：

```bash
PAPER_GRADER_PATH=/path/to/paper-grader python3 hub/server.py --root ... --data ./data
```

没设这个变量时，中台的搜索、资料管理照常工作，只有「开始批改」会提示未启用。

## 页面

| 页面 | 用途 |
|---|---|
| 总览 | 全部项目卡片、节次、内容块数量 |
| 项目详情 | 节次 → 知识点/案例/活动，一键跳到「找这节资料」或「批改这一节」 |
| 资源库 | 按**文件名和文档正文**搜全库，显示命中片段 |
| ✍️ 批改台 | 贴学生答案 + 评分标准 → 逐小问得分、失分理由、错误清单；下方是错项画像与最近批改 |
| 说明 | 安全边界与数据文件位置 |

## API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/ping` | 健康检查，返回资料根目录与数据目录 |
| GET | `/api/data` | 读取 `workspace.json` |
| POST | `/api/save` | 保存 `workspace.json`（只允许写这座一个文件） |
| POST | `/api/scan` | 重建资料索引 |
| GET | `/api/scanstate` | 索引时间与文件数 |
| GET | `/api/search?q=` | 全库搜索（文件名 + 正文） |
| POST | `/api/mark` | 按评分标准批改一份答案 |
| GET | `/api/attempts?limit=` | 批改历史 |
| GET | `/api/diagnostics` | 错项画像（按节次聚合，低分在前） |

`/api/mark` 请求体：

```json
{
  "project": "econ101", "section": "s-2", "student": "李四",
  "question_file": "courses/econ101/week2/task.md",
  "markscheme_file": "courses/econ101/week2/markscheme.md",
  "parts": ["第1题 [3]", "第2题 [3]", "第3题 [4]"], "out_of": 10,
  "answer": "……学生答案全文……",
  "judge": {"provider": "deepseek", "model": "deepseek-v4-pro"}
}
```

`question_file` / `markscheme_file` 也可以换成 `question_text` / `markscheme_text` 直接传正文。

## 安全边界

- 资料根目录**只读**；写入只发生在 `--data` 目录内（`index.json` / `workspace.json` / `attempts.json`）。
- 只绑定 `127.0.0.1`。
- `attempts.json` 含学生答案，落盘权限 `600`，且默认在 `.gitignore` 里。
- 路径解析拒绝任何逃出资料根目录的相对路径。

## 目录结构

```
hub/server.py      本地服务器 + API（标准库，无框架）
site/              前端（hash 路由 SPA，无构建步骤）
examples/demo/     自造示例数据：workspace.json + 3 份资料 + 1 份学生答案
tools/test_mark.py 批改接口的端到端测试脚本
SCHEMA.md          workspace.json / index.json / attempts.json 字段定义
```

## 局限

- 批改分数适合**发现问题**，不适合当最终成绩：实测同一答案换评委，125 分里能差 4–6 分。
- 索引只对纯文本类文件抽取正文（`.md/.txt/.csv/.json/.html/.py/.js/.css`）。
  PDF/DOCX/PPTX 需要你先转成文本（paper-grader 仓库里有相应提示）。
- 单机单用户，没有鉴权——不要暴露到公网。

MIT License.

---

## English

A **dependency-free, fully local** teaching-material hub: index a course folder into a
searchable library, manage courses → sessions → knowledge points in `workspace.json`, and use
the built-in **marking desk** to grade student answers against a markscheme and aggregate the
lost marks into a per-session weakness ranking — so you know what to reteach.

This is the generic skeleton extracted from a real lesson-prep workbench. It ships no real
course material, no student data and no copyrighted exam content — only a synthetic demo.

```bash
mkdir -p data && cp examples/demo/workspace.json data/workspace.json
python3 hub/server.py --root examples/demo/files --data ./data --port 8770 --scan
# open http://127.0.0.1:8770/hub/
```

Marking is optional and depends on [paper-grader]; enable it with
`PAPER_GRADER_PATH=/path/to/paper-grader`. Everything else works without it.

**Safety**: the material root is read-only (writes only inside `--data`), bound to `127.0.0.1`,
`attempts.json` is chmod 600 and git-ignored, and path resolution refuses anything outside the
material root.

**Caveat**: AI marks are for *finding problems*, not for final grades — the same script marked
by two different judge models differed by 4–6 marks out of 125 in our testing.
