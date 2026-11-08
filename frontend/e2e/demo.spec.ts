import { test, expect } from '@playwright/test';

test.describe('Cashflow Lifeline Demo Flow E2E Test', () => {
  test('walks through the 3-minute hackathon demo with mocked backend responses', async ({ page }) => {
    // 1. Mock the initial forecast endpoint with the baseline shortfall scenario
    await page.route('**/api/forecast/latest', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          run_id: 'fc_e2e_demo_test',
          obligation: {
            id: 1,
            owner_id: 1,
            payee_name: 'Marcus Sterling',
            payee_email: 'marcus.contractor@example.com',
            amount: 3200.0,
            currency: 'USD',
            due_date: '2026-11-13T17:00:00Z',
            split_allowed: true,
            status: 'pending',
          },
          shortfall_amount: 1400.0,
          first_shortfall_date: '2026-11-13',
          tradeoff_summary:
            'Plan A incurs $0.00 cost but relies on prompt response. Plan B accelerates cash flow at an early-pay discount cost of $60.00. Plan C splits the payout with $0.00 cash cost.',
          plans: [
            {
              id: 1,
              run_id: 'fc_e2e_demo_test',
              plan_type: 'A',
              name: 'Plan A: Collect Without Concessions',
              description: 'Send reminder with pay link to reliable client.',
              cost: 0.0,
              cost_description: '$0.00 concession cost. Zero revenue lost.',
              incoming_needed: 1400.0,
              selected_clients: [],
              rationale: 'Targets Apex Design Studio for prompt settlement.',
              forecast_with_plan: [],
              forecast_without_plan: [],
              late_scenario: { outcome: 'If client remains late, shortfall persists.', shortfall: 1400.0 },
              remaining_risk:
                'Plausibly protects contractor payment if client settles promptly. Timing is not guaranteed.',
              primary_action: {
                id: 101,
                action_type: 'SEND_REMINDER',
                recipient: 'Apex Design Studio',
                amount: 2000.0,
                currency: 'USD',
                state: 'proposed',
                idempotency_key: 'act_e2e_remind_1',
                approval_hash: '9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08',
                is_simulated: false,
              },
            },
            {
              id: 2,
              run_id: 'fc_e2e_demo_test',
              plan_type: 'B',
              name: 'Plan B: Limited Early-Pay Discount',
              description: 'Apply 3% discount to accelerate cashflow.',
              cost: 60.0,
              cost_description: '$60.00 discount cost (3% concession).',
              incoming_needed: 1400.0,
              selected_clients: [],
              rationale: 'Incentivizes early settlement.',
              forecast_with_plan: [],
              forecast_without_plan: [],
              late_scenario: { outcome: 'Discount expires if unaccepted.', shortfall: 1400.0 },
              remaining_risk: 'Plausibly protects Friday invoice by providing monetary incentive.',
              primary_action: {
                id: 102,
                action_type: 'APPLY_DISCOUNT',
                recipient: 'Apex Design Studio',
                amount: 60.0,
                currency: 'USD',
                state: 'proposed',
                idempotency_key: 'act_e2e_disc_2',
                approval_hash: '5d41402abc4b2a76b9719d911017c592',
                is_simulated: false,
              },
            },
            {
              id: 3,
              run_id: 'fc_e2e_demo_test',
              plan_type: 'C',
              name: 'Plan C: Collect Plus Agreed Contractor Split',
              description: 'Split payout into two installments.',
              cost: 0.0,
              cost_description: '$0.00 cash cost (goodwill proxy).',
              incoming_needed: 0.0,
              selected_clients: [],
              rationale: 'Defers 50% of contractor payout.',
              forecast_with_plan: [],
              forecast_without_plan: [],
              late_scenario: { outcome: 'Second installment liability remains.', shortfall: 1600.0 },
              remaining_risk: 'Plausibly protects Friday payout; requires mutual contractor agreement in writing.',
              primary_action: {
                id: 103,
                action_type: 'SCHEDULE_PAYOUT_SPLIT',
                recipient: 'Marcus Sterling',
                amount: 1600.0,
                currency: 'USD',
                state: 'proposed',
                idempotency_key: 'act_e2e_split_3',
                approval_hash: '7d41402abc4b2a76b9719d911017c593',
                is_simulated: false,
              },
            },
          ],
        }),
      });
    });

    // 2. Navigate to Dashboard
    await page.goto('http://localhost:5173');

    // 3. Verify At-Risk Obligation Banner is displayed with $1,400 shortfall
    await expect(page.locator('text=Projected Shortfall of $1,400.00')).toBeVisible();
    await expect(page.locator('text=Marcus Sterling')).toBeVisible();

    // 4. Verify three Rescue Plans are displayed side by side
    await expect(page.locator('text=Plan A: Collect Without Concessions')).toBeVisible();
    await expect(page.locator('text=Plan B: Limited Early-Pay Discount')).toBeVisible();
    await expect(page.locator('text=Plan C: Collect Plus Agreed Contractor Split')).toBeVisible();

    // 5. Verify safety rule: "plausibly protects" is present
    await expect(page.locator('text=Plausibly protects contractor payment if client settles promptly.')).toBeVisible();

    // 6. Mock owner approval POST request
    await page.route('**/api/actions/101/approve', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 101,
          action_type: 'SEND_REMINDER',
          recipient: 'Apex Design Studio',
          amount: 2000.0,
          currency: 'USD',
          state: 'approved',
          idempotency_key: 'act_e2e_remind_1',
          approval_hash: '9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08',
          approved_at: new Date().toISOString(),
          is_simulated: false,
        }),
      });
    });

    // 7. Mock execute POST request
    await page.route('**/api/actions/101/execute', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 101,
          action_type: 'SEND_REMINDER',
          recipient: 'Apex Design Studio',
          amount: 2000.0,
          currency: 'USD',
          state: 'executed',
          idempotency_key: 'act_e2e_remind_1',
          approval_hash: '9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08',
          approved_at: new Date().toISOString(),
          executed_at: new Date().toISOString(),
          paypal_ref: 'INV2-DEMO-APEX-001',
          is_simulated: false,
        }),
      });
    });

    // 8. Click "Approve Exact Action"
    const approveBtn = page.locator('button:has-text("Approve Exact Action")');
    await expect(approveBtn).toBeVisible();
    await approveBtn.click();

    // 9. Verify Action timeline reflects approved state
    await expect(page.locator('text=Plan Approved!')).toBeVisible();
  });
});

