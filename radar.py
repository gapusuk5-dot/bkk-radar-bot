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

# ปิดแจ้งเตือน SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==========================================
# 1. ฟังก์ชันดึงภาพและวิเคราะห์เรดาร์ (อัปเดตสเกลสีแบบกรมอุตุฯ)
# ==========================================
def get_latest_radar_rgb(url):
    try:
        # 🔥 ทะลุ Cache: เติมเวลาปัจจุบันต่อท้ายลิงก์
        current_time_ts = int(time.time())
        no_cache_url = f"{url}?v={current_time_ts}"
        
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(no_cache_url, headers=headers, timeout=15, verify=False)
        gif = Image.open(BytesIO(res.content))
        frames = []
        try:
            while True:
                frames.append(gif.copy())
                gif.seek(gif.tell() + 1)
        except EOFError: pass
        return np.array(frames[-1].convert('RGB'))
    except Exception as e: 
        print(f"Error fetching radar: {e}")
        return None

def rgb_to_dbz(r, g, b):
    r, g, b = int(r), int(g), int(b)
    # อัปเดตสเกลสีให้ใกล้เคียงกับภาพแถบสีของกรมอุตุฯ
    rain_colors = [
        ((255, 255, 255), 66.0), # ขาว (หนักสุดขั้ว)
        ((255, 150, 255), 61.0), # ชมพูอ่อน
        ((255, 0, 255), 56.0),   # ม่วง/บานเย็น
        ((255, 0, 0), 49.0),     # แดง
        ((255, 128, 0), 41.0),   # ส้ม
        ((255, 255, 0), 31.0),   # เหลือง
        ((0, 255, 0), 21.0),     # เขียว
        ((0, 150, 0), 16.0),     # เขียวเข้ม
        ((0, 0, 255), 10.0)      # น้ำเงิน
    ]
    for target, dbz in rain_colors:
        tr, tg, tb = int(target[0]), int(target[1]), int(target[2])
        dist = math.sqrt((r - tr)**2 + (g - tg)**2 + (b - tb)**2)
        if dist < 45: return dbz # ลดระยะความคลาดเคลื่อนสีลงเพื่อความแม่นยำ
    return 0

def get_dbz_color(dbz):
    # คืนค่าสีเพื่อเอาไปพล็อตลงแผนที่ Folium
    if dbz >= 66: return '#FFFFFF' # ขาว
    if dbz >= 60: return '#FF99FF' # ชมพู
    if dbz >= 55: return '#FF00FF' # ม่วง
    if dbz >= 45: return '#FF0000' # แดง
    if dbz >= 35: return '#FF8000' # ส้ม
    if dbz >= 25: return '#FFFF00' # เหลือง
    if dbz >= 15: return '#00FF00' # เขียว
    return '#0000FF'               # น้ำเงิน

# ==========================================
# 2. เริ่มประมวลผลและสร้างแผนที่เรดาร์
# ==========================================
RADAR_RANGE_KM = 100.0  # 💡 ลดรัศมีเหลือ 100 กม. ตามต้องการ
STEP_KM = 1.0           # 💡 ปรับความละเอียดให้แน่นขึ้น (1 กม./จุด) ภาพจะเนียนขึ้น

# คอนฟิกสถานีสุวรรณภูมิ
configs = {
    "Suvarnabhumi": {
        "url": "https://weather.tmd.go.th/svp/svp240LoopHQ.gif", 
        "lat": 13.693, 
        "lon": 100.752
    }
}

# 💡 ซูมแผนที่เข้ามาใกล้ขึ้นที่ระดับ 9
m = folium.Map(location=[13.693, 100.752], zoom_start=9, 
               tiles='https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', attr='©CartoDB')

