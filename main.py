import os
import shutil
import base64
import requests
from io import BytesIO
from flask import Flask, send_file, render_template_string
from pymongo import MongoClient

app = Flask(__name__)

# --- ⚙️ ڈیٹا بیس کنکشن ---
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:XrGKBDHzBwUtYpIgSVolqCFRKGbsUblH@caboose.proxy.rlwy.net:51078/")
DB_NAME = os.getenv("DB_NAME", "whatsapp_bot")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "chat_history")

# --- 🌐 ایچ ٹی ایم ایل ڈیش بورڈ کا ڈیزائن (Dark Theme) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en" dir="ltr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Database Extractor</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #121212; color: #e0e0e0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        .container { max-width: 900px; margin-top: 50px; }
        .card { background-color: #1e1e1e; border: 1px solid #333; margin-bottom: 15px; border-radius: 10px; }
        .card-header { background-color: #2c2c2c; border-bottom: 1px solid #333; cursor: pointer; border-radius: 10px 10px 0 0; }
        .card-header h5 { margin: 0; color: #00d2ff; display: flex; align-items: center; justify-content: space-between; }
        .list-group-item { background-color: #1e1e1e; border-color: #333; color: #ccc; display: flex; justify-content: space-between; align-items: center; }
        .list-group-item:hover { background-color: #2a2a2a; }
        .btn-download { background-color: #00d2ff; color: #000; font-weight: bold; border: none; }
        .btn-download:hover { background-color: #00a8cc; color: #fff; }
        .logo-text { text-align: center; color: #fff; margin-bottom: 40px; text-transform: uppercase; letter-spacing: 2px; }
        .logo-text span { color: #00d2ff; }
    </style>
</head>
<body>
    <div class="container">
        <h2 class="logo-text">Data <span>Extractor</span> Dashboard</h2>
        
        {% if bots %}
            <div class="accordion" id="botsAccordion">
                {% for bot_id, users in bots.items() %}
                <div class="card">
                    <div class="card-header" data-bs-toggle="collapse" data-bs-target="#collapse_{{ loop.index }}">
                        <h5>🤖 Bot ID: {{ bot_id }} <small class="text-muted" style="font-size: 14px;">(Click to view {{ users|length }} users)</small></h5>
                    </div>
                    <div id="collapse_{{ loop.index }}" class="collapse" data-bs-parent="#botsAccordion">
                        <div class="card-body p-0">
                            <ul class="list-group list-group-flush">
                                {% for user in users %}
                                <li class="list-group-item">
                                    <span>👤 {{ user }}</span>
                                    <a href="/download/{{ bot_id }}/{{ user }}" class="btn btn-sm btn-download">⬇️ Download Data</a>
                                </li>
                                {% endfor %}
                            </ul>
                        </div>
                    </div>
                </div>
                {% endfor %}
            </div>
        {% else %}
            <div class="alert alert-warning text-center" style="background-color: #332b00; border-color: #665c00; color: #ffd700;">
                No data found in the database. Ensure MongoDB connection and collection names are correct.
            </div>
        {% endif %}
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

def get_db_collection():
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    return db[COLLECTION_NAME]

@app.route('/')
def index():
    collection = get_db_collection()
    
    # 🧠 Aggregation: تمام Bot IDs اور ان کے اندر موجود Senders (Users) کی لسٹ بنانا
    pipeline = [
        {"$group": {"_id": "$bot_id", "users": {"$addToSet": "$sender"}}},
        {"$sort": {"_id": 1}}
    ]
    
    results = list(collection.aggregate(pipeline))
    
    # ڈیٹا کو HTML کے لیے سیٹ کرنا
    bots = {}
    for doc in results:
        bot_name = doc.get("_id")
        if not bot_name:
            bot_name = "Unknown Bot"
        
        # خالی یوزرز کو فلٹر کر کے لسٹ بنانا
        users_list = [u for u in doc.get("users", []) if u]
        if users_list:
            bots[bot_name] = users_list
            
    return render_template_string(HTML_TEMPLATE, bots=bots)

@app.route('/download/<bot_id>/<path:target_id>')
def download_user_data(bot_id, target_id):
    collection = get_db_collection()

    # فولڈرز کی سیٹنگ
    clean_target = target_id.replace("@", "_").replace(".", "_")
    base_folder = f"/tmp/Export_{bot_id}_{clean_target}"
    
    folders = {
        "image": os.path.join(base_folder, "pictures"),
        "video": os.path.join(base_folder, "videos"),
        "audio": os.path.join(base_folder, "voices")
    }

    if os.path.exists(base_folder):
        shutil.rmtree(base_folder)
        
    for f_path in folders.values():
        os.makedirs(f_path, exist_ok=True)

    # 🔍 کیوری: مخصوص Bot اور مخصوص User کا ڈیٹا نکالنا
    query = {
        "bot_id": bot_id if bot_id != "Unknown Bot" else None,
        "sender": target_id,
        "type": {"$in": ["image", "video", "audio"]}
    }
    
    cursor = collection.find(query)
    has_data = False

    for doc in cursor:
        msg_type = doc.get("type")
        content = doc.get("content", "")
        msg_id = doc.get("message_id", "unknown")

        if not content or content == "MEDIA_WAITING" or msg_type not in folders:
            continue

        folder_path = folders[msg_type]

        try:
            # Base64 ڈیکوڈ
            if content.startswith("data:"):
                header, encoded_data = content.split(",", 1)
                ext = header.split(";")[0].split("/")[1]
                if ext == "octet-stream": ext = "bin"
                
                file_path = os.path.join(folder_path, f"{msg_id}.{ext}")
                with open(file_path, "wb") as f:
                    f.write(base64.b64decode(encoded_data))
                has_data = True

            # URL سے ڈاؤن لوڈ
            elif content.startswith("http"):
                ext = content.split(".")[-1]
                if len(ext) > 4: 
                    ext = "mp4" if msg_type == "video" else "ogg"
                
                file_path = os.path.join(folder_path, f"{msg_id}.{ext}")
                response = requests.get(content, stream=True, timeout=15)
                if response.status_code == 200:
                    with open(file_path, "wb") as f:
                        for chunk in response.iter_content(1024):
                            f.write(chunk)
                    has_data = True
        except Exception as e:
            print(f"⚠️ Error downloading {msg_id}: {e}")

    # اگر کوئی میڈیا نہیں ملا تو فولڈر ڈیلیٹ کریں
    if not has_data:
        shutil.rmtree(base_folder)
        return f"""
        <div style='background:#121212; color:#fff; text-align:center; padding:50px; font-family:sans-serif;'>
            <h2>اس یوزر کے پاس کوئی پکچر، وائس یا ویڈیو نہیں ہے۔</h2>
            <a href='/' style='color:#00d2ff;'>واپس مینیو پر جائیں</a>
        </div>
        """, 404

    # زپ بنانا
    shutil.make_archive(base_folder, 'zip', base_folder)
    zip_path = f"{base_folder}.zip"

    with open(zip_path, 'rb') as f:
        zip_data = f.read()
    
    # صفائی
    shutil.rmtree(base_folder)
    os.remove(zip_path)

    # فائل ڈائریکٹ ڈاؤن لوڈ کے لیے بھیجیں
    return send_file(
        BytesIO(zip_data),
        mimetype='application/zip',
        as_attachment=True,
        download_name=f"Data_{clean_target}.zip"
    )

if __name__ == '__main__':
    port = int(os.getenv("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
