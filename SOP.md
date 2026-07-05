# Vibe Hub 项目施工与开发规范 (SOP)

## 项目结构总览

```
vibe_hub/
├── app.py                      # 主程序（不要修改！）
├── requirements.txt            # 项目依赖
├── templates/
│   └── index.html              # Hub 首页（不要修改！）
├── static/
│   └── style.css               # 全局样式
├── modules/                    # 功能模块目录（在这里新增）
│   ├── bilibili_subtitle/      # 示例：Bilibili 字幕抓取
│   │   ├── __init__.py
│   │   ├── meta.json           # 模块元信息（必须）
│   │   ├── routes.py           # 路由蓝图（必须）
│   │   ├── templates/          # 模块私有模板
│   │   └── static/             # 模块私有静态资源
│   └── speaker_diarization/    # 示例：AI 字幕角色分离
│       ├── __init__.py
│       ├── meta.json
│       ├── routes.py
│       ├── templates/
│       └── static/
└── SOP.md                      # 本文档
```

---

## 新增功能模块的完整步骤（傻瓜式）

假设你要新增一个叫做「图片压缩」的功能，按以下步骤操作即可。
**全程不需要修改 `app.py`、`templates/index.html` 或其他已有模块的任何代码。**

### 第一步：创建模块目录

在 `modules/` 下新建一个文件夹，文件夹名使用 **小写下划线命名法**：

```
modules/
└── image_compress/          ← 新建这个文件夹
```

### 第二步：创建 `__init__.py`

在模块文件夹内新建 `__init__.py`，写一行注释即可：

```python
# 图片压缩模块
```

### 第三步：创建 `meta.json`（必须）

这是主程序识别模块的**唯一凭证**。没有这个文件，模块不会被加载。

```json
{
    "name": "图片压缩",
    "description": "上传图片，自动压缩并下载。",
    "icon": "🖼️",
    "url_prefix": "/image-compress"
}
```

字段说明：

| 字段 | 必填 | 说明 |
|------|------|------|
| `name` | 是 | 模块显示名称，会出现在首页卡片上 |
| `description` | 是 | 一句话描述功能，出现在首页卡片上 |
| `icon` | 是 | 首页卡片图标，建议用 emoji |
| `url_prefix` | 是 | 该模块的 URL 前缀，必须唯一，以 `/` 开头 |

### 第四步：创建 `routes.py`（必须）

这是模块的后端逻辑文件，**必须定义一个名为 `bp` 的 Flask Blueprint 对象**：

```python
from flask import Blueprint, render_template

# ⚠️ 变量名必须叫 bp，Blueprint 名称建议与文件夹名一致
bp = Blueprint(
    "image_compress",           # Blueprint 名称（内部标识）
    __name__,                   # 固定写法
    template_folder="templates", # 指向模块自己的 templates 文件夹
    static_folder="static",     # 指向模块自己的 static 文件夹
)

@bp.route("/")
def index():
    return render_template("image_compress.html")

# ... 你的其他路由和逻辑 ...
```

### 第五步：创建模板和静态资源

在模块文件夹内创建 `templates/` 和 `static/` 目录：

```
modules/image_compress/
├── templates/
│   └── image_compress.html   ← 模块首页（必须用唯一名称，禁止 index.html）
└── static/
    └── style.css             ← 模块专用样式（可选）
```

模板中引用资源的方式：

```html
<!-- 引用全局样式 -->
<link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">

<!-- 引用模块自己的样式（用蓝图名.static） -->
<link rel="stylesheet" href="{{ url_for('image_compress.static', filename='style.css') }}">

<!-- 回首页链接（必须用 url_for，兼容反向代理） -->
<a href="{{ url_for('index') }}">← 返回 Hub 首页</a>
```

### 第六步：重启服务

```bash
python app.py
```

主程序启动时会自动扫描 `modules/` 目录，发现新模块并注册。首页会自动出现新功能卡片。

---

## 关键规范速查

### 命名规范

| 项目 | 规范 | 示例 |
|------|------|------|
| 模块文件夹名 | 小写 + 下划线 | `image_compress` |
| Blueprint 变量名 | **必须叫 `bp`** | `bp = Blueprint(...)` |
| meta.json 的 url_prefix | 以 `/` 开头，用连字符 | `/image-compress` |
| Blueprint 名称 | 与文件夹名一致 | `"image_compress"` |
| **模块主模板文件名** | **必须与模块文件夹名相同** | `templates/image_compress.html` |

> ⚠️ **重要：模板文件名冲突问题**
>
> Flask 查找模板时，应用级 `templates/` 目录**优先于**蓝图级 `templates/` 目录。
> 如果子模块的模板也叫 `index.html`，会与应用级首页 `templates/index.html` 冲突，
> 导致子模块页面渲染成 Hub 首页。**因此子模块模板必须使用唯一名称**，推荐与模块文件夹名同名。
>
> 在 `routes.py` 中使用：`render_template("image_compress.html")`（而非 `render_template("index.html")`）

### 绝对禁止

1. **不要修改 `app.py`** — 动态扫描机制会自动发现新模块
2. **不要修改 `templates/index.html`** — 首页会自动渲染所有已注册模块
3. **不要在 `routes.py` 中遗漏 `bp` 变量** — 主程序通过 `getattr(mod, "bp")` 获取蓝图
4. **不要省略 `meta.json`** — 这是模块被扫描的必要条件
5. **不要给子模块模板命名为 `index.html`** — 会与应用级首页冲突
6. **不要在模板中硬编码 URL 路径** — 所有链接和 JS fetch 地址必须使用 `url_for()`，否则反向代理下路径会失效

> ⚠️ **JS 中使用 API 路径的方式**：在 `<script>` 标签顶部定义常量，由 Jinja2 渲染：
> ```html
> <script>
> const API = {
>     fetchData: "{{ url_for('your_module.fetch') }}",
>     download:  "{{ url_for('your_module.download') }}",
> };
> // 后续使用 API.fetchData、API.download 作为 fetch() 的 URL
> </script>
> ```

### 推荐实践

- 每个模块保持完全独立，不依赖其他模块
- 模块间如需共享逻辑，提取到项目根目录的 `utils/` 公共目录
- 使用 `POST` 方法处理需要提交数据的接口
- 模块页面记得加返回首页链接 `<a href="{{ url_for('index') }}">← 返回 Hub 首页</a>`
- 临时文件统一放在各自模块下的 `tmp/` 目录，并注意清理

---

## 模块清单模板

新增模块时可复制以下模板，替换占位内容：

```
modules/{your_module_name}/
├── __init__.py                     # 注释即可
├── meta.json                       # 模块元信息
├── routes.py                       # Flask Blueprint 路由（必须定义 bp 变量）
├── templates/
│   └── {your_module_name}.html     # 模块页面（禁止命名为 index.html）
└── static/
    └── style.css                   # 模块样式（可留空）
```

按照以上 6 步操作，新功能即自动接入 Hub，零入侵主逻辑。
