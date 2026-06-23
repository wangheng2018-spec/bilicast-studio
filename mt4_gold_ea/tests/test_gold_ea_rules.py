import re
import unittest
from pathlib import Path


EA_PATH = Path(__file__).resolve().parents[1] / "Experts" / "GoldShortScalpEA.mq4"


class GoldEaRulesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = EA_PATH.read_text(encoding="utf-8")

    def test_max_lot_is_capped_at_002(self):
        self.assertRegex(self.source, r"input\s+double\s+MaxLot\s*=\s*0\.02\s*;")
        self.assertIn("MathMin(lot, MaxLot)", self.source)

    def test_profit_lock_uses_random_5_to_10_usd_window(self):
        self.assertRegex(self.source, r"input\s+double\s+LockTriggerMinUSD\s*=\s*5\.0\s*;")
        self.assertRegex(self.source, r"input\s+double\s+LockTriggerMaxUSD\s*=\s*10\.0\s*;")
        self.assertRegex(self.source, r"input\s+double\s+LockProfitMinUSD\s*=\s*5\.0\s*;")
        self.assertRegex(self.source, r"input\s+double\s+LockProfitMaxUSD\s*=\s*10\.0\s*;")
        self.assertIn("EnsureTicketProfile(ticket)", self.source)

    def test_huge_short_term_profit_closes_between_10_and_20_usd(self):
        self.assertRegex(self.source, r"input\s+double\s+HugeProfitMinUSD\s*=\s*10\.0\s*;")
        self.assertRegex(self.source, r"input\s+double\s+HugeProfitMaxUSD\s*=\s*20\.0\s*;")
        self.assertIn("HugeProfitWindowSeconds", self.source)
        self.assertIn("CloseOrder(ticket, \"huge short-term profit\")", self.source)

    def test_strict_stop_loss_has_money_and_atr_guards(self):
        self.assertRegex(self.source, r"input\s+double\s+MaxLossUSD\s*=\s*8\.0\s*;")
        self.assertIn("BuildInitialShortStopLoss", self.source)
        self.assertIn("MoneyToPriceDistance", self.source)
        self.assertIn("iATR", self.source)

    def test_no_grid_martingale_or_many_open_positions(self):
        lowered = self.source.lower()
        self.assertNotIn("martingale", lowered)
        self.assertNotIn("grid", lowered)
        self.assertIn("CountOpenPositions()", self.source)
        self.assertIn("MaxOpenPositions", self.source)

    def test_ea_is_short_only(self):
        self.assertNotIn("OP_BUY", self.source)
        self.assertIn("OrderSend(TradeSymbol, OP_SELL", self.source)
        self.assertIn("ShouldOpenShort()", self.source)


if __name__ == "__main__":
    unittest.main()
