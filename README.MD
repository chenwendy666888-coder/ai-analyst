# Pension AI Analyst

A Streamlit hackathon app for analysing a Defined Benefit pension fund, combining quantitative portfolio analysis with Azure OpenAI explanations.

## Features

- Matching/growth ETF allocation with interactive charts.
- Return, volatility, drawdown and funding-ratio comparisons.
- AI investment committee discussion.
- Stress scenarios with funding-ratio visualisations.
- Trustee Q&A grounded in calculated facts.
- Cached analytics and AI responses.

## Setup

```bash
git clone [https://github.com/chenwendy666888-coder/ai-analyst.git](https://github.com/chenwendy666888-coder/ai-analyst.git)
cd ai-analyst
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows activation:

```powershell
.\.venv\Scripts\Activate.ps1
```

Create `.env` in the project root:

```env
HACK_API_KEY=your_key
HACK_ENDPOINT=[https://your-resource.openai.azure.com/](https://your-resource.openai.azure.com/)
USE_FAKE_FACTS=0
```

Never commit `.env`. Azure deployment settings are configured in `llm.py`.

## Run

```bash
streamlit run app.py
```

Enter assets, annual payment and years, then click Run analysis.

If market-data files are missing:

```bash
python data.py
```

Set `USE_FAKE_FACTS=1` and restart for fixed demo data. Uncached AI responses still require Azure access.

## Project Structure

| File | Purpose |
|---|---|
| `app.py` | Dashboard |
| `engine.py` | Allocation, liabilities, metrics and projections |
| `stress.py` | Standard and custom stress calculations |
| `compare.py` | Portfolio comparisons |
| `llm.py` / `prompts.py` | AI integration and response caching |
| `data.py` | Market-data loading |
| `ENGINE_API.md` | Engine documentation |

## Testing

```bash
python test_all.py
```

Check the printed results; test Azure and dashboard features separately.

## Limitations

Uses historical returns and simplified assumptions—not forecasts. AI output may contain errors, and funding ratios do not guarantee future payments.

Educational hackathon project. Not financial advice.
