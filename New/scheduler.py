import time
import asyncio
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
import google.generativeai as genai  # 공식 구글 제미나이 SDK

# 우리가 앞서 영혼을 갈아 만든 config에서 무적의 방어막 설정들을 수입합니다.
import config

# =====================================================================
# [초기화] 제미나이 API 키 순환 발급 및 보안 커넥터 세팅
# =====================================================================
def get_activated_gemini_model():
    """
    호출할 때마다 config.py의 라운드 로빈 엔진을 통해 안전한 무료 API 키를 배정받고,
    구글 실시간 검색(Google Search Grounding) 툴을 장착한 Flash 모델을 리턴합니다.
    """
    # 1원도 안 내는 무료 멀티 키 중 이번 턴에 쓸 키 하나 획득
    api_key = config.get_next_api_key()
    genai.configure(api_key=api_key)
    
    # 무료 티어에서 가장 빠르고 가성비 미친 Gemini 2.5 Flash 모델 선정
    # 중요: 홈페이지에서 직접 검색하듯 실시간 구글 검색 기능을 강제로 주입합니다.
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        tools=[{"google_search_grounding": {}}]  # 👈 실시간 미장/뉴스 긁어오는 핵심 치트키
    )
    return model


# =====================================================================
# [배치 메인 제어 센터] 매일 오전 6시 정각에 깨어나는 트리거 엔진
# =====================================================================
def start_scheduler():
    """
    백그라운드 스케줄러를 가동하여 매일 아침 6시 정각에 
    전체 코스피 200 종목 분석 및 지수 도출 파이프라인을 실행합니다.
    """
    scheduler = BackgroundScheduler(timezone="Asia/Seoul")
    
    # 서버가 켜져 있는 한, 매일 아침 6시 00분 00초에 run_morning_pipeline 함수를 실행
    scheduler.add_job(
        func=execute_morning_pipeline_bridge,
        trigger="cron",
        hour=6,
        minute=0,
        id="kospi200_morning_batch"
    )
    scheduler.start()
    print("⏰ [오전 6시 배치 시스템] 정상 가동 시작. 매일 아침 6시에 제미나이가 깨어납니다.")

def execute_morning_pipeline_bridge():
    """
    APScheduler(동기식)와 파이썬 비동기(Asyncio) 루프를 매끄럽게 연결해주는 다리 역할입니다.
    """
    print(f"☀️ [오전 6시] 배치가 트리거되었습니다. 시각: {datetime.now()}")
    asyncio.run(run_morning_pipeline())

