import unittest

from fin_ai_stats_extract.cost import MODEL_INPUT_PRICING, get_model_input_price


class CostPricingTests(unittest.TestCase):
    def test_gpt_5_4_mini_price_is_known(self) -> None:
        self.assertEqual(MODEL_INPUT_PRICING["gpt-5.4-mini"], 0.75)
        self.assertEqual(get_model_input_price("gpt-5.4-mini"), 0.75)

    def test_gpt_5_4_nano_price_is_known(self) -> None:
        self.assertEqual(MODEL_INPUT_PRICING["gpt-5.4-nano"], 0.20)
        self.assertEqual(get_model_input_price("gpt-5.4-nano"), 0.20)
        self.assertEqual(get_model_input_price("gpt-5.4-nano"), 0.20)
