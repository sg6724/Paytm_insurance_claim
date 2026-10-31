# Claimezy

Paytm Build for India AI Hackathon, Grand Finals, Track 2 (AI-Powered Financial Journeys). Team Twisted Minds.

Claimezy lives inside Paytm's Health Insurance section and takes a policyholder from "I'm in hospital" to "money in my account": it explains the policy in any Indian language, checks the hospital stay before discharge (by chat, voice, form or bill photo), fills the claim form from documents (or checks the user's own entries live), estimates the payout in rupees, tracks the claim, explains deductions and rejections, drafts appeals up to the Ombudsman, and offers a lender-decided bridge loan.

**AI explains, rules decide.** Every rupee figure comes from a tested rule engine (`backend/app/rules/engine.py`). Sarvam AI reads documents, talks to the user and explains results.

See [PRD.md](PRD.md) for the full product spec.

## Run it

### 1. Backend (laptop)

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
echo "SARVAM_API_KEY=<your key>" > .env
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8787 --reload
```

Check: `curl localhost:8787/health` returns `{"ok":true,"sarvam":true,...}`.
Tests: `.venv/bin/python -m pytest -q tests` (121 tests, offline, no Sarvam key needed).

### 2. App (phone, Expo Go)

1. Turn on the laptop's hotspot (or put phone and laptop on the same Wi-Fi) and connect the phone.
2. On the laptop:
   ```bash
   cd app
   npm install
   npx expo start
   ```
3. Install **Expo Go** from the Play Store and scan the QR code.

The app finds the backend automatically on the same host as the Metro bundler, port 8787. To point it elsewhere: `EXPO_PUBLIC_API_URL=http://<ip>:8787 npx expo start`.

If the phone can't load the bundle on a locked-down network, use `npx expo start --tunnel` and set `EXPO_PUBLIC_API_URL` to a reachable backend URL.

### Reset between demos

```bash
curl -X POST localhost:8787/demo/reset
```

This clears policies and claims so My Policies shows "No policies found" again. Onboarding shows again too.

## Demo script (about 4 minutes)

1. **Paytm home → Health Insurance.** First run shows onboarding (3 screens + DPDP consent).
2. **My Policies is empty**, the gap in today's Paytm app. Tap **Try with a sample claim → Sunita Kulkarni**.
3. **Your cover in plain words**: 5 topics, each with clause and page. Switch language (globe icon on home) to Hindi or Marathi and tap **Listen**.
4. **I'm in hospital** → Chat or speak → say in Hindi: *"मेरी माँ सुनीता भर्ती हैं, सिंगल रूम 7500 रुपये रोज़, पित्ताशय की सर्जरी"*. The check flags the room above the ₹5,000/day limit and the proportionate deduction.
5. Back on the policy → **Start a claim → Sunita → Pay & claim later** → **Use sample documents** → **Continue**. The consent dialog asks **Fill it for me / I'll fill it myself**.
6. Form shows AI-filled fields with their source, live checks (room rent warning, insurer not informed). Try typing a wrong IFSC to see a correction. **Check my payout** shows **₹68,400 of ₹1,10,000** with every deduction and its clause.
7. **Submit** → tracker. Show the **bridge loan** card (Key Facts, cooling-off, lender decides).
8. Tap **Insurer: next step** (demo control) twice → insurer query → reply → next step → **partly approved ₹62,400**.
9. **Explain this decision** (in Hindi, with voice): the rule engine finds **₹6,000 wrongly deducted** on medicines and tests → **Draft letter for me** → Send. The escalation ladder unlocks GRO → Bima Bharosa → Ombudsman (office found by PIN code). Then tap **Insurer: next step** once more: the insurer accepts the appeal and **₹6,000 is reversed** (₹62,400 becomes ₹68,400).
10. **NHCX claim pack**: FHIR R4 ClaimBundle. **Privacy & AI activity** lists everything AI did.

Other samples: **Arjun** (bought on Paytm, clean claim, full payout) and **Rakesh** (knee replacement inside the 24-month waiting period: rejected, honest appeal odds, medical EMI option after the appeal path).

To show a real upload, use `demo-docs/Family_Shield_Plus_policy.pdf` (copy it to the phone), or any public policy wording PDF.

## Architecture

```
Expo React Native app (Expo Go)  ──HTTP──►  FastAPI (laptop :8787)
                                              ├─ rules/engine.py     money math, IRDAI rules, unit-tested
                                              ├─ ai/sarvam.py        sarvam-105b chat, vision, Saaras STT, Bulbul TTS (disk-cached)
                                              ├─ ai/tools.py         parse policy, read documents, hospital chat, explain, draft appeals, assistant
                                              ├─ claims.py           checklist, autofill, live validation, mock insurer, bridge, FHIR
                                              └─ store.py            SQLite + audit log
```

| Real / open | Mocked behind an interface |
|---|---|
| IRDAI non-payable list, proportionate-deduction exemptions, cashless 1 h / discharge 3 h timelines | Paytm login, "Bought on Paytm" policies, UPI, Postpaid |
| Insurance Ombudsman jurisdictions by PIN code | Insurer / TPA claim API, decisions, settlement |
| NRCeS FHIR ClaimBundle profile | NHCX submission, ABHA fetch |
| Sarvam AI (team credits) | Lender decision, human support ticket |

Sample policies, patients and bills are fictional. No real patient data.
