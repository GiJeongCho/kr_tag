import unicodedata
import os
import json

def normalize_morpheme(morpheme):
    # 유니코드 정규화를 통해 결합 문자 처리
    return unicodedata.normalize('NFC', morpheme)

def load_resources():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    resources_dir = os.path.join(base_dir, 'resources')

    with open(os.path.join(resources_dir, 'pos_descriptions.json'), 'r', encoding='utf-8') as f:
        pos_descriptions = json.load(f)
        
    with open(os.path.join(resources_dir, 'grammatical_items.json'), 'r', encoding='utf-8') as f:
        grammatical_items = json.load(f)
        
    with open(os.path.join(resources_dir, 'quantity_nouns.json'), 'r', encoding='utf-8') as f:
        quantity_nouns = set(json.load(f))
        
    with open(os.path.join(resources_dir, 'time_nouns.json'), 'r', encoding='utf-8') as f:
        time_nouns = set(json.load(f))
        
    with open(os.path.join(resources_dir, 'place_nouns.json'), 'r', encoding='utf-8') as f:
        place_nouns = set(json.load(f))
        
    return pos_descriptions, grammatical_items, quantity_nouns, time_nouns, place_nouns

pos_descriptions, grammatical_items, quantity_nouns, time_nouns, place_nouns = load_resources()
grammatical_items_dict = {item['번호']: item for item in grammatical_items} # 딕셔너리로 빨리 찾기

def check_item_1(output):
    idx = 0
    while idx < len(output):
        token = output[idx]
        # '나' 또는 '이나'이고 품사가 'JX'인지 확인
        if token['morpheme'] in ['나', '이나'] and token['pos'] == 'JX':
            should_tag = False

            # 다음 토큰이 존재하고, 다음 토큰의 품사가 'VV'인지 확인
            if idx + 1 < len(output):
                next_token = output[idx + 1]
                if next_token['pos'] == 'VV':
                    should_tag = True

                    # 제외 조건 2: '나/이나' + 동사(VV) + '니까' 제외
                    if idx + 2 < len(output):
                        next_next_token = output[idx + 2]
                        if next_next_token['morpheme'] == '니까':
                            should_tag = False

            # 제외 조건 1: 앞에 일반 명사(NNG)가 있고, 다음에 일반 명사(NNG)가 오는 경우 제외
            if idx > 0 and idx + 1 < len(output):
                prev_token = output[idx - 1]
                next_token = output[idx + 1]
                if prev_token['pos'] == 'NNG' and next_token['pos'] == 'NNG':
                    should_tag = False

            # 제외 조건 3: 앞에 '아무'가 오는 경우 제외
            if idx > 0:
                prev_token = output[idx - 1]
                if prev_token['morpheme'] == '아무':
                    should_tag = False

            # 제외 조건 4: 앞에 '어떤'이 오는 경우 제외
            if idx > 0:
                prev_token = output[idx - 1]
                if prev_token['morpheme'] == '어떤':
                    should_tag = False

            # 태깅 여부 결정
            if should_tag:
                token['matched_items'] = [item for item in grammatical_items if item['번호'] == 1]

        idx += 1
    return output

def check_item_2(output): # 있어요
    idx = 0
    while idx < len(output) - 1:
        token = output[idx]
        next_token = output[idx + 1]
        if token['morpheme'] == '있' and token['pos'] == 'VA':
            if next_token['morpheme'] == '어요' and next_token['pos'] == 'EF':
                # '있' + '어요'를 병합하여 '있어요'로 만듦
                merged_token = {
                    'morpheme': '있어요',
                    'pos': 'VA+EF',
                    'pos_desc': '형용사+종결 어미',
                    'matched_items': [item for item in grammatical_items if item['번호'] == 2],
                    'start': token['start'],
                    'len': token['len'] + next_token['len'],
                    'end': next_token['end']
                }
                # 기존 토큰을 병합된 토큰으로 대체
                output = output[:idx] + [merged_token] + output[idx + 2:]
                # 인덱스 조정
                idx += 1
            else:
                idx += 1
        else:
            idx += 1
    return output

def check_item_5(output): # -았/었/였어요 (Past tense)
    idx = 0
    while idx < len(output) - 1:
        token = output[idx]
        next_token = output[idx + 1]
        if token['morpheme'] in ['았', '었', '였'] and token['pos'] == 'EP':
            if next_token['morpheme'] == '어요' and next_token['pos'] == 'EF':
                # '았/었/였' + '어요'를 병합하여 처리
                merged_morpheme = token['morpheme'] + '어요'
                merged_token = {
                    'morpheme': merged_morpheme,
                    'pos': 'EP+EF',
                    'pos_desc': '선어말 어미+종결 어미',
                    'matched_items': [item for item in grammatical_items if item['번호'] == 5],
                    'start': token['start'],
                    'len': token['len'] + next_token['len'],
                    'end': next_token['end']
                }
                output = output[:idx] + [merged_token] + output[idx + 2:]
                idx += 1
            else:
                idx += 1
        else:
            idx += 1
    return output

def check_item_6(output): # 주세요
    idx = 0
    while idx < len(output) - 1:
        token = output[idx]
        next_token = output[idx + 1]
        if token['morpheme'] == '주' and token['pos'] in ['VV']:
            if next_token['morpheme'] == '세요' and next_token['pos'] == 'EF':
                # '주' + '세요'를 병합하여 처리
                merged_token = {
                    'morpheme': '주세요',
                    'pos': token['pos'] + '+EF',
                    'pos_desc': '동사+종결 어미',
                    'matched_items': [item for item in grammatical_items if item['번호'] == 6],
                    'start': token['start'],
                    'len': token['len'] + next_token['len'],
                    'end': next_token['end']
                }
                output = output[:idx] + [merged_token] + output[idx + 2:]
                idx += 1
            else:
                idx += 1
        else:
            idx += 1
    return output

