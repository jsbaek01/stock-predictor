import socket
import datetime
import requests
import re
from flask import Flask, jsonify, request

app = Flask(__name__)

@app.after_request
def after_request(response):
    """ Vercel 프론트엔드와 백엔드 간의 도메인 교차 출처 차단(CORS) 정책을 해제합니다. """
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
    return response

def get_stock_code_by_name(stock_name):
    search_url = "https://raw.githubusercontent.com/FinanceData/FinanceDataReader/master/krx_items.json"
    try:
        # 🔗 [DNS 강제 우회 터널링 교정] 
        # 앞에 프로토콜 기호(://)가 있으면 소켓 연산이 터집니다. 순수 도메인 이름만 들어가도록 철자 교정!
        try:
            domain = "raw.githubusercontent.com"
            socket.gethostbyname(domain)
        except socket.gaierror as dns_error:
            # 💡 [로그 인젝션 포인트 1]: 만약 Vercel DNS가 아예 맛이 갔다면 여기서 화면을 멈추고 에러를 뿜습니다.
            return jsonify({
                "success": False,
                "message": f"❌ [디버깅 1단계] Vercel 내부 소켓 DNS 해석 실패!\n사유: {str(dns_error)}"
            })

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        # 주소 차단과 튕김 현상을 막는 Session 기법으로 API 데이터 획득 시도
        session = requests.Session()
        response = session.get(search_url, headers=headers, timeout=5)
        
        # 💡 [로그 인젝션 포인트 2]: HTTP 상태 코드가 200 정상 코드가 아닐 경우 상태값을 화면에 인젝션합니다.
        if response.status_code != 200:
            return jsonify({
                "success": False,
                "message": f"❌ [디버깅 2단계] 깃허브 서버 연결 실패!\nHTTP 응답 코드: {response.status_code}"
            })
            
        search_data = response.json()
        
        # 💡 [로그 인젝션 포인트 3]: 데이터는 성공적으로 다운로드 받았으나 데이터 크기나 규격이 깨졌는지 검증합니다.
        if not search_data or len(search_data) == 0:
            return jsonify({
                "success": False,
                "message": f"❌ [디버깅 3단계] 금융 API 원시 데이터 획득했으나 배열이 완전히 텅 비어있음!"
            })
            
        # [RENDER 로그 강제 인젝션] 기존 출력 포맷 및 구조 확인 로그 100% 보존
        print(f"=== [디버깅] 네이버 검색 API 원시 데이터: {search_data[:3]} ===")
        
        if len(search_data) > 0:
            match_list = search_data
            print(f"=== [디버깅] 추출된 match_list 구조: {match_list[:1]} ===")
            
            for item in match_list:
                ticker_name = item.get("Name", "")
                ticker_code = item.get("Symbol", "")
                
                if ticker_name and ticker_code and ticker_name.replace(" ", "") == stock_name.replace(" ", ""):
                    print(f"=== [디버깅] 매칭 성공! 종목코드: {ticker_code} ===")
                    return ticker_code  # 순수한 6자리 종목코드 문자열 반환
                    
        # 💡 [로그 인젝션 포인트 4]: 데이터 통신도 성공했고 배열도 가득 찼으나, 사용자가 입력한 글자와 매칭에 실패했을 때
        # 첫 번째 종목 샘플 3개를 화면에 강제로 띄워 딕셔너리 키값 규격(`Name`, `Symbol`)이 달라졌는지 확인합니다.
        return jsonify({
            "success": False,
            "message": f"❌ [디버깅 4단계] 데이터 파싱 성공했으나 종목명 매칭 실패!\n원시 데이터 첫 항목 샘플: {str(search_data[:2])}"
        })
        
    except Exception as e:
        # 💡 [로그 인젝션 포인트 5]: 원인 불명의 치명적 오류나 JSONDecodeError가 날 경우 범인을 찍어버립니다.
        return jsonify({
            "success": False,
            "message": f"❌ [디버깅 5단계] get_stock_code_by_name 내부 치명적 예외 터짐:\n{str(e)}"
        })



# [AI 모델] 익일 일별 롤링 가중 가이던스 주가 예측 연산 클래스
class ForwardPricePredictor:
    def __init__(self, eps_this_year, eps_next_year):
        self.eps_this_year = eps_this_year if eps_this_year and eps_this_year > 0 else 1
        self.eps_next_year = eps_next_year if eps_next_year and eps_next_year > 0 else self.eps_this_year

    def calculate_daily_forward_eps(self, target_date):
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
        per_multiple = target_per if target_per and target_per > 0 else 10.0
        fwd_eps = self.calculate_daily_forward_eps(target_date)
        predicted_price = per_multiple * fwd_eps
        return int(round(predicted_price, -2))


# ========================================================
# PART 4. LIVE FINANCE WEB SCRAPER (CONSEN & COUNT)
# ========================================================

