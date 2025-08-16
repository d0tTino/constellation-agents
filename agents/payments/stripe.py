"""Stripe payment account implementation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict

from .database import get_setting


@dataclass
class StripeAccount:
    """Representation of a Stripe account.

    Upon initialization the class loads gateway configuration from the database
    settings. The configuration is stored in ``gateway_config``.
    """

    account_id: str
    gateway_config: Dict[str, Any] = field(init=False)

    def __post_init__(self) -> None:
        settings = get_setting("payment_gateways") or {}
        config = settings.get("stripe")
        if config is None:
            raise ValueError("Stripe settings not found in database")
        self.gateway_config = config