# =====================================================================
# [청크 분할 및 비동기 루프 엔진] 10종목씩 쪼개고 강제 휴식 부여
# =====================================================================
async def run_morning_pipeline():
    """
    코스피 200 종목을 10개씩 묶어 총 20바퀴의 사이클을 돌립니다.
    구글 무료 API 분당 호출 제한(RPM)을 우회하는 핵심 심장부입니다.
    """
    # config.py에 박아둔 무적의 200개 종목 리스트의 '공식 명칭'만 싹 추출합니다.
    # 중복 제거를 통해 순수 코스피 200 종목만 리스트업합니다.
    all_stocks = list(set(config.STOCK_NAME_MAPPING.values()))
    
    # 혹시 모를 누락 방지 및 정렬
    all_stocks.sort()
    
    total_stocks_count = len(all_stocks)
    chunk_size = 10  # 형님이 딱 정해주신 10종목 묶음 크기
    
    print(f"📊 [데이터 수집] 총 {total_stocks_count}개 종목을 {chunk_size}개씩 쪼개서 분석을 시작합니다.")
    
    # 오전 6시 임시 저장 공간 초기화
    temp_stock_data = {}
    
    # 0부터 200까지 10씩 점프하며 루프를 돕니다 (총 20번 회전)
    for i in range(0, total_stocks_count, chunk_size):
        chunk = all_stocks[i:i + chunk_size]
        current_batch_num = (i // chunk_size) + 1
        total_batches = (total_stocks_count + chunk_size - 1) // chunk_size
        
        print(f"🔄 [배치 {current_batch_num}/{total_batches}] {chunk} 분석 요청 중...")
        
        try:
            # 💡 [핵심] 10개 종목 묶음을 제미나이에게 던져서 한방에 분석해옵니다 (3/4단계에서 구현)
            batch_result = await analyze_stock_chunk_with_gemini(chunk)
            
            # 받아온 10개 종목의 결과 데이터를 임시 저장소에 병합
            if batch_result:
                temp_stock_data.update(batch_result)
                
        except Exception as e:
            print(f"❌ [배치 {current_batch_num} 오류] 제미나이 호출 중 에러 발생: {e}")
            # 에러가 나더라도 다음 10종목은 돌아야 하므로 무시하고 진행 (Fault Tolerance)
            pass
        
        # 🔥 [비용 0원 무한 우회 치트키]
        # 구글 무료 API는 1분당 15번까지만 호출이 허용됩니다.
        # 10종목씩 묶어서 1바퀴 돌 때마다 의도적으로 12초~15초 동안 서버를 완전 일시정지(`await asyncio.sleep`) 시킵니다.
        # 이렇게 하면 1분에 최대 4~5번만 호출하므로 구글 보안 필터링에 절대 걸리지 않고 안전하게 통과합니다.
        if i + chunk_size < total_stocks_count:
            sleep_time = 13  # 13초 휴식
            print(f"💤 [무료 API 한계 우회] 구글 차단을 피하기 위해 {sleep_time}초간 휴식합니다... (안전모드)")
            await asyncio.sleep(sleep_time)

    print("✅ [1~2단계 완료] 코스피 200 전 종목의 미장 및 뉴스 분석 데이터 수집을 마쳤습니다.")
    
    # 이제 수집된 데이터를 가지고 3단계 시총 가중치 연산으로 넘겨줍니다 (4/4단계에서 구현)
    await calculate_final_kospi200_index(temp_stock_data)




import json

# =====================================================================
# [AI 분석 엔진] 10개 종목에 대해 미국 시장 & 최신 뉴스 더블 점수화
# =====================================================================
async def analyze_stock_chunk_with_gemini(stock_chunk):
    """
    10개 종목 리스트를 인풋으로 받아, 구글 실시간 검색 기능을 켠 제미나이에게
    미장 이슈와 최신 뉴스 영향도 점수를 정확하게 뜯어냅니다.
    """
    # 1/4 단계에서 만든 멀티 API 키 순환 발급 모델 로드
    model = get_activated_gemini_model()
    
    # 제미나이가 정확히 백엔드 코드가 파싱하기 좋은 구조로 대답하도록 프롬프트를 정밀 설계합니다.
    prompt = f"""
    당신은 대한민국 최고의 인공지능 퀀트 애널리스트이자 주가 예측 시스템입니다.
    현재 제공된 코스피 200 종목 리스트에 대해 오늘 오전 6시 기준의 시장 상황을 정밀 분석해주세요.

    [분석 대상 종목 리스트]: {stock_chunk}

    [임무 및 분석 가이드라인]:
    1. 실시간 구글 검색 기능을 활용하여, 간밤에 마감된 미국 시장(뉴욕증시, 나스닥, 필라델피아 반도체 지수 등) 및 글로벌 거시경제 이슈가 각 종목에 미치는 영향(호재/악재)을 분석하여 'us_market_score'로 점수화 하세요.
    2. 어제 하루 동안의 뉴스부터 오늘 오전 6시 직전까지 대한민국 언론 및 공시에 올라온 각 종목별 최신 개별 뉴스(실적, 계약, 노조, 규제 등)를 검색하고 분석하여 'news_score'로 점수화 하세요.
    3. 모든 점수는 반드시 아래의 기준을 철저히 준수해야 합니다:
       - +2: 매우 강력한 호재 (주가 급등 예상)
       - +1: 완만한 호재 (상승 분위기)
       -  0: 영향 없음 (보합 또는 중립)
       - -1: 완만한 악재 (하락 분위기)
       - -2: 매우 치명적인 악재 (주가 급락 예상)
    4. 각 종목별로 분석된 핵심 사유를 한 문장(summary)으로 간략하게 요약하세요.

    [⚠️ 출력 형식 필수 규칙]:
    - 마크다운이나 다른 설명 문구는 일체 넣지 마십시오.
    - 오직 파이썬의 json.loads()로 즉시 변환 가능한 형태의 순수한 JSON 데이터 포맷만 반환해야 합니다.
    - 대답의 처음 시작은 반드시 '{{' 이여야 하고 끝은 '}}' 로 끝나야 합니다.

    [JSON 출력 구조 예시]:
    {{
        "삼성전자": {{
            "us_market_score": 1.0,
            "news_score": -1.0,
            "summary": "미국 엔비디아 상승으로 미장 분위기는 좋으나, 국내 내부 노조 파업 뉴스 리스크가 발생함."
        }},
        "LG화학": {{
            "us_market_score": -1.0,
            "news_score": -1.0,
            "summary": "글로벌 전기차 수요 둔화 여파 및 배터리 공급 과잉 우려 뉴스로 전반적 약세 예상."
        }}
    }}
    """

    # 제미나이 API 호출 (동기 함수를 비동기 루프에서 안전하게 실행)
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, lambda: model.generate_content(prompt))
    
    # 제미나이가 준 텍스트 정제 작업 (간혹 구글이 앞뒤에 꼼수로 붙이는 ```json 코드 블록 제거)
    raw_text = response.text.strip()
    if raw_text.startswith("```json"):
        raw_text = raw_text.split("```json")[1].split("```")[0].strip()
    elif raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1].split("```")[0].strip()

    try:
        # 순수한 JSON 문자열을 파이썬 딕셔너리로 변환하여 반환
        parsed_data = json.loads(raw_text)
        return parsed_data
    except Exception as e:
        print(f"⚠️ [JSON 파싱 에러] 제미나이가 지정된 형식을 벗어났습니다. 원문 일부: {raw_text[:100]}")
        return None

