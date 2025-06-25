import sys
from pathlib import Path
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))
from risk import RiskManager


def test_can_trade_limits():
    rm = RiskManager(10, 2, 10, 3, 'normal', 2, 3, True, True, 0.8, ['EURUSD'])
    assert rm.can_trade('EURUSD')
    rm.assets['EURUSD']['losses_amount'] = 15
    assert not rm.can_trade('EURUSD')


def test_next_amount_martingale():
    rm = RiskManager(100, 10, 100, 10, 'martingale', 2, 3, True, True, 0.8, ['EURUSD'])
    rm.register_trade('EURUSD', False)
    assert rm.next_amount('EURUSD', high_chance=True) == 2
    rm.register_trade('EURUSD', True)
    assert rm.next_amount('EURUSD', high_chance=True) == 1


def test_next_amount_soros():
    rm = RiskManager(100, 10, 100, 10, 'soros', 2, 3, True, True, 0.8, ['EURUSD'])
    rm.register_trade('EURUSD', False)
    assert rm.next_amount('EURUSD', high_chance=True, payout=0.9) == 3
    rm.register_trade('EURUSD', True)
    assert rm.next_amount('EURUSD') == 1


def test_next_amount_reset_on_limit():
    rm = RiskManager(5, 1, 10, 3, 'martingale', 2, 3, True, True, 0.8, ['EURUSD'])
    rm.assets['EURUSD']['losses_amount'] = 6
    rm.assets['EURUSD']['current_amount'] = 4
    assert rm.next_amount('EURUSD') == 1
