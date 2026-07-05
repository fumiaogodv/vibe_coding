FROM python:3.12-slim

WORKDIR /app

# 安装依赖（利用 Docker 缓存层，先复制 requirements.txt）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目文件
COPY app.py .
COPY static/ static/
COPY templates/ templates/
COPY modules/ modules/

# 创建 tmp 目录
RUN mkdir -p tmp

EXPOSE 5000

# 生产环境使用 gunicorn，4 个工作进程
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "--timeout", "300", "app:create_app()"]
