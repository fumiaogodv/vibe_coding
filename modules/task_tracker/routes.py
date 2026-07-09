"""
周期性任务打卡与日记生成器模块
核心逻辑：基于"起始日"和"循环天数"自动计算当天需执行的任务。
"""
import json
import os
from datetime import date, datetime

from flask import Blueprint, render_template, request, jsonify

bp = Blueprint(
    "task_tracker",
    __name__,
    template_folder="templates",
    static_folder="static",
)

# 数据存放目录：Docker 中通过环境变量指向挂载卷；本地开发默认存模块目录
DATA_DIR = os.environ.get("TASK_TRACKER_DATA_DIR", os.path.dirname(__file__))
os.makedirs(DATA_DIR, exist_ok=True)
DATA_FILE = os.path.join(DATA_DIR, "data.json")


# ─── 数据读写工具 ────────────────────────────────────────────────────────────────
def _load_data() -> dict:
    """从 JSON 文件加载所有数据，文件不存在则返回空结构。"""
    if not os.path.isfile(DATA_FILE):
        return {"tasks": [], "next_id": 1}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_data(data: dict) -> None:
    """将数据写回 JSON 文件。"""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ─── 核心算法 ────────────────────────────────────────────────────────────────────
def is_due_today(task: dict, target_date: date | None = None) -> bool:
    """
    判断任务在指定日期是否需要执行。
    算法：(目标日期 - start_date) % 周期天数 == 0
    """
    if target_date is None:
        target_date = date.today()
    start = datetime.strptime(task["start_date"], "%Y-%m-%d").date()
    diff = (target_date - start).days
    return diff >= 0 and diff % task["cycle_days"] == 0


# ─── 页面路由 ────────────────────────────────────────────────────────────────────
@bp.route("/")
def index():
    """模块首页 — 今日打卡 + 任务管理。"""
    return render_template("task_tracker.html")


# ─── API：任务 CRUD ──────────────────────────────────────────────────────────────
@bp.route("/api/tasks", methods=["GET"])
def list_tasks():
    """获取所有任务列表。"""
    data = _load_data()
    return jsonify(data["tasks"])


@bp.route("/api/tasks", methods=["POST"])
def add_task():
    """添加新任务。请求体：{name, cycle_days}"""
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    cycle_days = body.get("cycle_days", 1)

    if not name:
        return jsonify({"error": "任务名称不能为空"}), 400
    try:
        cycle_days = int(cycle_days)
        if cycle_days < 1:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"error": "周期天数必须为正整数"}), 400

    data = _load_data()
    task = {
        "id": data["next_id"],
        "name": name,
        "cycle_days": cycle_days,
        "start_date": date.today().isoformat(),  # 默认起始日为今天
    }
    data["tasks"].append(task)
    data["next_id"] += 1
    _save_data(data)
    return jsonify(task), 201


@bp.route("/api/tasks/<int:task_id>", methods=["DELETE"])
def delete_task(task_id: int):
    """删除指定任务。"""
    data = _load_data()
    before = len(data["tasks"])
    data["tasks"] = [t for t in data["tasks"] if t["id"] != task_id]
    if len(data["tasks"]) == before:
        return jsonify({"error": "任务不存在"}), 404
    _save_data(data)
    return jsonify({"ok": True})


@bp.route("/api/tasks/<int:task_id>", methods=["PUT"])
def update_task(task_id: int):
    """更新任务信息。请求体：{name?, cycle_days?, start_date?}"""
    body = request.get_json(silent=True) or {}
    data = _load_data()
    for task in data["tasks"]:
        if task["id"] == task_id:
            if "name" in body:
                name = body["name"].strip()
                if not name:
                    return jsonify({"error": "任务名称不能为空"}), 400
                task["name"] = name
            if "cycle_days" in body:
                try:
                    cd = int(body["cycle_days"])
                    if cd < 1:
                        raise ValueError
                except (ValueError, TypeError):
                    return jsonify({"error": "周期天数必须为正整数"}), 400
                task["cycle_days"] = cd
            if "start_date" in body:
                # 简单校验日期格式
                try:
                    datetime.strptime(body["start_date"], "%Y-%m-%d")
                except ValueError:
                    return jsonify({"error": "日期格式无效，请使用 YYYY-MM-DD"}), 400
                task["start_date"] = body["start_date"]
            _save_data(data)
            return jsonify(task)
    return jsonify({"error": "任务不存在"}), 404


# ─── API：今日任务 ────────────────────────────────────────────────────────────────
@bp.route("/api/today", methods=["GET"])
def today_tasks():
    """返回今天需要执行的任务列表，标注每个任务是否到期。"""
    data = _load_data()
    today = date.today()
    result = []
    for task in data["tasks"]:
        due = is_due_today(task, today)
        result.append({
            **task,
            "is_due": due,
            "day_number": (today - datetime.strptime(task["start_date"], "%Y-%m-%d").date()).days + 1 if due else None,
        })
    return jsonify({
        "date": today.isoformat(),
        "tasks": result,
    })


# ─── API：Markdown 生成 ───────────────────────────────────────────────────────────
@bp.route("/api/generate-markdown", methods=["POST"])
def generate_markdown():
    """
    根据前端提交的打卡数据生成 Markdown 日记。
    请求体：
    {
        "date": "2026-07-05",
        "tasks": [
            {"id": 1, "name": "...", "checked": true, "detail": "哑铃飞鸟4组"},
            ...
        ],
        "notes": "全天随笔/饮食记录..."
    }
    """
    body = request.get_json(silent=True) or {}
    target_date = body.get("date", date.today().isoformat())
    tasks_data = body.get("tasks", [])
    notes = (body.get("notes") or "").strip()

    lines = []
    # 日期标题
    lines.append(f"## 日期：{target_date}")
    lines.append("")

    # 今日任务清单
    lines.append("### 今日任务清单")
    for t in tasks_data:
        name = t.get("name", "")
        checked = t.get("checked", False)
        detail = (t.get("detail") or "").strip()
        checkbox = "[x]" if checked else "[ ]"
        if checked and detail:
            lines.append(f"- {checkbox} {name}：{detail}")
        else:
            lines.append(f"- {checkbox} {name}")
    lines.append("")

    # 今日随笔与饮食
    lines.append("### 今日随笔与饮食")
    if notes:
        lines.append(notes)
    else:
        lines.append("（暂无记录）")

    markdown = "\n".join(lines)
    return jsonify({"markdown": markdown})
