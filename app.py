=====================================================================
PART 1. DEPENDENCIES & GLOBAL CORS FILTER
=====================================================================
import datetime
import requests
import re
from flask import Flask, jsonify, request

app = Flask(name)

@app.after_request
def after_request(response):
""" Vercel과 Render 간의 도메인 교차 출처 차단(CORS) 보안 정책을 허용합니다. """
response.headers.add('Access-Control-Allow-Origin', '*')
response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
return response

=====================================================================
PART 2. REAL-TIME STOCK CODE MAPPING ENGINE
=====================================================================
def get_stock_code_by_name(stock_name):
""" 한글 종목명을 실시간으로 네이버 서버에 매핑하여 6자리 거래소 표준 코드를 탈취합니다. """
search_url = f"https://naver.com{stock_name}&q_enc=euc-kr&st=1&frm=stock&r_format=json"
try:
response = requests.get(search_url, timeout=5)
search_data = response.json()
if "items" in search_data and len(search_data["items"]) > 0:
match_list = search_data["items"][0]
for item in match_list:
if item[0].replace(" ", "") == stock_name:
return item[1] # 6자리 종목 코드 추출
return None
except Exception as e:
print(f"Stock Code Mapping Failed: {str(e)}")
return None

=====================================================================
PART 3. QUANT ROLLING FORWARD EPS ENGINE
=====================================================================
class ForwardPricePredictor:
""" JP모건 금융공학 캘린더 계산 가이드라인에 따른 선형 보간 롤링 가중치 연산 클래스입니다. """
def init(self, eps_this_year, eps_next_year):
self.eps_this_year = eps_this_year if eps_this_year and eps_this_year > 0 else 1
self.eps_next_year = eps_next_year if eps_next_year and eps_next_year > 0 else self.eps_this_year

def calculate_daily_forward_eps(self, target_date):
""" 타겟 날짜가 윤년인지 평년인지 정밀 스캔하여 일별 선형 가중치를 계산합니다. """
if isinstance(target_date, str):
target_date = datetime.datetime.strptime(target_date, "%Y-%m-%d").date()
year = target_date.year
is_leap = (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)
total_days = 366 if is_leap else 365
day_of_year = target_date.timetuple().tm_yday
days_remaining = total_days - day_of_year

forward_eps = (self.eps_this_year * (days_remaining / total_days)) + (self.eps_next_year * (day_of_year / total_days))
return round(forward_eps, 2)

def predict_price(self, target_date, target_per):
""" 롤링 EPS와 멀티플을 결합하고 대한민국 주식시장 호가 단위(백원)로 반올림합니다. """
per_multiple = target_per if target_per and target_per > 0 else 10.0
fwd_eps = self.calculate_daily_forward_eps(target_date)
predicted_price = per_multiple * fwd_eps
return int(round(predicted_price, -2))

=====================================================================
PART 4. LIVE FINANCE WEB SCRAPER (CONSEN & COUNT)
=====================================================================
def get_live_financial_data(stock_code):
""" 네이버 증권 데이터를 실시간 슬라이싱하여 기관 추정치 개수와 EPS를 파싱합니다. """
headers = {
"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# 1. 실시간 마켓 현재가 수집
price_url = f"https://naver.com{stock_code}/integration"
current_price = 0
try:
price_res = requests.get(price_url, headers=headers, timeout=5)
price_data = price_res.json()
if "closePrice" in price_data:
current_price = int(price_data["closePrice"].replace(",", ""))
except Exception as e:
print(f"Live Price API Network Error: {str(e)}")

# 2. 기업실적분석 테이블 정밀 스캔 및 가이던스 추출
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

# 추정 기관 수(증권사 개수) 가로채기
count_match = re.search(r'추정기관수\s*<em[^>]>(\d+)</em>|추정기관수\s(\d+)', html_text)
if count_match:
cnt_str = count_match.group(1) if count_match.group(1) else count_match.group(2)
est_count = int(cnt_str)

# 시장 선행 PER 추출
per_match = re.search(r'선행\sPER.?<em[^>]*>([\d.]+)</em>', html_text, re.DOTALL)
if per_match:
per_multiple = float(per_match.group(1))

# 정규식 간섭을 차단하기 위한 EPS(원) 데이터 행 전용 슬라이싱 파서
eps_row_match = re.search(r'EPS(원).?</tr>', html_text, re.DOTALL)
if eps_row_match and est_count > 0:
eps_row_html = eps_row_match.group(0)
eps_values = re.findall(r'<td[^>]>([\d,-]+)</td>', eps_row_html)
if len(eps_values) >= 5:
val_this = eps_values[3].replace(",", "").strip() # 당해연도 컨센서스 위치
val_next = eps_values[4].replace(",", "").strip() # 차년도 컨센서스 위치
if val_this != '-' and val_next != '-':
eps_this = int(val_this)
eps_next = int(val_next)
is_consensus_exist = True
except Exception as e:
print(f"Financial Parsing Logic Exception: {str(e)}")

# 3. 컨센서스 공백 종목(소형주) 발생 시 시장 임플라이드 보정 알고리즘 가동
if not is_consensus_exist or est_count == 0 or not eps_this:
est_count = 0
is_consensus_exist = False
eps_this = int(current_price / 10.0) if current_price > 0 else 25000
eps_next = int(eps_this * 1.05)
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
PART 5. MAIN BUSINESS API CONTROLLER
=====================================================================
@app.route("/search", methods=["POST"])
def search_stock():
""" 프론트엔드의 비동기 통신을 수신하여 최종 예측 리포트를 패키징하는 라우터입니다. """
req_data = request.get_json()
if not req_data or "stock_name" not in req_data:
return jsonify({"success": False, "message": "Invalid Request Protocol"})

stock_name = req_data.get("stock_name", "").strip()
code = get_stock_code_by_name(stock_name)

if not code:
return jsonify({
"success": False,
"message": f"'{stock_name}'은(는) 한국거래소(KRX) 상장 사전에 존재하지 않습니다."
})

raw_data = get_live_financial_data(code)
if raw_data["current_price"] == 0:
return jsonify({"success": False, "message": "거래소 실시간 시세 패킷 동기화 실패"})

# 익일 일별 롤링 연산 가동
predictor = ForwardPricePredictor(
eps_this_year=raw_data["eps_this"],
eps_next_year=raw_data["eps_next"]
)

tomorrow_date = datetime.date.today() + datetime.timedelta(days=1)
predicted_price_val = predictor.predict_price(tomorrow_date, raw_data["per"])

return jsonify({
"success": True,
"stock_name": stock_name,
"stock_code": code,
"current_price": f"{raw_data['current_price']:,}원",
"predicted_price": f"{predicted_price_val:,}원",
"is_consensus": raw_data["is_consensus"],
"est_count": raw_data["est_count"]
})

=====================================================================
PART 6. INFRA DEPLOYMENT EXECUTER
=====================================================================
if name == "main":
# 클라우드 컨테이너 환경 전용 인프라 표준 포트 가동
app.run(host="0.0.0.0", port=10000, debug=True)

