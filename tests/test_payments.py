from unittest.mock import patch
import pytest

from agents.payments.stripe import StripeAccount
from agents.payments.processor import ProcessorInterface


def test_stripe_account_loads_gateway_config():
    with patch("agents.payments.stripe.get_setting") as mock_get:
        mock_get.return_value = {"stripe": {"api_key": "secret"}}
        account = StripeAccount("acct_1")
        assert account.gateway_config == {"api_key": "secret"}
        mock_get.assert_called_once_with("payment_gateways")


def test_processor_requires_connect_classmethod_when_action_present():
    class BadProcessor(ProcessorInterface):
        actions = {"connect"}

    with pytest.raises(NotImplementedError):
        BadProcessor.versioned()

    class GoodProcessor(ProcessorInterface):
        actions = {"connect"}

        @classmethod
        def connect(cls):  # pragma: no cover - simple stub
            return True

    assert GoodProcessor.versioned() is GoodProcessor