def check_item_7(output): # 고 싶어요
    idx = 0
    while idx < len(output) - 2:
        token = output[idx]
        next_token = output[idx + 1]
        next_next_token = output[idx + 2]
        if token['morpheme'] == '고' and token['pos'] == 'EC':
            if next_token['morpheme'] == '싶' and next_token['pos'] == 'VX':
                if next_next_token['morpheme'] == '어요' and next_next_token['pos'] == 'EF':
                    # '고' + '싶' + '어요'를 병합하여 처리
                    merged_token = {
                        'morpheme': '고 싶어요',
                        'pos': 'EC+VX+EF',
                        'pos_desc': '연결 어미+보조 동사+종결 어미',
                        'matched_items': [item for item in grammatical_items if item['번호'] == 7],
                        'start': token['start'],
                        'len': token['len'] + next_token['len'] + next_next_token['len'],
                        'end': next_next_token['end']
                    }
                    output = output[:idx] + [merged_token] + output[idx + 3:]
                    idx += 1
                else:
                    idx += 1
            else:
                idx += 1
        else:
            idx += 1
    return output

def check_item_8(output):
    idx = 0
    while idx < len(output) - 2:
        token = output[idx]
        next_token = output[idx + 1]
        next_next_token = output[idx + 2]
        if token['morpheme'] == '거' and token['pos'] == 'NNB':
            if next_token['morpheme'] == '이' and next_token['pos'] == 'VCP':
                if next_next_token['morpheme'] == '에요' and next_next_token['pos'] == 'EF':
                    # '거' + '이' + '에요'를 병합하여 처리
                    merged_token = {
                        'morpheme': '거예요',
                        'pos': 'NNB+VCP+EF',
                        'pos_desc': '의존 명사+긍정 지시사+종결 어미',
                        'matched_items': [item for item in grammatical_items if item['번호'] == 8],
                        'start': token['start'],
                        'len': token['len'] + next_token['len'] + next_next_token['len'],
                        'end': next_next_token['end']
                    }
                    output = output[:idx] + [merged_token] + output[idx + 3:]
                    idx += 1
                else:
                    idx += 1
            else:
                idx += 1
        else:
            idx += 1
    return output

def check_item_9(output):
    idx = 0
    while idx < len(output) - 2:
        token = output[idx]
        next_token = output[idx + 1]
        next_next_token = output[idx + 2]
        if token['morpheme'] == '고' and token['pos'] == 'EC':
            if next_token['morpheme'] == '있' and next_token['pos'] == 'VX':
                if next_next_token['morpheme'] in ['다', '어요'] and next_next_token['pos'] == 'EF':
                    # '고' + '있' + '다/어요'를 병합하여 처리
                    merged_morpheme = '고 있' + next_next_token['morpheme']
                    merged_token = {
                        'morpheme': merged_morpheme,
                        'pos': 'EC+VX+EF',
                        'pos_desc': '연결 어미+보조 동사+종결 어미',
                        'matched_items': [item for item in grammatical_items if item['번호'] == 9],
                        'start': token['start'],
                        'len': token['len'] + next_token['len'] + next_next_token['len'],
                        'end': next_next_token['end']
                    }
                    output = output[:idx] + [merged_token] + output[idx + 3:]
                    idx += 1
                else:
                    idx += 1
            else:
                idx += 1
        else:
            idx += 1
    return output
# def check_item_10(output):
#     for idx, token in enumerate(output):
#         if token['morpheme'] == '어서' and token['pos'] == 'EC':
#             # '어서'를 10번 항목으로 태깅
#             token['matched_items'] = [item for item in grammatical_items if item['번호'] == 10]
#     return output
def check_item_12(output):
    idx = 0
    while idx < len(output) - 2:
        token = output[idx]
        next_token = output[idx + 1]
        next_next_token = output[idx + 2]
        if token['morpheme'] == '것' and token['pos'] == 'NNB':
            if next_token['morpheme'] == '같' and next_token['pos'] == 'VA':
                if next_next_token['pos'] == 'EF':
                    # '것' + '같' + 종결어미를 병합하여 처리
                    merged_token = {
                        'morpheme': '것 같' + next_next_token['morpheme'],
                        'pos': 'NNB+VA+EF',
                        'pos_desc': '의존 명사+형용사+종결 어미',
                        'matched_items': [item for item in grammatical_items if item['번호'] == 12],
                        'start': token['start'],
                        'len': token['len'] + next_token['len'] + next_next_token['len'],
                        'end': next_next_token['end']
                    }
                    output = output[:idx] + [merged_token] + output[idx + 3:]
                    idx += 1
                else:
                    idx += 1
            else:
                idx += 1
        else:
            idx += 1
    return output
