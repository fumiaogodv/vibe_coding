"""
AI 字幕角色分离模块（功能二）
使用小米 Mimo API，批量处理字幕文件，智能识别并分离对话角色。
"""
import json
import os
import re
import time

import requests
from flask import Blueprint, render_template, request, jsonify, send_file, current_app, Response

bp = Blueprint(
    "speaker_diarization",
    __name__,
    template_folder="templates",
    static_folder="static",
)

# ─── AI 配置（写死在后端）─────────────────────────────────────────────────────
AI_API_BASE = "https://token-plan-cn.xiaomimimo.com/v1"
AI_API_KEY = "tp-c2akalznnw7cbzdrd3d8bjvkch7s31udxkp0yvy31cqr6brm"
AI_MODEL = "mimo-v2.5"


# ─── 字幕解析 ─────────────────────────────────────────────────────────────────
def parse_srt(text: str) -> list[dict]:
    """解析 SRT 格式字幕，返回 [{index, start, end, text}, ...]"""
    blocks = re.split(r'\n\s*\n', text.strip())
    results = []
    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) < 3:
            continue
        # 第一行为序号，第二行为时间轴，其余为文本
        try:
            idx = int(lines[0].strip())
        except ValueError:
            continue
        time_match = re.match(
            r'(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,\.]\d{3})',
            lines[1].strip()
        )
        if not time_match:
            continue
        content = ' '.join(lines[2:]).strip()
        if content:
            results.append({
                "index": idx,
                "start": time_match.group(1),
                "end": time_match.group(2),
                "text": content,
            })
    return results


def parse_plain_text(text: str) -> list[dict]:
    """解析纯文本格式，每行一句"""
    results = []
    for i, line in enumerate(text.strip().split('\n'), 1):
        line = line.strip()
        if line:
            results.append({"index": i, "text": line})
    return results


def parse_subtitle(text: str) -> list[dict]:
    """自动检测格式并解析"""
    # 检测是否为 SRT 格式
    if re.search(r'\d{2}:\d{2}:\d{2}[,\.]\d{3}\s*-->', text):
        return parse_srt(text)
    return parse_plain_text(text)


