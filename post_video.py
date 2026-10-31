import os, random, asyncio, subprocess, requests
from PIL import Image, ImageDraw
from post_image import gemini, clean, font, PAGE_ID, TOKEN, PIX_KEY

MODES = {
    "info": dict(voice="ur-PK-AsadNeural", vtype="film",
                 brief="dilchasp maloomat ya 5 hairan kun facts"),
    "tips": dict(voice="ur-PK-UzmaNeural", vtype="film",
                 brief="sehat, zindagi ya paison ka ek asaan mashwara"),
    "story": dict(voice="ur-PK-UzmaNeural", vtype="film",
                  brief="choti kahani jis mein sabaq ho"),
    "quiz": dict(voice="ur-PK-AsadNeural", vtype="film",
                 brief="ek general knowledge sawal 3 options (A, B, C) ke saath. "
                       "voice ke aakhir mein kaho ke jawab comment mein likhein. "
                       "jawab kahin na batao. lines mein pehli line sawal, baqi options"),
    "cartoon": dict(voice="ur-PK-UzmaNeural", vtype="animation",
                    brief="bachon ke liye chhoti mazedar kahani ya sabaq"),
}

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("cmd fail: " + r.stderr[-600:])
    return r.stdout

def make_voice(text, path, voice):
    try:
        import edge_tts

        async def go():
            await edge_tts.Communicate(text, voice).save(path)

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

def search_clip(q, vtype):
    r = requests.get("https://pixabay.com/api/videos/", params={
        "key": PIX_KEY, "q": q, "per_page": 20,
        "safesearch": "true", "video_type": vtype}, timeout=60)
    r.raise_for_status()
    return r.json()["hits"]

def get_clips(queries, vtype, n=3):
    paths = []
    for i in range(n):
        q = queries[i % len(queries)]
        hits = search_clip(q, vtype)
        if not hits:
            hits = search_clip(q, "all")
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

def build(j, mode):
    make_voice(j["voice"], "voice.mp3", mode["voice"])
    dur = duration("voice.mp3") + 1.0
    clips = get_clips(j["clip_queries"], mode["vtype"])
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

def fb_reel(path, caption):
    base = f"https://graph.facebook.com/v21.0/{PAGE_ID}/video_reels"
    r = requests.post(base, data={"upload_phase": "start", "access_token": TOKEN}, timeout=60)
    print("reel start", r.status_code, r.text[:200])
    r.raise_for_status()
    info = r.json()
    vid, url = info["video_id"], info["upload_url"]
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        u = requests.post(url, headers={"Authorization": "OAuth " + TOKEN,
                                        "offset": "0", "file_size": str(size)},
                          data=f, timeout=600)
    print("reel upload", u.status_code, u.text[:200])
    u.raise_for_status()
    r = requests.post(base, data={"upload_phase": "finish", "video_id": vid,
                                  "video_state": "PUBLISHED", "description": caption,
                                  "access_token": TOKEN}, timeout=120)
    print("reel finish", r.status_code, r.text[:300])
    r.raise_for_status()

def main():
    name = os.environ.get("MODE") or random.choice(list(MODES))
    if name not in MODES:
        name = random.choice(list(MODES))
    mode = MODES[name]
    print("MODE:", name)
    shape = '{"title": "", "voice": "", "lines": [], "clip_queries": [], "caption": ""}'
    prompt = f"""Tum ek Pakistani Facebook Reel ke liye script likhte ho.
Qism: {mode["brief"]}.
Topic har baar alag aur dilchasp (seed {random.randint(1, 99999)}).
Sirf asli aur durust maloomat, koi siyasi ya mazhabi ya ghalat khabar nahi.
voice = Urdu rasmul khat (Urdu script) mein 60 se 80 alfaz ki seedhi script.
lines = 4 se 5 chhoti Roman Urdu lines (har line 60 characters se kam) jo screen par aayengi.
clip_queries = 3 English search words (1-2 words) jo aam video clips mein mil sakein.
title Roman Urdu mein. caption = Roman Urdu 2-3 chhoti lines aur 3 hashtags.
Sirf JSON do is shakal mein: {shape}"""
    j = gemini(prompt)
    path = build(j, mode)
    try:
        fb_reel(path, j["caption"])
        print("REEL POSTED |", name, "|", j["title"])
    except Exception as e:
        print("Reel fail, normal video:", clean(e)[:300])
        fb_video(path, j["caption"])
        print("VIDEO POSTED |", name, "|", j["title"])
      try:
        from stories import video_story
        video_story(path)
    except Exception as e:
        print("Story fail:", clean(e)[:300]) 
    try:
        from youtube_upload import upload
        upload(path, j["title"], j["caption"])
    except Exception as e:
        print("YouTube fail:", clean(e)[:300])

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