def check_item_14(output):
    idx = 0
    while idx < len(output):
        token = output[idx]
        if token['morpheme'] == '같' and token['pos'] == 'VA':
            should_tag = True  # 태깅 여부 결정 변수

            # 이전 토큰 검사
            if idx >= 1:
                prev_token = output[idx - 1]

                # 경우 2: "것"(NNB) + "같"(VA)
                if prev_token['morpheme'] == '것' and prev_token['pos'] == 'NNB':
                    should_tag = False

                # 경우 1 및 3: "것"(NNB) + 격 조사(JK*) 또는 보조사(JX) + "같"(VA)
                elif idx >= 2:
                    prev_prev_token = output[idx - 2]
                    if prev_prev_token['morpheme'] == '것' and prev_prev_token['pos'] == 'NNB':
                        if prev_token['pos'].startswith('JK') or prev_token['pos'] == 'JX':
                            should_tag = False

            if should_tag:
                # 14번 항목으로 태깅
                token['matched_items'] = [item for item in grammatical_items if item['번호'] == 14]
            idx += 1
        else:
            idx += 1
    return output
def check_item_17(output):
    idx = 0
    while idx < len(output) - 1:
        token = output[idx]
        next_token = output[idx + 1]
        if token['morpheme'] == '보' and token['pos'] == 'VX':
            if next_token['morpheme'] in ['았', '었'] and next_token['pos'] == 'EP':
                # '보' + '았/었'을 병합하여 처리
                merged_morpheme = '보' + next_token['morpheme']
                merged_token = {
                    'morpheme': merged_morpheme,
                    'pos': 'VX+EP',
                    'pos_desc': '보조 동사+선어말 어미',
                    'matched_items': [item for item in grammatical_items if item['번호'] == 17],
                    'start': token['start'],
                    'len': token['len'] + next_token['len'],
                    'end': next_token['end']
                }
                output = output[:idx] + [merged_token] + output[idx + 2:]
                idx += 1
            else:
                idx += 1
        else:
            idx += 1
    return output
def check_item_18(output):
    idx = 0
    while idx < len(output) - 4:
        token = output[idx]
        next_token = output[idx + 1]
        next_next_token = output[idx + 2]
        next_next_next_token = output[idx + 3]
        # 뒤의 토큰들을 가져옵니다.
        following_tokens = output[idx + 4:]

        if token['morpheme'] == '그렇' and token['pos'] == 'VA-I':
            if next_token['morpheme'] == '지' and next_token['pos'] == 'EC':
                if next_next_token['morpheme'] == '않' and next_next_token['pos'] == 'VX':
                    if next_next_next_token['morpheme'] == '아도' and next_next_next_token['pos'] == 'EC':
                        # 뒤에 '려고'(EC) + '하'(VX)가 있는지 확인
                        if len(following_tokens) >= 2:
                            after_token1 = following_tokens[0]
                            after_token2 = following_tokens[1]
                            if after_token1['morpheme'] == '려고' and after_token1['pos'] == 'EC':
                                if after_token2['morpheme'] == '하' and after_token2['pos'] == 'VX':
                                    # '그렇지 않아도' 부분만 18번 항목으로 태깅
                                    merged_token = {
                                        'morpheme': '그렇지 않아도',
                                        'pos': '+'.join([t['pos'] for t in output[idx:idx+4]]),
                                        'pos_desc': '형용사 어간+연결 어미+보조 동사+연결 어미',
                                        'matched_items': [item for item in grammatical_items if item['번호'] == 18],
                                        'start': token['start'],
                                        'len': sum([t['len'] for t in output[idx:idx+4]]),
                                        'end': next_next_next_token['end']
                                    }
                                    # '그렇지 않아도' 부분을 병합하여 대체
                                    output = output[:idx] + [merged_token] + output[idx + 4:]
                                    idx += 1
                                    continue  # 다음 인덱스로 이동
        idx += 1
    return output

def check_item_19(output):
    idx = 0
    while idx < len(output) - 2:
        token = output[idx]
        next_token = output[idx + 1]
        next_next_token = output[idx + 2]
        if token['morpheme'] == '는' and token['pos'] == 'ETM':
            if next_token['morpheme'] == '중' and next_token['pos'] == 'NNB':
                if next_next_token['morpheme'] == '이' and next_next_token['pos'] == 'VCP':
                    # 세 토큰을 병합하여 처리
                    merged_token = {
                        'morpheme': '는 중이',
                        'pos': 'ETM+NNB+VCP',
                        'pos_desc': '관형형 전성 어미+의존 명사+긍정 지시사',
                        'matched_items': [item for item in grammatical_items if item['번호'] == 19],
                        'start': token['start'],
                        'len': sum([t['len'] for t in output[idx:idx+3]]),
                        'end': next_next_token['end']
                    }
                    output = output[:idx] + [merged_token] + output[idx + 3:]
                    idx += 1
                else:
                    idx += 1
            else:
                idx += 1
        else:
            idx += 1
    return output

def check_item_20(output):
    idx = 0
    while idx < len(output) - 3:
        token = output[idx]
        next_token = output[idx + 1]
        next_next_token = output[idx + 2]
        next_next_next_token = output[idx + 3]

        # 형태소 정규화
        normalized_morpheme = normalize_morpheme(token['morpheme'])

        # '을까', 'ㄹ까', 'ᆯ까' 형태 검사
        if normalized_morpheme in ['을까', 'ㄹ까', 'ᆯ까'] and token['pos'] == 'EC':
            if next_token['morpheme'] == '생각' and next_token['pos'] == 'NNG':
                if next_next_token['morpheme'] == '중' and next_next_token['pos'] == 'NNB':
                    if next_next_next_token['morpheme'] == '이' and next_next_next_token['pos'] == 'VCP':
                        # 네 토큰을 병합하여 처리
                        merged_token = {
                            'morpheme': token['morpheme'] + ' ' + next_token['morpheme'] + next_next_token['morpheme'] + next_next_next_token['morpheme'],
                            'pos': '+'.join([token['pos'], next_token['pos'], next_next_token['pos'], next_next_next_token['pos']]),
                            'pos_desc': '연결 어미+명사+의존 명사+긍정 지시사',
                            'matched_items': [item for item in grammatical_items if item['번호'] == 20],
                            'start': token['start'],
                            'len': sum([t['len'] for t in output[idx:idx+4]]),
                            'end': next_next_next_token['end']
                        }
                        output = output[:idx] + [merged_token] + output[idx + 4:]
                        idx += 1
                    else:
                        idx += 1
                else:
                    idx += 1
            else:
                idx += 1
        else:
            idx += 1
    return output

