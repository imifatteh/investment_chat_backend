import requests

from django.conf import settings
from polygon import RESTClient

client = RESTClient(api_key=settings.POLYGON_API_KEY)


# def get_aggs_data(ticker: str, time_range: str) -> dict:
#     # Determine the timespan based on the selected filter
#     if time_range == "1D":
#         timespan = "minute"
#     elif time_range == "1W":
#         timespan = "hour"
#     elif time_range == "1M":
#         timespan = "day"
#     elif time_range == "1Y":
#         timespan = "week"
#     else:
#         timespan = "minute"

#     aggs = []
#     for a in client.list_aggs(
#         ticker=ticker,
#         multiplier=2,
#         timespan=timespan,
#         from_="2022-11-01",
#         to="2024-11-02",
#         limit=50000,
#     ):
#         aggs.append(a.__dict__)

#     print(client.get_ticker_details(ticker).name)
#     company_name = client.get_ticker_details(ticker).name
#     return {"data": aggs, "company_name": company_name}


def get_aggs_data(ticker: str, time_range: str) -> dict:
    # Define your API key (make sure to store it securely, e.g. in environment variables)
    API_KEY = settings.POLYGON_API_KEY
    BASE_URL = settings.POLYGON_BASE_URL

    # Determine the timespan and multiplier based on the selected filter
    if time_range == "1D":
        timespan = "day"
        multiplier = 1
    elif time_range == "1W":
        timespan = "week"
        multiplier = 1
    elif time_range == "1M":
        timespan = "month"
        multiplier = 1
    elif time_range == "3M":
        timespan = "month"
        multiplier = 3
    elif time_range == "6M":
        timespan = "month"
        multiplier = 6
    elif time_range == "1Y":
        timespan = "year"
        multiplier = 1
    else:
        timespan = "minute"
        multiplier = 1

    # Hardcoded 'from' and 'to' dates (format: YYYY-MM-DD)
    from_date = "2021-11-01"
    to_date = "2024-11-02"

    # Construct the URL to fetch data
    url = f"{BASE_URL}/{ticker}/range/{multiplier}/{timespan}/{from_date}/{to_date}"

    # Add your API key as a query parameter
    params = {"apiKey": API_KEY}

    try:
        # Make the GET request to the API
        response = requests.get(url, params=params)
        response.raise_for_status()
        # Get the response data
        data = response.json()
        # Extract the aggregated data from the response
        aggs = data.get("results", [])
        return {"data": aggs}
    except requests.exceptions.RequestException as e:
        # Handle errors (e.g., network errors, API errors)
        return {"error": str(e)}


# # Get Last Trade
# trade = client.get_last_trade(ticker=ticker)
# print(trade)

# # # List Trades
# trades = client.list_trades(ticker="AAPL", timestamp="2022-12-10")
# for trade in trades:
#     print(trade)

# # Get Last Quote
# quote = client.get_last_quote(ticker=ticker)
# print(quote)

# # List Quotes
# quotes = client.list_quotes(ticker=ticker, timestamp="2022-01-04")
# for quote in quotes:
#     print(quote)
