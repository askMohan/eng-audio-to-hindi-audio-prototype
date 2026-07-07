from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from sessions.serializers import SessionCreateSerializer
from sessions.services import SessionService


class CreateSessionView(APIView):
    def post(self, request):
        serializer = SessionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session = SessionService().create_session(serializer.to_service_data())
        stream_path = "/ws/sessions/%s/stream/" % session.id
        stream_url = request.build_absolute_uri(stream_path).replace("http://", "ws://").replace(
            "https://", "wss://"
        )
        return Response(
            {
                "sessionId": session.id,
                "streamUrl": stream_url,
                "expiresAt": session.expires_at,
            },
            status=status.HTTP_201_CREATED,
        )

