"""Generate synthetic hospital / insurer documents for testing Claimezy.

All people, hospitals, insurers and numbers are fictional. Every page carries a
"Synthetic sample for demo" footer.

Run: .venv/bin/python scripts/make_demo_docs.py
Output: ../demo-docs/ (served by the API at /demo-docs/)
"""

import sys
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.data.samples import SAMPLE_CLAIMS, SAMPLE_POLICIES  # noqa: E402

OUT = Path(__file__).resolve().parent.parent.parent / "demo-docs"
OUT.mkdir(exist_ok=True)

NAVY = (0, 0.18, 0.43)
GREY = (0.4, 0.4, 0.45)
LIGHT = (0.93, 0.95, 0.98)
W, H = 595, 842
M = 40


def inr(n):
    s = f"{int(round(n)):,}"
    # Indian grouping
    n = int(round(n))
    t = str(n)
    if len(t) > 3:
        head, tail = t[:-3], t[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts) + "," + tail
    else:
        s = t
    return "Rs. " + s


class Doc:
    def __init__(self):
        self.doc = pymupdf.open()
        self.page = None
        self.y = 0

    def new_page(self, org, sub, title):
        self.page = self.doc.new_page(width=W, height=H)
        p = self.page
        p.draw_rect(pymupdf.Rect(0, 0, W, 78), color=None, fill=NAVY)
        p.insert_text((M, 34), org, fontsize=16, fontname="hebo", color=(1, 1, 1))
        p.insert_text((M, 54), sub, fontsize=8.5, fontname="helv", color=(0.85, 0.9, 1))
        p.insert_text((M, 108), title, fontsize=13, fontname="hebo", color=NAVY)
        p.draw_line((M, 116), (W - M, 116), color=NAVY, width=1)
        p.insert_text((M, H - 22), "Synthetic sample for Claimezy demo. Not a real medical or financial record.", fontsize=7, fontname="helv", color=GREY)
        self.y = 136

    def kv(self, pairs, cols=2):
        col_w = (W - 2 * M) / cols
        for i in range(0, len(pairs), cols):
            for j, (k, v) in enumerate(pairs[i:i + cols]):
                x = M + j * col_w
                self.page.insert_text((x, self.y), k, fontsize=7.5, fontname="helv", color=GREY)
                self.page.insert_text((x, self.y + 12), str(v), fontsize=10, fontname="hebo")
            self.y += 30

    def heading(self, text):
        self.y += 6
        self.page.insert_text((M, self.y), text.upper(), fontsize=8.5, fontname="hebo", color=NAVY)
        self.y += 12

    def para(self, text, size=9.5):
        rect = pymupdf.Rect(M, self.y, W - M, self.y + 300)
        rest = self.page.insert_textbox(rect, text, fontsize=size, fontname="helv")
        self.y += (300 - rest) + 6 if rest >= 0 else 300

    def table(self, header, rows, widths, align_right=(), total=None):
        x0 = M
        self.page.draw_rect(pymupdf.Rect(M, self.y - 11, W - M, self.y + 5), color=None, fill=LIGHT)
        x = x0
        for h, w in zip(header, widths):
            self.page.insert_text((x + 4, self.y), h, fontsize=8, fontname="hebo", color=NAVY)
            x += w
        self.y += 18
        for r in rows:
            x = x0
            for k, (cell, w) in enumerate(zip(r, widths)):
                txt = str(cell)
                if k in align_right:
                    tw = pymupdf.get_text_length(txt, fontname="helv", fontsize=9)
                    self.page.insert_text((x + w - tw - 4, self.y), txt, fontsize=9, fontname="helv")
                else:
                    self.page.insert_text((x + 4, self.y), txt, fontsize=9, fontname="helv")
                x += w
            self.page.draw_line((M, self.y + 5), (W - M, self.y + 5), color=(0.88, 0.9, 0.93), width=0.5)
            self.y += 17
        if total:
            label, val = total
            self.y += 4
            tw = pymupdf.get_text_length(val, fontname="hebo", fontsize=11)
            self.page.insert_text((W - M - tw - 4, self.y), val, fontsize=11, fontname="hebo")
            self.page.insert_text((W - M - 230, self.y), label, fontsize=10, fontname="hebo")
            self.y += 20

    def sign(self, who):
        self.y += 24
        self.page.draw_line((W - M - 160, self.y), (W - M, self.y), color=GREY, width=0.6)
        self.page.insert_text((W - M - 160, self.y + 12), who, fontsize=8, fontname="helv", color=GREY)
        self.y += 24

    def save_pdf(self, name):
        self.doc.save(OUT / name)
        return OUT / name

    def save_jpg(self, name, dpi=110, crop_bottom=None):
        pix = self.doc[0].get_pixmap(dpi=dpi, clip=pymupdf.Rect(0, 0, W, crop_bottom or H))
        pix.save(OUT / name, jpg_quality=82) if hasattr(pix, "save") else None
        return OUT / name


