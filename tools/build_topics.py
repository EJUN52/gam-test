# -*- coding: utf-8 -*-
"""공개 데이터 → 10주제 × 5문항.

**모든 숫자는 raw/ 의 원본에서 계산합니다.** 지어낸 값이 하나도 없어야 합니다.
결과는 앱이 읽는 topics/*.json 과, 사람이 읽는 tools/정답지.md 로 나갑니다.

정답지와 이 스크립트는 .vercelignore 에 들어 있어 **배포되지 않습니다.**
공개 URL 에 정답지가 올라가면 게임이 성립하지 않습니다.

실행 (저장소 최상위에서):
    python tools/build_topics.py
"""
from __future__ import annotations

import collections
import csv
import io
import json
import sys
import zipfile
import datetime as dt
from collections import Counter
from pathlib import Path
from statistics import mean

# 윈도우 콘솔(cp949)은 이모지 · 기호를 못 찍고 멈춘다. 출력만 UTF-8 로 맞춘다
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

HERE = Path(__file__).resolve().parent          # tools/
APP = HERE.parent                                # 저장소 최상위 = 배포되는 곳
RAW = APP / "data" / "raw"
OUT = APP / "topics"

TOPICS: list[dict] = []


def load_json(name):
    return json.load(io.open(RAW / name, encoding="utf-8"))


def load_csv(name, encoding="utf-8"):
    return list(csv.DictReader(io.open(RAW / name, encoding=encoding, newline="")))


# World Bank·OWID 응답에는 '유럽연합' '고소득국' 같은 **집계치**가 섞여 있다.
# 그대로 순위를 매기면 나라와 대륙을 한 줄에 놓고 세는 셈이 된다.
REAL = {x["id"] for x in load_json("wb_countries.json")[1]
        if x["region"]["id"] != "NA"}


def wb_countries(rows, year):
    """그 해의 실제 국가 값만 남긴다 (집계치 제외)."""
    return {r["country"]["value"]: r["value"] for r in rows
            if int(r["date"]) == year and r["countryiso3code"] in REAL}


def owid_countries(rows, year, col):
    """OWID 도 마찬가지. code 가 비었거나 OWID_ 로 시작하면 집계치다."""
    return {r["entity"]: float(r[col]) for r in rows
            if int(r["year"]) == year and r["code"]
            and not r["code"].startswith("OWID")}


def topic(tid, emoji, title, blurb, source, source_url, questions, caveat=""):
    """caveat = 이 데이터를 믿을 때의 한계. 앱 화면에도 그대로 나간다.

    출처가 다르면 같은 '서울 기온'도 값이 다르다. 그 사실을 감추지 않는다.
    """
    TOPICS.append({"id": tid, "emoji": emoji, "title": title, "blurb": blurb,
                   "source": source, "source_url": source_url,
                   "caveat": caveat, "questions": questions})


def slider(qid, text, answer, unit, lo, hi, step, basis, why):
    return {"id": qid, "type": "slider", "text": text, "unit": unit,
            "min": lo, "max": hi, "step": step,
            "answer": round(float(answer), 1), "basis": basis, "why": why}


def choice(qid, text, options, answer, basis, why):
    assert answer in options, f"{qid}: 정답이 선택지에 없습니다"
    return {"id": qid, "type": "choice", "text": text, "options": options,
            "answer": answer, "basis": basis, "why": why}


# ════════════════════════════════════════════════════════════════
# 기상 공통
# ════════════════════════════════════════════════════════════════
w = load_json("seoul_weather.json")["daily"]
W = [{"d": dt.date.fromisoformat(t), "hi": hi, "lo": lo, "rain": r}
     for t, hi, lo, r in zip(w["time"], w["temperature_2m_max"],
                             w["temperature_2m_min"], w["precipitation_sum"])]
W24 = [x for x in W if x["d"].year == 2024]


def years(a, b):
    return [x for x in W if a <= x["d"].year <= b]


# ── 1. 서울 기온 ─────────────────────────────────────────────────
# ERA5 는 1950~70년대 구간의 품질이 낮고(초기 확장), 격자 평균이라 도심
# 관측값보다 낮게 나온다. 그래서 '역대 최고기온'이나 '폭염일 추세'처럼
# 그 구간에 기대는 문항은 쓰지 않는다. 열대야·연평균처럼 신호가 뚜렷한 것만 쓴다.
tropical_24 = sum(1 for x in W24 if x["lo"] >= 25)
trop_50s = sum(1 for x in years(1950, 1959) if x["lo"] >= 25) / 10
trop_10s = sum(1 for x in years(2015, 2024) if x["lo"] >= 25) / 10
t_ratio = trop_10s / trop_50s if trop_50s else 0
mean_50s = mean((x["hi"] + x["lo"]) / 2 for x in years(1950, 1959))
mean_10s = mean((x["hi"] + x["lo"]) / 2 for x in years(2015, 2024))
warming = mean_10s - mean_50s
below0_24 = sum(1 for x in W24 if x["lo"] < 0)
hot_days = Counter((x["d"].month, x["d"].day)
                   for x in years(1995, 2024) if x["hi"] >= 33)
peak_day = hot_days.most_common(1)[0]
# 한계 문장의 숫자도 손으로 적지 않는다 — 원본에서 가장 더웠던 날을 찾는다
hottest = max(W, key=lambda x: x["hi"])

topic(
    "seoul-heat", "🌡️", "서울은 얼마나 더워졌나",
    "1950년부터 2024년까지, 서울의 매일 기온",
    "Open-Meteo Archive (ERA5 재분석)", "https://open-meteo.com/",
    [
        slider("h1", "2024년 서울에서 열대야(밤 최저기온 25도 이상)는 며칠이었을까요?",
               tropical_24, "일", 0, 60, 1,
               f"2024년 일최저기온 25도 이상인 날 {tropical_24}일",
               "유난히 더웠던 밤 몇 번이 기억을 지배합니다. 실제 일수는 세어 봐야 "
               "압니다."),
        # 보기는 배수에 가장 가까운 것이 정답이 되게 경계를 둔다 (2.8배 → «약 3배»)
        choice("h2", "1950년대와 2015~2024년, 열대야는 몇 배 차이일까요?",
               ["거의 같다", "약 2배", "약 3배", "약 5배"],
               ["거의 같다", "약 2배", "약 3배", "약 5배"][
                   0 if t_ratio < 1.5 else 1 if t_ratio < 2.5
                   else 2 if t_ratio < 4 else 3],
               f"연평균 열대야 1950년대 {trop_50s:.1f}일 → 2015~2024년 "
               f"{trop_10s:.1f}일 ({t_ratio:.1f}배)",
               "'옛날에도 더웠다'는 느낌과 기록은 다릅니다. 기억은 유난히 더웠던 "
               "몇 밤으로 남지만, 기록은 해마다 빠짐없이 셉니다."),
        slider("h3", "1950년대와 비교해 서울의 연평균 기온은 몇 도 올랐을까요?",
               warming, "도", 0, 4, 0.1,
               f"1950년대 {mean_50s:.2f}도 → 2015~2024년 {mean_10s:.2f}도 "
               f"(+{warming:.2f}도)",
               "1~2도는 작아 보이지만, 그 변화가 열대야 일수를 몇 배로 바꿉니다. "
               "평균의 변화와 극단의 변화는 크기가 다릅니다."),
        choice("h4", "최근 30년간 33도 이상인 날이 가장 잦았던 날짜는?",
               ["7월 초", "7월 말", "8월 초", "8월 말"],
               "7월 말" if peak_day[0][0] == 7 and peak_day[0][1] >= 20
               else "8월 초" if peak_day[0][0] == 8 and peak_day[0][1] <= 10
               else "7월 초" if peak_day[0][0] == 7 else "8월 말",
               f"1995~2024년 중 가장 잦았던 날짜는 {peak_day[0][0]}월 "
               f"{peak_day[0][1]}일 ({peak_day[1]}회)",
               "장마가 끝나는 시점과 가장 더운 시점은 다릅니다."),
        slider("h5", "2024년 서울에서 밤 기온이 영하로 내려간 날은 며칠이었을까요?",
               below0_24, "일", 30, 150, 5,
               f"2024년 일최저기온 0도 미만인 날 {below0_24}일",
               "겨울이 짧아졌다고 느끼지만, 영하로 내려가는 날은 여전히 석 달 "
               "치가 넘습니다."),
    ],
    caveat="ERA5는 넓은 격자의 재분석 값이라 도심 관측소와 다르게 나옵니다. "
           f"예컨대 여기서는 역대 최고기온이 {hottest['hi']:.1f}도"
           f"({hottest['d']:%Y년})지만 기상청 서울 관측 기록은 2018년 39.6도입니다. "
           "같은 '서울 기온'도 출처에 따라 다릅니다.")

# ── 2. 비 ────────────────────────────────────────────────────────
rain_days = [sum(1 for x in W if x["d"].year == y and x["rain"] >= 1.0)
             for y in range(1995, 2025)]
rain_avg = mean(rain_days)
by_month = {m: mean([sum(x["rain"] for x in W
                         if x["d"].year == y and x["d"].month == m)
                     for y in range(1995, 2025)]) for m in range(1, 13)}
wettest_m = max(by_month, key=by_month.get)
max_day = max(W, key=lambda x: x["rain"])
ann = {y: sum(x["rain"] for x in W if x["d"].year == y) for y in range(1995, 2025)}
norm = mean(ann.values())
r2024 = ann[2024]


def days_to_half(y):
    v = sorted((x["rain"] for x in W if x["d"].year == y), reverse=True)
    half, s = sum(v) / 2, 0
    for i, r in enumerate(v, 1):
        s += r
        if s >= half:
            return i
    return len(v)


half_days = round(mean(days_to_half(y) for y in range(1995, 2025)))

topic(
    "seoul-rain", "☔", "비는 언제, 얼마나",
    "서울의 하루치 강수량 30년",
    "Open-Meteo Archive (ERA5 재분석)", "https://open-meteo.com/",
    [
        slider("r1", "서울에서 1년 중 비가 온 날(1mm 이상)은 며칠쯤일까요?",
               rain_avg, "일", 40, 160, 5,
               f"1995~2024년 평균 {rain_avg:.1f}일 "
               f"(최소 {min(rain_days)}일 · 최대 {max(rain_days)}일)",
               "비 오는 날은 기억에 오래 남아서 실제보다 많게 느껴집니다."),
        choice("r2", "1년 강수량이 가장 많은 달은?",
               ["6월", "7월", "8월", "9월"], f"{wettest_m}월",
               " · ".join(f"{m}월 {by_month[m]:.0f}mm" for m in (6, 7, 8, 9)),
               "장마가 낀 달과 비가 가장 많이 오는 달이 같지 않을 수 있습니다."),
        slider("r3", "하루에 내린 비의 최대 기록은?",
               max_day["rain"], "mm", 100, 500, 10,
               f"{max_day['d']:%Y년 %m월 %d일} {max_day['rain']:.1f}mm",
               f"가장 많이 온 날 하루에, 비가 가장 많은 {wettest_m}월 한 달 평균"
               f"({by_month[wettest_m]:.0f}mm)의 {max_day['rain'] / by_month[wettest_m] * 100:.0f}%가 "
               "쏟아졌습니다. 비는 고르게 오지 않습니다."),
        slider("r4", "1년 강수량의 절반은 '비 온 날' 며칠 만에 채워질까요?",
               half_days, "일", 3, 40, 1,
               f"많이 온 날부터 더해서 연 강수량의 절반에 도달하는 데 "
               f"평균 {half_days}일 (1995~2024년)",
               "비는 고르게 오지 않습니다. 열흘 남짓이 1년의 절반을 만듭니다."),
        slider("r5", "2024년 서울 강수량은 30년 평균의 몇 %였을까요?",
               r2024 / norm * 100, "%", 50, 180, 5,
               f"2024년 {r2024:.0f}mm · 1995~2024년 평균 {norm:.0f}mm",
               "'올해 비가 많았다'는 체감과 실제 총량은 자주 어긋납니다."),
    ],
    caveat="ERA5 재분석 값입니다. 기상청 관측 강수량과 조금씩 다릅니다.")

