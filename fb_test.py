import os, requests

page_id = os.environ["FB_PAGE_ID"]
token = os.environ["FB_PAGE_TOKEN"]

img = requests.get("https://picsum.photos/800/800.jpg", timeout=60)
img.raise_for_status()

r = requests.post(
    f"https://graph.facebook.com/v21.0/{page_id}/photos",
    data={"access_token": token, "caption": "test", "published": "false"},
    files={"source": ("t.jpg", img.content, "image/jpeg")},
    timeout=120,
)
print(r.status_code, r.text)
r.raise_for_status()
print("FACEBOOK OK")
