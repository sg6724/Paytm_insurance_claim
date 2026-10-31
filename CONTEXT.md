# CONTEXT.md: handover for humans and agents

Read this first if you are picking up Claimezy. It covers what exists, why it was built this way, how to run it, and what is left. [PRD.md](PRD.md) has the product spec and [README.md](README.md) has the run steps and the demo script.

Last updated: 31 Oct 2026, finals day.

**Name:** the product was renamed from **Claim-to-Cash** to **Claimezy** on 31 Oct. The repo folder is still `claim-to-cash/` and the database file is still `claim_to_cash.db`; only user-facing names changed.

---

## 1. The project in one paragraph

**Team:** Twisted Minds (Jainam Oswal, Samriddhi Gupta).

**Event:** Paytm Build for India AI Hackathon, Track 2 (AI-Powered Financial Journeys). The grand finals are on 31 Oct 2026 at Paytm, Andheri East, Mumbai. The Top 10 jury pitch is 16:30 to 18:30.

**Idea:** **Claimezy** lives inside Paytm's Health Insurance section. It takes a policyholder from "I'm in hospital" to "money in my account." Paytm today explains claims only *before* purchase. After purchase, "My Policies" just says "No policies found." This app fills that gap. The core principle is **"AI explains, rules decide"**: every rupee figure comes from a deterministic rule engine, and the LLM only reads documents, converses and explains.

## 2. Status

| Area | State |
|---|---|
| PRD | Done (`PRD.md`) |
| Rule engine | Done. 121 backend tests pass: engine, API journeys, mock partners, insurer paths, assistant memory, stay-facts reader (`backend/tests/`) |
| Backend API + mocks + AI | Done, verified live with Sarvam |
| Expo app (about 20 screens) | Done, `tsc` and `expo lint` clean, Android bundle builds |
| Sample documents | Done (`demo-docs/`, served at `/demo-docs/`) |
| Onboarding, How it works, tips | Done. Five-slide onboarding, Help opens `/guide`, one-time tips |
| Audit | Done, see [AUDIT.md](AUDIT.md). Ready to demo, not ready for real customers |
| **On-phone end-to-end test** | **Pending.** Voice recording and the camera are untested on a real device. |
| Git | History rewritten (conventional commits, Samriddhi as co-author) and force-pushed to `sg6724/Paytm_insurance_claim` main on 31 Oct. |

**Live tracker:** https://claude.ai/artifact/3N5B3odjQdrRh2vAA4zC4R. It is a Claude artifact backed by a db: collection `phases` (docs `p0` to `p8`) and doc `meta/status` (headline plus log). Update it with the ArtifactData tool, pinning `if_version`.

## 3. Decisions already made (do not reopen without the user)

- **Platform.** Android phone only, through **Expo Go** (no web backup). The backend runs on the **laptop**, and the phone joins the same Wi-Fi or the laptop's hotspot.
- **AI.** **Sarvam only** (the team has credits). Everything else must be **free, open or publicly accessible**. Paytm, UPI, Postpaid, lender, insurer, NHCX and ABHA are **mocked** behind swappable interfaces.
- **Languages.** All Sarvam languages: 23 for text, and voice output for the 11 that Bulbul supports.
- **Scope cuts.**
  - **Caregiver mode was removed.** The user's reasoning: anyone can fill the form for anyone, and children usually buy the policy themselves.
  - Product recommendation and selling are out of scope.
  - Motor and life insurance are out of scope.
- **Hospital-stay check.** A bill is **optional**. The user can talk to the agent by chat or voice, use a quick form, or add a bill photo.
- **Claim form.**
  - After documents are uploaded, a **consent popup** asks "Fill it for me / I'll fill it myself."
  - The **manual mode gets live corrections** with Fix / Keep mine. The user can switch modes at any time.
  - If no documents were uploaded, the form opens in manual mode directly.
- **Loans.** Trigger them at the reimbursement wait (a bridge repaid from the settlement) and at a discharge shortfall (UPI or EMI). On rejection, show the **appeal path first** and a medical EMI only after that. Show the key-facts statement and cooling-off period, and make clear the lender decides (RBI Digital Lending Directions).
- **Real names.** Real bank and hospital names on the sample documents are fine; the user asked for realism. Keep the "Synthetic sample for demo" footer on every page.
- **Writing style for anything the team presents.**
  - Human readable.
  - **No em dashes.**
  - No "illustrative" labels; use real, sourced numbers.
- **Git.**
  - Conventional commit messages, human readable.
  - Every commit carries `Co-authored-by: Samriddhi Gupta <151558855+sg6724@users.noreply.github.com>`.
  - **No Claude or AI attribution lines.**
  - Commit and push only when asked. Never force-push without the user's explicit go-ahead; the permission classifier blocks it, so the user runs it.

