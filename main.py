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

# --- 🌐 ایچ ٹی ایم ایل ڈیش بورڈ ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en" dir="ltr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mongo Explorer</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #121212; color: #e0e0e0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        .container { max-width: 900px; margin-top: 40px; }
        .card { background-color: #1e1e1e; border: 1px solid #333; margin-bottom: 15px; border-radius: 10px; }
        .card-header { background-color: #2c2c2c; border-bottom: 1px solid #333; cursor: pointer; border-radius: 10px 10px 0 0; }
        .list-group-item { background-color: #1e1e1e; border-color: #333; color: #ccc; }
        .list-group-item:hover { background-color: #2a2a2a; }
        .btn-custom { background-color: #00d2ff; color: #000; font-weight: bold; border: none; text-decoration: none; }
        .btn-custom:hover { background-color: #00a8cc; color: #fff; }
        .logo-text { text-align: center; color: #fff; margin-bottom: 30px; letter-spacing: 2px; }
        .logo-text span { color: #00d2ff; }
        .breadcrumb-item a { color: #00d2ff; text-decoration: none; }
        .breadcrumb-item.active { color: #888; }
    </style>
</head>
<body>
    <div class="container">
        <h2 class="logo-text">Database <span>Explorer</span></h2>
        
        <nav aria-label="breadcrumb">
          <ol class="breadcrumb" style="background: #1e1e1e; padding: 10px; border-radius: 5px; border: 1px solid #333;">
            <li class="breadcrumb-item"><a href="/">Home (Databases)</a></li>
            {% if current_db %}
                <li class="breadcrumb-item"><a href="/db/{{ current_db }}">{{ current_db }}</a></li>
            {% endif %}
            {% if current_coll %}
                <li class="breadcrumb-item active" aria-current="page">{{ current_coll }}</li>
            {% endif %}
          </ol>
        </nav>

        {% if error %}
            <div class="alert alert-danger" style="background-color: #4a0000; border: none; color: #ffcccc;">{{ error }}</div>
        {% endif %}

        {% if view == 'dbs' %}
            <h4 class="mb-3">📂 Available Databases</h4>
            <div class="list-group">
                {% for db in items %}
                    <a href="/db/{{ db }}" class="list-group-item list-group-item-action d-flex justify-content-between align-items-center">
                        🗄️ {{ db }}
                        <span class="badge bg-secondary rounded-pill">View Collections ➔</span>
                    </a>
                {% endfor %}
            </div>
        
        {% elif view == 'colls' %}
            <h4 class="mb-3">📁 Collections in <span style="color:#00d2ff;">{{ current_db }}</span></h4>
            <div class="list-group">
                {% for coll in items %}
                    <a href="/db/{{ current_db }}/{{ coll }}" class="list-group-item list-group-item-action d-flex justify-content-between align-items-center">
                        📄 {{ coll }}
                        <span class="badge bg-secondary rounded-pill">View Data ➔</span>
                    </a>
                {% endfor %}
            </div>

        {% elif view == 'data' %}
            <h4 class="mb-3">🤖 Bots & Users in <span style="color:#00d2ff;">{{ current_coll }}</span></h4>
            
            {% if sample_keys %}
                <div class="alert alert-info" style="background-color: #003344; border: none; color: #aaddff; font-size: 13px;">
                    <strong>Detected Fields in DB:</strong> {{ sample_keys | join(', ') }}
                </div>
            {% endif %}

            {% if bots %}
                <div class="accordion" id="botsAccordion">
                    {% for bot_id, users in bots.items() %}
                    <div class="card">
                        <div class="card-header" data-bs-toggle="collapse" data-bs-target="#collapse_{{ loop.index }}">
                            <h5 style="margin: 0; color: #00d2ff;">🤖 Bot: {{ bot_id }} <small style="font-size: 14px; color: #888; float: right;">({{ users|length }} users)</small></h5>
                        </div>
                        <div id="collapse_{{ loop.index }}" class="collapse" data-bs-parent="#botsAccordion">
                            <div class="card-body p-0">
                                <ul class="list-group list-group-flush">
                                    {% for user in users %}
                                    <li class="list-group-item d-flex justify-content-between align-items-center">
                                        <span>👤 {{ user }}</span>
                                        <a href="/download/{{ current_db }}/{{ current_coll }}/{{ bot_id }}/{{ user }}" class="btn btn-sm btn-custom">⬇️ Download Media</a>
                                    </li>
                                    {% endfor %}
                                </ul>
                            </div>
                        </div>
                    </div>
                    {% endfor %}
                </div>
            {% else %}
                <div class="alert alert-warning text-center" style="background-color: #332b00; border: none; color: #ffd700;">
                    اس کلیکشن میں کوئی بوٹ یا یوزر ڈیٹا نہیں ملا۔
                </div>
            {% endif %}
        {% endif %}
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

def get_client():
    return MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)

# 1. ہوم پیج - تمام Databases دکھائیں
@app.route('/')
def index():
    try:
        client = get_client()
        dbs = client.list_database_names()
        # سسٹم کی کچھ ڈیفالٹ ڈیٹا بیسز چھپانی ہوں تو یہاں سے کر سکتے ہیں
        clean_dbs = [db for db in dbs if db not in ['admin', 'config', 'local']]
        return render_template_string(HTML_TEMPLATE, view='dbs', items=clean_dbs)
    except Exception as e:
        return render_template_string(HTML_TEMPLATE, error=f"Database connection error: {e}")

# 2. ڈیٹا بیس پر کلک - تمام Collections دکھائیں
@app.route('/db/<db_name>')
def list_collections(db_name):
    try:
        client = get_client()
        db = client[db_name]
        colls = db.list_collection_names()
        return render_template_string(HTML_TEMPLATE, view='colls', current_db=db_name, items=colls)
    except Exception as e:
        return render_template_string(HTML_TEMPLATE, error=f"Error reading collections: {e}")

# 3. کلیکشن پر کلک - Bots اور Users دکھائیں
@app.route('/db/<db_name>/<coll_name>')
def view_collection(db_name, coll_name):
    try:
        client = get_client()
        collection = client[db_name][coll_name]
        
        # ڈیٹا بیس کا ایک سیمپل چیک کریں تاکہ پتا چلے Go نے کس نام سے فیلڈز سیو کی ہیں
        sample = collection.find_one()
        sample_keys = list(sample.keys()) if sample else []

        # سمارٹ ڈیٹیکشن (اگر Go نے BotID کیپیٹل میں سیو کیا ہے)
        bot_field = "BotID" if "BotID" in sample_keys else "bot_id"
        sender_field = "Sender" if "Sender" in sample_keys else "sender"

        # ایگریگیشن (ڈیٹا کو گروپ کرنے کے لیے)
        pipeline = [
            {"$group": {"_id": f"${bot_field}", "users": {"$addToSet": f"${sender_field}"}}},
            {"$sort": {"_id": 1}}
        ]
        
        results = list(collection.aggregate(pipeline))
        
        bots = {}
        for doc in results:
            bot_name = str(doc.get("_id", "Unknown"))
            users_list = [str(u) for u in doc.get("users", []) if u]
            if users_list:
                bots[bot_name] = users_list

        return render_template_string(HTML_TEMPLATE, view='data', current_db=db_name, current_coll=coll_name, bots=bots, sample_keys=sample_keys)
    except Exception as e:
        return render_template_string(HTML_TEMPLATE, error=f"Error reading data: {e}", current_db=db_name, current_coll=coll_name)

# 4. ڈاؤن لوڈ بٹن کا فنکشن
@app.route('/download/<db_name>/<coll_name>/<bot_id>/<path:target_id>')
def download_user_data(db_name, coll_name, bot_id, target_id):
    client = get_client()
    collection = client[db_name][coll_name]

    sample = collection.find_one()
    sample_keys = list(sample.keys()) if sample else []
    
    # سمارٹ فیلڈ ڈیٹیکشن
    b_field = "BotID" if "BotID" in sample_keys else "bot_id"
    s_field = "Sender" if "Sender" in sample_keys else "sender"
    t_field = "Type" if "Type" in sample_keys else "type"
    c_field = "Content" if "Content" in sample_keys else "content"
    m_field = "MessageID" if "MessageID" in sample_keys else "message_id"

    # فولڈرز بنانا
    clean_target = target_id.replace("@", "_").replace(".", "_")
    base_folder = f"/tmp/Export_{bot_id}_{clean_target}"
    
    folders = {
        "image": os.path.join(base_folder, "pictures"),
        "video": os.path.join(base_folder, "videos"),
        "audio": os.path.join(base_folder, "voices")
    }

    if os.path.exists(base_folder): shutil.rmtree(base_folder)
    for f_path in folders.values(): os.makedirs(f_path, exist_ok=True)

    # ڈیٹا ڈھونڈنے کی کیوری
    query = {
        b_field: bot_id if bot_id != "Unknown" else None,
        s_field: target_id,
        t_field: {"$in": ["image", "video", "audio"]}
    }
    
    cursor = collection.find(query)
    has_data = False

    for doc in cursor:
        msg_type = doc.get(t_field)
        content = doc.get(c_field, "")
        msg_id = doc.get(m_field, "unknown")

        if not content or content == "MEDIA_WAITING" or msg_type not in folders:
            continue

        folder_path = folders[msg_type]

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
                if len(ext) > 4: ext = "mp4" if msg_type == "video" else "ogg"
                
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
        return f"<div style='background:#121212; color:#fff; text-align:center; padding:50px; font-family:sans-serif;'><h2>اس یوزر کے پاس کوئی میڈیا نہیں ہے۔</h2><a href='/db/{db_name}/{coll_name}' style='color:#00d2ff;'>واپس جائیں</a></div>", 404

    shutil.make_archive(base_folder, 'zip', base_folder)
    zip_path = f"{base_folder}.zip"

    with open(zip_path, 'rb') as f: zip_data = f.read()
    
    shutil.rmtree(base_folder)
    os.remove(zip_path)

    return send_file(BytesIO(zip_data), mimetype='application/zip', as_attachment=True, download_name=f"Data_{clean_target}.zip")

if __name__ == '__main__':
    port = int(os.getenv("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