def check_item_21(output):
    idx = 0
    while idx < len(output) - 2:
        token = output[idx]
        next_token = output[idx + 1]
        next_next_token = output[idx + 2]

        normalized_morpheme = normalize_morpheme(next_next_token['morpheme'])

        # 'ㄹ게요', '을게요', 'ᆯ게요' 형태 검사
        if token['morpheme'] == '어' and token['pos'] == 'EC':
            if next_token['morpheme'] == '드리' and next_token['pos'] == 'VX':
                if normalized_morpheme in ['ㄹ게요', '을게요', 'ᆯ게요'] and next_next_token['pos'] == 'EF':
                    # 세 토큰을 병합하여 처리
                    merged_token = {
                        'morpheme': '어 드릴게요',
                        'pos': 'EC+VX+EF',
                        'pos_desc': '연결 어미+보조 동사+종결 어미',
                        'matched_items': [item for item in grammatical_items if item['번호'] == 21],
                        'start': token['start'],
                        'len': sum([t['len'] for t in output[idx:idx+3]]),
                        'end': next_next_token['end']
                    }
                    output = output[:idx] + [merged_token] + output[idx + 3:]
                    idx += 1
                else:
                    idx += 1
            else:
                idx += 1
        else:
            idx += 1
    return output

def check_item_23(output):
    idx = 0
    while idx < len(output) - 2:
        token = output[idx]
        next_token = output[idx + 1]
        next_next_token = output[idx + 2]
        
        # 관형형 전성어미(ETM) 체크
        if token['morpheme'] in ['은', '는', 'ㄴ', '던'] and token['pos'] == 'ETM':
            if next_token['morpheme'] == '대신' and next_token['pos'] == 'NNG':
                if next_next_token['morpheme'] == '에' and next_next_token['pos'] == 'JKB':
                    # 세 토큰을 병합하여 처리
                    merged_token = {
                        'morpheme': token['morpheme'] + next_token['morpheme'] + next_next_token['morpheme'],
                        'pos': 'ETM+NNG+JKB',
                        'pos_desc': '관형형 전성어미+일반 명사+부사격 조사',
                        'matched_items': [item for item in grammatical_items if item['번호'] == 23],
                        'start': token['start'],
                        'len': token['len'] + next_token['len'] + next_next_token['len'],
                        'end': next_next_token['end']
                    }
                    # 병합된 토큰으로 대체
                    output = output[:idx] + [merged_token] + output[idx + 3:]
                    idx += 1
                else:
                    idx += 1
            else:
                idx += 1
        else:
            idx += 1
    return output

def check_item_24(output):
    idx = 0
    while idx < len(output):
        token = output[idx]
        if token['morpheme'] == '다가' and token['pos'] == 'EC':
            # 바로 앞의 토큰이 '었'(EP)이면 제외
            if idx >= 1:
                prev_token = output[idx - 1]
                if prev_token['morpheme'] == '었' and prev_token['pos'] == 'EP':
                    idx += 1
                    continue
            # 그렇지 않으면 24번 항목으로 태깅
            token['matched_items'] = [item for item in grammatical_items if item['번호'] == 24]
        idx += 1
    return output

def check_item_25(output):
    idx = 0
    while idx < len(output) - 1:
        token = output[idx]
        normalized_morpheme = normalize_morpheme(token['morpheme'])
        
        # 패턴 1: '대요'(EF)
        if normalized_morpheme == '대요' and token['pos'] == 'EF':
            token['matched_items'] = [item for item in grammatical_items if item['번호'] == 25]
            idx += 1
            continue
        
        # 패턴 2: 'ㄴ대요'(EF)
        if normalized_morpheme in ['ㄴ대요', 'ᆫ대요'] and token['pos'] == 'EF':
            token['matched_items'] = [item for item in grammatical_items if item['번호'] == 25]
            idx += 1
            continue
        
        # 패턴 3: '는대'(EF) + '요'(JX)
        if normalized_morpheme in ['는대', 'ᄂ는대'] and token['pos'] == 'EF':
            next_token = output[idx + 1]
            if next_token['morpheme'] == '요' and next_token['pos'] == 'JX':
                # 두 토큰을 병합하여 처리
                merged_token = {
                    'morpheme': token['morpheme'] + next_token['morpheme'],
                    'pos': 'EF+JX',
                    'pos_desc': '종결 어미+보조사',
                    'matched_items': [item for item in grammatical_items if item['번호'] == 25],
                    'start': token['start'],
                    'len': token['len'] + next_token['len'],
                    'end': next_token['end']
                }
                output = output[:idx] + [merged_token] + output[idx + 2:]
                idx += 1
                continue
        idx += 1
    return output

