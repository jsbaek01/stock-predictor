from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

# 우리가 빌드한 무적의 설정과 배치 스케줄러를 수입합니다.
import config
import scheduler

# =====================================================================
# [수명 주기 제어] 웹 서버 가동 시 오전 6시 스케줄러 자동 자동화
# =====================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    서버가 켜지는 순간 백그라운드에서 매일 오전 6시 배치가 돌도록 알람을 맞춥니다.
    서버가 꺼질 때는 리소스를 안전하게 정리합니다.
    """
    print("🌐 [웹 서버 기동] 시스템을 시작합니다.")
    try:
        # scheduler.py의 BackgroundScheduler를 깨웁니다.
        scheduler.start_scheduler()
    except Exception as e:
        print(f"⚠️ 스케줄러 초기화 실패 (테스트 모드 지속 가능): {e}")
        
    yield  # 서버가 켜져 있는 동안 이 지점에서 대기합니다.
    
    print("🛑 [웹 서버 종료] 시스템을 안전하게 종료합니다.")


# =====================================================================
# [서버 인프라 설정] FastAPI 인스턴스 생성 및 CORS 무력화
# =====================================================================
app = FastAPI(
    title="KOSPI200 AI 주가 예측 시스템 API",
    description="비용 0원으로 구현하는 실시간 퀀트-LLM 가중합 예측 서버",
    version="1.0.0",
    lifespan=lifespan
)

# 프론트엔드(HTML/React 등)가 어떤 도메인에서 접속해도 보안 에러(CORS) 없이 
# 데이터를 매끄럽게 가져갈 수 있도록 문을 활짝 열어둡니다.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 실무 배포 시 특정 도메인으로 제한 가능
    allow_credentials=True,
    allow_methods=["*"],  # GET, POST 등 모든 요청 허용
    allow_headers=["*"],
)


# =====================================================================
# [기초 엔드포인트] 서버 생존 확인용 헬스 체크 API
# =====================================================================
@app.get("/", tags=["Health"])
def health_check():
    """ 서버가 정상적으로 살아 숨쉬고 있는지 확인하는 통로입니다. """
    return {
        "status": "healthy",
        "message": "코스피 200 AI 예측 서버가 정상 작동 중입니다.",
        "timezone": "Asia/Seoul"
    }

# =====================================================================
# [실시간 라우터 엔진] 고객 종목 검색 및 AI 예측 통합 제어기
# =====================================================================
@app.get("/api/predict", tags=["Prediction"])
async def predict_stock_price(
    keyword: str = Query(..., description="고객이 입력한 종목명 또는 약어 (예: 삼전, 하닉, 땅콩)")
):
    """
    고객이 검색창에 종목을 입력하면 실시간으로 예측 리포트를 도출하는 핵심 엔드포인트입니다.
    분당 50명 대규모 트래픽을 비용 0원 무료 API 키로 버텨내는 방어벽이 작동합니다.
    """
    if not keyword:
        raise HTTPException(status_code=400, detail="⚠️ 검색할 종목명을 입력해주세요.")

    # -----------------------------------------------------------------
    # [1단계] 입력값 좆같이 들어와도 정밀 정제 (예: '하닉' -> 'SK하이닉스')
    # -----------------------------------------------------------------
    official_stock_name = config.normalize_stock_name(keyword)
    print(f"🔍 [검색 요청] 입력값: '{keyword}' ➡️ 공식 종목명 판정: '{official_stock_name}'")

    # -----------------------------------------------------------------
    # [2단계] 분당 50명 트래픽 폭주 방어벽 - 5분 무료 인메모리 캐시 확인
    # -----------------------------------------------------------------
    # 똑같은 핫한 종목(예: 삼성전자)을 여러 명이 동시에 검색하면,
    # 제미나이를 부르지 않고 config.py의 메모리에서 0.001초 만에 바로 꺼내줍니다.
    cached_prediction = config.get_cached_search(official_stock_name)
    if cached_prediction:
        print(f"⚡ [캐시 힛(Hit)!] '{official_stock_name}'은 5분 이내 분석 건이므로 제미나이 호출 없이 광속 반환합니다.")
        return {
            "success": True,
            "source": "cache",
            "stock_name": official_stock_name,
            "prediction": cached_prediction,
            "morning_baseline": config.MORNING_BATCH_STORE.get("stock_data", {}).get(official_stock_name, {})
        }

    # -----------------------------------------------------------------
    # [3단계] 오전 6시 베이스라인 데이터 존재 유무 검증
    # -----------------------------------------------------------------
    morning_data_store = config.MORNING_BATCH_STORE.get("stock_data", {})
    morning_stock_info = morning_data_store.get(official_stock_name)

    # 만약 코스피 200 종목이 아니거나, 아침 배치에 누락된 생소한 종목일 경우 처리
    if not morning_stock_info:
        print(f"⚠️ [주의] '{official_stock_name}'은 오늘 아침 코스피 200 데이터베이스에 존재하지 않습니다.")
        # 코스피 200이 아니더라도 제미나이에게 실시간 검색을 돌려 서비스는 가능하게 백업 정보를 세팅합니다.
        morning_stock_info = {
            "us_market_score": 0.0,
            "news_score": 0.0,
            "combined_score": 0.0,
            "summary": "코스피 200 기본 데이터베이스에 없으나 실시간 시황 분석을 단독 진행합니다."
        }

    # -----------------------------------------------------------------
    # [4단계] 3/3 단계로 이관 (캐시에 없으므로 제미나이 2차 실시간 결합 분석 호출)
    # -----------------------------------------------------------------
    try:
        # 아침 6시 점수 + 현재 장중 실시간 뉴스를 엮어서 제미나이 최종 1회 호출 진행
        final_report = await generate_live_combined_prediction(official_stock_name, morning_stock_info)
        
        # 0원으로 분당 50명 버티기 위해, 새로 뽑은 분석 결과는 메모리에 5분 동안 즉시 박아둠
        config.set_search_cache(official_stock_name, final_report)
        
        return {
            "success": True,
            "source": "live_ai",
            "stock_name": official_stock_name,
            "prediction": final_report,
            "morning_baseline": morning_stock_info
        }
        
    except Exception as e:
        print(f"❌ [실시간 분석 에러] {official_stock_name} 처리 실패: {e}")
        raise HTTPException(status_code=500, detail=f"AI 실시간 시황 결합 중 오류가 발생했습니다: {str(e)}")


import json
# scheduler.py에서 세팅한 제미나이 활성화 클라이언트를 그대로 재사용합니다.
from scheduler import get_activated_gemini_model

# =====================================================================
# [AI 결합 예측 엔진] 오전 6시 데이터 + 현 시황 실시간 믹싱 분석
# =====================================================================
async def generate_live_combined_prediction(stock_name: str, morning_info: dict) -> str:
    """
    메모리에 보관 중이던 오전 6시 분석 베이스라인 정보와
    사용자가 검색한 현재 시점의 실시간 시황 검색 결과를 결합하여 최종 내일의 주가를 예측합니다.
    """
    # config.py의 멀티 키 로테이션을 활용해 차단 우회용 제미나이 모델 획득
    model = get_activated_gemini_model()
    
    # 오전 6시에 이미 퀀트 파이프라인이 연산해둔 점수와 요약본을 가져옵니다.
    m_us_score = morning_info.get("us_market_score", 0.0)
    m_news_score = morning_info.get("news_score", 0.0)
    m_combined_score = morning_info.get("combined_score", 0.0)
    m_summary = morning_info.get("summary", "오전 6시 기본 시황 데이터가 상주해 있습니다.")

    # 제미나이에게 현재 장중 상황까지 싹 긁어오도록 지시하는 고도화 프롬프트
    prompt = f"""
    당신은 대한민국 최고의 주식 투자 전략가이자 인공지능 퀀트 애널리스트입니다.
    다음 종목에 대해 [오전 6시 베이스라인 데이터]와 [현재 실시간 구글 검색 결과]를 매끄럽게 결합하여, '내일의 예상 주가 흐름 및 투자 대응 리포트'를 작성해주세요.

    [분석 대상 종목]: {stock_name}

    [오전 6시 기준 사전 분석 데이터]:
    - 미국 시장 연동 점수: {m_us_score}점 (-2 ~ +2)
    - 전일~오전6시 국내 뉴스 점수: {m_news_score}점 (-2 ~ +2)
    - 오전 6시 기준 총합 점수: {m_combined_score}점 (-4 ~ +4)
    - 아침 시황 요약: {m_summary}

    [임무 가이드라인]:
    1. 실시간 구글 검색을 통해 현재 이 시간 기준 '{stock_name}'에 대한 추가적인 장중 속보, 찌라시, 공시, 수급 현황(외인/기관 매매 패턴)이 있는지 확인하십시오.
    2. 제공된 오전 6시의 미장/뉴스 베이스라인 점수에 현재 장중 시황 변동성을 융합하여, 최종적으로 내일 이 종목이 어떤 방향성으로 움직일지 정밀 예측하십시오.
    3. 일반적인 설명 대신 투자자가 직관적으로 파악할 수 있도록 리포트 형태로 작성하십시오.

    [⚠️ 출력 리포트 구성 필수 양식]:
    - 📌 [종목 요약]: 오전 6시 데이터와 현재 시황의 핵심 충돌 지점 요약
    - 📈 [내일의 주가 방향성 예측]: 내일 장 시작 후 예상되는 변동폭(급등, 완만한 상승, 보합, 약세, 급락 중 택1) 및 이유
    - 💡 [실시간 장중 특이사항]: 오전 6시 이후 현재까지 추가로 포착된 뉴스나 수급 특징
    - 🛠️ [투자자 대응 전략]: 내일 시초가 진입 여부 및 손절/익절 가이드라인

    ※ 주의: 대답 서두에 불필요한 인사말("안녕하세요", "리포트를 작성하겠습니다")은 생략하고 바로 본론인 '📌 [종목 요약]'부터 출력하십시오.
    """

    # 제미나이 실시간 검색 기능 가동 (동기 함수를 비동기 루프로 안전하게 가동)
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, lambda: model.generate_content(prompt))
    
    # 제미나이가 최종 도출해낸 고해상도 예측 리포트 텍스트 반환
    final_report_text = response.text.strip()
    return final_report_text


# =====================================================================
# [Uvicorn 서버 구동부] 파이썬 코드로 서버 즉시 실행 가능
# =====================================================================
if __name__ == "__main__":
    import uvicorn
    print("🔥 [서버 구동] 로컬 호스트 8000번 포트에서 FastAPI 서버를 켭니다.")
    # 로컬에서 테스트 및 프론트엔드와 연동할 수 있도록 uvicorn 웹서버를 실행합니다.
    uvicorn.run("app.py:app", host="0.0.0.0", port=8000, reload=False)



