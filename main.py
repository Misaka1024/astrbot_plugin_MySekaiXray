import os
import re
import json
import tempfile
import traceback
from collections import Counter, OrderedDict

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
ICON_DIR = os.path.join(PLUGIN_DIR, 'icon')
MAP_DIR = os.path.join(PLUGIN_DIR, 'map')

# 后端 API 地址（html 工作区的 Flask 服务）
API_BASE = 'http://127.0.0.1:5100'

SITE_ORDER = ['初始空地', '心愿沙滩', '烂漫花田', '忘却之所']

MAP_COLORS = {
    '初始空地': (76, 175, 80),
    '心愿沙滩': (66, 165, 245),
    '烂漫花田': (240, 98, 146),
    '忘却之所': (149, 117, 205),
}

ICON_MAP = {
    '心愿木材': 'Wood_of_Feelings.png', '硬质木材': 'Heavy_Wood.png',
    '轻质木材': 'Light_Wood.png', '粘稠的树液': 'Sticky_Sap.png',
    '夕桐': 'Evening_Paulownia.png', '心愿石块': 'Pebble_of_Feelings.png',
    '铜': 'Copper.png', '铁': 'Iron.png', '粘土': 'Clay.png',
    '漂亮的玻璃': 'Clear_Glass.png', '闪耀石英': 'Sparkly_Quartz.png',
    '钻石': 'Diamond.png', '螺丝': 'Screw.png', '钉子': 'Nail.png',
    '塑料': 'Plastic.png', '马达': 'Motor.png', '电池': 'Battery.png',
    '灯泡': 'Lightbulb.png', '电路板': 'Circuit_Board.png',
    '四叶草': 'Four-Leaf_Clover.png', '顺滑的亚麻': 'Smooth_Linen.png',
    '蓬松的棉花': 'Fluffy_Cotton.png', '花瓣': 'Petal.png',
    '空白的音色': 'Pure_Tone.png', '蓝天海玻璃': 'Blue_Sky_Sea_Glass.png',
    '月光石': 'Moonlight_Stone.png', '流星碎片': 'Fragment_of_Shooting_Star.png',
    '雪之结晶': 'Snowflake.png', '最棒斧子的斧刃': 'Best_Axe_Blade.png',
    '最棒十字镐的镐尖': 'Best_Pickaxe_Tip.png', '雷光石': 'Lightning_Stone.png',
    '彩虹玻璃': 'Rainbow_Glass.png',
    '空白设计图': 'Blank_Blueprint.png', '多余设计图': 'Extra_Blueprint.png',
    '多余唱片': 'Extra_Record.png', '设计图碎片': 'Blueprint_Scrap.png',
    '蓬松的云': 'Fluffy_Cloud.png', '宇宙零件': 'Space_Component.png',
    'SEKAI碎片': 'SEKAI_Bits.png',
}

MAP_BG = {
    '初始空地': 'grassland.png',
    '心愿沙滩': 'beach.png',
    '烂漫花田': 'flowergarden.png',
    '忘却之所': 'memorialplace.png',
}

PALETTE = [
    (231, 76, 60), (46, 204, 113), (52, 152, 219), (241, 196, 15),
    (155, 89, 182), (230, 126, 34), (26, 188, 156), (192, 57, 43),
    (22, 160, 133), (41, 128, 185), (142, 68, 173), (243, 156, 18),
    (211, 84, 0), (44, 62, 80), (127, 140, 141), (39, 174, 96),
]


# ========== 工具函数 ==========
def _get_font(size):
    """跨平台字体加载"""
    from PIL import ImageFont
    font_paths = [
        os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts', 'msyh.ttc'),
        '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc',
        os.path.join(PLUGIN_DIR, 'fonts', 'NotoSansSC-Regular.ttf'),
    ]
    for fp in font_paths:
        if os.path.isfile(fp):
            return ImageFont.truetype(fp, size)
    return ImageFont.load_default()


def _load_icon_cache():
    """预加载所有图标"""
    from PIL import Image
    cache = {}
    for name, fname in ICON_MAP.items():
        path = os.path.join(ICON_DIR, fname)
        if os.path.isfile(path):
            cache[name] = Image.open(path).convert('RGBA')
    return cache


