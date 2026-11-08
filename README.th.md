# ILA Manager 🔍

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![AMD Vivado](https://img.shields.io/badge/EDA-AMD%20Vivado-red.svg)](https://www.xilinx.com/products/design-tools/vivado.html)
[![CI](https://github.com/parama-ch/ILA-Manager/actions/workflows/ci.yml/badge.svg)](https://github.com/parama-ch/ILA-Manager/actions)

> **ภาษาไทย** | [English](README.md)

**ILA Manager** คือโปรแกรม GUI แบบ Open-Source และเครื่องมือ CLI สำหรับวิศวกร FPGA ที่ช่วยจัดการพอร์ต ILA (Integrated Logic Analyzer) บน AMD/Xilinx Vivado ได้อย่างสะดวกรวดเร็วและแม่นยำ

ช่วยแก้ปัญหาความยุ่งยากในการไล่เลข Probe ใน Vivado โดยผู้ใช้สามารถลากไฟล์ HDL (VHDL, Verilog, SystemVerilog) มาวาง เลือกสัญญาณ เลือกระบุช่วงบิต (Bit Slice) หรือมิติของ Array สลับตำแหน่งหรือเลื่อนลำดับ Probe ได้อย่างอิสระ (เช่น สลับ `probe3` ⇄ `probe5`) พร้อมสร้างโค้ดให้อัตโนมัติ:
1. **สคริปต์ Vivado TCL แบบ Smart**: ตรวจสอบอัตโนมัติว่ามี IP อยู่แล้วหรือไม่เพื่อสลับระหว่าง `create_ip` กับ `set_property` (Update) พร้อมตั้งค่า **Flip-Flop Pipeline Stages เริ่มต้นเป็น 4** เพื่อช่วยเรื่อง Timing Closure
2. **Snippet สำหรับ Port-Map ใน HDL**: รองรับการต่อสายตรงแบบ `entity work.<ila>` ใน VHDL โดยไม่ต้องประกาศ `component` พร้อมรองรับไวยากรณ์สัญญาณ 1-bit แบบ `probeN(0) => onebitsignal;` ตามมาตรฐาน ILA อย่างถูกต้อง และรองรับ Verilog
3. **ระบบ Diff & Sync ตรวจจับความเปลี่ยนแปลง**: แจ้งเตือนเมื่อสัญญาณในโค้ด HDL มีขนาดบิตเปลี่ยนไป หรือสัญญาณเดิมถูกลบ/เปลี่ยนชื่อ

---

## ฟีเจอร์เด่น (Key Features)

- **รองรับการอ่านและแกะสัญญาณ HDL (HDL Parsing)**:
  - รองรับไฟล์ VHDL (`.vhd`, `.vhdl`), Verilog (`.v`), และ SystemVerilog (`.sv`)
  - คำนวณความกว้างบิตจาก generics, parameters, และ constants ในไฟล์ผ่านตัวประเมินนิพจน์คณิตศาสตร์ที่ปลอดภัย
  - รองรับสัญญาณ 1-bit (`std_logic`, `bit`), เวกเตอร์ (`std_logic_vector`, `signed`, `unsigned`), อาเรย์ 1D/2D และโครงสร้าง Record ใน VHDL
- **Tree-Based Signal Picker (เลือกเจาะจงระดับบิตและมิติ)**:
  - สามารถขยายสัญญาณเพื่อเลือก index ของ array, ฟิลด์ของ record หรือช่วงบิตที่ต้องการ (เช่น `mem(2).data(15 downto 8)`)
- **ILA Port Manager ที่จัดการได้อิสระ**:
  - เลื่อนตำแหน่ง probe ขึ้น-ลง หรือลากวาง (Drag & Drop) เพื่อจัดลำดับใหม่
  - สลับตำแหน่ง probe โดยตรง (เช่น สลับ `probe3` ⇄ `probe5`) ผ่านปุ่ม Swap หรือกด Alt ค้างแล้วลากวาง
  - แทรก probe ใหม่ระหว่างช่อง หรือกดปุ่ม `+` เพื่อเพิ่มสัญญาณต่อท้าย
  - รองรับพอร์ต unmapped (สร้างคอมเมนต์ placeholder ใน port map และแจ้งเตือนก่อน export)
- **ตัวสร้างโค้ด Port-Map ใน HDL**:
  - **VHDL Direct Entity Instantiation**: สร้างโค้ด `u_<ila_name> : entity work.<ila_name>` โดยตรง ไม่ต้องประกาศ component
  - **VHDL 1-Bit Vector Syntax**: สัญญาณขนาด 1 bit จะถูกแมปเข้ากับพอร์ต ILA ในรูปแบบ `probeN(0) => my_signal;` อย่างถูกต้องตามที่พอร์ต ILA ใน Vivado กำหนดให้เป็น vector
  - **VHDL Type Conversion**: แปลงชนิดข้อมูล `unsigned`/`signed` เป็น `std_logic_vector` ให้อัตโนมัติ และสร้างสัญญาณตัวกลาง (intermediate signals) สำหรับ `integer`, `boolean`, `enum`
  - **Verilog / SystemVerilog**: สร้าง instance `<ila_name> u_<ila_name> (...)` ที่สะอาดตา
- **สคริปต์ Vivado TCL อัจฉริยะ**:
  - ตรวจสอบในตัว: หากยังไม่มี IP ในโปรเจกต์จะสั่ง `create_ip` หากมีอยู่แล้วจะอัพเดทผ่าน `set_property`
  - **Default `CONFIG.C_INPUT_PIPE_STAGES` = 4** (ในขณะที่ Vivado ให้ค่าเริ่มต้นเป็น 1 ซึ่งการใส่ 4 ชั้นจะช่วยแก้ปัญหา Timing Violation ในวงจรความเร็วสูงได้อย่างมาก)
  - กำหนดประเภทของ Probe ได้ (`DATA AND TRIGGER`, `DATA ONLY`, `TRIGGER ONLY`)
  - กำหนดจำนวน Trigger Match Units (`ALL_PROBE_SAME_MU` หรือแยกอิสระต่อพอร์ต `C_PROBE<N>_MU_CNT`)
  - กำหนดความลึกของตัวอย่างข้อมูล (Sample Depth 1024 ถึง 131072) และ Storage Qualification
- **นำเข้า ILA เดิม (Import Existing ILA)**:
  - สแกนหาบล็อก instance ILA เดิมในไฟล์ HDL เพื่อดึงความสัมพันธ์ของ probe และสัญญาณกลับมาจัดตำแหน่งใหม่
  - อ่านสคริปต์ Vivado TCL เดิมเพื่อนำค่าการตั้งค่ากลับมาใช้
- **บันทึก/เปิดโปรเจกต์ และตรวจจับความเปลี่ยนแปลง (Diff & Sync)**:
  - บันทึกสถานะงานเป็นไฟล์ `.ilaproj` (JSON)
  - เมื่อเปิดโปรเจกต์เดิมขึ้นมาใหม่ โปรแกรมจะสแกนไฟล์ HDL เพื่อตรวจว่าสัญญาณใดเปลี่ยนขนาดบิต หรือสัญญาณใดหายไป พร้อมหน้าต่าง **Diff Review Dialog** ให้เลือกปรับปรุงได้ในคลิกเดียว
- **รองรับสองภาษา (EN / TH)**:
  - เอกสารประกอบครบถ้วนทั้งภาษาไทยและภาษาอังกฤษ
  - หน้าต่าง GUI มีปุ่มสลับภาษา TH/EN ได้ทันทีแบบเรียลไทม์
- **ใช้งานง่าย ไม่ต้องติดตั้ง Node.js**:
  - พัฒนาส่วนหน้าด้วย Vanilla JavaScript (ES modules) และ CSS ล้วน ติดตั้งผ่าน pip ได้ทันทีโดยไม่ต้องใช้ Node build tools

---

## การติดตั้ง (Installation)

### ข้อกำหนดเบื้องต้น
- Python 3.9 ขึ้นไป

### ติดตั้งผ่าน pip หรือ pipx
```bash
# ติดตั้งตรงจาก GitHub
pip install git+https://github.com/parama-ch/ILA-Manager.git

# หรือติดตั้งผ่าน pipx (แนะนำสำหรับเครื่องมือ CLI)
pipx install git+https://github.com/parama-ch/ILA-Manager.git
```

### ติดตั้งสำหรับนักพัฒนา (Development)
```bash
git clone https://github.com/parama-ch/ILA-Manager.git
cd ILA-Manager
python3 -m venv .venv
source .venv/bin/activate  # สำหรับ Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

---

## เริ่มต้นใช้งาน (Quick Start)

### 1. เปิดโปรแกรม Web GUI
```bash
ila-manager
```
คำสั่งนี้จะเริ่มทำงาน local web server ที่ `http://127.0.0.1:8765` และเปิดเว็บเบราว์เซอร์เริ่มต้นของคุณขึ้นมาโดยอัตโนมัติ

หากต้องการกำหนดพอร์ตเองหรือไม่ต้องการให้เปิดเบราว์เซอร์อัตโนมัติ:
```bash
ila-manager --port 9000 --no-browser
```

### 2. ขั้นตอนการทำงานใน GUI
1. **วางไฟล์ต้นฉบับ (Drop Sources)**: ลากไฟล์ Verilog หรือ VHDL มาวางในแผงซ้าย (หรือใช้ปุ่มเปิดไฟล์ในเครื่อง)
2. **เลือก Target Unit**: เลือกโมดูลหรือ architecture ที่ต้องการนำ ILA ไปฝังไว้
3. **จัดการ Probe**:
   - กดปุ่ม `+` ที่สัญญาณ หรือลากสัญญาณไปวางในตาราง Probe
   - ใช้ Tree Picker สำหรับ Array หรือ Record หรือระบุช่วงบิต (เช่น `[15:8]`)
   - ใช้ปุ่ม `⇄ Swap` หรือลากการ์ด Probe ไปซ้อนกันเพื่อสลับตำแหน่ง (เช่น สลับ `probe3` กับ `probe5`)
4. **ตั้งค่า ILA**:
   - ตั้งชื่อ ILA (เช่น `ila_0`), สัญญาณนาฬิกา (`clk`), Sample Depth และประเภทของแต่ละ Probe
   - สังเกตว่าค่าเริ่มต้นของ Flip-Flop Pipeline Stages จะถูกตั้งไว้ที่ **4** ชั้นโดยอัตโนมัติ
5. **คัดลอกโค้ดไปใช้งาน**:
   - **แท็บ TCL**: กดคัดลอก แล้วนำไปรันใน Vivado Tcl Console ด้วยคำสั่ง `source ila_0.tcl`
   - **แท็บ HDL**: กดคัดลอกโค้ด port map ไปวางในไฟล์ HDL ของคุณได้ทันที

### 3. โหมด CLI แบบ Headless (สำหรับการเขียนสคริปต์อัตโนมัติ)
คุณสามารถสั่งสร้างสคริปต์จากไฟล์โปรเจกต์ผ่าน command line ได้โดยไม่ต้องเปิดหน้าต่าง GUI:
```bash
ila-manager generate examples/demo.ilaproj --ila ila_0 --out build/
```

---

## ตัวอย่างโค้ดที่สร้างขึ้น

### ตัวอย่าง VHDL Direct Entity Instantiation
```vhdl
-- สร้างโดย ILA Manager v0.1.0
-- ต่อสายตรงผ่าน Direct Entity Instantiation (ไม่ต้องประกาศ component)
u_ila_0 : entity work.ila_0
    port map (
        clk       => clk,
        probe0(0) => rx_valid,                       -- สัญญาณ 1-bit ต่อเข้า probe(0)
        probe1(0) => rx_status(3),                   -- บิตเดี่ยวที่ตัดมาจากเวกเตอร์
        probe2    => rx_data(15 downto 8),           -- เวกเตอร์ช่วงบิต 8 บิต
        probe3    => rx_fifo_mem(2)(7 downto 0),     -- สมาชิกของ Array 2 มิติ
        probe4    => s_axis.tdata(31 downto 0),      -- ฟิลด์ใน Record
        probe5    => std_logic_vector(packet_cnt_u)  -- แปลง unsigned เป็น std_logic_vector อัตโนมัติ
    );
```

### ตัวอย่าง Verilog / SystemVerilog Named Instantiation
```verilog
// สร้างโดย ILA Manager v0.1.0
ila_0 u_ila_0 (
    .clk    (clk),
    .probe0 (rx_valid),
    .probe1 (rx_status[3]),
    .probe2 (rx_data[15:8]),
    .probe3 (rx_fifo_mem[2][7:0]),
    .probe4 (s_axis.tdata[31:0]),
    .probe5 (packet_cnt_u)
);
```

### ตัวอย่าง Vivado TCL Configuration Script
```tcl
# สร้างโดย ILA Manager v0.1.0 — ila_0 (6 probes)
set ila_name ila_0
if {[llength [get_ips -quiet $ila_name]] == 0} {
    create_ip -name ila -vendor xilinx.com -library ip -module_name $ila_name
}
set_property -dict [list \
    CONFIG.C_NUM_OF_PROBES       {6} \
    CONFIG.C_INPUT_PIPE_STAGES   {4} \
    CONFIG.C_DATA_DEPTH          {1024} \
    CONFIG.C_EN_STRG_QUAL        {0} \
    CONFIG.ALL_PROBE_SAME_MU     {true} \
    CONFIG.ALL_PROBE_SAME_MU_CNT {1} \
    CONFIG.C_PROBE0_WIDTH {1}  CONFIG.C_PROBE0_TYPE {0} \
    CONFIG.C_PROBE1_WIDTH {1}  CONFIG.C_PROBE1_TYPE {0} \
    CONFIG.C_PROBE2_WIDTH {8}  CONFIG.C_PROBE2_TYPE {0} \
    CONFIG.C_PROBE3_WIDTH {8}  CONFIG.C_PROBE3_TYPE {0} \
    CONFIG.C_PROBE4_WIDTH {32} CONFIG.C_PROBE4_TYPE {0} \
    CONFIG.C_PROBE5_WIDTH {16} CONFIG.C_PROBE5_TYPE {0} \
] [get_ips $ila_name]
generate_target all [get_files [get_property IP_FILE [get_ips $ila_name]]]
```

---

## การทดสอบ (Testing)

รันชุดทดสอบอัตโนมัติและตรวจเช็คคุณภาพโค้ดด้วย `pytest` และ `ruff`:
```bash
pytest -v
ruff check .
```

---

## สัญญาอนุญาต (License)

โปรเจกต์นี้เผยแพร่ภายใต้สัญญาอนุญาต [MIT License](LICENSE) — สามารถนำไปใช้งาน ปรับปรุง และแจกจ่ายต่อได้อย่างอิสระทั้งสำหรับงานส่วนตัว การศึกษา และเชิงพาณิชย์
