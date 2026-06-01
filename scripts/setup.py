"""
AMRO — First-time Setup Script
รัน: python scripts/setup.py
จะดาวน์โหลด PocketBase, สร้าง .env, และตั้งค่าโครงสร้างเริ่มต้น
"""
import os, sys, platform, zipfile, shutil, urllib.request, json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def banner(text):
    print(f"\n{'='*55}")
    print(f"  {text}")
    print(f"{'='*55}")

def step(n, text): print(f"\n[{n}] {text}...")
def ok(text):      print(f"    ✅ {text}")
def warn(text):    print(f"    ⚠️  {text}")
def info(text):    print(f"    ℹ️  {text}")

# ── 1. Download PocketBase ─────────────────────────────
def download_pocketbase():
    step(1, "ดาวน์โหลด PocketBase")
    pb_path = os.path.join(ROOT, "pocketbase.exe")
    if os.path.exists(pb_path):
        ok("PocketBase มีอยู่แล้ว ข้ามขั้นตอนนี้")
        return

    # Get latest version
    try:
        url = "https://api.github.com/repos/pocketbase/pocketbase/releases/latest"
        req = urllib.request.Request(url, headers={"User-Agent": "AMRO-Setup"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
        version = data["tag_name"]
        info(f"Latest version: {version}")
    except Exception:
        version = "v0.22.18"  # fallback
        info(f"ใช้ version fallback: {version}")

    # Build download URL
    sys_os = platform.system().lower()
    arch = "amd64" if platform.machine().endswith("64") else "arm64"
    if sys_os == "windows":
        filename = f"pocketbase_{version[1:]}_windows_{arch}.zip"
    elif sys_os == "darwin":
        filename = f"pocketbase_{version[1:]}_darwin_{arch}.zip"
    else:
        filename = f"pocketbase_{version[1:]}_linux_{arch}.zip"

    dl_url = f"https://github.com/pocketbase/pocketbase/releases/download/{version}/{filename}"
    zip_path = os.path.join(ROOT, "pb_temp.zip")

    print(f"    ⬇️  กำลังดาวน์โหลด {filename}...")
    try:
        urllib.request.urlretrieve(dl_url, zip_path)
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(ROOT)
        os.remove(zip_path)
        ok(f"PocketBase ดาวน์โหลดสำเร็จ")
    except Exception as e:
        warn(f"ดาวน์โหลดไม่สำเร็จ: {e}")
        warn("ดาวน์โหลดเองที่: https://pocketbase.io/docs/ แล้ววางไว้ใน amro/")

# ── 2. Create .env ─────────────────────────────────────
def create_env():
    step(2, "สร้างไฟล์ .env")
    env_path = os.path.join(ROOT, ".env")
    example_path = os.path.join(ROOT, ".env.example")
    if os.path.exists(env_path):
        ok(".env มีอยู่แล้ว ข้ามขั้นตอนนี้")
        return
    if os.path.exists(example_path):
        shutil.copy(example_path, env_path)
        ok(".env สร้างจาก .env.example แล้ว")
        warn("กรุณาแก้ไข .env ใส่ค่าจริงก่อนใช้งาน Production")
    else:
        warn("ไม่พบ .env.example")

# ── 3. Print Next Steps ────────────────────────────────
def print_next_steps():
    banner("ตั้งค่าสำเร็จ! ขั้นตอนต่อไป")
    print("""
  1. แก้ไขไฟล์ .env ใส่ค่าจริง:
     - POCKETBASE_ADMIN_EMAIL / PASSWORD
     - STRIPE_SECRET_KEY / PUBLISHABLE_KEY / WEBHOOK_SECRET
     - ANTHROPIC_API_KEY (สำหรับ Audit Agent)

  2. รัน PocketBase ครั้งแรก:
     > pocketbase serve
     แล้วเปิด http://127.0.0.1:8090/_/
     สร้าง admin account ให้ตรงกับ .env

  3. ตั้งค่า PocketBase Collections:
     - เปิด http://127.0.0.1:8090/_/
     - ไปที่ Settings > Auth Providers > เปิด Google
     - ใส่ Google OAuth Client ID + Secret
     - ไปที่ Collections > users > เพิ่ม field:
         tier (text, default: "free")
         stripe_customer_id (text)

  4. รันทุกอย่างพร้อมกัน:
     > start.bat    (Windows)

  5. เปิดเว็บ:
     http://localhost:8000
""")

if __name__ == "__main__":
    banner("AMRO — Setup")
    download_pocketbase()
    create_env()
    print_next_steps()
