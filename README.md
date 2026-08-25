# HarnessParsePredict — Streamlit

Harness-racing prediction app built for Racing & Sports **Enhanced Form** pasted text.

## Features
- Paste → parse → inspect → tactical map → predict → explanations
- Automatically excludes scratches
- Harness-specific fundamentals: adjusted mile rate, tactical position/draw, course-distance, recent form, driver/trainer, OHR, sectionals, reliability and freshness
- Market/fundamental probability blend
- Top-2 / Top-3 / expected position simulation
- Fair odds, EV, confidence and CSV export

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Cloud
- Repository: `sbachagian1101/horse-race-predictor`
- Branch: `harness-predictor`
- Main file: `app.py`

## Notes
The model is probabilistic decision support. It does not guarantee race outcomes. V1 uses listed runner order as the current gate proxy when the pasted Enhanced Form does not expose a separate current HCP/barrier.