# ── 3. 미세먼지 ──────────────────────────────────────────────────
a = load_json("seoul_air.json")["hourly"]
A = [{"t": dt.datetime.fromisoformat(t), "pm25": p25, "pm10": p10}
     for t, p25, p10 in zip(a["time"], a["pm2_5"], a["pm10"])]
A24 = [x for x in A if x["t"].year == 2024]
pm_month = {m: mean([x["pm25"] for x in A if x["t"].month == m])
            for m in range(1, 13)}
worst_m = max(pm_month, key=pm_month.get)
pm_hour = {h: mean([x["pm25"] for x in A if x["t"].hour == h])
           for h in range(24)}
worst_h = max(pm_hour, key=pm_hour.get)
pm24_avg = mean(x["pm25"] for x in A24)


def daily_avg(year):
    d = {}
    for x in A:
        if x["t"].year == year:
            d.setdefault(x["t"].date(), []).append(x["pm25"])
    return {k: mean(v) for k, v in d.items()}


d24 = daily_avg(2024)
d23 = daily_avg(2023)
bad_ratio = sum(1 for v in d24.values() if v > 35) / len(d24) * 100
worse_year = "2023년" if mean(d23.values()) > mean(d24.values()) else "2024년"

topic(
    "seoul-air", "😷", "미세먼지, 언제 나쁜가",
    "서울의 시간별 초미세먼지 2년치",
    "Open-Meteo Air Quality (CAMS)", "https://open-meteo.com/",
    [
        choice("a1", "초미세먼지(PM2.5)가 가장 나쁜 달은?",
               ["1월", "3월", "5월", "11월"],
               f"{worst_m}월" if f"{worst_m}월" in ["1월", "3월", "5월", "11월"]
               else "3월",
               " · ".join(f"{m}월 {pm_month[m]:.1f}" for m in (1, 3, 5, 11))
               + f" (최악은 {worst_m}월 {pm_month[worst_m]:.1f})",
               "황사 뉴스가 많은 달과 실제 수치가 높은 달은 다를 수 있습니다."),
        slider("a2", "2024년 서울의 초미세먼지 연평균 농도는?",
               pm24_avg, "㎍/㎥", 5, 60, 1,
               f"2024년 시간값 {len(A24):,}개의 평균 {pm24_avg:.1f}㎍/㎥ "
               f"(WHO 권고 연평균 5, 국내 기준 15)",
               "'나쁨'인 날이 인상에 남아서 연평균을 높게 잡게 됩니다."),
        choice("a3", "하루 중 초미세먼지가 가장 높은 시간대는?",
               ["새벽 4시", "오전 10시", "오후 3시", "밤 9시"],
               {4: "새벽 4시", 10: "오전 10시", 15: "오후 3시",
                21: "밤 9시"}.get(worst_h, "오전 10시"),
               " · ".join(f"{h}시 {pm_hour[h]:.1f}" for h in (4, 10, 15, 21))
               + f" (최고는 {worst_h}시)",
               "출퇴근 시간이 가장 나쁠 것 같지만 대기가 정체되는 시간은 따로 "
               "있습니다."),
        slider("a4", "2024년 하루 평균이 '나쁨'(35㎍/㎥ 초과)이었던 날의 비율은?",
               bad_ratio, "%", 0, 60, 1,
               f"2024년 {len(d24)}일 중 "
               f"{sum(1 for v in d24.values() if v > 35)}일",
               "마스크를 챙긴 날은 강하게 기억되지만, 1년 전체로 보면 비율이 "
               "다릅니다."),
        choice("a5", "2023년과 2024년 중 초미세먼지가 더 나빴던 해는?",
               ["2023년", "2024년"], worse_year,
               f"연평균 2023년 {mean(d23.values()):.1f} · "
               f"2024년 {mean(d24.values()):.1f}㎍/㎥",
               "체감은 최근 쪽으로 쏠립니다. 두 해 차이는 생각보다 작습니다."),
    ],
    caveat="CAMS 대기질 모델의 추정값입니다. 에어코리아 측정소 실측값과 "
           "다를 수 있습니다.")

# ── 4. 노동시간 ──────────────────────────────────────────────────
wh = [r for r in load_csv("working_hours.csv") if r["working_hours_omm"]]
latest_year = max(int(r["year"]) for r in wh if r["code"] == "KOR")
cur = owid_countries(wh, latest_year, "working_hours_omm")
kor = cur["South Korea"]
rank = sorted(cur.items(), key=lambda kv: -kv[1])
kor_rank = [k for k, _ in rank].index("South Korea") + 1
longer = kor_rank - 1
past = {int(r["year"]): float(r["working_hours_omm"])
        for r in wh if r["code"] == "KOR"}
y30 = latest_year - 30
drop = past[y30] - kor
trio = {c: cur[c] for c in ("South Korea", "Japan", "Germany") if c in cur}
shortest = min(trio, key=trio.get)
name_ko = {"South Korea": "한국", "Japan": "일본", "Germany": "독일"}

topic(
    "working-hours", "⏰", "우리는 얼마나 일하나",
    "나라별 1인당 연간 노동시간",
    "Our World in Data", "https://ourworldindata.org/grapher/annual-working-hours-per-worker",
    [
        slider("w1", f"{latest_year}년 한국의 1인당 연간 노동시간은?",
               kor, "시간", 1200, 2600, 50,
               f"{latest_year}년 한국 {kor:,.0f}시간 "
               f"(주 5일 기준 하루 약 {kor / 250:.1f}시간)",
               "연 단위로 물으면 감이 잘 안 옵니다. 하루로 나눠 보면 체감과 "
               "맞는지 확인할 수 있습니다."),
        slider("w2", f"한국보다 더 오래 일하는 나라는 {len(cur)}개국 중 몇 개일까요?",
               longer, "개국", 0, 60, 1,
               f"{latest_year}년 기준 {len(cur)}개국 중 한국은 {kor_rank}위",
               "'한국이 제일 많이 일한다'는 인상이 강하지만, 비교 대상에 따라 "
               "순위가 달라집니다."),
        slider("w3", f"한국의 노동시간은 30년 전({y30}년)보다 몇 시간 줄었을까요?",
               drop, "시간", 0, 900, 50,
               f"{y30}년 {past[y30]:,.0f}시간 → {latest_year}년 {kor:,.0f}시간",
               "줄어든 폭은 대개 과소평가됩니다. 하루로 치면 크게 달라진 값입니다."),
        choice("w4", "한국·일본·독일 중 가장 적게 일하는 나라는?",
               ["한국", "일본", "독일"], name_ko[shortest],
               " · ".join(f"{name_ko[c]} {trio[c]:,.0f}시간" for c in trio),
               "나라마다 통계 기준이 다릅니다. 순위보다 격차의 크기를 봅니다."),
        slider("w5", "한국과 독일의 연간 노동시간 차이는?",
               abs(cur["South Korea"] - cur["Germany"]), "시간", 0, 900, 50,
               f"한국 {cur['South Korea']:,.0f} · 독일 "
               f"{cur['Germany']:,.0f}시간",
               "두 나라 차이를 주 단위로 나눠 보면 체감이 확 달라집니다."),
    ],
    caveat="이 자료에는 개발도상국이 많이 포함돼 있어, OECD 안에서의 순위와 "
           "전체 순위가 다릅니다. '어느 집단과 비교하느냐'가 순위를 만듭니다.")

# ── 5. 인구와 출산 ───────────────────────────────────────────────
fert = [r for r in load_json("wb_fertility.json")[1] if r["value"] is not None]
f_latest = max(int(r["date"]) for r in fert if r["countryiso3code"] == "KOR")
f_cur = wb_countries(fert, f_latest)
kor_f = f_cur["Korea, Rep."]
f_rank = sorted(f_cur.items(), key=lambda kv: kv[1])
kor_f_rank = [k for k, _ in f_rank].index("Korea, Rep.") + 1
kor_1970 = next(r["value"] for r in fert
                if r["countryiso3code"] == "KOR" and r["date"] == "1970")

pop = load_json("wb_pop_kor.json")[1]
tot = {int(r["date"]): r["value"] for r in pop
       if r["indicator"]["id"] == "SP.POP.TOTL" and r["value"]}
old = {int(r["date"]): r["value"] for r in pop
       if r["indicator"]["id"] == "SP.POP.65UP.TO.ZS" and r["value"]}
urb = {int(r["date"]): r["value"] for r in pop
       if r["indicator"]["id"] == "SP.URB.TOTL.IN.ZS" and r["value"]}
peak_year = max(tot, key=tot.get)
old_latest = max(old)
urb_latest = max(urb)

topic(
    "population", "👶", "인구와 출산",
    "전 세계 출산율과 한국의 인구 구조",
    "World Bank Open Data", "https://data.worldbank.org/",
    [
        slider("p1", f"{f_latest}년 한국의 합계출산율(여성 1명당 출생아 수)은?",
               kor_f, "명", 0.5, 3.0, 0.05,
               f"{f_latest}년 한국 {kor_f:.2f}명",
               "숫자는 자주 들었어도 '여성 1명당'이라는 단위는 잘 안 와닿습니다."),
        slider("p2", f"출산율이 낮은 순으로 세면 한국은 {len(f_cur)}개 나라·지역 중 몇 위일까요?",
               kor_f_rank, "위", 1, 30, 1,
               f"{f_latest}년 기준 {len(f_cur)}곳 중 {kor_f_rank}위 "
               f"(1위 {f_rank[0][0]} {f_rank[0][1]:.2f})",
               "'꼴찌'라고 알고 있지만, 비교 목록에 어떤 나라·지역이 들어가느냐에 "
               "따라 순위가 달라집니다."),
        slider("p3", "1970년 한국의 출산율은 몇 명이었을까요?",
               kor_1970, "명", 1.0, 7.0, 0.1,
               f"1970년 {kor_1970:.2f}명 → {f_latest}년 {kor_f:.2f}명",
               "한 세대 만에 일어난 변화의 크기는 대개 과소평가됩니다."),
        slider("p4", f"{old_latest}년 한국에서 65세 이상 인구의 비율은?",
               old[old_latest], "%", 5, 35, 1,
               f"{old_latest}년 {old[old_latest]:.1f}% "
               f"(World Bank 최신 공표치. 최근 연도는 추계값입니다)",
               "고령화는 '다가올 일'로 느껴지지만 이미 지나온 숫자입니다."),
        slider("p5", f"{urb_latest}년 한국에서 도시에 사는 사람의 비율은?",
               urb[urb_latest], "%", 50, 100, 1,
               f"{urb_latest}년 {urb[urb_latest]:.1f}% "
               f"(World Bank 최신 공표치. 최근 연도는 추계값입니다)",
               "'절반쯤'이라고 답하기 쉽지만 한국은 세계에서도 손꼽히는 도시 국가입니다."),
    ])

