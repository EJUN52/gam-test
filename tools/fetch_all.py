# -*- coding: utf-8 -*-
"""공개 데이터 내려받기 — 10주제의 원본을 raw/ 에 저장한다.

**전부 키도 로그인도 필요 없습니다.** 수업 중에 20명이 동시에 받아도 막히지
않는 곳만 골랐습니다.

한 번 받으면 raw/ 에 남으므로 다시 돌려도 새로 받지 않습니다.
(--force 를 주면 다시 받습니다)

실행 (저장소 최상위에서):
    python tools/fetch_all.py
    python tools/fetch_all.py --force
"""
from __future__ import annotations

import http.client
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# 윈도우 콘솔(cp949)은 한글 · 기호를 못 찍고 멈출 때가 있다. 출력만 UTF-8 로 맞춘다
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"
# HTTP 헤더는 latin-1 만 담는다. 한글을 넣으면 UnicodeEncodeError 가 난다
UA = {"User-Agent": "gam-test-class/1.0 (data analysis class)"}
TIMEOUT = 300

SEOUL = (37.5665, 126.9780)
BUSAN = (35.1796, 129.0756)

# 날씨는 **모델을 ERA5로 못 박는다** (&models=era5).
# 모델을 적지 않으면 Open-Meteo가 그때그때 '가장 알맞은 모델'(best_match)을 골라 섞어 준다.
# 그 구성이 바뀌면 같은 주소로 받아도 지난 값이 달라진다 — 2026-10에 실제로 2024년 서울
# 열대야가 15일에서 12일로 바뀌었다. 출처에 모델까지 적어야 다시 받아도 같은 값이 나온다.
ERA5 = "&models=era5"

# 공공데이터포털 파일데이터는 주소 하나로 받을 수 없다. 파일을 갱신할 때마다 파일 번호
# (atchFileId)가 바뀌기 때문이다. 그래서 '데이터 번호'만 적어 두고, 받을 때 포털에
# 그때의 파일 번호를 물어본 뒤 받는다 (로그인 불필요). 시가 해마다 갱신하므로
# 다시 받으면 내용이 바뀔 수 있다 — 받은 파일의 기준일자를 꼭 확인한다.
DATAGOKR = "datagokr:"


def datagokr(pk: str, detail_pk: str) -> str:
    return f"{DATAGOKR}{pk}/{detail_pk}"


def resolve(url: str) -> str:
    """datagokr: 주소면 포털에 지금의 파일 번호를 물어 실제 받을 주소로 바꾼다."""
    if not url.startswith(DATAGOKR):
        return url
    pk, detail_pk = url[len(DATAGOKR):].split("/", 1)
    form = urllib.parse.urlencode({
        "publicDataPk": pk, "publicDataDetailPk": detail_pk,
        "atchFileId": "", "fileDetailSn": "1", "publicDataTyCode": "PR0051",
    }).encode()
    req = urllib.request.Request(
        "https://www.data.go.kr/tcs/dss/selectFileDataDownload.do", data=form, headers=UA)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        info = json.loads(r.read().decode("utf-8"))
    if not info.get("status"):
        raise urllib.error.URLError(f"공공데이터포털이 파일 번호를 주지 않았습니다: {info.get('error')}")
    return ("https://www.data.go.kr/cmm/cmm/fileDownload.do"
            f"?atchFileId={info['atchFileId']}&fileDetailSn={info['fileDetailSn']}")

