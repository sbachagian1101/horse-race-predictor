# GreyhoundParsePredict

Streamlit greyhound racing parser and probability model for Racing & Sports **Enhanced Form** copy/paste data.

## Features

- Paste a complete greyhound Enhanced Form page
- Parse scratches and active reserves; reserve 9/10 fill vacant boxes when identifiable
- Inspect runner, trainer, odds, box stats, course/distance records and recent run data
- Greyhound-specific speed map using early position + start notes + box profile
- Ensemble model: adjusted speed, early pace, box, track/distance, form, trainer and freshness
- Market/fundamental blend with adjustable market weight
- Monte Carlo finishing-order simulation
- Win / Top-2 / Top-3 probabilities, fair odds, EV and confidence
- CSV export and per-runner explanations

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Community Cloud

- Repository: `sbachagian1101/horse-race-predictor`
- Branch: `greyhound-predictor`
- Main file: `app.py`

## Data note

The first version is designed around Racing & Sports Australian greyhound Enhanced Form text. Parser heuristics may need adjustment if R&S changes its page layout.