# ── 6. 인터넷 ────────────────────────────────────────────────────
net = [r for r in load_json("wb_internet.json")[1] if r["value"] is not None]
n_latest = max(int(r["date"]) for r in net if r["countryiso3code"] == "KOR")
n_cur = wb_countries(net, n_latest)
kor_n = n_cur["Korea, Rep."]
n_rank = sorted(n_cur.items(), key=lambda kv: -kv[1])
kor_n_rank = [k for k, _ in n_rank].index("Korea, Rep.") + 1
kor_2000 = next(r["value"] for r in net
                if r["countryiso3code"] == "KOR" and r["date"] == "2000")
world = next((r["value"] for r in net
              if r["countryiso3code"] == "WLD" and int(r["date"]) == n_latest), None)
if world is None:
    world = mean(n_cur.values())
offline = 100 - world

topic(
    "internet", "🌐", "인터넷과 연결",
    "나라별 인터넷 사용 인구 비율",
    "World Bank Open Data", "https://data.worldbank.org/",
    [
        slider("i1", f"{n_latest}년 한국에서 인터넷을 쓰는 사람의 비율은?",
               kor_n, "%", 60, 100, 1,
               f"{n_latest}년 한국 {kor_n:.1f}%",
               "'거의 다'라고 생각하지만 100%는 아닙니다. 남은 몇 %가 누구인지가 "
               "정책의 대상입니다."),
        slider("i2", f"한국보다 인터넷 사용률이 높은 나라는 {len(n_cur)}곳 중 몇 곳일까요?",
               kor_n_rank - 1, "곳", 0, 60, 1,
               f"{n_latest}년 {len(n_cur)}곳 중 한국 {kor_n_rank}위",
               "'IT 강국'이라는 말과 실제 보급률 순위는 다른 이야기입니다."),
        slider("i3", "2000년 한국의 인터넷 사용률은?",
               kor_2000, "%", 0, 100, 5,
               f"2000년 {kor_2000:.1f}% → {n_latest}년 {kor_n:.1f}%",
               "20여 년 전을 떠올릴 때는 지금의 기준으로 과대평가하기 쉽습니다."),
        slider("i4", f"{n_latest}년 전 세계 평균 인터넷 사용률은?",
               world, "%", 20, 100, 5,
               f"{n_latest}년 세계 {world:.1f}%",
               "내 주변이 전부 연결돼 있으면 세계도 그럴 거라고 생각하게 됩니다."),
        slider("i5", "전 세계에서 인터넷을 쓰지 않는 사람은 몇 %일까요?",
               offline, "%", 0, 70, 5,
               f"100 - {world:.1f} = {offline:.1f}%",
               "같은 사실을 뒤집어 물으면 전혀 다른 크기로 느껴집니다."),
    ])

# ── 7. 환율 ──────────────────────────────────────────────────────
fx = load_json("usdkrw.json")["rates"]
FX = sorted((d, v["KRW"]) for d, v in fx.items() if "KRW" in v)
hi_d, hi_v = max(FX, key=lambda x: x[1])
lo_d, lo_v = min(FX, key=lambda x: x[1])
avg_fx = mean(v for _, v in FX)
under1200 = sum(1 for _, v in FX if v < 1200) / len(FX) * 100
last_d, last_v = FX[-1]
era = ("1997~1999년 외환위기" if hi_d < "2005" else
       "2008~2009년 금융위기" if hi_d < "2012" else
       "2020년 코로나" if hi_d < "2022" else "2022년 이후")

topic(
    "usdkrw", "💵", "원달러 환율 26년",
    "1999년부터 오늘까지의 원달러 환율",
    "Frankfurter (유럽중앙은행 고시)", "https://frankfurter.dev/",
    [
        slider("x1", "1999년 이후 원달러 환율의 최고 기록은?",
               hi_v, "원", 1100, 1800, 25,
               f"{hi_d} {hi_v:,.2f}원",
               "최고치는 위기의 기억과 함께 남지만, 정확한 시점은 자주 헷갈립니다."),
        choice("x2", "그 최고치를 찍은 시기는?",
               ["1997~1999년 외환위기", "2008~2009년 금융위기",
                "2020년 코로나", "2022년 이후"], era,
               f"최고 {hi_v:,.2f}원 ({hi_d}). 이 데이터는 1999년부터라 "
               f"1997~98년 외환위기 구간은 포함되어 있지 않습니다",
               "데이터가 시작하는 시점을 확인하지 않으면 '역대 최고'를 잘못 "
               "말하게 됩니다."),
        slider("x3", "26년간의 평균 환율은?",
               avg_fx, "원", 900, 1500, 25,
               f"{FX[0][0]} ~ {FX[-1][0]} 거래일 {len(FX):,}일 평균 "
               f"{avg_fx:,.0f}원 (최저 {lo_v:,.0f}원 · {lo_d})",
               "최근 값이 기준점이 되어 과거 평균을 높게 잡게 됩니다."),
        slider("x4", "환율이 1,200원 아래였던 날은 전체의 몇 %일까요?",
               under1200, "%", 0, 100, 5,
               f"거래일 {len(FX):,}일 중 1,200원 미만은 "
               f"{sum(1 for _, v in FX if v < 1200):,}일",
               "'원래 1,100원대였는데'라는 감각이 맞는지 비율로 확인해 봅니다."),
        slider("x5", f"{last_d} 기준 환율은?",
               last_v, "원", 1100, 1800, 25,
               f"{last_d} {last_v:,.2f}원",
               "가장 최근 값조차 기억은 며칠 전 뉴스에 묶여 있습니다."),
    ])

# ── 8. 도시 비교 ─────────────────────────────────────────────────
CITY = {}
for cid in ("seoul", "tokyo", "london", "singapore"):
    _d = load_json(f"city_{cid}.json")["daily"]
    CITY[cid] = [{"d": dt.date.fromisoformat(t), "hi": a, "lo": b, "r": c}
                 for t, a, b, c in zip(_d["time"], _d["temperature_2m_max"],
                                       _d["temperature_2m_min"],
                                       _d["precipitation_sum"])]
CN = {"seoul": "서울", "tokyo": "도쿄", "london": "런던", "singapore": "싱가포르"}
YRS = 30
c_rain = {k: sum(x["r"] for x in v) / YRS for k, v in CITY.items()}
c_days = {k: sum(1 for x in v if x["r"] >= 1) / YRS for k, v in CITY.items()}
c_temp = {k: mean((x["hi"] + x["lo"]) / 2 for x in v) for k, v in CITY.items()}
c_hot = {k: max(x["hi"] for x in v) for k, v in CITY.items()}
c_jan = {k: mean(x["lo"] for x in v if x["d"].month == 1) for k, v in CITY.items()}
dry = min(c_rain, key=c_rain.get)
hottest = max(c_hot, key=c_hot.get)
colder = "서울" if c_jan["seoul"] < c_jan["tokyo"] else "도쿄"

topic(
    "cities", "🏙️", "서울·도쿄·런던·싱가포르",
    "네 도시의 30년 평년값 (1991~2020)",
    "Open-Meteo Archive (ERA5 재분석)", "https://open-meteo.com/",
    [
        choice("c1", "1년 강수량이 가장 적은 도시는?",
               ["서울", "도쿄", "런던", "싱가포르"], CN[dry],
               " · ".join(f"{CN[k]} {c_rain[k]:,.0f}mm" for k in CITY),
               "비가 자주 오는 것과 많이 오는 것은 다릅니다. 런던은 자주 오지만 "
               "적게 옵니다."),
        slider("c2", "런던에서 1년에 비가 오는 날(1mm 이상)은 며칠일까요?",
               c_days["london"], "일", 40, 220, 5,
               f"런던 {c_days['london']:.0f}일 · 서울 {c_days['seoul']:.0f}일 "
               f"(강수량은 런던 {c_rain['london']:,.0f}mm · "
               f"서울 {c_rain['seoul']:,.0f}mm)",
               "런던은 서울보다 비 오는 날이 많은데 총량은 절반입니다. "
               "'며칠 왔나'와 '얼마나 왔나'는 다른 질문입니다."),
        choice("c3", "30년간 가장 높은 기온을 기록한 도시는?",
               ["서울", "도쿄", "런던", "싱가포르"], CN[hottest],
               " · ".join(f"{CN[k]} {c_hot[k]:.1f}도" for k in CITY),
               "적도에 가까울수록 덥다고 생각하지만, 최고기온 기록은 중위도 "
               "도시에서 나옵니다."),
        slider("c4", "서울의 연평균 기온은?",
               c_temp["seoul"], "도", 5, 30, 0.5,
               " · ".join(f"{CN[k]} {c_temp[k]:.1f}도" for k in CITY),
               "여름과 겨울의 기억이 강해서 연평균은 감이 잘 안 옵니다."),
        choice("c5", "1월 밤이 더 추운 도시는?",
               ["서울", "도쿄"], colder,
               f"1월 평균 최저기온 서울 {c_jan['seoul']:.1f}도 · "
               f"도쿄 {c_jan['tokyo']:.1f}도",
               "위도가 비슷해도 대륙의 영향을 받는 도시가 훨씬 춥습니다."),
    ],
    caveat="ERA5 재분석 값이고, 도시별로 관측소 위치와 기준이 다릅니다.")

# ── 9. 지진 ──────────────────────────────────────────────────────
Q = [f["properties"] for f in load_json("quakes.geojson")["features"]]
QK = [f["properties"] for f in load_json("quakes_korea.geojson")["features"]]
n_years = 25
per_year = len(Q) / n_years
m7 = sum(1 for p in Q if p["mag"] >= 7.0) / n_years
biggest = max(Q, key=lambda p: p["mag"])


def region(place):
    return (place or "").split(",")[-1].strip()


top_region = Counter(region(p["place"]) for p in Q).most_common(1)[0]
region_ko = {"Japan": "일본", "Indonesia": "인도네시아", "Chile": "칠레",
             "Philippines": "필리핀"}
kr_band = ("50건 미만" if len(QK) < 50 else "50~150건" if len(QK) <= 150
           else "150~400건" if len(QK) <= 400 else "400건 이상")

