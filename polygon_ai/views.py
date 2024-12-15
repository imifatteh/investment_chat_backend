from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from polygon_ai.utils import get_aggs_data


def aggs_data_view(request, ticker: str):
    if request.method == "GET":
        time_range = request.GET.get("time_range")
        try:
            data = get_aggs_data(ticker, time_range)  # Get data based on the ticker
            return JsonResponse(
                data, safe=False
            )  # Respond with the data in JSON format
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
    else:
        return JsonResponse({"error": "Invalid request method"}, status=400)