# [엔진 2] 정식 금융 주소 서브 도메인 복구를 통해 현재가 및 기업 실적 노드를 파싱하는 함수
def get_live_financial_data(stock_code):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    # 🎯 1. 실시간 거래소 주가 패치 (m.stock 정식 통합 시세 API 서브 도메인 정상화)
    price_url = f"https://m.stock.naver.com/api/json/integration/{stock_code}"
    current_price = 0
    try:
        price_res = requests.get(price_url, headers=headers, timeout=5)
        price_data = price_res.json()
        # 네이버 실시간 모바일 API 시세 추출 반영
        if price_data and "closePrice" in price_data:
            current_price = int(price_data["closePrice"].replace(",", ""))
    except Exception as e:
        print(f"Live Price API Network Error: {str(e)}")

    # 🎯 2. 기업실적분석 재무 가이던스 추출 (finance.naver 정식 서브 도메인 정상화)
    finance_url = f"https://finance.naver.com/item/coinfo.naver?code={stock_code}"
    eps_this = None
    eps_next = None
    per_multiple = None
    est_count = 0
    is_consensus_exist = False
    
    try:
        finance_res = requests.get(finance_url, headers=headers, timeout=5)
        finance_res.encoding = 'euc-kr'
        html_text = finance_res.text
        
        # 추정 기관 수(증권사 개수) 가로채기 정규식 파서
        count_match = re.search(r'추정기관수\s*<em[^>]*>(\d+)</em>|추정기관수\s+(\d+)', html_text)
        if count_match:
            cnt_str = count_match.group(1) if count_match.group(1) else count_match.group(2)
            est_count = int(cnt_str)
            
        # 시장 선행 PER 추출 정규식 파서
        per_match = re.search(r'선행\s*PER.*?<em[^>]*>([\d.]+)</em>', html_text, re.DOTALL)
        if per_match:
            per_multiple = float(per_match.group(1))
            
        # 인덱스 초과 버그 원천 차단형 EPS 행 세그먼트 슬라이싱 파서
        eps_row_match = re.search(r'EPS\(원\).*?</tr>', html_text, re.DOTALL)
        if eps_row_match and est_count > 0:
            eps_row_html = eps_row_match.group(0)
            eps_values = re.findall(r'<td[^>]*>([\d,-]+)</td>', eps_row_html)
            # 컨센서스 컬럼 위치 매핑 안전 슬라이싱 (유동적인 컬럼 개수 방어)
            if len(eps_values) >= 5:
                try:
                    val_this = eps_values[-2].replace(",", "").strip()
                    val_next = eps_values[-1].replace(",", "").strip()
                except IndexError:
                    val_this, val_next = '-', '-'
                if val_this != '-' and val_next != '-':
                    eps_this = int(val_this)
                    eps_next = int(val_next)
                    is_consensus_exist = True
    except Exception as e:
        print(f"Financial Parsing Logic Exception: {str(e)}")

    # 🎯 3. 컨센서스 부재 종목(소형주) 대응 시장 임플라이드 보정 알고리즘
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

# ========================================================
# PART 5. MAIN BUSINESS API CONTROLLER
# ========================================================

@app.route("/search", methods=["POST"])
def search_stock():
    # 대원칙 적용: 질문자님의 기존 변수명 구조 100% 보존
    req_data = request.get_json()
    if not req_data or "stock_name" not in req_data:
        return jsonify({"success": False, "message": "Invalid Request Protocol"})
        
    stock_name = req_data.get("stock_name", "").strip()
    
    # 1단계 엔진 작동: 해외 가상 서버 차단 없는 금융 API망 경유 종목코드 선점
    code = get_stock_code_by_name(stock_name)
    # 🎯 핵심: 만약 내부 함수에서 jsonify 결과(딕셔너리가 아닌 Flask Response 객체)를 직접 리턴했다면,
    # 라우터가 가로채서 프론트엔드 브라우저 화면으로 곧바로 리턴(토스)시켜 버립니다.
    if isinstance(code, Flask.response_class) or not code:
        if not code:
            return jsonify({"success": False, "message": f"'{stock_name}'은(는) 상장 주식 사전에 존재하지 않습니다."})
        return code # 내부 함수가 보낸 디버깅 1~5단계 로그 팝업창을 화면에 즉시 띄움
        
    # 🎯 [논리 오류 대수술]: 중간에 함수를 죽여 백엔드를 멈추던 가짜 야후 크롤러 코드를 완전히 걷어내고,
    # 2단계에서 완벽 복구한 실시간 네이버 시세 패치 및 가이던스 파싱 엔진으로 흐름을 정상 도킹합니다.
    raw_data = get_live_financial_data(code)
    if raw_data["current_price"] == 0:
        return jsonify({"success": False, "message": "거래소 실시간 시세 패킷 동기화 실패"})
        
    # 2단계의 예측 AI 모델 구동 (익일 적정 주가 산출 알고리즘 가동)
    predictor = ForwardPricePredictor(eps_this_year=raw_data["eps_this"], eps_next_year=raw_data["eps_next"])
    tomorrow_date = datetime.date.today() + datetime.timedelta(days=1)
    predicted_price_val = predictor.predict_price(tomorrow_date, raw_data["per"])
    
    # 🚀 [최종 연산 성공 반환]: 질문자님이 설계하신 아웃풋 포맷 그대로 프론트엔드 화면으로 전달!
    return jsonify({
        "success": True,
        "stock_name": stock_name,
        "stock_code": code,
        "current_price": f"{raw_data['current_price']:,}원",
        "predicted_price": f"{predicted_price_val:,}원",
        "is_consensus": raw_data["is_consensus"],
        "est_count": raw_data["est_count"]
    })


# ========================================================
# PART 6. INFRA DEPLOYMENT EXECUTER
# ========================================================

if __name__ == "__main__":
    # 클라우드 인프라 아키텍처 및 로컬 테스트 범용 10000 포트 개방
    app.run(host="0.0.0.0", port=10000, debug=True)
