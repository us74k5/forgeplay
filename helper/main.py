from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
import yt_dlp
import os
import time
import threading
import logging

app = FastAPI()

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

CACHE_DIR = "cache"
CACHE_MAX_AGE = 86400

os.makedirs(CACHE_DIR, exist_ok=True)


class DownloadRequest(BaseModel):
    url: str
    quality: str = "720"


PLAYER_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
<title>Local Player</title>
</head>
<body style="margin:0;background:#000;overflow:hidden;">

<video
id="player"
controls
autoplay
playsinline
muted
style="width:100vw;height:100vh;"
>
<source src="/media/{id}">
</video>

<script>
const v=document.getElementById("player");

v.play().then(()=>{{
v.muted=false;
}}).catch(()=>{{
document.addEventListener(
"click",
()=>v.play(),
{{once:true}}
);
}});
</script>

</body>
</html>
"""


def purge_old_cache():
    now=time.time()

    for f in os.listdir(CACHE_DIR):
        p=os.path.join(CACHE_DIR,f)

        if os.path.isfile(p):
            if now-os.path.getmtime(p)>CACHE_MAX_AGE:
                try:
                    os.remove(p)
                    log.info(f"Deleted {p}")
                except Exception as e:
                    log.error(e)


def cleanup_loop():
    while True:
        purge_old_cache()
        time.sleep(3600)


threading.Thread(
    target=cleanup_loop,
    daemon=True
).start()

purge_old_cache()


def find_cached_file(video_id):

    for f in os.listdir(CACHE_DIR):
        if f.startswith(video_id + "."):
            return os.path.join(CACHE_DIR, f)

    return None


def format_for_quality(q):

    if q=="480":
        return "best[height<=480][ext=mp4]/best"

    if q=="720":
        return "best[height<=720][ext=mp4]/best"

    return "best[height<=1080][ext=mp4]/best"


@app.post("/download")
async def download_video(
request: DownloadRequest = Body(...)
):
    try:

        ydl_opts = {
            "format":
            format_for_quality(
                request.quality
            ),

            "outtmpl":
            os.path.join(
                CACHE_DIR,
                "%(id)s.%(ext)s"
            ),

            "noplaylist":True,
            "cachedir":False,
            "quiet":False,
            "logger":log
        }

        with yt_dlp.YoutubeDL(
            ydl_opts
        ) as ydl:

            info = ydl.extract_info(
                request.url,
                download=False
            )

            video_id = info["id"]

            cached = find_cached_file(
                video_id
            )

            if cached:
                log.info(
                    f"Using cached {video_id}"
                )

            else:
                log.info(
                    f"Downloading {video_id}"
                )

                ydl.download(
                    [request.url]
                )

        return {
            "playerUrl":
            f"http://127.0.0.1:8000/player/{video_id}"
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@app.get(
"/player/{video_id}",
response_class=HTMLResponse
)
async def player(video_id:str):

    return PLAYER_TEMPLATE.format(
        id=video_id
    )


@app.get("/media/{video_id}")
async def media(video_id:str):

    path = find_cached_file(
        video_id
    )

    if not path:
        raise HTTPException(
            status_code=404,
            detail="Video not found"
        )

    return FileResponse(
        path,
        media_type="video/mp4"
    )


@app.get("/progress/{video_id}")
async def progress(video_id:str):
    return {
        "status":"ready"
    }


if __name__ == "__main__":

    import uvicorn
    import pystray
    import webbrowser

    from PIL import Image, ImageDraw
    from pystray import MenuItem as item


    def run_server():

        time.sleep(1)

        uvicorn.run(
            app,
            host="127.0.0.1",
            port=8000,
            log_level="warning"
        )


    def tray_image():

        img = Image.new(
            "RGB",
            (64,64),
            "black"
        )

        d = ImageDraw.Draw(img)

        d.rectangle(
            [18,18,46,46],
            fill="white"
        )

        return img


    def open_control(icon,item):

        webbrowser.open(
            "http://127.0.0.1:8000/docs"
        )


    def quit_app(icon,item):

        icon.stop()
        os._exit(0)


    threading.Thread(
        target=run_server,
        daemon=True
    ).start()


    tray = pystray.Icon(
        "ForgePlayHelper",
        tray_image(),
        "ForgePlay Helper",
        menu=pystray.Menu(
            item(
                "Open Control",
                open_control
            ),
            item(
                "Quit",
                quit_app
            )
        )
    )

    tray.run()