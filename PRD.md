# Claim-to-Cash: Product Requirements

Team Twisted Minds (Jainam Oswal, Samriddhi Gupta)
Paytm Build for India AI Hackathon, Grand Finals, Mumbai, 31 Oct 2026
Track 2: AI-Powered Financial Journeys

---

## 1. Summary

Claim-to-Cash lives inside Paytm's Health Insurance section and takes a policyholder from "I'm in hospital" to "money in my account". It reads the policy, checks the hospital bill before discharge, estimates the payout in rupees, helps file the claim (by AI or by hand), tracks it against IRDAI timelines, explains deductions and rejections in the user's language, drafts appeals, and, only where it helps, connects the user to a lender for a bridge loan.

**Principle: AI explains, rules decide.** Every rupee figure comes from a deterministic rule engine. The LLM reads documents and explains results. It never invents a number.

## 2. Problem

- Paytm teaches users about claims before they buy (room rent, waiting periods, co-pay, claim experience). After purchase, "My Policies" shows "No policies found" and there is no claims journey at all.
- IRDAI FY25: 3.26 crore health claims, about 8% repudiated. FY24: ₹26,038 cr of claims rejected or disallowed.
- Reimbursement claimants wait 20 to 46 days and see 13 to 26% deducted (SecureNow study). 3 in 4 borrowed to cover the gap. 73% got no clear reason for a deduction (Policybazaar Health Claims Index 2026).
- Most deductions are avoidable: room-rent caps, non-payable items, missing papers, late intimation.

## 3. Users

| Persona | Need |
|---|---|
| Policyholder in hospital (planned or emergency) | Know what is covered, avoid surprise deductions at discharge |
| Policyholder after discharge (reimbursement) | File correctly the first time, get paid fast, bridge the wait |
| Policyholder with a deduction or rejection | Understand why in plain language, know what to do next, get help appealing |

Any person can file for any insured member on the policy. There is no separate caregiver role.

## 4. Scope

**In scope:** individual and family floater health insurance; cashless and reimbursement claims; all Indian languages supported by Sarvam; Android phone app.

**Out of scope:** product recommendation or plan selling, caregiver role, motor and life insurance, real partner integrations (all mocked, see section 9).

## 5. Feature requirements

Priority: **P0** must work in the demo, **P1** should work, **P2** nice to have.

### F1. Onboarding and guided first claim (P1)
- 3 intro screens: what Claim-to-Cash does, how AI and rules split the work, data and consent.
- Contextual tips on first visit to key screens.
- "Try with a sample claim" loads a sample policy and patient so the user can walk the full journey without real documents. This doubles as the product tour.

### F2. Policy vault and plain-language explainer (P0)
- Add a policy three ways: upload PDF/photo; "Bought on Paytm" (mock list); enter insurer + policy number (mock fetch).
- Extract: insurer, plan, members, sum insured, room-rent cap, ICU cap, co-pay, deductible, sub-limits, initial / pre-existing / specific-disease waiting periods, exclusions, pre/post hospitalisation days, restoration, policy start date.
- Show "Your cover in plain words" under the same 5 topics Paytm uses pre-purchase: Room rent limit, Waiting periods, Coverage and exclusions, Co-pay, Claim experience. Every statement links to the clause and page.
- Show extraction confidence; low-confidence fields are flagged for the user to confirm.

### F3. Document capture and reading (P0)
- Upload photos or PDFs: final bill, itemised bill, discharge summary, prescriptions, investigation reports, payment receipts, ID, cancelled cheque.
- Auto-classify each document, extract fields (patient, hospital, dates, diagnosis, line items, amounts), show confidence.
- Completeness checklist per claim type; missing items shown as tasks.
- "Fetch from ABHA" (mock) as an alternative to upload.

### F4. Hospital stay check, before discharge (P0)
- Entry: "I'm in hospital" from the policy card.
- **The bill is optional.** The user can:
  - talk to the assistant by chat or voice ("I'm in a single private room at ₹6,000 a day, surgery is tomorrow"), or
  - upload an interim bill or estimate if they have one, or
  - fill a short structured form (room type, room rent per day, expected days, procedure).
