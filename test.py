import openai # 0.28.0
import re
from kiwipiepy import Kiwi

# Kiwi 초기화
kiwi = Kiwi(num_workers=0, model_path=None, load_default_dict=True, integrate_allomorph=True, model_type='sbg', typos=None, typo_cost_threshold=2.5)

"""
num_workers: 2 이상이면 단어 추출 및 형태소 분석에 멀티 코어를 활용하여 조금 더 빠른 속도로 분석을 진행할 수 있습니다.
1인 경우 단일 코어만 활용합니다. num_workers가 0이면 현재 환경에서 사용가능한 모든 코어를 활용합니다.
생략 시 기본값은 0입니다.
model_path: 형태소 분석 모델이 있는 경로를 지정합니다. 생략시 kiwipiepy_model 패키지로부터 모델 경로를 불러옵니다.
load_default_dict: 추가 사전을 로드합니다. 추가 사전은 위키백과의 표제어 타이틀로 구성되어 있습니다. 이 경우 로딩 및 분석 시간이 약간 증가하지만 다양한 고유명사를 좀 더 잘 잡아낼 수 있습니다. 분석 결과에 원치 않는 고유명사가 잡히는 것을 방지하려면 이를 False로 설정하십시오.
integrate_allomorph: 어미 중, '아/어', '았/었'과 같이 동일하지만 음운 환경에 따라 형태가 달라지는 이형태들을 자동으로 통합합니다.
model_type: 형태소 분석에 사용할 언어 모델을 지정합니다. 'knlm', 'sbg' 중 하나를 선택할 수 있습니다. 'sbg' 는 상대적으로 느리지만 먼 거리에 있는 형태소 간의 관계를 포착할 수 있습니다.
typos: 형태소 분석 시 간단한 오타를 교정합니다. None으로 설정 시 교정을 수행하지 않습니다.
typo_cost_threshold: 오타 교정을 허용할 최대 오타 비용을 설정합니다.
"""

# API 키 설정
openai.api_key = 'sk-proj-nlhN73CnCzO3ShLYyCPuT3BlbkFJdzOuNYCbeHCwAhrhhh7p'

        
######## 데이터 => src/v1/resoures/ 디렉토리 내부로 이동시켜서 불러오게 바꾸기
pos_descriptions  = {"NNG"	:"일반 명사",
"NNP"	:"고유 명사",
"NNB"	:"의존 명사",
"NR"	:"수사",
"NP"	:"대명사",
"VV"	:"동사",
"VV-R"	:"동사(규칙)",
"VV-I"	:"동사(불규칙)",
"VA"	:"형용사",
"VA-R"	:"형용사(규칙)",
"VA-I"	:"형용사(불규칙)",
"VX"	:"보조 용언",
"VX-R"	:"보조 용언(규칙)",
"VX-I"	:"보조 용언(불규칙)",
"VCP"	:"긍정 지시사(이다)",
"VCN"	:"부정 지시사(아니다)",
"MM"	:"관형사",
"MAG"	:"일반 부사",
"MAJ"	:"접속 부사",
"IC"	:"감탄사",
"JKS"	:"주격 조사",
"JKC"	:"보격 조사",
"JKG"	:"관형격 조사",
"JKO"	:"목적격 조사",
"JKB"	:"부사격 조사",
"JKV"	:"호격 조사",
"JKQ"	:"인용격 조사",
"JX"	:"보조사",
"JC"	:"접속 조사",
"EP"	:"선어말 어미",
"EF"	:"종결 어미",
"EC"	:"연결 어미",
"ETN"	:"명사형 전성 어미",
"ETM"	:"관형형 전성 어미",
"XPN"	:"체언 접두사",
"XSN"	:"명사 파생 접미사",
"XSV"	:"동사 파생 접미사",
"XSA"	:"형용사 파생 접미사",
"XSA-R"	:"형용사 파생 접미사(규칙)",
"XSA-I"	:"형용사 파생 접미사(불규칙)",
"XSM"	:"부사 파생 접미사",
"XR"	:"어근",
"SF"	:"종결 부호(. ! ?)",
"SP"	:"구분 부호(, / : ;)",
"SS"	:"""인용 부호 및 괄호(' " ( ) [ ] < > { } ― ‘ ’ “ ” ≪ ≫ 등)""",
"SSO"	:"SS 중 여는 부호",
"SSC"	:"SS 중 닫는 부호",
"SE"	:"줄임표(…)",
"SO"	:"붙임표(- ~)",
"SW"	:"기타 특수 문자",
"SL"	:"알파벳(A-Z a-z)",
"SH"	:"한자",
"SN"	:"숫자(0-9)",
"SB"	:"순서 있는 글머리(가. 나. 1. 2. 가) 나) 등)*",
"UN"	:"분석 불능",
"W_URL"	:"URL 주소",
"W_EMAIL"	:"이메일 주소",
"W_HASHTAG"	:"해시태그(#abcd)",
"W_MENTION"	:"멘션(@abcd)",
"W_SERIAL"	:"일련번호(전화번호, 통장번호, IP주소 등)",
"Z_CODA"	:"덧붙은 받침",
"USER0_4"	:"사용자 정의 태그"}