# ========== 统计图生成 ==========
def generate_summary_chart(summary, outpath):
    """从 summary dict 生成资源数量统计图"""
    from PIL import Image, ImageDraw

    FONT_TITLE = _get_font(20)
    FONT_MAP = _get_font(16)
    FONT_NUM = _get_font(10)

    icon_cache = _load_icon_cache()
    seed_path = os.path.join(ICON_DIR, 'seed.png')
    seed_icon = Image.open(seed_path).convert('RGBA') if os.path.isfile(seed_path) else None

    # 整理数据：按数量降序
    data = {}
    for site_name in SITE_ORDER:
        if site_name not in summary:
            continue
        items = sorted(summary[site_name].items(), key=lambda t: t[1], reverse=True)
        data[site_name] = items

    ICON_S = 28
    CELL_W, CELL_H = 44, 42
    LEFT_PAD = 16
    MAP_TITLE_H = 28
    MAP_GAP = 12
    COLS = 8

    def block_height(items):
        rows = (len(items) + COLS - 1) // COLS
        return MAP_TITLE_H + rows * CELL_H + MAP_GAP

    site_list = list(data.keys())
    left_sites = site_list[:2]
    right_sites = site_list[2:]

    col_content_w = LEFT_PAD + COLS * CELL_W + LEFT_PAD
    COL_GAP = 12

    left_h = sum(block_height(data[sn]) for sn in left_sites)
    right_h = sum(block_height(data[sn]) for sn in right_sites)
    top_pad = 40
    total_h = top_pad + max(left_h, right_h) + 6
    total_w = col_content_w * 2 + COL_GAP

    img = Image.new('RGBA', (total_w, total_h), (245, 228, 232, 255))
    draw = ImageDraw.Draw(img)
    draw.text((LEFT_PAD, 8), '资源数量统计', fill=(80, 60, 70), font=FONT_TITLE)

    for col_idx, sites in enumerate([left_sites, right_sites]):
        x_base = col_idx * (col_content_w + COL_GAP)
        y = top_pad
        for site_name in sites:
            items = data[site_name]
            color = MAP_COLORS.get(site_name, (200, 200, 200))
            draw.text((x_base + LEFT_PAD, y + 4), site_name, fill=color, font=FONT_MAP)
            y += MAP_TITLE_H
            for i, (name, count) in enumerate(items):
                col = i % COLS
                row = i // COLS
                cx = x_base + LEFT_PAD + col * CELL_W
                cy = y + row * CELL_H
                ix = cx + (CELL_W - ICON_S) // 2
                iy = cy
                if name in icon_cache:
                    ic = icon_cache[name].resize((ICON_S, ICON_S), Image.LANCZOS)
                    img.paste(ic, (ix, iy), ic)
                else:
                    draw.rectangle([(ix, iy), (ix + ICON_S, iy + ICON_S)], fill=color + (120,))
                    if seed_icon:
                        si = seed_icon.resize((ICON_S - 4, ICON_S - 4), Image.LANCZOS)
                        img.paste(si, (ix + 2, iy + 2), si)
                ct = str(count)
                tw = int(FONT_NUM.getlength(ct))
                tx = cx + (CELL_W - tw) // 2
                ty = iy + ICON_S + 1
                draw.text((tx, ty), ct, fill=(60, 50, 55), font=FONT_NUM)
            total_rows = (len(items) + COLS - 1) // COLS
            y += total_rows * CELL_H + MAP_GAP

    img.save(outpath)


