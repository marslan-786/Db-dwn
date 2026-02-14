import os
import shutil
import base64
import requests
from io import BytesIO
from flask import Flask, send_file, abort
from pymongo import MongoClient

app = Flask(__name__)

# Railway کے Environment Variables سے ڈیٹا بیس کی سیٹنگز اٹھائیں
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:XrGKBDHzBwUtYpIgSVolqCFRKGbsUblH@caboose.proxy.rlwy.net:51078")
DB_NAME = os.getenv("DB_NAME", "whatsapp_bot")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "chat_history")

@app.route('/download/<target_id>')
def download_user_data(target_id):
    # 1. MongoDB سے کنیکٹ کریں
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]

    # 2. ٹیمپریری فولڈرز بنائیں (ہر ڈاؤن لوڈ کے لیے الگ تاکہ مکس نہ ہو)
    base_folder = f"/tmp/Export_{target_id}"
    folders = {
        "image": os.path.join(base_folder, "pictures"),
        "video": os.path.join(base_folder, "videos"),
        "audio": os.path.join(base_folder, "voices"),
        "link": os.path.join(base_folder, "links")
    }

    if os.path.exists(base_folder):
        shutil.rmtree(base_folder)
        
    for f_path in folders.values():
        os.makedirs(f_path, exist_ok=True)

    print(f"🔍 آئی ڈی {target_id} کا ڈیٹا نکالا جا رہا ہے...")

    # 3. ڈیٹا بیس سے کیوری کریں
    query = {"sender": {"$regex": target_id}}
    cursor = collection.find(query)
    
    has_data = False
    links_file_path = os.path.join(folders["link"], "extracted_links.txt")

    # 4. ڈیٹا پروسیس کریں
    for doc in cursor:
        msg_type = doc.get("type")
        content = doc.get("content", "")
        msg_id = doc.get("message_id", "unknown")

        if not content or content == "MEDIA_WAITING":
            continue

        # ---> Case A: لنکس نکالنا
        if msg_type == "text" and "http" in content:
            with open(links_file_path, "a", encoding="utf-8") as lf:
                lf.write(f"Message ID: {msg_id}\nLink: {content}\n\n")
            has_data = True
            continue

        if msg_type not in folders:
            continue

        folder_path = folders[msg_type]

        try:
            # ---> Case B: Base64 ڈیٹا (تصاویر، وائسز)
            if content.startswith("data:"):
                header, encoded_data = content.split(",", 1)
                ext = header.split(";")[0].split("/")[1]
                if ext == "octet-stream": ext = "bin"
                
                file_path = os.path.join(folder_path, f"{msg_id}.{ext}")
                with open(file_path, "wb") as f:
                    f.write(base64.b64decode(encoded_data))
                has_data = True

            # ---> Case C: URLs سے ڈاؤن لوڈ (ویڈیوز، بڑی فائلز)
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
            print(f"⚠️ ایرر: {msg_id} - {e}")

    # اگر کوئی ڈیٹا نہیں ملا تو فولڈر ڈیلیٹ کر کے ایرر دکھائیں
    if not has_data:
        shutil.rmtree(base_folder)
        return f"آئی ڈی {target_id} کا کوئی ڈیٹا نہیں ملا۔", 404

    # 5. ڈیٹا مل گیا، اب زپ فائل بنائیں
    print("📦 زپ فائل بنائی جا رہی ہے...")
    shutil.make_archive(base_folder, 'zip', base_folder)
    zip_path = f"{base_folder}.zip"

    # زپ فائل کو میموری میں ریڈ کریں تاکہ سرور سے ڈیلیٹ کی جا سکے
    with open(zip_path, 'rb') as f:
        zip_data = f.read()
    
    # 6. سرور کی صفائی (کلین اپ)
    shutil.rmtree(base_folder)
    os.remove(zip_path)

    # 7. یوزر کو ڈائریکٹ ڈاؤن لوڈ کے لیے بھیج دیں
    return send_file(
        BytesIO(zip_data),
        mimetype='application/zip',
        as_attachment=True,
        download_name=f"Data_{target_id}.zip"
    )

if __name__ == '__main__':
    # Railway اٹومیٹک PORT دیتا ہے، ورنہ 5000 استعمال ہوگا
    port = int(os.getenv("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
