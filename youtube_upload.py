import os, json, requests

def access_token():
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": os.environ["YT_CLIENT_ID"],
        "client_secret": os.environ["YT_CLIENT_SECRET"],
        "refresh_token": os.environ["YT_REFRESH_TOKEN"],
        "grant_type": "refresh_token"}, timeout=60)
    if not r.ok:
        print("yt token fail", r.status_code, r.text[:200])
    r.raise_for_status()
    return r.json()["access_token"]

def upload(path, title, desc, privacy="public"):
    at = access_token()
    meta = {
        "snippet": {"title": title[:90] + " #Shorts",
                    "description": desc[:4000] + "\n\n#Shorts",
                    "categoryId": "22"},
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
    }
    size = os.path.getsize(path)
    r = requests.post(
        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
        headers={"Authorization": "Bearer " + at,
                 "Content-Type": "application/json; charset=UTF-8",
                 "X-Upload-Content-Length": str(size),
                 "X-Upload-Content-Type": "video/mp4"},
        data=json.dumps(meta), timeout=60)
    print("yt start", r.status_code, r.text[:300])
    r.raise_for_status()
    loc = r.headers["Location"]
    with open(path, "rb") as f:
        u = requests.put(loc, headers={"Content-Type": "video/mp4",
                                       "Content-Length": str(size)},
                         data=f, timeout=900)
    print("yt upload", u.status_code, u.text[:300])
    u.raise_for_status()
    vid = u.json()["id"]
    print("YT UPLOADED: https://youtu.be/" + vid)
    try:
        s = requests.get("https://www.googleapis.com/youtube/v3/videos",
                         params={"part": "status", "id": vid},
                         headers={"Authorization": "Bearer " + at}, timeout=60)
        print("yt status", s.status_code, s.text[:300])
    except Exception as e:
        print("status check skip", e)
    return vid
