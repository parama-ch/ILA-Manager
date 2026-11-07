# คู่มือการมีส่วนร่วมในโครงการ ILA Manager

ขอขอบคุณที่ให้ความสนใจร่วมพัฒนา ILA Manager!

> **ภาษาไทย** | [English](CONTRIBUTING.md)

## การตั้งค่าสภาพแวดล้อมเพื่อการพัฒนา (Development Setup)

1. Fork และ Clone repository:
   ```bash
   git clone https://github.com/<your-username>/ILA-Manager.git
   cd ILA-Manager
   ```

2. สร้าง Virtual Environment และติดตั้ง dependencies:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # บน Windows: .venv\Scripts\activate
   pip install -e ".[dev]"
   ```

3. เริ่มรันเซิร์ฟเวอร์เพื่อทดสอบ:
   ```bash
   ila-manager --port 8765
   ```

## มาตรฐานการเขียนโค้ดและ Git Workflow

- **การแตก Branch**: สร้าง branch ใหม่จาก `main`:
  ```bash
  git checkout -b feat/your-feature-name
  ```
- **รูปแบบ Commit Message**: ใช้รูปแบบ [Conventional Commits](https://www.conventionalcommits.org/):
  - `feat: ...` สำหรับฟีเจอร์ใหม่
  - `fix: ...` สำหรับการแก้ไขบั๊ก
  - `docs: ...` สำหรับการปรับปรุงเอกสาร
  - `test: ...` สำหรับการเพิ่มชุดทดสอบ
- **การตรวจสอบคุณภาพโค้ด (Linting)**: รัน `ruff` ก่อน commit เสมอ:
  ```bash
  ruff check .
  ```
- **การทดสอบ (Testing)**: เขียนชุดทดสอบในโฟลเดอร์ `tests/` และตรวจสอบว่าผ่านทั้งหมด:
  ```bash
  pytest -v
  ```
- **Frontend แบบ Zero-Build**: โค้ดส่วนหน้าใน `src/ila_manager/web/` ใช้มาตรฐาน ES modules และ CSS โดยตรงเพื่อความสะดวกในการติดตั้งผ่าน pip กรุณาอย่าเพิ่ม build tools เช่น npm/webpack ที่ทำให้ผู้ใช้ทั่วไปต้องติดตั้ง Node.js เพิ่มเติม

## การส่ง Pull Request

1. Push branch ของคุณขึ้น GitHub
2. เปิด Pull Request เข้าสู่ `main`
3. เขียนคำอธิบายสิ่งที่แก้ไขอย่างชัดเจน และแนบภาพหน้าจอหรือผลการรัน test ประกอบ