# =====================================================================
# [퀀트 계산 엔진] 시가총액 가중치 반영 최종 코스피 200 지수 도출
# =====================================================================
async def calculate_final_kospi200_index(collected_stock_data):
    """
    제미나이가 준 각 종목별 호재/악재 점수와 config.py의 시총 비중을 합산하여
    최종 코스피 200 예상 지수 변동률을 계산하고 메모리에 상주시킵니다.
    """
    if not collected_stock_data:
        print("❌ [퀀트 연산 실패] 수집된 종목 데이터가 없어 최종 지수를 계산할 수 없습니다.")
        return

    total_weight_sum = 0.0
    weighted_score_sum = 0.0

    print("🧮 [퀀트 연산 시작] 코스피 200 시가총액 가중치 기반 최종 변동률 산출 중...")

    for stock_name, scores in collected_stock_data.items():
        # 1번(미장 점수)과 2번(국내 최신 뉴스 점수)을 합산하여 종목별 최종 결합 점수 도출
        us_score = scores.get("us_market_score", 0.0)
        news_score = scores.get("news_score", 0.0)
        combined_score = us_score + news_score  # 범위: -4.0 ~ +4.0
        
        # config.py에서 해당 종목의 실제 시가총액 비중(%)을 가져옴 (없으면 기본값 적용)
        weight = config.KOSPI200_WEIGHTS.get(stock_name, config.DEFAULT_WEIGHT)
        
        # [수학적 가중합 계산] (점수 * 시총 비중)을 계속 누적
        weighted_score_sum += (combined_score * weight)
        total_weight_sum += weight
        
        # 개별 종목의 최종 합산 점수도 메모리에 보관하기 위해 가공
        collected_stock_data[stock_name]["combined_score"] = combined_score

    # 지수 변동률 수치 보정 (최종 점수를 퍼센트 단위로 변환하기 위한 보정 계수 적용)
    # 가중합을 총 가중치로 나누어 평균 점수를 내고, 이를 한국 증시 변동성 폭에 맞춤 공식화
    if total_weight_sum > 0:
        raw_index_result = weighted_score_sum / total_weight_sum
        # 평균 결합점수 기반으로 코스피 지수 예상 변동률(%) 확정 (소수점 둘째자리까지 반올림)
        final_kospi200_variation = round(raw_index_result * 1.5, 2) 
    else:
        final_kospi200_variation = 0.0

    # =====================================================================
    # [최종 메모리 상주] RAM에 데이터 바인딩 (배포 시 비용 0원의 핵심)
    # =====================================================================
    config.MORNING_BATCH_STORE["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    config.MORNING_BATCH_STORE["expected_kospi200"] = final_kospi200_variation
    config.MORNING_BATCH_STORE["stock_data"] = collected_stock_data

    print("=====================================================================")
    print(f"🎉 [오전 6시 배치 완료] 메모리 상주 성공!")
    print(f"📅 업데이트 시각: {config.MORNING_BATCH_STORE['last_updated']}")
    print(f"📈 최종 예측 코스피 200 지수 변동률: {final_kospi200_variation}%")
    print(f"📦 메모리에 상주된 코스피 200 종목 데이터 수: {len(collected_stock_data)}개")
    print("=====================================================================")


# =====================================================================
# [로컬 테스트용 메인 블록] 이 파일만 단독 실행했을 때 아침 6시 상황 테스트 가능
# =====================================================================
if __name__ == "__main__":
    print("🚀 [테스트 모드] 즉시 오전 6시 파이썬 배치 파이프라인을 구동합니다.")
    # 실제 구동 테스트 시 아래 주석을 풀고 실행하면 10종목씩 제미나이가 긁기 시작합니다.
    # asyncio.run(run_morning_pipeline())