topic(
    "quakes", "🌎", "지진은 얼마나 자주",
    "2000~2024년 전 세계 지진 기록",
    "USGS 지진 카탈로그", "https://earthquake.usgs.gov/",
    [
        slider("q1", "규모 5.5 이상 지진은 전 세계에서 1년에 몇 번쯤 일어날까요?",
               per_year, "회", 50, 1200, 50,
               f"2000~2024년 {len(Q):,}건 ÷ {n_years}년 = "
               f"연평균 {per_year:.0f}회",
               "뉴스에 나오는 지진만 세면 실제보다 훨씬 적게 잡게 됩니다."),
        slider("q2", "규모 7.0 이상은 1년에 몇 번쯤일까요?",
               m7, "회", 0, 40, 1,
               f"2000~2024년 규모 7.0 이상 "
               f"{sum(1 for p in Q if p['mag'] >= 7.0)}건, 연평균 {m7:.1f}회",
               "규모는 로그 척도입니다. 0.5만 올라가도 횟수가 크게 줄어듭니다."),
        choice("q3", "규모 5.5 이상 지진이 가장 자주 기록된 나라는?",
               ["일본", "인도네시아", "칠레", "필리핀"],
               region_ko.get(top_region[0], "인도네시아"),
               f"1위 {top_region[0]} {top_region[1]:,}건",
               "지진 하면 떠오르는 나라와 실제로 가장 많이 기록되는 곳은 "
               "다를 수 있습니다."),
        slider("q4", "2000년 이후 기록된 가장 큰 지진의 규모는?",
               biggest["mag"], "", 7.0, 9.9, 0.1,
               f"규모 {biggest['mag']} · "
               f"{dt.datetime.fromtimestamp(biggest['time'] / 1000, dt.UTC):%Y-%m-%d} "
               f"{biggest['place']}",
               "규모 9는 8보다 약 32배 큰 에너지입니다."),
        choice("q5", "한반도 주변(위도 33~39.5도)에서 25년간 기록된 규모 3.0 이상 지진은?",
               ["50건 미만", "50~150건", "150~400건", "400건 이상"], kr_band,
               f"USGS 기준 {len(QK)}건. 이 관측망은 작은 지진을 모두 잡지는 "
               f"못하므로 기상청 집계와 다릅니다",
               "'어느 기관이 센 숫자인가'를 확인하지 않으면 같은 현상도 다른 "
               "값이 됩니다."),
    ],
    caveat="USGS 카탈로그는 작은 지진을 모두 담지 못합니다. 한반도 지진은 "
           "기상청 집계가 더 많습니다.")

# ── 10. 수명 ─────────────────────────────────────────────────────
le = [r for r in load_csv("life_expectancy.csv") if r["life_expectancy_0"]]
l_latest = max(int(r["year"]) for r in le if r["code"] == "KOR")
l_cur = owid_countries(le, l_latest, "life_expectancy_0")
kor_l = l_cur["South Korea"]
l_rank = sorted(l_cur.items(), key=lambda kv: -kv[1])
kor_l_rank = [k for k, _ in l_rank].index("South Korea") + 1
_kle = {r["year"]: float(r["life_expectancy_0"]) for r in le if r["code"] == "KOR"}
kor_1950, kor_1953, kor_1955 = _kle["1950"], _kle["1953"], _kle["1955"]
wld = next(float(r["life_expectancy_0"]) for r in le
           if r["code"] == "OWID_WRL" and int(r["year"]) == l_latest)
trio_l = {c: l_cur[c] for c in ("South Korea", "Japan", "United States")
          if c in l_cur}
top_l = max(trio_l, key=trio_l.get)
name_l = {"South Korea": "한국", "Japan": "일본", "United States": "미국"}

topic(
    "life", "🩺", "얼마나 오래 사나",
    "나라별 기대수명 1950~현재",
    "Our World in Data", "https://ourworldindata.org/grapher/life-expectancy",
    [
        slider("l1", f"{l_latest}년 한국의 기대수명은?",
               kor_l, "세", 60, 95, 1,
               f"{l_latest}년 한국 {kor_l:.1f}세",
               "기대수명은 '지금 태어난 아이가 평균적으로 살 햇수'입니다. "
               "지금 살아 있는 사람의 예상 수명과는 다릅니다."),
        slider("l2", f"기대수명이 긴 순으로 세면 한국은 {len(l_cur)}곳 중 몇 위일까요?",
               kor_l_rank, "위", 1, 60, 1,
               f"{l_latest}년 {len(l_cur)}곳 중 {kor_l_rank}위 "
               f"(1위 {l_rank[0][0]} {l_rank[0][1]:.1f}세)",
               "상위권인 것은 맞지만 몇 위인지는 대개 크게 빗나갑니다."),
        slider("l3", "1950년 한국의 기대수명은?",
               kor_1950, "세", 20, 70, 1,
               f"1950년 {kor_1950:.1f}세. 한국전쟁 기간의 사망이 반영된 값이라 "
               f"1953년 {kor_1953:.1f}세, 1955년 {kor_1955:.1f}세로 빠르게 "
               f"회복합니다. {l_latest}년은 {kor_l:.1f}세",
               "숫자가 튀면 사건을 의심해야 합니다. 이 값은 오류가 아니라 "
               "전쟁의 기록입니다."),
        choice("l4", "한국·일본·미국 중 기대수명이 가장 긴 나라는?",
               ["한국", "일본", "미국"], name_l[top_l],
               " · ".join(f"{name_l[c]} {trio_l[c]:.1f}세" for c in trio_l),
               "가장 잘사는 나라가 가장 오래 사는 나라는 아닙니다."),
        slider("l5", f"{l_latest}년 세계 평균 기대수명은?",
               wld, "세", 50, 90, 1,
               f"{l_latest}년 세계 평균 {wld:.1f}세 · 한국 {kor_l:.1f}세",
               "내가 사는 곳의 수준을 세계 평균으로 착각하기 쉽습니다."),
    ])

# ── 11. 눈 ───────────────────────────────────────────────────────
# '눈 온 날' = 하루 강설량 1cm 이상. 모델 값이라 0.01cm 같은 부스러기가 많아
# 기준 없이 세면 일수가 부풀려진다.
_s = load_json("seoul_snow.json")["daily"]
S = [{"d": dt.date.fromisoformat(t), "snow": v}
     for t, v in zip(_s["time"], _s["snowfall_sum"])]
SNOW = [x for x in S if x["snow"] >= 1]
s_years = S[-1]["d"].year - S[0]["d"].year + 1
snow_avg = len(SNOW) / s_years
per_year = {y: sum(1 for x in SNOW if x["d"].year == y)
            for y in range(S[0]["d"].year, S[-1]["d"].year + 1)}
snow_90s = mean(per_year[y] for y in range(1990, 2000))
snow_10s = mean(per_year[y] for y in range(2015, 2025))
s_ratio = snow_10s / snow_90s
max_snow = max(S, key=lambda x: x["snow"])
snow_day_avg = mean(x["snow"] for x in SNOW)
snow_month = Counter(x["d"].month for x in SNOW)
top_snow_m = max((12, 1, 2, 3), key=snow_month.get)

# 첫눈은 겨울 시즌(7월 1일 ~ 이듬해 6월 30일) 단위로 센다. 1990/91 ~ 2023/24 =
# 34시즌. 2024/25 는 12월 31일에서 자료가 끊겨 완전한 시즌이 아니라 뺀다
seasons = range(S[0]["d"].year, S[-1]["d"].year)
first_off = [(min(x["d"] for x in SNOW
                  if dt.date(y, 7, 1) <= x["d"] < dt.date(y + 1, 7, 1))
              - dt.date(y, 7, 1)).days for y in seasons]
# 윤년이 아닌 해(2001/02)의 7월 1일에 얹어 날짜로 바꾼다
first_avg = dt.date(2001, 7, 1) + dt.timedelta(days=round(mean(first_off)))
first_early = dt.date(2001, 7, 1) + dt.timedelta(days=min(first_off))
first_late = dt.date(2001, 7, 1) + dt.timedelta(days=max(first_off))
first_after_newyear = sum(1 for o in first_off
                          if o >= (dt.date(2002, 1, 1) - dt.date(2001, 7, 1)).days)
# 보기는 상순(1~10일) · 중순(11~20일) · 하순(21일~)
first_band = (f"{first_avg.month}월 "
              f"{'상순' if first_avg.day <= 10 else '중순' if first_avg.day <= 20 else '하순'}")

topic(
    "seoul-snow", "❄️", "서울의 눈은 줄었나",
    "1990년부터 2024년까지, 서울의 하루 강설량",
    "Open-Meteo Archive (ERA5 재분석)", "https://open-meteo.com/",
    [
        slider("s1", "1990~2024년 서울에서 눈이 1cm 이상 온 날은 1년에 평균 며칠일까요?",
               snow_avg, "일", 0, 30, 1,
               f"{S[0]['d'].year}~{S[-1]['d'].year}년 {s_years}년 동안 하루 강설량 "
               f"1cm 이상인 날 {len(SNOW)}일 ÷ {s_years}년 = 연평균 {snow_avg:.1f}일",
               f"해마다 차이가 큽니다. 가장 적은 해는 {min(per_year.values())}일, "
               f"가장 많은 해는 {max(per_year.values())}일입니다."),
        # 경계: 1.1배 이상 늘었다 · 0.9~1.1 거의 같다 · 0.5~0.9 조금 줄었다 · 0.5 미만 절반 아래로
        choice("s2", "1990년대와 비교해 2015~2024년, 한 해 눈(1cm 이상) 온 날은 "
                     "어떻게 달라졌을까요?",
               ["늘었다", "거의 같다", "조금 줄었다", "절반 아래로 줄었다"],
               "늘었다" if s_ratio >= 1.1 else "거의 같다" if s_ratio >= 0.9
               else "조금 줄었다" if s_ratio >= 0.5 else "절반 아래로 줄었다",
               f"하루 강설량 1cm 이상인 날을 연도별로 세어 평균하면 1990~1999년 "
               f"{snow_90s:.1f}일 → 2015~2024년 {snow_10s:.1f}일 ({s_ratio:.2f}배)",
               f"가장 많았던 해는 1990~1999년 {max(range(1990, 2000), key=per_year.get)}년 "
               f"{max(per_year[y] for y in range(1990, 2000))}일, 2015~2024년 "
               f"{max(range(2015, 2025), key=per_year.get)}년 "
               f"{max(per_year[y] for y in range(2015, 2025))}일입니다."),
        slider("s3", "1990~2024년 서울에서 하루에 내린 눈의 최대 기록은?",
               max_snow["snow"], "cm", 0, 40, 1,
               f"1990~2024년 매일의 강설량 중 가장 큰 값은 "
               f"{max_snow['d']:%Y년 %m월 %d일} {max_snow['snow']:.1f}cm",
               f"1cm 이상 눈 온 날의 평균 강설량은 {snow_day_avg:.1f}cm로, "
               f"최대 기록의 {snow_day_avg / max_snow['snow'] * 100:.0f}%입니다."),
        choice("s4", "1990~2024년 서울에서 눈이 1cm 이상 온 날이 가장 많았던 달은?",
               ["12월", "1월", "2월", "3월"], f"{top_snow_m}월",
               "1990~2024년 하루 강설량 1cm 이상인 날을 달별로 세면 "
               + " · ".join(f"{m}월 {snow_month[m]}일" for m in (12, 1, 2, 3)),
               f"{top_snow_m}월 한 달에 1cm 이상 눈 온 날 {len(SNOW)}일 중 "
               f"{snow_month[top_snow_m] / len(SNOW) * 100:.0f}%가 몰려 있습니다. "
               f"보기 밖의 달은 11월 {snow_month[11]}일 · 4월 {snow_month[4]}일입니다."),
        choice("s5", f"{len(first_off)}개 겨울(1990/91~2023/24) 동안 서울의 평균 "
                     "첫눈(1cm 이상) 날짜는?",
               ["11월 하순", "12월 상순", "12월 중순", "12월 하순"], first_band,
               f"겨울 시즌(7월~이듬해 6월)마다 하루 강설량 1cm 이상인 첫날을 찾아 "
               f"{len(first_off)}시즌 평균하면 {first_avg:%m월 %d일} "
               f"(가장 이른 해 {first_early:%m월 %d일} · 가장 늦은 해 "
               f"{first_late:%m월 %d일})",
               f"{len(first_off)}시즌 중 {first_after_newyear}시즌은 1cm 이상 첫눈이 "
               "해를 넘겨 1월 이후에 왔습니다."),
    ],
    caveat="ERA5 재분석의 강설량은 모델이 계산한 값이라 기상청 서울 관측소의 "
           "적설과 다릅니다. 기상청의 '첫눈'은 쌓이지 않아도 눈발이 처음 관측된 "
           "날이라, 여기서 센 '1cm 이상 첫날'과 기준이 다릅니다.")