## 4. Repository map

```
claim-to-cash/
├── PRD.md                    product spec (features F1-F11, flows, screens, phases)
├── README.md                 run steps + demo script
├── CONTEXT.md                this file
├── AUDIT.md                  pre-production audit: what was tested, found, fixed and is still open
├── demo-docs/                generated sample PDFs/JPGs + index.html (served at /demo-docs/)
├── backend/                  FastAPI, Python 3.14, venv in backend/.venv
│   ├── .env                  SARVAM_API_KEY=... (gitignored, never commit)
│   ├── app/
│   │   ├── main.py           all HTTP routes (single file)
│   │   ├── config.py         env, paths, Sarvam model names, LANGUAGES list, BANK_RATE
│   │   ├── store.py          SQLite doc store: put/get/find/delete/wipe + audit()
│   │   ├── claims.py         checklist, autofill, validate (live corrections), preflight,
│   │   │                     mock insurer (submit/advance/respond/decide/letter),
│   │   │                     analyse_decision, ladder, bridge_offer, fhir_bundle, deadlines
│   │   ├── rules/engine.py   compute(), hospital_check(), deadlines(): ALL money math
│   │   ├── rules/non_payables.py  IRDAI non-payable list (word-boundary matching)
│   │   ├── ai/sarvam.py      chat (v1, json mode + retry), vision (v2, gemma4), stt, tts, translate; disk cache
│   │   ├── ai/stay_facts.py  reads room, rent, procedure and patient from what the user says (Hindi, Marathi, English); fills gaps the LLM leaves
│   │   ├── formpdf.py        claim form as a PDF
│   │   ├── assistant_memory.py  one saved chat thread per claim/policy; last 16 messages + rolling summary; return-visit detection
│   │   ├── ai/tools.py       parse_policy, extract_document, explainer_template/localise,
│   │   │                     hospital_chat, summarise_check, explain_decision, draft_appeal,
│   │   │                     assistant, summarise_conversation, recap_conversation, describe_attachment
│   │   └── data/             samples.py (2 policies, 3 claims), ombudsman.py (PIN → office), ai_cache/
│   ├── scripts/make_demo_docs.py   regenerates demo-docs/
│   └── tests/            test_engine, test_api, test_mocks, test_memory, test_stay_facts (conftest runs offline)
└── app/                      Expo SDK 58, React Native 0.88, expo-router, TypeScript, React Compiler on
    └── src/
        ├── lib/api.ts        API_BASE auto-detect (Metro host:8787 or EXPO_PUBLIC_API_URL), get/send/upload, ttsUrl, rupees
        ├── lib/app-context.tsx  language + UI translation (POST /i18n), assistant screen context, online flag
        ├── lib/strings.ts    English UI strings (translated at runtime)
        ├── lib/theme.ts      Paytm colours (navy #002E6E, sky #00BAF2)
        ├── ui/kit.tsx        Header, Screen, Card, Row, Btn, Pill, Field, Sheet, Money, useAsync…
        ├── ui/voice.tsx      MicButton (expo-audio record → /assistant/stt), ListenButton (TTS URL)
        ├── ui/tip.tsx        one-time hint per screen (seen ids saved on the profile)
        ├── ui/assistant-avatar.tsx  assistant image used on the Ask button and chat
        ├── lib/guide.ts      the 4-step journey text shared by onboarding and /guide
        └── app/              routes (see section 6)
```

## 5. Architecture and key behaviours

```
Expo Go app ──HTTP──► FastAPI :8787 (laptop)
                        ├─ rules/engine.py   (deterministic; tested)
                        ├─ ai/* → Sarvam     (sarvam-105b chat, gemma4 vision on /v2, saaras:v3 STT, bulbul:v4-flash TTS)
                        ├─ claims.py         (workflow + mock insurer/lender/NHCX)
                        └─ store.py SQLite   (backend/storage/claim_to_cash.db, gitignored)
```

### Rule engine (`compute`)

The steps run in this order:
1. Policy in force.
2. Waiting periods and exclusions, matched on diagnosis plus procedure, in English keywords.
3. IRDAI non-payables (skipped for List I when `consumables_cover` is set).
4. Room-rent cap with proportionate deduction. This applies to the room, nursing, doctor, OT, anaesthesia, procedure and misc heads. It does **not** apply to pharmacy, consumables, implants or diagnostics.
5. ICU cap.
6. Sub-limits.
7. Deductible.
8. Co-pay.
9. Remaining sum insured.

