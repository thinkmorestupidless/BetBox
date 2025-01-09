# BetBox

## Quick Start

```
# create and use the virtual environment
python -m venv .venv
source .venv/bin/activate
pip freeze -r requirements.txt

# run the app
chainlit run app.py -w
```

Then just ask questions... there aren't too many endpoints hooked up to the Betfair API yet so you're pretty much limited to two questions:

1. Which sports can you bet on? (this is the list of `Event Types` in Betfair API parlance)
2. Which competitions are there for Event Type 'X' (e.g. for 'Soccer' there is Premier League, Serie A, La Liga, etc, etc)
