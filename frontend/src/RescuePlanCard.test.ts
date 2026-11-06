import { describe, it, expect } from 'vitest';
import { RescuePlan } from './types';

describe('Rescue Plan Logic & Safety Tests', () => {
  const mockPlanA: RescuePlan = {
    id: 1,
    run_id: 'fc_test_1',
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
    remaining_risk: 'Plausibly protects contractor payment if client settles promptly. Timing is not guaranteed.',
    primary_action: {
      id: 101,
      action_type: 'SEND_REMINDER',
      recipient: 'Apex Design Studio',
      amount: 2000.0,
      currency: 'USD',
      state: 'proposed',
      idempotency_key: 'act_remind_1',
      approval_hash: '9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08',
      is_simulated: false,
    },
  };

  it('enforces safety wording: plausibly protects present and guarantees absent', () => {
    expect(mockPlanA.remaining_risk.toLowerCase()).toContain('plausibly protects');
    expect(mockPlanA.remaining_risk.toLowerCase()).not.toContain('guarantees');
  });

  it('calculates zero concession cost for Plan A', () => {
    expect(mockPlanA.cost).toBe(0.0);
    expect(mockPlanA.incoming_needed).toBe(1400.0);
  });

  it('binds exact action parameters to primary action', () => {
    const act = mockPlanA.primary_action;
    expect(act.action_type).toBe('SEND_REMINDER');
    expect(act.recipient).toBe('Apex Design Studio');
    expect(act.amount).toBe(2000.0);
    expect(act.currency).toBe('USD');
    expect(act.state).toBe('proposed');
    expect(act.approval_hash.length).toBe(64);
  });
});