# 문법 항목 리스트 생성
"""
"/" 로 끊어서 판단.
품사번호 확인 후 형태가 같으면 해당 태그가 사용 됨.

"""
grammatical_items = [
    {
        '번호': 1,
        '형태': '이/가',
        '품사': 'JKS',
        '의미': '어떤 상태를 보이는 대상이나 일정한 상태나 상황을 겪는 경험주 또는 일정한 동작의 주체임을 나타내는 격 조사',
    },
    {
        '번호': 2,
        '형태': '은/는',
        '품사': 'JX',
        '의미': '문장 속에서 어떤 대상이 화제임을 나타내는 보조사',
    },
    {
        '번호': 3,
        '형태': '은/는',
        '품사': 'JX',
        '의미': '어떤 대상이 다른 것과 대조됨을 나타내는 보조사',
    },
    {
        '번호': 4,
        '형태': '은/는',
        '품사': 'JX',
        '의미': '강조의 뜻을 나타내는 보조사',
    },
    {
        '번호': 5,
        '형태': '-은',
        '품사': 'ETM',
        '의미': '앞말이 관형어 구실을 하게 하고 동작이 과거에 이루어졌음을 나타내는 어미',
    },
    {
        '번호': 6,
        '형태': '-는',
        '품사': 'ETM',
        '의미': '앞말이 관형어 구실을 하게 하고 이야기하는 시점에서 볼 때 사건이나 행위가 현재 일어남을 나타내는 어미',
    },
    {
        '번호': 7,
        '형태': '이',
        '품사': 'MM',
        '의미': '말하는 이에게 가까이 있거나 말하는 이가 생각하고 있는 대상을 가리킬 때 쓰는 말',
    },
    {
        '번호': 8,
        '형태': '그',
        '품사': 'MM',
        '의미': '듣는 이에게 가까이 있거나 듣는 이가 생각하고 있는 대상을 가리킬 때 쓰는 말',
    },
    {
        '번호': 9,
        '형태': '저',
        '품사': 'MM',
        '의미': '말하는 이와 듣는 이로부터 멀리 있는 대상을 가리킬 때 쓰는 말',
    },
    {
        '번호': 10,
        '형태': '에',
        '품사': 'JKB',
        '의미': '앞말이 처소의 부사어임을 나타내는 격 조사 또는 진행 방향의 부사어임을 나타내는 격 조사',
    },
    {
        '번호': 11,
        '형태': '에',
        '품사': 'JKB',
        '의미': '앞말이 시간의 부사어임을 나타내는 격 조사',
    },
    {
        '번호': 12,
        '형태': '도',
        '품사': 'JX',
        '의미': '이미 어떤 것이 포함되고 그 위에 더함의 뜻을 나타내는 보조사',
    },
    {
        '번호': 13,
        '형태': '만',
        '품사': 'JX',
        '의미': '다른 것으로부터 제한하여 어느 것을 한정함을 나타내는 보조사',
    },
    {
        '번호': 14,
        '형태': '다',
        '품사': 'EF',
        '의미': '해라할 자리에 쓰여, 어떤 사건이나 사실, 상태를 서술하는 뜻을 나타내는 종결 어미',
    },
    {
        '번호': 15,
        '형태': '다',
        '품사': 'MAG',
        '의미': '남거나 빠진 것이 없이 모두',
    },
    {
        '번호': 16,
        '형태': '보고',
        '품사': 'JKB',
        '의미': '어떤 행동이 미치는 대상임을 나타내는 격 조사',
    },
    {
        '번호': 17,
        '형태': '-(으)시-/으/시/셧/세/세요/으시',
        '품사': 'EP',
        '의미': '높임의 뜻을 더하는 선어말 어미',
    },
    {
        '번호': 18,
        '형태': '-아/어/여/아',
        '품사': 'EF',
        '의미': '해할 자리에 쓰여, 어떤 사실을 서술하거나 물음ㆍ명령ㆍ청유를 나타내는 종결 어미',
    },
    {
        '번호': 19,
        '형태': '(으)니까/으니/으니까/니까',
        '품사': 'EC',
        '의미': '앞말이 뒷말의 원인이나 근거, 전제 따위가 됨을 나타내는 연결 어미',
    },
    {
        '번호': 20,
        '형태': '들',
        '품사': 'XSN',
        '의미': '복수의 뜻을 더하는 접미사',
    },
    {
        '번호': 21,
        '형태': '(이)나/이나/나',
        '품사': 'JC',
        '의미': '둘 이상의 사물을 같은 자격으로 이어 주는 접속 조사',
    },
    {
        '번호': 22,
        '형태': '(이)나/이나/나',
        '품사': 'JX',
        '의미': '수량이 크거나 많음, 혹은 정도가 높음을 강조하는 보조사',
    },
    {
        '번호': 23,
        '형태': '(이)나/나/이나',
        '품사': 'JX',
        '의미': '마음에 차지 않는 선택, 또는 최소한 허용되어야 할 선택이라는 뜻을 나타내는 보조사',
    },
    {
        '번호': 24,
        '형태': '밖에',
        '품사': 'JX',
        '의미': '그것 말고는, 그것 이외에는의 뜻을 나타내는 보조사',
    },
    {
        '번호': 25,
        '형태': '안',
        '품사': 'MAG',
        '의미': '부정이나 반대의 뜻을 나타내는 말',
    },
    {
        '번호': 26,
        '형태': '안',
        '품사': 'NNG',
        '의미': '어떤 물체나 공간의 둘러싸인 가에서 가운데로 향한 쪽. 또는 그런 곳이나 부분',
    },
    {
        '번호': 27,
        '형태': '-게',
        '품사': 'EC',
        '의미': '앞의 내용이 뒤에서 가리키는 사태의 목적이나 결과, 방식, 정도 따위가 됨을 나타내는 연결 어미',
    }
]