POL = {p["id"]: p for p in SAMPLE_POLICIES}
HOSP_SUB = {
    "sunita_gallbladder": "NABH accredited · Andheri East, Mumbai 400069 · GSTIN 27AAACS0000X1Z5 · Ph 022-4000 0000",
    "arjun_dengue": "Powai, Mumbai 400076 · GSTIN 27AAACL0000X1Z2 · Ph 022-4100 0000",
    "rakesh_knee": "Joint replacement centre · Mumbai 400053 · GSTIN 27AAACK0000X1Z9",
}
DOCTOR = {"sunita_gallbladder": "Dr. A. Deshpande, MS (General Surgery)", "arjun_dengue": "Dr. R. Iyer, MD (Medicine)", "rakesh_knee": "Dr. V. Rao, MS (Ortho)"}
PREFIX = {"sunita_gallbladder": "Sunita", "arjun_dengue": "Arjun", "rakesh_knee": "Rakesh"}
UHID = {"sunita_gallbladder": "SSMH/26/104523", "arjun_dengue": "LH/26/088120", "rakesh_knee": "KOC/26/221904"}


def dmy(iso):
    y, m, d = iso.split("-")
    return f"{d}/{m}/{y}"


def member(key):
    c = SAMPLE_CLAIMS[key]
    return next(m for m in POL[c["policy_id"]]["members"] if m["id"] == c["member_id"])


def hospital_name(c):
    return c["hospital"].split(",")[0]


