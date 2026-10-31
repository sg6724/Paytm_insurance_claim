# Claimezy

Health insurance claims assistant built for the Paytm Build for India AI Hackathon, Track 2. Team Twisted Minds: Jainam Oswal and Samriddhi Gupta.

Paytm explains insurance claims before you buy a policy, but offers little help once you need to claim. Claimezy covers that gap, from hospital admission to the money reaching your account:

- Explains your policy in plain language, in Indian languages, by text or voice
- Checks your hospital stay before discharge and shows likely deductions
- Reads your bills and fills the claim form, or checks the form as you fill it in
- Estimates your payout, line by line
- Tracks the claim, explains the insurer's decision, and drafts appeals
- Offers a bridge loan from a lending partner while you wait

Payout amounts come from a rule engine with unit tests (`backend/app/rules/engine.py`). The AI reads documents and explains results, but it does not calculate payouts.

## Try it

[Download the Android APK](https://github.com/sg6724/Paytm_insurance_claim/releases/latest/download/Claimezy.apk)

1. Install it. You may need to allow installs from your browser.
2. Tap **New here? Create an account**.
3. Scroll down to **Financial Services** and tap **Health Insurance**.
4. Go through the intro, then tap **Try a sample claim**.

The app uses the live backend at https://claimezy-backend.vercel.app, so it only needs an internet connection.

| Sample claim | Case | Result |
|---|---|---|
| Sunita | Gallbladder surgery, room above the policy limit | ₹68,400 of ₹1,10,000 |
| Arjun | Dengue, clean claim | ₹62,000 of ₹62,000 |
| Rakesh | Knee replacement inside the waiting period | Rejected, Clause C4.3 |

Sample policies and bills to upload are in [demo-docs](demo-docs/).

## Run it locally

Backend:

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
cp .env.example .env   # then add your keys
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8787
.venv/bin/python -m pytest -q tests
```

App, using Expo Go on a phone on the same network:

```bash
cd app
npm install
npx expo start
```

## Environment variables

| Name | Needed for |
|---|---|
| `SARVAM_API_KEY` | AI features |
| `DATABASE_URL` | Postgres. Without it, the backend uses local SQLite |
| `RESEND_API_KEY` | Password reset emails |

## How it's built

| Part | Technology |
|---|---|
| App | Expo, React Native, TypeScript |
| Backend | FastAPI on Vercel |
| Database | Postgres on Neon |
| AI | Sarvam: chat, document reading, speech-to-text, text-to-speech |
| Email | Resend |

| Folder | Contents |
|---|---|
| `app/` | Android app |
| `backend/app/rules/` | Rule engine and IRDAI non-payable list |
| `backend/app/ai/` | Sarvam client and AI tools |
| `backend/app/claims.py` | Claim workflow and mock insurer |
| `backend/tests/` | Backend tests |
| `demo-docs/` | Synthetic sample documents |

## What is real and what is mocked

| Real | Mocked |
|---|---|
| Sarvam AI | Paytm login and policies bought on Paytm |
| IRDAI non-payable list and claim timelines | Insurer and TPA |
| Insurance Ombudsman offices by PIN code | NHCX submission and ABHA |
| FHIR R4 claim pack format | UPI, lender and human support |

All sample policies, patients and bills are fictional. No real patient data is used.

## Known limits

- This is a hackathon build, not a production service. No real claim or payment is processed.
- Reset emails currently reach only the Resend account owner, until a sending domain is verified.
- File uploads are limited to about 4 MB by the hosting platform.
