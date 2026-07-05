"""
博客字幕阅读与金句感悟管理器
功能：字幕列表、手动上传、句子级别喜欢、句子级别收藏与感悟
"""
import json
import os
import re
from datetime import datetime

from flask import Blueprint, render_template, request, jsonify

bp = Blueprint(
    "blog_reader",
    __name__,
    template_folder="templates",
    static_folder="static",
)

MODULE_DIR = os.path.dirname(__file__)
SUBTITLES_DIR = os.path.join(MODULE_DIR, "subtitles")
LIKES_DIR = os.path.join(MODULE_DIR, "likes")
NOTES_DIR = os.path.join(MODULE_DIR, "notes")
DATA_DIR = os.path.join(MODULE_DIR, "data")
PROGRESS_FILE = os.path.join(DATA_DIR, "progress.json")

for d in [SUBTITLES_DIR, LIKES_DIR, NOTES_DIR, DATA_DIR]:
    os.makedirs(d, exist_ok=True)


def _load_json(filepath: str):
    if os.path.isfile(filepath):
        with open(filepath, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_json(filepath: str, data):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _safe_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "_", name).strip()


def _parse_to_lines(content: str) -> list[dict]:
    """将文件内容解析为行列表，跳过 SRT 序号和时间轴"""
    lines = []
    for text in content.split("\n"):
        text = text.strip()
        if not text:
            continue
        if re.match(r'^\d+$', text):
            continue
        if re.match(r'\d{2}:\d{2}:\d{2}', text):
            continue
        lines.append({"index": len(lines) + 1, "text": text})
    return lines


def _get_likes_filepath(filename: str) -> str:
    return os.path.join(LIKES_DIR, f"{_safe_filename(filename)}.json")


def _get_notes_dir(filename: str) -> str:
    d = os.path.join(NOTES_DIR, _safe_filename(filename))
    os.makedirs(d, exist_ok=True)
    return d


# ─── 页面路由 ─────────────────────────────────────────────────────────────────
@bp.route("/")
def index():
    """首页：字幕文件列表 + 上传"""
    files = []
    if os.path.isdir(SUBTITLES_DIR):
        for fname in sorted(os.listdir(SUBTITLES_DIR)):
            fpath = os.path.join(SUBTITLES_DIR, fname)
            if os.path.isfile(fpath) and fname.endswith((".txt", ".srt", ".md")):
                files.append(fname)
    progress = _load_json(PROGRESS_FILE)
    return render_template("blog_reader.html", files=files, progress=progress, view="list")


@bp.route("/read/<path:filename>")
def read_file(filename):
    """阅读页面"""
    filename = _safe_filename(filename)
    fpath = os.path.join(SUBTITLES_DIR, filename)
    if not os.path.isfile(fpath):
        return "文件不存在", 404

    with open(fpath, encoding="utf-8") as f:
        content = f.read()
    lines = _parse_to_lines(content)

    # 加载该文件的喜欢列表
    likes_data = _load_json(_get_likes_filepath(filename))
    liked_indices = likes_data.get("liked", [])  # [1, 3, 5, ...]

    progress = _load_json(PROGRESS_FILE)
    return render_template("blog_reader.html",
                           files=[], progress=progress,
                           view="reader", filename=filename,
                           lines=lines, content=content,
                           liked_indices=liked_indices)


# ─── API：文件上传 ────────────────────────────────────────────────────────────
@bp.route("/api/upload", methods=["POST"])
def upload_file():
    """上传字幕文件"""
    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify({"error": "请选择文件"}), 400

    if not file.filename.endswith((".txt", ".srt", ".md")):
        return jsonify({"error": "仅支持 .txt / .srt / .md 文件"}), 400

    save_name = _safe_filename(file.filename)
    save_path = os.path.join(SUBTITLES_DIR, save_name)
    file.save(save_path)
    return jsonify({"ok": True, "filename": save_name})