### Demo numbers (tests lock these)

| Claim | Result |
|---|---|
| **Sunita**, gallbladder surgery, ₹7,500/day room vs a ₹5,000 cap | **₹68,400 of ₹1,10,000** |
| **Arjun**, dengue, policy bought on Paytm | ₹62,000 of ₹62,000 |
| **Rakesh**, knee replacement | Rejected: specific-disease waiting period, Clause C4.3 |

### Mock insurer

`POST /claims/{id}/advance` moves the claim through submitted → under review → query (only for `over_deduct`) → decision → settled.

For Sunita, the insurer behaviour is `over_deduct`. It also cuts pharmacy and diagnostics proportionately, which is wrong, so it approves **₹62,400**. `analyse_decision` then finds **₹6,000 wrongly deducted**, rates the appeal as **strong**, and the ladder unlocks step by step: insurer, then GRO, then Bima Bharosa, then the Ombudsman.

After an appeal is sent, the next `advance` makes the mock insurer answer it from the rule engine: Sunita's ₹6,000 is reversed (₹62,400 becomes ₹68,400, topped up once if already settled) and the ladder closes; Rakesh's rejection stands and can still escalate.

### Bridge loan (mock lender)

- **Offer:** 80% of the expected payout, 30 days, 16% APR, 1% fee plus GST, 3-day cooling-off. These are demo values.
- **Repayment:** automatic when the claim is settled. If the insurer pays less than is owed, the loan is part-repaid and the rest is due in EMIs.
- **Consent:** `POST /bridge/accept` must carry `{"consent": true}`; the API refuses without it.

### The rest

| Feature | Behaviour |
|---|---|
| Hospital chat | The LLM pulls out facts as JSON. The backend forces `ready=true` once it has the member, room rent or category, and the diagnosis or procedure, then runs `hospital_check`. |
| Live corrections | `claims.validate()` is deterministic: format checks, cross-checks against extracted documents and the policy, and risk hints. The app calls it debounced by 450 ms. |
| Audit log | Every AI action, consent and submission goes through `store.audit()` and shows on the app's "Privacy & AI activity" screen. |
| TTS | `GET /assistant/tts.wav?text=&lang=` returns a wav. The app splits text into sentence chunks (`speechChunks`), plays the first as soon as it is ready and prefetches the rest, so speech starts in about 2 s. Replies to spoken questions are read out automatically. |
| UI translation | `POST /i18n` translates the `EN` strings dictionary once per language, cached on disk. |
| Hospital chat fallback | `ai/stay_facts.py` reads room, rent, illness and patient from the user's own words (English, Hindi, Marathi) and fills only what the LLM missed. The stay check works even if Sarvam is down. |
| Human review | Documents read under 60% confidence, poor policy reads (6+ uncertain fields) and decisions the rules can't explain open a mock review ticket. |
| Assistant memory | One thread per claim (or policy, or general). The model gets the last 16 messages plus a rolling summary. Screenshot text is saved with its message, so follow-ups still see it. `previous_session_ended` is sent only after a 30-minute gap. |
| Assistant recap | `GET /assistant/thread` returns at once with no AI call; if the cached recap is stale it sets `recap_pending` and the app fetches `GET /assistant/thread/recap`. The "Next:" line comes from `claims.next_step()`, not the AI. |
| Cover used | Settling a claim lowers the policy's `remaining_si`; deleting a settled claim gives it back. |
| Disk cache | `backend/app/data/ai_cache/` stores responses by input hash. Most prompts include dates or IDs, so the cache rarely hits on new runs. The network is effectively required. |

## 6. App routes (`app/src/app/`)

| Route | Purpose |
|---|---|
| `index` | Paytm-style home. The Health Insurance tile leads to `/insurance`; the globe icon opens the language picker. |
| `insurance` | Insurance landing. Redirects to `onboarding` until the profile has `onboarded=true`. |
| `onboarding` | 5 slides: what it does, the 4 steps, what to keep ready, AI vs rules, consent. Ends with "Try a sample claim" or "Add my own policy" |
| `guide` | How it works: the 4 steps with a button each. Opened by Help in the header |
| `settings` | Language picker (23 languages) |
| `trust` | Consent toggles, AI activity log, delete data |
| `samples` | Guided sample claims (Sunita, Arjun, Rakesh) |
| `policies/index` | My Policies, including the empty state. `?next=hospital` sends the user to the hospital check instead. |
| `policies/add` | Bought on Paytm, PDF/photo upload, or fetch by number |
| `policies/[id]` | "Your cover in plain words", clause sheet, start claim. `?sample=key` preselects a sample. |
| `hospital/[policyId]` | Cashless or reimbursement; chat/voice, form or bill photo; result |
| `claims/index` | Claims list |
| `claims/[id]/documents` | Upload, ABHA fetch (mock), checklist, sample documents, fill-mode consent popup |
| `claims/[id]/form` | AI or manual form with live corrections |
| `claims/[id]/preflight` | Payout estimate, export form as PDF, submit |
| `claims/[id]/index` | Tracker, tasks, decision card, bridge card, NHCX link, "Insurer: next step" demo control |
| `claims/[id]/decision` | Explanation with voice, appeal strength, escalation ladder, draft editor |
| `claims/[id]/bridge` | Key Facts Statement and accept |
| `claims/[id]/fhir` | FHIR bundle viewer |
| `pay` | Mock UPI |
| `assistant` | Modal chat: text, mic (stops on a pause, replies read out), photo or PDF sharing, talk to a human. Opened by the draggable Ask button, which snaps to the nearest side |