# ── 12. 부산 더위 ────────────────────────────────────────────────
# 기준은 기상청을 따른다: 폭염 = 일최고 33도 이상, 열대야 = 일최저 25도 이상,
# 여름 = 6~8월. 서울과 견주는 문항은 같은 출처(ERA5)끼리만 비교한다.
_b = load_json("busan_heat_plus.json")["daily"]
B = [{"d": dt.date.fromisoformat(t), "hi": hi, "lo": lo}
     for t, hi, lo in zip(_b["time"], _b["temperature_2m_max"],
                          _b["temperature_2m_min"])]
b_first, b_last = B[0]["d"].year, B[-1]["d"].year


def b_years(a, b):
    return [x for x in B if a <= x["d"].year <= b]


b_trop_24 = sum(1 for x in B if x["d"].year == 2024 and x["lo"] >= 25)
# 비교 기준은 1981~2010년 30년 평균. 1973~1982년과 견주면 ERA5 와 부산 관측소(GSOD)가
# 서로 다른 보기를 가리켰다 — 초기 ERA5 품질 탓. 30년 평균은 두 자료가 같은 보기를,
# 경계(1.5·2.5배)에서 멀리 떨어져 가리킨다
b_trop_base = sum(1 for x in b_years(1981, 2010) if x["lo"] >= 25) / 30
b_trop_10s = sum(1 for x in b_years(2015, 2024) if x["lo"] >= 25) / 10
assert b_trop_base > 0, "1981~2010년 열대야가 0일이라 배수를 낼 수 없습니다"
b_ratio = b_trop_10s / b_trop_base
s_trop_10s = sum(1 for x in years(2015, 2024) if x["lo"] >= 25) / 10
more_trop = "부산" if b_trop_10s > s_trop_10s else "서울"
b_hottest = max(B, key=lambda x: x["hi"])

# 체감온도 문항은 뺐다. Open-Meteo 의 체감온도 공식이 기상청 여름철 체감온도와 달라
# 문항이 묻는 것과 정답이 재는 것이 어긋나고, '체감 최고'와 '실제 최고'가 서로 다른
# 시각의 값이라 같은 순간의 차이도 아니었다. 대신 공식 없이 세기만 하는 문항을 둔다
#
# 남긴 다섯 문항은 부산·서울 관측소(NOAA GSOD)로 같은 기준을 세어 견줘 고른 것이다.
# 뺀 문항: 2024년 폭염일 · 폭염 최장 연속일 — ERA5 가 낮 최고기온을 낮게 잡아 관측과
# 30% 넘게 어긋났다. 첫 열대야 평균 날짜 — 관측으로 세면 정답 보기가 바뀌었다


def longest_run(days, hit):
    """조건을 만족하는 날이 끊기지 않고 이어진 가장 긴 구간 → (일수, 첫날, 끝날)."""
    best, start, cur = (0, None, None), None, 0
    for x in days:
        if hit(x):
            cur += 1
            start = x["d"] if cur == 1 else start
            if cur > best[0]:
                best = (cur, start, x["d"])
        else:
            cur = 0
    return best


b_trop_run = longest_run(b_years(2024, 2024), lambda x: x["lo"] >= 25)
assert b_trop_run[0] < 60, "연속일이 슬라이더 범위 밖입니다"

b_trop_month = Counter(x["d"].month for x in b_years(2015, 2024) if x["lo"] >= 25)
b_top_m = max(b_trop_month, key=b_trop_month.get)

topic(
    "busan-heat", "🌙", "부산의 밤은 얼마나 더운가",
    f"{b_first}년부터 {b_last}년까지, 부산의 열대야",
    "Open-Meteo Archive (ERA5 재분석)", "https://open-meteo.com/",
    [
        slider("b1", "2024년 부산에서 열대야(밤 최저기온 25도 이상)는 며칠이었을까요?",
               b_trop_24, "일", 0, 90, 1,
               f"2024년 일최저기온 25도 이상인 날을 세면 {b_trop_24}일",
               "바닷가라 밤이 시원할 거라고 생각하지만, 바다는 밤에도 열을 "
               "붙잡아 둡니다."),
        # 보기는 배수에 가장 가까운 것이 정답이 되게 경계를 둔다 (서울 h2 와 같은 경계)
        choice("b2", "1981~2010년(30년 평균)과 2015~2024년, 부산의 열대야는 몇 배 "
                     "차이일까요?",
               ["거의 같다", "약 2배", "약 3배", "약 5배"],
               ["거의 같다", "약 2배", "약 3배", "약 5배"][
                   0 if b_ratio < 1.5 else 1 if b_ratio < 2.5
                   else 2 if b_ratio < 4 else 3],
               f"일최저기온 25도 이상인 날을 해마다 세어 평균하면 "
               f"1981~2010년 {b_trop_base:.1f}일 → 2015~2024년 {b_trop_10s:.1f}일 "
               f"({b_ratio:.1f}배)",
               "'옛날에도 더웠다'는 기억은 유난히 더웠던 몇 밤으로 남지만, "
               "기록은 해마다 빠짐없이 셉니다."),
        choice("b3", "2015~2024년, 열대야가 더 많은 도시는?",
               ["서울", "부산"], more_trop,
               f"일최저기온 25도 이상인 날의 연평균(2015~2024년, 같은 ERA5 자료) "
               f"서울 {s_trop_10s:.1f}일 · 부산 {b_trop_10s:.1f}일",
               "'남쪽 바닷가는 덜 덥다'는 감은 낮 기온 이야기입니다. 밤은 "
               "다릅니다."),
        slider("b4", "2024년 부산에서 열대야는 가장 길게 며칠 연속됐을까요?",
               b_trop_run[0], "일", 0, 60, 1,
               f"2024년 일최저기온 25도 이상인 날이 끊기지 않고 이어진 가장 긴 구간 "
               f"{b_trop_run[1]:%m월 %d일}~{b_trop_run[2]:%m월 %d일} "
               f"{b_trop_run[0]}일",
               f"그해 열대야 {b_trop_24}일 가운데 {b_trop_run[0]}일이 한 번에 "
               "이어졌습니다. 더운 밤은 띄엄띄엄 오지 않고 몰려옵니다."),
        choice("b5", "2015~2024년 부산에서 열대야가 가장 많았던 달은?",
               ["6월", "7월", "8월", "9월"], f"{b_top_m}월",
               "2015~2024년 일최저기온 25도 이상인 날을 달별로 세면 "
               + " · ".join(f"{m}월 {b_trop_month[m]}일" for m in (6, 7, 8, 9)),
               f"열대야 {sum(b_trop_month.values())}일 중 "
               f"{b_trop_month[b_top_m] / sum(b_trop_month.values()) * 100:.0f}%가 "
               f"{b_top_m}월에 몰려 있습니다."),
    ],
    caveat="ERA5는 넓은 격자의 재분석 값이라 부산 관측소와 다르게 나옵니다. "
           f"여기서는 {b_first}~{b_last}년 최고기온이 {b_hottest['hi']:.1f}도"
           f"({b_hottest['d']:%Y년})인데, 격자가 바다와 육지를 섞어 평균하므로 "
           "기상청 부산 관측 기록과 다릅니다.")

# ── 13. 춘천 먹거리 ──────────────────────────────────────────────
# 공공데이터포털 파일은 CP949 다. 업태에 '닭갈비'·'막국수' 분류가 없어 **가게 이름**으로
# 가른다. 이름에 둘 다 들어간 가게(○○닭갈비막국수)는 양쪽에 다 센다.
# 동네는 지번 주소의 세 번째 낱말(법정동·읍·면)이다.
R = load_csv("chuncheon_restaurants.csv", encoding="cp949")
r_date = R[0]["데이터기준일자"]
DAK = [x for x in R if "닭갈비" in x["업소명"]]
MAK = [x for x in R if "막국수" in x["업소명"]]
both = sum(1 for x in DAK if "막국수" in x["업소명"])
dm_ratio = len(DAK) / len(MAK)


def dong(x):
    return x["소재지(지번)"].split()[2]


dak_dong = Counter(dong(x) for x in DAK)
top_dong = dak_dong.most_common(1)[0]
coffee = sum(1 for x in R if x["업태명"] == "커피숍")
# 모범음식점의 '주된 음식으로 닭갈비 vs 막국수' 문항은 뺐다. 97곳 중 몇 곳 차이라
# 해마다 지정·취소 한두 곳으로 정답이 뒤집힐 수 있었다. 대신 닭갈비집 전체에서 센다
sutbul = sum(1 for x in DAK if "숯불" in x["업소명"])
cheolpan = sum(1 for x in DAK if "철판" in x["업소명"])
assert sutbul != cheolpan, "'숯불'·'철판' 수가 같아 정답을 정할 수 없습니다"
assert len(DAK) != coffee, "닭갈비집과 커피숍 수가 같아 정답을 정할 수 없습니다"
# 한 줄은 가게가 아니라 신고 한 건이다. 층이나 업종(음식점·제과점)을 따로 신고하면 여러 줄
r_multi = sum(1 for v in Counter((x["업소명"].strip(), x["소재지(지번)"].strip())
                                 for x in R).values() if v > 1)

