import subprocess
from youtube_upload import upload

subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=blue:s=720x1280:d=6",
                "-f", "lavfi", "-i", "anullsrc", "-shortest", "-c:v", "libx264",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "t.mp4"], check=True)
upload("t.mp4", "Test video", "bot test", "unlisted")
