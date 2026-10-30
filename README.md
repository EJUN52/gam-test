# 감 테스트

숫자에 대한 당신의 감은 몇 점입니까

주소: https://github.com/EJUN52/gam-test

## 내가 내린 판단

다들 "한 시간은 걸린다"고 하는데, 실제 평균은 다를 것 같다

## 주제 10개

| | 주제 | 출처 |
|---|---|---|
| 🌡️ | 서울은 얼마나 더워졌나 | Open-Meteo Archive (ERA5) |
| ☔ | 비는 언제, 얼마나 | Open-Meteo Archive (ERA5) |
| 😷 | 미세먼지, 언제 나쁜가 | Open-Meteo Air Quality (CAMS) |
| ⏰ | 우리는 얼마나 일하나 | Our World in Data |
| 👶 | 인구와 출산 | World Bank |
| 🌐 | 인터넷과 연결 | World Bank |
| 💵 | 원달러 환율 26년 | Frankfurter (ECB) |
| 🏙️ | 서울·도쿄·런던·싱가포르 | Open-Meteo Archive (ERA5) |
| 🌎 | 지진은 얼마나 자주 | USGS |
| 🩺 | 얼마나 오래 사나 | Our World in Data |

## 돌려보기

```
python -m http.server 8000      # index.html 을 더블클릭하면 안 됩니다
```

## 데이터가 오는 길

```
   [내 노트북]                                   [인터넷]

   tools/fetch_all.py      공개 데이터 6곳에서 받기 (키·로그인 없음)
        ↓  data/raw/  약 19MB   ← git 에도 배포에도 올라가지 않습니다
   tools/build_topics.py   원본에서 문항 계산
        ↓
   topics/*.json  약 40KB  ← 이것만 올라갑니다
```

원본을 브라우저로 보내서 거기서 평균을 내는 게 아닙니다. **평균은 내 노트북에서 미리
내고, 그 결과만 싣습니다.** 그래서 폰에서 즉시 뜹니다.
