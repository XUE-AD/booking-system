import os
import uuid
import logging
from zoneinfo import ZoneInfo

from django.conf import settings
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/meetings.space.created',
]

TOKEN_PATH = os.path.join(settings.BASE_DIR, 'token.json')
CREDENTIALS_PATH = os.path.join(settings.BASE_DIR, 'credentials.json')


class GoogleCalendarService:

    @staticmethod
    def _get_service():
        """
        回傳已認證的 Google Calendar API 服務。
        Token 過期時自動 refresh；無法自動 refresh 則 raise RuntimeError。
        token.json 需先在本機透過 test_google_meet.py 產生。
        """
        creds = None
        if os.path.exists(TOKEN_PATH):
            creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                with open(TOKEN_PATH, 'w') as token_file:
                    token_file.write(creds.to_json())
            else:
                raise RuntimeError(
                    "Google Calendar 憑證遺失或過期，無法自動更新。"
                    "請在本機執行 test_google_meet.py 重新產生 token.json。"
                )

        return build('calendar', 'v3', credentials=creds)

    @staticmethod
    def create_event(title, description, start_time, end_time,
                     attendee_emails, timezone='Asia/Taipei'):
        """
        建立 Google Calendar 活動並附帶 Google Meet 連結。

        Args:
            title (str):             活動標題。
            description (str):       活動描述。
            start_time (datetime):   開始時間（Django DateTimeField，UTC）。
            end_time (datetime):     結束時間（UTC）。
            attendee_emails (list):  參與者 email 清單。
            timezone (str):          IANA 時區字串，預設 Asia/Taipei。

        Returns:
            dict:
                'meet_link'  (str | None): Google Meet URL。
                'event_id'   (str):        Google Calendar 活動 ID。
        """
        service = GoogleCalendarService._get_service()

        taipei_tz = ZoneInfo(timezone)
        start_local = start_time.astimezone(taipei_tz)
        end_local = end_time.astimezone(taipei_tz)
        start_str = start_local.strftime('%Y-%m-%dT%H:%M:%S')
        end_str = end_local.strftime('%Y-%m-%dT%H:%M:%S')

        event_body = {
            'summary': title,
            'description': description,
            'start': {'dateTime': start_str, 'timeZone': timezone},
            'end': {'dateTime': end_str, 'timeZone': timezone},
            'attendees': [{'email': email} for email in attendee_emails if email],
            'conferenceData': {
                'createRequest': {
                    'requestId': f"meet-{uuid.uuid4().hex}",
                    'conferenceSolutionKey': {'type': 'hangoutsMeet'},
                }
            },
        }

        event = service.events().insert(
            calendarId='primary',
            body=event_body,
            conferenceDataVersion=1,
        ).execute()

        return {
            'meet_link': event.get('hangoutLink'),
            'event_id': event.get('id'),
        }

    @staticmethod
    def get_initial_sync_token():
        """取得初始 sync token（用於之後 get_changed_events）。"""
        service = GoogleCalendarService._get_service()
        response = service.events().list(calendarId='primary').execute()
        return response.get('nextSyncToken')

    @staticmethod
    def watch_calendar(callback_url, channel_id, expiration_days=7):
        """向 Google Calendar 註冊 Webhook。"""
        import time
        from django.conf import settings as django_settings

        service = GoogleCalendarService._get_service()
        expiration_ms = int((time.time() + expiration_days * 86400) * 1000)

        body = {
            'id': channel_id,
            'type': 'web_hook',
            'address': callback_url,
            'token': django_settings.CALENDAR_WEBHOOK_TOKEN,
            'expiration': expiration_ms,
        }
        return service.events().watch(calendarId='primary', body=body).execute()

    @staticmethod
    def stop_watching(channel_id, resource_id):
        """取消 Webhook 訂閱。"""
        service = GoogleCalendarService._get_service()
        service.channels().stop(body={
            'id': channel_id,
            'resourceId': resource_id,
        }).execute()

    @staticmethod
    def get_changed_events(sync_token):
        """回傳自 sync_token 以來有異動的事件 list 和新的 sync_token。"""
        service = GoogleCalendarService._get_service()
        response = service.events().list(
            calendarId='primary',
            syncToken=sync_token,
        ).execute()
        return response.get('items', []), response.get('nextSyncToken')