def discharge_summary(key):
    c, m, p = SAMPLE_CLAIMS[key], member(key), POL[SAMPLE_CLAIMS[key]["policy_id"]]
    d = Doc()
    d.new_page(hospital_name(c).upper(), HOSP_SUB[key], "DISCHARGE SUMMARY")
    d.kv([("Patient name", m["name"]), ("UHID / IP No.", UHID[key]), ("Age / Sex", f"{m['age']} / {'Female' if m['gender'] == 'F' else 'Male'}"),
          ("Insurance", f"{p['insurer']} · {p['policy_number']}"), ("Date of admission", dmy(c["admission_date"]) + "  09:40"),
          ("Date of discharge", dmy(c["discharge_date"]) + "  12:15"), ("Consultant", DOCTOR[key]),
          ("Room", {"single_private": "Single private", "twin_sharing": "Twin sharing", "general_ward": "General ward"}[c["room_category"]])])
    d.heading("Final diagnosis")
    d.para(c["diagnosis"])
    d.heading("Procedure / treatment")
    d.para(c["procedure"] + (" under general anaesthesia on " + dmy(c["admission_date"]) if key != "arjun_dengue" else ""))
    hist = {
        "sunita_gallbladder": "Patient presented with recurrent right upper quadrant pain for 3 weeks, worse after meals, with nausea. Known hypertensive on Tab. Telmisartan 40 mg. USG abdomen showed multiple gallbladder calculi with wall thickening.",
        "arjun_dengue": "Fever for 4 days with body ache and retro-orbital pain. NS1 antigen positive. Platelet count dropped to 38,000/cumm on day 2; one unit of single donor platelets transfused.",
        "rakesh_knee": "Progressive right knee pain for 3 years, difficulty walking more than 200 m. X-ray: Kellgren-Lawrence grade IV osteoarthritis right knee. Known diabetic on Tab. Metformin 500 mg BD.",
    }[key]
    d.heading("History and findings")
    d.para(hist)
    course = {
        "sunita_gallbladder": "Underwent uneventful laparoscopic cholecystectomy. Post-operative recovery smooth, tolerating oral diet, port sites healthy. Discharged in stable condition.",
        "arjun_dengue": "Managed with IV fluids, antipyretics and monitoring. Platelets recovered to 1,12,000/cumm. Afebrile for 48 hours. Discharged in stable condition.",
        "rakesh_knee": "Underwent right total knee replacement. Mobilised with walker on day 2. Wound healthy. Discharged with physiotherapy advice.",
    }[key]
    d.heading("Course in hospital")
    d.para(course)
    d.heading("Advice on discharge")
    d.para("Medicines as prescribed. Review in OPD after 7 days with reports. Return immediately if fever, severe pain or bleeding.")
    d.sign(DOCTOR[key])
    return d.save_pdf(f"{PREFIX[key]}_Discharge_Summary.pdf")


def final_bill(key):
    c, m, p = SAMPLE_CLAIMS[key], member(key), POL[SAMPLE_CLAIMS[key]["policy_id"]]
    d = Doc()
    d.new_page(hospital_name(c).upper(), HOSP_SUB[key], "FINAL IN-PATIENT BILL (ITEMISED)")
    d.kv([("Patient name", m["name"]), ("Bill No.", f"IPB-{UHID[key][-6:]}"), ("Admission", dmy(c["admission_date"])), ("Discharge", dmy(c["discharge_date"])),
          ("Payer", "Self (reimbursement)"), ("Room", f"{c['room_category'].replace('_', ' ').title()} · {c['room_days']} days")])
    rows = [(i + 1, it["name"], it["category"].title(), inr(it["amount"]).replace("Rs. ", "")) for i, it in enumerate(c["line_items"])]
    total = sum(i["amount"] for i in c["line_items"])
    d.table(["#", "Particulars", "Head", "Amount (Rs.)"], rows, [26, 300, 95, 94], align_right=(3,), total=("Net payable", inr(total)))
    d.para(f"Amount in words: Rupees {words(total)} only.", 9)
    d.para("Received with thanks. This is a computer generated bill.", 8)
    d.sign("Billing Executive")
    return d.save_pdf(f"{PREFIX[key]}_Final_Bill.pdf")


