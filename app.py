
import datetime
import requests
import re
from flask import Flask, jsonify, request

app = Flask(__name__)

@app.after_request
def after_request(response):
    """ Vercel 프론트엔드와 Render 백엔드 간의 도메인 교차 출처 차단 정책을 해제합니다. """
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
    return response

def get_stock_code_by_name(stock_name):
def get_stock_code_by_name(stock_name):
    # 1. 수정한 완벽한 내부 자동완성 주소
    search_url = f"https://ac.finance.naver.com/ac?q={stock_name}&q_enc=utf-8&st=1&frm=stock&r_format=json"
    try:
        response = requests.get(search_url, timeout=5)
        search_data = response.json()
        
        # [RENDER 로그 강제 인젝션] 네이버 원시 데이터 출력
        print(f"=== [디버깅] 네이버 검색 API 원시 데이터: {search_data} ===")
        
        if "items" in search_data and len(search_data["items"]) > 0:
            # 🎯 교정 핵심: items의 첫 번째 인덱스 내부 배열을 순회 데이터셋으로 타격합니다.
            match_list = search_data["items"][0]
            print(f"=== [디버깅] 추출된 match_list 구조: {match_list} ===")
            
            for item in match_list:
                # 🎯 item 구조는 ["삼성전자", "005930", "삼설전다", ...] 형태의 리스트입니다.
                # item[0][0] 구조가 아니라 1차원 데이터의 0번 인덱스(종목명)와 1번 인덱스(코드)를 바라봅니다.
                if len(item) > 1 and item[0].replace(" ", "") == stock_name.replace(" ", ""):
                    print(f"=== [디버깅] 매칭 성공! 종목코드: {item[1]} ===")
                    return item[1]
                    
        print("=== [디버깅] 네이버 데이터는 왔으나 종목명 매칭에 실패했습니다. ===")
        return None
    except Exception as e:
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
# =====================================================================
@app.route("/search", methods=["POST"])
def search_stock():
    req_data = request.get_json()
    if not req_data or "stock_name" not in req_data:
        return jsonify({"success": False, "message": "Invalid Request Protocol"})
        
    stock_name = req_data.get("stock_name", "").strip()
    
    # 💡 1단계 디버깅 진단: 네이버 자동완성 API 원시 주소 직격 호출 테스트
    search_url = f"https://naver.com?q={stock_name}&q_enc=euc-kr&st=1&frm=stock&r_format=json"
    try:
        # 💡 네이버 보안 필터를 완벽히 우회하는 브라우저 가짜 가면(Headers) 주입
        debug_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get(search_url, headers=debug_headers, timeout=5)
        search_data = response.json()
    except Exception as e:
        return jsonify({"success": False, "message": f"❌ 네이버 접속 자체가 실패함: {str(e)}"})
        
    # 💡 [화면 강제 로그 인젝션 1] 네이버가 준 전체 원시 JSON을 프론트엔드 알림창으로 즉시 쏴버립니다.
    # 만약 이 팝업창에 데이터가 텅 비어있다면 네이버 IP 차단이 확실한 것입니다.
    if stock_name and ("items" in search_data):
        return jsonify({
            "success": False, 
            "message": f"🔍 [네이버 원시 데이터 획득 성공]\n전체 배열 구조: {str(search_data['items'])}"
        })

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
