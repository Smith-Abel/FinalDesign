import urllib.request
import ssl
import os

base_dir = r"E:\FinalDesign\Campus Mutual Aid Mini Program\miniprogram\images\tab"

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# 专业版：未选中的大纲（灰色），选中时的实心（绿色）
url_normal = "https://img.icons8.com/ios/81/606266/speech-bubble-with-dots.png"
url_active = "https://img.icons8.com/ios-filled/81/67C23A/speech-bubble-with-dots.png"

try:
    with urllib.request.urlopen(url_normal, context=ctx) as r:
        with open(os.path.join(base_dir, "message.png"), 'wb') as f: f.write(r.read())
    with urllib.request.urlopen(url_active, context=ctx) as r:
        with open(os.path.join(base_dir, "message-active.png"), 'wb') as f: f.write(r.read())
    print("Icons downloaded successfully.")
except Exception as e:
    print(f"Failed to download icons: {e}")
