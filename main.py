import os
import shutil
import base64
import re
import requests
from io import BytesIO
from datetime import datetime  # 🔥 یہ ٹائم کنورٹ کرنے کے لیے شامل کیا ہے
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
    <title>Advanced Data Extractor</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #121212; color: #e0e0e0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        .container { max-width: 800px; margin-top: 40px; }
        .list-group-item { background-color: #1e1e1e; border-color: #333; color: #ccc; font-size: 16px; transition: 0.2s; }
        .list-group-item:hover { background-color: #2a2a2a; color: #fff; }
        .btn-custom { background-color: #00d2ff; color: #000; font-weight: bold; border: none; text-decoration: none; padding: 6px 15px; border-radius: 5px; }
        .btn-custom:hover { background-color: #00a8cc; color: #fff; }
        .logo-text { text-align: center; color: #fff; margin-bottom: 20px; letter-spacing: 2px; }
        .logo-text span { color: #00d2ff; }
        .breadcrumb { background: #1e1e1e; padding: 12px 15px; border-radius: 8px; border: 1px solid #333; }
        .breadcrumb-item a { color: #00d2ff; text-decoration: none; }
        .breadcrumb-item.active { color: #888; }
        .badge-custom { background-color: #333; color: #aaa; font-weight: normal; }
        .search-box { background-color: #1e1e1e; color: #fff; border: 1px solid #00d2ff; border-radius: 8px; padding: 10px 15px; width: 100%; margin-bottom: 20px; outline: none; }
        .search-box:focus { background-color: #2a2a2a; color: #fff; box-shadow: 0 0 10px rgba(0, 210, 255, 0.5); }
    </style>
</head>
<body>
    <div class="container">
        <h2 class="logo-text">Advanced <span>Extractor</span></h2>
        
        <nav aria-label="breadcrumb">
          <ol class="breadcrumb mb-3">
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

        {% if items %}
            <input type="text" id="searchInput" class="search-box" placeholder="🔍 Search IDs or Names here..." onkeyup="filterList()">
        {% endif %}

        <div class="list-group" id="dataList">
            {% if view == 'dbs' %}
                <h5 class="mb-3" style="color:#00d2ff;">📂 Select Database</h5>
                {% for db in items %}
                    <a href="/db/{{ db }}" class="list-group-item list-group-item-action d-flex justify-content-between align-items-center searchable-item">
                        <div>🗄️ <strong>{{ db }}</strong></div>
                        <span class="badge badge-custom rounded-pill">View Collections ➔</span>
                    </a>
                {% endfor %}
            
            {% elif view == 'colls' %}
                <h5 class="mb-3" style="color:#00d2ff;">📁 Select Collection</h5>
                {% for coll in items %}
                    <a href="/db/{{ current_db }}/{{ coll }}" class="list-group-item list-group-item-action d-flex justify-content-between align-items-center searchable-item">
                        <div>📄 <strong>{{ coll }}</strong></div>
                        <span class="badge badge-custom rounded-pill">View Bots ➔</span>
                    </a>
                {% endfor %}

            {% elif view == 'bots' %}
                <h5 class="mb-3" style="color:#00d2ff;">🤖 Select Bot ID</h5>
                {% for bot in items %}
                    <a href="/db/{{ current_db }}/{{ current_coll }}/{{ bot }}" class="list-group-item list-group-item-action d-flex justify-content-between align-items-center searchable-item">
                        <div>🤖 <strong>{{ bot }}</strong></div>
                        <span class="badge badge-custom rounded-pill">View Chats ➔</span>
                    </a>
                {% endfor %}

            {% elif view == 'chats' %}
                <h5 class="mb-3" style="color:#00d2ff;">💬 Chat IDs for Bot: <span style="color:#fff;">{{ current_bot }}</span></h5>
                {% for chat in items %}
                    <div class="list-group-item d-flex justify-content-between align-items-center searchable-item">
                        <div>👤 <strong>{{ chat }}</strong></div>
                        <a href="/download/{{ current_db }}/{{ current_coll }}/{{ current_bot }}/{{ chat }}" class="btn-custom">⬇️ Extract Data</a>
                    </div>
                {% endfor %}
            {% endif %}
        </div>
        
        {% if view in ['bots', 'chats'] and not items %}
             <div class="alert alert-warning" style="background-color: #332b00; border: none; color: #ffd700;">کوئی ڈیٹا نہیں ملا۔</div>
        {% endif %}
    </div>

    <script>
    function filterList() {
        var input = document.getElementById('searchInput');
        var filter = input.value.toLowerCase();
        var nodes = document.getElementsByClassName('searchable-item');

        for (i = 0; i < nodes.length; i++) {
            if (nodes[i].innerText.toLowerCase().includes(filter)) {
                nodes[i].style.display = "flex";
            } else {
                nodes[i].style.display = "none";
            }
        }
    }
    </script>
</body>
</html>
"""

def get_client():
    return MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)

@app.route('/')
def index():
    try:
        client = get_client()
        dbs = client.list_database_names()
        clean_dbs = [db for db in dbs if db not in ['admin', 'config', 'local']]
        return render_template_string(HTML_TEMPLATE, view='dbs', items=clean_dbs)
    except Exception as e:
        return render_template_string(HTML_TEMPLATE, error=f"DB Error: {e}")

@app.route('/db/<db_name>')
def list_collections(db_name):
    try:
        colls = get_client()[db_name].list_collection_names()
        return render_template_string(HTML_TEMPLATE, view='colls', current_db=db_name, items=colls)
    except Exception as e:
        return render_template_string(HTML_TEMPLATE, error=f"Error: {e}")

@app.route('/db/<db_name>/<coll_name>')
def view_bots(db_name, coll_name):
    try:
        bots = get_client()[db_name][coll_name].distinct("bot_id")
        clean_bots = [str(b) for b in bots if b and str(b).strip() != "None"]
        return render_template_string(HTML_TEMPLATE, view='bots', current_db=db_name, current_coll=coll_name, items=clean_bots)
    except Exception as e:
        return render_template_string(HTML_TEMPLATE, error=f"Error reading bots: {e}")

@app.route('/db/<db_name>/<coll_name>/<bot_id>')
def view_chats(db_name, coll_name, bot_id):
    try:
        chats = get_client()[db_name][coll_name].distinct("chat_id", {"bot_id": bot_id})
        clean_chats = [str(c) for c in chats if c and str(c).strip() != "None"]
        return render_template_string(HTML_TEMPLATE, view='chats', current_db=db_name, current_coll=coll_name, current_bot=bot_id, items=clean_chats)
    except Exception as e:
        return render_template_string(HTML_TEMPLATE, error=f"Error reading chats: {e}")

@app.route('/download/<db_name>/<coll_name>/<bot_id>/<path:target_id>')
def download_user_data(db_name, coll_name, bot_id, target_id):
    client = get_client()
    collection = client[db_name][coll_name]

    clean_target = target_id.replace("@", "_").replace(".", "_")
    base_folder = f"/tmp/Export_{bot_id}_{clean_target}"
    
    folders = {
        "pictures": os.path.join(base_folder, "pictures"),
        "voices": os.path.join(base_folder, "voices"),
        "links": os.path.join(base_folder, "links"),
        "chats": os.path.join(base_folder, "chats") 
    }

    if os.path.exists(base_folder): shutil.rmtree(base_folder)
    for f_path in folders.values(): os.makedirs(f_path, exist_ok=True)

    query = {"bot_id": bot_id, "chat_id": target_id}
    cursor = collection.find(query).sort("timestamp", 1) 
    has_data = False
    
    links_file_path = os.path.join(folders["links"], "catbox_and_media_links.txt")
    chat_file_path = os.path.join(folders["chats"], "chat_history.txt")

    for doc in cursor:
        msg_type = str(doc.get("type", "unknown")).lower()
        content = str(doc.get("content", "")).strip()
        msg_id = str(doc.get("message_id", "unknown"))
        is_from_me = doc.get("is_from_me", False)
        sender_name = str(doc.get("sender_name", "User"))
        
        # 🔥 ٹائم کنورٹر (Original Time Generator)
        raw_ts = doc.get("timestamp")
        time_str = "Unknown Time"
        
        if raw_ts:
            if isinstance(raw_ts, datetime):
                # اگر ڈیٹا بیس میں پہلے ہی Date object ہے
                time_str = raw_ts.strftime("%Y-%m-%d %I:%M %p")
            elif isinstance(raw_ts, (int, float)):
                # اگر Unix Timestamp ہے
                ts_val = float(raw_ts)
                if ts_val > 1e11:  # اگر ملی سیکنڈز میں ہے تو سیکنڈز میں لائیں
                    ts_val /= 1000.0
                try:
                    time_str = datetime.fromtimestamp(ts_val).strftime("%Y-%m-%d %I:%M %p")
                except:
                    time_str = str(raw_ts)
            else:
                time_str = str(raw_ts)

        if not content or content == "MEDIA_WAITING":
            continue

        has_data = True

        try:
            # ---------------------------------------------------------
            # 1. 💬 چیٹ ہسٹری (اصل ٹائم کے ساتھ)
            # ---------------------------------------------------------
            if msg_type in ["text", "conversation", "extendedtext"] or (not content.startswith("http") and not content.startswith("data:")):
                sender = "Bot (Me)" if is_from_me else sender_name
                with open(chat_file_path, "a", encoding="utf-8") as cf:
                    cf.write(f"[{time_str}] {sender}: {content}\n")

            # ---------------------------------------------------------
            # 2. 🔥 EXACT CATBOX HUNTER (خاص کر ویڈیوز کے لیے)
            # ---------------------------------------------------------
            if "catbox" in content.lower() or "http" in content.lower():
                url_matches = re.findall(r'(https?://[^\s"\'>]+)', content)
                for actual_url in url_matches:
                    
                    # خاص طور پر کیٹ باکس کی ویڈیو کو ہائی لائٹ کرنا
                    if "catbox" in actual_url.lower() and (".mp4" in actual_url.lower() or "video" in msg_type):
                        icon = "🎬 [CATBOX VIDEO (Direct Link)]"
                    elif "catbox" in actual_url.lower():
                        icon = "🔥 [CATBOX FILE]"
                    else:
                        icon = f"🔗 [{msg_type.upper()} LINK]"
                    
                    with open(links_file_path, "a", encoding="utf-8") as lf:
                        lf.write(f"{icon} | Date: {time_str} | ID: {msg_id}\n")
                        lf.write(f"URL: {actual_url}\n")
                        lf.write("-" * 60 + "\n")

            # ---------------------------------------------------------
            # 3. 🖼️ Base64 Media 
            # ---------------------------------------------------------
            if "data:" in content and ";base64," in content:
                target_folder = folders["pictures"] if msg_type in ["image", "sticker"] else folders["voices"]
                
                header, encoded_data = content.split(";base64,", 1)
                encoded_data = encoded_data.strip()
                encoded_data += "=" * ((4 - len(encoded_data) % 4) % 4)
                
                ext = header.split("/")[-1]
                if ext == "octet-stream" or not ext: 
                    ext = "jpg" if msg_type in ["image", "sticker"] else "ogg"
                
                file_path = os.path.join(target_folder, f"{msg_id}.{ext}")
                with open(file_path, "wb") as f:
                    f.write(base64.b64decode(encoded_data))

        except Exception as e:
            print(f"⚠️ Error processing {msg_id}: {e}")

    if not has_data:
        shutil.rmtree(base_folder)
        return f"<div style='background:#121212; color:#fff; text-align:center; padding:50px; font-family:sans-serif;'><h2>اس Chat ID کا کوئی ڈیٹا نہیں ملا۔</h2></div>", 404

    if os.path.exists(links_file_path) and os.path.getsize(links_file_path) == 0:
        os.remove(links_file_path)
    if os.path.exists(chat_file_path) and os.path.getsize(chat_file_path) == 0:
        os.remove(chat_file_path)

    shutil.make_archive(base_folder, 'zip', base_folder)
    zip_path = f"{base_folder}.zip"

    with open(zip_path, 'rb') as f: zip_data = f.read()
    
    shutil.rmtree(base_folder)
    os.remove(zip_path)

    return send_file(BytesIO(zip_data), mimetype='application/zip', as_attachment=True, download_name=f"Data_{clean_target}.zip")

if __name__ == '__main__':
    port = int(os.getenv("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