def check_item_26(output):
    idx = 0
    while idx < len(output) - 2:
        token = output[idx]
        next_token = output[idx + 1]
        next_next_token = output[idx + 2]
        # 패턴 1: '이'(VCP) + '래'(EF) + '요'(JX)
        if token['morpheme'] == '이' and token['pos'] == 'VCP':
            if next_token['morpheme'] == '래' and next_token['pos'] == 'EF':
                if next_next_token['morpheme'] == '요' and next_next_token['pos'] == 'JX':
                    # 세 토큰을 병합하여 처리
                    merged_token = {
                        'morpheme': '이래요',
                        'pos': 'VCP+EF+JX',
                        'pos_desc': '긍정 지시사+종결 어미+보조사',
                        'matched_items': [item for item in grammatical_items if item['번호'] == 26],
                        'start': token['start'],
                        'len': token['len'] + next_token['len'] + next_next_token['len'],
                        'end': next_next_token['end']
                    }
                    output = output[:idx] + [merged_token] + output[idx + 3:]
                    idx += 1
                    continue
        # 패턴 2: '이'(VCP) + '래요'(EF)
        if token['morpheme'] == '이' and token['pos'] == 'VCP':
            if next_token['morpheme'] == '래요' and next_token['pos'] == 'EF':
                # 두 토큰을 병합하여 처리
                merged_token = {
                    'morpheme': '이래요',
                    'pos': 'VCP+EF',
                    'pos_desc': '긍정 지시사+종결 어미',
                    'matched_items': [item for item in grammatical_items if item['번호'] == 26],
                    'start': token['start'],
                        'len': token['len'] + next_token['len'],
                        'end': next_token['end']
                }
                output = output[:idx] + [merged_token] + output[idx + 2:]
                idx += 1
                continue
        idx += 1
    return output

def check_item_27(output):
    idx = 0
    while idx < len(output) - 1:
        token = output[idx]
        next_token = output[idx + 1]
        # 패턴 1: '다고요'(EF)
        if token['morpheme'] == '다고요' and token['pos'] == 'EF':
            # 뒤에 물음표(SF)가 붙는 경우 제외
            if idx + 1 < len(output) and output[idx + 1]['pos'] == 'SF' and output[idx + 1]['morpheme'] == '?':
                idx += 1
                continue
            else:
                token['matched_items'] = [item for item in grammatical_items if item['번호'] == 27]
                idx += 1
                continue
        # 패턴 2: 'ᆫ다고'(EF) + '요'(JX)
        normalized_morpheme = normalize_morpheme(token['morpheme'])
        if normalized_morpheme in ['ㄴ다고', 'ᆫ다고'] and token['pos'] == 'EF':
            if next_token['morpheme'] == '요' and next_token['pos'] == 'JX':
                # 두 토큰을 병합하여 처리
                merged_token = {
                    'morpheme': token['morpheme'] + next_token['morpheme'],
                    'pos': 'EF+JX',
                    'pos_desc': '종결 어미+보조사',
                    'matched_items': [item for item in grammatical_items if item['번호'] == 27],
                    'start': token['start'],
                    'len': token['len'] + next_token['len'],
                    'end': next_token['end']
                }
                # 물음표(SF)가 뒤에 있는 경우 제외
                if idx + 2 < len(output) and output[idx + 2]['pos'] == 'SF' and output[idx + 2]['morpheme'] == '?':
                    idx += 1
                    continue
                output = output[:idx] + [merged_token] + output[idx + 2:]
                idx += 1
                continue
        idx += 1
    return output

def check_item_28(output):
    idx = 0
    while idx < len(output) - 1:
        token = output[idx]
        next_token = output[idx + 1]
        if token['morpheme'] in ['시', '으시'] and token['pos'] == 'EP':
            normalized_morpheme = normalize_morpheme(next_token['morpheme'])
            # 'ㅂ시오'와 'ᆸ시오' 모두 비교
            if normalized_morpheme in ['ㅂ시오', 'ᆸ시오'] and next_token['pos'] == 'EF':
                # 두 토큰을 병합하여 처리
                merged_token = {
                    'morpheme': token['morpheme'] + next_token['morpheme'],
                    'pos': 'EP+EF',
                    'pos_desc': '선어말 어미+종결 어미',
                    'matched_items': [item for item in grammatical_items if item['번호'] == 28],
                    'start': token['start'],
                    'len': token['len'] + next_token['len'],
                    'end': next_token['end']
                }
                output = output[:idx] + [merged_token] + output[idx + 2:]
                idx += 1
                continue
        idx += 1
    return output

def check_item_31(output):
    idx = 0
    while idx < len(output):
        token = output[idx]
        normalized_morpheme = normalize_morpheme(token['morpheme'])
        # 패턴 1: '이'(VCP) + '라든가'(EC)
        if token['morpheme'] == '이' and token['pos'] == 'VCP':
            if idx + 1 < len(output):
                next_token = output[idx + 1]
                if next_token['morpheme'] == '라든가' and next_token['pos'] == 'EC':
                    # 두 토큰을 병합하여 처리
                    merged_token = {
                        'morpheme': '이라든가',
                        'pos': 'VCP+EC',
                        'pos_desc': '긍정 지시사+연결 어미',
                        'matched_items': [item for item in grammatical_items if item['번호'] == 31],
                        'start': token['start'],
                        'len': token['len'] + next_token['len'],
                        'end': next_token['end']
                    }
                    output = output[:idx] + [merged_token] + output[idx + 2:]
                    idx += 1
                    continue
        # 패턴 2~6: '라든가'
        if normalized_morpheme == '라든가' and token['pos'] in ['EC', 'JC', 'JX']:
            token['matched_items'] = [item for item in grammatical_items if item['번호'] == 31]
            idx += 1
            continue
        # 패턴 3~5: '이라든가'
        if normalized_morpheme == '이라든가' and token['pos'] in ['JC', 'JX']:
            token['matched_items'] = [item for item in grammatical_items if item['번호'] == 31]
            idx += 1
            continue
        idx += 1
    return output

