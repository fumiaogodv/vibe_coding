"""
Bilibili 字幕抓取与下载模块
参考 Chrome 扩展示例的抓取逻辑，用 Python + Flask 重新实现。
核心流程：bvid → 获取 aid/cid → /x/player/wbi/v2 获取字幕列表 → 下载字幕内容
"""
import hashlib
import functools
import json
import os
import re
import time
import urllib.parse

import requests
from flask import Blueprint, render_template, request, jsonify, send_file, current_app

bp = Blueprint(
    "bilibili_subtitle",
    __name__,
    template_folder="templates",
    static_folder="static",
)

# ─── WBI 签名 ────────────────────────────────────────────────────────────────
MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
    27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
    37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4,
    22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52,
]

_wbi_cache = {"img": "", "sub": "", "ts": 0}


def _get_mixin_key(raw: str) -> str:
    return functools.reduce(lambda s, i: s + raw[i], MIXIN_KEY_ENC_TAB, "")[:32]


def _get_wbi_keys(session: requests.Session) -> tuple[str, str]:
    now = time.time()
    if _wbi_cache["img"] and now - _wbi_cache["ts"] < 300:
        return _wbi_cache["img"], _wbi_cache["sub"]

    resp = session.get(
        "https://api.bilibili.com/x/web-interface/nav",
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json().get("data", {})
    wbi_img = data.get("wbi_img", {})
    img_key = wbi_img.get("img_url", "").rsplit("/", 1)[-1].split(".")[0]
    sub_key = wbi_img.get("sub_url", "").rsplit("/", 1)[-1].split(".")[0]
    _wbi_cache.update({"img": img_key, "sub": sub_key, "ts": now})
    return img_key, sub_key


def sign_wbi(params: dict, session: requests.Session) -> dict:
    img_key, sub_key = _get_wbi_keys(session)
    mixin_key = _get_mixin_key(img_key + sub_key)
    params["wts"] = int(time.time())
    params = dict(sorted(params.items()))
    query = urllib.parse.urlencode(params)
    params["w_rid"] = hashlib.md5((query + mixin_key).encode()).hexdigest()
    return params


# ─── Cookie 处理 ──────────────────────────────────────────────────────────────
def _load_default_cookie() -> str:
    """从 modules/cookie.md 读取默认 SESSDATA（如果存在）"""
    cookie_file = os.path.join(os.path.dirname(__file__), "cookie.md")
    if os.path.isfile(cookie_file):
        with open(cookie_file, encoding="utf-8") as f:
            val = f.read().strip()
            if val:
                return val
    return ""


def _normalize_cookie(raw: str) -> str:
    """将各种格式的 Cookie 统一为 Cookie 头格式"""
    raw = raw.strip()
    if not raw:
        return ""
    if "SESSDATA=" in raw:
        return raw
    return f"SESSDATA={raw}"


def _build_session(user_cookie: str = "") -> requests.Session:
    """
    构建带完整请求头和 Cookie 的 Session。
    模拟浏览器行为，获取所有必要的反爬 Cookie。
    """
    import uuid as _uuid

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Referer": "https://www.bilibili.com",
        "Origin": "https://www.bilibili.com",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    })

    # Step 1: 通过 SPI 接口获取 buvid3 和 buvid4（B 站指纹设备 ID）
    try:
        spi_resp = session.get(
            "https://api.bilibili.com/x/frontend/finger/spi",
            timeout=10,
        )
        spi_data = spi_resp.json().get("data", {})
        buvid3 = spi_data.get("b_3", "")
        buvid4 = spi_data.get("b_4", "")
        if buvid3:
            session.cookies.set("buvid3", buvid3, domain=".bilibili.com",
                                path="/")
        if buvid4:
            session.cookies.set("buvid4", buvid4, domain=".bilibili.com",
                                path="/")
    except Exception:
        pass

    # Step 2: 设置 b_nut（时间戳 Cookie）和 b_lsid（会话 ID）
    now_ts = int(time.time())
    session.cookies.set("b_nut", str(now_ts), domain=".bilibili.com", path="/")
    # b_lsid 格式: 103_XXXXXXXX (8位随机大写hex)
    lsid_hex = _uuid.uuid4().hex[:8].upper()
    session.cookies.set("b_lsid", f"103_{lsid_hex}",
                        domain=".bilibili.com", path="/")

    # Step 3: 访问首页获取更多基础 Cookie（bili_ticket 等）
    try:
        session.get("https://www.bilibili.com", timeout=10)
    except Exception:
        pass

    # Step 4: 获取 bili_ticket（进一步降低风控概率）
    try:
        ticket_resp = session.post(
            "https://api.bilibili.com/bapis/bilibili.api.ticket.v1.Ticket/GenWebTicket",
            json={"key_id": "ec02"},
            timeout=10,
        )
        ticket_data = ticket_resp.json().get("data", {})
        ticket = ticket_data.get("ticket", "")
        if ticket:
            session.cookies.set("bili_ticket", ticket,
                                domain=".bilibili.com", path="/")
            session.cookies.set("bili_ticket_expires",
                                str(ticket_data.get("created_at", now_ts + 259200)),
                                domain=".bilibili.com", path="/")
    except Exception:
        pass

    # Step 5: 叠加用户 Cookie（优先前端输入，其次 cookie.md）
    cookie_val = _normalize_cookie(user_cookie) or _normalize_cookie(_load_default_cookie())
    if cookie_val:
        session.cookies.set("SESSDATA", cookie_val.replace("SESSDATA=", ""),
                            domain=".bilibili.com", path="/")
    return session


