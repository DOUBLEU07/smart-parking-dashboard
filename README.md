# Smart Parking Dashboard

Web dashboard สำหรับเจ้าของและพนักงานลานจอดรถขนาดเล็ก–กลาง ใช้ดูช่องว่าง บันทึกรถเข้า–ออก รับชำระเงิน และติดตามรายได้แบบ Real-time
พัฒนาตาม Sprint 0 One-Pager (`Main.dc.html` / `Smart_Parking_Dashboard.pdf`)

## เริ่มใช้งาน (Docker)

```bash
cp .env.example .env        # แล้วแก้รหัสผ่านและ JWT_SECRET
docker compose up -d --build
```

เปิด http://localhost:8080

| ผู้ใช้ | รหัสผ่าน (ค่าเริ่มต้นใน `.env`) | สิทธิ์ |
|---|---|---|
| `owner` | `INITIAL_OWNER_PASSWORD` (owner1234) | เจ้าของ: ทำได้ทุกอย่าง |
| `manager` | `DEMO_PASSWORD` (demo1234) | ผู้จัดการ: รายงาน, จัดการช่องจอด, export |
| `staff` | `DEMO_PASSWORD` (demo1234) | พนักงาน: รถเข้า–ออก, รับเงิน, ดูผังลาน |

บัญชี `manager` และ `staff` กับข้อมูลตัวอย่างจะถูกสร้างเมื่อ `SEED_DEMO_DATA=true` เท่านั้น ส่วน API docs อยู่ที่ http://localhost:8080/api/docs

## Demo Flow

1. **Login** ด้วย `staff`
2. **Parking Dashboard** แสดงช่องว่าง 6/30 ช่อง ใช้งานอยู่ 80% และรายได้วันนี้
3. **ดูช่องจอดว่าง / ไม่ว่าง** บนผังช่องจอด (เขียว = ว่าง, ดำ = มีรถ)
4. **รถเข้าลาน**: กด “บันทึกรถเข้า” หรือกดช่องสีเขียว แล้วกรอกทะเบียน
5. **จำนวนช่องว่างลดลง**: KPI และผังอัปเดตทันทีในทุกหน้าจอที่เปิดอยู่ (ลองเปิด 2 browser)
   รับรถเพิ่มอีก 1–2 คันจนใช้งานถึง ≥90% จะมีแถบแจ้งเตือน “ลานจอดใกล้เต็ม”
6. **รถออก + ชำระเงิน**: กดช่องสีดำ หรือไปที่หน้า “รถเข้า–ออก” แล้วกด “ปล่อยรถ” เลือกเงินสด/QR แล้วพิมพ์ใบเสร็จได้
7. **รายได้เพิ่มขึ้น**: “รายได้วันนี้” บน Dashboard และหน้า “รายงานรายได้” (login เป็น manager) เพิ่มขึ้นตามยอดที่รับ

## Demo Mode (สำหรับ Live Demo)

เมนู **Demo Mode** (`/demo`) แสดงลานจอดจำลองที่ใช้ข้อมูลและ API จริง คู่กับ **Backend Debug** ที่ดึง trace ของแต่ละ request จากหลังบ้าน

- **ลานจอดจำลอง**: กดรถในคิวทางเข้า → กดช่องที่เรืองแสงเพื่อจอด | กดรถที่จอดอยู่ → ⏩ เลื่อนเวลา → เลือกวิธีชำระ → ปล่อยรถ
- **Stepper**: ติ๊ก Demo Flow ทั้ง 7 ขั้นตาม one-pager อัตโนมัติ พร้อมบอกว่าต้องกดอะไรต่อ
- **Backend Debug**:
  - เส้นทาง Browser → Nginx (public) → FastAPI (private) → PostgreSQL (private DB) พร้อม IP จริงของแต่ละ subnet
  - Trace ทีละขั้น: Nginx proxy, JWT, RBAC, validation, กฎธุรกิจ, row lock, คำนวณค่าจอด, SQL จริง, COMMIT และ WebSocket broadcast
  - Checklist ว่า feature ไหนใน one-pager ถูกเรียกใช้แล้ว
  - ปุ่มทดสอบความปลอดภัยสำหรับช่วง Q&A: token ปลอม (401), RBAC (403), ทะเบียนแปลกปลอม (422), จอดทะเบียนซ้ำ (409)
- **รีเซ็ตเดโม** (manager ขึ้นไป): คืนข้อมูลเป็น 30 ช่อง ใช้งาน 80% ก่อนขึ้นนำเสนอ

