import os, io, requests
from PIL import Image, ImageDraw, ImageEnhance
from post_image import font, PAGE_ID, TOKEN

BASE = f"https://graph.facebook.com/v21.0/{PAGE_ID}"

def story_image(img, headline, text, options=None, sub=""):
    W, H = 1080, 1920
    iw, ih = img.size
    s = max(W / iw, H / ih)
    img = img.resize((int(iw * s) + 1, int(ih * s) + 1))
    x0, y0 = (img.width - W) // 2, (img.height - H) // 2
    img = img.crop((x0, y0, x0 + W, y0 + H))
    img = ImageEnhance.Brightness(img).enhance(0.4)
    d = ImageDraw.Draw(img)

    def wrap(t, f, maxw):
        lines, cur = [], ""
        for word in t.split():
            test = (cur + " " + word).strip()
            if d.textlength(test, font=f) <= maxw:
                cur = test
            else:
                lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)
        return lines

    items = []
    for ln in wrap(headline, font(80), 900):
        items.append((ln, font(80), (255, 215, 0)))
    items.append(("", font(40), None))
    for ln in wrap(text, font(58), 900):
        items.append((ln, font(58), (255, 255, 255)))
    if options:
        items.append(("", font(40), None))
        for i, o in enumerate(options):
            for ln in wrap("ABCD"[i] + ") " + o, font(52), 900):
                items.append((ln, font(52), (200, 255, 200)))
    if sub:
        items.append(("", font(40), None))
        for ln in wrap(sub, font(44), 900):
            items.append((ln, font(44), (220, 220, 220)))

    total = sum(f.size + 22 for _, f, _ in items)
    y = (H - total) // 2
    for ln, f, col in items:
        if ln:
            x = (W - d.textlength(ln, font=f)) / 2
            d.text((x + 3, y + 3), ln, font=f, fill=(0, 0, 0))
            d.text((x, y), ln, font=f, fill=col)
        y += f.size + 22
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=92)
    return buf.getvalue()

def photo_story(data):
    r = requests.post(BASE + "/photos", data={"access_token": TOKEN, "published": "false"},
                      files={"source": ("s.jpg", data, "image/jpeg")}, timeout=120)
    print("story up", r.status_code, r.text[:200])
    r.raise_for_status()
    pid = r.json()["id"]
    r = requests.post(BASE + "/photo_stories", data={"access_token": TOKEN, "photo_id": pid}, timeout=120)
    print("photo story", r.status_code, r.text[:200])
    r.raise_for_status()

def video_story(path):
    r = requests.post(BASE + "/video_stories", data={"upload_phase": "start", "access_token": TOKEN}, timeout=60)
    print("vstory start", r.status_code, r.text[:200])
    r.raise_for_status()
    info = r.json()
    vid, url = info["video_id"], info["upload_url"]
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        u = requests.post(url, headers={"Authorization": "OAuth " + TOKEN,
                                        "offset": "0", "file_size": str(size)},
                          data=f, timeout=600)
    print("vstory upload", u.status_code, u.text[:200])
    u.raise_for_status()
    r = requests.post(BASE + "/video_stories", data={"upload_phase": "finish", "video_id": vid,
                                                      "access_token": TOKEN}, timeout=120)
    print("video story", r.status_code, r.text[:200])
    r.raise_for_status()
