# ThisData

KJB를 건드리지 않고 별도 폴더로 만든 ThisData 커뮤니티 앱입니다.

## 포함 기능
- 여러 서버 생성/가입 (공개 서버 직접 가입, 공개/비공개 모두 초대 링크 가입)
- 서버 리스트 + 채널 리스트 UI (디스코드 스타일 3단 레이아웃)
- 서버 생성자가 해당 서버 관리자(admin)
- 서버별 관리자 분리 (서버마다 권한 독립)
- 관리자 밴 기능
- 친구 요청/수락 + DM
- 봇 계정 생성 및 API 토큰으로 메시지 읽기/쓰기
- 상점/KC/알림 시스템 제외

## 실행
```bash
cd ThisData
python run.py
```

## 봇 API 예시
```bash
curl -H "Authorization: Bearer <BOT_TOKEN>" "http://localhost:5050/api/bot/messages?channel_id=1"

curl -X POST -H "Authorization: Bearer <BOT_TOKEN>" -H "Content-Type: application/json" \
  -d '{"channel_id":1, "content":"hello from bot"}' \
  http://localhost:5050/api/bot/messages
```
