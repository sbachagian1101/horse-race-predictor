# RaceParsePredict — Streamlit

Browser version of the RaceParsePredict desktop app.

## What it does

1. Paste the full **Racing & Sports Enhanced Form** page text.
2. Parse the race header and runner-level form data.
3. Review parsed horse / jockey / trainer / odds / form fields.
4. Run the existing market + fundamentals prediction engine.
5. View predicted finishing order, win and Top-3 probabilities, fair odds, EV, confidence and runner explanations.
6. Download parsed data and predictions as CSV.

## Run locally

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

## Deploy on Streamlit Community Cloud

Create a new app and select this GitHub repository, branch `main`, and entry point `app.py`. No secrets are required.

## Files

- `app.py` — Streamlit user interface
- `rs_parser.py` — Racing & Sports Enhanced Form paste parser
- `model.py` — prediction engine
- `requirements.txt` — Python dependencies
- `.streamlit/config.toml` — Streamlit theme/server settings

## Model note

The prediction engine uses market de-vigging, a standardized fundamental score, a market/fundamental probability blend and Monte Carlo finishing-order simulation. It is a decision-support model; predicted probabilities, confidence and EV are not guarantees of race results.
