from flask import Flask, render_template, request, redirect, url_for, send_from_directory, abort, jsonify
from flask_mail import Mail, Message
from datetime import datetime
import os
import uuid
import socket
import json
import logging
import time
from logging.handlers import RotatingFileHandler

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        RotatingFileHandler('email_debug.log', maxBytes=1024*1024, backupCount=5, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['WORKSPACES_DIR'] = 'workspaces'
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size
app.config['FILE_METADATA'] = 'file_metadata.json'
app.config['WORKSPACES_METADATA'] = 'workspaces_metadata.json'

# 添加模板过滤器
@app.template_filter('datetimeformat')
def datetimeformat(value, format='%Y-%m-%d %H:%M:%S'):
    if isinstance(value, float) or isinstance(value, int):
        return datetime.fromtimestamp(value).strftime(format)
    return value

# CDN配置
app.config['CDN_ENABLED'] = False  # 可根据需要开启
app.config['CDN_DOMAIN'] = 'http://8.156.82.1'  # CDN域名

# 邮箱访问密码配置
app.config['EMAIL_PASSWORD'] = 'admin123'  # 邮箱界面访问密码

# 邮件配置（使用163邮箱作为默认配置）
app.config['MAIL_SERVER'] = 'smtp.163.com'  # 163邮箱SMTP服务器
app.config['MAIL_PORT'] = 587  # 端口
app.config['MAIL_USE_TLS'] = True  # 启用TLS
app.config['MAIL_USE_SSL'] = False  # 不启用SSL（与TLS二选一）
app.config['MAIL_USERNAME'] = 'your_163_email@163.com'  # 您的163邮箱
app.config['MAIL_PASSWORD'] = 'your_163_authorization_code'  # 生成的授权码
app.config['MAIL_DEFAULT_SENDER'] = 'your_163_email@163.com'  # 默认发件人
app.config['MAIL_TIMEOUT'] = 10  # 超时时间10秒

# 初始化邮件扩展
mail = Mail(app)

# Ensure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['WORKSPACES_DIR'], exist_ok=True)

# Ensure metadata files exist
if not os.path.exists(app.config['FILE_METADATA']):
    with open(app.config['FILE_METADATA'], 'w') as f:
        json.dump({}, f)

if not os.path.exists(app.config['WORKSPACES_METADATA']):
    with open(app.config['WORKSPACES_METADATA'], 'w') as f:
        json.dump({}, f)

# Get or create file metadata
def get_file_metadata():
    with open(app.config['FILE_METADATA'], 'r') as f:
        return json.load(f)

# Save file metadata
def save_file_metadata(metadata):
    with open(app.config['FILE_METADATA'], 'w') as f:
        json.dump(metadata, f, indent=2)

# Get or create workspaces metadata
def get_workspaces_metadata():
    with open(app.config['WORKSPACES_METADATA'], 'r') as f:
        return json.load(f)

# Save workspaces metadata
def save_workspaces_metadata(metadata):
    with open(app.config['WORKSPACES_METADATA'], 'w') as f:
        json.dump(metadata, f, indent=2)

# Check if custom route is unique
def is_custom_route_unique(route):
    if not route:
        return True
    metadata = get_workspaces_metadata()
    for workspace_data in metadata.values():
        if workspace_data.get('custom_route') == route:
            return False
    return True

# Create a new workspace
def create_workspace(workspace_id, workspace_name, user_id, custom_route=None):
    # Create workspace directory
    workspace_path = os.path.join(app.config['WORKSPACES_DIR'], workspace_id)
    os.makedirs(workspace_path, exist_ok=True)
    
    # Save workspace metadata
    metadata = get_workspaces_metadata()
    metadata[workspace_id] = {
        'name': workspace_name,
        'user_id': user_id,
        'created_at': os.path.getmtime(workspace_path),
        'updated_at': os.path.getmtime(workspace_path),
        'custom_route': custom_route
    }
    save_workspaces_metadata(metadata)
    return workspace_path

# Get workspace path
def get_workspace_path(workspace_id):
    return os.path.join(app.config['WORKSPACES_DIR'], workspace_id)

# Check if workspace exists
def workspace_exists(workspace_id):
    return os.path.exists(get_workspace_path(workspace_id))

# Get workspace by custom route
def get_workspace_by_custom_route(route):
    if not route:
        return None
    metadata = get_workspaces_metadata()
    for workspace_id, workspace_data in metadata.items():
        if workspace_data.get('custom_route') == route:
            return workspace_id
    return None

# Get user workspaces
def get_user_workspaces(user_id):
    metadata = get_workspaces_metadata()
    user_workspaces = []
    for workspace_id, workspace_data in metadata.items():
        if workspace_data['user_id'] == user_id:
            user_workspaces.append({
                'id': workspace_id,
                'name': workspace_data['name'],
                'created_at': workspace_data['created_at'],
                'updated_at': workspace_data['updated_at'],
                'custom_route': workspace_data.get('custom_route')
            })
    # Sort by updated_at in descending order
    user_workspaces.sort(key=lambda x: x['updated_at'], reverse=True)
    return user_workspaces

# Get all public workspaces (for square)
def get_all_workspaces():
    metadata = get_workspaces_metadata()
    workspaces = []
    for workspace_id, workspace_data in metadata.items():
        workspaces.append({
            'id': workspace_id,
            'name': workspace_data['name'],
            'user_id': workspace_data['user_id'],
            'created_at': workspace_data['created_at'],
            'updated_at': workspace_data['updated_at'],
            'custom_route': workspace_data.get('custom_route')
        })
    # Sort by updated_at in descending order
    workspaces.sort(key=lambda x: x['updated_at'], reverse=True)
    return workspaces

# Update workspace name
def update_workspace_name(workspace_id, new_name):
    metadata = get_workspaces_metadata()
    if workspace_id in metadata:
        metadata[workspace_id]['name'] = new_name
        metadata[workspace_id]['updated_at'] = time.time()
        save_workspaces_metadata(metadata)
        return True
    return False

# Delete workspace
def delete_workspace(workspace_id):
    # Delete workspace directory
    workspace_path = get_workspace_path(workspace_id)
    if os.path.exists(workspace_path):
        import shutil
        shutil.rmtree(workspace_path)
    
    # Remove from metadata
    metadata = get_workspaces_metadata()
    if workspace_id in metadata:
        del metadata[workspace_id]
        save_workspaces_metadata(metadata)
        return True
    return False

# Get files in workspace
def get_workspace_files(workspace_id):
    workspace_path = get_workspace_path(workspace_id)
    if not os.path.exists(workspace_path):
        return []
    
    files = []
    for root, dirs, filenames in os.walk(workspace_path):
        for filename in filenames:
            file_path = os.path.join(root, filename)
            relative_path = os.path.relpath(file_path, workspace_path)
            files.append({
                'name': filename,
                'path': relative_path,
                'size': os.path.getsize(file_path),
                'modified_at': os.path.getmtime(file_path),
                'is_html': filename.lower().endswith('.html')
            })
    return files

@app.route('/')
def index():
    # Use client IP as user ID for simplicity
    user_id = request.remote_addr
    
    # Get user workspaces
    workspaces = get_user_workspaces(user_id)
    
    # Render workspace management page
    return render_template('workspaces.html', workspaces=workspaces, user_id=user_id)

@app.route('/workspaces')
def workspaces():
    # Redirect to home page which now shows workspaces
    return redirect(url_for('index'))

@app.route('/workspace/create', methods=['POST'])
def create_workspace_route():
    # Create a new workspace
    user_id = request.remote_addr
    workspace_name = request.form.get('name', 'Untitled')
    custom_route = request.form.get('custom_route', '').strip()
    
    # Check if custom route is unique
    if custom_route and not is_custom_route_unique(custom_route):
        # For simplicity, we'll just redirect back with an error message in query string
        return redirect(url_for('index', error='custom_route_exists'))
    
    # Generate unique workspace ID
    workspace_id = str(uuid.uuid4())
    
    # Create workspace
    create_workspace(workspace_id, workspace_name, user_id, custom_route)
    
    return redirect(url_for('workspace_detail', workspace_id=workspace_id))

@app.route('/workspace/<workspace_id>')
def workspace_detail(workspace_id):
    # Show workspace details and files
    if not workspace_exists(workspace_id):
        abort(404)
    
    # Get workspace metadata
    metadata = get_workspaces_metadata()
    workspace = metadata.get(workspace_id)
    if not workspace:
        abort(404)
    
    # Get workspace files
    files = get_workspace_files(workspace_id)
    
    return render_template('workspace_detail.html', workspace=workspace, workspace_id=workspace_id, files=files)

@app.route('/workspace/<workspace_id>/upload', methods=['POST'])
def upload_to_workspace(workspace_id):
    # Upload files to workspace
    if not workspace_exists(workspace_id):
        abort(404)
    
    if 'file' not in request.files:
        return redirect(url_for('workspace_detail', workspace_id=workspace_id))
    
    files = request.files.getlist('file')
    if not files:
        return redirect(url_for('workspace_detail', workspace_id=workspace_id))
    
    # Get workspace path
    workspace_path = get_workspace_path(workspace_id)
    latest_modified = 0
    
    for file in files:
        if file.filename == '':
            continue
        
        if file:
            # Save file with its relative path
            file_path = os.path.join(workspace_path, file.filename)
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Save the file
            file.save(file_path)
            
            # Update latest modified time
            modified_time = os.path.getmtime(file_path)
            if modified_time > latest_modified:
                latest_modified = modified_time
    
    # Update workspace updated_at time
    metadata = get_workspaces_metadata()
    if workspace_id in metadata and latest_modified > 0:
        metadata[workspace_id]['updated_at'] = latest_modified
        save_workspaces_metadata(metadata)
    
    return redirect(url_for('workspace_detail', workspace_id=workspace_id))

@app.route('/workspace/<workspace_id>/preview/<path:file_path>')
def preview_workspace_file(workspace_id, file_path):
    # Preview a file in workspace
    if not workspace_exists(workspace_id):
        abort(404)
    
    # Get full file path
    full_path = os.path.join(get_workspace_path(workspace_id), file_path)
    
    if not os.path.exists(full_path):
        abort(404)
    
    # Check if file is HTML
    if file_path.lower().endswith('.html'):
        # Return HTML file content for preview
        with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
            html_content = f.read()
        return html_content
    else:
        # For non-HTML files, show file info or download
        return send_from_directory(get_workspace_path(workspace_id), file_path, as_attachment=False)

@app.route('/<custom_route>')
def custom_route_handler(custom_route):
    # Handle custom workspace routes
    # Skip reserved routes
    reserved_routes = ['workspaces', 'workspace', 'square', 'share-file', 'upload', 'download', 'send-mail', 'email', 'preview', 'raw', 'delete', '1', '2', '3', '5']
    if custom_route in reserved_routes:
        abort(404)
    
    # Check if custom route exists
    workspace_id = get_workspace_by_custom_route(custom_route)
    if workspace_id:
        # Redirect to workspace detail page
        return redirect(url_for('workspace_detail', workspace_id=workspace_id))
    
    abort(404)

@app.route('/square')
def square():
    # Show all workspaces (square)
    all_workspaces = get_all_workspaces()
    return render_template('square.html', workspaces=all_workspaces)

@app.route('/share-file')
def share_file():
    # Keep the original file sharing functionality
    files = os.listdir(app.config['UPLOAD_FOLDER'])
    files.sort(key=lambda x: os.path.getmtime(os.path.join(app.config['UPLOAD_FOLDER'], x)), reverse=True)
    return render_template('files.html', files=files)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return redirect(url_for('index'))
    
    # 获取所有上传的文件，包括文件夹中的文件
    files = request.files.getlist('file')
    
    if not files or all(f.filename == '' for f in files):
        return redirect(url_for('index'))
    
    # Get client IP
    client_ip = request.remote_addr
    
    # Save file metadata
    metadata = get_file_metadata()
    
    for file in files:
        if file.filename != '':
            # 生成唯一文件名，避免冲突
            filename = str(uuid.uuid4()) + '_' + file.filename
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            
            # 保存文件元数据，包含创建者IP
            metadata[filename] = {
                'creator_ip': client_ip,
                'upload_time': os.path.getmtime(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            }
    
    save_file_metadata(metadata)
    return redirect(url_for('files'))

@app.route('/files')
def files():
    # Get list of files in upload folder
    files = os.listdir(app.config['UPLOAD_FOLDER'])
    # Sort files by modification time (newest first)
    files.sort(key=lambda x: os.path.getmtime(os.path.join(app.config['UPLOAD_FOLDER'], x)), reverse=True)
    # Get metadata
    metadata = get_file_metadata()
    # Get client IP for delete permission check
    client_ip = request.remote_addr
    return render_template('files.html', files=files, metadata=metadata, client_ip=client_ip)

def get_file_url(filename):
    """获取文件的URL，支持CDN"""
    if app.config['CDN_ENABLED']:
        return f"{app.config['CDN_DOMAIN']}/download/{filename}"
    return url_for('download_file', filename=filename, _external=True)

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

@app.route('/send-mail', methods=['POST'])
def send_mail():
    """发送邮件功能"""
    try:
        email = request.form.get('email')
        subject = request.form.get('subject', '文件分享通知')
        body = request.form.get('body', '您有新的文件分享通知')
        
        if not email:
            logger.warning("邮件发送失败: 缺少收件人邮箱")
            return "请提供收件人邮箱地址", 400
        
        logger.debug(f"准备发送邮件: 收件人={email}, 主题={subject}")
        
        # 构建邮件消息
        msg = Message(subject, recipients=[email])
        msg.body = body
        
        logger.debug(f"邮件消息构建完成，准备发送")
        
        # 发送邮件
        mail.send(msg)
        
        logger.info(f"邮件发送成功: 收件人={email}")
        return "邮件发送成功！", 200
    except Exception as e:
        # 详细的错误信息，便于调试
        error_msg = f"邮件发送失败: {type(e).__name__}: {str(e)}"
        # 添加更详细的错误日志
        logger.error(f"邮件发送错误详情: {error_msg}")
        logger.error(f"错误堆栈:", exc_info=True)
        
        # 返回用户友好的错误信息
        return f"邮件发送失败，请检查邮箱配置: {str(e)}", 500

@app.route('/email', methods=['GET', 'POST'])
def email_login():
    """邮箱登录界面"""
    error = None
    if request.method == 'POST':
        password = request.form.get('password')
        if password == app.config['EMAIL_PASSWORD']:
            # 登录成功，重定向到邮箱主界面
            return redirect(url_for('email_main'))
        else:
            error = '密码错误，请重试'
    
    # 返回登录表单
    return '''
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>邮箱登录</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 400px; margin: 0 auto; padding: 20px; background-color: #f0f0f0; }
            .container { background-color: white; padding: 30px; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.1); margin-top: 100px; }
            h1 { text-align: center; color: #333; }
            .form-group { margin-bottom: 20px; }
            label { display: block; margin-bottom: 5px; font-weight: bold; color: #333; }
            input[type="password"] { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; font-size: 16px; }
            .submit-btn { background-color: #4CAF50; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; width: 100%; }
            .submit-btn:hover { background-color: #45a049; }
            .error { color: #dc3545; text-align: center; margin-bottom: 15px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>邮箱系统登录</h1>
            {% if error %}
                <div class="error">{{ error }}</div>
            {% endif %}
            <form method="POST">
                <div class="form-group">
                    <label for="password">访问密码</label>
                    <input type="password" id="password" name="password" required>
                </div>
                <button type="submit" class="submit-btn">登录</button>
            </form>
        </div>
    </body>
    </html>
    '''

@app.route('/email/main')
def email_main():
    """邮箱主界面"""
    # 这里可以添加收件箱功能，目前只实现发送功能
    return '''
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>邮箱主界面</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; background-color: #f0f0f0; }
            .container { background-color: white; padding: 30px; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
            h1 { text-align: center; color: #333; }
            .nav { display: flex; justify-content: center; margin-bottom: 30px; gap: 20px; }
            .nav-btn { background-color: #0066cc; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; text-decoration: none; font-size: 16px; }
            .nav-btn:hover { background-color: #0052a3; }
            .section { margin-top: 30px; }
            h2 { color: #333; border-bottom: 1px solid #ddd; padding-bottom: 10px; }
            .form-group { margin-bottom: 20px; }
            label { display: block; margin-bottom: 5px; font-weight: bold; color: #333; }
            input[type="email"], input[type="text"], textarea { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; font-size: 16px; }
            textarea { height: 150px; resize: vertical; }
            .submit-btn { background-color: #4CAF50; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; }
            .submit-btn:hover { background-color: #45a049; }
            .result { margin-top: 20px; padding: 15px; border-radius: 4px; }
            .success { background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
            .error { background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>邮箱系统</h1>
            
            <div class="nav">
                <a href="#compose" class="nav-btn">写信</a>
                <a href="#inbox" class="nav-btn">收件箱</a>
                <a href="#sent" class="nav-btn">已发送</a>
            </div>
            
            <div id="compose" class="section">
                <h2>写信</h2>
                <form id="sendForm">
                    <div class="form-group">
                        <label for="to">收件人</label>
                        <input type="email" id="to" name="email" required>
                    </div>
                    <div class="form-group">
                        <label for="subject">主题</label>
                        <input type="text" id="subject" name="subject" placeholder="邮件主题">
                    </div>
                    <div class="form-group">
                        <label for="body">正文</label>
                        <textarea id="body" name="body" placeholder="邮件正文"></textarea>
                    </div>
                    <button type="submit" class="submit-btn">发送</button>
                </form>
                <div id="result"></div>
            </div>
            
            <div id="inbox" class="section">
                <h2>收件箱</h2>
                <p>收件箱功能开发中...</p>
            </div>
            
            <div id="sent" class="section">
                <h2>已发送</h2>
                <p>已发送功能开发中...</p>
            </div>
        </div>
        
        <script>
            // 表单提交处理
            document.getElementById('sendForm').addEventListener('submit', function(e) {
                e.preventDefault();
                
                const formData = new FormData(this);
                const resultDiv = document.getElementById('result');
                
                fetch('/send-mail', {
                    method: 'POST',
                    body: formData
                })
                .then(response => response.text())
                .then(data => {
                    if (data.includes('成功')) {
                        resultDiv.className = 'result success';
                    } else {
                        resultDiv.className = 'result error';
                    }
                    resultDiv.innerHTML = data;
                })
                .catch(error => {
                    resultDiv.className = 'result error';
                    resultDiv.innerHTML = '发送失败：网络错误';
                });
            });
        </script>
    </body>
    </html>
    '''

@app.route('/preview/<filename>')
def preview_file(filename):
    # Check if file exists
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(file_path):
        abort(404)
    
    # Get file extension
    file_ext = os.path.splitext(filename)[1].lower()
    file_name = filename.split('_', 1)[1]
    
    # Get file URL with CDN support
    file_url = get_file_url(filename)
    
    # Determine preview type
    if file_ext in ['.txt', '.md', '.py', '.js', '.html', '.css', '.json', '.xml', '.yaml', '.yml', '.log']:
        preview_type = 'text'
        # Read file content
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            file_content = f.read()
    elif file_ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg', '.webp']:
        preview_type = 'image'
        file_content = None
    elif file_ext in ['.mp4', '.webm', '.ogg']:
        preview_type = 'video'
        file_content = None
    elif file_ext in ['.mp3', '.wav', '.ogg', '.flac']:
        preview_type = 'audio'
        file_content = None
    else:
        preview_type = 'unknown'
        file_content = None
    
    return render_template('preview.html', file=filename, file_name=file_name, preview_type=preview_type, file_content=file_content, file_url=file_url)

@app.route('/raw/<filename>')
def raw_file(filename):
    # Check if file exists
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(file_path):
        abort(404)
    
    # Get file content
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        file_content = f.read()
    
    return f"<html><head><meta name=\"color-scheme\" content=\"light dark\"></head><body><pre style=\"word-wrap: break-word; white-space: pre-wrap;\">{file_content}</pre></body></html>"

@app.route('/delete/<filename>')
def delete_file(filename):
    # Check if file exists
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(file_path):
        abort(404)
    
    # Get metadata
    metadata = get_file_metadata()
    client_ip = request.remote_addr
    
    # Check if client is the creator (same IP)
    if filename in metadata and metadata[filename]['creator_ip'] == client_ip:
        # Delete file
        os.remove(file_path)
        # Remove from metadata
        del metadata[filename]
        save_file_metadata(metadata)
        return redirect(url_for('files'))
    else:
        # Permission denied
        return "<h1>403 Forbidden</h1><p>You don't have permission to delete this file.</p>", 403

@app.route('/1')
def video_play():
    # Video URL to play automatically
    video_url = 'http://8.156.82.1/download/ae6ef661-ec9e-4f73-9950-e593734cf554_Bilibili%20%E8%A7%86%E9%A2%91%E4%B8%8B%E8%BD%BD%E5%99%A8%20-%20%E4%B8%8B%E8%BD%BD%E5%93%94%E5%93%A9%E5%93%94%E5%93%A9%E8%A7%86%E9%A2%91.mp4'
    return render_template('video_play.html', video_url=video_url)

@app.route('/2')
def redirect_mp3():
    # Redirect to the specified MP3 file
    mp3_url = 'http://8.156.82.1/download/21b0f24f-fcb4-469a-a062-52565c201cd5_zztdd.mp3'
    return redirect(mp3_url)

@app.route('/3')
def redirect_mtr_mp3():
    # Redirect to the specified MTR MP3 file
    mtr_mp3_url = 'http://8.156.82.1/download/cba33320-783a-45d7-87aa-3a26df7fd1ab_%E6%B8%AF%E9%93%81MTR%E8%A7%86%E9%9A%9C%E4%BA%BA%E5%A3%AB%E8%BE%85%E5%8A%A9%E6%9C%BA%E9%9F%B3%E4%B9%90.mp3'
    return redirect(mtr_mp3_url)

@app.route('/5')
def play_video():
    # Play the specified video using the video_play template
    video_url = 'http://8.156.82.1/download/1ee6fc49-9a36-41d6-98d3-bc8e50a66311_Bilibili%20%E8%A7%86%E9%A2%91%E4%B8%8B%E8%BD%BD%E5%99%A8%20-%20%E4%B8%8B%E8%BD%BD%E5%93%94%E5%93%A9%E5%93%94%E5%93%A9%E8%A7%86%E9%A2%91(1).mp4'
    return render_template('video_play.html', video_url=video_url)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)