# 로직컬 적으로 판단을 위해
 
# 시간 명사
time_nouns = {
'시간', '때', '시각', '분', '초', '어제', '오늘', '내일', '모레', '그제', '글피', '지난주', '이번주', '다음주',
    '월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일', '주말', '평일', '아침', '점심', '저녁', '밤', '새벽', '낮',
    '방금', '그때', '이때', '저때', '지금', '그동안', '이후', '이전', '지난달', '이번달', '다음달', '작년', '올해', '내년',
    '봄', '여름', '가을', '겨울', '어린 시절', '청소년기', '성인기', '노년기', '초', '중', '말', '첫날', '마지막 날',
    '전날', '이튿날', '사흘', '나흘', '닷새', '엿새', '일주일', '보름', '한 달', '두 달', '세 달', '석 달', '반년', '일년', '두 해', '세 해',
    '연초', '연말', '중순', '상반기', '하반기', '사계절', '1분기', '2분기', '3분기', '4분기', '10년', '세기', '밀레니엄', '대공황',
    '유년기', '사춘기', '청년기', '중년기', '노년기', '이전', '다음', '이후', '현재', '과거', '미래', '선사시대', '고대', '중세', '근세', '현대',
    '새벽 1시', '새벽 2시', '오전 3시', '오전 4시', '오후 5시', '오후 6시', '밤 7시', '밤 8시', '자정', '정오',
    '초반', '중반', '후반', '초기', '중기', '말기', '하루', '주중', '주간', '연중', '평생', '영원', '순간', '찰나', '잠시', '얼마간', 
    '하루하루', '해마다', '계속', '영겁', '어느 날', '어느 순간', '동이 틀 무렵', '해질 녘', '밤중', '한낮', '정오', '이른 아침', '늦은 저녁',
    '초저녁', '심야', '한밤중', '말년', '초창기', '말미', '막바지', '오랜만', '잠깐', '순식간', '한순간', '짧은 시간', '긴 시간',
    '첫 번째', '두 번째', '세 번째', '네 번째', '다섯 번째', '처음', '마지막', '종반', '결말', '피날레',
    '20세기', '21세기', '100년', '200년', '천년', '십년', '반세기', '한 세대', '두 세대', '역사 속에서', '오래전', 
    '아득한 옛날','시간', '때', '시각', '분', '초', '어제', '오늘', '내일', '모레', '지난주', '이번주', '다음주',
    '월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일', '주말', '아침', '점심', '저녁', '밤', '새벽', '방금', '그때', '지난달', '이번달', '다음달', '작년', '올해', '내년', '저번' , '이번', '옛날', '새벽','아침','오전','자정','주','오전','백년','십년','일년'
}

