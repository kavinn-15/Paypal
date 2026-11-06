# Cashflow Lifeline: 3-Minute Hackathon Demo Script

**PayPal AI Hackathon ("Build What's Next with PayPal and AI")**
**Target Duration:** 2 minutes 45 seconds (Buffer: 15s)

---

## Preparation (Before Recording)
1. Run `make demo-reset` (or `python -m backend.scripts.seed --clean --demo-mode`).
2. Start backend: `uvicorn backend.app.main:app --port 8000`.
3. Start frontend: `cd frontend && npm run dev`.
4. Open browser to `http://localhost:5173`.

---

## Timed Demo Walkthrough

### Act I: The Hook & The Illusion of Health (0:00 - 0:30)

| Timestamp | Visual Action on Screen | Voiceover Script |
|---|---|---|
| **0:00 - 0:15** | Open Dashboard. Show the top stats: Current Balance **\$1,800.00**. | *"Freelancers are profitable on paper and still run out of cash. Meet Alex Morgan. Her PayPal balance looks healthy at \$1,800 today. She has over \$4,500 in open client invoices, and one crucial obligation: paying her lead contractor, Marcus Sterling, \$3,200 this coming Friday."* |
| **0:15 - 0:30** | Hover over the red At-Risk Obligation Banner. | *"To standard accounting apps, everything looks fine. But Cashflow Lifeline reveals the truth: on Friday, Alex will be **short by \$1,400**. Why? Because client payment dates don't match paper due dates."* |

---

### Act II: Explaining the Shortfall Drivers (0:30 - 1:00)

| Timestamp | Visual Action on Screen | Voiceover Script |
|---|---|---|
| **0:30 - 0:45** | Scroll to the Forecast Chart. Show the red balance line dipping to -\$1,400 on Friday. Toggle the Monte Carlo uncertainty band. | *"Our statistical model trains on 12 months of client transaction history, using empirical Bayes shrinkage to model payment delays. In 85% of simulated trajectories, Alex misses Friday's payment."* |
| **0:45 - 1:00** | Point to the Driver Explanation Card. Highlight Apex Design Studio. | *"Here is the culprit: Apex Design Studio has a \$2,000 invoice due in two days, but historically, they pay 14 days late. Their cash won't arrive until next week—well after Marcus is expecting his payout."* |

---

### Act III: Comparing the Three Rescue Plans (1:00 - 1:45)

| Timestamp | Visual Action on Screen | Voiceover Script |
|---|---|---|
| **1:00 - 1:20** | Scroll down to the three side-by-side Rescue Plan cards. Hover over Plan A and Plan B. | *"Instead of just showing another scary graph, Cashflow Lifeline computes the three cheapest ways to protect Marcus's payment.*<br><br>*Plan A is 'Collect Without Concessions': an official PayPal invoice reminder with a direct pay link. Cost: zero dollars.*<br><br>*Plan B is a 'Limited Early-Pay Discount': offering Apex a 3% concession (\$60.00) in exchange for settlement by Friday."* |
| **1:20 - 1:45** | Click on Plan B to preview the green dashed overlay on the chart. Then click Plan C. | *"Notice how the chart dynamically overlays the recovery path. Plan C is 'Contractor Split': paying Marcus \$1,600 from current cash on Friday and scheduling the second \$1,600 for next week. Every plan clearly shows costs, incoming needed, and remaining risks. Notice our non-negotiable rule: nothing is promised as guaranteed—only 'plausibly protects'."* |

---

### Act IV: Cryptographic Guardrail Approval & Sandbox Execution (1:45 - 2:15)

| Timestamp | Visual Action on Screen | Voiceover Script |
|---|---|---|
| **1:45 - 2:00** | On Plan A, point to the HMAC parameters box: Recipient `Apex Design Studio`, Amount `\$2000.00 USD`. Click **"Approve Exact Action"**. | *"Now, the safety guardrail. The LLM can NEVER approve transactions. Approval requires an explicit owner signature. Our HMAC-SHA256 signature cryptographically binds the exact recipient, amount, and action type. If any parameter were tampered with by even one cent, approval would fail."* |
| **2:00 - 2:15** | Click **"Execute in PayPal Sandbox"**. Show the Action Timeline transition from Approved to Executed. | *"We approve Plan A and dispatch it to the PayPal Sandbox. The Invoicing v2 API immediately sends the reminder with an active sandbox payment link. The action enters the 'Executed' state."* |

---

### Act V: Live Webhook Confirmation & Recovery (2:15 - 2:45)

| Timestamp | Visual Action on Screen | Voiceover Script |
|---|---|---|
| **2:15 - 2:30** | Click **"Simulate Client Payment ($2,000)"** in the demo fast-track bar. | *"Now the client pays through PayPal. The sandbox fires a verified `INVOICING.INVOICE.PAID` webhook. Our in-process event queue verifies the cryptographic signature against PayPal's servers."* |
| **2:30 - 2:45** | Show the green banner: **"Contractor Payout to Marcus Sterling is Fully Covered"**. Balance is now **\$3,800.00**. | *"Boom! The action instantly transitions to 'CONFIRMED'. The forecast recalculates in real time. Alex's balance rises to \$3,800. Friday's obligation is 100% protected."* |

---

### Act VI: Cryptographic Audit Trail Verification (2:45 - 3:00)

| Timestamp | Visual Action on Screen | Voiceover Script |
|---|---|---|
| **2:45 - 3:00** | Click on the **Audit Trail** tab. Click **"Verify Chain Integrity"**. Show the green badge: "Audit Chain 100% Intact". | *"Finally, our append-only audit trail. Every decision and webhook event is chained via SHA-256 blocks from Genesis. We click 'Verify Chain Integrity'—all blocks intact. That is Cashflow Lifeline: finding the payment you are about to miss, comparing the cheapest fixes, and protecting it through PayPal with deterministic safety."* |
