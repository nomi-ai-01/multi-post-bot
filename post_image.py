import os, io, json, random, requests
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

GEMINI_KEY = os.environ["GEMINI_API_KEY"]
PIX_KEY = os.environ["PIXABAY_KEY"]
PAGE_ID = os.environ["FB_PAGE_ID"]
TOKEN = os.environ["FB_PAGE_TOKEN"]
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

FORMATS = {
    "quiz": "General knowledge quiz. text = ek chota sawal. options = 4 jawab (sirf ek sahi). answer = sahi option ka text. headline = 'QUIZ'.",
    "this_or_that": "This or That. headline = 'THIS or THAT'. text = ek mazedar sawal. options = 2 choices.",
    "fact": "Dilchasp fact. headline = 'DILCHASP FACT'. text = 1-2 chhoti lines. options = [].",
    "riddle": "Paheli. headline = 'PAHELI'. text = paheli (2-3 chhoti lines). options = []. answer = jawab.",
}

def gemini(prompt):
    for model in ["gemini-2.5-flash", "gemini-3.5-flash", "gemini-2.5-flash-lite"]:
        r = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            headers={"x-goog-api-key": GEMINI_KEY, "Content-Type": "application/json"},
            json={"contents": [{"parts": [{"text": prompt}]}],
                  "generationConfig": {"responseMimeType": "application/json", "temperature": 1.1}},
            timeout=90)
        if r.ok:
            return json.loads(r.json()["candidates"][0]["content"]["parts"][0]["text"])
        print(model, r.status_code, r.text[:200])
    raise RuntimeError("Gemini fail")

def get_photo(q):
    r = requests.get("https://pixabay.com/api/", params={
        "key": PIX_KEY, "q": q, "image_type": "photo", "orientation": "horizontal",
        "per_page": 30, "safesearch": "true", "min_width": 1000}, timeout=60)
    r.raise_for_status()
    hits = r.json()["hits"]
    if not hits:
        raise RuntimeError("no photo for " + q)
    b = requests.get(random.choice(hits)["largeImageURL"], timeout=60)
    b.raise_for_status()
    return Image.open(io.BytesIO(b.content)).convert("RGB")

def font(n):
    try:
        return ImageFont.truetype(FONT, n)
    except Exception:
        return ImageFont.load_default()

def compose(img, headline, text, options):
    S = 1080
    w, h = img.size
    m = min(w, h)
    x0, y0 = (w - m) // 2, (h - m) // 2
    img = img.crop((x0, y0, x0 + m, y0 + m)).resize((S, S))
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
    for ln in wrap(headline, font(70), 900):
        items.append((ln, font(70), (255, 215, 0)))
    items.append(("", font(30), None))
    for ln in wrap(text, font(52), 900):
        items.append((ln, font(52), (255, 255, 255)))
    if options:
        items.append(("", font(30), None))
        for i, o in enumerate(options):
            for ln in wrap("ABCD"[i] + ") " + o, font(46), 900):
                items.append((ln, font(46), (200, 255, 200)))

    total = sum(f.size + 18 for _, f, _ in items)
    y = (S - total) // 2
    for ln, f, col in items:
        if ln:
            x = (S - d.textlength(ln, font=f)) / 2
            d.text((x + 3, y + 3), ln, font=f, fill=(0, 0, 0))
            d.text((x, y), ln, font=f, fill=col)
        y += f.size + 18
    return img

def main():
    fmt = random.choice(list(FORMATS))
    prompt = (
        "Tum ek Pakistani Facebook Page ke liye post banate ho. Roman Urdu (Latin letters) mein likho. "
        f"Format: {fmt}. {FORMATS[fmt]} "
        f"Topic har baar alag aur dilchasp chuno (seed {random.randint(1, 99999)}): science, history, sports, food, "
        "nature, geography, technology, health, general knowledge. Sirf asli aur durust maloomat, "
        "koi siyasi ya mazhabi ya ghalat khabar nahi. "
        'Sirf JSON do: {"headline": "", "text": "", "options": [], "answer": "", "caption": "", "photo_query": ""}. '
        "text 160 characters se kam, har option 30 characters se kam. caption 2-3 chhoti lines aur 3 hashtags. "
        "photo_query English mein 1-2 aam lafz hon jo photo mein mil sakein (jaise nature, food, cricket, city)."
    )
    j = gemini(prompt)
    img = compose(get_photo(j["photo_query"]), j["headline"], j["text"], j.get("options") or [])
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=92)
    caption = j["caption"]
    if fmt in ("quiz", "this_or_that", "riddle"):
        caption += "\n\nAap ka jawab comment mein likhein 👇"
    r = requests.post(
        f"https://graph.facebook.com/v21.0/{PAGE_ID}/photos",
        data={"access_token": TOKEN, "caption": caption},
        files={"source": ("p.jpg", buf.getvalue(), "image/jpeg")},
        timeout=120)
    print(r.status_code, r.text)
    r.raise_for_status()
    print("POSTED", fmt, "|", j["headline"], "|", j.get("answer"))

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        try:
            from alert import alert
            alert("❌ multi-post-bot image post fail: " + str(e)[:500])
        except Exception:
            pass
        raise