- The rule engine checks the stated or extracted facts against the policy and reports: room-rent breach and its proportionate-deduction impact, likely non-payable items, waiting-period risk, sub-limit hits, and documents to collect before discharge.
- Shows actions the user can take now: ask for a room within the cap, ask the hospital to itemise consumables, collect specific papers.
- Intimation reminder: emergency within 24 hours of admission, planned 48 hours before admission (policy wording overrides). One-tap intimation message draft.
- Cashless: pre-auth checklist; 1-hour decision timer and 3-hour discharge timer from the IRDAI master circular (May 2024).

### F5. Claim form: AI-filled or manual, with live checks (P0)
- After documents are uploaded, a consent dialog asks:
  **"Shall we fill the claim form for you using your documents?"**
  - **Fill it for me**: AI pre-fills every field from documents and policy; user reviews and edits; each AI-filled field is marked.
  - **I'll fill it myself**: blank form; documents stay available for reference.
  - The choice and the consent are recorded in the audit log. The user can switch modes at any time.
- If the user uploaded nothing, the form opens in manual mode directly (the dialog is skipped).
- **Live corrections in manual mode** (and on edits in AI mode), shown inline under the field:
  - mismatch with documents (e.g. admission date on form differs from discharge summary),
  - mismatch with policy (member not on policy, date before policy start, claimed amount above remaining sum insured),
  - format errors (IFSC, mobile, dates in future, discharge before admission),
  - risk hints (intimation late, pre-existing condition inside waiting period).
  Each correction offers "Fix" (apply the suggested value) or "Keep mine".
- **Pre-flight result** before submit: "You'll likely get ₹X of ₹Y" with a line-by-line deduction table, the reason and the clause for each, and a rejection-risk level.
- Export the form as a PDF.

### F6. Filing and tracking (P0)
- Submit to the insurer (mock API). Claim gets a reference number.
- Status timeline: Draft, Intimated, Documents pending, Ready, Submitted, Query raised, Under review, Approved / Partially approved / Rejected, Settled.
- Timers against regulatory timelines; if the insurer is late on a reimbursement claim, show interest due.
- Insurer queries arrive as tasks with a due date; the assistant explains each query and helps answer it.
- Push-style in-app notifications.

### F7. Deduction and rejection explainer, escalation ladder (P0)
- Read the decision letter (mock from insurer, or user uploads a photo/screenshot).
- Explain in plain language in the user's chosen language, text and voice, mapped to the policy clause.
- Appeal-strength indicator (Strong / Possible / Weak) based on rule engine findings (e.g. a deduction the rules say is not allowed, such as proportionate deduction on pharmacy).
- Escalation ladder with deadlines:
  1. Reply / appeal to insurer (one-tap draft citing clause and documents),
  2. Insurer grievance (GRO),
  3. IRDAI Bima Bharosa,
  4. Insurance Ombudsman, office chosen by the user's pincode, within one year of the insurer's final reply.
- Each step's draft is editable; nothing is sent without the user tapping Send (mock).

### F8. One assistant across the journey (P0)
- Floating "Ask" button on every screen; knows the current screen, policy and claim.
- Input: text, voice (Sarvam speech-to-text), images and screenshots (Sarvam Vision), PDFs.
- Output: text plus voice playback (Sarvam text-to-speech), in the language picked by the user; all Sarvam-supported Indian languages.
- Cites the policy clause behind any coverage statement. Never states a payout number unless it came from the rule engine.
- "Talk to a human" creates a mock support ticket with the conversation attached.

### F9. Cash bridge (P1)
- Triggers:
  - reimbursement claim submitted and payout estimated, settlement expected in N days: bridge loan repaid automatically from the settlement;
  - discharge shortfall (cashless covered part of the bill): pay via UPI, Postpaid or EMI;
  - rejection: appeal path shown first; a regular medical EMI offered only after the user dismisses or completes the appeal step.
