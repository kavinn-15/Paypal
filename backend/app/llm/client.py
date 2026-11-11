import logging
from typing import Optional, Dict, Any, List
import httpx
from backend.app.config import settings
from backend.app.llm.validator import validate_llm_numbers

logger = logging.getLogger("llm_service")


class LLMService:
    """
    LLM abstraction layer strictly restricted to:
    (1) Plain-language explanation of forecast drivers
    (2) Reasoning over rescue plan trade-offs
    (3) Drafting client and contractor communication messages

    SAFETY: The LLM is NEVER permitted to approve, execute, or alter amounts.
    All numeric values must be validated against computed figures; any mismatch
    immediately falls back to deterministic templates.
    """

    def __init__(self):
        self.provider = (settings.LLM_PROVIDER or "template").lower()
        self.api_key = settings.LLM_API_KEY
        self.model = settings.LLM_MODEL or ("gemini-1.5-flash" if self.provider == "gemini" else "claude-3-haiku-20240307")

    def generate_driver_explanation(
        self,
        starting_balance: float,
        shortfall_amount: float,
        target_date_str: str,
        contractor_name: str,
        top_client_name: str,
        top_client_delay: int,
        p_shortfall: float,
        currency: str = "USD",
        currency_symbol: str = "$"
    ) -> str:
        """Generates plain-language explanation of the primary cashflow shortfall driver."""
        sym = currency_symbol or "$"
        template_fallback = (
            f"If your largest client ({top_client_name}) pays {top_client_delay} days late as historically "
            f"observed, you will be short by {sym}{shortfall_amount:,.2f} before your contractor payout to "
            f"{contractor_name} on {target_date_str} (shortfall risk: {p_shortfall*100:.0f}%)."
        )

        if self.provider == "template" or not self.api_key:
            return template_fallback

        prompt = (
            f"Write a concise, natural 1-sentence explanation for a freelancer's cashflow dashboard. "
            f"Computed facts: Starting balance is {sym}{starting_balance:,.2f}. Shortfall amount is {sym}{shortfall_amount:,.2f}. "
            f"Contractor payout to {contractor_name} is due on {target_date_str}. "
            f"Top late client is {top_client_name} who typically pays {top_client_delay} days late. "
            f"Shortfall risk is {p_shortfall*100:.0f}%. "
            f"Rules: Quote exact amounts ({sym}{shortfall_amount:,.2f}) and names. Do not invent any numbers."
        )

        try:
            llm_text = self._call_llm(prompt)
            if llm_text:
                # Strictly validate that numbers match
                allowed = [starting_balance, shortfall_amount, float(top_client_delay), p_shortfall, round(p_shortfall * 100)]
                if validate_llm_numbers(llm_text, allowed):
                    return llm_text.strip().strip('"')
                logger.info("Number validation mismatch; falling back to deterministic template.")
        except Exception as e:
            logger.warning(f"LLM call failed: {e}. Using deterministic template.")

        return template_fallback

    def generate_tradeoff_summary(
        self,
        shortfall_amount: float,
        plan_b_discount_cost: float,
        contractor_name: str,
        plan_a_risk: str,
        plan_b_risk: str,
        plan_c_risk: str,
        currency: str = "USD",
        currency_symbol: str = "$"
    ) -> str:
        """Generates plain-language comparison of the three Rescue Plans."""
        sym = currency_symbol or "$"
        template_fallback = (
            f"Plan A incurs {sym}0.00 cost but leaves payment timing uncertain if clients remain late. "
            f"Plan B plausibly accelerates cash flow at an early-pay concession cost of {sym}{plan_b_discount_cost:,.2f}. "
            f"Plan C protects your Friday balance with {sym}0.00 cash cost by splitting the {contractor_name} "
            f"payout, requiring mutual contractor consent."
        )

        if self.provider == "template" or not self.api_key:
            return template_fallback

        prompt = (
            f"Summarize the trade-offs between three rescue plans for a {sym}{shortfall_amount:,.2f} shortfall: "
            f"Plan A: Collect without concessions (Cost: {sym}0.00, Risk: {plan_a_risk}). "
            f"Plan B: Limited early-pay discount (Cost: {sym}{plan_b_discount_cost:,.2f}, Risk: {plan_b_risk}). "
            f"Plan C: Collect + agreed contractor split with {contractor_name} (Cost: {sym}0.00, Risk: {plan_c_risk}). "
            f"Write a neutral 2-sentence trade-off comparison. Must use 'plausibly protects' instead of 'guarantees'. "
            f"Never alter the figures: {sym}0.00 and {sym}{plan_b_discount_cost:,.2f}."
        )

        try:
            llm_text = self._call_llm(prompt)
            if llm_text:
                allowed = [0.0, shortfall_amount, plan_b_discount_cost]
                if validate_llm_numbers(llm_text, allowed):
                    return llm_text.strip().strip('"')
        except Exception as e:
            logger.warning(f"LLM call failed: {e}. Using deterministic template.")

        return template_fallback

    def draft_reminder_message(
        self,
        client_name: str,
        invoice_id: str,
        amount: float,
        due_date_str: str,
        pay_link: Optional[str] = None,
        currency: str = "USD",
        currency_symbol: str = "$"
    ) -> str:
        """Drafts polite payment reminder with live PayPal payment link."""
        sym = currency_symbol or "$"
        curr = currency or "USD"
        link_str = f" Pay securely via PayPal: {pay_link}" if pay_link else ""
        template_fallback = (
            f"Hi {client_name}, this is a gentle reminder regarding invoice #{invoice_id} "
            f"for {sym}{amount:,.2f} {curr} due on {due_date_str}.{link_str} "
            f"Thank you for your business!"
        )

        if self.provider == "template" or not self.api_key:
            return template_fallback

        prompt = (
            f"Draft a polite, professional 2-sentence payment reminder email from a freelancer to a client ({client_name}). "
            f"Invoice #{invoice_id} for {sym}{amount:,.2f} {curr} is due on {due_date_str}. "
            f"Include this exact PayPal payment link if present: '{pay_link or ''}'. "
            f"Keep tone warm and professional. Do NOT alter the invoice ID, amount, currency, or due date."
        )

        try:
            llm_text = self._call_llm(prompt)
            if llm_text:
                if validate_llm_numbers(llm_text, [amount]):
                    return llm_text.strip().strip('"')
                logger.info("Reminder message number validation mismatch; using template fallback.")
        except Exception as e:
            logger.warning(f"LLM reminder draft failed: {e}. Using deterministic template.")

        return template_fallback

    def draft_discount_message(
        self,
        client_name: str,
        invoice_id: str,
        original_amount: float,
        discount_pct: float,
        discounted_amount: float,
        deadline_str: str,
        pay_link: Optional[str] = None,
        currency: str = "USD",
        currency_symbol: str = "$"
    ) -> str:
        """Drafts early settlement incentive message."""
        sym = currency_symbol or "$"
        curr = currency or "USD"
        savings = original_amount - discounted_amount
        link_str = f" Pay here: {pay_link}" if pay_link else ""
        template_fallback = (
            f"Hi {client_name}, we are pleased to offer a {discount_pct:.0f}% early payment discount on "
            f"invoice #{invoice_id}. If settled by {deadline_str}, the revised amount is "
            f"{sym}{discounted_amount:,.2f} {curr} (saving {sym}{savings:,.2f}).{link_str} "
            f"Let us know if you'd like to take advantage of this concession!"
        )

        if self.provider == "template" or not self.api_key:
            return template_fallback

        prompt = (
            f"Draft a professional, compelling message from a freelancer to a client ({client_name}) offering a {discount_pct:.0f}% "
            f"early payment discount on invoice #{invoice_id}. "
            f"Original amount is {sym}{original_amount:,.2f}. Discounted amount is {sym}{discounted_amount:,.2f} {curr} "
            f"(saving {sym}{savings:,.2f}) if settled by {deadline_str}. "
            f"Include payment link '{pay_link or ''}' if available. Never alter the figures."
        )

        try:
            llm_text = self._call_llm(prompt)
            if llm_text:
                allowed = [original_amount, discounted_amount, discount_pct, savings]
                if validate_llm_numbers(llm_text, allowed):
                    return llm_text.strip().strip('"')
                logger.info("Discount message number validation mismatch; using template fallback.")
        except Exception as e:
            logger.warning(f"LLM discount draft failed: {e}. Using deterministic template.")

        return template_fallback

    def draft_contractor_split_message(
        self,
        contractor_name: str,
        total_amount: float,
        first_installment: float,
        first_date_str: str,
        second_installment: float,
        second_date_str: str,
        currency: str = "USD",
        currency_symbol: str = "$"
    ) -> str:
        """Drafts polite installment agreement message for contractor payout."""
        sym = currency_symbol or "$"
        template_fallback = (
            f"Hi {contractor_name}, thank you for your continued great work. To align with our client payment "
            f"cycles, we propose splitting your {sym}{total_amount:,.2f} payout into two installments: "
            f"{sym}{first_installment:,.2f} on {first_date_str}, and the remaining {sym}{second_installment:,.2f} "
            f"on {second_date_str}. Please let us know if this arrangement works for you."
        )

        if self.provider == "template" or not self.api_key:
            return template_fallback

        prompt = (
            f"Draft a respectful, collaborative message from a business owner to their contractor ({contractor_name}) "
            f"proposing to split their upcoming {sym}{total_amount:,.2f} payment into two installments: "
            f"{sym}{first_installment:,.2f} on {first_date_str}, and {sym}{second_installment:,.2f} on {second_date_str}. "
            f"Thank them for great work and ask for their consent. Do not alter the amounts or dates."
        )

        try:
            llm_text = self._call_llm(prompt)
            if llm_text:
                allowed = [total_amount, first_installment, second_installment]
                if validate_llm_numbers(llm_text, allowed):
                    return llm_text.strip().strip('"')
                logger.info("Contractor split message number validation mismatch; using template fallback.")
        except Exception as e:
            logger.warning(f"LLM contractor split draft failed: {e}. Using deterministic template.")

        return template_fallback

    def _call_llm(self, prompt: str) -> Optional[str]:
        """Synchronously calls Anthropic or Gemini endpoint."""
        if self.provider == "anthropic":
            return self._call_anthropic(prompt)
        elif self.provider == "gemini":
            return self._call_gemini(prompt)
        return None

    def _call_anthropic(self, prompt: str) -> Optional[str]:
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        body = {
            "model": self.model,
            "max_tokens": 250,
            "messages": [{"role": "user", "content": prompt}]
        }
        with httpx.Client(timeout=10.0) as client:
            resp = client.post("https://api.anthropic.com/v1/messages", json=body, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                return data["content"][0]["text"]
        return None

    def _call_gemini(self, prompt: str) -> Optional[str]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        body = {
            "contents": [{"parts": [{"text": prompt}]}]
        }
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, json=body)
            if resp.status_code == 200:
                data = resp.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
        return None


llm_service = LLMService()