## 7. How to run

```bash
# backend (from claim-to-cash/backend)
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8787 --reload
curl localhost:8787/health          # {"ok":true,"sarvam":true}
.venv/bin/python -m pytest -q tests
curl -X POST localhost:8787/demo/reset   # empty My Policies + onboarding again

# app (from claim-to-cash/app)
npx expo start --lan                 # phone: Expo Go → exp://<laptop-ip>:8081
npx tsc --noEmit && npx expo lint    # must be clean before declaring done

# sample docs
backend/.venv/bin/python backend/scripts/make_demo_docs.py   # phone: http://<laptop-ip>:8787/demo-docs/
```

On 31 Oct the laptop's Wi-Fi IP was `10.50.123.136`. If the phone switches to the laptop hotspot, the IP changes: restart Expo, optionally with `EXPO_PUBLIC_API_URL=http://<new-ip>:8787`.

## 8. API surface (main routes)

**Meta and trust**
- `GET /health`
- `GET /languages`
- `GET` and `PATCH /profile`
- `POST /i18n`
- `GET` and `POST /consents`
- `POST /consents/all`
- `GET /audit`
- `DELETE /me/data`
- `POST /demo/reset`

**Policies**
- `GET /policies`
- `GET /policies/paytm`
- `POST /policies/paytm/{pid}`
- `POST /policies/fetch`
- `POST /policies/upload` (multipart)
- `GET`, `PATCH` and `DELETE /policies/{pid}`
- `GET /policies/{pid}/explainer?lang=`

**Hospital**
- `POST /hospital/check`
- `POST /hospital/chat`
- `POST /hospital/bill` (multipart)

**Claims**
- `POST` and `GET /claims`
- `GET` and `DELETE /claims/{cid}`
- `POST /claims/{cid}/documents` (multipart)
- `PATCH` and `DELETE /documents/{did}`
- `POST /claims/{cid}/fill-mode {mode: ai|manual}`
- `POST /claims/{cid}/validate`
- `POST /claims/{cid}/preflight`
- `POST /claims/{cid}/submit`
- `POST /claims/{cid}/advance`
- `POST /claims/{cid}/tasks/{tid}`
- `POST /claims/{cid}/intimate`
- `GET /claims/{cid}/decision?lang=`
- `POST /claims/{cid}/appeal/draft`
- `POST /claims/{cid}/appeal/send`
- `POST /claims/{cid}/appeal/dismiss`
- `GET /ombudsman?pincode=`
- `GET /claims/{cid}/fhir`
- `GET /claims/{cid}/form.pdf`
- `GET /claims/{cid}/bridge`
- `POST /claims/{cid}/bridge/accept` (body `{"consent": true}`)

**Mock partners and assistant**
- `POST /mock/upi/pay`
- `POST /mock/abha/fetch/{cid}`
- `POST /assistant/chat` (body: `message`, optional `attachment`; history comes from the saved thread)
- `GET` and `DELETE /assistant/thread`
- `GET /assistant/thread/recap`
- `POST /assistant/attach` (photo, screenshot or PDF; scanned PDFs are read page by page with vision)
- `POST /assistant/stt`
- `POST /assistant/tts`
- `GET /assistant/tts.wav`
- `POST /support/ticket`

**Samples**
- `GET /samples`
- `POST /samples/{key}/policy`
- `POST /samples/{key}/documents/{cid}`

## 9. Gotchas learned the hard way