# ─── 核心业务函数 ─────────────────────────────────────────────────────────────
def extract_bvid(url: str) -> str | None:
    """从各种 B 站链接格式中提取 BV 号"""
    match = re.search(r"(BV[\w]{10})", url)
    if match:
        return match.group(1)
    # b23.tv 短链接
    if "b23.tv" in url:
        try:
            resp = requests.head(url, allow_redirects=True, timeout=10,
                                 headers={"User-Agent": "Mozilla/5.0"})
            match = re.search(r"(BV[\w]{10})", resp.url)
            if match:
                return match.group(1)
        except Exception:
            pass
    return None


def get_video_info(bvid: str, session: requests.Session) -> dict:
    """获取视频基本信息（aid、cid、分P列表等）"""
    params = sign_wbi({"bvid": bvid}, session)
    resp = session.get(
        "https://api.bilibili.com/x/web-interface/view",
        params=params,
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise ValueError(f"获取视频信息失败: {data.get('message', '未知错误')}")
    return data["data"]


def get_subtitle_list(aid: int, cid: int, session: requests.Session) -> list:
    """
    获取字幕列表 — 使用与 Chrome 扩展相同的接口。
    Chrome 扩展直接用 credentials: 'include' 调用，不带 WBI 签名。
    """
    # 方式一：不带 WBI 签名（与 Chrome 扩展一致）
    try:
        resp = session.get(
            "https://api.bilibili.com/x/player/wbi/v2",
            params={"aid": aid, "cid": cid},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") == 0:
            subtitles = data.get("data", {}).get("subtitle", {}).get("subtitles", [])
            if subtitles:
                return [s for s in subtitles if s.get("subtitle_url")]
    except Exception:
        pass

    # 方式二：带 WBI 签名
    params = sign_wbi({"aid": aid, "cid": cid}, session)
    resp = session.get(
        "https://api.bilibili.com/x/player/wbi/v2",
        params=params,
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise ValueError(f"获取字幕列表失败: {data.get('message', '未知错误')}")

    subtitles = data.get("data", {}).get("subtitle", {}).get("subtitles", [])
    return [s for s in subtitles if s.get("subtitle_url")]


def download_subtitle(subtitle_url: str, session: requests.Session) -> dict:
    """下载字幕 JSON 内容"""
    if subtitle_url.startswith("//"):
        subtitle_url = "https:" + subtitle_url
    resp = session.get(subtitle_url, timeout=15)
    resp.raise_for_status()
    return resp.json()


def to_plain_text(subtitle_data: dict) -> str:
    """提取纯文本（与示例 extractJsonContentToText 一致）"""
    return "\n".join(item.get("content", "") for item in subtitle_data.get("body", []))


def to_timestamped_text(subtitle_data: dict) -> str:
    """带时间戳的文本"""
    lines = []
    for item in subtitle_data.get("body", []):
        start = item.get("from", 0)
        text = item.get("content", "")
        h = int(start // 3600)
        m = int((start % 3600) // 60)
        s = int(start % 60)
        if h > 0:
            lines.append(f"[{h:02d}:{m:02d}:{s:02d}] {text}")
        else:
            lines.append(f"[{m:02d}:{s:02d}] {text}")
    return "\n".join(lines)


def to_srt(subtitle_data: dict) -> str:
    """转换为 SRT 格式"""
    srt_lines = []
    for i, item in enumerate(subtitle_data.get("body", []), 1):
        start = item.get("from", 0)
        end = item.get("to", start + 2)
        content = item.get("content", "")
        srt_lines.append(str(i))
        srt_lines.append(f"{_fmt_srt_time(start)} --> {_fmt_srt_time(end)}")
        srt_lines.append(content)
        srt_lines.append("")
    return "\n".join(srt_lines)


def _fmt_srt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _safe_filename(name: str) -> str:
    return re.sub(r'[\s\\/*?:"<>|=\^$#`~\n]', '_', name).strip()[:100]


# ─── 路由 ─────────────────────────────────────────────────────────────────────
@bp.route("/")
def index():
    # 检查是否有已保存的 Cookie
    has_cookie = bool(_load_default_cookie())
    return render_template("bilibili_subtitle.html", has_cookie=has_cookie)


@bp.route("/cookie/save", methods=["POST"])
def save_cookie():
    """保存 Cookie 到本地文件"""
    cookie_val = request.form.get("cookie", "").strip()
    if not cookie_val:
        return jsonify({"error": "Cookie 不能为空"}), 400
    cookie_file = os.path.join(os.path.dirname(__file__), "cookie.md")
    with open(cookie_file, "w", encoding="utf-8") as f:
        f.write(cookie_val)
    return jsonify({"ok": True, "message": "Cookie 已保存，后续使用会自动加载"})


@bp.route("/cookie/clear", methods=["POST"])
def clear_cookie():
    """清除已保存的 Cookie"""
    cookie_file = os.path.join(os.path.dirname(__file__), "cookie.md")
    if os.path.isfile(cookie_file):
        with open(cookie_file, "w", encoding="utf-8") as f:
            f.write("")
    return jsonify({"ok": True, "message": "Cookie 已清除"})


@bp.route("/cookie/status", methods=["GET"])
def cookie_status():
    """查询当前 Cookie 状态"""
    val = _load_default_cookie()
    return jsonify({
        "has_cookie": bool(val),
        "preview": val[:15] + "..." if len(val) > 15 else val,
    })


@bp.route("/fetch", methods=["POST"])
def fetch_subtitles():
    """抓取字幕的 API 端点"""
    url = request.form.get("url", "").strip()
    cookie = request.form.get("cookie", "").strip()
    page_index = int(request.form.get("page_index", 0))
    subtitle_index = int(request.form.get("subtitle_index", 0))

    if not url:
        return jsonify({"error": "请输入视频链接"}), 400

    bvid = extract_bvid(url)
    if not bvid:
        return jsonify({"error": "无法从链接中提取 BV 号，请检查链接格式"}), 400

    session = _build_session(cookie)

    try:
        # 1. 获取视频信息（拿到 aid、cid、分P列表）
        video_info = get_video_info(bvid, session)
        title = video_info.get("title", "未知标题")
        aid = video_info.get("aid")
        pages = video_info.get("pages", [])

        if not pages:
            return jsonify({"error": "该视频无分P信息"}), 400

        page_list = [
            {"cid": p["cid"], "part": p.get("part", f"P{i+1}"), "page": p["page"]}
            for i, p in enumerate(pages)
        ]

        if page_index >= len(pages):
            page_index = 0
        target_page = pages[page_index]
        cid = target_page["cid"]
        part_name = target_page.get("part", "")

        # 2. 用 aid + cid 获取字幕列表（与 Chrome 扩展一致）
        subtitles = get_subtitle_list(aid, cid, session)
        if not subtitles:
            return jsonify({
                "error": "该视频没有可用的字幕。",
                "hint": "提示：部分 AI 字幕需要登录才能获取，请在高级选项中填入你的 B 站 SESSDATA Cookie。",
                "title": title,
                "pages": page_list,
            }), 404

        subtitle_list = []
        for sub in subtitles:
            subtitle_list.append({
                "lan": sub.get("lan", ""),
                "lan_doc": sub.get("lan_doc", "未知语言"),
                "subtitle_url": sub.get("subtitle_url", ""),
                "type": sub.get("type", 0),
            })

        if subtitle_index >= len(subtitles):
            subtitle_index = 0
        sub = subtitles[subtitle_index]
        subtitle_url = sub.get("subtitle_url", "")
        lang = sub.get("lan_doc", "未知语言")

        # 3. 下载字幕内容
        subtitle_data = download_subtitle(subtitle_url, session)
        plain_text = to_plain_text(subtitle_data)
        timestamped_text = to_timestamped_text(subtitle_data)
        srt_text = to_srt(subtitle_data)

        display_title = title
        if len(pages) > 1:
            display_title = f"{title} - P{target_page['page']}"
            if part_name:
                display_title += f" {part_name}"

        return jsonify({
            "title": display_title,
            "raw_title": title,
            "language": lang,
            "count": len(subtitle_data.get("body", [])),
            "plain_text": plain_text,
            "text": timestamped_text,
            "srt_text": srt_text,
            "raw": subtitle_data,
            "pages": page_list,
            "subtitles": subtitle_list,
            "current_page": page_index,
        })

    except requests.RequestException as e:
        return jsonify({"error": f"网络请求失败: {str(e)}"}), 502
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"发生未知错误: {str(e)}"}), 500


@bp.route("/send-to-reader", methods=["POST"])
def send_to_reader():
    """将字幕发送到博客字幕阅读器模块"""
    text = request.form.get("text", "")
    filename = request.form.get("filename", "subtitle")

    if not text:
        return jsonify({"error": "没有可保存的内容"}), 400

    safe_name = _safe_filename(filename)
    # 保存到 blog_reader/subtitles/ 目录
    reader_dir = os.path.join(os.path.dirname(__file__), "..", "blog_reader", "subtitles")
    os.makedirs(reader_dir, exist_ok=True)
    filepath = os.path.join(reader_dir, f"{safe_name}.txt")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(text)

    return jsonify({"ok": True, "message": f"已发送到阅读器：{safe_name}.txt"})


@bp.route("/download", methods=["POST"])
def download():
    """下载字幕文件"""
    text = request.form.get("text", "")
    filename = request.form.get("filename", "subtitle")
    fmt = request.form.get("format", "txt")
    srt_text = request.form.get("srt_text", "")
    raw_str = request.form.get("raw", "{}")

    if not text and not srt_text:
        return jsonify({"error": "没有可下载的内容"}), 400

    tmp_dir = os.path.join(current_app.root_path, "tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    safe_name = _safe_filename(filename)

    if fmt == "json":
        filepath = os.path.join(tmp_dir, f"{safe_name}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(raw_str)
        dl_name = f"{safe_name}.json"
    elif fmt == "srt":
        filepath = os.path.join(tmp_dir, f"{safe_name}.srt")
        if not srt_text:
            try:
                srt_text = to_srt(json.loads(raw_str))
            except json.JSONDecodeError:
                return jsonify({"error": "字幕数据解析失败"}), 400
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(srt_text)
        dl_name = f"{safe_name}.srt"
    else:
        filepath = os.path.join(tmp_dir, f"{safe_name}.txt")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(text)
        dl_name = f"{safe_name}.txt"

    return send_file(filepath, as_attachment=True, download_name=dl_name)
