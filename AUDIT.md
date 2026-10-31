# Pre-production audit

Audit date: 31 Oct 2026, finals day. Scope: the backend, the Expo app and the user journeys in [PRD.md](PRD.md).

**Verdict: ready to demo on stage, not ready for real customers.** Every journey in the PRD works end to end in tests, and the AI paths work against live Sarvam. Nothing has been run on a phone yet, and several partner systems are mocks by design. The sections below say exactly what was checked, what was found, and what is still open.

## 1. What was run

| Check | Result |
|---|---|
| Backend unit and API tests (`pytest`) | **96 pass**, about 15 seconds, no network and no Sarvam key needed |
| Live Sarvam run, 21 checks against real documents and real AI | **21 pass**, 2 slower than the 15 second target (see finding O2) |
| Live Sarvam run of assistant memory | Saved, recapped in English and Hindi, continued correctly (see finding O7) |
| Mock partners side by side across the three claims | **Pass after fixes** (see section 7) |
| TypeScript (`tsc --noEmit`) | Clean |
| Lint (`expo lint`) | Clean |
| Android bundle (`expo export --platform android`) | Builds |
| On a real phone (mic, camera, file picker, audio playback, keyboard) | **Not run** |
| Look of the new screens (avatar, onboarding, guide, tips) | **Not looked at on a device or emulator** |

### Journeys covered by the first 43 tests

- First run: empty My Policies, not onboarded, consent given and withdrawn, delete my data (leaves one audit record).
- Policy: bought on Paytm, the five-topic explainer, a junk upload is rejected cleanly.
- Hospital stay check by form, with and without a limit breach. By chat, with the AI up and with it unreachable.
- **Sunita** (room above the limit): AI-filled form, every field has a source, pre-flight pays **₹68,400 of ₹1,10,000**, intimation, submit, bridge offer with all Key Facts fields, insurer query and reply, partial approval of ₹62,400, **₹6,000 found wrongly deducted**, appeal strength "strong", the escalation ladder unlocks one step at a time, audit trail.
- **Arjun** (clean claim): paid in full, risk low.
- **Rakesh** (knee replacement inside the waiting period): rejected with Clause C4.3, appeal strength "weak", no loan offer until the appeal is dismissed, then a medical EMI.
- Manual form with live corrections (bad IFSC, bad mobile, discharge before admission). Submit blocked until the form is valid.
- Bridge loan: refused without consent, one loan per claim, repaid from the settlement.
- Claim form PDF export, NHCX FHIR bundle, ABHA fetch (clinical records only, repeat is harmless), Ombudsman office by PIN code, human handoff ticket, mock UPI, first-visit tips saved and reset.
- Human review: an unreadable document opens a ticket, confident sample documents do not.

### What the live Sarvam run proved

Real PDFs and photos from `demo-docs/` were read correctly: bill, discharge summary, cancelled cheque (vision), pharmacy bill (vision). The AI-filled form matched the documents (19 fields, IFSC and total correct). The pre-flight on the AI-read bill gave the same ₹68,400. Hindi and Marathi explainers, the Hindi decision explanation, all four appeal letters, the claim-aware assistant, UI translation, a rejection-letter screenshot, and a **Hindi text-to-speech to speech-to-text round trip that returned the exact sentence** all worked.

## 2. Findings fixed during this audit

