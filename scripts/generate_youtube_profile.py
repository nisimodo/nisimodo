#!/usr/bin/env python3
import os
import sys
import argparse
import requests
from io import BytesIO
from PIL import Image, ImageFilter, ImageDraw, ImageFont


def find_japanese_font():
    # Try common system font locations and candidate names for Japanese support
    candidates = ['Hiragino', 'HiraginoSans', 'NotoSansCJK', 'NotoSansJP', 'YuGothic', 'YuGothicUI', 'Meiryo', 'IPAexGothic', '源ノ角ゴ', 'TakaoPGothic']
    search_dirs = [
        '/System/Library/Fonts',
        '/Library/Fonts',
        os.path.expanduser('~/Library/Fonts'),
        '/usr/share/fonts',
        os.path.expanduser('~/.local/share/fonts'),
    ]
    for d in search_dirs:
        if not os.path.isdir(d):
            continue
        for root, _, files in os.walk(d):
            for f in files:
                fname = f.lower()
                for key in candidates:
                    if key.lower() in fname:
                        return os.path.join(root, f)
    return None


def get_channel_id(api_key, query):
    url = 'https://www.googleapis.com/youtube/v3/search'
    params = {'part': 'snippet', 'q': query, 'type': 'channel', 'maxResults': 1, 'key': api_key}
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    data = r.json()
    items = data.get('items', [])
    if not items:
        raise RuntimeError('channel not found for query: %s' % query)
    return items[0]['snippet']['channelId']


def get_channel_info(api_key, channel_id):
    url = 'https://www.googleapis.com/youtube/v3/channels'
    params = {'part': 'snippet,statistics', 'id': channel_id, 'key': api_key}
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    data = r.json()
    items = data.get('items', [])
    if not items:
        raise RuntimeError('channel id not found: %s' % channel_id)
    item = items[0]
    snippet = item.get('snippet', {})
    stats = item.get('statistics', {})
    title = snippet.get('title', '')
    subs = stats.get('subscriberCount', '0')
    thumbnails = snippet.get('thumbnails', {})
    # prefer high quality
    for key in ('maxres', 'high', 'standard', 'medium', 'default'):
        if key in thumbnails:
            thumb = thumbnails[key].get('url')
            if thumb:
                return title, subs, thumb
    return title, subs, None


def download_image(url):
    r = requests.get(url, stream=True, timeout=15)
    r.raise_for_status()
    return Image.open(BytesIO(r.content)).convert('RGB')


