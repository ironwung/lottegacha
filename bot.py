from flask import Flask, request, jsonify
import requests
import json
import os
import random
from datetime import datetime
import sys
from dotenv import load_dotenv

load_dotenv(override=True)

app = Flask(__name__)

# ================= 설정 영역 =================
BOT_ACCESS_TOKEN = os.getenv("BOT_ACCESS_TOKEN", "")
API_URL = "https://webexapis.com/v1/messages"

# 데이터 (이전과 동일)
user_db = {}
CHARACTERS = [
    {"name": "👑 황금망토 로티", "grade": "SSR", "score": 100, "img": "https://i.imgur.com/example_ssr.png"},
    {"name": "🎢 자이로드롭 로티", "grade": "SR", "score": 70, "img": "https://i.imgur.com/example_sr.png"},
    {"name": "🐻 화이트 베어", "grade": "R", "score": 40, "img": "https://i.imgur.com/example_r.png"},
    {"name": "🎈 놓쳐버린 풍선", "grade": "N", "score": 5, "img": "https://via.placeholder.com/300?text=Balloon"},
]
WEIGHTS = [5, 15, 30, 50]

# ================= 로그 출력 헬퍼 =================
def log(msg):
    """강제로 터미널에 출력하는 함수"""
    print(f"[LOG] {msg}", file=sys.stdout, flush=True)

# ================= 기능 함수 =================
def send_message(room_id, text):
    headers = {"Authorization": f"Bearer {BOT_ACCESS_TOKEN}", "Content-Type": "application/json"}
    payload = {"roomId": room_id, "text": text}
    res = requests.post(API_URL, headers=headers, json=payload)
    log(f"메시지 전송 결과: {res.status_code} / {res.text}")

def send_adaptive_card(room_id, character, remaining_tickets):
    color = "Good" if character['grade'] in ['SSR', 'SR'] else "Warning"
    card_content = {
        "type": "AdaptiveCard", "$schema": "http://adaptivecards.io/schemas/adaptive-card.json", "version": "1.2",
        "body": [
            {"type": "TextBlock", "text": "🎉 뽑기 결과!", "size": "Large", "weight": "Bolder", "color": "Accent"},
            {"type": "Image", "url": character['img'], "size": "Stretch", "height": "300px"},
            {"type": "TextBlock", "text": f"[{character['grade']}] {character['name']}", "size": "Medium", "weight": "Bolder", "color": color},
            {"type": "TextBlock", "text": f"남은 티켓: {remaining_tickets}장", "isSubtle": True}
        ],
        "actions": [{"type": "Action.Submit", "title": "🎲 다시 뽑기", "data": { "command": "뽑기" }}]
    }
    
    headers = {"Authorization": f"Bearer {BOT_ACCESS_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "roomId": room_id, 
        "markdown": "결과 확인", 
        "attachments": [{"contentType": "application/vnd.microsoft.card.adaptive", "content": card_content}]
    }
    res = requests.post(API_URL, headers=headers, json=payload)
    log(f"카드 전송 결과: {res.status_code} (200이 아니면 실패)")
    if res.status_code != 200:
        log(f"에러 상세: {res.text}")

# ================= 메인 로직 =================
@app.route('/', methods=['POST'])
def webhook():
    log("=== 1. Webhook 요청 도착 ===")
    
    try:
        json_data = request.json
        data = json_data.get('data', {})
        person_email = data.get('personEmail', '')
        room_id = data.get('roomId')
        msg_id = data.get('id')

        log(f"요청자: {person_email}")

        # 내(봇)가 보낸 메시지면 무시
        if "webex.bot" in person_email: 
            log("봇 자신의 메시지이므로 무시합니다.")
            return "OK", 200

        # DB 초기화
        if person_email not in user_db:
            user_db[person_email] = {"tickets": 10, "last_refill": datetime.now().strftime("%Y-%m-%d"), "weekly_best_score": 0}

        # 명령어 파악
        command = ""
        
        # A. 버튼 클릭(Attachment Action)인 경우
        if 'inputs' in data:
            log("유형: 버튼 클릭")
            command = data['inputs'].get('command', '')
        
        # B. 일반 메시지인 경우 (여기서 에러가 많이 납니다!)
        else:
            log(f"유형: 일반 메시지 (ID: {msg_id}) -> 내용 조회 시도")
            headers = {"Authorization": f"Bearer {BOT_ACCESS_TOKEN}"}
            
            # [핵심] 메시지 내용 가져오기
            res = requests.get(f"{API_URL}/{msg_id}", headers=headers)
            
            if res.status_code == 200:
                msg_body = res.json()
                command = msg_body.get('text', '')
                log(f"메시지 내용 조회 성공: {command}")
            else:
                log(f"❌ 메시지 조회 실패! 토큰을 확인하세요. (Status: {res.status_code})")
                log(f"Webex 응답: {res.text}")
                return "Error fetching message", 200

        # 로직 실행
        if "어드벤쳐" in command:
            log("명령어 인식: 어드벤쳐 입장")
            send_message(room_id, f"🎢 {person_email.split('@')[0]}님 환영합니다! (티켓: {user_db[person_email]['tickets']}장)")
            
        elif "뽑기" in command:
            log("명령어 인식: 뽑기")
            if user_db[person_email]["tickets"] > 0:
                user_db[person_email]["tickets"] -= 1
                picked = random.choices(CHARACTERS, weights=WEIGHTS, k=1)[0]
                send_adaptive_card(room_id, picked, user_db[person_email]["tickets"])
            else:
                send_message(room_id, "티켓 부족")
        
        else:
            log(f"알 수 없는 명령어: {command}")

    except Exception as e:
        log(f"❌ 코드 실행 중 치명적 오류 발생: {str(e)}")

    return "OK", 200

if __name__ == '__main__':
    # -u 옵션 없이 실행해도 출력되도록 flush 처리했지만,
    # 실행할 때 `python -u bot.py` 로 실행하는 것이 가장 확실합니다.
    app.run(host='0.0.0.0', port=5000)
