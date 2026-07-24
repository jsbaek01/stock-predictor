

=====================================================================
1. 필수 의존성 패키지 및 클라우드 CORS 보안 표준 필터
=====================================================================
import datetime
import requests
import re
from flask import Flask, jsonify, request

app = Flask(name)

[CORS 전역 우회 필터]
프론트엔드(Vercel)와 백엔드(Render)가 서로 다른 클라우드 주소에서
소통할 때 브라우저 보안 정책으로 발생하는 차단 에러를 완벽하게 예방합니다.
@app.after_request
def after_request(response):
response.headers.add('Access-Control-Allow-Origin', '*')
response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
return response

=====================================================================
2. 국내 전종목 실시간 네이버 통합검색 및 표준 코드 추출 엔진
=====================================================================
def get_stock_code_by_name(stock_name):
"""
네이버 증권 내부 검색 서버를 직접 노크하여 사용자가 입력한 한글 종목명을
거래소 등록용 6자리 표준 종목코드로 실시간 변환 및 유효성 검증을 수행합니다.
"""
# 네이버 파이낸스 자동완성 및 통합검색 백엔드 API 포맷
search_url = f"https://naver.com{stock_name}&q_enc=euc-kr&st=1&frm=stock&r_format=json"

try:
response = requests.get(search_url, timeout=5)
search_data = response.json()

# 검색어 리스트와 반환 노드가 완벽히 살아있는지 2중 매칭 검증
if "items" in search_data and len(search_data["items"]) > 0 and len(search_data["items"][0]) > 0:
match_list = search_data["items"][0]
for item in match_list:
# 사용자가 입력한 글자와 시장 상장명이 공백 없이 정확히 일치하는 노드 타겟팅
if item[0][0].replace(" ", "") == stock_name:
return item[1][0] # 6자리 종목코드 추출 성공 (예: '005930')
return None # 검색 결과가 없거나 시장에 미상장된 종목
except Exception as e:
print(f"종목 식별 엔진 치명적 예외 발생: {str(e)}")
return None

=====================================================================
3. JP모건 금융공학 관점의 정밀 일별 롤링 12M Forward EPS 수식 엔진
=====================================================================
class ForwardPricePredictor:
def init(self, eps_this_year, eps_next_year):
# 데이터 공백으로 인한 제로 디비전(Zero Division) 계산 오류 방어막
self.eps_this_year = eps_this_year if eps_this_year and eps_this_year > 0 else 1
self.eps_next_year = eps_next_year if eps_next_year and eps_next_year > 0 else self.eps_this_year

def calculate_daily_forward_eps(self, target_date):
""" 타겟 날짜 기준 연중 잔여 일수 비율을 연산하여 일별 선형 보간 가중치를 적용합니다. """
if isinstance(target_date, str):
target_date = datetime.datetime.strptime(target_date, "%Y-%m-%d").date()

year = target_date.year
# 캘린더 일수 추적을 위한 윤년/평년 판별 알고리즘
is_leap = (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)
total_days = 366 if is_leap else 365

day_of_year = target_date.timetuple().tm_yday
days_remaining = total_days - day_of_year

# 12M Forward 선형 가중 가이던스 수식 적용
forward_eps = (
self.eps_this_year * (days_remaining / total_days)
) + (
self.eps_next_year * (day_of_year / total_days)
)
return round(forward_eps, 2)

def predict_price(self, target_date, target_per):
""" 산출된 미래 지향 롤링 EPS에 실시간 멀티플(PER)을 곱해 익일 최종 예측 주가를 도출합니다. """
per_multiple = target_per if target_per and target_per > 0 else 10.0

fwd_eps = self.calculate_daily_forward_eps(target_date)
predicted_price = per_multiple * fwd_eps

# 대한민국 거래소 호가 단위를 준수하기 위한 백 원 단위 반올림 (-2)
return int(round(predicted_price, -2))