def check_item_32(output):
    idx = 0
    while idx < len(output) - 1:
        token = output[idx]
        next_token = output[idx + 1]
        if token['morpheme'] == '거나' and token['pos'] in ['EC', 'JX']:
            if next_token['morpheme'] == '하' and next_token['pos'] == 'VV':
                # 두 토큰을 병합하여 처리
                merged_token = {
                    'morpheme': token['morpheme'] + next_token['morpheme'],
                    'pos': token['pos'] + '+' + next_token['pos'],
                    'pos_desc': '연결 어미/보조사+동사',
                    'matched_items': [item for item in grammatical_items if item['번호'] == 32],
                    'start': token['start'],
                    'len': token['len'] + next_token['len'],
                    'end': next_token['end']
                }
                output = output[:idx] + [merged_token] + output[idx + 2:]
                idx += 1
                continue
        idx += 1
    return output

def check_item_34(output):
    idx = 0
    while idx < len(output) - 1:
        token = output[idx]
        next_token = output[idx + 1]
        # 패턴 1: '척'(NNB) + '하'(XSV)
        if token['morpheme'] == '척' and token['pos'] == 'NNB':
            if next_token['morpheme'] == '하' and next_token['pos'] == 'XSV':
                # 두 토큰을 병합하여 처리
                merged_token = {
                    'morpheme': '척하',
                    'pos': 'NNB+XSV',
                    'pos_desc': '의존 명사+동사 파생 접미사',
                    'matched_items': [item for item in grammatical_items if item['번호'] == 34],
                    'start': token['start'],
                    'len': token['len'] + next_token['len'],
                    'end': next_token['end']
                }
                output = output[:idx] + [merged_token] + output[idx + 2:]
                idx += 1
                continue
        # 패턴 2: '척하'(VX)
        elif token['morpheme'] == '척하' and token['pos'] == 'VX':
            # 34번 항목으로 태깅
            token['matched_items'] = [item for item in grammatical_items if item['번호'] == 34]
        idx += 1
    return output

def check_item_36(output):
    idx = 0
    while idx < len(output) - 2:
        token1 = output[idx]
        token2 = output[idx + 1]
        token3 = output[idx + 2]
        if token1['morpheme'] == '웬만' and token1['pos'] == 'XR':
            if token2['morpheme'] == '하' and token2['pos'] == 'XSA':
                if token3['morpheme'] == '면' and token3['pos'] == 'EC':
                    # 세 토큰을 병합하여 처리
                    merged_token = {
                        'morpheme': '웬만하면',
                        'pos': '+'.join([token1['pos'], token2['pos'], token3['pos']]),
                        'pos_desc': '어근+형용사 파생 접미사+연결 어미',
                        'matched_items': [item for item in grammatical_items if item['번호'] == 36],
                        'start': token1['start'],
                        'len': token1['len'] + token2['len'] + token3['len'],
                        'end': token3['end']
                    }
                    output = output[:idx] + [merged_token] + output[idx + 3:]
                    idx += 1
                    continue
        idx += 1
    return output

def check_item_37(output):
    idx = 0
    while idx < len(output) - 1:
        token1 = output[idx]
        token2 = output[idx + 1]
        if token1['morpheme'] == '나' and token1['pos'] == 'EC':
            if token2['morpheme'] == '보' and token2['pos'] == 'VX':
                # 두 토큰을 병합하여 처리
                merged_token = {
                    'morpheme': '나보',
                    'pos': token1['pos'] + '+' + token2['pos'],
                    'pos_desc': '연결 어미+보조 용언',
                    'matched_items': [item for item in grammatical_items if item['번호'] == 37],
                    'start': token1['start'],
                    'len': token1['len'] + token2['len'],
                    'end': token2['end']
                }
                output = output[:idx] + [merged_token] + output[idx + 2:]
                idx += 1
                continue
        idx += 1
    return output

def check_item_38(output):
    idx = 0
    while idx < len(output) - 1:
        token1 = output[idx]
        token2 = output[idx + 1]
        if token1['morpheme'] == '이' and token1['pos'] == 'VCP':
            if token2['morpheme'] == '라도' and token2['pos'] == 'EC':
                # 두 토큰을 병합하여 처리
                merged_token = {
                    'morpheme': '이라도',
                    'pos': token1['pos'] + '+' + token2['pos'],
                    'pos_desc': '긍정 지시사(이다)+연결 어미',
                    'matched_items': [item for item in grammatical_items if item['번호'] == 38],
                    'start': token1['start'],
                    'len': token1['len'] + token2['len'],
                    'end': token2['end']
                }
                output = output[:idx] + [merged_token] + output[idx + 2:]
                idx += 1
                continue
        idx += 1
    return output

def check_item_39(output):
    idx = 0
    while idx < len(output) - 2:
        token1 = output[idx]
        token2 = output[idx + 1]
        token3 = output[idx + 2]
        if token1['morpheme'] == '에' and token1['pos'] == 'JKB':
            if token2['morpheme'] == '비하' and token2['pos'] == 'VV':
                if token3['morpheme'] == '면' and token3['pos'] == 'EC':
                    # 세 토큰을 병합하여 처리
                    merged_token = {
                        'morpheme': '에비하면',
                        'pos': '+'.join([token1['pos'], token2['pos'], token3['pos']]),
                        'pos_desc': '부사격 조사+동사+연결 어미',
                        'matched_items': [item for item in grammatical_items if item['번호'] == 39],
                        'start': token1['start'],
                        'len': token1['len'] + token2['len'] + token3['len'],
                        'end': token3['end']
                    }
                    output = output[:idx] + [merged_token] + output[idx + 3:]
                    idx += 1
                    continue
        idx += 1
    return output

