FROM python:3.12-slim

# 设置工作目录
WORKDIR /app

# 安装依赖
RUN pip install flask gunicorn gevent

# 复制项目文件
COPY . .

# 创建uploads目录
RUN mkdir -p uploads

# 暴露端口
EXPOSE 80

# 启动服务
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:80", "app:app"]