def words(n):
    ones = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
    tens = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()

    def two(x):
        return ones[x] if x < 20 else tens[x // 10] + ("" if x % 10 == 0 else " " + ones[x % 10])

    def three(x):
        h, r = divmod(x, 100)
        return ((ones[h] + " hundred" + (" " if r else "")) if h else "") + (two(r) if r else "")

    n = int(n)
    parts = []
    for div, name in ((10000000, "crore"), (100000, "lakh"), (1000, "thousand")):
        q, n = divmod(n, div)
        if q:
            parts.append(f"{three(q)} {name}")
    if n:
        parts.append(three(n))
    return " ".join(parts).title()


def receipt(key):
    c, m = SAMPLE_CLAIMS[key], member(key)
    total = sum(i["amount"] for i in c["line_items"])
    d = Doc()
    d.new_page(hospital_name(c).upper(), HOSP_SUB[key], "PAYMENT RECEIPT")
    d.kv([("Receipt No.", f"RC-{UHID[key][-6:]}-01"), ("Date", dmy(c["discharge_date"])), ("Received from", m["name"]), ("Mode", "UPI · Ref 6302 1188 4471"),
          ("Against bill", f"IPB-{UHID[key][-6:]}"), ("Amount", inr(total))])
    d.para(f"Received a sum of {inr(total)} (Rupees {words(total)} only) towards in-patient charges.")
    d.sign("Cashier")
    return d.save_jpg(f"{PREFIX[key]}_Payment_Receipt.jpg", crop_bottom=420)


def pharmacy(key):
    c, m = SAMPLE_CLAIMS[key], member(key)
    d = Doc()
    d.new_page(f"{hospital_name(c).upper()} PHARMACY", "Drug licence MH-MZ1-000000 · " + HOSP_SUB[key].split(" · ")[-1], "PHARMACY BILL WITH PRESCRIPTION REFERENCE")
    d.kv([("Patient", m["name"]), ("Prescribed by", DOCTOR[key]), ("Bill date", dmy(c["discharge_date"])), ("IP No.", UHID[key])])
    meds = {
        "sunita_gallbladder": [("Inj. Ceftriaxone 1 g", 6, 145), ("Inj. Pantoprazole 40 mg", 8, 62), ("Inj. Paracetamol 1 g IV", 8, 210), ("Inj. Ondansetron 4 mg", 6, 48), ("IV fluids RL / NS 500 ml", 14, 95), ("Tab. Telmisartan 40 mg", 10, 14), ("Inj. Tramadol 50 mg", 6, 39), ("Surgical consumables (port, clips)", 1, 5878)],
        "arjun_dengue": [("IV fluids NS 500 ml", 24, 95), ("Inj. Paracetamol 1 g IV", 10, 210), ("Single donor platelets processing", 1, 9500), ("Tab. Pantoprazole 40 mg", 8, 12), ("ORS sachets", 10, 22)],
        "rakesh_knee": [("Inj. Cefuroxime 1.5 g", 8, 420), ("Inj. Enoxaparin 40 mg", 10, 520), ("Inj. Tranexamic acid", 4, 180), ("Tab. Metformin 500 mg", 20, 3), ("Analgesics and antibiotics (oral)", 1, 15660), ("Insulin (sliding scale)", 1, 1200)],
    }[key]
    rows = [(i + 1, n, q, f"{r:,}", f"{q * r:,}") for i, (n, q, r) in enumerate(meds)]
    total = sum(q * r for _, q, r in meds)
    d.table(["#", "Item", "Qty", "Rate", "Amount"], rows, [26, 290, 50, 70, 79], align_right=(2, 3, 4), total=("Total", inr(total)))
    d.sign("Pharmacist")
    return d.save_jpg(f"{PREFIX[key]}_Pharmacy_Bill.jpg")


def lab(key):
    c, m = SAMPLE_CLAIMS[key], member(key)
    d = Doc()
    d.new_page(f"{hospital_name(c).upper()} LABORATORY", "NABL accredited laboratory", "INVESTIGATION REPORT")
    d.kv([("Patient", m["name"]), ("Referred by", DOCTOR[key]), ("Collected", dmy(c["admission_date"])), ("Report ID", f"LAB-{UHID[key][-6:]}")])
    tests = {
        "sunita_gallbladder": [("Haemoglobin", "12.1", "g/dL", "12.0 - 15.5"), ("Total leucocyte count", "11,800", "/cumm", "4,000 - 11,000"), ("Total bilirubin", "1.4", "mg/dL", "0.3 - 1.2"), ("SGPT (ALT)", "52", "U/L", "7 - 35"), ("Alkaline phosphatase", "168", "U/L", "40 - 129"), ("USG abdomen", "Multiple calculi, GB wall 4 mm", "", "")],
        "arjun_dengue": [("Dengue NS1 antigen", "Positive", "", "Negative"), ("Platelet count (day 2)", "38,000", "/cumm", "1.5 - 4.5 lakh"), ("Platelet count (day 4)", "1,12,000", "/cumm", "1.5 - 4.5 lakh"), ("Haematocrit", "46", "%", "40 - 50")],
        "rakesh_knee": [("HbA1c", "7.4", "%", "< 5.7"), ("Fasting blood sugar", "142", "mg/dL", "70 - 100"), ("X-ray right knee", "KL grade IV OA", "", ""), ("Serum creatinine", "1.0", "mg/dL", "0.7 - 1.3")],
    }[key]
    d.table(["Test", "Result", "Unit", "Reference"], tests, [190, 150, 70, 105])
    d.sign("Pathologist")
    return d.save_pdf(f"{PREFIX[key]}_Lab_Report.pdf")


def cheque(key):
    c = SAMPLE_CLAIMS[key]
    b = c["bank"]
    doc = pymupdf.open()
    pg = doc.new_page(width=600, height=270)
    bank = "HDFC BANK" if b["ifsc"].startswith("HDFC") else "AXIS BANK"
    pg.draw_rect(pymupdf.Rect(0, 0, 600, 270), color=None, fill=(0.94, 0.97, 1))
    pg.insert_text((24, 36), bank, fontsize=16, fontname="hebo", color=NAVY)
    pg.insert_text((24, 54), f"Branch: Andheri East, Mumbai   IFSC: {b['ifsc']}", fontsize=9, fontname="helv")
    pg.insert_text((440, 36), "Date  __/__/____", fontsize=9, fontname="helv")
    pg.insert_text((24, 96), "Pay ______________________________________________   or Bearer", fontsize=10, fontname="helv")
    pg.insert_text((24, 126), "Rupees ____________________________________________", fontsize=10, fontname="helv")
    pg.insert_text((24, 168), f"A/c No. {b['account_number']}", fontsize=12, fontname="hebo")
    pg.insert_text((24, 186), b["account_name"].upper(), fontsize=10, fontname="hebo")
    pg.insert_text((24, 245), f"\"{b['account_number'][-6:]}\"  {b['ifsc'][:4]}0{b['ifsc'][5:]}:  000229  31", fontsize=12, fontname="cour")
    pg.draw_line((60, 230), (540, 40), color=(0.8, 0.1, 0.1), width=4)
    pg.insert_text((240, 150), "CANCELLED", fontsize=34, fontname="hebo", color=(0.8, 0.1, 0.1), rotate=0)
    pg.insert_text((24, 262), "Synthetic sample for Claimezy demo.", fontsize=6, fontname="helv", color=GREY)
    pg.get_pixmap(dpi=130).save(OUT / f"{PREFIX[key]}_Cancelled_Cheque.jpg", jpg_quality=82)


def interim_bill():
    key = "sunita_gallbladder"
    c, m = SAMPLE_CLAIMS[key], member(key)
    d = Doc()
    d.new_page(hospital_name(c).upper(), HOSP_SUB[key], "INTERIM BILL (PROVISIONAL) · DAY 2")
    d.kv([("Patient", m["name"]), ("Admitted", dmy(c["admission_date"])), ("Room", "Single private · Rs. 7,500 per day"), ("Planned procedure", "Laparoscopic cholecystectomy")])
    rows = [(1, "Room charges (2 days x 7,500)", "15,000"), (2, "Nursing charges (2 days)", "2,000"), (3, "Surgeon fees (estimate)", "25,000"), (4, "OT charges (estimate)", "15,000"),
            (5, "Pharmacy till date", "6,200"), (6, "Investigations", "7,500"), (7, "Admission kit", "800")]
    d.table(["#", "Particulars", "Amount (Rs.)"], rows, [26, 380, 109], align_right=(2,), total=("Running total", "Rs. 71,500"))
    d.para("Estimated final bill: Rs. 1,05,000 to 1,15,000 for a 4-day stay. Provisional, subject to change.", 9)
    return d.save_jpg("Sunita_Interim_Bill_Day2.jpg")


def decision_letter(key, typ):
    c, m, p = SAMPLE_CLAIMS[key], member(key), POL[SAMPLE_CLAIMS[key]["policy_id"]]
    d = Doc()
    d.new_page(p["insurer"].upper(), "Health Claims Department · Toll free 1800-000-0000 (demo)", "CLAIM SETTLEMENT LETTER" if typ != "rejected" else "INTIMATION OF REPUDIATION")
    ref = {"sunita_gallbladder": "CLM2610214471", "rakesh_knee": "CLM2610298803"}[key]
    total = sum(i["amount"] for i in c["line_items"])
    d.kv([("Claim No.", ref), ("Policy No.", p["policy_number"]), ("Patient", m["name"]), ("Hospital", hospital_name(c)),
          ("Admission / discharge", f"{dmy(c['admission_date'])} to {dmy(c['discharge_date'])}"), ("Amount claimed", inr(total))])
    if typ == "rejected":
        d.heading("Decision")
        d.para(f"We regret that your claim is not admissible. The treatment ({c['procedure']}) falls within the 24-month waiting period for specified diseases under Clause C4.3 of your policy. Continuous coverage started on 15/08/2025.")
        d.heading("Amount approved")
        d.para("Rs. 0")
    else:
        d.heading("Settlement summary")
        rows = [("Amount claimed", inr(110000)), ("Less: non-payable items (Clause C6.2)", "- Rs. 6,000"), ("Less: room rent above eligibility (Clause C3.2)", "- Rs. 10,000"),
                ("Less: proportionate deduction on associated charges (Clause C3.2)", "- Rs. 18,000"), ("Less: proportionate deduction on pharmacy and diagnostics", "- Rs. 6,667"),
                ("Less: co-payment 10% (Clause C5.6)", "- Rs. 6,933"), ("Amount approved", inr(62400))]
        d.table(["Particulars", "Amount"], rows, [380, 135], align_right=(1,))
        d.para("Payment will be credited by NEFT to the account on record within 7 working days. UTR will be shared by SMS.")
    d.heading("Grievance")
    d.para("If you are not satisfied, write to our Grievance Redressal Officer at gro@insurer.example within 15 days. You may also register a complaint on IRDAI Bima Bharosa or approach the Insurance Ombudsman under the Insurance Ombudsman Rules, 2017.")
    d.sign("Authorised Signatory, Claims")
    name = f"{PREFIX[key]}_{'Rejection' if typ == 'rejected' else 'Settlement'}_Letter.pdf"
    d.save_pdf(name)
    d.save_jpg(name.replace(".pdf", ".jpg"))


def sms_screenshot():
    doc = pymupdf.open()
    pg = doc.new_page(width=360, height=640)
    pg.draw_rect(pymupdf.Rect(0, 0, 360, 640), color=None, fill=(0.96, 0.96, 0.97))
    pg.draw_rect(pymupdf.Rect(0, 0, 360, 56), color=None, fill=(1, 1, 1))
    pg.insert_text((16, 34), "AX-SGIHLT", fontsize=14, fontname="hebo")
    pg.insert_text((16, 48), "Suraksha Health Claims (demo)", fontsize=8, fontname="helv", color=GREY)
    msgs = [
        "Dear Customer, your claim CLM2610214471 for SUNITA KULKARNI has been received on 21-10-2026. Track: sgi.example/track",
        "Claim CLM2610214471: Additional document required - pharmacy bills with prescriptions for all medicines billed (Rs 12,500). Please submit within 7 days or claim may be closed.",
        "Claim CLM2610214471 settled for Rs 62,400 against claimed Rs 1,10,000. Deductions: Rs 47,600. Details in settlement letter sent to your email.",
    ]
    y = 80
    for t in msgs:
        r = pymupdf.Rect(16, y, 300, y + 110)
        pg.draw_rect(pymupdf.Rect(12, y - 6, 308, y + 82), color=None, fill=(1, 1, 1), radius=0.08)
        pg.insert_textbox(r, t, fontsize=9.5, fontname="helv")
        y += 100
    pg.insert_text((16, 628), "Synthetic sample for Claimezy demo.", fontsize=6, fontname="helv", color=GREY)
    pg.get_pixmap(dpi=160).save(OUT / "Insurer_SMS_Screenshot.png")


def policy_pdf(pid, fname, header_lines):
    p = POL[pid]
    d = Doc()
    d.new_page(p["insurer"].upper(), "Retail Health Insurance · UIN DEMO-HLT-0001 (demo)", f"{p['plan']} · POLICY SCHEDULE AND WORDING")
    d.kv(header_lines)
    pages = {}
    for cl in p["clauses"]:
        pages.setdefault(cl["page"], []).append(cl)
    for pg_no in sorted(pages):
        d.new_page(p["insurer"].upper(), f"{p['plan']} · Policy wording", f"Page {pg_no}")
        for cl in pages[pg_no]:
            d.heading(f"Section {cl['id']} · {cl['title']}")
            d.para(cl["text"])
    d.save_pdf(fname)


def upload_test_policy():
    """A policy that exists only as this PDF, not in samples.py, so uploading it is a real read with known answers."""
    org, plan = "NAVDEEP GENERAL INSURANCE (DEMO)", "Parivar Raksha Gold"
    d = Doc()
    d.new_page(org, "Retail Health Insurance · UIN DEMO-HLT-0002 (demo)", f"{plan} · POLICY SCHEDULE AND WORDING")
    d.kv([("Policy No.", "NGI/PRG/2026/0071542"), ("Policy type", "Family floater"), ("Policy period", "01/04/2026 to 31/03/2027"),
          ("Sum insured", f"Rs {inr(750000)}"), ("Policyholder", "Meera Joshi, Self, Female, age 45"), ("Insured member", "Anil Joshi, Spouse, Male, age 49"),
          ("Pre-existing condition declared", "Anil Joshi: Diabetes"), ("Consumables cover", "Not opted")])
    wording = [
        (2, [("C1.1", "Sum insured", f"The sum insured is Rs {inr(750000)} per policy year, shared by all insured members on a floater basis."),
             ("C2.1", "Room rent", "Room rent is payable up to 1% of the sum insured per day. If a higher room is chosen, associated medical expenses are paid in the same proportion, except pharmacy, consumables, implants and diagnostics."),
             ("C2.2", "ICU charges", "ICU charges are payable up to 2% of the sum insured per day."),
             ("C3.1", "Co-payment", "A co-payment of 20% applies to every admissible claim for an insured member aged 60 years or above. No co-payment applies below that age."),
             ("C3.2", "Deductible", f"A deductible of Rs {inr(10000)} applies to each claim."),
             ("C4.1", "Sub-limits", f"Cataract is payable up to Rs {inr(40000)} per eye. Hernia repair is payable up to Rs {inr(60000)}.")]),
        (3, [("C5.1", "Initial waiting period", "Illness claims are not covered in the first 30 days from the policy start date. Accidents are covered from day one."),
             ("C5.2", "Pre-existing diseases", "Pre-existing diseases are covered after 48 months of continuous cover."),
             ("C5.3", "Specific diseases", "Cataract, hernia, joint replacement and kidney stones are covered after 24 months of continuous cover."),
             ("C6.1", "Exclusions", "Cosmetic surgery, weight-loss surgery and treatment outside India are excluded."),
             ("C6.2", "Non-payable items", "Items on the IRDAI list of non-medical expenses are not payable."),
             ("C7.1", "Pre and post hospitalisation", "Medical expenses are covered for 60 days before admission and 90 days after discharge."),
             ("C8.1", "Claim intimation", "Inform the insurer within 24 hours of an emergency admission, and at least 48 hours before a planned admission."),
             ("C8.2", "Claim documents", "Submit all claim documents within 15 days of discharge.")]),
    ]
    for page_no, clauses in wording:
        d.new_page(org, f"{plan} · Policy wording", f"Page {page_no}")
        for cid, title, text in clauses:
            d.heading(f"Section {cid} · {title}")
            d.para(text)
    d.save_pdf("Upload_Test_Parivar_Raksha_policy.pdf")


def index_html():
    files = sorted(f.name for f in OUT.iterdir() if f.suffix in (".pdf", ".jpg", ".png"))
    groups = {"Policies": [f for f in files if "policy" in f.lower()],
              "Sunita (gallbladder, room above limit)": [f for f in files if f.startswith("Sunita")],
              "Arjun (dengue, clean claim)": [f for f in files if f.startswith("Arjun")],
              "Rakesh (knee replacement, waiting period)": [f for f in files if f.startswith("Rakesh")],
              "Screenshots for the assistant": [f for f in files if f.startswith("Insurer")]}
    body = "".join(f"<h2>{g}</h2><ul>" + "".join(f'<li><a href="{f}" download>{f}</a></li>' for f in fs) + "</ul>" for g, fs in groups.items() if fs)
    (OUT / "index.html").write_text(f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Claimezy sample documents</title><style>body{{font-family:system-ui,sans-serif;margin:16px;color:#101828;background:#F3F6FA}}h1{{color:#002E6E;font-size:22px}}
h2{{font-size:15px;margin-top:22px}}ul{{list-style:none;padding:0}}li{{margin:8px 0}}a{{display:block;background:#fff;border:1px solid #E4E9F0;border-radius:12px;padding:12px;color:#002E6E;text-decoration:none;font-weight:600}}
p{{color:#5B6B7F;font-size:13px}}</style></head><body><h1>Claimezy sample documents</h1>
<p>Tap a file to download it to your phone, then pick it in the app (Add policy, Documents, Bill photo, or the assistant's image button). All documents are synthetic.</p>{body}</body></html>""")


if __name__ == "__main__":
    for k in SAMPLE_CLAIMS:
        discharge_summary(k)
        final_bill(k)
        cheque(k)
    for k in ("sunita_gallbladder", "rakesh_knee"):
        receipt(k)
        pharmacy(k)
        lab(k)
    interim_bill()
    decision_letter("sunita_gallbladder", "partial")
    decision_letter("rakesh_knee", "rejected")
    sms_screenshot()
    upload_test_policy()
    policy_pdf("pol_shield", "Family_Shield_Plus_policy.pdf", [
        ("Policy No.", POL["pol_shield"]["policy_number"]), ("Policy period", "15/08/2026 to 14/08/2027"), ("Continuous cover since", "15/08/2025"),
        ("Plan type / Sum insured", "Family floater · Rs. 5,00,000"), ("Insured 1", "Sunita Kulkarni, Self, 58 F · PED: Hypertension"),
        ("Insured 2", "Rakesh Kulkarni, Spouse, 61 M · PED: Diabetes"), ("Pre / post hospitalisation", "30 days / 60 days"), ("Room rent", "1% of SI per day, ICU 2%")])
    policy_pdf("pol_paytm_care", "Care_Max_10L_policy.pdf", [
        ("Policy No.", POL["pol_paytm_care"]["policy_number"]), ("Policy period", "02/03/2026 to 01/03/2027"), ("Continuous cover since", "02/03/2024"),
        ("Plan type / Sum insured", "Individual · Rs. 10,00,000"), ("Insured", "Arjun Mehta, Self, 34 M"), ("Add-on", "Claim Shield (consumables cover)"),
        ("Pre / post hospitalisation", "60 days / 180 days"), ("Room rent", "No capping")])
    index_html()
    print("\n".join(sorted(f.name for f in OUT.iterdir())))