def check_item_40(output):
    idx = 0
    while idx < len(output) - 2:
        token1 = output[idx]
        token2 = output[idx + 1]
        token3 = output[idx + 2]
        if token1['morpheme'] == '었' and token1['pos'] == 'EP':
            if token2['morpheme'] == '는데' and token2['pos'] == 'EC':
                if token3['morpheme'] == '도' and token3['pos'] == 'JX':
                    # 세 토큰을 병합하여 처리
                    merged_token = {
                        'morpheme': '었는데도',
                        'pos': '+'.join([token1['pos'], token2['pos'], token3['pos']]),
                        'pos_desc': '선어말 어미+연결 어미+보조사',
                        'matched_items': [item for item in grammatical_items if item['번호'] == 40],
                        'start': token1['start'],
                        'len': token1['len'] + token2['len'] + token3['len'],
                        'end': token3['end']
                    }
                    output = output[:idx] + [merged_token] + output[idx + 3:]
                    idx += 1
                    continue
        idx += 1
    return output

def check_item_42(output):
    idx = 0
    while idx < len(output) - 1:
        token1 = output[idx]
        token2 = output[idx + 1]
        if token1['morpheme'] in ['다고', '라고'] and token1['pos'] == 'EC':
            if token2['morpheme'] == '보' and token2['pos'] == 'VV':
                # 두 토큰을 병합하여 처리
                merged_token = {
                    'morpheme': token1['morpheme'] + '보',
                    'pos': token1['pos'] + '+' + token2['pos'],
                    'pos_desc': '연결 어미+동사',
                    'matched_items': [item for item in grammatical_items if item['번호'] == 42],
                    'start': token1['start'],
                    'len': token1['len'] + token2['len'],
                    'end': token2['end']
                }
                output = output[:idx] + [merged_token] + output[idx + 2:]
                idx += 1
                continue
        idx += 1
    return output

def check_item_43(output):
    idx = 0
    while idx < len(output) - 2:
        token1 = output[idx]
        token2 = output[idx + 1]
        token3 = output[idx + 2]
        if token1['morpheme'] == '곤' and token1['pos'] == 'EC':
            if token2['morpheme'] == '하' and token2['pos'] == 'VX':
                if token3['morpheme'] == '었' and token3['pos'] == 'EP':
                    # 세 토큰을 병합하여 처리
                    merged_token = {
                        'morpheme': '곤하었',
                        'pos': '+'.join([token1['pos'], token2['pos'], token3['pos']]),
                        'pos_desc': '연결 어미+보조 용언+선어말 어미',
                        'matched_items': [item for item in grammatical_items if item['번호'] == 43],
                        'start': token1['start'],
                        'len': sum(t['len'] for t in output[idx:idx + 3]),
                        'end': token3['end']
                    }
                    output = output[:idx] + [merged_token] + output[idx + 3:]
                    idx += 1
                    continue
        idx += 1
    return output

def check_item_44(output):
    idx = 0
    while idx < len(output) - 1:
        token = output[idx]
        next_token = output[idx + 1]
        if token['morpheme'] == '게' and token['pos'] in ['EC', 'EF']:
            if next_token['morpheme'] == '?' and next_token['pos'] == 'SF':
                # '게' 토큰을 44번 항목으로 태깅
                token['matched_items'] = [item for item in grammatical_items if item['번호'] == 44]
        idx += 1
    return output


def check_item_45(output):
    idx = 0
    while idx < len(output):
        token = output[idx]
        if token['morpheme'] in ['나', '이나'] and token['pos'] == 'JX':
            # 조건 1: 앞에 NNG, 뒤에 EC
            if idx > 0 and idx + 1 < len(output):
                prev_token = output[idx - 1]
                next_token = output[idx + 1]
                if prev_token['pos'] == 'NNG' and next_token['pos'] == 'EC':
                    token['matched_items'] = [item for item in grammatical_items if item['번호'] == 45]
                    idx += 1
                    continue
            # 조건 2: 뒤에 VV
            if idx + 1 < len(output):
                next_token = output[idx + 1]
                if next_token['pos'] == 'VV':
                    token['matched_items'] = [item for item in grammatical_items if item['번호'] == 45]
                    idx += 1
                    continue
        idx += 1
    return output

def check_item_46(output):
    idx = 0
    while idx < len(output) - 1:
        token1 = output[idx]
        token2 = output[idx + 1]
        if token1['morpheme'] in ['을', '를'] and token1['pos'] == 'JKO':
            if token2['morpheme'] == '떠나' and token2['pos'] == 'VV':
                # 두 토큰을 병합하여 처리
                merged_token = {
                    'morpheme': token1['morpheme'] + token2['morpheme'],
                    'pos': token1['pos'] + '+' + token2['pos'],
                    'pos_desc': '목적격 조사+동사',
                    'matched_items': [item for item in grammatical_items if item['번호'] == 46],
                    'start': token1['start'],
                    'len': token1['len'] + token2['len'],
                    'end': token2['end']
                }
                output = output[:idx] + [merged_token] + output[idx + 2:]
                idx += 1
                continue
        idx += 1
    return output

