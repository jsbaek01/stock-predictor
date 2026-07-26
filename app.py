
import datetime
import requests
import re
from flask import Flask, jsonify, request
from pykrx import stock

app = Flask(__name__)

@app.after_request
def after_request(response):
    """ Vercel 프론트엔드와 Render 백엔드 간의 도메인 교차 출처 차단 정책을 해제합니다. """
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
    return response

def get_stock_code_by_name(stock_name):
    try:
        # 1. 오늘 날짜 기준으로 코스피/코스닥에 상장된 모든 종목코드(티커) 리스트 확보
        # 네이버를 찌르지 않고 가상 서버 환경에서도 차단 없이 안전하게 데이터를 가져옵니다.
        match_list = stock.get_market_ticker_list()
        
        # [RENDER 로그 강제 인젝션] 가져온 상장 주식 마켓 데이터 리스트 출력
        print(f"=== [디버깅] 거래소 엔진 데이터 확보 성공 (총 {len(match_list)}개 종목) ===")
        print(f"=== [디버깅] 추출된 match_list 구조(일부): {match_list[:5]} ===")
        
        for item in match_list:
            # item 변수 하나에는 '005930' 같은 순수한 종목코드가 들어옵니다.
            # stock.get_market_ticker_name(item) 함수를 쓰면 해당 코드의 진짜 종목명을 알아낼 수 있습니다.
            ticker_name = stock.get_market_ticker_name(item)
            
            # 사용자가 입력한 종목명과 공백을 제거하고 정밀 비교합니다.
            if ticker_name.replace(" ", "") == stock_name.replace(" ", ""):
                print(f"=== [디버깅] 매칭 성공! 종목명: {ticker_name} -> 종목코드: {item} ===")
                return item  # 정상적인 종목코드(예: '005930') 반환
                
        print("=== [디버깅] 거래소 데이터는 왔으나 종목명 매칭에 실패했습니다. ===")
        return None
        
    except Exception as e:
        # 에러 발생 시 Render 로그창에 범인을 찍어버립니다.
        print(f"❌ 치명적 오류 [get_stock_code_by_name]: {str(e)}")
        return None


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



# =====================================================================
# PART 4. LIVE FINANCE WEB SCRAPER (CONSEN & COUNT)
# =====================================================================
def get_live_financial_data(stock_code):
    """ 네이버 증권 금융 서버 도메인을 정상 복구하여 기관 추정치 개수와 실적 노드를 파싱합니다. """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    # 1. 실시간 거래소 주가 패치 (m.stock 서브 도메인 네트워크 정상화)
    price_url = f"https://naver.com{stock_code}/integration"
    current_price = 0
    try:
        price_res = requests.get(price_url, headers=headers, timeout=5)
        price_data = price_res.json()
        if price_data and "closePrice" in price_data:
            current_price = int(price_data["closePrice"].replace(",", ""))
    except Exception as e:
        print(f"Live Price API Network Error: {str(e)}")

    # 2. 기업실적분석 재무 가이던스 추출 (finance.naver 서브 도메인 정상화)
    finance_url = f"https://naver.com?code={stock_code}"
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
        count_match = re.search(r'추정기관수\s*<em[^>]*>(\d+)</em>|추정기관수\s*(\d+)', html_text)
        if count_match:
            cnt_str = count_match.group(1) if count_match.group(1) else count_match.group(2)
            est_count = int(cnt_str)

        # 시장 선행 PER 추출
        per_match = re.search(r'선행\s*PER.*?<em[^>]*>([\d\.]+)</em>', html_text, re.DOTALL)
        if per_match:
            per_multiple = float(per_match.group(1))

        # 인덱스 초과 버그 원천 차단형 EPS 행 세그먼트 슬라이싱 파서
        eps_row_match = re.search(r'EPS\(원\).*?</tr>', html_text, re.DOTALL)
        if eps_row_match and est_count > 0:
            eps_row_html = eps_row_match.group(0)
            eps_values = re.findall(r'<td[^>]*>([\d,\-]+)</td>', eps_row_html)
            
            # 컨센서스 컬럼 위치 매핑 안전 슬라이싱 (유동적인 칼럼 개수 방어)
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

    # 3. 컨센서스 부재 종목(소형주) 대응 시장 임플라이드 보정 알고리즘
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

# =====================================================================
# PART 5. MAIN BUSINESS API CONTROLLER

@app.route("/search", methods=["POST"])
def search_stock():
    req_data = request.get_json()
    if not req_data or "stock_name" not in req_data:
        return jsonify({"success": False, "message": "Invalid Request Protocol"})
        
    stock_name = req_data.get("stock_name", "").strip()
    
    try:
        # 🎯 1. 오늘 날짜 기준으로 코스피/코스닥에 상장된 모든 종목코드(티커) 리스트 확보
        # 이 함수는 가상 서버 환경에서도 차단 없이 안전하게 데이터를 가져옵니다.
        tickers = stock.get_market_ticker_list()
        
        stock_code = None
        # 🎯 2. 전체 종목을 돌며 사용자가 입력한 종목명과 일치하는 코드가 있는지 매칭
        for ticker in tickers:
            ticker_name = stock.get_market_ticker_name(ticker)
            if ticker_name.replace(" ", "") == stock_name.replace(" ", ""):
                stock_code = ticker
                break
                
        # 💡 [화면 강제 로그 인젝션] 질문자님의 디버깅 스타일 유지
        # 정상적으로 코드를 찾았든 못 찾았든 원시 탐색 결과를 무조건 리턴하여 화면에 띄웁니다.
        if stock_code:
            return jsonify({
                "success": False,  # 기존 테스트 흐름 유지를 위해 False로 유지 (원하면 True로 변경 가능)
                "message": f"🔍 [KRX 엔진 데이터 획득 성공]\n종목명: {stock_name} -> 매칭된 종목코드: [{stock_code}]"
            })
        else:
            return jsonify({
                "success": False,
                "message": f"❌ '{stock_name}'에 해당하는 종목코드를 거래소 사전에서 찾을 수 없습니다."
            })
            
    except Exception as e:
        # 버셀 네트워크 단에서 또 다른 예외가 발생하는지 모니터링하기 위한 예외 처리구문
        return jsonify({"success": False, "message": f"❌ 거래소 사전 조회 실패: {str(e)}"})

    # 이하 코드는 혹시 모를 다음 단계를 위해 기존 흐름을 유지합니다.
    code = get_stock_code_by_name(stock_name)
    if not code:
        return jsonify({"success": False, "message": f"'{stock_name}'은(는) 상장 주식 사전에 존재하지 않습니다."})
        
    raw_data = get_live_financial_data(code)
    if raw_data["current_price"] == 0:
        return jsonify({"success": False, "message": "거래소 실시간 시세 패킷 동기화 실패"})

    predictor = ForwardPricePredictor(eps_this_year=raw_data["eps_this"], eps_next_year=raw_data["eps_next"])
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


# =====================================================================
# PART 6. INFRA DEPLOYMENT EXECUTER
# =====================================================================
if __name__ == "__main__":
    # 클라우드 인프라 아키텍처 및 로컬 테스트 범용 10000 포트 개방
    app.run(host="0.0.0.0", port=10000, debug=True)
