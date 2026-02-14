import os
import shutil
import base64
import requests
from io import BytesIO
from flask import Flask, send_file, render_template_string
from pymongo import MongoClient

app = Flask(__name__)

# --- ⚙️ کنکشن سٹرنگ ---
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:XrGKBDHzBwUtYpIgSVolqCFRKGbsUblH@caboose.proxy.rlwy.net:51078/")

# --- 🌐 ایچ ٹی ایم ایل ڈیش بورڈ (Step-by-Step Navigation) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en" dir="ltr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mongo Data Extractor</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #121212; color: #e0e0e0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        .container { max-width: 800px; margin-top: 40px; }
        .list-group-item { background-color: #1e1e1e; border-color: #333; color: #ccc; font-size: 16px; }
        .list-group-item:hover { background-color: #2a2a2a; color: #fff; }
        .btn-custom { background-color: #00d2ff; color: #000; font-weight: bold; border: none; text-decoration: none; padding: 6px 15px; border-radius: 5px; }
        .btn-custom:hover { background-color: #00a8cc; color: #fff; }
        .logo-text { text-align: center; color: #fff; margin-bottom: 30px; letter-spacing: 2px; }
        .logo-text span { color: #00d2ff; }
        .breadcrumb { background: #1e1e1e; padding: 12px 15px; border-radius: 8px; border: 1px solid #333; }
        .breadcrumb-item a { color: #00d2ff; text-decoration: none; }
        .breadcrumb-item.active { color: #888; }
        .badge-custom { background-color: #333; color: #aaa; font-weight: normal; }
    </style>
</head>
<body>
    <div class="container">
        <h2 class="logo-text">Database <span>Extractor</span></h2>
        
        <nav aria-label="breadcrumb">
          <ol class="breadcrumb mb-4">
            <li class="breadcrumb-item"><a href="/">Databases</a></li>
            {% if current_db %}
                <li class="breadcrumb-item"><a href="/db/{{ current_db }}">{{ current_db }}</a></li>
            {% endif %}
            {% if current_coll %}
                <li class="breadcrumb-item"><a href="/db/{{ current_db }}/{{ current_coll }}">{{ current_coll }}</a></li>
            {% endif %}
            {% if current_bot %}
                <li class="breadcrumb-item active" aria-current="page">{{ current_bot }}</li>
            {% endif %}
          </ol>
        </nav>

        {% if error %}
            <div class="alert alert-danger" style="background-color: #4a0000; border: none; color: #ffcccc;">{{ error }}</div>
        {% endif %}

        {% if view == 'dbs' %}
            <h5 class="mb-3" style="color:#00d2ff;">📂 Select Database</h5>
            <div class="list-group">
                {% for db in items %}
                    <a href="/db/{{ db }}" class="list-group-item list-group-item-action d-flex justify-content-between align-items-center">
                        <div>🗄️ <strong>{{ db }}</strong></div>
                        <span class="badge badge-custom rounded-pill">View Collections ➔</span>
                    </a>
                {% endfor %}
            </div>
        
        {% elif view == 'colls' %}
            <h5 class="mb-3" style="color:#00d2ff;">📁 Select Collection</h5>
            <div class="list-group">
                {% for coll in items %}
                    <a href="/db/{{ current_db }}/{{ coll }}" class="list-group-item list-group-item-action d-flex justify-content-between align-items-center">
                        <div>📄 <strong>{{ coll }}</strong></div>
                        <span class="badge badge-custom rounded-pill">View Bots ➔</span>
                    </a>
                {% endfor %}
            </div>

        {% elif view == 'bots' %}
            <h5 class="mb-3" style="color:#00d2ff;">🤖 Select Bot ID</h5>
            {% if items %}
                <div class="list-group">
                    {% for bot in items %}
                        <a href="/db/{{ current_db }}/{{ current_coll }}/{{ bot }}" class="list-group-item list-group-item-action d-flex justify-content-between align-items-center">
                            <div>🤖 <strong>{{ bot }}</strong></div>
                            <span class="badge badge-custom rounded-pill">View Chats ➔</span>
                        </a>
                    {% endfor %}
                </div>
            {% else %}
                <div class="alert alert-warning" style="background-color: #332b00; border: none; color: #ffd700;">اس کلیکشن میں کوئی Bot ID موجود نہیں ہے۔</div>
            {% endif %}

        {% elif view == 'chats' %}
            <h5 class="mb-3" style="color:#00d2ff;">💬 Chat IDs for Bot: <span style="color:#fff;">{{ current_bot }}</span></h5>
            {% if items %}
                <div class="list-group">
                    {% for chat in items %}
                        <div class="list-group-item d-flex justify-content-between align-items-center">
                            <div>👤 <strong>{{ chat }}</strong></div>
                            <a href="/download/{{ current_db }}/{{ current_coll }}/{{ current_bot }}/{{ chat }}" class="btn-custom">⬇️ Download Media</a>
                        </div>
                    {% endfor %}
                </div>
            {% else %}
                <div class="alert alert-warning" style="background-color: #332b00; border: none; color: #ffd700;">اس بوٹ کے لیے کوئی Chat ID نہیں ملی۔</div>
            {% endif %}
        {% endif %}
    </div>
</body>
</html>
"""

def get_client():
    return MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)

# 1. Databases دکھائیں
@app.route('/')
def index():
    try:
        client = get_client()
        dbs = client.list_database_names()
        clean_dbs = [db for db in dbs if db not in ['admin', 'config', 'local']]
        return render_template_string(HTML_TEMPLATE, view='dbs', items=clean_dbs)
    except Exception as e:
        return render_template_string(HTML_TEMPLATE, error=f"DB Error: {e}")

# 2. Collections دکھائیں
@app.route('/db/<db_name>')
def list_collections(db_name):
    try:
        client = get_client()
        colls = client[db_name].list_collection_names()
        return render_template_string(HTML_TEMPLATE, view='colls', current_db=db_name, items=colls)
    except Exception as e:
        return render_template_string(HTML_TEMPLATE, error=f"Error: {e}")

# 3. تمام Bot IDs دکھائیں
@app.route('/db/<db_name>/<coll_name>')
def view_bots(db_name, coll_name):
    try:
        client = get_client()
        collection = client[db_name][coll_name]
        
        # منگو ڈی بی کی distinct کیوری جو صرف منفرد bot_ids لائے گی (بہت تیز ہے)
        bots = collection.distinct("bot_id")
        clean_bots = [str(b) for b in bots if b and str(b).strip() != "None"]

        return render_template_string(HTML_TEMPLATE, view='bots', current_db=db_name, current_coll=coll_name, items=clean_bots)
    except Exception as e:
        return render_template_string(HTML_TEMPLATE, error=f"Error reading bots: {e}")

# 4. مخصوص Bot کی تمام Chat IDs دکھائیں
@app.route('/db/<db_name>/<coll_name>/<bot_id>')
def view_chats(db_name, coll_name, bot_id):
    try:
        client = get_client()
        collection = client[db_name][coll_name]
        
        # مخصوص bot_id کے اندر موجود منفرد chat_ids لانا
        chats = collection.distinct("chat_id", {"bot_id": bot_id})
        clean_chats = [str(c) for c in chats if c and str(c).strip() != "None"]

        return render_template_string(HTML_TEMPLATE, view='chats', current_db=db_name, current_coll=coll_name, current_bot=bot_id, items=clean_chats)
    except Exception as e:
        return render_template_string(HTML_TEMPLATE, error=f"Error reading chats: {e}")

# 5. مخصوص Chat ID کا میڈیا ڈاؤن لوڈ کریں
@app.route('/download/<db_name>/<coll_name>/<bot_id>/<path:target_id>')
def download_user_data(db_name, coll_name, bot_id, target_id):
    client = get_client()
    collection = client[db_name][coll_name]

    # فائل کے نام کے لیے آئی ڈی کو کلین کرنا
    clean_target = target_id.replace("@", "_").replace(".", "_")
    base_folder = f"/tmp/Export_{bot_id}_{clean_target}"
    
    folders = {
        "image": os.path.join(base_folder, "pictures"),
        "video": os.path.join(base_folder, "videos"),
        "audio": os.path.join(base_folder, "voices")
    }

    if os.path.exists(base_folder): shutil.rmtree(base_folder)
    for f_path in folders.values(): os.makedirs(f_path, exist_ok=True)

    # ڈیٹا نکالنے کی کیوری
    query = {"bot_id": bot_id, "chat_id": target_id}
    cursor = collection.find(query)
    has_data = False

    for doc in cursor:
        msg_type = doc.get("type", "unknown")
        content = doc.get("content", "")
        msg_id = doc.get("message_id", "unknown")
        mime_type = doc.get("mime", "")

        if not content or content == "MEDIA_WAITING":
            continue

        folder_path = None
        if "image" in msg_type or "sticker" in msg_type or "image" in mime_type:
            folder_path = folders["image"]
        elif "video" in msg_type or "video" in mime_type:
            folder_path = folders["video"]
        elif "audio" in msg_type or "audio" in mime_type:
            folder_path = folders["audio"]
            
        if not folder_path:
            continue

        try:
            if content.startswith("data:"):
                header, encoded_data = content.split(",", 1)
                ext = header.split(";")[0].split("/")[1]
                if ext == "octet-stream": ext = "bin"
                
                file_path = os.path.join(folder_path, f"{msg_id}.{ext}")
                with open(file_path, "wb") as f:
                    f.write(base64.b64decode(encoded_data))
                has_data = True

            elif content.startswith("http"):
                ext = content.split(".")[-1]
                if len(ext) > 4: 
                    ext = mime_type.split("/")[-1] if mime_type else ("mp4" if "video" in folder_path else "ogg")
                
                file_path = os.path.join(folder_path, f"{msg_id}.{ext}")
                response = requests.get(content, stream=True, timeout=15)
                if response.status_code == 200:
                    with open(file_path, "wb") as f:
                        for chunk in response.iter_content(1024):
                            f.write(chunk)
                    has_data = True
        except Exception as e:
            print(f"⚠️ Error downloading {msg_id}: {e}")

    if not has_data:
        shutil.rmtree(base_folder)
        return f"<div style='background:#121212; color:#fff; text-align:center; padding:50px; font-family:sans-serif;'><h2>اس Chat ID کے پاس کوئی میڈیا نہیں ہے۔</h2><a href='/db/{db_name}/{coll_name}/{bot_id}' style='color:#00d2ff;'>واپس جائیں</a></div>", 404

    shutil.make_archive(base_folder, 'zip', base_folder)
    zip_path = f"{base_folder}.zip"

    with open(zip_path, 'rb') as f: zip_data = f.read()
    
    shutil.rmtree(base_folder)
    os.remove(zip_path)

    return send_file(BytesIO(zip_data), mimetype='application/zip', as_attachment=True, download_name=f"Data_{clean_target}.zip")

if __name__ == '__main__':
    port = int(os.getenv("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
