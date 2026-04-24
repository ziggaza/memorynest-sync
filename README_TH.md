# MemoryNest Sync — คู่มือการใช้งาน

**พื้นที่ปลอดภัยสำหรับทุกเรื่องราวที่มีค่าของคุณ**

MemoryNest Sync คือแอปพลิเคชัน Desktop ที่จะช่วยดูแลและจัดระเบียบรูปภาพและวิดีโอแห่งความทรงจำที่กระจัดกระจายอยู่ตาม Drive ต่างๆ ให้กลายเป็น "ไดอารี่ดิจิทัล" ที่เป็นระเบียบและค้นหาง่าย

เปลี่ยนการจัดการไฟล์ที่น่าปวดหัวให้เป็นเรื่องง่ายและปลอดภัย โปรแกรมมาพร้อมระบบจัดเรียงโฟลเดอร์อัตโนมัติ ตรวจจับและแยกไฟล์ซ้ำอย่างชาญฉลาดเพื่อประหยัดพื้นที่ ระบบบันทึกการทำงานที่ให้คุณหยุดพักและกลับมาทำต่อ (Resume) ได้เสมอ พร้อมหน้าตาโปรแกรมที่ใช้งานง่าย อบอุ่น และเป็นมิตรกับทุกคน

> พัฒนาโดย **ZigGaZa Studio**

---

## สารบัญ