# 수량 명사
quantity_nouns = {
    '한', '두', '세', '네', '다섯', '여섯', '일곱', '여덟', '아홉', '열', '백', '천', '만',
    '개', '명', '번', '시간', '일', '주', '달', '년', '원', '킬로그램', '그램', '미터', '센티미터', '리터', '도'
}

#############
        
# 함수 내에서 동기적으로 호출
def chatgpt(text, matched_items, pna_token, now_token):
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{
            "role": "user",
            "content": f"""
            sentence: {text}
            pna_token : {pna_token}
            now_token : {now_token}
            matched_items: {matched_items}

            현재 나는 한국어 문장 태깅 모델에서 판단하기 어려운 부분을 너에게 맡기려고 해.
            sentence는 전체 문장이고, pna_token의 가운데인 now_token의 태깅을 판단해야해.
            matched_items는 현재 태깅의 어려운 부분이야. 이 부분이 2가지 이상의 태깅이 되어있어.
            matched_items의 번호가 몇번이 정답일지 판단해서 숫자로 정답만 알려줘
            matched_items의 번호가 0번인 경우 nlp모델이 분류한 결과야 이게 맞을 수 있는데 나머지 번호가 틀렸다고 판단될 경우 0번으로 알려줘
            """
        }],
        stream=False,  # 스트리밍 비활성화
    )

    # 응답 처리
    full_text = str(response['choices'][0]['message']['content'])
    print("====GPT answer====", full_text)

    return full_text

# 
def pos_tag_print(results):
    output = []
    # 형태소 분석 결과와 문법 항목 매핑
    for tokens, score in results:
        for token in tokens:
            morpheme = token.form  # 형태소 (form)
            pos = token.tag        # 품사 태그 (tag)
            pos_desc = pos_descriptions.get(pos, '알 수 없음')
            matched_items = []
            for item in grammatical_items:
                # 형태에서 '-'를 제거하고 '/'로 분리하여 각 형태소를 비교
                item_forms = item['형태'].replace('-', '').split('/')
                if morpheme in item_forms and pos == item['품사']:
                    matched_items.append(item)
            output.append({
                'morpheme': morpheme,
                'pos': pos,
                'pos_desc': pos_desc,
                'matched_items': matched_items
            })
    return output

#문장을 끊어서 판단
def split_sentences(output): 
    sentences = []
    sentence = []
    for token in output: 
        sentence.append(token)
        if token['pos'] in ['EF']: # 문장 구분: 종결 어미(EF)와 종결 부호(SF)를 기준으로 문장을 분리 # @@ 바꾸어야 할 지도.
            sentences.append(sentence)
            sentence = []
    # 마지막 문장이 EF나 SF로 끝나지 않는 경우 처리
    if sentence:
        sentences.append(sentence)
    return sentences


