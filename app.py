"""
Vibe Hub - Web 工具集中枢
动态扫描 modules/ 目录，自动注册所有功能模块的 Flask Blueprint。
"""
import importlib
import os
import json

from flask import Flask, render_template
from werkzeug.middleware.proxy_fix import ProxyFix

MODULES_DIR = os.path.join(os.path.dirname(__file__), "modules")


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "vibe-hub-dev-key"

    # 支持反向代理：读取 X-Forwarded-Prefix 等头
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    registered_modules = []

    # 动态扫描 modules 目录下的所有子包
    for name in sorted(os.listdir(MODULES_DIR)):
        module_path = os.path.join(MODULES_DIR, name)

        # 只处理包含 meta.json 的目录
        if not os.path.isdir(module_path):
            continue
        meta_file = os.path.join(module_path, "meta.json")
        if not os.path.isfile(meta_file):
            continue

        with open(meta_file, encoding="utf-8") as f:
            meta = json.load(f)

        # 导入子包的 routes 模块，获取其中的 bp
        try:
            mod = importlib.import_module(f"modules.{name}.routes")
            bp = getattr(mod, "bp", None)
            if bp is None:
                print(f"[WARN] 模块 {name} 的 routes.py 中未定义 bp，已跳过")
                continue
            # 用 meta 中的 url_prefix 覆盖蓝图默认前缀
            url_prefix = meta.get("url_prefix", f"/{name}")
            app.register_blueprint(bp, url_prefix=url_prefix)

            registered_modules.append({
                "name": meta.get("name", name),
                "description": meta.get("description", ""),
                "url": url_prefix,
                "icon": meta.get("icon", "🔧"),
                "endpoint": f"{name}.index",
            })
            print(f"[OK] 已注册模块: {meta.get('name', name)} -> {url_prefix}")
        except Exception as e:
            print(f"[ERROR] 注册模块 {name} 失败: {e}")

    @app.route("/")
    def index():
        return render_template("index.html", modules=registered_modules)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=5000)