def create_profile_image(icon_img, title, subs, out_path, size=(1200,360)):
    w, h = size
    # white canvas
    canvas = Image.new('RGB', (w, h), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)

    # draw rounded dark card
    margin = 20
    card_bbox = (margin, margin, w - margin, h - margin)
    card_radius = 24
    card_color = (18, 20, 24)
    draw.rounded_rectangle(card_bbox, radius=card_radius, fill=card_color)

    # compute positions inside card
    inner_x0, inner_y0, inner_x1, inner_y1 = card_bbox
    inner_w = inner_x1 - inner_x0
    inner_h = inner_y1 - inner_y0

    # (removed small top-left icon) — only use the large profile image on the right
    padding_left = inner_x0 + 40
    name_x = padding_left
    name_y = inner_y0 + 28

    # prepare fonts (reuse detection logic) — larger sizes for this layout
    big_num_size = max(72, int(inner_h * 0.45))
    # increase channel name size (approximately 2x larger)
    name_size = max(56, int(inner_h * 0.32))
    small_label_size = max(18, int(inner_h * 0.08))

    font_path = os.environ.get('PROFILE_FONT') or '/Users/nm/vantan/テスト用/画像化/Corporate-Logo-Bold-ver3.otf'
    if not os.path.isfile(font_path):
        font_path = find_japanese_font()
    try:
        font_num = ImageFont.truetype(font_path, big_num_size)
        font_name = ImageFont.truetype(font_path, name_size)
        font_label = ImageFont.truetype(font_path, small_label_size)
    except Exception:
        try:
            font_num = ImageFont.truetype('DejaVuSans-Bold.ttf', big_num_size)
            font_name = ImageFont.truetype('DejaVuSans.ttf', name_size)
            font_label = ImageFont.truetype('DejaVuSans.ttf', small_label_size)
        except Exception:
            font_num = ImageFont.load_default()
            font_name = ImageFont.load_default()
            font_label = ImageFont.load_default()

    # draw channel name at top-left of the card
    # name_x and name_y set above
    try:
        draw.text((name_x, name_y), title, font=font_name, fill=(255,255,255), stroke_width=1, stroke_fill=(0,0,0))
    except TypeError:
        draw.text((name_x+1, name_y+1), title, font=font_name, fill=(0,0,0))
        draw.text((name_x, name_y), title, font=font_name, fill=(255,255,255))

    # draw subscriber number and label: label larger and bottom-aligned with number
    label = "登録者"
    subs_num = subs if subs and subs.isdigit() else '0'
    try:
        subs_val = f"{int(subs_num):,}"
    except Exception:
        subs_val = str(subs_num)

    # measure text sizes
    try:
        num_w, num_h = font_num.getsize(subs_val)
    except Exception:
        num_w, num_h = (len(subs_val) * big_num_size // 2, big_num_size)
    try:
        label_w, label_h = font_label.getsize(label)
    except Exception:
        label_w, label_h = (len(label) * small_label_size, small_label_size)

    # bottom baseline coordinate (distance above card bottom)
    baseline_bottom = inner_y1 - 40

    # compute y positions so bottoms align
    num_y = baseline_bottom - num_h
    label_y = baseline_bottom - label_h

    label_x = padding_left
    num_x = label_x + label_w + 12

    # draw label (larger) and number to its right, bottom-aligned
    try:
        draw.text((label_x, label_y), label, font=font_label, fill=(200,200,200))
    except Exception:
        draw.text((label_x, label_y), label, font=font_label, fill=(200,200,200))

    try:
        draw.text((num_x, num_y), subs_val, font=font_num, fill=(255,255,255), stroke_width=2, stroke_fill=(0,0,0))
    except TypeError:
        draw.text((num_x+2, num_y+2), subs_val, font=font_num, fill=(0,0,0))
        draw.text((num_x, num_y), subs_val, font=font_num, fill=(255,255,255))

    # large circular profile image on right
    profile_size = int(inner_h * 0.95)
    profile_x = inner_x1 - profile_size - 30
    profile_y = inner_y0 + (inner_h - profile_size)//2
    profile_img = icon_img.copy().resize((profile_size, profile_size))
    mask2 = Image.new('L', (profile_size, profile_size), 0)
    md = ImageDraw.Draw(mask2)
    md.ellipse((0,0,profile_size,profile_size), fill=255)
    # shadow for profile
    shadow = Image.new('RGBA', (profile_size, profile_size), (0,0,0,0))
    sd = ImageDraw.Draw(shadow)
    sd.ellipse((0,0,profile_size,profile_size), fill=(0,0,0,180))
    shadow = shadow.filter(ImageFilter.GaussianBlur(10))
    canvas.paste(shadow, (profile_x+6, profile_y+6), shadow)
    canvas.paste(profile_img, (profile_x, profile_y), mask2)

    os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
    canvas.save(out_path, optimize=True, quality=90)

    pass


def ensure_readme_has_image(readme_path, image_path):
    try:
        with open(readme_path, 'r', encoding='utf-8') as f:
            text = f.read()
    except FileNotFoundError:
        text = ''
    md_line = f"![YouTube Channel]({image_path})\n\n"
    if md_line.strip() in text:
        return False
    # insert after first heading or at top
    if text.startswith('#'):
        parts = text.split('\n', 1)
        new = parts[0] + '\n\n' + md_line + (parts[1] if len(parts)>1 else '')
    else:
        new = md_line + text
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(new)
    return True


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--query', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--readme', required=False)
    args = p.parse_args()
    # API key must be provided via the YOUTUBE_API_KEY environment variable
    api_key = os.environ.get('YOUTUBE_API_KEY')
    if not api_key:
        print('Missing YOUTUBE_API_KEY environment variable', file=sys.stderr)
        sys.exit(2)

    channel_id = get_channel_id(api_key, args.query)
    title, subs, thumb = get_channel_info(api_key, channel_id)
    if not thumb:
        print('No thumbnail found, aborting', file=sys.stderr)
        sys.exit(3)
    icon_img = download_image(thumb)
    create_profile_image(icon_img, title, subs, args.output)
    modified = False
    if args.readme:
        modified = ensure_readme_has_image(args.readme, args.output)
    if modified:
        print('README updated')


if __name__ == '__main__':
    main()
