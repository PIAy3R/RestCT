# 使用Python 3.8作为基础镜像
FROM python:3.9

# 设置工作目录
WORKDIR /app

# 复制项目文件到容器中
COPY . /app/

# 安装项目依赖项和spacy模型文件
RUN pip install --no-cache-dir -r requirements.txt

# 暴露项目需要的端口（如果需要）
EXPOSE 8000

# 启动应用程序
CMD ["python", "src/resct.py"]
