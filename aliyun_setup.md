# 阿里云服务器配置指南

## 1. 创建密钥对

### 操作步骤
1. 在阿里云控制台的"登录凭证"部分：
   - 选择 **"密钥对"**
   - 点击 **"创建密钥对"**
   - 输入密钥对名称，如 `file-share-key`
   - 点击 **"确定"**
   - **立即下载私钥文件**（重要！仅能下载一次）
   - 将私钥文件保存到安全位置，如 `C:\Users\你的用户名\Downloads\file-share-key.pem`

### 2. 配置密钥对权限

#### Windows用户：
1. 下载并安装PuTTY：https://www.putty.org/
2. 下载PuTTYgen：用于转换密钥格式
3. 打开PuTTYgen：
   - 选择 **"Load"**
   - 选择 **"All Files (*.*)"**
   - 选择下载的私钥文件 `file-share-key.pem`
   - 点击 **"Save private key"**
   - 保存为 `.ppk` 文件，如 `file-share-key.ppk`

#### Linux/Mac用户：
```bash
# 设置私钥文件权限（必须）
chmod 600 ~/Downloads/file-share-key.pem
```

### 3. 使用密钥对登录服务器

#### 使用PuTTY（Windows）：
1. 打开PuTTY
2. 在"Session"中：
   - 输入服务器公网IP
   - 端口：22
   - 连接类型：SSH
3. 在"Connection" → "SSH" → "Auth"中：
   - 点击 **"Browse"**
   - 选择 `.ppk` 文件
4. 点击 **"Open"** 连接服务器
5. 用户名：`root`（Ubuntu/CentOS默认用户名）

#### 使用Terminal（Linux/Mac）：
```bash
# 连接服务器
ssh -i ~/Downloads/file-share-key.pem root@你的服务器公网IP
```

## 4. 部署文件分享站

### 1. 更新系统
```bash
# Ubuntu
apt update && apt upgrade -y

# CentOS
yum update -y
```

### 2. 安装Python和Flask
```bash
# Ubuntu
apt install python3 python3-pip python3-venv -y

# CentOS
yum install python3 python3-pip -y

# 安装Flask
pip3 install flask
```

### 3. 部署文件分享站
```bash
# 创建项目目录
mkdir -p /opt/file-sharing
cd /opt/file-sharing

# 复制项目文件（从本地复制到服务器）
# 使用scp命令：
# scp -i /path/to/私钥.pem -r /本地项目目录/* root@服务器IP:/opt/file-sharing/

# 或直接在服务器上创建文件：

# 创建app.py
cat > app.py << 'EOF'
from flask import Flask, render_template, request, redirect, url_for, send_from_directory
import os
import uuid

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return redirect(url_for('index'))
    file = request.files['file']
    if file.filename == '':
        return redirect(url_for('index'))
    if file:
        filename = str(uuid.uuid4()) + '_' + file.filename
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        return redirect(url_for('files'))

@app.route('/files')
def files():
    files = os.listdir(app.config['UPLOAD_FOLDER'])
    files.sort(key=lambda x: os.path.getmtime(os.path.join(app.config['UPLOAD_FOLDER'], x)), reverse=True)
    return render_template('files.html', files=files)

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)
EOF

# 创建templates目录和HTML文件
mkdir -p templates

# 创建index.html
cat > templates/index.html << 'EOF'
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>文件分享站</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; background-color: #f0f0f0; }
        .container { background-color: white; padding: 30px; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
        h1 { text-align: center; color: #333; }
        .upload-form { margin-top: 20px; text-align: center; }
        .file-input { margin: 10px 0; padding: 10px; }
        .submit-btn { background-color: #4CAF50; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; }
        .submit-btn:hover { background-color: #45a049; }
        .files-link { display: block; text-align: center; margin-top: 20px; color: #0066cc; text-decoration: none; }
        .files-link:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <div class="container">
        <h1>文件分享站</h1>
        <form class="upload-form" action="/upload" method="post" enctype="multipart/form-data">
            <input type="file" name="file" class="file-input" required>
            <br>
            <input type="submit" value="上传文件" class="submit-btn">
        </form>
        <a href="/files" class="files-link">查看已上传文件</a>
    </div>
</body>
</html>
EOF

# 创建files.html
cat > templates/files.html << 'EOF'
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width