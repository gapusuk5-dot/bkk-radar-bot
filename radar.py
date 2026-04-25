import requests
from PIL import Image
from io import BytesIO
import numpy as np
import folium
import time
import random
import urllib3

# ปิดการแจ้งเตือน InsecureRequestWarning กรณีใช้ verify=False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------------------------------------------------------
# 1. ตั้งค่าสถานีเรดาร์ (ใช้สุวรรณภูมิจากกรมอุตุฯ)
# ---------------------------------------------------------
configs = {
    "Suvarnabhumi": {
        "url": "https://weather.tmd.go.th/svp/svp240LoopHQ.gif", 
        "lat": 13.693, 
        "lon": 100.752
    }
}

# ---------------------------------------------------------
# 2. ฟังก์ชันดึงภาพเรดาร์ (ทะลุ Cache + ดึงเฟรมล่าสุด)
# ---------------------------------------------------------
def get_latest_radar_rgb(url):
    try:
        # สุ่มหน่วงเวลาเล็กน้อย ป้องกันการโดนเซิร์ฟเวอร์เพ่งเล็ง
        time.sleep(random.uniform(1, 3))
        
        # 🔥 เทคนิค Cache Busting: เติมเวลาปัจจุบันต่อท้ายลิงก์
        current_time = int(time.time())
        no_cache_url = f"{url}?v={current_time}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
            'Referer': 'https://weather.tmd.go.th/'
        }
        
        print(f"📡 Fetching: {no_cache_url}")
        res = requests.get(no_cache_url, headers=headers, timeout=30, verify=False)
        res.raise_for_status() 
        
        # เปิดไฟล์ภาพ (รองรับทั้ง GIF, PNG, JPG)
        img = Image.open(BytesIO(res.content))
        
        # ถ้าเป็นไฟล์ภาพเคลื่อนไหว (GIF) ให้กระโดดไปเฟรมสุดท้าย (ล่าสุด)
        if hasattr(img, 'is_animated') and img.is_animated:
            img.seek(img.n_frames - 1)
            
        return np.array(img.convert('RGB'))
    except Exception as e:
        print(f"❌ Error: {url} | {e}")
        return None

# ---------------------------------------------------------
# 3. ฟังก์ชันหลักสำหรับดึงข้อมูลและสร้างแผนที่
# ---------------------------------------------------------
def main():
    # สร้างแผนที่ศูนย์กลางที่กรุงเทพฯ
    m = folium.Map(location=[13.7563, 100.5018], zoom_start=9)
    
    for name, config in configs.items():
        print(f"📡 Checking {name}...")
        
        # 3.1 ดึงภาพเรดาร์เป็น NumPy Array
        img_array = get_latest_radar_rgb(config['url'])
        
        if img_array is not None:
            
            # 3.2 กำหนดขอบเขตของภาพ (Bounds) 
            # เรดาร์สุวรรณภูมิรัศมีประมาณ 240 กม. (เทียบเท่าประมาณ 2.16 องศา lat/lon)
            lat, lon = config['lat'], config['lon']
            offset = 2.16 
            bounds = [[lat - offset, lon - offset], [lat + offset, lon + offset]]
            
            # 3.3 แปะภาพลงบนแผนที่ (ใช้ img_array ตรงๆ เพื่อแก้ปัญหา TypeError)
            folium.raster_layers.ImageOverlay(
                image=img_array,
                bounds=bounds,
                opacity=0.6,
                name=f"Radar {name}"
            ).add_to(m)
            
            print(f"✅ Success! Fetched {name}")

    # เพิ่มปุ่มเลือกเปิด/ปิดเลเยอร์ที่มุมขวาบน
    folium.LayerControl().add_to(m)
    
    # 3.4 เซฟเป็น index.html
    file_name = "index.html"
    m.save(file_name)
    print(f"🎉 Saved to {file_name}")

if __name__ == "__main__":
    main()