def check_item_48(output):
    idx = 0
    while idx < len(output) - 3:
        token1 = output[idx]
        token2 = output[idx + 1]
        token3 = output[idx + 2]
        token4 = output[idx + 3]

        # 형태소 정규화
        normalized_morpheme1 = normalize_morpheme(token1['morpheme'])
        normalized_morpheme2 = normalize_morpheme(token2['morpheme'])
        normalized_morpheme3 = normalize_morpheme(token3['morpheme'])
        normalized_morpheme4 = normalize_morpheme(token4['morpheme'])

        # '을', 'ㄹ', 'ᆯ'(ETM) + '수'(NNB) + '밖에'(JX) + '없'(VA) 패턴
        if normalized_morpheme1 in ['을', 'ㄹ', 'ᆯ'] and token1['pos'] == 'ETM':
            if normalized_morpheme2 == '수' and token2['pos'] == 'NNB':
                if normalized_morpheme3 == '밖에' and token3['pos'] == 'JX':
                    if normalized_morpheme4 == '없' and token4['pos'] == 'VA':
                        # 네 토큰을 병합하여 처리
                        merged_token = {
                            'morpheme': ''.join([t['morpheme'] for t in [token1, token2, token3, token4]]),
                            'pos': '+'.join([t['pos'] for t in [token1, token2, token3, token4]]),
                            'pos_desc': 'ETM+NNB+JX+VA',
                            'matched_items': [item for item in grammatical_items if item['번호'] == 48],
                            'start': token1['start'],
                            'len': sum([t['len'] for t in [token1, token2, token3, token4]]),
                            'end': token4['end']
                        }
                        output = output[:idx] + [merged_token] + output[idx + 4:]
                        idx += 1
                        continue
        idx += 1
    return output




def check_item_49(output):
    idx = 0
    while idx < len(output) - 1:
        token1 = output[idx]
        token2 = output[idx + 1]

        # 형태소 정규화
        morpheme1 = normalize_morpheme(token1['morpheme'])
        morpheme2 = normalize_morpheme(token2['morpheme'])

        # '었/았/였'(EP) + '더라면'(EC) 패턴
        if morpheme1 in ['었', '았', '였'] and token1['pos'] == 'EP':
            if morpheme2 == '더라면' and token2['pos'] == 'EC':
                # 문장 내에서 '터'(NNB) + '이'(VCP) + 'ㄴ데'(EF)가 있는지 확인
                idx_search = idx + 2
                while idx_search < len(output) - 2:
                    token3 = output[idx_search]
                    token4 = output[idx_search + 1]
                    token5 = output[idx_search + 2]

                    morpheme3 = normalize_morpheme(token3['morpheme'])
                    morpheme4 = normalize_morpheme(token4['morpheme'])
                    morpheme5 = normalize_morpheme(token5['morpheme'])

                    if morpheme3 == '터' and token3['pos'] == 'NNB':
                        if morpheme4 == '이' and token4['pos'] == 'VCP':
                            if morpheme5 in ['ㄴ데', 'ᆫ데'] and token5['pos'] == 'EF':
                                # '었더라면'과 '터인데'를 각각 병합하여 처리
                                merged_token1 = {
                                    'morpheme': token1['morpheme'] + token2['morpheme'],
                                    'pos': token1['pos'] + '+' + token2['pos'],
                                    'pos_desc': 'EP+EC',
                                    'matched_items': [item for item in grammatical_items if item['번호'] == 49],
                                    'start': token1['start'],
                                    'len': token1['len'] + token2['len'],
                                    'end': token2['end']
                                }
                                merged_token2 = {
                                    'morpheme': token3['morpheme'] + token4['morpheme'] + token5['morpheme'],
                                    'pos': '+'.join([token3['pos'], token4['pos'], token5['pos']]),
                                    'pos_desc': 'NNB+VCP+EF',
                                    'matched_items': [item for item in grammatical_items if item['번호'] == 49],
                                    'start': token3['start'],
                                    'len': token3['len'] + token4['len'] + token5['len'],
                                    'end': token5['end']
                                }
                                # 해당 토큰들을 병합하고, idx를 갱신
                                output = output[:idx] + [merged_token1] + output[idx + 2:idx_search] + [merged_token2] + output[idx_search + 3:]
                                idx = idx_search + 1
                                break
                    idx_search += 1
        idx += 1
    return output


def check_item_50(output):
    idx = 0
    while idx < len(output) - 2:
        token1 = output[idx]
        token2 = output[idx + 1]
        token3 = output[idx + 2]
        if token1['morpheme'] in ['을', 'ㄹ'] and token1['pos'] == 'ETM':
            if token2['morpheme'] == '바' and token2['pos'] == 'NNB':
                if token3['morpheme'] == '에' and token3['pos'] == 'JKB':
                    # 세 토큰을 병합하여 처리
                    merged_token = {
                        'morpheme': ''.join([t['morpheme'] for t in output[idx:idx + 3]]),
                        'pos': '+'.join([t['pos'] for t in output[idx:idx + 3]]),
                        'pos_desc': '관형형 전성 어미+의존 명사+부사격 조사',
                        'matched_items': [item for item in grammatical_items if item['번호'] == 50],
                        'start': token1['start'],
                        'len': sum([t['len'] for t in output[idx:idx + 3]]),
                        'end': token3['end']
                    }
                    output = output[:idx] + [merged_token] + output[idx + 3:]
                    idx += 1
                    continue
        idx += 1
    return output