def check_logic(sentence_tokens):
    
    output = all_text = sentence_tokens # GPT에 쓰임
    
    ### 은/는 JX 처리
    # 문장 내에서 '은/는'이고 품사가 'JX'인 형태소의 인덱스 목록 추출
    eunnun_indices = [i for i, token in enumerate(output) if token['morpheme'] in ['은', '는'] and token['pos'] == 'JX']

    # 1. 번호 3번 항목 처리: 문장 내에서 '은/는'이 두 번 이상 등장하고, 그 사이에 EC와 NNG가 있는 경우
    assigned_indices = set()
    if len(eunnun_indices) >= 2:
        for idx1 in eunnun_indices:
            for idx2 in eunnun_indices:
                if idx2 <= idx1:
                    continue
                between_tokens = output[idx1+1:idx2]
                has_EC = any(tok['pos'] == 'EC' for tok in between_tokens)
                has_NNG = any(tok['pos'] == 'NNG' for tok in between_tokens)
                if has_EC and has_NNG:
                    for idx in [idx1, idx2]:
                        token = output[idx]
                        item3 = next((item for item in token['matched_items'] if item['번호'] == 3), None)
                        
                        if item3:
                            token['matched_items'] = [item3]
                            assigned_indices.add(idx)  # 태깅된 인덱스 저장

    # 2. 번호 4번 항목 처리: '은/는' 뒤에 동사(VV)가 오는 경우
    for idx in eunnun_indices:
        if idx in assigned_indices:
            continue  # 이미 태깅된 경우 건너뜀
        token = output[idx]
        if idx + 1 < len(output):
            next_token = output[idx + 1]
            if next_token['pos'] == 'VV':
                item4 = next((item for item in token['matched_items'] if item['번호'] == 4), None)
                
                if item4:
                    token['matched_items'] = [item4]
                    assigned_indices.add(idx)
                continue

    # 3. 번호 2번 항목 처리: 앞에 명사(N*)가 오는 경우
    for idx in eunnun_indices:
        if idx in assigned_indices:
            continue  # 이미 태깅된 경우 건너뜀
        token = output[idx]
        assigned = False
        if idx > 0:
            prev_token = output[idx - 1]
            if prev_token['pos'].startswith('N'):
                item2 = next((item for item in token['matched_items'] if item['번호'] == 2), None)
                
                if item2:
                    token['matched_items'] = [item2]
                    assigned_indices.add(idx)
                    assigned = True
                    
        if not assigned and idx >= 2:
            prev_prev_token = output[idx - 2]
            prev_token = output[idx - 1]
            if prev_prev_token['pos'].startswith('N') and prev_token['pos'] in ['JKB','JKS' ,'XSN']:
                item2 = next((item for item in token['matched_items'] if item['번호'] == 2), None)
                if item2:
                    token['matched_items'] = [item2]
                    assigned_indices.add(idx)
                        
        # 새로운 로직 추가: 이전 이전 토큰이 명사(N*), 이전 토큰이 XSN 또는 JKB인 경우 , 이전 토큰이 명사 인 경우
        if not assigned and idx >= 2:
            prev_prev_token = output[idx - 2]
            prev_token = output[idx - 1]
            
            if prev_prev_token['pos'].startswith('N') and prev_token['pos'] in ['XSN', 'JKB']:
                # 번호 2로 설정
                # print("이전 이전 토큰이 명사(N*), 이전 토큰이 XSN 또는 JKB인 경우=========")
                item2 = next((item for item in token['matched_items'] if item['번호'] == 2), None)
                if item2:
                    token['matched_items'] = [item2]
                    assigned = True
                    
    ### JKB 처리 (10번 11번)
    for idx, token in enumerate(output):
        if token['morpheme'] == '에' and token['pos'] == 'JKB':
            # 앞의 토큰을 가져옵니다.
            if idx > 0:
                prev_token = output[idx - 1]
                # 앞의 토큰이 의존 명사(NNB)인 경우
                if prev_token['pos'] == 'NNB':
                    # 앞의 토큰이 의존 명사라면, 그 앞의 가장 가까운 일반 명사(NNG)를 찾습니다.
                    found_time_noun = False
                    for back_idx in range(idx - 2, -1, -1):
                        back_token = output[back_idx]
                        if back_token['pos'] == 'NNG':
                            if back_token['morpheme'] in time_nouns:
                                # 시간 표현 단어를 찾았으므로 번호 11로 설정
                                item11 = next((item for item in token['matched_items'] if item['번호'] == 11), None)
                                if item11:
                                    token['matched_items'] = [item11]
                                found_time_noun = True
                            break  # 가장 가까운 NNG를 찾았으므로 루프 종료
                    if not found_time_noun:
                        # 시간 표현 단어를 찾지 못한 경우 번호 10으로 설정
                        item10 = next((item for item in token['matched_items'] if item['번호'] == 10), None)
                        if item10:
                            token['matched_items'] = [item10]
                            
                # 앞의 토큰이 명사(NNG, NNP, NP)인 경우
                elif prev_token['pos'] in ['NNG', 'NNP', 'NP']:
                    if prev_token['morpheme'] in time_nouns:
                        # 번호 11로 설정 (시간의 부사어)
                        item11 = next((item for item in token['matched_items'] if item['번호'] == 11), None)
                        if item11:
                            token['matched_items'] = [item11]
                    else:
                        # 번호 10으로 설정 (처소의 부사어)
                        item10 = next((item for item in token['matched_items'] if item['번호'] == 10), None)
                        if item10:
                            token['matched_items'] = [item10]
                else:
                    # 앞의 토큰이 명사가 아닌 경우 기본적으로 번호 10으로 설정
                    item10 = next((item for item in token['matched_items'] if item['번호'] == 10), None)
                    if item10:
                        token['matched_items'] = [item10]
            else:
                # 앞의 토큰이 없는 경우 번호 10으로 설정
                print("JKB else 구문 오류 날 수 있음")
                item10 = next((item for item in token['matched_items'] if item['번호'] == 10), None)
                if item10:
                    token['matched_items'] = [item10]
                    

            
    ### '(이)나' (JX) 처리 22,23,21도
    # 문장 내에서 '(이)나' (JX)를 처리
    for idx, token in enumerate(output):
        if token['morpheme'] in ['이나', '나'] and token['pos'] == 'JX':
            assign_number = None  # 22 또는 23으로 설정할 변수

            # 조건 1: 수사(NR) 또는 숫자(SN) + 명사(NN*) + JX('이나'/'나') (번호 22번)
            if idx >= 2:
                prev_token = output[idx - 1]
                prev_prev_token = output[idx - 2]
                if (prev_prev_token['pos'] in ['NR', 'SN']) and prev_token['pos'].startswith('NN'):
                    assign_number = 22

            # 조건 2: MM(수량 관형사) + 명사(NN*) + JX('이나'/'나') (번호 22번)
            if assign_number is None and idx >= 2:
                prev_token = output[idx - 1]
                prev_prev_token = output[idx - 2]
                if (prev_prev_token['pos'] == 'MM' and prev_prev_token['morpheme'] in quantity_nouns and prev_token['pos'].startswith('NN')):
                    assign_number = 22

            # 조건 3: EC + NNG + JX('이나'/'나') (번호 23번)
            if assign_number is None and idx >= 2:
                prev_token = output[idx - 1]
                prev_prev_token = output[idx - 2]
                if prev_prev_token['pos'] == 'EC' and prev_token['pos'] == 'NNG':
                    assign_number = 23

            # 조건 4: JX('이나'/'나') 뒤에 VV (번호 23번)
            if assign_number is None and idx + 1 < len(output):
                next_token = output[idx + 1]
                if next_token['pos'] == 'VV':
                    assign_number = 23

            # 번호 할당
            if assign_number == 22:
                item22 = next((item for item in token['matched_items'] if item['번호'] == 22), None)
                if item22:
                    token['matched_items'] = [item22]
            elif assign_number == 23:
                item23 = next((item for item in token['matched_items'] if item['번호'] == 23), None)
                if item23:
                    token['matched_items'] = [item23]
            else:
                # 조건에 해당하지 않는 경우 matched_items를 그대로 유지
                pass

    ### '나/이나' (JC) 처리: 아이템 21번 태깅
    for idx, token in enumerate(output):
        if token['morpheme'] in ['나', '이나'] and token['pos'] == 'JC':
            # 앞뒤 토큰을 확인합니다.
            prev_token = output[idx - 1] if idx > 0 else None
            next_token = output[idx + 1] if idx + 1 < len(output) else None

            if prev_token and next_token:
                # 앞뒤 토큰의 품사가 명사(N*)인지 확인
                if prev_token['pos'].startswith('N') and next_token['pos'].startswith('N'):
                    # 번호 21번 항목을 가져옵니다.
                    
                    item21 = next((item for item in token['matched_items'] if item['번호'] == 21), None)
                    if item21:
                        token['matched_items'] = [item21]    
                        
    ### '세요' (EF) 처리  17번 (강제로 찾게 만듦.)
    for token in output:
        if token['pos'] == 'EF' and token['morpheme'].endswith('세요'):
            token_1 = [grammatical_items[k] for k in range(len(grammatical_items)) if (grammatical_items[k]['번호']==17)][0] # n 번 태깅 찾기
            token['pos']= token_1["품사"]
            token['pos_desc']= token_1["의미"]
            token['matched_items'].append(token_1)
    
    ### N* N* N* 패턴에서 가운데 N이 '보고'인 경우 번호 16번 태깅 (강제로 찾게 만듦.)
    for idx in range(1, len(output) - 1):
        token = output[idx]
        if token['pos'] == 'NNG' and token['morpheme'] == '보고':
            prev_token = output[idx - 1]
            next_token = output[idx + 1]
            if prev_token['pos'].startswith('N') and next_token['pos'].startswith('N'):
                # 번호 16으로 설정
                token_1 = [grammatical_items[k] for k in range(len(grammatical_items)) if (grammatical_items[k]['번호']==16)][0] # 16번 태깅 찾기
                token['pos']= token_1["품사"]
                token['pos_desc']= token_1["의미"]
                token['matched_items'].append(token_1)

    # # gpt 이용 부문.
    # # @@ 여기서 gpt가 답을 고르지 못한 경우 None 태그를 만들어서 이 경우엔 기본 태그가 나오게 하자.
    # # 최종, 태그가 2개 이상 있는 경우 해당 태그를 llm모델에 맡겨서 뭐가 맞는지 판단하게 함.
    for idx, token in enumerate(output):
        if len(token["matched_items"]) >= 2:
            # 이전 토큰과 다음 토큰을 가져옵니다.
            pre_token = output[idx - 1]["morpheme"] if idx > 0 else ''
            now_token = token["morpheme"]
            after_token = output[idx + 1]["morpheme"] if idx + 1 < len(output) else ''

            # 문장 전체 텍스트를 재구성합니다.
            sentence_text = ''.join(tok['morpheme'] for tok in output)

            try:
                # GPT 함수 호출
                token['matched_items'].insert(0,{'번호': 0,'형태': token['morpheme'],'품사': token['pos'],'의미': token['pos_desc']}) # 기존 형태의 품사(nlp가 분류한 더 큰 집합[분류]의 품사)를 넣고 비교
                gpt_answer = chatgpt(sentence_text, token["matched_items"], pre_token + now_token + after_token, now_token)
                correct_tag = int(re.findall(r'\d+', gpt_answer)[0]) # GPT 응답에서 숫자 추출

                item = next((item for item in token['matched_items'] if item['번호'] == correct_tag), None)
                if item:
                    token['matched_items'] = [item]

                print("llm사용됨", sentence_text)
                print("정답으로 만든 태그", correct_tag, token["matched_items"])
            except Exception as e:
                print("GPT오류", e)
                pass
            # try:
            #     # GPT 함수 호출
            #     token['matched_items'].insert(0,{'번호': 0,'형태': token['morpheme'],'품사': token['pos'],'의미': token['pos_desc']}) # 기존 형태의 품사(nlp가 분류한 더 큰 집합[분류]의 품사)를 넣고 비교
                
            #     # print("token['matched_items']",token['matched_items'])
                
            #     # GPT 함수 호출을 비동기적으로 처리
            #     gpt_answer = await asyncio.to_thread(
            #         get_correct_tag,
            #         sentence_text,
            #         token["matched_items"],
            #         pre_token + now_token + after_token,
            #         now_token
            #     )
            #     correct_tag = int(re.findall(r'\d+', gpt_answer)[0]) # GPT 응답에서 숫자 추출 

            #     item = next((item for item in token['matched_items'] if item['번호'] == correct_tag), None)
            #     if item:
            #         token['matched_items'] = [item]

            #     # print("llm사용됨", sentence_text)
            #     # print("정답으로 만든 태그", correct_tag, token["matched_items"])
            # except Exception as e:
            #     print("llm오류", e)
            #     pass
            
        else:
            # 태그가 1개인 경우 패스 
            pass
        
    # 최종 결과 출력
    for token in output:
        morpheme = token['morpheme']
        pos = token['pos']
        pos_desc = token['pos_desc']
        matched_items = token['matched_items']
        if matched_items:
            for item in matched_items:
                print(f"형태소 '{morpheme}' (품사: {pos} - {pos_desc})는 문법 항목 번호 {item['번호']}에 해당합니다: {item['의미']}")
        else:
            print(f"형태소 '{morpheme}' (품사: {pos} - {pos_desc})")
    return output  # 수정된 output 리스트 반환"""