topic(
    "chuncheon-food", "🍗", "춘천은 닭갈비의 도시인가",
    f"춘천시 음식점 {len(R):,}곳의 이름으로 본 먹거리 지도",
    "춘천시 요식업소 현황 (공공데이터포털)",
    "https://www.data.go.kr/data/15003349/fileData.do",
    [
        slider("f1", "춘천에서 이름에 '닭갈비'가 들어간 음식점은 몇 곳일까요?",
               len(DAK), "곳", 0, 600, 10,
               f"{r_date} 기준 춘천시 요식업소 {len(R):,}곳 중 업소명에 '닭갈비'가 "
               f"들어간 곳 {len(DAK)}곳",
               f"전체 음식점의 {len(DAK) / len(R) * 100:.1f}%입니다. 도시의 얼굴이 되는 "
               "음식도 가게 수로는 일부입니다."),
        # 보기는 배수에 가장 가까운 것이 정답이 되게 경계를 둔다 (서울 h2 와 같은 경계)
        choice("f2", "이름에 '닭갈비'가 들어간 가게는 '막국수'가 들어간 가게의 몇 배일까요?",
               ["거의 같다", "약 2배", "약 3배", "약 5배"],
               ["거의 같다", "약 2배", "약 3배", "약 5배"][
                   0 if dm_ratio < 1.5 else 1 if dm_ratio < 2.5
                   else 2 if dm_ratio < 4 else 3],
               f"{r_date} 기준 업소명에 '닭갈비' {len(DAK)}곳 · '막국수' {len(MAK)}곳 "
               f"({dm_ratio:.1f}배). 둘 다 들어간 {both}곳은 양쪽에 다 셌습니다",
               f"{both}곳은 이름에 닭갈비와 막국수를 함께 걸었습니다. 춘천에서 둘은 "
               "경쟁자라기보다 한 상에 오르는 짝입니다."),
        choice("f3", "춘천에서 이름에 '닭갈비'가 들어간 가게가 가장 많은 동네는?",
               ["조양동", "남산면", "퇴계동", "석사동"], top_dong[0],
               f"{r_date} 기준 업소명에 '닭갈비'가 들어간 가게를 지번 주소의 동·읍·면으로 "
               "세면 " + " · ".join(f"{d} {dak_dong[d]}곳"
                                   for d in ("조양동", "남산면", "퇴계동", "석사동")),
               "'닭갈비 골목'으로 이름난 곳(명동이 있는 조양동)과 닭갈비집이 가장 많은 "
               "곳은 같지 않을 수 있습니다. 골목은 관광의 얼굴이고, 가게 수는 "
               "사람이 사는 동네를 따라갑니다."),
        choice("f4", "춘천에 닭갈비집과 커피숍 중 어느 쪽이 더 많을까요?",
               ["닭갈비집", "커피숍"], "닭갈비집" if len(DAK) > coffee else "커피숍",
               f"{r_date} 기준 업소명에 '닭갈비'가 들어간 곳 {len(DAK)}곳 · 업태가 "
               f"'커피숍'인 곳 {coffee}곳",
               "도시를 대표하는 음식과 사람들이 매일 들르는 가게는 다릅니다."),
        # 실제 조리 방식이 아니라 '이름에 내건 말'을 묻는다. 이름에 둘 다 없는 가게가 대부분이다
        choice("f5", "춘천 닭갈비집 이름에 더 많이 들어간 말은?",
               ["숯불", "철판"], "숯불" if sutbul > cheolpan else "철판",
               f"{r_date} 기준 업소명에 '닭갈비'가 들어간 {len(DAK)}곳 중 '숯불'이 들어간 곳 "
               f"{sutbul}곳 · '철판'이 들어간 곳 {cheolpan}곳 "
               f"(둘 다 없는 곳 {len(DAK) - sutbul - cheolpan}곳)",
               "이름은 조리 방식의 통계가 아니라 간판의 선택입니다. 흔한 방식은 굳이 "
               "내걸지 않고, 남과 다른 점을 이름에 씁니다."),
    ],
    caveat=f"이 숫자는 {r_date} 기준 춘천시 신고 목록에서 이름에 '닭갈비'·'막국수'가 "
           "들어간 줄을 센 것이라, 이름에 그 말이 없는 닭갈비집은 빠지고, 한 가게가 "
           f"층이나 업종별로 따로 신고한 경우(같은 이름·지번 {r_multi}건)는 여러 번 "
           "세어지며, 목록에 휴·폐업 여부가 없고 동네는 지번 주소의 법정동으로 나눴기 "
           "때문에 지도 앱이나 행정동 기준 집계의 가게 수와 다를 수 있습니다.")


# ── 14. 사람보다 많은 동물들 ─────────────────────────────────────
# FAO 는 ZIP 을 풀지 않고 안의 CSV 를 읽는다. 'Stocks'(그해 기르고 있는 마릿수) 줄만 쓴다.
# 같은 표에 '소와 물소' '양과 염소' '가금류' 같은 **합계 항목**이 개별 동물과 나란히 있어
# 그대로 세면 두 번 세어진다. 벌(Bees)은 마리가 아니라 벌통 수라 뺀다.
# 닭은 1,000마리 단위로 적혀 있어 Unit 을 보고 곱한다.
LIVESTOCK = {"Sheep": "양", "Goats": "염소", "Cattle": "소", "Horses": "말",
             "Camels": "낙타", "Swine / pigs": "돼지", "Chickens": "닭", "Asses": "당나귀"}
FAO_ISO = {"New Zealand": "NZL", "Mongolia": "MNG", "Republic of Korea": "KOR",
           "World": "WLD"}
FAO = {}                                    # (나라, 연도, 동물) → (마릿수, 표시)
# 작물 생산량(톤)도 같은 파일에서 한 번에 읽는다 — 품목코드 → 연도 → 줄 목록.
# 바나나 486 · 키위 592 · 커피 생두 656 · 카카오콩 661 · 사과 515 · 감 587 ·
# 배추(양배추 포함) 358 · 딸기 544 · 쌀(벼) 27 · 달걀 1062
PROD_ITEMS = {"486", "592", "656", "661", "515", "587", "358", "544", "27", "1062"}
PROD = collections.defaultdict(lambda: collections.defaultdict(list))
with zipfile.ZipFile(RAW / "fao_qcl.zip") as _z, \
        _z.open("Production_Crops_Livestock_E_All_Data_(Normalized).csv") as _f:
    for x in csv.DictReader(io.TextIOWrapper(_f, encoding="utf-8")):
        if (x["Element"] == "Production" and x["Item Code"] in PROD_ITEMS
                and x["Unit"] == "t" and x["Value"]):
            PROD[x["Item Code"]][int(x["Year"])].append(
                {"code": int(x["Area Code"]), "area": x["Area"],
                 "value": float(x["Value"]), "flag": x["Flag"]})
        if (x["Element"] == "Stocks" and x["Area"] in FAO_ISO
                and x["Item"] in LIVESTOCK and x["Year"] in ("1961", "2024")
                and x["Value"]):
            scale = 1000 if x["Unit"].startswith("1000") else 1
            FAO[(x["Area"], int(x["Year"]), x["Item"])] = (float(x["Value"]) * scale,
                                                         x["Flag"])
POP = {(r["countryiso3code"], int(r["date"])): r["value"]
       for r in load_json("wb_pop_all.json")[1] if r["value"]}


def per_person(area, item, year=2024):
    return FAO[(area, year, item)][0] / POP[(FAO_ISO[area], year)]


nz_sheep = per_person("New Zealand", "Sheep")
mn_pop = POP[("MNG", 2024)]
mn_more = [LIVESTOCK[i] for i in LIVESTOCK
           if ("Mongolia", 2024, i) in FAO and FAO[("Mongolia", 2024, i)][0] > mn_pop]
mn_horse = per_person("Mongolia", "Horses")
kr_chicken = per_person("Republic of Korea", "Chickens")
w_chicken = per_person("World", "Chickens")
w_flag = FAO[("World", 2024, "Chickens")][1]
kr_pig_61 = FAO[("Republic of Korea", 1961, "Swine / pigs")][0]
kr_pig_24 = FAO[("Republic of Korea", 2024, "Swine / pigs")][0]
kr_pig_x = kr_pig_24 / kr_pig_61
kr_pop_x = POP[("KOR", 2024)] / POP[("KOR", 1961)]
assert 0 <= nz_sheep <= 20 and 0 <= kr_chicken <= 10 and 0 <= kr_pig_x <= 20, \
    "정답이 슬라이더 범위 밖입니다"
mn_band = "4종 이상" if len(mn_more) >= 4 else f"{len(mn_more)}종"

topic(
    "animals", "🐑", "사람보다 많은 동물들",
    "나라별 가축 마릿수와 인구, 1961년과 2024년",
    "FAO FAOSTAT · World Bank", "https://www.fao.org/faostat/",
    [
        slider("v1", "2024년 뉴질랜드에는 사람 1명당 양이 몇 마리일까요?",
               nz_sheep, "마리", 0, 20, 0.5,
               f"2024년 FAO 뉴질랜드 양 {FAO[('New Zealand', 2024, 'Sheep')][0]:,.0f}마리 ÷ "
               f"세계은행 뉴질랜드 인구 {POP[('NZL', 2024)]:,.0f}명 = {nz_sheep:.1f}마리",
               "'양이 사람보다 훨씬 많은 나라'라는 말이 너무 유명해서 수십 배쯤으로 "
               "부풀려 기억하기 쉽습니다."),
        choice("v2", "2024년 몽골에서 사람보다 많은 가축은 몇 종일까요?",
               ["1종", "2종", "3종", "4종 이상"], mn_band,
               f"2024년 양·염소·소·말·낙타·돼지·닭·당나귀 중 FAO 마릿수가 몽골 인구 "
               f"{mn_pop:,.0f}명보다 많은 종: {', '.join(mn_more)}",
               f"몽골에서는 말도 사람 1명당 {mn_horse:.1f}마리입니다. 초원의 나라에서는 "
               "사람이 소수입니다."),
        slider("v3", "2024년 한국에는 사람 1명당 닭이 몇 마리일까요?",
               kr_chicken, "마리", 0, 10, 0.1,
               f"2024년 FAO 한국 닭 {FAO[('Republic of Korea', 2024, 'Chickens')][0]:,.0f}마리 ÷ "
               f"세계은행 한국 인구 {POP[('KOR', 2024)]:,.0f}명 = {kr_chicken:.1f}마리",
               "닭은 눈에 보이지 않는 곳에서 길러집니다. 보이지 않는 것은 적게 "
               "어림하게 됩니다."),
        # 보기는 배수에 가장 가까운 것이 정답이 되게 경계를 둔다 (서울 h2 와 같은 경계)
        choice("v4", "2024년 지구의 닭은 사람의 몇 배일까요?",
               ["거의 같다", "약 2배", "약 3배", "약 5배"],
               ["거의 같다", "약 2배", "약 3배", "약 5배"][
                   0 if w_chicken < 1.5 else 1 if w_chicken < 2.5
                   else 2 if w_chicken < 4 else 3],
               f"2024년 FAO 세계 닭 {FAO[('World', 2024, 'Chickens')][0]:,.0f}마리 ÷ "
               f"세계은행 세계 인구 {POP[('WLD', 2024)]:,.0f}명 = {w_chicken:.1f}배",
               f"지금 지구에서는 사람 1명마다 닭 {w_chicken:.1f}마리가 길러지고 있는 "
               "셈입니다."),
        slider("v5", "1961년과 비교해 2024년 한국의 돼지는 몇 배로 늘었을까요?",
               kr_pig_x, "배", 0, 20, 0.5,
               f"FAO 한국 돼지 1961년 {kr_pig_61:,.0f}마리 → 2024년 {kr_pig_24:,.0f}마리 "
               f"({kr_pig_x:.1f}배)",
               f"같은 기간 한국 인구는 {kr_pop_x:.1f}배 늘었습니다. 돼지는 사람보다 "
               f"{kr_pig_x / kr_pop_x:.1f}배 빠르게 늘었습니다."),
    ],
    caveat="마릿수는 한 해 중 한 시점에 기르고 있는 수라 1년 동안 도축되는 수(닭은 "
           "훨씬 큼)와 다르고, 나라별 값은 각국이 FAO에 보고한 값이지만 세계 합계는 "
           f"FAO 추정값(표시 '{w_flag}')이며, 인구는 세계은행 값이라 다른 통계의 "
           "'사람 1명당' 수와 다를 수 있습니다.")