1. [ความต้องการของระบบ](#ความต้องการของระบบ)
2. [วิธีเปิดโปรแกรม](#วิธีเปิดโปรแกรม)
3. [เริ่มต้นอย่างรวดเร็ว](#เริ่มต้นอย่างรวดเร็ว)
4. [หน้าต่างหลัก](#หน้าต่างหลัก)
5. [ตัวเลือกต่างๆ](#ตัวเลือกต่างๆ)
6. [Device Manager](#device-manager)
7. [Folder Structure Manager](#folder-structure-manager)
8. [Category Manager](#category-manager)
9. [โครงสร้าง Folder ปลายทาง](#โครงสร้าง-folder-ปลายทาง)
10. [การจัดการไฟล์ซ้ำ](#การจัดการไฟล์ซ้ำ)
11. [Resume / Checkpoint](#resume--checkpoint)
12. [Log ไฟล์](#log-ไฟล์)
13. [เคล็ดลับสำหรับ Library ขนาดใหญ่ (20TB+)](#เคล็ดลับสำหรับ-library-ขนาดใหญ่-20tb)

---

## ความต้องการของระบบ

| รายการ | ขั้นต่ำ |
|--------|--------|
| ระบบปฏิบัติการ | Windows 10 / 11 (64-bit) |
| Python | 3.10 ขึ้นไป |
| Libraries | ดู `requirements.txt` |

ติดตั้ง dependencies ครั้งเดียว:
```
pip install -r requirements.txt
```

---

## วิธีเปิดโปรแกรม

**ดับเบิ้ลคลิก:**
```
Run MemoryNest Sync.bat
```
Launcher ใช้ `pythonw.exe` — ไม่มีหน้าต่าง CMD โผล่ขึ้นมา

**หรือจาก Terminal:**
```
python main.py
```

### System Tray
เมื่อกดปิดหน้าต่าง (ปุ่ม X) โปรแกรม**จะซ่อนตัวลง System Tray** ไม่ได้ปิดออกจริงๆ
- **คลิกขวาที่ไอคอน Tray** → Show / Quit
- **ดับเบิ้ลคลิกที่ไอคอน Tray** → เปิดหน้าต่างขึ้นมา

---

## เริ่มต้นอย่างรวดเร็ว

1. คลิก **+ Add Folder** เพื่อเพิ่ม folder ต้นทาง (เพิ่มได้หลาย Drive)
2. คลิก **Browse** เพื่อเลือก folder ปลายทาง
3. ตรวจสอบว่า **Dry Run** ติ๊กอยู่ (ค่าเริ่มต้น) — ยังไม่มีการแตะไฟล์จริง
4. คลิก **▶ Start**
5. ดู Activity Log ตรวจสอบว่า path ถูกต้อง
6. ยกเลิกติ๊ก **Dry Run** แล้วคลิก **▶ Start** อีกครั้งเพื่อทำงานจริง

---

## หน้าต่างหลัก

### ปุ่ม Theme (มุมบนขวา)
คลิกปุ่ม 🌙 / ☀️ / 🖥 เพื่อสลับระหว่าง **Dark → Light → System**
โปรแกรมจดจำการตั้งค่าไว้อัตโนมัติ

### กล่องสถิติ

| กล่อง | ความหมาย |
|-------|----------|
| Total | ไฟล์มีเดียทั้งหมดที่พบใน folder ต้นทาง |
| Photos | ไฟล์ที่ประมวลผลเป็นรูปภาพ |
| Videos | ไฟล์ที่ประมวลผลเป็นวิดีโอ |
| Dupes | ไฟล์ซ้ำที่ถูกแยกไว้ใน folder Duplicates |
| Resumed | ไฟล์ที่ข้ามเพราะถูกประมวลผลแล้วในการ run ก่อนหน้า |
| Errors | ไฟล์ที่เกิดข้อผิดพลาด |

### Activity Log
แสดงผลการทำงานแต่ละไฟล์:
- `[DRY]` — Dry Run (ยังไม่ได้เคลื่อนย้าย)
- `[MOV]` — ย้ายสำเร็จ
- `[CPY]` — คัดลอกสำเร็จ
- `[DUP]` — ตรวจพบว่าเป็นไฟล์ซ้ำ
- `[SKP]` — ข้ามไฟล์ (นามสกุลไม่รู้จัก)
- `[ERR]` — เกิดข้อผิดพลาด

---

## ตัวเลือกต่างๆ

### Dry Run
เมื่อติ๊ก โปรแกรมจะ **จำลอง** การทำงานโดยไม่แตะไฟล์จริงเลย
ใช้ตรวจสอบว่า folder structure ถูกต้องก่อนทำจริง

### Detect & Quarantine Duplicates
ตรวจจับไฟล์ที่มีเนื้อหาเหมือนกันทุกประการโดยใช้ xxHash
- ไฟล์ซ้ำถูกย้ายไปที่ folder `Duplicates/` ในปลายทาง
- ไม่ได้ลบทิ้ง — เก็บไว้ให้ตรวจสอบเอง

### Include Sub-folders
เมื่อติ๊ก โปรแกรมจะสแกน sub-folder ทั้งหมดใน folder ต้นทางแบบ recursive

### Resume
ข้ามไฟล์ที่ถูกประมวลผลเรียบร้อยแล้วในการ run ก่อนหน้า
- ใช้ SQLite database เก็บสถานะไว้ที่ `<ปลายทาง>/.organizer/progress.db`
- ปลอดภัย — สามารถหยุดกลางคันและเริ่มใหม่ได้เสมอ

### Operation: Copy / Move
- **Copy** — ไฟล์ต้นทางถูกเก็บไว้ นำสำเนาไปวางที่ปลายทาง
- **Move** — ไฟล์ต้นทางถูกลบออกหลังวางที่ปลายทางเรียบร้อย
- มี dialog ยืนยันก่อนทำงานจริงเมื่อปิด Dry Run

### Metadata Threads
จำนวน thread ที่ใช้อ่าน EXIF/metadata แบบ parallel พร้อมกัน
- ยิ่งมากยิ่งเร็วในขั้นตอน scan
- แนะนำ: **4** สำหรับ HDD, **6–8** สำหรับ SSD

---

## Device Manager

จัดการการแมป EXIF Make/Model ของกล้อง → ชื่อ folder

**รูปแบบ EXIF Key:** `Make|Model` เช่น `Panasonic|DMC-GX85`
**Folder Name:** ชื่อที่จะปรากฏใน path เช่น `Panasonic GX85`

### Auto-detected Devices
เมื่อพบ EXIF ของกล้องที่ยังไม่อยู่ใน mapping โปรแกรมจะเพิ่มเข้าไปโดยอัตโนมัติ
โดยใช้ EXIF string ดิบเป็นชื่อชั่วคราว ปุ่ม **Device Manager** จะแสดง badge `(N)` สีเหลือง

วิธีตั้งชื่อที่อ่านได้:
1. เปิด Device Manager
2. หาแถวที่แสดง **auto** (สีเหลืองอำพัน)
3. แก้ไข Folder Name ให้สวยงาม เช่น `Samsung Galaxy S25 Ultra`
4. คลิก **Save**

---

## Folder Structure Manager

ควบคุมว่า folder ปลายทางจะมีโครงสร้างอย่างไร

### Segment ที่ใช้ได้

| Segment | ตัวอย่าง | Format ที่เลือกได้ |
|---------|---------|------------------|
| Category | `Photos` / `Videos` | — |
| Device | `Panasonic GX85` | — |
| Year | `2024` | — |
| Quarter | `Q2` | — (Q1–Q4 เสมอ) |
| Month | `06_June` | `MM_MonthName` / `MM` / `MonthName` |
| Year-Month | `2024-06` | `YYYY-MM` / `YYYYMM` / `YYYY_MM` |
| Day | `20240615` | `YYYYMMDD` / `DD` / `YYYY-MM-DD` |

แต่ละ segment สามารถ:
- **เปิด/ปิด** ด้วย checkbox
- **เปลี่ยนลำดับ** ด้วยปุ่ม ↑ ↓

**Quarter** (Q1 = ม.ค.–มี.ค., Q2 = เม.ย.–มิ.ย., Q3 = ก.ค.–ก.ย., Q4 = ต.ค.–ธ.ค.) เหมาะกับการ review ความทรงจำทุก 3 เดือน

### Format ของวันที่

**Month:**
- `MM_MonthName` → `06_June` (ค่าเริ่มต้น — sort ง่าย + อ่านง่าย)
- `MM` → `06`
- `MonthName` → `June`

**Year-Month:**
- `YYYY-MM` → `2024-06` (ค่าเริ่มต้น)
- `YYYYMM` → `202406`
- `YYYY_MM` → `2024_06`

**Day:**
- `YYYYMMDD` → `20240615` (ค่าเริ่มต้น — sort ได้ดี)
- `DD` → `15`
- `YYYY-MM-DD` → `2024-06-15`

### Presets

| Preset | โครงสร้าง |
|--------|----------|
| Default | `Category / Device / Year / Month` |
| With Day | `Category / Device / Year / Month / Day` |
| Date-first | `Year / Month / Device / Category` |
| Flat | `Category / Device / Year` |

**Preview** แสดง path จริงที่จะเกิดขึ้นแบบ real-time

---

## Category Manager

จัดการว่านามสกุลไฟล์ใดอยู่ใน category ไหน

### Built-in Categories (ลบไม่ได้ แต่แก้ extensions ได้)
- **Photos** — JPEG, HEIC, PNG, RAW (.CR3, .ARW, .NEF ฯลฯ)
- **Videos** — MP4, MOV, MTS, MXF, BRAW ฯลฯ

### สร้าง Category ใหม่
1. คลิก **+ New Category**
2. ตั้ง **Category Name** (ชื่อที่แสดงใน log)
3. ตั้ง **Folder Name** (ชื่อ folder จริงบน disk)
4. เลือก **Metadata type**: Photo (อ่าน EXIF) หรือ Video
5. เพิ่ม extensions ในช่อง เช่น `.dng .tiff`
6. คลิก **Save**

**ตัวอย่าง:** สร้าง category "RAW Files" ด้วย `.arw .cr3 .nef` เพื่อแยก RAW ออกจาก JPEG

---

## โครงสร้าง Folder ปลายทาง

ตัวอย่าง (Default + With Day):
```
ปลายทาง/
├── Photos/
│   ├── iPhone 15 Pro/
│   │   └── 2024/
│   │       └── 06_June/
│   │           └── 20240615/
│   │               └── IMG_0001.HEIC
│   └── Panasonic GX85/
│       └── 2024/
│           └── 11_November/
│               └── 20241101/
│                   └── P1010001.RW2
├── Videos/
│   └── DJI Mini 3 Pro/
│       └── 2024/
│           └── 06_June/
│               └── DJI_0001.MP4
├── Duplicates/
│   └── IMG_0001_1.HEIC
└── .organizer/          ← database ภายใน อย่าลบ
    ├── hashes.db
    └── progress.db
```

### Unknown Device
ถ้าไม่พบข้อมูลกล้องเลย (ไม่มี EXIF และ filename pattern ไม่ตรง) ไฟล์จะไปที่:
```
Photos/Unknown_Device/2024/06_June/
```

### Conflict Resolution
ถ้า filename ซ้ำที่ปลายทาง โปรแกรมจะเติม `_1`, `_2`, ... อัตโนมัติ:
```
IMG_0001.JPG → IMG_0001_1.JPG → IMG_0001_2.JPG
```

---

## การจัดการไฟล์ซ้ำ

โปรแกรมใช้ xxHash เพื่อ fingerprint เนื้อหาของไฟล์

1. ไฟล์แรกที่พบ → บันทึก fingerprint และย้าย/คัดลอกตามปกติ
2. ไฟล์เดิมซ้ำถูกพบอีก → ตรวจพบว่าซ้ำ ย้ายไป `Duplicates/`
3. บันทึก path ต้นทางของ duplicate ไว้ใน log

**ไฟล์ซ้ำไม่ถูกลบ** — เก็บไว้ใน `Duplicates/` เพื่อให้ตรวจสอบเองได้

---

## Resume / Checkpoint

Database `progress.db` บันทึกสถานะของทุกไฟล์:

| สถานะ | ความหมาย |
|-------|----------|
| moved | ย้ายสำเร็จ |
| copied | คัดลอกสำเร็จ |
| duplicate | ตรวจพบว่าซ้ำ ส่งไป Duplicates/ |
| skipped | นามสกุลไม่รู้จัก |
| error | เกิดข้อผิดพลาด (ดูรายละเอียดใน log) |

การ run ครั้งถัดไปเมื่อติ๊ก **Resume** ไฟล์ที่มีสถานะ `moved`, `copied`, `duplicate` จะถูกข้ามทันที

**เริ่มใหม่ตั้งแต่ต้น:** ยกเลิกติ๊ก Resume หรือลบ `<ปลายทาง>/.organizer/progress.db`

---

## Log ไฟล์

Log ถูกบันทึกที่:
```
<โฟลเดอร์โปรแกรม>/logs/organizer_YYYY-MM-DD.log
```

Log หมุนเวียนทุกวัน มีรายละเอียดแบบ per-file ใช้สำหรับ audit ได้

---

## เคล็ดลับสำหรับ Library ขนาดใหญ่ (20TB+)

1. **ทำ Dry Run ก่อนเสมอ** — ลองกับ folder ตัวอย่างก่อน แล้วค่อยประมวลผลทั้งหมด
2. **ทำทีละ Drive** — เพิ่ม source ทีละตัว run เสร็จแล้วค่อยเพิ่มตัวถัดไป
3. **ใช้ Move แทน Copy** เมื่อพื้นที่ disk จำกัด (Copy ต้องใช้พื้นที่ 2 เท่าชั่วคราว)
4. **ใช้ Resume เสมอ** — หยุดกลางคันได้ไม่มีปัญหา เริ่มใหม่ต่อจากเดิมได้
5. **ปลายทางควรเป็น SSD** เพื่อประสิทธิภาพสูงสุด
6. **Metadata threads 4–6** สำหรับ HDD source, ถึง 8 สำหรับ SSD
7. **อย่าย้ายหรือลบ folder `.organizer`** — จำเป็นสำหรับ resume และ deduplication ข้าม session
8. **ตรวจสอบ Errors** หลังแต่ละ run — ไฟล์ที่ error ถูกข้าม ไม่ได้หาย ลอง run ใหม่ได้

---

<div align="center">

**POWERED BY ZigGaZa STUDIO**

*MemoryNest Sync — พื้นที่ปลอดภัยสำหรับทุกเรื่องราวที่มีค่าของคุณ*

</div>