# ─── AI 调用 ──────────────────────────────────────────────────────────────────
def call_mimo_ai(messages: list[dict], temperature: float = 0.15) -> str:
    """调用小米 Mimo API"""
    resp = requests.post(
        f"{AI_API_BASE}/chat/completions",
        headers={
            "Authorization": f"Bearer {AI_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": AI_MODEL,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 4096,
        },
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"].strip()


def build_batch_prompt(lines: list[dict], prev_speakers: list[str] | None = None) -> str:
    """
    为一批字幕行构建 Prompt。
    让 AI 一次性识别多行的说话人，大幅减少 API 调用次数。
    """
    line_block = "\n".join(f"[{l['index']}] {l['text']}" for l in lines)

    history_hint = ""
    if prev_speakers:
        history_hint = f"\n\n之前最近几行的说话人分配（供参考延续）：\n{chr(10).join(prev_speakers[-5:])}"

    prompt = f"""你是一个字幕角色分离专家。以下是字幕文件中的连续对话内容（已按行编号）。
请逐行判断每句话的说话人角色。

规则：
1. 根据对话的语境、语气、称呼、逻辑关系来判断说话人。
2. 如果这句话明显是上一个说话人继续说的（话题延续、语气连贯、句子被拆分），返回相同角色。
3. 如果明显换了一个人（回答问题、语气突变、不同称呼），返回新角色。
4. 角色名使用 "角色A"、"角色B"、"角色C" ... 的简洁格式。
5. 如果有明确的旁白/解说/独白，可命名为 "旁白"。
6. 如果无法确定，倾向于沿用上一句的角色。
{history_hint}

需要分析的对话内容：
{line_block}

请严格按以下 JSON 格式返回（不要包含任何其他文字）：
{{"results": [{{"index": 行号, "speaker": "角色X"}}, ...]}}"""

    return prompt


def parse_ai_response(content: str) -> list[dict]:
    """解析 AI 返回的 JSON，兼容各种格式"""
    content = content.strip()
    # 去掉 markdown 代码块
    if content.startswith("```"):
        content = re.sub(r'^```(?:json)?\s*', '', content)
        content = re.sub(r'\s*```$', '', content)
        content = content.strip()

    data = json.loads(content)
    if isinstance(data, dict) and "results" in data:
        return data["results"]
    if isinstance(data, list):
        return data
    return []


# ─── 主处理流程 ───────────────────────────────────────────────────────────────
def process_subtitles(sentences: list[dict], batch_size: int = 30):
    """
    生成器：批量处理字幕，通过 yield 返回进度和结果。
    每次处理 batch_size 行，前面有 5 行重叠作为上下文。
    """
    total = len(sentences)
    all_results = []
    speaker_map = {}  # index -> speaker
    overlap = 5  # 上下文重叠行数
    i = 0

    while i < total:
        # 确定当前批次范围
        batch_start = max(0, i - overlap) if i > 0 else 0
        batch_end = min(total, i + batch_size)
        batch = sentences[batch_start:batch_end]

        # 获取之前的说话人分配作为参考
        prev_speakers = []
        if all_results:
            for r in all_results[-5:]:
                prev_speakers.append(f"[{r['index']}] {r['speaker']}")

        # 构建 Prompt 并调用 AI
        prompt = build_batch_prompt(batch, prev_speakers)
        batch_label = f"处理第 {i+1}-{batch_end} 行（共 {total} 行）"

        try:
            raw_response = call_mimo_ai([
                {"role": "system", "content": "你是字幕角色分离专家，只输出 JSON。"},
                {"role": "user", "content": prompt},
            ])
            parsed = parse_ai_response(raw_response)

            # 只取当前需要的行（跳过重叠部分的前面行）
            for item in parsed:
                idx = item.get("index")
                speaker = item.get("speaker", "未知")
                if idx is not None and idx > len(all_results):
                    speaker_map[idx] = speaker

        except Exception as e:
            # 失败时沿用上一句的角色
            for j in range(i + 1, batch_end + 1):
                if j not in speaker_map:
                    prev = speaker_map.get(j - 1, "角色A")
                    speaker_map[j] = prev
            yield {
                "type": "error",
                "message": f"{batch_label} 出错: {str(e)}，已沿用上一句角色",
                "progress": batch_end / total,
            }

        # 整理当前批次结果
        for j in range(i + 1, batch_end + 1):
            if j <= len(sentences):
                s = sentences[j - 1]
                all_results.append({
                    "index": s["index"],
                    "text": s["text"],
                    "speaker": speaker_map.get(j, "角色A"),
                })

        yield {
            "type": "progress",
            "message": batch_label,
            "progress": batch_end / total,
            "processed": batch_end,
            "total": total,
        }

        i = batch_end
        # 批次间短暂间隔，避免触发限流
        if i < total:
            time.sleep(0.5)

    # 最终结果
    yield {
        "type": "done",
        "results": all_results,
        "total": total,
    }


# ─── 路由 ─────────────────────────────────────────────────────────────────────
@bp.route("/")
def index():
    return render_template("speaker_diarization.html")


@bp.route("/process", methods=["POST"])
def process():
    """SSE 流式处理字幕角色分离"""
    subtitle_text = request.form.get("subtitle_text", "").strip()
    uploaded_file = request.files.get("subtitle_file")

    if uploaded_file and uploaded_file.filename:
        subtitle_text = uploaded_file.read().decode("utf-8")

    if not subtitle_text:
        return jsonify({"error": "请上传字幕文件或粘贴字幕文本"}), 400

    # 解析字幕
    sentences = parse_subtitle(subtitle_text)
    if not sentences:
        return jsonify({"error": "字幕内容为空或格式无法识别"}), 400

    if len(sentences) > 5000:
        return jsonify({"error": "字幕过长（超过 5000 行），请分段处理"}), 400

    batch_size = int(request.form.get("batch_size", 30))

    def generate():
        for event in process_subtitles(sentences, batch_size):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@bp.route("/download", methods=["POST"])
def download():
    """下载角色分离后的字幕文件"""
    data = request.form.get("data", "[]")
    fmt = request.form.get("format", "txt")

    try:
        results = json.loads(data)
    except json.JSONDecodeError:
        return jsonify({"error": "数据解析失败"}), 400

    tmp_dir = os.path.join(current_app.root_path, "tmp")
    os.makedirs(tmp_dir, exist_ok=True)

    if fmt == "txt":
        filepath = os.path.join(tmp_dir, "diarized_subtitle.txt")
        lines = []
        for item in results:
            lines.append(f"[{item['speaker']}] {item['text']}")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        dl_name = "diarized_subtitle.txt"
    elif fmt == "json":
        filepath = os.path.join(tmp_dir, "diarized_subtitle.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        dl_name = "diarized_subtitle.json"
    elif fmt == "csv":
        filepath = os.path.join(tmp_dir, "diarized_subtitle.csv")
        import csv
        with open(filepath, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["序号", "角色", "内容"])
            for item in results:
                writer.writerow([item.get("index", ""), item["speaker"], item["text"]])
        dl_name = "diarized_subtitle.csv"
    elif fmt == "srt":
        filepath = os.path.join(tmp_dir, "diarized_subtitle.srt")
        srt_lines = []
        for i, item in enumerate(results, 1):
            srt_lines.append(str(i))
            start = item.get("start", "00:00:00,000")
            end = item.get("end", "00:00:02,000")
            srt_lines.append(f"{start} --> {end}")
            srt_lines.append(f"[{item['speaker']}] {item['text']}")
            srt_lines.append("")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(srt_lines))
        dl_name = "diarized_subtitle.srt"
    else:
        return jsonify({"error": "不支持的格式"}), 400

    return send_file(filepath, as_attachment=True, download_name=dl_name)
