from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status

from polygon_ai.utils import get_aggs_data


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def aggs_data_view(request, ticker: str):
    if request.method == "GET":
        time_range = request.GET.get("time_range")
        try:
            data = get_aggs_data(ticker, time_range)  # Get data based on the ticker
            return Response(
                data, status=status.HTTP_200_OK
            )  # Respond with the data in JSON format
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    else:
        return Response(
            {"error": "Invalid request method"}, status=status.HTTP_400_BAD_REQUEST
        )
