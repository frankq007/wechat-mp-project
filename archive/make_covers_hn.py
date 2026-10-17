#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cover-artist: 生成 hn-ai-top5 三张封面（master / cover / square）。

风格对齐 images/style-ref.png（奶油底 + 标题条 + 环形流程 + 底部标语 + 四角装饰 + 水印）。
仅产出图片，不排版、不发布、不碰 sync 层。
"""
from __future__ import annotations
import math
import os
from PIL import Image, ImageDraw, ImageFont

# ---------------- 配色体系（基准值，可微调不换体系） ----------------
CREAM    = (250, 245, 234)   # 背景奶油 #FAF5EA
CORAL    = (238, 110, 91)    # 强调珊瑚红 #EE6E5B
BRUSH    = (248, 217, 206)   # 笔刷浅粉 #F8D9CE
BLUE     = (205, 226, 246)   # 框·蓝 #CDE2F6
GREEN    = (205, 231, 211)   # 框·绿 #CDE7D3
PURPLE   = (219, 210, 239)   # 框·紫 #DBD2EF
PINK     = (245, 206, 200)   # 框·粉 #F5CEC8
INK      = (26, 26, 26)      # 描边/正文黑 #1A1A1A
DARKWIN  = (58, 63, 74)      # 窗口深灰 #3A3F4A
YELLOW   = (245, 200, 76)    # 点缀黄 #F5C84C

FONT = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
OUT  = "/mnt/d/code/wechat-mp-project/images/covers"

def F(sz):  # 缓存字体
    if sz not in _FC:
        _FC[sz] = ImageFont.truetype(FONT, sz)
    return _FC[sz]
_FC = {}

# 标题与文案
TITLE_1, TITLE_2 = "Claude", " 半小时破解 26 年密码学悬案"
SLOGAN = "给 AI 一双能验证的眼睛"
WATER  = "公众号·和弦代码"
SUBS = {  # 位置: (小标题, 框色, 内容类型)
    "top":    ("自己找线索", BLUE,   "code"),
    "right":  ("自己跑复现", GREEN,  "terminal"),
    "bottom": ("自己看结果", PURPLE, "report"),
    "left":   ("自己审代码", PINK,   "review"),
}

# ---------------- 基础绘图 ----------------
def rr(d, box, fill, outline=INK, w=4, r=18):
    """圆角矩形（手绘感）。"""
    d.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=w)

def seg_w(d, font, *segs):
    """返回 (total_w, 各段x偏移)。segs 为 (text, fill) 列表。"""
    offs, x = [], 0
    for text, _ in segs:
        offs.append(x)
        x += d.textlength(text, font=font)
    return x, offs

def draw_segs(d, xy, font, segs, anchor_center=True):
    """绘制多色分段文字，返回包围盒。xy=(cx,cy)居中或 (x0,y0) 左对齐。"""
    total, offs = seg_w(d, font, *segs)
    asc, desc = font.getmetrics()
    line_h = asc + desc
    if anchor_center:
        cx, cy = xy
        x0 = cx - total / 2
        y0 = cy - line_h / 2 + desc / 2 - 2
    else:
        x0, y0 = xy
    for (text, fill), o in zip(segs, offs):
        d.text((x0 + o, y0), text, font=font, fill=fill)
    return (x0, y0, x0 + total, y0 + line_h)

def axis(d, pts):
    """线段折线，手绘略微抖动 + 端点小圆。"""
    for a, b in zip(pts, pts[1:]):
        d.line([a, b], fill=INK, width=6)
        d.ellipse([b[0]-3, b[1]-3, b[0]+3, b[1]+3], fill=INK)
    for p in pts:
        d.ellipse([p[0]-2.5, p[1]-2.5, p[0]+2.5, p[1]+2.5], fill=INK)

def brush_strip(d, box, keep_margins=(0,0)):
    """浅粉笔刷横条（标题/标语底），两侧略超出；返回 (x0,y0,x1,y1)。"""
    x0, y0, x1, y1 = box
    d.rounded_rectangle([x0, y0, x1, y1],
                        radius=(y1-y0)/2, fill=BRUSH)
    return box

def chevron(d, cx, cy, s, color=CORAL):
    """'>' 形斜线笔触强调，s 为缩放。"""
    pts = [(cx-s, cy-s), (cx+s, cy), (cx-s, cy+s)]
    d.line(pts, fill=color, width=5)

def bezier_pts(p0, p1, c):
    pts = []
    for t in [i/20 for i in range(21)]:
        u = 1 - t
        x = u*u*p0[0] + 2*u*t*c[0] + t*t*p1[0]
        y = u*u*p0[1] + 2*u*t*c[1] + t*t*p1[1]
        pts.append((x, y))
    return pts

def curved_arrow(d, p0, p1, c):
    pts = bezier_pts(p0, p1, c)
    axis(d, pts)
    # 箭头沿末端切线方向
    a, b = pts[-2], pts[-1]
    ang = math.atan2(b[1]-a[1], b[0]-a[0])
    L = 15
    for da in (math.radians(150), math.radians(-150)):
        t = ang + da
        d.line([b, (b[0]+L*math.cos(t), b[1]+L*math.sin(t))],
               fill=INK, width=6)

# ---------------- 机器人吉祥物 ----------------
def robot(d, cx, cy, r):
    # 头顶天线球
    d.ellipse([cx-10, cy-r-34, cx+10, cy-r-10], fill=CORAL, outline=INK, width=3)
    d.arc([cx-1, cy-r-20, cx+1, cy-r-16], 90, 270, fill=DARKWIN, width=3)
    # 身体
    body_top = cy + r - 8
    body_w = int(r * 0.78)
    d.rounded_rectangle([cx-body_w, body_top, cx+body_w, body_top+int(r*0.62)],
                        radius=12, fill=(255,255,255), outline=INK, width=4)
    # 头
    d.ellipse([cx-r, cy-r, cx+r, cy+r], fill=(255,255,255), outline=INK, width=4)
    # 手（上举）
    for side in (-1, 1):
        hx = cx + side*(r+4)
        hy = cy + r - 12
        d.ellipse([hx-9, hy-16, hx+9, hy+16], fill=(255,255,255), outline=INK, width=3)
        d.line([(cx+side*r*0.6, body_top), (cx+side*(r+6), hy+2)],
               fill=INK, width=4)
    # 面罩（黑）
    mask_y = cy - int(r*0.15)
    d.rounded_rectangle([cx-int(r*0.55), mask_y-int(r*0.18),
                         cx+int(r*0.55), mask_y+int(r*0.18)],
                        radius=8, fill=INK)
    # 眯眼笑脸：一条弧线
    d.arc([cx-int(r*0.42), mask_y-int(r*0.55), cx-int(r*0.05), mask_y-int(r*0.08)],
          200, 340, fill=INK, width=4)
    d.arc([cx+int(r*0.05), mask_y-int(r*0.55), cx+int(r*0.42), mask_y-int(r*0.08)],
          200, 340, fill=INK, width=4)
    # 腮红
    for side in (-1, 1):
        sx = cx + side*int(r*0.72)
        sy = cy + int(r*0.12)
        d.ellipse([sx-7, sy-4, sx+7, sy+4], fill=BRUSH)
    # 四周黄色放射短线 + 右上红心
    for k in range(8):
        a = k * math.pi/4 - math.pi/2
        x0 = cx + (r+10)*math.cos(a); y0 = cy+(r+10)*math.sin(a)
        x1 = cx + (r+20)*math.cos(a); y1 = cy+(r+20)*math.sin(a)
        d.line([(x0,y0),(x1,y1)], fill=YELLOW, width=3)
    hx, hy = cx+int(r*0.8), cy-int(r*0.85)
    hs = int(r*0.16)
    d.polygon([(hx,hy+hs),(hx-hs,hy),(hx,hy-hs),(hx+hs,hy)],
              fill=CORAL, outline=INK)

# ---------------- 角落装饰 ----------------
def books(d, x, y, scale=1.0):
    """三本叠书（蓝/绿/粉）+ 顶芽。x,y 为底部中心。"""
    w, h = 62*scale, 12*scale
    colors = [BLUE, GREEN, PINK]
    for i, col in enumerate(colors):
        yy = y - (i+1)*h
        d.rounded_rectangle([x-w/2, yy, x+w/2, yy+h],
                            radius=2, fill=col, outline=INK, width=3)
        d.line([(x-w/2+6, yy), (x-w/2+6, yy+h)], fill=INK, width=2)
    # 顶芽
    tx, ty = x+w*0.22, y-3*h
    d.line([(tx, ty), (tx, ty-10*scale)], fill=GREEN, width=3)
    d.ellipse([tx-6*scale, ty-18*scale, tx+3*scale, ty-7*scale], fill=GREEN)

def cat(d, cx, cy, scale=1.0):
    """睡猫（橘白），cx,cy 大致中心。"""
    # 身体
    d.rounded_rectangle([cx-46*scale, cy-18*scale, cx+34*scale, cy+20*scale],
                        radius=20*scale, fill=(244,157,94), outline=INK, width=3)
    d.ellipse([cx-18*scale, cy-6*scale, cx-2*scale, cy+12*scale],
              fill=(255,255,255), outline=INK, width=2)
    # 头（在右侧）
    hx = cx+38*scale
    d.ellipse([hx-18*scale, cy-20*scale, hx+16*scale, cy+10*scale],
              fill=(244,157,94), outline=INK, width=3)
    # 耳朵
    d.polygon([(hx-14, cy-18),(hx-6, cy-30),(hx+0, cy-18)], fill=(244,157,94), outline=INK)
    # 闭眼线
    d.line([(hx-10, cy-2),(hx+2, cy-2)], fill=INK, width=2)
    # 尾巴
    d.arc([cx+20*scale, cy-24*scale, cx+46*scale, cy+6*scale], 0, 160,
          fill=(244,157,94), width=5)

def cloud(d, cx, cy, s):
    d.arc([cx-40*s, cy-14*s, cx+2*s, cy+18*s], 180, 360, fill=BLUE, width=4)
    d.arc([cx-6*s, cy-22*s, cx+34*s, cy+10*s], 240, 60, fill=BLUE, width=4)
    d.arc([cx+30*s, cy-12*s, cx+54*s, cy+12*s], 90, 250, fill=BLUE, width=4)
    d.line([(cx-40*s, cy), (cx+30*s, cy)], fill=BLUE, width=4)

def hearts(d, cx, cy, s, color=CORAL):
    d.polygon([(cx, cy+s),(cx-s, cy-s/2),(cx+s, cy-s/2)], fill=color)

# ---------------- 流程框内嵌内容 ----------------
def paint_code(d, box):
    x0,y0,x1,y1 = box
    d.rounded_rectangle(box, radius=6, fill=DARKWIN, outline=INK, width=3)
    bars = [(0, CORAL),(1, YELLOW),(2, (120,200,160)),(3, (150,180,240)),
            (4, CORAL),(5, YELLOW)]
    iy = y0+10
    ih = (y1-y0-18)/len(bars)
    for i, (_, col) in enumerate(bars):
        frac = 0.55 if i % 2 else 0.85
        y = y0+10+i*ih
        w = (x1-x0-20)*frac
        d.rounded_rectangle([x0+10, y, x0+10+w, y+ih*0.7],
                            radius=2, fill=col, width=0)
    # 左上角小圆点
    for i, col in enumerate((CORAL, YELLOW, (120,200,160))):
        d.ellipse([x0+10+i*14, y0+6, x0+10+i*14+8, y0+14], fill=col)

def paint_terminal(d, box):
    x0,y0,x1,y1 = box
    d.rounded_rectangle(box, radius=6, fill=DARKWIN, outline=INK, width=3)
    for i, col in enumerate((CORAL, YELLOW, (120,200,160))):
        d.ellipse([x0+10+i*14, y0+6, x0+10+i*14+8, y0+14], fill=col)
    d.text((x0+14, y0+26), ">$", font=F(20), fill=(150,180,240))
    for i, col in enumerate((CORAL, YELLOW, (150,180,240))):
        y = y0+52+i*20
        w = 60 if i < 2 else 30
        d.rounded_rectangle([x0+14, y, x0+14+w, y+8], radius=2, fill=col, width=0)
    # 绿色播放圆钮（右下）
    cx, cy = x1-24, y1-26
    d.ellipse([cx-14, cy-14, cx+14, cy+14], fill=(120,200,160), outline=INK, width=3)
    d.polygon([(cx-4, cy-8),(cx+8, cy),(cx-4, cy+8)], fill=(255,255,255))

def paint_report(d, box):
    x0,y0,x1,y1 = box
    d.rounded_rectangle(box, radius=6, fill=(255,255,255), outline=INK, width=3)
    iy = y0+14
    for i, col in enumerate((CORAL, YELLOW, GREEN)):
        y = iy + i*10
        w = 30 - i*6
        d.rounded_rectangle([x0+16, y, x0+16+w, y+7], radius=2, fill=col, width=0)
    # 条形图
    bx0, by1 = x0+56, y1-16
    for i, col in enumerate((GREEN, (120,200,160), YELLOW, CORAL)):
        h = [26, 40, 18, 32][i]
        d.rounded_rectangle([bx0+i*18, by1-h, bx0+i*18+12, by1],
                            radius=3, fill=col, outline=INK, width=2)
    # 蓝色眼睛（右上）
    ex, ey = x1-24, y0+28
    d.ellipse([ex-16, ey-10, ex+16, ey+12], fill=(255,255,255), outline=INK, width=3)
    d.ellipse([ex-8, ey-6, ex+8, ey+8], fill=(90,130,210))

def paint_review(d, box):
    x0,y0,x1,y1 = box
    d.rounded_rectangle(box, radius=6, fill=DARKWIN, outline=INK, width=3)
    for i, col in enumerate((CORAL, YELLOW, (120,200,160))):
        d.ellipse([x0+10+i*14, y0+6, x0+10+i*14+8, y0+14], fill=col)
    for i, col in enumerate((CORAL, YELLOW, (150,180,240), CORAL)):
        y = y0+30+i*18
        d.rounded_rectangle([x0+12, y, x0+12+70, y+9], radius=2, fill=col, width=0)
    # 灰色扳手（右下）
    cx, cy = x1-26, y1-30
    d.line([(cx-16, cy+16),(cx+12, cy-12)], fill=(180,180,180), width=7)
    d.line([(cx+16, cy-16),(cx+12, cy-12)], fill=INK, width=5)
    d.ellipse([cx-8, cy+8, cx+10, cy+26], outline=(180,180,180), width=6)
    d.ellipse([cx-8, cy+8, cx+10, cy+26], outline=INK, width=3)

def draw_frame(d, pos, box, content_extra=0):
    """pos in top/right/bottom/left; box 为框外接矩形。content_extra 扩展窗口高度。"""
    title, col, ctype = SUBS[pos]
    x0, y0, x1, y1 = box
    rr(d, box, col, INK, 4, 16)
    # 顶部小标题
    bbox = draw_segs(d, ((x0+x1)/2, y0+18), F(22), [(title, INK)])
    # 内嵌窗口
    win = [x0+12, bbox[3]+6, x1-12, y1-12-content_extra]
    if ctype == "code":      paint_code(d, win)
    elif ctype == "terminal":paint_terminal(d, win)
    elif ctype == "report":  paint_report(d, win)
    elif ctype == "review":  paint_review(d, win)

# ---------------- 顶层合成（master） ----------------
def make_master():
    im = Image.new("RGB", (1080, 608), CREAM)
    d = ImageDraw.Draw(im)
    # —— 顶部标题条 ——
    brush_strip(d, [56, 16, 1024, 66])
    f = F(46)
    bbox = draw_segs(d, (540, 41), f, [(TITLE_1, CORAL), (TITLE_2, INK)])
    chevron(d, 84, 41, 14); chevron(d, 996, 41, 14)
    # 标题下垫一层更浅笔刷（略错位，手绘感）
    d.rounded_rectangle([bbox[0]-14, bbox[3]-2, bbox[2]+14, bbox[3]+10],
                        radius=6, fill=BRUSH)

    # —— 中部环形流程 ——
    robot(d, 540, 300, 58)
    # 四个框
    top    = [430, 84,  650, 214]
    right  = [700, 196, 892, 404]
    bottom = [430, 386, 650, 516]
    left   = [188, 196, 380, 404]
    draw_frame(d, "top",    top)
    draw_frame(d, "right",  right)
    draw_frame(d, "bottom", bottom, content_extra=0)
    draw_frame(d, "left",   left)
    # 环形箭头（顺时针）—— 对角线转折点
    curved_arrow(d, (656, 150), (790, 198), (730, 138))   # top→right（右上框边中部出发，避开标题）
    curved_arrow(d, (820, 370), (640, 470), (760, 470))   # right→bottom
    curved_arrow(d, (500, 500), (340, 380), (420, 470))   # bottom→left
    curved_arrow(d, (260, 180), (560, 100), (420, 120))   # left→top

    # —— 底部标语横幅 ——
    brush_strip(d, [150, 552, 930, 594])
    fb = F(40)
    segs = [(SLOGAN[:4], INK), (SLOGAN[4:7], INK), (SLOGAN[7:], CORAL if False else INK)]
    # 标语里把关键词「验证」用珊瑚红
    segs = [("给 AI 一双能", INK), ("验证", CORAL), ("的眼睛", INK)]
    bb = draw_segs(d, (540, 573), fb, segs)
    d.rounded_rectangle([bb[0]-16, bb[3]-2, bb[2]+16, bb[3]+12], radius=6, fill=BRUSH)

    # —— 四角装饰 ——
    books(d, 92, 596, 1.15)
    cat(d, 985, 540, 1.0)
    cloud(d, 250, 100, 1.0); cloud(d, 850, 96, 0.8)
    hearts(d, 200, 130, 8, CORAL); hearts(d, 900, 300, 6, CORAL)
    hearts(d, 430, 300, 5, YELLOW); hearts(d, 660, 350, 5, YELLOW)
    # 散落小笔触
    d.line([(640, 96),(690, 112)], fill=CORAL, width=4)
    d.line([(390, 96),(350, 112)], fill=CORAL, width=4)
    # 右下角水印
    wf = F(30)
    wt = d.textlength(WATER, font=wf)
    d.text((1080-wt-20, 600-34), WATER, font=wf, fill=INK)
    return im

# ---------------- 2.35:1 cover：标题左上 + 吉祥物居中 + 左右两框 ----------------
def make_cover():
    W, H = 900, 383
    im = Image.new("RGB", (W, H), CREAM)
    d = ImageDraw.Draw(im)
    # 中央垂直 60% 安全带
    band = (H*0.2, H*0.8)   # (77, 306)
    # —— 顶部标题条（居左上，落在安全带内）——
    brush_strip(d, [40, 88, 720, 138])
    f = F(34)
    bbox = draw_segs(d, (380, 113), f, [(TITLE_1, CORAL), (TITLE_2, INK)])
    d.rounded_rectangle([bbox[0]-12, bbox[3]-2, bbox[2]+12, bbox[3]+8],
                        radius=5, fill=BRUSH)
    chevron(d, 56, 113, 12); chevron(d, 700, 113, 12)
    # —— 吉祥物居中 ——
    robot(d, 455, 205, 52)
    # —— 左右两个流程框（在安全带内）——
    draw_frame(d, "left",   [60,  130, 252, 300])
    draw_frame(d, "right",  [645, 130, 837, 300])
    # 箭头：左框 → 吉祥物，吉祥物 → 右框（真实连接元素）
    curved_arrow(d, (258, 215), (398, 212), (330, 190))
    curved_arrow(d, (512, 215), (636, 222), (575, 195))
    # —— 角饰 ——
    cloud(d, 250, 120, 0.8)
    books(d, 74, 372, 0.85)
    cat(d, 700, 360, 0.75)
    hearts(d, 640, 110, 6, CORAL); hearts(d, 320, 130, 5, YELLOW)
    # —— 水印 ——
    wf = F(24)
    wt = d.textlength(WATER, font=wf)
    d.text((W-wt-14, H-32), WATER, font=wf, fill=INK)
    return im

# ---------------- 1:1 square：吉祥物居中 + 标题置顶 + 两框置底 ----------------
def make_square():
    S = 500
    im = Image.new("RGB", (S, S), CREAM)
    d = ImageDraw.Draw(im)
    band = (S*0.2, S*0.8)   # (100, 400)
    # —— 标题置顶（安全带内，留≥24px 边距）——
    brush_strip(d, [28, 104, 472, 152])
    f = F(24)
    bbox = draw_segs(d, (250, 128), f, [(TITLE_1, CORAL), (TITLE_2, INK)])
    d.rounded_rectangle([bbox[0]-10, bbox[3]-2, bbox[2]+10, bbox[3]+8],
                        radius=4, fill=BRUSH)
    # —— 吉祥物居中 ——
    robot(d, 250, 235, 50)
    # —— 两个流程框置底（安全带内）——
    draw_frame(d, "right",  [34,  330, 246, 430], content_extra=0)
    draw_frame(d, "bottom", [254, 330, 466, 430])
    # —— 角饰（避开流程框与标题，互不压盖）——
    books(d, 72, 96, 0.7)          # 左上角，标题上方
    cloud(d, 430, 100, 0.65)       # 右上角
    cat(d, 60, 474, 0.6)           # 左下角，流程框下方空白带
    cloud(d, 160, 318, 0.5)        # 吉祥物与框之间
    # —— 水印 ——
    wf = F(22)
    wt = d.textlength(WATER, font=wf)
    d.text((S-wt-12, S-30), WATER, font=wf, fill=INK)
    return im

def check_band(title, size, band_frac=0.6):
    """自检：对单色背景估算，若有文字超出中央 60% 会在此提示（主检查在画内）。"""
    print(f"[check] {title}: 画布 {size}, 中央{int(band_frac*100)}%安全带 y∈"
          f"[{size[1]*0.2:.0f},{size[1]*0.8:.0f}]")

def main():
    os.makedirs(OUT, exist_ok=True)
    jobs = {
        "hn-ai-top5-master.png": make_master,
        "hn-ai-top5-cover.png":  make_cover,
        "hn-ai-top5-square.png": make_square,
    }
    for name, fn in jobs.items():
        im = fn()
        im.save(os.path.join(OUT, name))
        check_band(name, im.size)
        print(f"  saved {name}  {im.size[0]}x{im.size[1]}")

if __name__ == "__main__":
    main()