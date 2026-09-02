# Deploying Agent Till

Three free services, no credit card required anywhere. Do them in this order — each step needs
a value produced by the one before it.

Total time: about 25 minutes.

---

## 1. Database — Neon (~4 min)

Neon rather than Render's own Postgres, whose free tier **expires 30 days after creation** and
would take the live demo down a month after the buildathon.

1. Go to **https://neon.com** → **Sign up** → continue with GitHub.
2. Create a project. Name it `agent-till`. Any region (pick one near you).
3. On the project dashboard, find **Connection string** and copy it. It looks like:
   ```
   postgresql://neondb_owner:XXXX@ep-something-123456.ap-southeast-1.aws.neon.tech/neondb?sslmode=require
   ```
4. **Keep this tab open** — you need this string in step 2.

> Make sure you copy the plain connection string, not the "pooled" psql command line.

---

## 2. Backend — Render (~10 min)

1. Go to **https://render.com** → **Get Started** → continue with GitHub.
2. **New +** → **Web Service** → **Build and deploy from a Git repository**.
3. Connect GitHub, find **`SaaGup/agent-till`**, click **Connect**.
4. Fill in the settings:

   | Field | Value |
   |---|---|
   | Name | `agent-till-api` |
   | Language / Runtime | `Python 3` |
   | Branch | `main` |
   | **Root Directory** | `backend` |
   | Build Command | `pip install -r requirements.txt` |
   | Start Command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
   | Instance Type | **Free** |

5. Scroll to **Environment Variables** and add these. Copy them exactly:

   | Key | Value |
   |---|---|
   | `PYTHON_VERSION` | `3.13.7` |
   | `ENVIRONMENT` | `production` |
   | `DATABASE_URL` | *(the Neon string from step 1)* |
   | `RAZORPAY_KEY_ID` | `rzp_test_TXCOeiMR4AKxdd` |
   | `RAZORPAY_KEY_SECRET` | *(from your `backend/.env`)* |
   | `LLM_API_KEY` | *(your Gemini key, from `backend/.env`)* |
   | `LLM_BASE_URL` | `https://generativelanguage.googleapis.com/v1beta/openai/` |
   | `LLM_MODEL` | `gemini-3.5-flash-lite` |
   | `DEMO_KEY` | `sEpeHXlC3kNZ6yKKZFW2rOg0mX2KaYS3` |
   | `JWT_SECRET` | `uC4aopTn_Ve9oandDPym1P-KlxIaE0Odtjs_qB3xV9SZGAfczNg4BYQNodwS_0mR` |
   | `DEMO_MERCHANT_EMAIL` | `merchant@agenttill.dev` |
   | `DEMO_MERCHANT_PASSWORD` | `AgentTill!2026` |
   | `ALLOWED_ORIGIN` | `http://localhost:5173` *(corrected in step 4)* |

6. **Create Web Service**. First build takes 3–5 minutes.
7. When it goes live, copy the URL — something like `https://agent-till-api.onrender.com`.
> The app **refuses to start in production** if `JWT_SECRET` is missing, too short, or left at
> the development value, and likewise if `DEMO_KEY` is still `change-me`. A guessable signing key
> would let anyone mint a merchant session and approve their own orders, so it fails loudly at
> startup rather than serving traffic with the approval gate quietly open. If the deploy dies on
> boot, read the log — it names exactly which variable is wrong.

8. Check it: open `https://<your-render-url>/health`. You want:
   ```json
   {"status":"ok","environment":"production","version":"0.1.0"}
   ```

Migrations run automatically on boot, so the Neon database creates its own tables and seeds the
catalog on that first request.

---

## 3. Frontend — Vercel (~5 min)

1. Go to **https://vercel.com** → **Sign up** → continue with GitHub.
2. **Add New…** → **Project** → import **`SaaGup/agent-till`**.
3. Settings:

   | Field | Value |
   |---|---|
   | Framework Preset | `Vite` |
   | **Root Directory** | `frontend` *(click Edit and select it)* |
   | Build Command | `npm run build` |
   | Output Directory | `dist` |

4. Expand **Environment Variables** and add:

   | Key | Value |
   |---|---|
   | `VITE_API_BASE` | *(your Render URL, e.g. `https://agent-till-api.onrender.com` — no trailing slash)* |

5. **Deploy**. Copy the resulting URL, e.g. `https://agent-till.vercel.app`.

---

## 4. Close the loop — CORS (~2 min)

The backend refuses browser origins it doesn't know, so it needs the Vercel URL.

1. Render → your service → **Environment**.
2. Edit `ALLOWED_ORIGIN` → set it to your Vercel URL exactly, e.g. `https://agent-till.vercel.app`
   (no trailing slash).
3. **Save** — Render redeploys automatically.
4. Open the Vercel URL and send a message. If the chat works, the loop is closed.

---

## 5. Razorpay webhook (~4 min)

This is what makes payment confirmation trustworthy rather than dependent on the browser.

1. Razorpay Dashboard → make sure you are in **Test Mode** → **Account & Settings** → **Webhooks**
   → **Add New Webhook**.
2. Webhook URL: `https://<your-render-url>/webhooks/razorpay`
3. Secret: `8qr9ZbY_xgn7h63qz18vLBV2vNKMYcPa`
4. Select events: **`payment.captured`**, **`order.paid`**, **`payment.failed`**.
5. Save. (If asked for an OTP to confirm, Razorpay's test-mode default is `754081`.)
6. Back in Render → **Environment** → add:

   | Key | Value |
   |---|---|
   | `RAZORPAY_WEBHOOK_SECRET` | `8qr9ZbY_xgn7h63qz18vLBV2vNKMYcPa` |

7. Save and let it redeploy.

---

## Before you demo

- **Warm the backend first.** Render's free tier sleeps after 15 minutes idle and takes about a
  minute to wake. Open `/health` a few minutes before presenting, or your first judge
  interaction stalls on a cold start.
- **Reset demo state** if you've been testing: the stock-conflict SKU can be restocked with
  ```
  curl -X POST https://<your-render-url>/api/demo/restock/shoe-flash-2799 \
    -H "X-Demo-Key: sEpeHXlC3kNZ6yKKZFW2rOg0mX2KaYS3"
  ```
- **Trigger the failure demo** mid-presentation with
  ```
  curl -X POST https://<your-render-url>/api/demo/force-out-of-stock/shoe-flash-2799 \
    -H "X-Demo-Key: sEpeHXlC3kNZ6yKKZFW2rOg0mX2KaYS3"
  ```

## Signing in

The console is behind a merchant sign-in, because approving an order releases money and that
endpoint must not be open to anyone who finds the URL. The demo account is pre-filled on the
login page and published deliberately so judges can get in:

```
merchant@agenttill.dev
AgentTill!2026
```

Change `DEMO_MERCHANT_EMAIL` / `DEMO_MERCHANT_PASSWORD` in Render if you want different
credentials — the account is seeded on first boot only, against an empty users table.

## Security notes

- Every secret above lives only in a dashboard. Nothing sensitive is committed; `.env` is
  gitignored and has never been in the history.
- `DEMO_KEY` guards the endpoints that deliberately break catalog state. Without it a visitor to
  your live URL could zero your stock mid-demo.
- If you ever paste a secret somewhere public, rotate it: Razorpay keys regenerate from the
  dashboard, Gemini keys from AI Studio.