- Eligibility check (mock lender), Key Facts Statement (APR, fees, total repayable, tenure), cooling-off period, explicit consent, lender decision (mock). Copy states the lender decides and Paytm only connects (RBI Digital Lending Directions 2025).
- UPI payment screen (mock).

### F10. Trust layer (P0 for consent and audit log, P1 for the rest)
- DPDP consent screen at first use, per purpose (reading documents, AI processing, sharing with insurer, sharing with lender). Each consent can be withdrawn.
- "What AI did with your data": audit log of every AI action, consent and submission, with timestamps.
- Delete my data.
- Low-confidence extraction and low-confidence explanations route to human review (flag + mock ticket).

### F11. NHCX claim pack export (P1)
- Export a claim as a FHIR R4 Bundle following the NRCeS ClaimBundle profile (Claim, Patient, Coverage, Organization, DocumentReference). Viewable in-app as JSON.

## 6. Key user flows

1. **Add policy:** My Policies (empty) → Add policy → Upload PDF → extraction → confirm low-confidence fields → policy card + "Your cover in plain words".
2. **In hospital:** Policy card → I'm in hospital → choose cashless / reimbursement → tell us (chat, voice, form or bill photo) → hospital stay check → actions + intimation reminder.
3. **File reimbursement:** Policy card → Start claim → upload documents → checklist → consent dialog (Fill it for me / I'll fill it myself) → form with live checks → pre-flight result → submit → tracker.
4. **Decision:** Notification → decision explainer (voice in user's language) → escalation ladder → appeal draft → send (mock).
5. **Bridge:** Tracker shows "settlement expected in ~N days" → See bridge offer → KFS → consent → lender decision (mock) → money credited (mock) → auto-repay on settlement.

## 7. Screens

1. Paytm-style home (Financial Services grid with Health Insurance tile)
2. Paytm Insurance landing with new "Claims" card
3. Onboarding (3)
4. Consent
5. My Policies (empty and filled)
6. Add policy (3 methods)
7. Policy detail: "Your cover in plain words"
8. I'm in hospital: claim type choice
9. Hospital stay check: chat / form / bill input
10. Hospital stay check: result
11. Documents: upload + checklist
12. Fill-mode consent dialog
13. Claim form (AI-filled or manual, inline corrections)
14. Pre-flight result
15. Submitted
16. Claims list + tracker timeline
17. Query task
18. Decision explainer
19. Escalation ladder + draft editor
20. Bridge offer + KFS + result
21. UPI pay (mock)
22. Assistant sheet (chat, voice, attach)
23. What AI did (audit log), consents, delete data
24. Settings: language

Visual language from the Paytm app recordings: navy primary buttons (#002E6E) pinned at the bottom, sky-blue accent (#00BAF2), pale blue card backgrounds, white rounded cards, "Paytm Insurance Broking" header with Help at top right, list rows with icon, title, grey subtitle and chevron.

## 8. Architecture

```
Expo React Native app (Android, Expo Go)
        │  HTTP (laptop hotspot)
        ▼
FastAPI backend ──► Rule engine (pure Python, unit-tested)
   │            ──► Agent layer (tools below) ──► Sarvam APIs
   │            ──► SQLite (policies, claims, documents, audit)
   │            ──► Local file storage (uploads)
   └──► Mock services: /mock/insurer, /mock/nhcx, /mock/abha, /mock/upi, /mock/lender, /mock/support
```

**Agent tools:** parse_policy, classify_document, extract_document, hospital_check, estimate_payout, fill_claim_form, validate_form, explain_letter, draft_appeal, find_ombudsman, bridge_eligibility, create_handoff, export_fhir.

**Rule engine covers:**
- Room-rent proportionate deduction: when room rent per day exceeds the cap, associated medical expenses are paid in the ratio cap / actual. Not applied to pharmacy and consumables, implants and medical devices, diagnostics (IRDAI). ICU handled by ICU cap.
- Co-pay (percentage, age-based), deductible.
- Sub-limits by procedure (e.g. cataract).
- Waiting periods: initial 30 days (accidents exempt), pre-existing disease, specific diseases.
- IRDAI non-payable items list.
- Remaining sum insured.
- Pre/post hospitalisation windows.
- Intimation and document submission deadlines.

**Claim data model:** User, Policy (fields + clauses with page refs), Member, Claim, Document (type, extracted fields, confidence), BillLineItem (category, amount, payable, deduction, reason, clause_ref), TimelineEvent, Task, Correction, Appeal, BridgeOffer, ConsentRecord, AuditLog.

## 9. Data sources: real vs mocked

Only free, open or publicly accessible sources are used. Sarvam is paid with the team's credits.

| Real (public / open) | Mocked behind a swappable interface |
|---|---|
| Public policy wordings of Care, Niva Bupa, ICICI Lombard (partners shown on Paytm) | Paytm login, "Bought on Paytm" policies, UPI, Postpaid |
| IRDAI non-payable items list, proportionate-deduction rules | Insurer / TPA claim API, status, decision letters |
| IRDAI timelines (cashless 1 hour, discharge 3 hours) | NHCX submission |
| Insurance Ombudsman offices and pincode jurisdiction | ABHA record fetch |
| NRCeS FHIR ClaimBundle profile | Lender decision, loan disbursal |
| Bima Bharosa grievance path | Human support ticket |
| Sarvam: Vision, LLM, speech-to-text, text-to-speech, translation | |

Sample bills and discharge summaries are synthetic. No real patient data. Fallback when Sarvam is unreachable: cached responses for the sample claims, and PyMuPDF text extraction for digital PDFs.

## 10. Non-functional

- Works offline-ish for the demo: sample claims have cached AI responses.
- AI responses under 5 s for chat; document extraction under 15 s with a progress state.
- Every AI action and consent written to the audit log.
- No secrets in the app bundle; Sarvam key stays on the backend.
- All money math covered by unit tests.

## 11. Success metrics

- ₹ recovered per claim (deductions avoided + successful appeals)
- First-time-right filing rate
- Days from discharge to money in account
- Share of claims needing human help
- Bridge uptake and repayment from settlement

Business: Paytm Insurance Broking can legally offer claims assistance as a licensed broker. Revenue from claims-assist fees to insurers / TPAs (cleaner claims, lower processing cost), lender referral fees on bridge loans, and retention of insurance customers.

## 12. Build phases

| Phase | Contents |
|---|---|
| 0. Setup | Repo, PRD, tracker, backend and app skeletons, Paytm theme |
| 1. Rule engine + data | Rule engine with tests, sample policies (from public wordings), synthetic patients, non-payables list, ombudsman offices |
| 2. Backend + mocks | FastAPI APIs, SQLite models, mock insurer / NHCX / ABHA / UPI / lender / support, audit log |
| 3. AI layer | Sarvam client (LLM, Vision, STT, TTS, translate), agent tools, caching, fallbacks |
| 4. Core app screens | Home, insurance landing, My Policies, add policy, cover explainer, documents, form (AI / manual + corrections), pre-flight, tracker |
| 5. Hospital check + assistant | I'm in hospital flow (chat / voice / form / bill), floating assistant with voice and attachments, language picker |
| 6. Decisions + bridge | Decision explainer, escalation ladder + drafts, bridge offer + KFS, UPI mock |
| 7. Trust + polish | Onboarding, consent, audit log, delete data, FHIR export, empty / loading / error states |
| 8. Demo readiness | End-to-end run on phone over hotspot, cached sample flows, demo script |

## 13. Demo script (about 4 minutes)

1. Paytm home → Health Insurance → My Policies says "No policies found". That is the gap.
2. Add a real Niva Bupa policy wording; see the cover explained in plain words.
3. I'm in hospital → speak in Hindi: "single room, ₹6,000 a day" → room-rent breach caught, with the rupee impact.
4. Upload discharge documents → consent dialog → Fill it for me → pre-flight: "₹68,400 of ₹1,10,000" with reasons.
5. Fast-forward: partial rejection → explained by voice in Hindi → appeal drafted in one tap.
6. Bridge offer with Key Facts Statement.
7. Export the NHCX claim pack.
