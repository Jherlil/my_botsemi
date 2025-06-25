import time
import pandas as pd
from iqoptionapi.stable_api import IQ_Option
from utils import log, load_config, entry_strength
from fundamental import FundamentalAnalyzer
from technical import TechnicalAnalyzer
from risk import RiskManager
from ml_model import MLModel


def get_candles_df(IQ, asset, timeframe, num_candles):
    """Busca velas recentes como DataFrame do pandas, mapeando campos IQ Option para OHLCV."""
    candles = IQ.get_candles(asset, timeframe, num_candles, time.time())
    df = pd.DataFrame(candles)
    # Renomear campos IQ Option: 'min'->'low', 'max'->'high'
    df.rename(columns={'min': 'low', 'max': 'high'}, inplace=True)
    # Converter timestamp para datetime e definir índice temporal
    df['time'] = pd.to_datetime(df['from'], unit='s')
    df.set_index('time', inplace=True)
    df.sort_index(inplace=True)
    return df


def main():
    """Ponto de entrada para o robô de trading."""
    config = load_config("config.yaml")

    IQ = IQ_Option(config["email"], config["password"])
    try:
        IQ.connect()
    except Exception as exc:
        log(f"Falha ao conectar: {exc}", level="error")
        return

    IQ.change_balance(config['account_type'].upper())

    fundamental = FundamentalAnalyzer(buffer_minutes=config['news_buffer_minutes'])
    technical = TechnicalAnalyzer(
        ma_fast=config['trend_ma_fast'],
        ma_slow=config['trend_ma_slow'],
        volume_period=config['volume_period'],
    )
    risk = RiskManager(
        stop_loss_amount=config['stop_loss_amount'],
        stop_loss_consecutive=config['stop_loss_consecutive'],
        stop_win_amount=config['stop_win_amount'],
        stop_win_victories=config['stop_win_victories'],
        strategy=config['strategy'],
        martingale_factor=config['martingale_factor'],
        soros_level=config['soros_level'],
        use_martingale_if_high_chance=config['use_martingale_if_high_chance'],
        use_soros_if_low_payout=config['use_soros_if_low_payout'],
        min_payout_for_soros=config['min_payout_for_soros'],
        assets=config['assets'],
    )
    ml = MLModel()

    daily_wins = 0
    last_trade_date = None

    while True:
        log("Loop principal...")
        ml.check_and_train_daily()

        # Pausa em notícias de alto impacto
        if fundamental.check_high_impact_news():
            log("Esperando — notícia importante próxima...")
            time.sleep(60)
            continue

        # Reinicia vitórias diárias ao mudar o dia
        now = pd.Timestamp.now()
        if last_trade_date is None or last_trade_date.date() < now.date():
            daily_wins = 0
        last_trade_date = now

        # Stop-win diário
        if daily_wins >= config['stop_win_victories']:
            log("Stop win diário atingido — esperando até amanhã...")
            time.sleep(60 * 60)
            continue

        # Atualiza payout de todos os ativos
        all_profit = IQ.get_all_profit()

        for asset in config['assets']:
            payout = all_profit.get(asset, {}).get('turbo', 0)
            if payout < config['min_payout'] or payout > config['max_payout']:
                continue

            # Obtém e prepara as velas
            try:
                df = get_candles_df(IQ, asset, config['timeframe_main'], num_candles=100)
            except Exception as exc:
                log(f"Erro ao obter velas: {exc}", level="error")
                continue

            df = technical.calculate_moving_averages(df)
            df = technical.add_m5_indicators(df)

            breakout = technical.detect_breakout(df, lookback=config.get('breakout_lookback', 50))
            trend = technical.detect_trend(df)
            patterns = technical.detect_candlestick_patterns(df)
            pattern_name = patterns[0][0] if patterns else None
            last_candle = df.iloc[-1]

            avg_volume = df['volume'].rolling(config['volume_period']).mean().iloc[-1]
            volume_ratio = last_candle.volume / avg_volume if avg_volume > 0 else 0


            # Monta features para o modelo de ML
            features = {
                "pattern_name": pattern_name or "unknown",
                "breakout": breakout or "none",
                "trend": trend,
                "volume_ratio": volume_ratio,
                "payout": payout,
                "ema_cross": bool(df['EMA_CROSS'].iloc[-1]),
                "rsi7": float(df['RSI7'].iloc[-1]),
                "macd_hist": float(df['MACD_HIST'].iloc[-1]),
                "adx14": float(df['ADX14'].iloc[-1]),
                "atr14": float(df['ATR14'].iloc[-1]),
            }
            ml_high = ml.predict_high_chance(features)

            if risk.can_trade(asset):
                direction = None
                super_dir = "up" if last_candle.close > last_candle.SUPERT else "down"
                if trend == "up" and super_dir == "up":
                    direction = "call"
                elif trend == "down" and super_dir == "down":
                    direction = "put"
                if not direction:
                    continue

                # Confluências de indicadores
                signals = []
                if breakout:
                    signals.append("breakout")
                if pattern_name:
                    signals.append("pattern")
                if volume_ratio > 1.0:
                    signals.append("volume")
                if trend != "flat":
                    signals.append("trend")
                if df['EMA_CROSS'].iloc[-1]:
                    signals.append("ema_cross")
                if (trend == "up" and df['MACD_HIST'].iloc[-1] > 0) or (
                    trend == "down" and df['MACD_HIST'].iloc[-1] < 0
                ):
                    signals.append("macd")
                if df['ADX14'].iloc[-1] > 20:
                    signals.append("adx")
                if (
                    trend == "up" and last_candle.close > last_candle.SUPERT
                ) or (
                    trend == "down" and last_candle.close < last_candle.SUPERT
                ):
                    signals.append("supertrend")
                if (
                    trend == "up" and last_candle.close > last_candle.VWAP
                ) or (
                    trend == "down" and last_candle.close < last_candle.VWAP
                ):
                    signals.append("vwap")
                if ml_high:
                    signals.append("ml")

                strength = entry_strength(len(signals))
                if strength == "nenhuma":
                    continue

                amount = risk.next_amount(asset, high_chance=strength != "fraca", payout=payout)
                log(
                    f"[{asset}] Entrando {direction} com {amount} — confluências:{len(signals)} ({strength})"
                )
                try:
                    status, order_id = IQ.buy(amount, asset, direction, expiry=1)
                    result, _ = IQ.check_win(order_id)
                except Exception as exc:
                    log(f"Erro ao executar ordem: {exc}", level="error")
                    result = False

                risk.register_trade(asset, result)
                ml.log_trade(features, result)

                if result:
                    daily_wins += 1

        log("Esperando próximo ciclo...")
        time.sleep(config['timeframe_main'])


if __name__ == "__main__":
    main()