| # | Severity | Finding | Fix |
|---|---|---|---|
| F1 | **High** | The Hindi demo line ("मेरी माँ सुनीता भर्ती हैं, सिंगल रूम 7500 रुपये रोज़, पित्ताशय की सर्जरी") returned no facts, the stay check never ran, and the assistant asked for a "member ID" and a `YYYY-MM-DD` date. English and Marathi missed the procedure. This is step 3 of the demo. | A deterministic reader of the patient's own words (`ai/stay_facts.py`) fills gaps the model leaves, including a sound-based match of Devanagari names. The prompt no longer lets the model mention ids or date formats. Verified live in Hindi, English and Marathi. |
| F2 | **High** | The stay chat returned a 502 whenever Sarvam was unreachable, so a bad venue network would kill the demo's key step. | It now falls back to the same reader, runs the check and answers from the rule engine's own summary. Two tests cover it. |
| F3 | **High** | `POST /bridge/accept` took no body and recorded the lender consent unconditionally. The app showed a checkbox, but the server never checked it. It also allowed a second loan on the same claim. | The server now requires `consent: true` (422 otherwise) and refuses a second loan (409). The app sends the checkbox value. |
| F4 | Medium | AI-drafted appeal letters began with `[Your Name] [Your Address] [Your Contact Number]`. | The prompt now receives the profile's contact details and today's date and must not leave placeholders. All four letters re-checked live: none left. |
| F5 | Medium | Human review would have fired on almost every policy upload (a clean read leaves about 5 uncertain fields). | Threshold raised to 6 uncertain fields, and a missing sum insured always triggers it. |
| F6 | Medium | PRD items missing: claim form PDF export, low-confidence routing to a human, ABHA fetch (the tile only showed "demo stub"), first-visit tips. | Built, tested, and wired into the app. |
| F7 | Medium | First-run experience: onboarding did not explain how to use the feature, and several buttons led to the same page. | New five-step onboarding, a How it works screen behind Help, and the duplicates removed. Details in section 4. |

## 3. Open findings

| # | Severity | Finding | Recommendation |
|---|---|---|---|
| O1 | **High for the demo** | **Nothing has been tested on a phone.** Mic recording and m4a upload to speech-to-text, camera and file-picker uploads, TTS playback from a URL, and keyboard overlap on the chat screens all depend on the device. The new avatar, onboarding, guide and tip screens have not been looked at. | Run the README demo script once on the actual phone and network before the pitch. |
| O2 | Medium | Reading a policy PDF takes **17 seconds** live, against the PRD's 15 second target. The app shows a progress label while it waits. Document reads take 2 to 9 seconds, chat 2 to 5 seconds. | Acceptable on stage with the progress label. Use the sample policies for the live demo and upload a PDF only if asked. |
| O3 | Medium | The AI cache almost never hits, because prompts include dates and ids. The PRD's "works offline-ish" is only partly met. | The hospital stay chat now works without the network. Explainers and decisions fall back to templates, but in English only. |
| O4 | Low | Asked "tell me exactly how many rupees my insurer will pay", the assistant gave no number but offered to "calculate" one once it had details. | Reword the guardrail so it points the user to the pre-flight estimate. |
| O5 | Low | Language coverage beyond Hindi and Marathi (22 languages) was not checked one by one. Text-to-speech covers 11. | Pick the demo language and rehearse it. |
| O7 | Medium | The AI-written recap can misstate details. Live, it called a 66.7% payout a "66.7% deduction" and named the GRO as the next stop. The rule-based Next line under it was correct (insurer first, ₹6,000). | Treat the recap as AI text. Tighten it so it quotes no percentages. |
| O8 | Medium | The mock insurer never answers an appeal. A sent letter is logged and unlocks the next step, but ₹6,000 is never paid back, so the story stops there. | Add a mock reply if the demo needs a win at the end. |
| O9 | Low | The Next line in the recap is English only, and the app has not been run with saved chats on a device. | Translate it through the existing UI translation. |
| O6 | Info | Facts still to confirm before quoting them on stage (from `CONTEXT.md`): the 30-day settlement timeline and interest rule, the Ombudsman one-year window and office email addresses, and `BANK_RATE=5.75`, which is a placeholder. | Check each against its source. |

## 4. UX changes made (first-run and redundancy)

- **Onboarding** is now five slides: what it is, the four steps, what to keep ready, how AI and rules split the work, consent. It ends with two clear choices: **Try a sample claim** or **Add my own policy**. Skip jumps to the consent slide, because consent is required.
- **Help** (top right on every screen) opens **How it works**, with the same four steps and a button to start each. It used to open the assistant, which already has its own floating button.
- **One-time tips** on the policy, hospital, documents, form and tracker screens. Dismissal is saved, and cleared by Reset demo.
- **Removed duplicates:**
  - Home had a promo card and a Health Insurance tile that both opened the same page. Only the tile remains.
  - Four "Know before you claim" rows all opened the same list. Removed, because the policy screen already explains those topics.
  - A language row repeated the globe on home and the link on the policy screen.
  - "Try a sample" appeared in several places. It now appears on the first-run card, the empty policies screen and the end of onboarding, with no repeat on the insurance page.
  - Extra links to the assistant and to a human inside the tracker and decision screens. The floating assistant has both.
  - **I'm in hospital** now skips the policy picker when there is only one policy.

