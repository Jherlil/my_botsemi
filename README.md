# 🤖 Robô Avançado para IQ Option + TradingView

## 🎯 Funcionalidades
- Operação automática (IQ Option) e confirmação TradingView.
- Análise técnica: MA, breakout (usando suporte/resistência com lookback configurável), Fibonacci, LTA/LTB, padrões candlestick (TA-Lib).
- Confirmação por volume (IQ Option e TradingView).
- Gestão de risco (normal, martingale, soros) por paridade.
- Filtro contra notícias de alto impacto.

## 🧠 Como usar
1. Configure o \`config.yaml\`.
2. Rode \`webhook.py\` (servidor TradingView).
3. Crie alertas TradingView apontando para o servidor.
4. Rode \`bot.py\` para análise automática + confirmação TradingView.

## 🚀 Dependências
\`\`\`
pip install iqoptionapi pandas flask feedparser pyyaml TA-Lib
\`\`\`

---
