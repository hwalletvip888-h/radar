# -*- coding: utf-8 -*-
"""把关键画面 + 字幕拼成 2 分钟 demo 视频（MP4）。"""
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import imageio.v2 as imageio

W, H = 1920, 1080
FPS = 2  # 幻灯片式，2 帧/秒
FONT_PATH = "C:/Windows/Fonts/msyh.ttc"

BG = (15, 12, 23)          # 品牌深底 #0f0c17
TEXT = (245, 242, 251)     # 珍珠白 #F5F2FB
ACCENT = (174, 157, 232)   # 薰衣草 #AE9DE8
MUTED = (150, 142, 174)    # #968EAE


def font(sz):
    return ImageFont.truetype(FONT_PATH, sz)


def draw_centered(img, lines, main_idx=0, y0=None):
    """在图上居中绘制多行文字。返回 img。"""
    d = ImageDraw.Draw(img)
    sizes = [64 if i == main_idx else 46 for i in range(len(lines))]
    # 计算总高度
    total = sum(s + 24 for s in sizes) - 24
    y = y0 if y0 is not None else (H - total) // 2
    for i, (line, sz) in enumerate(zip(lines, sizes)):
        f = font(sz)
        bbox = d.textbbox((0, 0), line, font=f)
        tw = bbox[2] - bbox[0]
        color = ACCENT if i == main_idx else TEXT
        d.text(((W - tw) // 2, y), line, font=f, fill=color)
        y += sz + 24
    return img


def draw_subtitle(img, text):
    """底部字幕条。"""
    d = ImageDraw.Draw(img, "RGBA")
    f = font(42)
    bbox = d.textbbox((0, 0), text, font=f)
    tw = bbox[2] - bbox[0]
    bar_h = 96
    d.rectangle([0, H - bar_h, W, H], fill=(10, 8, 16, 205))
    d.text(((W - tw) // 2, H - bar_h + 26), text, font=f, fill=TEXT)
    return img


def text_frame(lines, subtitle="", main_idx=0):
    img = Image.new("RGB", (W, H), BG)
    # 顶部小字品牌
    d = ImageDraw.Draw(img)
    b = font(28)
    d.text((80, 70), "🐬 海豚Radar · DolphinRadar", font=b, fill=MUTED)
    draw_centered(img, lines, main_idx=main_idx, y0=H // 2 - 120)
    if subtitle:
        draw_subtitle(img, subtitle)
    return np.array(img)


def shot_frame(path, subtitle):
    img = Image.open(path).convert("RGB")
    draw_subtitle(img, subtitle)
    return np.array(img)


def hold(frame, seconds):
    n = int(seconds * FPS)
    return [frame] * n


# ── 场景表：(类型, 内容, 字幕, 秒) ──────────────────────────────
scenes = [
    ("text", ["TapeOut 生态安全警报系统", "图谱是底层结构 · 广播是产品形态"], "海豚Radar · 双链安全雷达", 0),
    ("text", ["TapeOut 上 2 万台矿机在挖 BEM", "电路算错 → 链上永久撤销", "但撤销之后，波及了谁？"], "一个真实存在、却没人追溯的盲区", 14),
    ("shot", "01_dashboard.png", "双链安全雷达 · 运行于 X Layer DeWEB（tape://11.2.4.tape）", 18),
    ("shot", "02_bnb.png", "扫 BNB Chain 1340 万区块：12 台被撤销 · 4676 BEM 冻结，全部链上可查", 18),
    ("shot", "03_subscribe.png", "订阅即触发链上合约 · 免费只付 gas，Pro 0.2 BEM/月", 16),
    ("shot", "04_contract.png", "合约已部署 + 开源验证 · OKLink 上源码公开可读", 16),
    ("text", ["WebSocket 实时监听链上事件", "撤销 / 新反例 → 秒级推送"], "第一时间推到你的 Telegram", 14),
    ("text", ["图谱是底层结构，广播是产品形态", "海豚Radar · 运行于 X Layer DeWEB"], "谢谢观看", 10),
]

# 修正第一屏（标题）时长
scenes[0] = ("text", ["TapeOut 生态安全警报系统", "图谱是底层结构 · 广播是产品形态"], "海豚Radar · 双链安全雷达", 6)

frames = []
for typ, content, subtitle, sec in scenes:
    if typ == "shot":
        f = shot_frame(content, subtitle)
    else:
        f = text_frame(content, subtitle)
    frames.extend(hold(f, sec))

# 末尾定格 1 秒
frames.extend(hold(frames[-1], 1))

print(f"总帧数 {len(frames)}，约 {len(frames)/FPS:.0f} 秒")
writer = imageio.get_writer("demo.mp4", fps=FPS, codec="libx264", quality=8, macro_block_size=16)
for f in frames:
    writer.append_data(f)
writer.close()
print("完成：video/demo.mp4")
