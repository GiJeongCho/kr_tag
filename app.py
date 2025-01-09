import streamlit as st
import requests
import random

# 페이지 설정
st.set_page_config(
    page_title="POS 태깅 API 테스트",
    layout="centered",
)

# 예시 문장 리스트 정의
example_sentences = [
"산이 높다.",
"나무가 푸르다.",
"오늘은 금요일이다.",
"나는 학생이다.",
"인생은 짧고 예술은 길다.",
"사과는 먹어도 배는 먹지 마라.",
"너에게도 잘못은 있다.",
"아무리 바쁘더라도 식사는 해야지.",
"어제 내 팔을 잡은 사람이 바로 저 사람이다.",
"웃는 얼굴.",
"이 사과가 맛있게 생겼다.",
"그 책 이리 좀 줘 봐.",
"저 거리에는 항상 사람이 많다.",
"나는 시골에 산다.",
"동생은 방금 집에 갔다.",
"그 시간에 뭐 할 거니?",
"저번에 뭐 했니?",
"밥만 먹지 말고 반찬도 먹어라.",
"하루 종일 잠만 잤더니 머리가 띵했다.",
"물이 맑다.",
"올 사람은 다 왔다.",
"누가 너보고 그 일을 하라고 그러더냐?",
"선생님은 키가 크시다.",
"충무공은 훌륭한 장군이셨다.",
"이거 드세요.",
"네가 맞아.",
"나는 지금 밥 먹어.",
"그는 항상 공부를 열심히 해(*'하여'의 준발).",
"약속을 했으니(까) 가기 싫어도 갈 수밖에.",
"이 옷이 작으니까 좀 큰 것으로 바꿔 주세요.",
"사람들이 많다.",
"오늘이나 내일 중에 편할 때를 선택하여 찾아오거라.",
"백 명이나 모였다고?",
"심심한데 영화나 보러 가자.",
"공부밖에 모르는 학생",
"비가 안 온다.",
"건물 안.",
"날이 추운데 따뜻하게 입어."
]

# 현재 예시 문장 인덱스 관리
if 'current_example' not in st.session_state:
    st.session_state.current_example = random.choice(example_sentences)

# 버튼을 누르면 예시 문장을 바꾸기
if st.button("예시 문장 바꾸기"):
    st.session_state.current_example = random.choice(example_sentences)

# 페이지 제목
st.title("POS 태깅 API 테스트")

# 사용자 입력 받기 (예시 문장으로 초기화)
user_input = st.text_area("분석할 문장을 입력하세요:", st.session_state.current_example, height=100)

# 버튼 및 응답 처리
if st.button("API 요청 보내기"):
    with st.spinner('API 요청 중...'):
        url = 'https://121.78.147.172:30001/v1/pos-types'
        headers = {
            'accept': 'application/json',
            'Content-Type': 'application/json'
        }
        data = {
            'text': user_input
        }

        try:
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()

            result = response.json()
            st.success("API 요청 성공!")

            # 응답 결과 표시 (펼쳐서 볼 수 있도록 변경)
            with st.expander("응답 결과 보기"):
                st.json(result)

            # 결과를 표로 표시
            st.header("결과 테이블")
            st.table(result)

        except requests.exceptions.HTTPError as errh:
            st.error(f"HTTP 에러가 발생했습니다: {errh}")
        except requests.exceptions.ConnectionError as errc:
            st.error(f"연결 오류가 발생했습니다: {errc}")
        except requests.exceptions.Timeout as errt:
            st.error(f"타임아웃 오류가 발생했습니다: {errt}")
        except requests.exceptions.RequestException as err:
            st.error(f"요청 중 예외가 발생했습니다: {err}")
