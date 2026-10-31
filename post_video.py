import os, random, asyncio, subprocess, requests
from PIL import Image, ImageDraw
from post_image import gemini, clean, font, PAGE_ID, TOKEN, PIX_KEY

STYLES = [
    "dilchasp maloomat",
    "choti kahani jis mein sabaq ho",
    "5 hairan kun facts",
    "sehat ka mashwara",
    "science ka kamaal",
    "kya aap jante hain",
]

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("cmd fail: " + r.stderr[-600:])
    return r.stdout

def make_voice(text, path):
    try:
        import edge_tts

        async def go():
            await edge_tts.Communicate(text, "ur-PK-AsadNeural").save(path)

        asyncio.run(go())
        if os.path.getsize(path) < 2000:
            raise RuntimeError("voice file chhoti")
    except Exception as e:
        print("edge-tts fail:", clean(e)[:200], "-> gTTS")
        from gtts import gTTS
        gTTS(text, lang="ur").save(path)

def duration(path):
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=nw=1:nk=1", path])
    return float(out.strip())

def get_clips(queries, n=3):
    paths = []
    for i in range(n):
        q = queries[i % len(queries)]
        r = requests.get("https://pixabay.com/api/videos/", params={
            "key": PIX_KEY, "q": q, "per_page": 20, "safesearch": "true"}, timeout=60)
        r.raise_for_status()
        hits = r.json()["hits"]
        if not hits:
            continue
        v = random.choice(hits)["videos"]
        url = (v.get("medium") or v.get("small") or v.get("tiny"))["url"]
        b = requests.get(url, timeout=180)
        b.raise_for_status()
        p = f"clip{i}.mp4"
        with open(p, "wb") as f:
            f.write(b.content)
        paths.append(p)
    if not paths:
        raise RuntimeError("koi clip nahi mila")
    return paths

def overlay(text, path):
    W, H = 720, 1280
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    f = font(44)
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) <= 600:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    lh = 58
    bh = lh * len(lines) + 50
    y0 = 800
    d.rounded_rectangle((40, y0, W - 40, y0 + bh), radius=30, fill=(0, 0, 0, 150))
    y = y0 + 25
    for ln in lines:
        x = (W - d.textlength(ln, font=f)) / 2
        d.text((x, y), ln, font=f, fill=(255, 255, 255, 255))
        y += lh
    im.save(path)

def build(j):
    make_voice(j["voice"], "voice.mp3")
    dur = duration("voice.mp3") + 1.0
    clips = get_clips(j["clip_queries"])
    seg = dur / len(clips)
    segs = []
    for i, c in enumerate(clips):
        s = f"seg{i}.mp4"
        run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", c, "-t", f"{seg:.2f}",
             "-vf", "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,setsar=1,fps=30",
             "-an", "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", s])
        segs.append(s)
    with open("list.txt", "w") as f:
        for s in segs:
            f.write(f"file '{s}'\n")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "list.txt", "-c", "copy", "base.mp4"])

    lines = (j.get("lines") or [j["title"]])[:5]
    pngs = []
    for i, ln in enumerate(lines):
        p = f"ov{i}.png"
        overlay(ln, p)
        pngs.append(p)
    step = dur / len(lines)
    cmd = ["ffmpeg", "-y", "-i", "base.mp4"]
    for p in pngs:
        cmd += ["-i", p]
    cmd += ["-i", "voice.mp3"]
    fc, last = "", "0:v"
    for i in range(len(pngs)):
        a, b = i * step, (i + 1) * step
        out = f"v{i + 1}"
        fc += f"[{last}][{i + 1}:v]overlay=0:0:enable='between(t,{a:.2f},{b:.2f})'[{out}];"
        last = out
    fc = fc.rstrip(";")
    cmd += ["-filter_complex", fc, "-map", f"[{last}]", "-map", f"{len(pngs) + 1}:a",
            "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-t", f"{dur:.2f}", "final.mp4"]
    run(cmd)
    return "final.mp4"

def fb_video(path, caption):
    with open(path, "rb") as f:
        r = requests.post(
            f"https://graph.facebook.com/v21.0/{PAGE_ID}/videos",
            data={"access_token": TOKEN, "description": caption},
            files={"source": ("v.mp4", f, "video/mp4")}, timeout=600)
    print("FB video", r.status_code, r.text[:300])
    r.raise_for_status()

def main():
    style = random.choice(STYLES)
    shape = '{"title": "", "voice": "", "lines": [], "clip_queries": [], "caption": ""}'
    prompt = f"""Tum ek Pakistani Facebook Reel ke liye script likhte ho.
Style: {style}. Topic har baar alag aur dilchasp (seed {random.randint(1, 99999)}).
Sirf asli aur durust maloomat, koi siyasi ya mazhabi ya ghalat khabar nahi.
voice = Urdu rasmul khat (Urdu script) mein 60 se 80 alfaz ki seedhi script.
lines = 4 se 5 chhoti Roman Urdu lines (har line 60 characters se kam) jo screen par aayengi.
clip_queries = 3 English search words (1-2 words) jo aam video clips mein mil sakein (nature, city, food, people, sky).
title Roman Urdu mein. caption = Roman Urdu 2-3 chhoti lines aur 3 hashtags.
Sirf JSON do is shakal mein: {shape}"""
    j = gemini(prompt)
    path = build(j)
    fb_video(path, j["caption"])
    print("VIDEO POSTED |", j["title"])

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        try:
            from alert import alert
            alert("❌ multi-post-bot video fail: " + clean(e)[:500])
        except Exception:
            pass
        raise
