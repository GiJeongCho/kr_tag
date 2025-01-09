import openai # 0.28.0

# API 키 설정
openai.api_key = 'sk-proj-nlhN73CnCzO3ShLYyCPuT3BlbkFJdzOuNYCbeHCwAhrhhh7p  '

# 함수 내에서 동기적으로 호출
def get_correct_tag(text, matched_items, pna_token, now_token):
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{
            "role": "user",
            "content": f"""
            sentence: {text}
            pna_token : {pna_token}
            now_token : {now_token}
            matched_items: {matched_items}

            현재 나는 한국어 문장 태깅에서 판단하기 어려운 부분을 너에게 맡기려고 해.
            sentence는 전체 문장이고, pna_token의 가운데인 now_token의 태깅을 판단해야해.
            matched_items는 현재 태깅의 어려운 부분이야. 이 부분이 2가지 이상의 태깅이 되어있어.
            matched_items의 번호가 몇번이 정답일지 판단해서 숫자로 정답만 알려줘
            * 즉 matched_items 0번은 기존 분류고 nlp모델이 분류한 결과야 nlp모델 분류 결과가 틀렸다고 판단될 경우 0번으로 알려줘
            그렇지 않은 경우 반드시 matched_items의 번호 중에서의 숫자만 알려줘.
            반드시 설명하지말고 숫자만 알려줘.
            """
        }],
        stream=False,  # 스트리밍 비활성화
    )

    # 응답 처리
    full_text = str(response['choices'][0]['message']['content'])
    # print("====GPT answer====", full_text)
    
    return full_text