# ── 15. 설마 1위가 거기? ─────────────────────────────────────────
# 순위는 나라만 센다. 지역코드 5000 이상(세계·대륙·'Australia and New Zealand' 같은
# 묶음)은 빼고, 'China'(코드 351)는 본토·대만·홍콩·마카오를 합친 줄이라 빼서 중국이
# 두 번 세어지지 않게 한다 — 중국은 'China, mainland'(본토)로 센다.
P_YEAR = 2024
WORLD_CODE = 5000
KO = {"India": "인도", "Philippines": "필리핀", "Ecuador": "에콰도르", "Brazil": "브라질",
      "New Zealand": "뉴질랜드", "China, mainland": "중국", "Italy": "이탈리아",
      "Chile": "칠레", "Colombia": "콜롬비아", "Ethiopia": "에티오피아", "Viet Nam": "베트남",
      "Indonesia": "인도네시아", "Ghana": "가나", "Côte d'Ivoire": "코트디부아르",
      "Nigeria": "나이지리아", "United States of America": "미국", "Türkiye": "튀르키예",
      "Republic of Korea": "한국", "Japan": "일본", "Poland": "폴란드",
      "Russian Federation": "러시아", "Ukraine": "우크라이나", "Azerbaijan": "아제르바이잔",
      "United Kingdom of Great Britain and Northern Ireland": "영국",
      "Iran (Islamic Republic of)": "이란", "Madagascar": "마다가스카르",
      "Sri Lanka": "스리랑카", "Germany": "독일", "Spain": "스페인", "Egypt": "이집트",
      "Mexico": "멕시코"}


def ranking(item, year=P_YEAR):
    return sorted((r for r in PROD[item][year] if r["code"] < 5000 and r["code"] != 351),
                  key=lambda r: -r["value"])


def ko(r):
    return KO.get(r["area"], r["area"])


def flagged(r):
    """공식값이 아니면 표시를 붙인다 — E 추정, I 대체, X 외부기관."""
    return "" if r["flag"] == "A" else f"(FAO 표시 {r['flag']})"


ban, kiwi, cof, coc, app = (ranking(i) for i in ("486", "592", "656", "661", "515"))
app_world = next(r for r in PROD["515"][P_YEAR] if r["code"] == WORLD_CODE)
app_share = app[0]["value"] / app_world["value"] * 100
app2_share = app[1]["value"] / app_world["value"] * 100


def top2(rs):
    return (f"1위 {ko(rs[0])} {rs[0]['value']:,.0f}톤{flagged(rs[0])} · "
            f"2위 {ko(rs[1])} {rs[1]['value']:,.0f}톤{flagged(rs[1])}")


topic(
    "first-place", "🥇", "설마 1위가 거기?",
    f"{P_YEAR}년 세계 작물 생산량, 1위는 어디일까",
    "FAO FAOSTAT", "https://www.fao.org/faostat/",
    [
        choice("g1", f"{P_YEAR}년 세계에서 바나나를 가장 많이 생산한 나라는?",
               ["필리핀", "에콰도르", "인도", "브라질"], ko(ban[0]),
               f"{P_YEAR}년 FAO 바나나 생산량(플랜테인 제외) {top2(ban)}",
               f"1위는 2위의 {ban[0]['value'] / ban[1]['value']:.1f}배입니다. 바나나 수출로 "
               "이름난 나라와 가장 많이 기르는 나라는 다릅니다."),
        choice("g2", f"{P_YEAR}년 키위 생산 세계 1위 나라는?",
               ["뉴질랜드", "중국", "이탈리아", "칠레"], ko(kiwi[0]),
               f"{P_YEAR}년 FAO 키위 생산량 {top2(kiwi)}",
               f"1위는 2위의 {kiwi[0]['value'] / kiwi[1]['value']:.1f}배입니다. 과일 이름이 "
               "붙은 나라가 가장 많이 기르는 나라는 아닙니다."),
        choice("g3", f"{P_YEAR}년 세계 커피(생두) 생산 2위 나라는?",
               ["콜롬비아", "에티오피아", "베트남", "인도네시아"], ko(cof[1]),
               f"{P_YEAR}년 FAO 커피 생두 생산량 {top2(cof)} · "
               f"3위 {ko(cof[2])} {cof[2]['value']:,.0f}톤{flagged(cof[2])}",
               f"2위는 3위의 {cof[1]['value'] / cof[2]['value']:.1f}배입니다. 커피 광고에 "
               "자주 나오는 나라와 실제 생산량 순서는 다릅니다."),
        choice("g4", f"{P_YEAR}년 초콜릿 원료 카카오콩 생산 1위 나라는?",
               ["가나", "코트디부아르", "인도네시아", "나이지리아"], ko(coc[0]),
               f"{P_YEAR}년 FAO 카카오콩 생산량 {top2(coc)}",
               f"1위는 2위의 {coc[0]['value'] / coc[1]['value']:.1f}배입니다. 초콜릿 상표에 "
               "이름이 붙은 나라와 원료를 가장 많이 기르는 나라는 다릅니다."),
        slider("g5", f"{P_YEAR}년 세계 사과의 몇 %를 1위 나라 한 곳이 생산했을까요?",
               app_share, "%", 0, 100, 1,
               f"{P_YEAR}년 FAO 사과 생산량 1위 {ko(app[0])} {app[0]['value']:,.0f}톤 ÷ "
               f"세계 {app_world['value']:,.0f}톤{flagged(app_world)} = {app_share:.1f}%",
               f"2위 {ko(app[1])}의 몫은 {app2_share:.1f}%입니다. 한 나라가 세계 사과의 "
               "큰 몫을 혼자 기릅니다."),
    ],
    caveat=f"이 순위는 {P_YEAR}년 FAO 생산량(수출량 아님)으로 매겨 중국은 대만·홍콩을 뺀 "
           "본토만, 바나나는 플랜테인을 뺀 값만 셌고, 키위 1·2위("
           f"{ko(kiwi[0])} 표시 {kiwi[0]['flag']} · {ko(kiwi[1])} 표시 {kiwi[1]['flag']})처럼 "
           "FAO가 추정·대체한 값에 기댄 답이 있어 각국 통계청 발표나 '수출 1위' 기사의 "
           "숫자와 다를 수 있습니다.")


# ── 16. 설마 한국이? ─────────────────────────────────────────────
# 한국의 정확한 순위는 해마다 바뀐다(감 2022·2024년 2위, 2023년 3위 — 앞뒤 나라와 1% 차이).
# 그래서 '몇 위?'를 정확히 묻지 않고, 2022~2024년 세 해 모두 같은 보기에 들어가는 순위
# 구간으로 묻는다. 보기의 경계는 그 확인을 거쳐 정했다. 순위를 매기는 규칙은 15번과 같다.
def kor_rank(item, year=P_YEAR):
    rs = ranking(item, year)
    i = next(i for i, r in enumerate(rs) if r["area"] == "Republic of Korea")
    return i + 1, rs, i


def band(rank, bands):
    """bands = [(보기, 가장 높은 순위, 가장 낮은 순위)] → 순위가 들어가는 보기."""
    return next(label for label, lo, hi in bands if lo <= rank <= hi)


def kor_line(name, item):
    rank, rs, i = kor_rank(item)
    me = rs[i]
    return (f"{P_YEAR}년 FAO {name} 생산량을 나라별로 줄 세우면 {len(rs)}개국 중 한국 "
            f"{rank}위 {me['value']:,.0f}톤{flagged(me)} · 1위 {ko(rs[0])} "
            f"{rs[0]['value']:,.0f}톤{flagged(rs[0])}")


B_TOP = [("1위", 1, 1), ("2~3위", 2, 3), ("4~10위", 4, 10), ("11위 이하", 11, 999)]
B_MID = [("1~5위", 1, 5), ("6~15위", 6, 15), ("16~30위", 16, 30), ("31위 이하", 31, 999)]
k_pers, k_cab, k_straw, k_egg = (kor_rank(i) for i in ("587", "358", "544", "1062"))
rice = {r["area"]: r for r in PROD["27"][2006]}["Republic of Korea"], \
       {r["area"]: r for r in PROD["27"][P_YEAR]}["Republic of Korea"]
rice_drop = (1 - rice[1]["value"] / rice[0]["value"]) * 100
kor_pop_up = (POP[("KOR", P_YEAR)] / POP[("KOR", 2006)] - 1) * 100
assert 0 <= rice_drop <= 60, "쌀 감소율이 슬라이더 범위 밖입니다"

topic(
    "korea-rank", "🇰🇷", "설마 한국이?",
    f"{P_YEAR}년 세계 생산 순위 속 한국의 먹거리",
    "FAO FAOSTAT", "https://www.fao.org/faostat/",
    [
        choice("k1", f"{P_YEAR}년 한국의 감 생산량은 세계 몇 위일까요?",
               [b[0] for b in B_TOP], band(k_pers[0], B_TOP),
               kor_line("감", "587"),
               f"1위 {ko(k_pers[1][0])}의 생산량은 한국의 "
               f"{k_pers[1][0]['value'] / k_pers[1][k_pers[2]]['value']:.0f}배라, 2위부터는 "
               "한참 아래에서 비슷한 나라끼리 다툽니다. 한국은 그 다툼의 맨 앞줄입니다."),
        choice("k2", f"{P_YEAR}년 한국의 배추(양배추 포함) 생산량은 세계 몇 위일까요?",
               [b[0] for b in B_MID], band(k_cab[0], B_MID),
               kor_line("배추(양배추 포함)", "358"),
               f"{len(k_cab[1])}개 나라 가운데 상위권입니다. FAO는 배추와 양배추를 한 "
               "품목으로 셉니다."),
        choice("k3", f"{P_YEAR}년 한국의 딸기 생산량은 세계 몇 위일까요?",
               [b[0] for b in B_MID], band(k_straw[0], B_MID),
               kor_line("딸기", "544"),
               f"바로 위는 {ko(k_straw[1][k_straw[2] - 1])}, 바로 아래는 "
               f"{ko(k_straw[1][k_straw[2] + 1])}입니다."),
        choice("k4", f"{P_YEAR}년 한국의 달걀 생산량(무게)은 세계 몇 위일까요?",
               [b[0] for b in B_MID], band(k_egg[0], B_MID),
               kor_line("달걀(무게)", "1062"),
               f"1위 {ko(k_egg[1][0])}의 생산량은 한국의 "
               f"{k_egg[1][0]['value'] / k_egg[1][k_egg[2]]['value']:.0f}배입니다. 매일 먹는 "
               "음식이라고 순위가 높은 것은 아닙니다."),
        slider("k5", f"2006년과 비교해 {P_YEAR}년 한국의 쌀(벼) 생산량은 몇 % 줄었을까요?",
               rice_drop, "%", 0, 60, 1,
               f"FAO 한국 쌀(벼) 생산량 2006년 {rice[0]['value']:,.0f}톤"
               f"{flagged(rice[0])} → {P_YEAR}년 {rice[1]['value']:,.0f}톤"
               f"{flagged(rice[1])} ({rice_drop:.1f}% 감소)",
               f"같은 기간 한국 인구는 {kor_pop_up:.1f}% 늘었습니다(세계은행)."),
    ],
    caveat=f"이 순위는 {P_YEAR}년 FAO 값으로 매겨 한국의 "
           + "·".join(n for n, k in (("감", k_pers), ("배추", k_cab), ("딸기", k_straw),
                                    ("달걀", k_egg)) if k[1][k[2]]["flag"] != "A")
           + " 값이 한국 공식 보고가 아닌 FAO 대체·추정값이고, 배추는 양배추와 합친 "
           f"값이며, 앞뒤 나라와 차이가 작아 감은 2023년에 {kor_rank('587', 2023)[0]}위였을 "
           "만큼 해마다 순위가 바뀌므로 통계청 발표나 다른 해 기준 순위와 다를 수 "
           "있습니다.")


