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

### Act II: Autonomous Supervisor & Agent Coordination (0:30 - 1:00)

| Timestamp | Visual Action on Screen | Voiceover Script |
|---|---|---|
| **0:30 - 0:45** | Click **Supervisor** tab. Click **"Run Autonomous Supervisor Orchestration"**. Show step-by-step agent traces executing live. | *"Our Autonomous Supervisor Agent coordinates specialized AI agents. The Forecaster runs 1,000 Monte Carlo trajectories with empirical Bayes shrinkage; the Collector analyzes client payment reliability; the Treasurer solves for optimal timing; and the Planner synthesizes rescue options."* |
| **0:45 - 1:00** | Point to the Forecaster chart on the main dashboard. Highlight Apex Design Studio in Driver Explanation. | *"Here is the culprit: Apex Design Studio has a \$2,000 invoice due in two days, but historically pays 14 days late. Their cash won't arrive until next week—leaving Friday's contractor payout stranded."* |

---

### Act III: What-If Studio & Negotiation Engine (1:00 - 1:35)

| Timestamp | Visual Action on Screen | Voiceover Script |
|---|---|---|
| **1:00 - 1:15** | Click **What-If Studio** tab. Select the **"Client Delays +5 Days"** and **"Contractor 50% Split"** presets. | *"What if things get worse? Alex can test scenarios in our What-If Studio. It runs in-memory simulations without touching live records, showing exactly how delays or expense shocks affect cash runway."* |
| **1:15 - 1:35** | Click **Negotiation Studio** tab. Toggle between **Professional**, **Friendly**, and **Urgent** tones. | *"Our Financial Negotiation Agent crafts tone-calibrated messages: whether a formal corporate reminder for enterprise clients or a friendly note with early-pay discount incentives."* |

---

### Act IV: Comparing Rescue Plans & Cryptographic Guardrails (1:35 - 2:15)

| Timestamp | Visual Action on Screen | Voiceover Script |
|---|---|---|
| **1:35 - 1:55** | Return to Dashboard. Compare the three Rescue Plans (Plan A, B, and C). Click Plan B to see trajectory overlay. | *"Instead of just showing a scary graph, Cashflow Lifeline generates three costed rescue plans.*<br><br>*Plan A: Zero-cost PayPal invoice reminder with pay link.<br>Plan B: 3% early-pay discount (\$60 concession) to incentivize payment before Friday.<br>Plan C: Agreed contractor split payout.*<br><br>*Notice our non-negotiable rule: nothing is promised as guaranteed—only 'plausibly protects'."* |
| **1:55 - 2:15** | Click **"Approve Exact Action"** on Plan A. Show the HMAC Approval Modal. | *"Now, the safety guardrail. The LLM can NEVER approve transactions. Approval requires an explicit owner signature. Our HMAC-SHA256 signature cryptographically binds the exact recipient, amount, and action type. If any parameter were tampered with by even one cent, approval would fail."* |

---

### Act V: Live PayPal Sandbox Execution & Webhook Confirmation (2:15 - 2:45)

| Timestamp | Visual Action on Screen | Voiceover Script |
|---|---|---|
| **2:15 - 2:30** | Click **"Execute in PayPal Sandbox"**. Show Action Timeline enter 'Executed'. Then click **"Simulate Client Payment ($2,000)"**. | *"We dispatch Plan A to the PayPal Sandbox via Invoicing v2 API. When the client pays, PayPal fires an `INVOICING.INVOICE.PAID` webhook. Our in-process event queue verifies the cryptographic signature."* |
| **2:30 - 2:45** | Show the green banner: **"Contractor Payout to Marcus Sterling is Fully Covered"**. Balance is now **\$3,800.00**. | *"Boom! The action transitions to 'CONFIRMED'. The forecast recalculates in real time. Alex's balance rises to \$3,800. Friday's obligation is 100% protected."* |

---

### Act VI: Resilience Score & Audit Trail Verification (2:45 - 3:00)

| Timestamp | Visual Action on Screen | Voiceover Script |
|---|---|---|
| **2:45 - 3:00** | Click **Resilience Score** tab (show 6 dimensions), then click **Audit Trail** and click **"Verify Chain Integrity"**. | *"Alex's Financial Resilience Score jumps to 78. And on our Audit Trail tab, every decision is chained via SHA-256 blocks from Genesis. We click 'Verify Chain Integrity'—all blocks 100% intact. That is Cashflow Lifeline: autonomous prediction, bounded AI reasoning, and PayPal sandbox execution."* |
