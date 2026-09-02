import re
import logging
import subprocess
from datetime import datetime
from colab_leecher.utility.helper import sizeUnit, status_bar
from colab_leecher.utility.variables import BOT, Paths, Messages, BotTimes
from colab_leecher import JD_EMAIL, JD_PASS
from colab_leecher.myjd import MyJdApi
import asyncio
import os
import json
import random

class JDownloader(MyJdApi):
    def __init__(self):
        super().__init__()
        self._username = ""
        self._password = ""
        self._device_name = ""
        self.is_connected = False
        self.error = "JDownloader Credentials not provided!"

    async def boot(self):
        subprocess.run(["pkill", "-9", "-f", "java"])
        if not JD_EMAIL or not JD_PASS:
            self.is_connected = False
            self.error = "JDownloader Credentials not provided!"
            return
        self.error = "Connecting... Try again after couple of seconds"
        self._device_name = f"{random.randint(0, 1000)}@ColabLeecher"

        jdata = {
            "autoconnectenabledv2": True,
            "password": JD_PASS,
            "devicename": f"{self._device_name}",
            "email": JD_EMAIL,
        }

        os.makedirs("/JDownloader/cfg", exist_ok=True)
        with open("/JDownloader/cfg/org.jdownloader.api.myjdownloader.MyJDownloaderSettings.json", "w") as sf:
            json.dump(jdata, sf)

        remote_data = {
            "localapiserverheaderaccesscontrollalloworigin": "",
            "deprecatedapiport": 3128,
            "localapiserverheaderxcontenttypeoptions": "nosniff",
            "localapiserverheaderxframeoptions": "DENY",
            "externinterfaceenabled": True,
            "deprecatedapilocalhostonly": True,
            "localapiserverheaderreferrerpolicy": "no-referrer",
            "deprecatedapienabled": True,
            "localapiserverheadercontentsecuritypolicy": "default-src 'self'",
            "jdanywhereapienabled": True,
            "externinterfacelocalhostonly": False,
            "localapiserverheaderxxssprotection": "1; mode=block",
        }
        with open("/JDownloader/cfg/org.jdownloader.api.RemoteAPIConfig.json", "w") as rf:
            json.dump(remote_data, rf)

        if os.path.exists("/content/Telegram-Leecher/JDownloader.jar"):
            if not os.path.exists("/JDownloader/JDownloader.jar"):
                import shutil
                shutil.copy("/content/Telegram-Leecher/JDownloader.jar", "/JDownloader/JDownloader.jar")

        cmd = "java -Dsun.jnu.encoding=UTF-8 -Dfile.encoding=UTF-8 -Djava.awt.headless=true -jar /JDownloader/JDownloader.jar"
        self.is_connected = True

        # Start JDownloader in background
        subprocess.Popen(cmd.split(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Wait for JDownloader to start and connect
        # JDownloader takes time to download updates and restart
        for _ in range(60):
            try:
                await self.device.jd.get_core_revision()
                self.is_connected = True
                break
            except:
                await asyncio.sleep(5)
        else:
            logging.error("Failed to connect to JDownloader after 5 minutes")
            self.is_connected = False

jdownloader = JDownloader()

async def jdownloader_Download(link: str, num: int):
    global BotTimes, Messages
    name_d = get_JD_Name(link)
    BotTimes.task_start = datetime.now()
    Messages.status_head = f"<b>📥 DOWNLOADING FROM » </b><i>🔗Link {str(num).zfill(2)}</i>\n\n<b>🏷️ Name » </b><code>{name_d}</code>\n"

    if not jdownloader.is_connected:
        await jdownloader.boot()

    if not jdownloader.is_connected:
        logging.error("Failed to connect to MyJDownloader")
        return

    try:
        await jdownloader.device.linkgrabber.add_links([{"autoExtract": False, "links": link, "deepDecrypt": True}])

        # Wait for links to be parsed
        while await jdownloader.device.linkgrabber.is_collecting():
            await asyncio.sleep(1)
        await asyncio.sleep(3)

        queued_downloads = await jdownloader.device.linkgrabber.query_packages([{}])
        if not queued_downloads:
            logging.error("No packages found in linkgrabber")
            return

        online_packages = [pkg["uuid"] for pkg in queued_downloads]

        await jdownloader.device.linkgrabber.move_to_downloadlist(package_ids=online_packages)
        await asyncio.sleep(2)
        await jdownloader.device.downloads.start_downloads()

        # Wait a bit for it to move
        await asyncio.sleep(2)

        while True:
            download_packages = await jdownloader.device.downloads.query_packages([{}])

            bytesLoaded = 0
            bytesTotal = 0
            eta_seconds = 0
            speed = 0

            is_finished = True

            for pack in download_packages:
                if pack.get("uuid") in online_packages:
                    bytesLoaded += pack.get("bytesLoaded", 0)
                    bytesTotal += pack.get("bytesTotal", 0)
                    speed += pack.get("speed", 0)
                    eta_seconds = max(eta_seconds, pack.get("eta", 0))

                    st = pack.get("status", "")
                    if st and st.lower() != "finished" and bytesLoaded < bytesTotal:
                        is_finished = False
                    elif bytesLoaded < bytesTotal:
                        is_finished = False

            if bytesTotal == 0:
                is_finished = False

            if bytesTotal > 0:
                percentage = (bytesLoaded / bytesTotal) * 100

                downloaded_bytes = sizeUnit(bytesLoaded)
                total_size = sizeUnit(bytesTotal)

                speed_string = f"{sizeUnit(speed)}/s" if speed > 0 else "0B/s"
                eta = f"{int(eta_seconds)}s"

                await status_bar(
                    Messages.status_head,
                    speed_string,
                    int(percentage),
                    eta,
                    downloaded_bytes,
                    total_size,
                    "JDownloader 🧨",
                )

            if is_finished and bytesTotal > 0 and bytesLoaded >= bytesTotal:
                break

            if not download_packages:
                # If packages suddenly disappear, break to avoid infinite loop
                break

            await asyncio.sleep(2)

    except Exception as e:
        logging.error(f"JDownloader Error: {e}")

def get_JD_Name(link: str):
    if len(BOT.Options.custom_name) != 0:
        return BOT.Options.custom_name
    return "JDownloader Download"
