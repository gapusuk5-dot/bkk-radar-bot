import numpy as np
import requests
import math
from PIL import Image
from io import BytesIO
import folium
from branca.element import Template, MacroElement
import urllib3
from datetime import datetime
import pytz
import time
import random

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_latest_radar_rgb(url):
    try:
        time.sleep(random.uniform(1, 3))
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
            'Referer': 'https://weather.bangkok.go.th/'
        }
        res = requests.get(url, headers=headers, timeout=30, verify=False)
        res.raise_for_status() 
        gif = Image.open(BytesIO(res.content))
        frames = []
        try:
            while True:
                frames.append(gif.copy())
                gif.seek(gif.tell() + 1)
        except EOFError: pass
        return np.array(frames[-1].convert('RGB'))
    except Exception as e:
        print(f"❌ Error: {url} | {e}")
        return None

def rgb_to_dbz(r, g, b):
    r, g, b = int(r), int(g), int(b)
    rain_colors = [
        ((255, 255, 255), 66.0), ((255, 150, 255), 61.0), ((255, 0, 255), 56.0),
        ((255, 0, 0), 49.0), ((255, 128, 0), 41.0), ((255, 255, 0), 31.0),
        ((0, 255, 0), 21.0), ((0, 150, 0), 16.0), ((0, 0, 255), 10.0)
    ]
    for target, dbz in rain_colors:
        tr, tg, tb = int(target[0]), int(target[1]), int(target[2])
        if math.sqrt((r - tr)**2 + (g - tg)**2 + (b - tb)**2) < 45: return dbz
    return 0

def get_dbz_color(dbz):
    if dbz >= 66: return '#FFFFFF'
    if dbz >= 60: return '#FF99FF'
    if dbz >= 55: return '#FF00FF'
    if dbz >= 45: return '#FF0000'
    if dbz >= 35: return '#FF8000'
    if dbz >= 25: return '#FFFF00'
    if dbz >= 15: return '#00FF00'
    return '#0000FF'

RADAR_RANGE_KM = 60.0
STEP_KM = 0.5 
configs = {
    "Suvarnabhumi": {"url": "https://weather.tmd.go.th/svp/svp240_HQ_latest.gif", "lat": 13.693, "lon": 100.752}
}

m = folium.Map(location=[13.75, 100.5], zoom_start=11, tiles='https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', attr='©CartoDB')

for name, conf in configs.items():
    print(f"📡 Checking {name}...")
    img = get_latest_radar_rgb(conf["url"])
    if img is not None:
        print(f"✅ Success!")
        px_per_km = 300.0 / 60.0
        grid = np.arange(-RADAR_RANGE_KM, RADAR_RANGE_KM + STEP_KM, STEP_KM)
        for y_km in grid:
            for x_km in grid:
                if math.sqrt(x_km**2 + y_km**2) > RADAR_RANGE_KM: continue
                px, py = int(425 + (x_km * px_per_km)), int(380 - (y_km * px_per_km))
                if 0 <= px < img.shape[1] and 0 <= py < img.shape[0]:
                    dbz = rgb_to_dbz(*img[py, px])
                    if dbz > 0:
                        lat_p = conf["lat"] + (y_km/111.0)
                        lon_p = conf["lon"] + (x_km/(111.0*math.cos(math.radians(conf["lat"]))))
                        folium.CircleMarker(location=[lat_p, lon_p], radius=2, color=get_dbz_color(dbz), fill=True, weight=0, fill_opacity=0.7).add_to(m)

tz_bkk = pytz.timezone('Asia/Bangkok')
current_time = datetime.now(tz_bkk).strftime("%d %b %Y | %H:%M:%S")

overlay_html = f"""
{{% macro html(this, kwargs) %}}
<div style="position: fixed; top: 20px; left: 50px; width: 220px; background-color: rgba(255,255,255,0.9); z-index:9999; padding: 8px; border-radius: 5px; text-align: center; border:2px solid #333;">
    <b>🕒 {current_time}</b>
</div>
{{% endmacro %}}
"""
macro = MacroElement()
macro._template = Template(overlay_html)
m.get_root().add_child(macro)

file_name = "bkk_radar.html"
m.save(file_name)
print(f"🎉 Saved to {file_name}")