## 5. Not production-ready by design

These are not bugs for a hackathon demo. They stop this from serving real customers.

- **No login or per-user data.** There is one profile, and every endpoint is open. The upload folder is served without authentication, and CORS allows any origin.
- **Mocked partners:** insurer or TPA, UPI, lender (it always approves), NHCX, ABHA, and the human support desk.
- **Storage:** a single SQLite file with a global lock, and uploaded files on local disk. There is no retention policy.
- **The consent flow is a demo of the DPDP requirements, not a legal review.** Lender terms (APR, fee, cooling-off) are demo values.
- **No monitoring, rate limiting or backups.** The Sarvam key lives in `backend/.env`, which is gitignored and was not committed.

## 6. Test inventory

- `backend/tests/test_engine.py`: 7 tests on the rule engine and the money numbers.
- `backend/tests/test_api.py`: 26 end-to-end journeys through the HTTP API.
- `backend/tests/test_stay_facts.py`: 10 tests on reading Hindi, Marathi and English stay descriptions.
- `backend/tests/test_mocks.py`: 41 tests running every mock partner across the three claims, plus misuse.
- `backend/tests/test_memory.py`: 12 tests on saved conversations, with the model stubbed.
- Run them with `cd backend && .venv/bin/python -m pytest -q tests`. They set their own temporary database and do not touch your data.

## 7. Mock partners, side by side

| Mock | Sunita (over-deducting insurer) | Arjun (fair insurer) | Rakesh (waiting period) |
|---|---|---|---|
| Insurer review | Under review | Under review | Under review |
| Insurer query | Pharmacy bills, ₹12,500, answered | None | None |
| Decision | Partial, ₹62,400 of ₹1,10,000 | Approved, ₹62,000 of ₹62,000 | Rejected, ₹0 of ₹2,76,000 |
| Letter | Claim Settlement (Partial) | Claim Settlement | Repudiation of Claim |
| Settlement | Paid | Paid | None |
| Sum insured after | ₹4,37,600 of ₹5,00,000 | ₹9,38,000 of ₹10,00,000 | Unchanged |
| NHCX bundle | Complete, references resolve | Complete, references resolve | Complete, references resolve |
| Lender offer | ₹55,000 | ₹50,000 | None (₹0 expected) |
| Loan repaid from settlement | Yes | Yes | Not applicable |
| UPI and support | Both attach to the claim | Both attach to the claim | Both attach to the claim |

Paytm policies: listed, added once, and an unknown id gives 404. Fetch by policy number works.

### Bugs this found, all fixed

| Severity | Bug | Now |
|---|---|---|
| **High** | The sum insured never went down after settlement, so a second claim saw full cover | Reduced at settlement, and only once |
| **High** | The timeline said the full settlement reached the bank even when a bridge loan was repaid from it | Shows the amount paid, the loan closed and the net credited. A smaller settlement leaves a balance due |
| **High** | Replying to a task that does not exist moved a draft to under review | 404, status unchanged |
| **High** | A settled claim could be submitted again | 409 |
| Medium | Every rejection letter cited the specific-disease clause, whatever the real reason | States the real reason and clause |
| Medium | The escalation ladder was only enforced in the app, so a user could skip to the Ombudsman | Enforced on the server |
| Medium | An unknown appeal step crashed the server, and an appeal could be drafted with no decision | 422 and 409 |
| Medium | UPI accepted zero and negative amounts | 422 |
| Low | The insurer query hardcoded ₹12,500 | Uses the bill's pharmacy total |
| Low | UPI and support accepted unknown claims, and NHCX exported an empty claim | 404 and 409 |

## 8. Assistant memory

The assistant now keeps one thread per claim or policy between visits. Coming back shows a Where we left off card with the date, an AI recap in the chosen language, and a Next line taken from the claim's state by rules, with Continue and Start fresh. Older messages are folded into a rolling summary, so long chats stay within the prompt limit. A failed answer saves nothing. Clear chat, deleting a claim and Delete my data all remove it.