SOURCES: list[tuple[str, str, str]] = [
    # (저장 파일명, 설명, URL)
    ("seoul_weather.json",
     "서울 일별 기온·강수 1950~2024 (Open-Meteo Archive · ERA5 고정)",
     "https://archive-api.open-meteo.com/v1/archive"
     f"?latitude={SEOUL[0]}&longitude={SEOUL[1]}"
     "&start_date=1950-01-01&end_date=2024-12-31"
     "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum"
     "&timezone=Asia%2FSeoul" + ERA5),

    ("seoul_snow.json",
     "서울 일별 강설량 1990~2024 (Open-Meteo Archive · ERA5 고정)",
     "https://archive-api.open-meteo.com/v1/archive"
     f"?latitude={SEOUL[0]}&longitude={SEOUL[1]}"
     "&start_date=1990-01-01&end_date=2024-12-31"
     "&daily=snowfall_sum"
     "&timezone=Asia%2FSeoul" + ERA5),

    ("busan_heat.json",
     "부산 일별 최고·최저기온 1950~2024 (Open-Meteo Archive · ERA5 고정)",
     "https://archive-api.open-meteo.com/v1/archive"
     f"?latitude={BUSAN[0]}&longitude={BUSAN[1]}"
     "&start_date=1950-01-01&end_date=2024-12-31"
     "&daily=temperature_2m_max,temperature_2m_min"
     "&timezone=Asia%2FSeoul" + ERA5),

    ("busan_heat_plus.json",
     "부산 일별 기온·체감온도·습도 1973~2024 (Open-Meteo Archive · ERA5 고정)",
     "https://archive-api.open-meteo.com/v1/archive"
     f"?latitude={BUSAN[0]}&longitude={BUSAN[1]}"
     "&start_date=1973-01-01&end_date=2024-12-31"
     "&daily=temperature_2m_max,temperature_2m_min,temperature_2m_mean,"
     "apparent_temperature_max,apparent_temperature_min,relative_humidity_2m_mean"
     "&timezone=Asia%2FSeoul" + ERA5),

    # 부산 관측소 실측값. 1년에 파일 하나씩이다. 온도는 화씨, 빈 값은 9999.9
    *[(f"busan_gsod_{y}.csv", f"부산 관측소 일별 요약 {y} (NOAA GSOD 47159099999)",
       "https://www.ncei.noaa.gov/data/global-summary-of-the-day/access/"
       f"{y}/47159099999.csv")
      for y in range(1973, 2025)],

    # 춘천 먹거리. 한 시점 목록이고 인코딩은 CP949 그대로 둔다
    ("chuncheon_restaurants.csv",
     "춘천시 요식업소 현황 (공공데이터포털 15003349 · 해마다 갱신)",
     datagokr("15003349", "uddi:1412717a-2e64-4bf1-aeae-9013ab803b69")),

    ("chuncheon_model_restaurants.csv",
     "춘천시 모범음식점 (공공데이터포털 15050522 · 해마다 갱신)",
     datagokr("15050522", "uddi:9b1363c5-328c-4736-ab4e-fa2d457c9e2e")),

    # 사람보다 많은 동물들. FAO 는 전체 파일을 ZIP 으로만 준다 — 풀지 않고 그대로 두고,
    # 계산할 때 안의 CSV 를 읽는다. FAO 가 해마다 갱신하면 지난 연도 값도 고쳐질 수 있다
    ("fao_qcl.zip",
     "나라별 작물·가축 생산 1961~ (FAO FAOSTAT QCL 일괄 파일 · ZIP 안에 CSV)",
     "https://bulks-faostat.fao.org/production/"
     "Production_Crops_Livestock_E_All_Data_(Normalized).zip"),

    # 커피공화국. 나라별 수입·수출(1961~). 273MB 라 받는 데 시간이 걸린다
    ("fao_tcl.zip",
     "나라별 작물·축산물 수출입 1961~ (FAO FAOSTAT TCL 일괄 파일 · ZIP 안에 CSV)",
     "https://bulks-faostat.fao.org/production/"
     "Trade_CropsLivestock_E_All_Data_(Normalized).zip"),

    ("wb_pop_all.json",
     "나라별 전체 인구 1961~2024 (World Bank SP.POP.TOTL)",
     "https://api.worldbank.org/v2/country/all/indicator/SP.POP.TOTL"
     "?format=json&per_page=20000&date=1961:2024"),

    ("seoul_air.json",
     "서울 시간별 미세먼지 2023~2024 (Open-Meteo Air Quality · CAMS)",
     "https://air-quality-api.open-meteo.com/v1/air-quality"
     f"?latitude={SEOUL[0]}&longitude={SEOUL[1]}"
     "&start_date=2023-01-01&end_date=2024-12-31"
     "&hourly=pm10,pm2_5&timezone=Asia%2FSeoul"),

    ("working_hours.csv",
     "연간 노동시간 (Our World in Data)",
     "https://ourworldindata.org/grapher/annual-working-hours-per-worker.csv"
     "?csvType=full&useColumnShortNames=true"),

    ("life_expectancy.csv",
     "기대수명 (Our World in Data)",
     "https://ourworldindata.org/grapher/life-expectancy.csv"
     "?csvType=full&useColumnShortNames=true"),

    ("wb_fertility.json",
     "합계출산율 전세계 (World Bank SP.DYN.TFRT.IN)",
     "https://api.worldbank.org/v2/country/all/indicator/SP.DYN.TFRT.IN"
     "?format=json&per_page=20000&date=1960:2023"),

    ("wb_pop_kor.json",
     "한국 인구·고령화 (World Bank)",
     "https://api.worldbank.org/v2/country/KOR/indicator/"
     "SP.POP.TOTL;SP.POP.65UP.TO.ZS;SP.URB.TOTL.IN.ZS"
     "?format=json&per_page=2000&source=2"),

    ("wb_internet.json",
     "인터넷 사용률 전세계 (World Bank IT.NET.USER.ZS)",
     "https://api.worldbank.org/v2/country/all/indicator/IT.NET.USER.ZS"
     "?format=json&per_page=20000&date=1990:2023"),

    ("usdkrw.json",
     "원달러 환율 1999~ (Frankfurter · ECB)",
     "https://api.frankfurter.dev/v1/1999-01-04..2024-12-31"
     "?base=USD&symbols=KRW"),

    ("wb_countries.json",
     "World Bank 국가 목록 — 대륙·소득군 같은 집계치를 걸러내는 데 씁니다",
     "https://api.worldbank.org/v2/country?format=json&per_page=400"),

    *[(f"city_{cid}.json", f"{cn} 일별 기온·강수 1991~2020 (Open-Meteo Archive · ERA5 고정)",
       "https://archive-api.open-meteo.com/v1/archive"
       f"?latitude={lat}&longitude={lon}"
       "&start_date=1991-01-01&end_date=2020-12-31"
       "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum"
       f"&timezone=auto" + ERA5)
      for cid, cn, lat, lon in (
          ("seoul", "서울", 37.5665, 126.9780),
          ("tokyo", "도쿄", 35.6895, 139.6917),
          ("london", "런던", 51.5072, -0.1276),
          ("singapore", "싱가포르", 1.3521, 103.8198),
      )],

    ("quakes.geojson",
     "규모 5.5 이상 지진 2000~2024 (USGS) — 2만건 상한에 걸리지 않는 기준",
     "https://earthquake.usgs.gov/fdsnws/event/1/query"
     "?format=geojson&starttime=2000-01-01&endtime=2024-12-31"
     "&minmagnitude=5.5&orderby=time&limit=20000"),

    ("quakes_korea.geojson",
     "한반도 주변 지진 2000~2024 (USGS · 규모 3.0 이상)",
     "https://earthquake.usgs.gov/fdsnws/event/1/query"
     "?format=geojson&starttime=2000-01-01&endtime=2024-12-31"
     "&minmagnitude=3.0&minlatitude=33&maxlatitude=39.5"
     "&minlongitude=124&maxlongitude=132&limit=20000"),
]


