import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
from sklearn.linear_model import LogisticRegression
from backend.app.models import PaymentHistory, Invoice, Client


class PaymentDelayModel:
    """
    Statistical model for client payment delays:
    1. Logistic regression for p_late (probability invoice paid after due date).
    2. Quantile / empirical distribution for expected days late with confidence intervals.
    3. Small-sample shrinkage towards population prior for clients with limited history.
    """

    def __init__(self, shrinkage_strength: float = 5.0):
        self.shrinkage_k = shrinkage_strength
        self.clf = LogisticRegression(solver="lbfgs", max_iter=200, random_state=42)
        self.is_fitted = False
        self.population_mean_delay = 3.0
        self.population_std_delay = 4.0
        self.population_p_late = 0.5
        self.client_stats: Dict[int, Dict[str, Any]] = {}

    def fit(self, history_records: List[PaymentHistory]):
        if not history_records:
            return

        delays = [r.days_late for r in history_records]
        amounts = [r.amount for r in history_records]

        self.population_mean_delay = float(np.mean(delays))
        self.population_std_delay = float(np.std(delays)) if len(delays) > 1 else 3.0
        self.population_p_late = float(np.mean([1.0 if d > 0 else 0.0 for d in delays]))

        # Group by client_id
        client_groups: Dict[int, List[PaymentHistory]] = {}
        for r in history_records:
            client_groups.setdefault(r.client_id, []).append(r)

        for client_id, records in client_groups.items():
            c_delays = np.array([r.days_late for r in records])
            n = len(c_delays)

            # Empirical Bayes shrinkage towards population prior
            raw_mean = float(np.mean(c_delays))
            raw_std = float(np.std(c_delays)) if n > 1 else self.population_std_delay
            raw_p_late = float(np.mean(c_delays > 0))

            # Shrinkage weight: w = n / (n + k)
            w = n / (n + self.shrinkage_k)
            shrunk_mean = (w * raw_mean) + ((1 - w) * self.population_mean_delay)
            shrunk_p_late = (w * raw_p_late) + ((1 - w) * self.population_p_late)

            # Quantiles for confidence interval (10th percentile and 90th percentile)
            if n >= 5:
                q10 = float(np.percentile(c_delays, 10))
                q90 = float(np.percentile(c_delays, 90))
            else:
                # Widen interval for clients with little history (uncertainty penalty)
                spread = max(raw_std, self.population_std_delay) * 1.645
                q10 = shrunk_mean - (spread * (1.0 + (5 - n) * 0.2))
                q90 = shrunk_mean + (spread * (1.0 + (5 - n) * 0.2))

            self.client_stats[client_id] = {
                "n_records": n,
                "mean_delay": shrunk_mean,
                "p_late": min(max(shrunk_p_late, 0.02), 0.98),
                "ci_low": round(q10, 1),
                "ci_high": round(q90, 1),
                "std_delay": max(raw_std, 1.0),
            }

        # Train global logistic regression classifier on (amount, historical_client_mean) -> is_late
        X = []
        y = []
        for r in history_records:
            c_stat = self.client_stats.get(r.client_id, {})
            c_mean = c_stat.get("mean_delay", self.population_mean_delay)
            X.append([r.amount / 1000.0, c_mean])
            y.append(1 if r.days_late > 0 else 0)

        if len(set(y)) > 1:
            self.clf.fit(X, y)
            self.is_fitted = True

    def predict_client_delay(
        self,
        client_id: int,
        invoice_amount: float,
        due_date: datetime
    ) -> Dict[str, Any]:
        """
        Returns:
            - expected_pay_date: due_date + expected_days_late
            - p_late: probability paid after due date
            - expected_days_late: predicted days late (can be negative if early)
            - ci_low: 10th percentile days late
            - ci_high: 90th percentile days late
        """
        stats = self.client_stats.get(client_id)
        if not stats:
            # Fallback to population prior with wide interval
            expected_days = self.population_mean_delay
            p_late = self.population_p_late
            ci_low = expected_days - (self.population_std_delay * 1.96)
            ci_high = expected_days + (self.population_std_delay * 1.96)
        else:
            expected_days = stats["mean_delay"]
            p_late = stats["p_late"]
            ci_low = stats["ci_low"]
            ci_high = stats["ci_high"]

            # If logistic model is fitted, blend prediction
            if self.is_fitted:
                try:
                    prob = self.clf.predict_proba([[invoice_amount / 1000.0, expected_days]])[0][1]
                    p_late = (p_late * 0.7) + (prob * 0.3)
                except Exception:
                    pass

        expected_pay_date = due_date + timedelta(days=round(expected_days))
        return {
            "client_id": client_id,
            "expected_days_late": round(expected_days, 1),
            "expected_pay_date": expected_pay_date,
            "p_late": round(p_late, 3),
            "ci_low": round(ci_low, 1),
            "ci_high": round(ci_high, 1),
            "ci_low_date": due_date + timedelta(days=round(ci_low)),
            "ci_high_date": due_date + timedelta(days=round(ci_high)),
        }