@bp.route("/api/delete/<path:filename>", methods=["DELETE"])
def delete_file(filename):
    """删除字幕文件及其关联的喜欢和收藏数据"""
    filename = _safe_filename(filename)
    fpath = os.path.join(SUBTITLES_DIR, filename)
    if not os.path.isfile(fpath):
        return jsonify({"error": "文件不存在"}), 404

    # 删除字幕文件
    os.remove(fpath)

    # 删除对应的喜欢数据
    likes_path = _get_likes_filepath(filename)
    if os.path.isfile(likes_path):
        os.remove(likes_path)

    # 删除对应的进度数据
    progress = _load_json(PROGRESS_FILE)
    if filename in progress:
        del progress[filename]
        _save_json(PROGRESS_FILE, progress)

    # 删除对应的收藏笔记目录
    notes_dir = os.path.join(NOTES_DIR, filename)
    if os.path.isdir(notes_dir):
        import shutil
        shutil.rmtree(notes_dir)

    return jsonify({"ok": True, "message": f"已删除「{filename}」及其所有关联数据"})


# ─── API：阅读进度 ────────────────────────────────────────────────────────────
@bp.route("/api/progress/<path:filename>", methods=["GET"])
def get_progress(filename):
    filename = _safe_filename(filename)
    progress = _load_json(PROGRESS_FILE)
    return jsonify({"paragraph_index": progress.get(filename, 0)})


@bp.route("/api/progress", methods=["POST"])
def save_progress():
    data = request.get_json()
    filename = _safe_filename(data.get("filename", ""))
    paragraph_index = data.get("paragraph_index", 0)
    if not filename:
        return jsonify({"error": "filename 不能为空"}), 400
    progress = _load_json(PROGRESS_FILE)
    progress[filename] = paragraph_index
    _save_json(PROGRESS_FILE, progress)
    return jsonify({"ok": True})


# ─── API：句子级别喜欢 ───────────────────────────────────────────────────────
@bp.route("/api/like", methods=["POST"])
def toggle_like_sentence():
    """切换某句话的喜欢状态"""
    data = request.get_json()
    filename = _safe_filename(data.get("filename", ""))
    index = data.get("index")
    text = data.get("text", "")

    if not filename or index is None:
        return jsonify({"error": "缺少参数"}), 400

    filepath = _get_likes_filepath(filename)
    likes_data = _load_json(filepath)
    liked = likes_data.get("liked", [])  # [1, 3, 5, ...]
    liked_items = likes_data.get("items", {})  # {"1": "text...", "3": "text..."}

    idx_str = str(index)
    if index in liked:
        liked.remove(index)
        liked_items.pop(idx_str, None)
    else:
        liked.append(index)
        liked_items[idx_str] = text

    liked.sort()
    likes_data = {"liked": liked, "items": liked_items}
    _save_json(filepath, likes_data)
    return jsonify({"ok": True, "liked": index in liked})


@bp.route("/api/likes", methods=["GET"])
def get_all_likes():
    """获取所有文件的喜欢句子"""
    result = {}
    if os.path.isdir(LIKES_DIR):
        for fname in os.listdir(LIKES_DIR):
            if fname.endswith(".json"):
                source_name = fname[:-5]  # 去掉 .json
                data = _load_json(os.path.join(LIKES_DIR, fname))
                items = data.get("items", {})
                if items:
                    result[source_name] = [
                        {"index": int(k), "text": v}
                        for k, v in sorted(items.items(), key=lambda x: int(x[0]))
                    ]
    return jsonify({"likes": result})


@bp.route("/api/likes/<path:filename>", methods=["GET"])
def get_file_likes(filename):
    """获取某个文件的喜欢句子"""
    filename = _safe_filename(filename)
    data = _load_json(_get_likes_filepath(filename))
    items = data.get("items", {})
    return jsonify({
        "liked": [
            {"index": int(k), "text": v}
            for k, v in sorted(items.items(), key=lambda x: int(x[0]))
        ]
    })