Trace จะทำงานเฉพาะ request ที่ส่ง header `X-Debug-Trace: 1` และเฉพาะตอน `DEMO_MODE=true` ถ้าใช้งานจริงให้ตั้ง `DEMO_MODE=false` แล้ว `/api/demo/*` จะตอบ 404 ทั้งหมด

## Requirement ของ Mini Project

| ข้อกำหนด | ทำอย่างไร | พิสูจน์ตอน demo |
|---|---|---|
| Two-Tier Network: public & private subnet | `public_subnet` 172.28.1.0/24 (Nginx) · `private_app_subnet` 172.28.2.0/24 (FastAPI) · `private_db_subnet` 172.28.3.0/24 (PostgreSQL) โดย private ทั้งสองวงเป็น `internal: true` | กล่อง "เส้นทางของ request" ใน Debug แสดง IP แต่ละ subnet, `docker network ls` |
| Frontend: web app ใน public subnet | Nginx เสิร์ฟ Vue build อยู่ใน `public_subnet` | เปิด http://localhost:8080 |
| Backend: REST API ใน private subnet | FastAPI มีหลาย endpoint (`/api/docs`) อยู่เฉพาะ private subnet และไม่ publish port | `docker compose ps` จะเห็นแค่ nginx ที่มี `0.0.0.0:8080` |
| Security: เปิดพอร์ตสู่ Internet เท่าที่จำเป็น | เปิดพอร์ตเดียว (Nginx) · DB อยู่วงที่ Nginx เข้าไม่ถึง · JWT + RBAC · rate-limit ที่ login · CSP/security headers · container รันด้วย non-root | ปุ่มทดสอบความปลอดภัยใน Debug, `docker compose exec nginx nc -zv db 5432` (resolve ไม่ได้), `Test-NetConnection localhost -Port 5432` (False) |

## ฟีเจอร์ตามบทบาท

| หน้า | staff | manager | owner |
|---|:-:|:-:|:-:|
| ภาพรวม: KPI, ผังช่องจอด, ความเคลื่อนไหวล่าสุด, แจ้งเตือนใกล้เต็ม | ✓ | ✓ | ✓ |
| รถเข้า–ออก: บันทึกเข้า, ค้นหาทะเบียน, ปล่อยรถ + ชำระเงิน, แก้ทะเบียนที่พิมพ์ผิด | ✓ | ✓ | ✓ |
| ประวัติการจอด (กรองวันที่/ทะเบียน/สถานะ) | ✓ | ✓ | ✓ |
| Export CSV | | ✓ | ✓ |
| รายงานรายได้: รายวัน, ตามวิธีชำระ, ช่วงเวลาที่คนเข้ามากที่สุด | | ✓ | ✓ |
| จัดการช่องจอด: เพิ่มทีละช่อง/หลายช่อง, ปิดปรับปรุง, ลบ | | ✓ | ✓ |
| ผู้ใช้งาน: เพิ่ม, เปลี่ยนสิทธิ์, รีเซ็ตรหัส, ปิดบัญชี | | | ✓ |
| ตั้งค่า: ชื่อลาน, ค่าจอด, เกณฑ์แจ้งเตือน (พร้อมตัวอย่างค่าจอด) | | | ✓ |

### กติกาค่าจอด (ตั้งค่าได้)
- จอดไม่เกิน **15 นาที ฟรี** (รวมนาทีที่ 15)
- เกินจากนั้นคิด **ชั่วโมงละ 20 บาท** โดยเศษของชั่วโมงปัดขึ้น
- **เพดานวันละ 200 บาท** ต่อทุก 24 ชั่วโมง
- ค่าจอดคำนวณที่ server เท่านั้น ถ้ายอดเปลี่ยน (เช่น เวลาผ่านไปจนเข้าชั่วโมงใหม่) ระหว่างที่พนักงานเปิดหน้าชำระเงินอยู่ ระบบจะปฏิเสธและให้ยืนยันยอดใหม่

## สถาปัตยกรรม

```
Internet ──▶ nginx            [public_subnet, private_app_subnet]  ── static Vue build
                │  /api, /api/ws
                ▼
             FastAPI backend  [private_app_subnet, private_db_subnet]
                │
                ▼
             PostgreSQL       [private_db_subnet]                  ── no published port
```

