import datetime
import requests
import re
from flask import Flask, jsonify, request

app = Flask(__name__)

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
    return response

def get_stock_code_by_name(stock_name):
    search_url = f"https://naver.com{stock_name}&q_enc=euc-kr&st=1&frm=stock&r_format=json"
    try:
        response = requests.get(search_url, timeout=5)
        search_data = response.json()
        if "items" in search_data and len(search_data["items"]) > 0:
            match_list = search_data["items"]
            for item in match_list:
                if item.replace(" ", "") == stock_name:
                    return item
        return None
    except Exception as e:
        print(f"Stock Code Mapping Failed: {str(e)}")
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


def get_live_financial_data(stock_code):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    price_url = f"https://naver.com{stock_code}/integration"
    current_price = 0
    try:
        price_res = requests.get(price_url, headers=headers, timeout=5)
        price_data = price_res.json()
        if "closePrice" in price_data:
            current_price = int(price_data["closePrice"].replace(",", ""))
    except Exception as e:
        print(f"Live Price API Network Error: {str(e)}")

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
        
        count_match = re.search(r'추정기관수\s*<em[^>]*>(\d+)</em>|추정기관수\s*(\d+)', html_text)
        if count_match:
            cnt_str = count_match.group(1) if count_match.group(1) else count_match.group(2)
            est_count = int(cnt_str)

        per_match = re.search(r'선행\s*PER.*?<em[^>]*>([\d\.]+)</em>', html_text, re.DOTALL)
        if per_match:
            per_multiple = float(per_match.group(1))

        eps_row_match = re.search(r'EPS\(원\).*?</tr>', html_text, re.DOTALL)
        if eps_row_match and est_count > 0:
            eps_row_html = eps_row_match.group(0)
            eps_values = re.findall(r'<td[^>]*>([\d,\-]+)</td>', eps_row_html)
            
            if len(eps_values) >= 5:
                val_this = eps_values[3].replace(",", "").strip()
                val_next = eps_values[4].replace(",", "").strip()
                if val_this != '-' and val_next != '-':
                    eps_this = int(val_this)
                    eps_next = int(val_next)
                    is_consensus_exist = True
    except Exception as e:
        print(f"Financial Parsing Logic Exception: {str(e)}")

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

@app.route("/search", methods=["POST"])
def search_stock():
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)