def get(url: str, dest: Path, tries: int = 4) -> int:
    """받는다. 잠깐의 실패면 기다렸다가 다시 시도한다.

    공개 API 는 대부분 호출 제한이 있고(429), 큰 파일은 받다가 끊기기도 한다
    (IncompleteRead · 시간 초과). 한 번 실패했다고 포기하지 말고, 간격을 늘려 가며
    다시 부른다. 주소가 틀린 것(404 같은)은 다시 불러도 소용없으니 바로 알린다.
    """
    wait = 5
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                data = r.read()
            dest.write_bytes(data)
            return len(data)
        except urllib.error.HTTPError as e:
            if (e.code != 429 and e.code < 500) or i == tries - 1:
                raise
            why = str(e.code)
        except (http.client.IncompleteRead, urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if i == tries - 1:
                raise
            why = type(e).__name__
        print(f"          {why} — {wait}초 뒤 다시 시도합니다 ({i+1}/{tries-1})")
        time.sleep(wait)
        wait *= 2
    raise RuntimeError("도달 불가")


def main() -> int:
    force = "--force" in sys.argv
    RAW.mkdir(parents=True, exist_ok=True)
    fail = 0
    for name, desc, url in SOURCES:
        dest = RAW / name
        if dest.exists() and not force:
            print(f"  건너뜀  {name:<22} 이미 있음 ({dest.stat().st_size/1024:,.0f}KB)")
            continue
        t0 = time.time()
        try:
            n = get(resolve(url), dest)
            print(f"  받음    {name:<22} {n/1024:>7,.0f}KB  {time.time()-t0:.1f}s  {desc}")
        except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.IncompleteRead) as e:
            print(f"  실패    {name:<22} {e}")
            fail += 1
        time.sleep(0.4)          # 상대 서버에 예의를 지킨다

    print()
    print(f"총 {len(SOURCES)}건 / 실패 {fail}건 · 저장 위치 {RAW}")
    if fail:
        print("실패한 것은 잠시 뒤 다시 실행하면 대개 받아집니다.")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