- **Frontend**: Vue 3 + Vite + Pinia + Vue Router + Tailwind CSS v4 + Chart.js
- **Backend**: FastAPI + SQLAlchemy 2 + PostgreSQL 16, JWT (bcrypt)
- **Real-time**: WebSocket `/api/ws` ส่ง event เมื่อมีรถเข้า/ออก client จะดึงข้อมูลล่าสุดใหม่ ถ้า socket หลุดจะ fallback เป็น polling ทุก 10 วินาทีและเชื่อมต่อใหม่แบบ backoff
- **Least privilege**: `private_app_subnet` และ `private_db_subnet` เป็น `internal: true` (ไม่มี route ออก Internet) DB อยู่แค่ใน `private_db_subnet` จึงมีแค่ backend ที่เข้าถึงได้ nginx เองก็ resolve `db` ไม่ได้ และ nginx เป็นทางเข้าเดียวจาก Internet

### ฐานข้อมูล
ต่อยอดจาก schema ใน one-pager:

| ตาราง | คอลัมน์หลัก | ส่วนที่เพิ่ม |
|---|---|---|
| `users` | id, username, password_hash, role | full_name, is_active, created_at · role = owner/manager/staff |
| `parking_slots` | id, slot_number, status | status = available/occupied/maintenance |
| `parking_sessions` | id, slot_id, plate_number, entry_time, exit_time, fee | entered_by, exited_by · **unique index: 1 ช่อง / 1 ทะเบียน มีรายการที่ยังไม่ออกได้แค่ 1 รายการ** |
| `payments` | id, session_id, amount, paid_at | method (cash/qr), received_by |
| `lot_settings` | (ใหม่) | lot_name, free_minutes, hourly_rate, daily_cap, alert_threshold |

### การรับมือความเสี่ยง (ตาม one-pager)
| ความเสี่ยง | สิ่งที่ทำ |
|---|---|
| ข้อมูลสถานะไม่ Real-time | WebSocket + polling fallback + safety refresh ทุก 60 วินาที |
| ข้อมูลรายได้ไม่ตรง | คำนวณค่าจอดที่ server, ทำใน transaction เดียวพร้อม row lock (`SELECT … FOR UPDATE`), partial unique index กันรถหรือช่องซ้ำ, ตรวจ `expected_amount`, CHECK constraints |
| ระบบล่ม | access log ทุก request, global error handler, healthcheck ใน Docker, `restart: unless-stopped` |
| Database เสียหาย | `scripts/backup.sh` (pg_dump + gzip, เก็บ 14 ชุด) / `scripts/restore.sh` |
| Scope ใหญ่เกินไป | MVP: 1 ลาน, ไม่ต่อ payment gateway/เซ็นเซอร์ |
| Deployment ไม่สำเร็จ | Docker Compose ตั้งแต่ dev |
| Unauthorized access | JWT + RBAC ทุก endpoint, WebSocket ยืนยันตัวตนด้วย message แรก (token ไม่อยู่ใน URL/log), rate limit ที่ login, security headers/CSP, network isolation, container รันด้วย non-root |

## พัฒนาในเครื่อง (ไม่ใช้ Docker)

```bash
# Backend (ใช้ SQLite ได้)
cd backend
python -m venv .venv && .venv/Scripts/activate   # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
DATABASE_URL=sqlite:///./dev.db uvicorn app.main:app --reload     # http://localhost:8000/api/docs
pytest                                                             # 33 tests

# Frontend (proxy /api ไปที่ :8000)
cd frontend
npm install
npm run dev                                                        # http://localhost:5173
```

## Backup

```bash
./scripts/backup.sh                                   # → backups/parking-YYYYmmdd-HHMMSS.sql.gz
./scripts/restore.sh backups/parking-2026….sql.gz
# cron: 0 2 * * *  cd /path/to/project && ./scripts/backup.sh
```

## ข้อจำกัดที่รู้อยู่ / ต่อยอดได้
- WebSocket กระจาย event ภายใน process เดียว (uvicorn 1 worker) ถ้าจะ scale หลาย instance ต้องเพิ่ม Redis pub/sub หรือ Postgres LISTEN/NOTIFY
- สร้างตารางด้วย `create_all` ตอนเริ่มระบบ ถ้าจะแก้ schema ในอนาคตควรใช้ Alembic migration
- HTTPS: ควรวาง TLS (เช่น Caddy/Certbot หรือ load balancer) ไว้หน้า nginx ก่อนใช้งานจริง
- ยังไม่ต่อ payment gateway หรือเซ็นเซอร์/กล้องอ่านป้ายทะเบียน