- **Port 8000 is taken** on this laptop by another app ("LocalLens"). The backend uses **8787**.
- **Shell.** The interactive shell is **zsh**: unquoted `$VAR` holding several words does not word-split. Use `bash <<'EOF'` for scripts that rely on splitting.
- **Sarvam API.**
  - The auth header is `api-subscription-key`.
  - Chat runs `sarvam-105b` on `/v1/chat/completions`, with `reasoning_effort: null` for speed and `response_format: json_object` in JSON mode. It occasionally returns non-JSON; the client retries once.
  - Vision goes through `/v2/chat/completions` with model `gemma4` and an OpenAI-style `image_url` data URI.
  - STT: `/speech-to-text`, multipart, `model=saaras:v3`, maximum 30 seconds per synchronous call.
  - TTS: `/text-to-speech`, `bulbul:v4-flash` with one persona per language (`config.SARVAM_TTS_VOICES`, e.g. `simran_en_customer`, `simran_enhi_customer`, `ritu_mr_insurance`). Malayalam and Odia have no v4 persona yet and stay on `bulbul:v3` / `priya`. v4 rejects v3 names like `priya` with a 400. `enable_preprocessing` is on; ₹ amounts become the local word (ரூபாய், రూపాయలు, টাকা, രൂപ) because Bulbul reads ₹ as English "rupees" in those languages. Pitch/loudness are accepted but left at default. It returns base64 in `audios[0]`; the client handles both base64 and raw bytes.
- **Expo SDK 58 and React Native 0.88.**
  - `expo/fetch` is the global `fetch` and rejects React Native's `{ uri, name, type }` FormData parts ("Unsupported FormDataPart implementation"). All uploads go through `upload()` in `lib/api.ts`, which uses `new File(uri).upload(...)` from `expo-file-system` with `UploadType.MULTIPART`.
  - Don't start Metro with `EXPO_PUBLIC_API_URL` set to a LAN IP: the laptop's IP changes between networks. Without it the app calls the backend on the same host it loaded from.
  - `ScrollView` refs need `useRef<any>`.
  - The React Compiler's lint forbids synchronous `setState` in effects and reading refs during render. `useAsync` in `kit.tsx` is written around both.
  - Always check the versioned docs (`app/AGENTS.md`).
- **Browser automation** of the Expo web build was flaky: the window size stuck and the renderer froze. Verify through the API or on the phone instead.
- **Hospital chat.** The LLM must output diagnosis and procedure in **English** for the waiting-period keyword match. This is enforced in the prompt.
- **Uvicorn** runs with `--reload`, so backend edits apply live. Metro started with `CI=1` does **not** watch files.

## 10. Open items / next steps

1. ~~Force-push the rewritten history~~ Done on 31 Oct. Anyone with an older clone should run `git fetch && git reset --hard origin/main`.
2. **On-phone run** of the full demo script in README.md. Watch for:
   - mic permission and m4a upload to STT;
   - camera and document picker uploads (multipart from Expo Go);
   - TTS playback from the URL;
   - keyboard overlap on the chat screens.
3. If the venue Wi-Fi blocks phone-to-laptop traffic, use the laptop hotspot (the IP changes), or `npx expo start --tunnel` plus a reachable backend URL.
4. **Nice to have, not started:**
   - insurer/TPA web console;
   - analytics on money recovered;
   - real ABHA or NHCX sandbox (signup approval takes about a week);
   - caching sample AI responses for offline use (needs stable prompts without dates or IDs).
5. **Facts to verify before quoting them on stage:**
   - the reimbursement settlement timeline (we use 30 days after the last document) and the interest rule (bank rate plus 2%, PPI Regulations 2017);
   - the Ombudsman 1-year window;
   - Ombudsman email addresses (pattern `bimalokpal.<city>@cioins.co.in`, not checked one by one);
   - `BANK_RATE=5.75` in `config.py`, which is a placeholder.

## 11. Pitch facts used so far (sourced in the Stage 1 deck)

- **IRDAI FY25:** 3.26 crore health claims, about 8% repudiated.
- **FY24:** ₹26,038 cr rejected or disallowed.
- **Reimbursement experience:** 20 to 46 days to settle and 13 to 26% deducted (SecureNow study).
- **Policybazaar Health Claims Index 2026:** 3 in 4 reimbursement claimants borrowed; 73% got no clear reason for a deduction.
- **Paytm reach:** about 8 crore monthly transacting users; Paytm Insurance has 18+ partners.
- **Business model:**
  - Paytm Insurance Broking is licensed to offer claims assistance.
  - Revenue comes from claims-assist fees to insurers and TPAs, plus lender referral fees.
  - Pitch formula: 1% × 3.26 crore claims × ₹200 = ₹6.5 cr.

The Stage 1 deck files are one folder up: `../Claim-to-Cash - Twisted Minds.pptx` (made before the rename) and `.pdf`.
