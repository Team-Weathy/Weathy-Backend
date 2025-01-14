import time
from datetime import datetime
from io import BytesIO

from deep_translator import GoogleTranslator
from openai import OpenAI
client = OpenAI()

import requests
from PIL import Image
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from sticker.serializer import CreateStickerSerializer
from .models import Frame
from .s3_utils import upload_file_to_s3
import logging
from rest_framework.parsers import MultiPartParser

from .serializers import CreateFrameImgSerializer

logger = logging.getLogger("inframe")

class CreateFrameView(APIView):

    # MultiPartParser를 통해 파일 업로드를 처리
    parser_classes = [MultiPartParser]
    
    @swagger_auto_schema(
        operation_summary="프레임 생성 API",
        operation_description="form-data로 이미지 파일과 카메라 크기를 업로드하여 프레임을 생성합니다.",
        manual_parameters=[
            openapi.Parameter(
                'frameImg',
                openapi.IN_FORM,
                description='프레임 이미지 파일',
                type=openapi.TYPE_FILE,
                required=True
            ),
            openapi.Parameter(
                'cameraWidth',
                openapi.IN_FORM,
                description='카메라의 너비',
                type=openapi.TYPE_INTEGER,
                required=True
            ),
            openapi.Parameter(
                'cameraHeight',
                openapi.IN_FORM,
                description='카메라의 높이',
                type=openapi.TYPE_INTEGER,
                required=True
            ),
        ],
        responses={
            200: openapi.Response(
                description="성공적으로 프레임 생성",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "code": openapi.Schema(type=openapi.TYPE_STRING, description="응답 코드"),
                        "message": openapi.Schema(type=openapi.TYPE_STRING, description="응답 메시지"),
                        "data": openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                "frameId": openapi.Schema(type=openapi.TYPE_INTEGER, description="프레임 ID"),
                                "frameImgUrl": openapi.Schema(type=openapi.TYPE_STRING, description="프레임 이미지 URL"),
                            },
                        ),
                    },
                ),
            ),
            400: openapi.Response(
                description="요청 데이터 오류",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "code": openapi.Schema(type=openapi.TYPE_STRING, description="에러 코드"),
                        "status": openapi.Schema(type=openapi.TYPE_INTEGER, description="HTTP 상태 코드"),
                        "message": openapi.Schema(type=openapi.TYPE_STRING, description="에러 메시지"),
                    },
                ),
            ),
        },
    )
    def post(self, request):
        logger.info(f"Request Data: {request.data}")
        logger.info(f"Request Files: {request.FILES}")

        # form-data에서 값 가져오기
        cameraWidth = request.data.get("cameraWidth")
        cameraHeight = request.data.get("cameraHeight")
        frameImg = request.FILES.get("frameImg")

        # 필수 파라미터 확인
        if not cameraWidth or not cameraHeight:
            return Response(
                {
                    "code": "FRA_4001",
                    "status": 400,
                    "message": "카메라 크기 정보 누락",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not frameImg:
            return Response(
                {
                    "code": "FRA_4002",
                    "status": 400,
                    "message": "이미지 파일이 누락되었습니다.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # 이미지 저장 처리
            image_data = frameImg.read()
            img = Image.open(BytesIO(image_data))
            frameImgName = f"frame_{int(time.time())}.jpg"
            imgFile = BytesIO()
            img.save(imgFile, format="JPEG")
            imgFile.seek(0)

            frameImgUrl = upload_file_to_s3(
                file=imgFile,
                key=frameImgName,
                ExtraArgs={
                    "ContentType": "image/jpeg",
                    "ACL": "public-read",
                },
            )
            if not frameImgUrl:
                return Response(
                    {
                        "code": "FRA_5001",
                        "status": 500,
                        "message": "이미지 업로드 실패",
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            # 프레임 데이터 DB 저장
            frame = Frame.objects.create(
                frameUrl=frameImgName,
                cameraWidth=int(cameraWidth),
                cameraHeight=int(cameraHeight),
            )

            response_data = {
                "code": "FRA_2001",
                "message": "프레임 생성 성공",
                "data": {
                    "frameId": frame.frameId,
                    "frameImgUrl": frameImgUrl,
                },
            }
            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error creating frame: {str(e)}")
            response_data = {
                "code": "FRA_5002",
                "status": 500,
                "message": f"프레임 생성 실패: {str(e)}",
            }
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class CreateAiFrameView(APIView):
    @swagger_auto_schema(
        operation_summary="초기 프레임 배경 생성 API",
        operation_description="초기 프레임 배경 생성 페이지",
        request_body=CreateFrameImgSerializer,
        responses={
            201: openapi.Response(
                description="초기 프레임 배경 생성 성공",
                examples={
                    "application/json": {
                        "code": "FRA_2011",
                        "status": 201,
                        "message": "초기 프레임 배경 생성 성공",
                        "frameAiUrl": "https://example.com/stickers/generated_background.png"
                    }
                }
            ),
            400: openapi.Response(
                description="초기 프레임 배경 생성 실패",
                examples={
                    "application/json": {
                        "code": "FRA_4001",
                        "status": 400,
                        "message": "초기 프레임 배경 생성 실패"
                    }
                }
            ),
        }
    )
    def post(self, request):
        serializer = CreateFrameImgSerializer(data=request.data)

        if not serializer.is_valid():
            return Response({
                "code": "FRA_4001",
                "status": 400,
                "message": "유효하지 않은 데이터입니다.",
                "errors": serializer.errors,
            }, status=status.HTTP_400_BAD_REQUEST)

        validated_data = serializer.validated_data
        prompt = validated_data.get('prompt')

        if prompt:
            translator = GoogleTranslator(source='ko', target='en')
            english_prompt = translator.translate(prompt)

            detailed_prompt = (
                f"A animated-style illustration of {english_prompt}, "
                f"with the text {english_prompt} creatively incorporated into the borders of the image. "
            )

            response = client.images.generate(
                prompt=detailed_prompt,
                n=1,
                size="1024x1024"
            )
            generated_image_url = response.data[0].url

            generated_image = self.download_image(generated_image_url)

            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            file_name = f"ai-frames/{prompt[:30].replace(' ', '_')}_{timestamp}.png"

            frame_url = self.upload_to_s3(generated_image, file_name)

        else:
            return Response({
                "code": "FRA_4001",
                "status": 400,
                "message": "유효하지 않은 데이터입니다.",
            }, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "code": "FRA_2001",
            "status": 201,
            "message": "초기 프레임 배경 생성 완료",
            "frameAiUrl": frame_url
        }, status=status.HTTP_201_CREATED)

    def download_image(self, url):
        response = requests.get(url)
        response.raise_for_status()
        return BytesIO(response.content)
    def upload_to_s3(self, image, file_name):
        from django.core.files.storage import default_storage
        file_path = default_storage.save(file_name, image)
        return default_storage.url(file_path)
        
class FrameDetailView(APIView):
    @swagger_auto_schema(
        operation_summary="초기 프레임 조회 API",
        operation_description="프레임 ID를 기반으로 초기 프레임 URL을 반환합니다.",
        responses={
            200: openapi.Response(
                description="초기 프레임 조회 성공",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "code": openapi.Schema(type=openapi.TYPE_STRING, description="응답 코드"),
                        "message": openapi.Schema(type=openapi.TYPE_STRING, description="응답 메시지"),
                        "data": openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                "frameUrl": openapi.Schema(type=openapi.TYPE_STRING, description="프레임 URL"),
                            },
                        ),
                    },
                ),
            ),
            400: openapi.Response(
                description="초기 프레임 조회 실패",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "code": openapi.Schema(type=openapi.TYPE_STRING, description="에러 코드"),
                        "status": openapi.Schema(type=openapi.TYPE_INTEGER, description="HTTP 상태 코드"),
                        "message": openapi.Schema(type=openapi.TYPE_STRING, description="에러 메시지"),
                    },
                ),
            ),
        },
    )
    def get(self, request, frameId):
        """
        초기 프레임 조회 API
        프레임 ID를 기반으로 초기 프레임 URL을 반환합니다.
        """
        try:
            frame = Frame.objects.get(pk=frameId)
            logger.info(f"frame: {frame}")
            response_data = {
                "code": "FRA_2001",
                "message": "초기 프레임 조회 성공",
                "data": {
                    "frameId" : frame.frameId,
                    "frameUrl": frame.frameUrl,
                },
            }
            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error creating frame: {str(e)}")
            response_data = {
                "code": "FRA_5002",
                "status": 500,
                "message": f"프레임 생성 실패: {str(e)}",
            }
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