def main(text):
    # pos_tag_print 함수 호출 # 형태소 분석 수행
    output = pos_tag_print(results = kiwi.analyze(text))
    # 문장 단위로 분리 @@ => 이붑분 kiwi 분석기가 있다했음
    sentences = split_sentences(output)
    # 각 문장별로 처리하고 결과를 합침

    final_output = []
    for sentence_tokens in sentences:
        processed_sentence = check_logic(sentence_tokens)
        final_output.extend(processed_sentence)
        
    return final_output

# 실행 예시
text = """이거 드세요.
이것은 나의 것이다.
"""
final_output = main(text)

# final_output 예시 결과
"""
[{'morpheme': '이거', 'pos': 'NP', 'pos_desc': '대명사', 'matched_items': []},
 {'morpheme': '들', 'pos': 'VV', 'pos_desc': '동사', 'matched_items': []},
 {'morpheme': '세요',
  'pos': 'EP',
  'pos_desc': '높임의 뜻을 더하는 선어말 어미',
  'matched_items': [{'번호': 17,
    '형태': '-(으)시-/으/시/셧/세/세요/으시',
    '품사': 'EP',
    '의미': '높임의 뜻을 더하는 선어말 어미'}]},
 {'morpheme': '.',
  'pos': 'SF',
  'pos_desc': '종결 부호(. ! ?)',
  'matched_items': []},
 {'morpheme': '이것', 'pos': 'NP', 'pos_desc': '대명사', 'matched_items': []},
 {'morpheme': '은',
  'pos': 'JX',
  'pos_desc': '보조사',
  'matched_items': [{'번호': 2,
    '형태': '은/는',
    '품사': 'JX',
    '의미': '문장 속에서 어떤 대상이 화제임을 나타내는 보조사'}]},
 {'morpheme': '나', 'pos': 'NP', 'pos_desc': '대명사', 'matched_items': []},
 {'morpheme': '의', 'pos': 'JKG', 'pos_desc': '관형격 조사', 'matched_items': []},
 {'morpheme': '것', 'pos': 'NNB', 'pos_desc': '의존 명사', 'matched_items': []},
 {'morpheme': '이',
  'pos': 'VCP',
  'pos_desc': '긍정 지시사(이다)',
  'matched_items': []},
 {'morpheme': '다',
  'pos': 'EF',
  'pos_desc': '종결 어미',
  'matched_items': [{'번호': 14,
    '형태': '다',
    '품사': 'EF',
    '의미': '해라할 자리에 쓰여, 어떤 사건이나 사실, 상태를 서술하는 뜻을 나타내는 종결 어미'}]},
 {'morpheme': '.',
  'pos': 'SF',
  'pos_desc': '종결 부호(. ! ?)',
  'matched_items': []}]
"""