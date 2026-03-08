"""生成小程序 tabBar 图标和空数据页配图"""
from PIL import Image, ImageDraw, ImageFont
import os

os.makedirs('images/tab', exist_ok=True)
os.makedirs('images', exist_ok=True)

GRAY = (96, 98, 102, 255)
GREEN = (103, 194, 58, 255)
TRANSPARENT = (0, 0, 0, 0)
S = 81  # icon size

def new_img():
    return Image.new('RGBA', (S, S), TRANSPARENT)

def save(img, path):
    img.save(path, 'PNG')
    print(f'  Created: {path}')

# ── 首页图标（房子） ──
def draw_home(color):
    img = new_img()
    d = ImageDraw.Draw(img)
    # 屋顶三角形
    d.polygon([(40, 6), (4, 36), (76, 36)], fill=color)
    # 房体
    d.rectangle([14, 36, 66, 72], fill=color)
    # 门
    body_color = TRANSPARENT
    d.rectangle([30, 50, 50, 72], fill=TRANSPARENT)
    # 重新画门洞（白色透出背景色）
    d2 = ImageDraw.Draw(img)
    d2.rectangle([29, 49, 51, 73], fill=(255,255,255,0))
    return img

# ── 发布图标（加号） ──
def draw_add(color):
    img = new_img()
    d = ImageDraw.Draw(img)
    d.rectangle([34, 10, 46, 70], fill=color)
    d.rectangle([10, 34, 70, 46], fill=color)
    return img

# ── 我的图标（人形） ──
def draw_user(color):
    img = new_img()
    d = ImageDraw.Draw(img)
    # 脸部圆形
    d.ellipse([24, 4, 56, 36], fill=color)
    # 身体椭圆
    d.ellipse([4, 40, 76, 90], fill=color)
    return img

# ── 空数据配图（带感叹号的圆圈） ──
def draw_empty():
    img = Image.new('RGBA', (200, 200), TRANSPARENT)
    d = ImageDraw.Draw(img)
    c = (220, 223, 230, 255)  # light gray
    d.ellipse([10, 10, 190, 190], outline=c, width=6)
    d.rectangle([94, 60, 106, 120], fill=c)
    d.ellipse([94, 130, 106, 142], fill=c)
    return img

icons = [
    ('images/tab/home.png',         draw_home(GRAY)),
    ('images/tab/home-active.png',  draw_home(GREEN)),
    ('images/tab/add.png',          draw_add(GRAY)),
    ('images/tab/add-active.png',   draw_add(GREEN)),
    ('images/tab/user.png',         draw_user(GRAY)),
    ('images/tab/user-active.png',  draw_user(GREEN)),
    ('images/empty.png',            draw_empty()),
]

print('Generating icons...')
for path, img in icons:
    save(img, path)
print('Done!')