# ── 17. 커피공화국 한국 ──────────────────────────────────────────
# 수입량은 FAO 무역 통계(풀면 2.4GB). 커피 수입 줄만 필요해서, 'Coffee' 와 'Import quantity'
# 가 없는 줄은 csv 로 풀기 전에 건너뛴다. 커피는 **생두만** 세고 볶은 커피는 따로 묻는다
# (추출물은 원두를 졸인 것이라 무게를 생두와 더할 수 없다). 다시 수출하는 양은 빼지 않는다.
# 순위 규칙은 15번과 같고, 무역 파일에는 중국 합계 줄이 둘('China' 351,
# 'China (excluding intra-trade)' 265)이라 둘 다 뺀다.
CAFE = ("Coffee, green", "Coffee, decaffeinated or roasted")
IMP = collections.defaultdict(list)          # (품목, 연도) → 나라별 수입량 줄
with zipfile.ZipFile(RAW / "fao_tcl.zip") as _z, \
        _z.open("Trade_CropsLivestock_E_All_Data_(Normalized).csv") as _f:
    _t = io.TextIOWrapper(_f, encoding="utf-8")
    _h = {h: i for i, h in enumerate(next(csv.reader([_t.readline()])))}
    for _line in _t:
        if "Coffee" not in _line or "Import quantity" not in _line:
            continue
        x = next(csv.reader([_line]))
        if x[_h["Item"]] in CAFE and x[_h["Element"]] == "Import quantity" and x[_h["Value"]]:
            IMP[(x[_h["Item"]], int(x[_h["Year"]]))].append(
                {"code": int(x[_h["Area Code"]]), "area": x[_h["Area"]],
                 "value": float(x[_h["Value"]]), "flag": x[_h["Flag"]]})


def imp_kor(item, year):
    return next(r for r in IMP[(item, year)] if r["area"] == "Republic of Korea")


g06, g24 = imp_kor(CAFE[0], 2006), imp_kor(CAFE[0], P_YEAR)
r06, r24 = imp_kor(CAFE[1], 2006), imp_kor(CAFE[1], P_YEAR)
green_x = g24["value"] / g06["value"]
roast_x = r24["value"] / r06["value"]
kg_pp = g24["value"] * 1000 / POP[("KOR", P_YEAR)]
def imp_ranking(year):
    return sorted((r for r in IMP[(CAFE[0], year)]
                   if r["code"] < 5000 and r["code"] not in (351, 265)),
                  key=lambda r: -r["value"])


def imp_rank_of(year):
    return next(i for i, r in enumerate(imp_ranking(year))
                if r["area"] == "Republic of Korea") + 1


imp_rank = imp_ranking(P_YEAR)
k_imp = imp_rank_of(P_YEAR) - 1
cof_world = next(r for r in PROD["656"][P_YEAR] if r["code"] == WORLD_CODE)
bra = next(r for r in cof if r["area"] == "Brazil")
bra_share = bra["value"] / cof_world["value"] * 100
assert 0 <= green_x <= 10 and 0 <= kg_pp <= 10 and 0 <= roast_x <= 30, \
    "정답이 슬라이더 범위 밖입니다"

topic(
    "coffee-korea", "☕", "커피공화국 한국",
    f"한국이 들여온 커피, 2006년과 {P_YEAR}년",
    "FAO FAOSTAT · World Bank", "https://www.fao.org/faostat/",
    [
        slider("c1", f"{P_YEAR}년 한국의 커피 생두 수입량은 2006년의 몇 배일까요?",
               green_x, "배", 0, 10, 0.1,
               f"FAO 한국 커피 생두 수입량 2006년 {g06['value']:,.0f}톤{flagged(g06)} → "
               f"{P_YEAR}년 {g24['value']:,.0f}톤{flagged(g24)} ({green_x:.1f}배)",
               f"같은 기간 한국 인구는 {kor_pop_up:.1f}% 늘었습니다. 사람보다 커피가 훨씬 "
               "빨리 늘었습니다."),
        slider("c2", f"{P_YEAR}년 한국은 사람 1명당 커피 생두를 몇 kg 수입했을까요?",
               kg_pp, "kg", 0, 10, 0.1,
               f"{P_YEAR}년 FAO 한국 커피 생두 수입량 {g24['value']:,.0f}톤 ÷ 세계은행 한국 "
               f"인구 {POP[('KOR', P_YEAR)]:,.0f}명 = {kg_pp:.2f}kg (다시 수출한 양은 빼지 않음)",
               "한 잔에 쓰는 원두는 몇 그램뿐이라, 1년 치를 kg으로 물으면 감이 잘 오지 "
               "않습니다."),
        slider("c3", f"{P_YEAR}년 한국의 볶은 커피 수입량은 2006년의 몇 배일까요?",
               roast_x, "배", 0, 30, 0.5,
               f"FAO 한국 볶은 커피(디카페인 포함) 수입량 2006년 {r06['value']:,.0f}톤"
               f"{flagged(r06)} → {P_YEAR}년 {r24['value']:,.0f}톤{flagged(r24)} "
               f"({roast_x:.1f}배)",
               f"같은 기간 생두 수입은 {green_x:.1f}배였습니다. 한국에서 볶던 커피를, 볶아진 "
               "채로 들여오는 몫이 훨씬 빨리 늘었습니다."),
        choice("c4", f"{P_YEAR}년 한국의 커피 생두 수입량은 세계 몇 위일까요?",
               [b[0] for b in B_MID], band(k_imp + 1, B_MID),
               f"{P_YEAR}년 FAO 커피 생두 수입량을 나라별로 줄 세우면 {len(imp_rank)}개국 중 "
               f"한국 {k_imp + 1}위 {g24['value']:,.0f}톤 · 1위 {ko(imp_rank[0])} "
               f"{imp_rank[0]['value']:,.0f}톤{flagged(imp_rank[0])}",
               f"1위 {ko(imp_rank[0])}의 수입량은 한국의 "
               f"{imp_rank[0]['value'] / g24['value']:.1f}배입니다. '커피공화국'이라는 별명과 "
               "세계 순위 사이에는 거리가 있습니다."),
        slider("c5", f"{P_YEAR}년 세계 커피 생두의 몇 %를 브라질 한 나라가 생산했을까요?",
               bra_share, "%", 0, 100, 1,
               f"{P_YEAR}년 FAO 커피 생두 생산량 브라질 {bra['value']:,.0f}톤{flagged(bra)} ÷ "
               f"세계 {cof_world['value']:,.0f}톤{flagged(cof_world)} = {bra_share:.1f}%",
               f"2위 {ko(cof[1])}까지 더하면 두 나라가 세계 생두의 "
               f"{(cof[0]['value'] + cof[1]['value']) / cof_world['value'] * 100:.0f}%를 "
               "차지합니다."),
    ],
    caveat=f"이 숫자는 FAO 수입량(마신 양 아님) 중 생두만 센 것으로 볶은 커피·추출물"
           "(인스턴트)을 더하지 않았고 다시 수출한 양도 빼지 않았으며, 수입 순위는 중국 "
           "합계 줄 두 개(코드 351·265)를 빼고 매겨 한국이 2022년 "
           f"{imp_rank_of(2022)}위 · {P_YEAR}년 {k_imp + 1}위로 해마다 바뀌므로 관세청·"
           "커피협회 발표나 '1인당 소비' 순위와 다를 수 있습니다.")


# ════════════════════════════════════════════════════════════════
# 첫 화면 목록에 보일 주제와 그 순서. 여기 없는 주제도 문항 파일은 그대로 만들지만
# 목록(topics.json)에는 넣지 않아 화면에 나오지 않는다. 다시 보이게 하려면 id 를 더한다
SHOWN = ["first-place", "korea-rank", "coffee-korea", "animals", "chuncheon-food",
         "busan-heat"]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    index = []
    for t in TOPICS:
        assert len(t["questions"]) == 5, f"{t['id']}: 문항이 5개가 아닙니다"
        pack = {k: t[k] for k in ("id", "emoji", "title", "blurb",
                                  "source", "source_url", "caveat")}
        pack["questions"] = t["questions"]
        io.open(OUT / f"{t['id']}.json", "w", encoding="utf-8").write(
            json.dumps(pack, ensure_ascii=False, indent=2))
        index.append({k: t[k] for k in ("id", "emoji", "title", "blurb",
                                        "source")})
    index = sorted((t for t in index if t["id"] in SHOWN),
                   key=lambda t: SHOWN.index(t["id"]))

    # 제목·부제는 화면을 바꾸며 고친 값을 지킨다 (2장에서 내 제목으로 바꾼다).
    # 다시 계산해도 내 제목이 기본값으로 돌아가지 않게, 있던 값을 읽어 쓴다
    old = {}
    if (APP / "topics.json").exists():
        try:
            old = json.load(io.open(APP / "topics.json", encoding="utf-8"))
        except ValueError:
            old = {}
    io.open(APP / "topics.json", "w", encoding="utf-8").write(json.dumps({
        "title": old.get("title", "설마 퀴즈"),
        "subtitle": old.get("subtitle", "설마 그 정도일까? 찍어 보면 데이터가 답합니다"),
        # 등급·문구는 여기서 고칩니다. 코드를 건드릴 일이 아닙니다
        "grades": [
            {"min": 90, "name": "촉이 데이터급", "emoji": "🎯"},
            {"min": 70, "name": "감이 좋은 편", "emoji": "📊"},
            {"min": 50, "name": "보통의 감각", "emoji": "🙂"},
            {"min": 30, "name": "느낌대로 삽니다", "emoji": "🎲"},
            {"min": 0, "name": "감은 접어두시죠", "emoji": "🙈"},
        ],
        "reactions_choice": {"hit": "맞히셨습니다", "miss": "다들 그렇게 찍습니다"},
        "reactions": [
            {"max": 5, "text": "촉이 좋으시네요"},
            {"max": 20, "text": "비슷하게 보셨습니다"},
            {"max": 60, "text": "음…"},
            {"max": 999, "text": "꽤 멀리 가셨습니다"},
        ],
        "topics": index,
    }, ensure_ascii=False, indent=2))

    # 사람이 읽는 정답지
    md = [f"# 문항 정답지 — {len(TOPICS)}주제 "
          f"{sum(len(t['questions']) for t in TOPICS)}문항", "",
          "> 모든 값은 `data/raw/` 의 원본에서 `tools/build_topics.py` 가 계산합니다.", ""]
    for t in TOPICS:
        md += [f"## {t['emoji']} {t['title']}", "",
               f"- 출처: {t['source']} · {t['source_url']}"]
        if t["caveat"]:
            md += [f"- **한계** {t['caveat']}"]
        md += [""]
        for q in t["questions"]:
            a = f"{q['answer']}{q.get('unit', '')}" if q["type"] == "slider" \
                else q["answer"]
            md += [f"**{q['text']}**", "",
                   f"- 정답 **{a}**", f"- 근거 {q['basis']}",
                   f"- 왜 틀리나 {q['why']}", ""]
    io.open(HERE / "정답지.md", "w", encoding="utf-8").write("\n".join(md))

    print(f"주제 {len(TOPICS)}개 · 문항 {sum(len(t['questions']) for t in TOPICS)}개")
    for t in TOPICS:
        print(f"\n{t['emoji']} {t['title']}  ({t['source']})")
        for q in t["questions"]:
            a = f"{q['answer']}{q.get('unit', '')}" if q["type"] == "slider" \
                else q["answer"]
            print(f"    [{q['type'][:6]:<6}] {q['text'][:44]:<44} → {a}")


if __name__ == "__main__":
    main()