# ─── API：收藏与感悟（按字幕文件分文件夹） ────────────────────────────────────
@bp.route("/api/collect", methods=["POST"])
def collect_quote():
    """收藏金句，生成 .md 文件到 notes/{字幕文件名}/ 目录"""
    data = request.get_json()
    filename = _safe_filename(data.get("filename", ""))
    captured_text = data.get("captured_text", "").strip()

    if not filename or not captured_text:
        return jsonify({"error": "缺少参数"}), 400

    notes_dir = _get_notes_dir(filename)
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    short_text = re.sub(r'[\\/*?:"<>|\s\n]', '_', captured_text[:15]).strip("_")
    note_filename = f"{timestamp}_{short_text}.md"
    note_path = os.path.join(notes_dir, note_filename)

    md_content = f"""---
source_file: "{filename}"
captured_text: "{captured_text}"
created_at: "{now.strftime('%Y-%m-%d %H:%M:%S')}"
---

### 我的感悟
（在这里写下你的感悟...）
"""

    with open(note_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    return jsonify({"ok": True, "note_filename": note_filename, "message": f"已收藏"})


@bp.route("/api/collections", methods=["GET"])
def get_collections():
    """获取所有收藏，按字幕文件名分组"""
    result = {}
    if os.path.isdir(NOTES_DIR):
        for source_name in sorted(os.listdir(NOTES_DIR)):
            source_dir = os.path.join(NOTES_DIR, source_name)
            if not os.path.isdir(source_dir):
                continue
            notes = []
            for note_file in sorted(os.listdir(source_dir), reverse=True):
                if note_file.endswith(".md"):
                    note_path = os.path.join(source_dir, note_file)
                    with open(note_path, encoding="utf-8") as f:
                        content = f.read()
                    meta = _parse_front_matter(content)
                    notes.append({
                        "filename": note_file,
                        "captured_text": meta.get("captured_text", ""),
                        "created_at": meta.get("created_at", ""),
                    })
            if notes:
                result[source_name] = notes
    return jsonify({"collections": result})


@bp.route("/api/collections/<path:source_file>", methods=["GET"])
def get_file_collections(source_file):
    """获取某个字幕文件的所有收藏"""
    source_file = _safe_filename(source_file)
    source_dir = _get_notes_dir(source_file)
    notes = []
    for note_file in sorted(os.listdir(source_dir), reverse=True):
        if note_file.endswith(".md"):
            note_path = os.path.join(source_dir, note_file)
            with open(note_path, encoding="utf-8") as f:
                content = f.read()
            meta = _parse_front_matter(content)
            notes.append({
                "filename": note_file,
                "captured_text": meta.get("captured_text", ""),
                "created_at": meta.get("created_at", ""),
            })
    return jsonify({"notes": notes})


@bp.route("/api/notes/<path:note_filename>", methods=["GET"])
def get_note(note_filename):
    """读取单个笔记（note_filename 格式: 源文件名/笔记文件名）"""
    parts = note_filename.split("/", 1)
    if len(parts) != 2:
        return jsonify({"error": "路径格式错误"}), 400
    source_name, note_file = _safe_filename(parts[0]), parts[1]
    note_path = os.path.join(NOTES_DIR, source_name, note_file)
    if not os.path.isfile(note_path):
        return jsonify({"error": "笔记不存在"}), 404
    with open(note_path, encoding="utf-8") as f:
        content = f.read()
    meta = _parse_front_matter(content)
    reflection = content
    if "---" in content:
        p = content.split("---", 2)
        if len(p) >= 3:
            reflection = re.sub(r'^###\s*我的感悟\s*\n?', '', p[2]).strip()
    return jsonify({
        "filename": note_file,
        "source_file": source_name,
        "captured_text": meta.get("captured_text", ""),
        "created_at": meta.get("created_at", ""),
        "reflection": reflection,
    })


@bp.route("/api/notes/<path:note_filename>", methods=["PUT"])
def update_note(note_filename):
    """更新笔记感悟"""
    data = request.get_json()
    new_reflection = data.get("reflection", "")
    parts = note_filename.split("/", 1)
    if len(parts) != 2:
        return jsonify({"error": "路径格式错误"}), 400
    source_name, note_file = _safe_filename(parts[0]), parts[1]
    note_path = os.path.join(NOTES_DIR, source_name, note_file)
    if not os.path.isfile(note_path):
        return jsonify({"error": "笔记不存在"}), 404
    with open(note_path, encoding="utf-8") as f:
        content = f.read()
    if "---" in content:
        p = content.split("---", 2)
        if len(p) >= 3:
            front_matter = f"---{p[1]}---"
            new_content = f"{front_matter}\n\n### 我的感悟\n{new_reflection}\n"
            with open(note_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            return jsonify({"ok": True})
    return jsonify({"error": "笔记格式异常"}), 400


def _parse_front_matter(content: str) -> dict:
    meta = {}
    match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    if match:
        for line in match.group(1).split("\n"):
            if ":" in line:
                key, val = line.split(":", 1)
                meta[key.strip()] = val.strip().strip('"')
    return meta