# ========== 四宫格地图生成 ==========
def generate_grid_map(map_data, outpath):
    """从 mapData dict 生成四宫格地图"""
    from PIL import Image, ImageDraw

    ICON_SIZE = 20
    FONT_COUNT_BG = _get_font(11)

    icon_cache = {}
    for name, fname in ICON_MAP.items():
        path = os.path.join(ICON_DIR, fname)
        if os.path.isfile(path):
            icon_cache[name] = Image.open(path).convert('RGBA').resize((ICON_SIZE, ICON_SIZE), Image.LANCZOS)

    map_images = OrderedDict()
    map_item_px = OrderedDict()
    CROP_PAD = 50

    for site_name in SITE_ORDER:
        if site_name not in map_data:
            continue
        drops = map_data[site_name]

        # 按坐标聚合
        coords = {}
        for d in drops:
            name, x, z = d['name'], d['x'], d['z']
            if site_name in ('忘却之所', '心愿沙滩'):
                rx, rz = x, -z
            else:
                rx, rz = -z, -x
            coords.setdefault((rx, rz), {})
            coords[(rx, rz)][name] = coords[(rx, rz)].get(name, 0) + 1

        if not coords:
            continue

        all_x = [x for x, z in coords]
        all_z = [z for x, z in coords]
        min_x, max_x = min(all_x) - 1, max(all_x) + 1
        min_z, max_z = min(all_z) - 1, max(all_z) + 1

        unique_names = list(OrderedDict.fromkeys(d['name'] for d in drops))
        color_map = {n: PALETTE[i % len(PALETTE)] for i, n in enumerate(unique_names)}

        bg_file = os.path.join(MAP_DIR, MAP_BG.get(site_name, ''))
        if not os.path.isfile(bg_file):
            continue

        img = Image.open(bg_file).convert('RGBA')
        bg_w, bg_h = img.size
        range_x = max_x - min_x + 1
        range_z = max_z - min_z + 1
        usable_w = bg_w * 0.70
        usable_h = bg_h * 0.70
        scale = min(usable_w / range_x, usable_h / range_z)
        scale_x = scale
        scale_z = scale

        # 地图特定偏移调整
        if site_name == '初始空地':
            scale_x += 10; scale_z += 10
        elif site_name == '烂漫花田':
            scale_x += 5; scale_z += 3
        elif site_name == '忘却之所':
            scale_x += 3
        elif site_name == '心愿沙滩':
            scale_x += 4; scale_z += 3.5

        offset_x = (bg_w - range_x * scale_x) / 2
        offset_z = (bg_h - range_z * scale_z) / 2

        if site_name == '初始空地':
            offset_x += 30
        elif site_name == '烂漫花田':
            offset_z -= 70; offset_x += 15
        elif site_name == '忘却之所':
            offset_x -= 225
        elif site_name == '心愿沙滩':
            offset_x += 100

        def coord_to_px(cx, cz, _ox=offset_x, _oz=offset_z, _mx=min_x, _mz=min_z, _sx=scale_x, _sz=scale_z):
            px = _ox + (cx - _mx) * _sx + _sx / 2
            pz = _oz + (cz - _mz) * _sz + _sz / 2
            return int(px), int(pz)

        draw = ImageDraw.Draw(img)
        ICON_BG = 28
        item_pixels = []

        for (cx, cz), name_counts in coords.items():
            px, py = coord_to_px(cx, cz)
            item_pixels.append((px, py))
            main_name = max(name_counts, key=name_counts.get)
            total_count = sum(name_counts.values())

            if main_name in icon_cache:
                icon_img = icon_cache[main_name].resize((ICON_BG, ICON_BG), Image.LANCZOS)
                img.paste(icon_img, (px - ICON_BG // 2, py - ICON_BG // 2), icon_img)
            else:
                color = color_map.get(main_name, PALETTE[0])
                draw.ellipse([px - 10, py - 10, px + 10, py + 10], fill=color + (200,), outline=(255, 255, 255, 200))

            tx, ty = px + ICON_BG // 2 - 4, py + ICON_BG // 2 - 8
            for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                draw.text((tx+dx, ty+dy), str(total_count), fill=(0, 0, 0), font=FONT_COUNT_BG)
            draw.text((tx, ty), str(total_count), fill=(255, 255, 255), font=FONT_COUNT_BG)

        map_images[site_name] = img
        map_item_px[site_name] = item_pixels

    # 裁剪并合成四宫格
    if len(map_images) < 2:
        return

    bboxes = {}
    for sn in SITE_ORDER:
        if sn not in map_images:
            continue
        img = map_images[sn]
        pixels = map_item_px.get(sn, [])
        if not pixels:
            bboxes[sn] = (0, 0, img.width, img.height)
            continue
        xs = [p[0] for p in pixels]
        ys = [p[1] for p in pixels]
        bboxes[sn] = (min(xs) - CROP_PAD, min(ys) - CROP_PAD,
                       max(xs) + CROP_PAD, max(ys) + CROP_PAD)

    spans = [max(r - l, b - t) for l, t, r, b in bboxes.values()]
    uniform_span = max(spans)

    cropped = OrderedDict()
    for sn in SITE_ORDER:
        if sn not in map_images:
            continue
        img = map_images[sn]
        l, t, r, b = bboxes[sn]
        cx, cy = (l + r) / 2, (t + b) / 2
        half = uniform_span / 2
        crop_l, crop_t = int(cx - half), int(cy - half)
        crop_r, crop_b = int(cx + half), int(cy + half)
        if crop_l < 0: crop_r -= crop_l; crop_l = 0
        if crop_t < 0: crop_b -= crop_t; crop_t = 0
        if crop_r > img.width: crop_l -= (crop_r - img.width); crop_r = img.width
        if crop_b > img.height: crop_t -= (crop_b - img.height); crop_b = img.height
        crop_l, crop_t = max(0, crop_l), max(0, crop_t)
        cropped[sn] = img.crop((crop_l, crop_t, crop_r, crop_b))

    target = max(c.width for c in cropped.values())
    resized = OrderedDict()
    for sn, cimg in cropped.items():
        resized[sn] = cimg.resize((target, target), Image.LANCZOS)

    grid = Image.new('RGBA', (target * 2, target * 2), (0, 0, 0, 255))
    panels = list(resized.values())
    positions = [(0, 0), (target, 0), (0, target), (target, target)]
    for panel, (gx, gy) in zip(panels, positions):
        grid.paste(panel, (gx, gy), panel if panel.mode == 'RGBA' else None)
    grid.save(outpath)


# ========== 绑定数据存储 ==========
BINDFILE = os.path.join(PLUGIN_DIR, 'bindings.json')


def load_bindings():
    if os.path.isfile(BINDFILE):
        with open(BINDFILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_bindings(data):
    with open(BINDFILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)


# 帮助页面地址（代理模块安装指引）
HELP_URL = "https://www.artenas.online/MySekai/index.html"


# ========== AstrBot 插件主类 ==========
@register("astrbot_plugin_MySekaiXray", "Artenas", "MySekai 采集数据分析插件", "1.0.0")
class MySekaiXrayPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.bindings = {}

    async def initialize(self):
        self.bindings = load_bindings()
        logger.info(f"MySekaiXray 插件已加载，已绑定 {len(self.bindings)} 个用户")

    async def _fetch_data(self, uid: str):
        """从后端 API 获取用户数据"""
        import aiohttp
        url = f"{API_BASE}/api/mysekai/query/{uid}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 404:
                    return None, "未找到该 UID 的数据，请先安装代理模块抓包上传\n发送 /烤森帮助 查看安装方法"
                if resp.status != 200:
                    return None, f"后端请求失败 (HTTP {resp.status})"
                return await resp.json(), None

    @filter.command("烤森绑定")
    async def bind_command(self, event: AstrMessageEvent):
        """绑定游戏 UID 用法: 小奏烤森绑定 <游戏UID>"""
        raw = event.message_str.strip()
        match = re.search(r'(\d{5,})', raw)
        uid = match.group(1) if match else ''

        if not uid:
            yield event.plain_result("请输入你的游戏 UID\n用法: 小奏烤森绑定 <游戏UID>")
            return

        qq_id = event.get_sender_id()
        self.bindings[qq_id] = uid
        save_bindings(self.bindings)
        yield event.plain_result(f"小奏绑定成功~ \nQQ: {qq_id}\nUID: {uid}")

    @filter.command("烤森地图")
    async def map_command(self, event: AstrMessageEvent):
        """查询已绑定 UID 的 MySekai 采集数据，返回资源图片"""
        qq_id = event.get_sender_id()
        uid = self.bindings.get(qq_id)

        if not uid:
            yield event.plain_result("你还没有绑定游戏 UID\n请先发送: 小奏烤森绑定 <你的UID>")
            return

        try:
            record, err = await self._fetch_data(uid)
        except Exception as e:
            logger.error(f"API 请求异常: {traceback.format_exc()}")
            yield event.plain_result(f"无法连接后端服务: {e}")
            return

        if err:
            yield event.plain_result(err)
            return

        data = record.get('data', {})
        summary = data.get('summary', {})
        map_data = data.get('mapData', {})

        if not summary:
            yield event.plain_result("你的数据为空，请先通过代理模块抓包上传")
            return

        tmpdir = tempfile.mkdtemp(prefix='mysekai_xray_')
        try:
            chart_path = os.path.join(tmpdir, 'chart.png')
            generate_summary_chart(summary, chart_path)
            if os.path.isfile(chart_path):
                yield event.image_result(chart_path)

            grid_path = os.path.join(tmpdir, 'grid.png')
            generate_grid_map(map_data, grid_path)
            if os.path.isfile(grid_path):
                yield event.image_result(grid_path)
        except Exception as e:
            logger.error(f"图片生成异常: {traceback.format_exc()}")
            yield event.plain_result(f"图片生成出错: {e}")

    @filter.command("烤森帮助")
    async def help_command(self, event: AstrMessageEvent):
        """查看 MySekai Xray 使用帮助和模块安装地址"""
        help_text = (
            "世界计划MySekai资源查询\n\n"
            "指令列表:\n"
            "小奏烤森绑定 <UID> - 绑定游戏UID\n"
            "小奏烤森地图 - 查看采集资源分布\n"
            "小奏烤森帮助 - 查看本帮助\n\n"
            f"代理模块安装地址:\n{HELP_URL}"
        )
        yield event.plain_result(help_text)

    async def terminate(self):
        logger.info("MySekaiXray 插件已卸载")