# --- ส่วนที่ 1: วาดสถานีเรดาร์และรัศมี ---
for name, conf in configs.items():
    folium.Marker(
        location=[conf["lat"], conf["lon"]],
        popup=f"Radar Station: {name} (100km Range)",
        icon=folium.Icon(color='black', icon='plane', prefix='fa') 
    ).add_to(m)
    
    folium.Circle(
        location=[conf["lat"], conf["lon"]],
        radius=RADAR_RANGE_KM * 1000, color='blue', weight=1, fill=True, fill_opacity=0.03, dash_array='5, 5'
    ).add_to(m)

    img = get_latest_radar_rgb(conf["url"])
    if img is not None:
        print(f"📡 สแกนข้อมูลเรดาร์: {name}")
        
        # อ้างอิงจากตั้งค่า px/km = 10/3, Center X=902, Center Y=716
        px_per_km = 10.0 / 3.0
        center_x = 902
        center_y = 716
        
        grid = np.arange(-RADAR_RANGE_KM, RADAR_RANGE_KM + STEP_KM, STEP_KM)
        for y_km in grid:
            for x_km in grid:
                if math.sqrt(x_km**2 + y_km**2) > RADAR_RANGE_KM: continue
                
                # คำนวณตำแหน่ง Pixel ในภาพ
                px, py = int(center_x + (x_km * px_per_km)), int(center_y - (y_km * px_per_km))
                
                if 0 <= px < img.shape[1] and 0 <= py < img.shape[0]:
                    dbz = rgb_to_dbz(*img[py, px])
                    if dbz > 0:
                        lat_p = conf["lat"] + (y_km/111.0)
                        lon_p = conf["lon"] + (x_km/(111.0*math.cos(math.radians(conf["lat"]))))
                        folium.CircleMarker(
                            location=[lat_p, lon_p], radius=2,
                            color=get_dbz_color(dbz), fill=True, weight=0, fill_opacity=0.7,
                        ).add_to(m)

# --- ส่วนที่ 2: แถบเวลา & Legend ---
tz_bkk = pytz.timezone('Asia/Bangkok')
current_time_str = datetime.now(tz_bkk).strftime("%d %b %Y | %H:%M:%S")

overlay_html = f"""
{{% macro html(this, kwargs) %}}
<div style="position: fixed; top: 20px; left: 50px; width: 220px; 
    background-color: rgba(255, 255, 255, 0.9); border:2px solid #333; z-index:9999; font-size:14px;
    padding: 8px; border-radius: 5px; box-shadow: 2px 2px 5px rgba(0,0,0,0.3); text-align: center;">
    <b>🕒 ข้อมูลล่าสุดเมื่อ:</b><br>
    <span style="color: darkblue; font-weight: bold;">{current_time_str}</span>
</div>

<div style="position: fixed; bottom: 30px; left: 30px; width: 220px; 
    background-color: white; border:2px solid #ccc; z-index:9999; font-size:12px;
    padding: 10px; border-radius: 8px; box-shadow: 2px 2px 5px rgba(0,0,0,0.2);">
    
    <b>📡 สุวรรณภูมิ (dBZ) ระยะ 100 กม.</b><br>
    <i style="background:#FFFFFF; border:1px solid #ccc; width:10px;height:10px;display:inline-block"></i> 66+ (ขาว)<br>
    <i style="background:#FF99FF;width:10px;height:10px;display:inline-block"></i> 60-66 (ชมพู)<br>
    <i style="background:#FF00FF;width:10px;height:10px;display:inline-block"></i> 55-60 (ม่วง)<br>
    <i style="background:#FF0000;width:10px;height:10px;display:inline-block"></i> 45-55 (แดง)<br>
    <i style="background:#FF8000;width:10px;height:10px;display:inline-block"></i> 35-45 (ส้ม)<br>
    <i style="background:#FFFF00;width:10px;height:10px;display:inline-block"></i> 25-35 (เหลือง)<br>
    <i style="background:#00FF00;width:10px;height:10px;display:inline-block"></i> 15-25 (เขียว)<br>
    <i style="background:#0000FF;width:10px;height:10px;display:inline-block"></i> 10-15 (น้ำเงิน)<br>
</div>
{{% endmacro %}}
"""
macro = MacroElement()
macro._template = Template(overlay_html)
m.get_root().add_child(macro)

# เซฟเป็น index.html
file_name = "index.html"
m.save(file_name)
print(f"🎉 สำเร็จ! แผนที่เรดาร์สุวรรณภูมิ (ระยะ 100 กม.) บันทึกที่: {file_name}")

# ถ้าแสดงใน Jupyter Notebook
try:
    display(m)
except NameError:
    pass