=====================================================================
4. 네이버 증권 데이터 동적 파싱 엔진 (시세 및 추정 기관 수 추출)
=====================================================================
def get_live_financial_data(stock_code):
"""
네이버 증권 FnGuide 정밀 금융 가이드라인 전용 API를 직접 호출하여
타 태그와의 인덱스 간섭 없이 정확한 컨센서스 데이터와 추정기관수를 가로챕니다.
"""
headers = {
"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# [A. 실시간 현재가 수집]
price_url = f"https://naver.com{stock_code}/integration"
current_price = 0
try:
price_res = requests.get(price_url, headers=headers, timeout=5)
price_data = price_res.json()
if "closePrice" in price_data:
current_price = int(price_data["closePrice"].replace(",", ""))
except Exception as e:
print(f"실시간 시세 수집 오류: {str(e)}")

# [B. FnGuide 전용 서브 쿼리 데이터셋 파싱]
# 테이블 인덱스가 꼬이지 않는 네이버 증권 내부의 정밀 컨센서스 타겟 주소입니다.
enc_url = f"https://xn--fn-og4a5azl.com{stock_code}" # 내부 맵핑 우회용 주소 패턴
finance_url = f"https://naver.com{stock_code}"

eps_this = None
eps_next = None
per_multiple = None
est_count = 0
is_consensus_exist = False

try:
finance_res = requests.get(finance_url, headers=headers, timeout=5)
finance_res.encoding = 'euc-kr'
html_text = finance_res.text

# 1. 추정 기관 수 정밀 추출
count_match = re.search(r'추정기관수\s*<em[^>]>(\d+)</em>|추정기관수\s(\d+)', html_text)
if count_match:
# 매칭된 그룹 중 존재하는 숫자를 선택
cnt_str = count_match.group(1) if count_match.group(1) else count_match.group(2)
est_count = int(cnt_str)

# 2. 선행 PER 멀티플 추출
per_match = re.search(r'선행\sPER.?<em[^>]*>([\d.]+)</em>', html_text, re.DOTALL)
if per_match:
per_multiple = float(per_match.group(1))

# 3. 2026년 및 2027년 컨센서스 EPS 데이터 정밀 타겟팅 추출
# 다른 태그들과 섞이지 않도록 재무제표 내의 "EPS(원)" 행의 데이터 세그먼트만 정확히 잘라냅니다.
eps_row_match = re.search(r'EPS(원).?</tr>', html_text, re.DOTALL)
if eps_row_match and est_count > 0:
eps_row_html = eps_row_match.group(0)
eps_values = re.findall(r'<td[^>]>([\d,-]+)</td>', eps_row_html)

# 컨센서스 타임라인 배열에서 당해연도(2026)와 차년도(2027) 실적 칼럼 위치 가로채기
if len(eps_values) >= 5:
# 하이픈(-) 기호 처리 및 예외 방어
val_this = eps_values[3].replace(",", "").strip()
val_next = eps_values[4].replace(",", "").strip()

if val_this != '-' and val_next != '-':
eps_this = int(val_this)
eps_next = int(val_next)
is_consensus_exist = True

except Exception as e:
print(f"금융 데이터 파이프라인 연산 실패 예외 발생: {str(e)}")

# [C. 데이터 부재 시 퀀트 방어 알고리즘 (시장 임플라이드 모델) 가동]
# 컨센서스가 없거나 데이터가 오염되었을 경우 현재가 기반 역산 셋팅
if not is_consensus_exist or est_count == 0 or not eps_this:
est_count = 0
is_consensus_exist = False
# 현재 주가가 249,500원인 경우, 시장 부여 선행 EPS를 약 24,950원으로 역산하여
# 현재가 밴드 라인 내에서 익일 주가가 움직이도록 완벽한 안전 자산을 구축합니다.
eps_this = int(current_price / 10.0) if current_price > 0 else 25000
eps_next = int(eps_this * 1.05) # 보수적인 5% 성장률 셋팅
if not per_multiple or per_multiple <= 0:
per_multiple = 10.0

return {
"current_price": current_price,
"eps_this": eps_this,
"eps_next": eps_next,
"per": per_multiple,
"est_count": est_count,
"is_consensus": is_consensus_exist
}




=====================================================================
5. 비즈니스 라우팅 API 컨트롤러
=====================================================================
@app.route("/search", methods=["POST"])
def search_stock():
""" 프론트엔드의 비동기 비호출 요청을 수신하여 퀀트 보정 연산을 수행하는 관문입니다. """
req_data = request.get_json()
if not req_data or "stock_name" not in req_data:
return jsonify({"success": False, "message": "유효하지 않은 데이터 세그먼트 요청입니다."})

stock_name = req_data.get("stock_name", "").strip()

# 1단계의 동적 전종목 식별 엔진 작동
code = get_stock_code_by_name(stock_name)

# [예외 처리 팝업 분기] 시장에 상장되지 않은 종목 스크리닝
if not code:
return jsonify({
"success": False,
"message": f"'{stock_name}'은(는) 한국 거래소(KRX) 상장 사전에 존재하지 않는 종목입니다. 정확한 명칭을 입력해 주세요."
})

# 데이터 레이어 실시간 패치
raw_data = get_live_financial_data(code)

if raw_data["current_price"] == 0:
return jsonify({"success": False, "message": "거래소 실시간 시세 네트워크 패킷 수집에 실패했습니다. 잠시 후 재시도 바랍니다."})

# 익일 일별 롤링 가중 알고리즘 엔진 조립 및 시동
predictor = ForwardPricePredictor(
eps_this_year=raw_data["eps_this"],
eps_next_year=raw_data["eps_next"]
)

# 서버 시간 기준 익일(내일) 날짜 산출 및 대입
tomorrow_date = datetime.date.today() + datetime.timedelta(days=1)
predicted_price_val = predictor.predict_price(tomorrow_date, raw_data["per"])

# 프론트엔드로 최종 패키지 송신 (기관 수와 플래그 포함)
return jsonify({
"success": True,
"stock_name": stock_name,
"stock_code": code,
"current_price": f"{raw_data['current_price']:,}원",
"predicted_price": f"{predicted_price_val:,}원",
"is_consensus": raw_data["is_consensus"], # 💡 분기용 플래그
"est_count": raw_data["est_count"] # 💡 증권사 개수 세부 숫자
})

=====================================================================
6. 인프라 데몬 구동 엔진
=====================================================================
if name == "main":
# Render 및 클라우드 컨테이너 환경 표준 포트인 10000 오픈
app.run(host="0.0.0.0", port=10000, debug=True)

