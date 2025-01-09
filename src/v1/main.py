import os
import json
from .utils.kiwi_analyzer import KiwiAnalyzer
from .utils.gpt_helper import get_correct_tag
# from .utils.check_items import *
import asyncio
import re
import ast
import openai
### 캐쉬 빌드
# GPT 캐시를 위한 글로벌 딕셔너리
gpt_cache = {}

base_dir = os.path.dirname(os.path.abspath(__file__))
resources_dir = os.path.join(base_dir, 'resources')
CACHE_FILE_PATH = os.path.join(resources_dir, 'gpt_cache.json')

# 캐시 초기화
def load_cache():
    if os.path.exists(CACHE_FILE_PATH):
        try:
            with open(CACHE_FILE_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            # JSONDecodeError 발생 시 빈 딕셔너리 반환
            return {}
    else:
        return {}

def save_cache(cache):
    with open(CACHE_FILE_PATH, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=4)
        
gpt_cache = load_cache()
###

# 리소스 로드
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

# 함수 내에서 동기적으로 호출
def chatgpt(text, matched_items, pna_token, now_token):
    response = openai.ChatCompletion.create(
        model="gpt-4o", #gpt-4 ,gpt-4o-mini , gpt-4o, gpt-3.5-turbo
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
            matched_items의 번호가 0번인 경우 nlp모델이 분류한 결과야 이게 맞을 수 있는데 나머지 번호가 틀렸다고 판단될 경우 0번으로 알려줘
            그렇지 않은 경우 반드시 matched_items의 번호 중에서의 숫자만 알려줘.
            반드시 설명하지말고 숫자만 알려줘.
            """
        }],
        stream=False,  # 스트리밍 비활성화
    )

    # 응답 처리
    full_text = str(response['choices'][0]['message']['content'])
    print("====GPT answer====", full_text)

    return full_text

# Kiwi 형태소 분석기
kiwi_analyzer = KiwiAnalyzer()
import unicodedata

#문장을 끊어서 판단
def split_sentences(output): 
    sentences = []
    sentence = []
    for token in output: 
        sentence.append(token)
        if token['pos'] in ['SF']: # 문장 구분: 종결 어미(EF)와 종결 부호(SF)를 기준으로 문장을 분리 # @@ 바꾸어야 할 지도.
            sentences.append(sentence)
            sentence = []
    # 마지막 문장이 EF나 SF로 끝나지 않는 경우 처리
    if sentence:
        sentences.append(sentence)
    return sentences


def normalize_morpheme(morpheme):
    # 유니코드 정규화를 통해 결합 문자 처리
    return unicodedata.normalize('NFC', morpheme)


def remove_ep(tokens):
    # EP를 제거하여 핵심 실질 형태만 남김
    return [(t['morpheme'], t['pos']) for t in tokens if t['pos']!='EP']

def check_front_pattern_basic(fp):
    # fp는 EP 제거된 튜플 리스트 [(morph,pos),...]
    # 패턴:
    # (V*) : length=1, pos.startswith('V')
    # (NNG/MAG+XSV or XSA) : length=2, 첫토큰 NNG/MAG/XR, 두 번째 XSV/XSA
    # (N*+VCP) : length=2, 첫토큰 N*, 두번째 VCP
    # (V*+EC+VX): length=3, [V*,EC,VX]
    # (XR+(XSV/XSA)+EC+VX): length=4, [XR,XSV/XSA,EC,VX]
    l = len(fp)
    if l==1:
        # (V*)
        return fp[0][1].startswith('V')
    if l==2:
        # (NNG/MAG/XR+XSV/XSA) or (N*+VCP)
        if fp[0][1] in ['NNG','MAG','XR'] and fp[1][1] in ['XSV','XSA']:
            return True
        if fp[0][1].startswith('N') and fp[1][1]=='VCP':
            return True
    if l==3:
        # (V*+EC+VX)
        return fp[0][1].startswith('V') and fp[1][1]=='EC' and fp[2][1]=='VX'
    if l==4:
        # (XR+(XSV/XSA)+EC+VX)
        return fp[0][1]=='XR' and fp[1][1] in ['XSV','XSA'] and fp[2][1]=='EC' and fp[3][1]=='VX'
    return False

def normalize_morpheme(morpheme):
    return unicodedata.normalize('NFC', morpheme)

def remove_ep_ec_vx(tokens):
    result = []
    for t in tokens:
        mm = t['morpheme']
        pp = t['pos']
        if pp not in ['EP','EC','VX']:
            result.append((mm, pp))
    return result

def merge_no_space_tokens_both_sides(tokens):
    """
    tokens: [{'morpheme':..., 'pos':..., 'pos_desc':..., 'matched_items':..., 'start':..., 'len':..., 'end':...}, ...]

    병합 조건:
    1) 특정 번호의 matched_items를 가진 토큰끼리만 병합 (merge_item_numbers)
    2) 두 토큰 사이 공백 없이 이어지거나(start==end), 시작 위치가 같거나, 범위 일부 겹치면 병합
    3) 병합할 부분이 남아있는 한 계속 병합 수행

    병합 허용 문법 항목 번호:
    {10, 34, 37, 40, 41, 42, 43, 44, 46, 47, 48, 49, 50}
    """

    merge_item_numbers = {1, 4, 5, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 32, 34, 37, 40, 41, 42, 43, 44, 47, 48, 49, 50}

    def has_merge_items(t):
        for mi in t['matched_items']:
            if mi['번호'] in merge_item_numbers:
                return True
        return False

    # 병합이 발생하지 않을 때까지 반복
    merged_once = True
    while merged_once:
        merged_once = False
        merged = []
        i = 0
        while i < len(tokens):
            current = tokens[i].copy()
            j = i + 1
            while j < len(tokens):
                next_t = tokens[j]
                # 두 토큰 중 하나라도 병합 허용 번호를 포함해야 함
                if not (has_merge_items(current) or has_merge_items(next_t)):
                    break

                # 위치 기반 병합 조건 검사
                if (current['end'] == next_t['start']) or \
                   (current['start'] == next_t['start']) or \
                   (current['start'] <= next_t['start'] < current['end']):

                    # 병합
                    current['morpheme'] += next_t['morpheme']
                    current['pos'] = current['pos'] + '+' + next_t['pos']
                    current['pos_desc'] = current['pos_desc'] + ' ' + next_t['pos_desc']
                    current['matched_items'].extend(next_t['matched_items'])

                    if next_t['end'] > current['end']:
                        current['end'] = next_t['end']
                    current['len'] = current['end'] - current['start']

                    j += 1
                    merged_once = True  # 병합 발생 표시
                else:
                    break

            merged.append(current)
            i = j
        tokens = merged

    return tokens

def check_item_1(output):
    idx = 0
    while idx < len(output):
        patterns = [
            # (N*)+이(VCP)+라고(EC)+하(VV)+(EF/EC)
            {'len':5, 'cond': lambda t: t[0]['pos'].startswith('N') and t[1]['morpheme'] == '이' and t[1]['pos'] == 'VCP'
                                    and t[2]['morpheme'] == '라고' and t[2]['pos'] == 'EC'
                                    and t[3]['pos'].startswith('V') and t[4]['pos'] in ['EF','EC'],
             'type':'N_i라고_하'},
            # (N*)+이(VCP)+라고(EC)+하(VV)+(EP)+(EF)
            {'len':6, 'cond': lambda t: t[0]['pos'].startswith('N') and t[1]['morpheme'] == '이' and t[1]['pos'] == 'VCP'
                                    and t[2]['morpheme'] == '라고' and t[2]['pos'] == 'EC'
                                    and t[3]['pos'].startswith('V') and t[4]['pos'] == 'EP' and t[5]['pos'] == 'EF',
             'type':'N_i라고_하_ep_ef'},
            # 아니(VCN)+라고(EC)+하(VV)+(EF/EC)
            {'len':4, 'cond': lambda t: t[0]['morpheme'] == '아니' and t[0]['pos'] == 'VCN'
                                    and t[1]['morpheme'] == '라고' and t[1]['pos'] == 'EC'
                                    and t[2]['pos'].startswith('V')
                                    and t[3]['pos'] in ['EF','EC'],
             'type':'아니_라고_하'},
            # 아니(VCN)+라고(EC)+하(VV)+(EP)+(EF)
            {'len':5, 'cond': lambda t: t[0]['morpheme'] == '아니' and t[0]['pos'] == 'VCN'
                                    and t[1]['morpheme'] == '라고' and t[1]['pos'] == 'EC'
                                    and t[2]['pos'].startswith('V') and t[3]['pos'] == 'EP' and t[4]['pos'] == 'EF',
             'type':'아니_라고_하_ep_ef'},
            # 아니(VCN)+라고(EC)+주장(NNG)+하(XSV)+(EF/EC)
            {'len':5, 'cond': lambda t: t[0]['morpheme'] == '아니' and t[0]['pos'] == 'VCN'
                                    and t[1]['morpheme'] == '라고' and t[1]['pos'] == 'EC'
                                    and t[2]['morpheme'] == '주장' and t[2]['pos'] == 'NNG'
                                    and t[3]['pos'] == 'XSV'
                                    and t[4]['pos'] in ['EF','EC'],
             'type':'아니_라고_주장_하'},
            # 아니(VCN)+라고(EC)+주장(NNG)+하(XSV)+(EP)+(EF)
            {'len':6, 'cond': lambda t: t[0]['morpheme'] == '아니' and t[0]['pos'] == 'VCN'
                                    and t[1]['morpheme'] == '라고' and t[1]['pos'] == 'EC'
                                    and t[2]['morpheme'] == '주장' and t[2]['pos'] == 'NNG'
                                    and t[3]['pos'] == 'XSV'
                                    and t[4]['pos'] == 'EP' and t[5]['pos'] == 'EF',
             'type':'아니_라고_주장_하_ep_ef'}
        ]

        matched = False
        for pattern in patterns:
            plen = pattern['len']
            if idx + plen <= len(output):
                segment = output[idx:idx+plen]
                if pattern['cond'](segment):
                    pattern_type = pattern['type']

                    # 명사 + 이(VCP) 패턴인 경우와 아니(VCN) 패턴인 경우를 구분
                    # '이'(VCP)와 '라고'(EC)의 start 비교:
                    # 이(VCP) 토큰: segment[1] (N_i라고_하 계열)
                    # 아니 패턴의 경우 이(VCP) 없음 -> 무조건 '라고'
                    
                    if pattern_type in ['N_i라고_하', 'N_i라고_하_ep_ef']:
                        noun_token = segment[0]
                        i_token = segment[1]  # 이(VCP)
                        라고_token = segment[2] # 라고(EC)

                        # 이(VCP)와 라고(EC)의 start 비교
                        if i_token['start'] == 라고_token['start']:
                            morph_form = '라고'
                        else:
                            morph_form = '이라고'
                        
                        # final_morpheme 구성:
                        # noun_token + morph_form + 나머지 (하(V...) + EF/EC 등)
                        final_morpheme = noun_token['morpheme'] + morph_form + ''.join(t['morpheme'] for t in segment[3:])
                    else:
                        # 아니 패턴인 경우 이(VCP) 없음 -> 항상 '라고'
                        # 아니 + 라고(EC) + ... 이어붙이기
                        final_morpheme = segment[0]['morpheme'] + '라고' + ''.join(t['morpheme'] for t in segment[2:])
                    
                    merged_token = {
                        'morpheme': final_morpheme,
                        'pos': '+'.join(t['pos'] for t in segment),
                        'pos_desc': '문법 항목 1 해당 패턴',
                        'matched_items': [item for item in grammatical_items if item['번호'] == 1],
                        'start': segment[0]['start'],
                        'len': sum(t['len'] for t in segment),
                        'end': segment[-1]['end']
                    }

                    output = output[:idx] + [merged_token] + output[idx + plen:]
                    idx += 1
                    matched = True
                    break
        if not matched:
            idx += 1
    return output

def check_item_2(output): # 있어요
    idx = 0
    while idx < len(output) - 1:
        token = output[idx]
        next_token = output[idx + 1]
        if token['morpheme'] == '있' and (token['pos'] == 'VA' or token['pos'] =='VV'):
            if next_token['morpheme'] == '어요' and next_token['pos'] in ['EF','EC']:
                # '있' + '어요'를 병합하여 '있어요'로 만듦
                merged_token = {
                    'morpheme': '있어요',
                    'pos': 'VV or VA +EF',
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

def check_item_4(output):
    idx = 0
    while idx < len(output) - 1:
        token1 = output[idx]
        token2 = output[idx + 1]
        # (N*) + '에'(JKB) 형태에서 N*이 place_nouns에 있으면 4번
        if token2['morpheme'] == '에' and token2['pos'] == 'JKB':
            if token1['pos'].startswith('N') and token1['morpheme'] in place_nouns:
                merged_token = {
                    'morpheme': token1['morpheme'] + token2['morpheme'],
                    'pos': token1['pos'] + '+' + token2['pos'],
                    'pos_desc': '장소or방향 명사 + 에(부사격 조사)',
                    'matched_items': [item for item in grammatical_items if item['번호'] == 4],
                    'start': token1['start'],
                    'len': token1['len'] + token2['len'],
                    'end': token2['end']
                }
                output = output[:idx] + [merged_token] + output[idx+2:]
                idx += 1
                continue
        idx += 1
    return output

def check_item_5(output):
    idx = 0
    while idx < len(output) - 2:
        # 최대 6 토큰까지 확인 필요 (가장 긴 패턴)
        # 패턴별 길이가 다르므로, 가장 긴 패턴(6토큰)을 기준으로 검사 후 실패 시 짧은 패턴도 검사
        # 단, 여기서는 간단히 cond로 한 번에 처리하는 대신 여러 if로 분기할 수 있음
        # 여기서는 예시로 EP "았/었/였"을 ep_morph 리스트로 정의

        ep_morph = ['았','었','였']
        # 패턴 매칭 시 segment를 덩어리로 가져와서 조건 검사
        # 편의상 모든 패턴을 하나씩 if로 확인 (실제 구현 시 정규화나 별도 cond 함수 활용 가능)
        
        matched = False
        for length in [6,5,4,3]: # 길이가 긴 패턴부터 시도
            if idx + length <= len(output):
                segment = output[idx:idx+length]
                
                # 패턴 검사를 간결히 하기 위해 segment별로 pos와 morph 추출
                morphs = [t['morpheme'] for t in segment]
                poses = [t['pos'] for t in segment]

                # 패턴 1: (VV/VA) + "았/었/였"(EP) + "어요"(EF)
                # 최소 3토큰
                if length >= 3:
                    # 예: [VV/VA, EP(았/었/였), EF(어요)]
                    if poses[0].startswith('V') and poses[1] == 'EP' and poses[2] == 'EF':
                        if any(m in morphs[1] for m in ep_morph) and morphs[2] == '어요':
                            # 패턴 1 매칭
                            matched = True

                # 패턴 2: NNG + XSV + "았/었/였"(EP) + "어요"(EF)
                if length >= 4 and not matched:
                    # [NNG, XSV, EP(았/었/였), EF(어요)]
                    if poses[0] in ['NNG','MAG','XR'] and poses[1] == 'XSV' and poses[2] == 'EP' and poses[3] == 'EF':
                        if any(m in morphs[2] for m in ep_morph) and morphs[3] == '어요':
                            matched = True

                # 패턴 3: (N*) + (VCP) + "었"(EP) + "어요"(EF)
                if length >= 4 and not matched:
                    # [N*, VCP, EP(었), EF(어요)]
                    if poses[0].startswith('N') and poses[1] == 'VCP' and poses[2] == 'EP' and poses[3] == 'EF':
                        # EP는 "었"인지 확인
                        if '었' in morphs[2] and morphs[3] == '어요':
                            matched = True

                # 패턴 4: (VV/VA) + (EP) + "았/었/였"(EP) + "어요"(EF)
                if length >= 4 and not matched:
                    # 예: [VV/VA, EP, EP(았/었/였), EF(어요)]
                    # EP가 연속 2개 올 수 있으므로 poses[1], poses[2] 둘 다 EP인지 확인
                    if poses[0].startswith('V') and poses[1] == 'EP' and poses[2] == 'EP' and poses[3] == 'EF':
                        # 두 번째 EP가 "았/었/였" 포함하는지 확인
                        if any(m in morphs[2] for m in ep_morph) and morphs[3] == '어요':
                            matched = True

                # 패턴 5: NNG + XSV + (EP) + "았/었/였"(EP) + "어요"(EF)
                if length >= 5 and not matched:
                    # [NNG, XSV, EP, EP(았/었/였), EF(어요)] 형태인지 확인
                    # EP가 2개 연속일 가능성
                    # poses: NNG, XSV, EP, EP, EF
                    if poses[0] in ['NNG','MAG','XR'] and poses[1] == 'XSV' and poses[2] == 'EP' and poses[3] == 'EP' and poses[4] == 'EF':
                        if any(m in morphs[3] for m in ep_morph) and morphs[4] == '어요':
                            matched = True

                # 패턴 6: (N*) + (VCP) + (EP) + "었"(EP) + "어요"(EF)
                if length >= 5 and not matched:
                    # [N*, VCP, EP, EP(었), EF(어요)]
                    # 여기서도 EP가 2번 나옴, 두 번째 EP가 "었" 포함하는지 확인
                    if poses[0].startswith('N') and poses[1] == 'VCP' and poses[2] == 'EP' and poses[3] == 'EP' and poses[4] == 'EF':
                        # EP(3번 토큰)에 '었'이 있는지 확인
                        if '었' in morphs[3] and morphs[4] == '어요':
                            matched = True

                if matched:
                    # 패턴 매칭 성공 -> 병합
                    merged_token = {
                        'morpheme': ''.join(morphs),
                        'pos': '+'.join(poses),
                        'pos_desc': '과거+해요체 형태',
                        'matched_items': [item for item in grammatical_items if item['번호'] == 5],
                        'start': segment[0]['start'],
                        'len': sum(t['len'] for t in segment),
                        'end': segment[-1]['end']
                    }
                    output = output[:idx] + [merged_token] + output[idx + length:]
                    idx += 1
                    break
        else:
            # 패턴에 맞지 않으면 다음으로
            idx += 1
    return output

def check_item_6(output):
    idx = 0
    while idx < len(output) - 1:
        token1 = output[idx]
        token2 = output[idx + 1]

        # 형태소 정규화
        morpheme1 = normalize_morpheme(token1['morpheme'])
        morpheme2 = normalize_morpheme(token2['morpheme'])

        # 패턴: '주'(V*) + '세요'(EF)
        if morpheme1 == '주' and token1['pos'].startswith('V'):
            if morpheme2 == '세요' and token2['pos'] == 'EF':
                # 제외 조건: 바로 앞에 (V* 또는 XSV) + EC
                exclude = False
                if idx >= 2:
                    token_prev_prev = output[idx - 2]
                    token_prev = output[idx - 1]
                    if token_prev['pos'] == 'EC' and (token_prev_prev['pos'].startswith('V') or token_prev_prev['pos'] == 'XSV'):
                        exclude = True
                elif idx >= 1:
                    token_prev = output[idx - 1]
                    if token_prev['pos'] == 'EC':
                        exclude = True

                if exclude:
                    idx += 1
                    continue

                # 두 토큰을 병합하여 처리
                merged_token = {
                    'morpheme': token1['morpheme'] + token2['morpheme'],
                    'pos': token1['pos'] + '+' + token2['pos'],
                    'pos_desc': '보조용언/동사+종결어미',
                    'matched_items': [item for item in grammatical_items if item['번호'] == 6],
                    'start': token1['start'],
                    'len': token1['len'] + token2['len'],
                    'end': token2['end']
                }
                output = output[:idx] + [merged_token] + output[idx + 2:]
                idx += 1
                continue
        idx += 1
    return output

def check_item_7(output):
    idx = 0
    while idx < len(output):
        matched = False
        # 최대 길이: EP+EF까지 고려하면 최대 6토큰 (N*+VCP+고+싶+EP+EF)
        # 최소 길이: (V*)+고+싶+EF or EC => 4토큰
        # 패턴 길이 다양: 4~6 토큰
        
        for length in [6,5,4]: 
            # segment 추출
            if idx + length <= len(output):
                segment = output[idx:idx+length]
                morphs = [t['morpheme'] for t in segment]
                poses = [t['pos'] for t in segment]

                # 고(EC)+싶(VX) 위치 확인
                # 고(EC)와 싶(VX)가 연속적으로 나와야 함
                # 고_idx, 싶_idx를 찾음
                if '고' in morphs and '싶' in morphs:
                    try:
                        고_idx = morphs.index('고')
                        싶_idx = morphs.index('싶')
                    except:
                        # 없으면 다음 패턴
                        continue

                    # 고와 싶이 연속적이고 pos 조건 확인
                    if 고_idx+1 == 싶_idx and poses[고_idx] == 'EC' and poses[싶_idx].startswith('V'):
                        # 고싶 패턴 핵심 확인됨
                        # 앞쪽 조건:
                        # 패턴 1: (V*) + 고 + 싶 + (EF/EC)
                        # 패턴 2: (NNG or MAG)+(XSV)+고+싶+(EF/EC)
                        # 패턴 3: (V*)+고+싶+(EP)+(EF)
                        # 패턴 4: (NNG or MAG)+(XSV)+고+싶+(EP)+(EF)
                        # 패턴 5: (N*)+(VCP)+고+싶+(EF/EC)
                        # 패턴 6: (N*)+(VCP)+고+싶+(EP)+(EF)

                        # 뒤쪽 마지막 형태가 EF/EC 혹은 EP+EF인지 판별
                        # 마지막 1토큰이 EF나 EC이면 패턴 1,2,5
                        # 마지막 2토큰이 EP+EF이면 패턴 3,4,6

                        last_poses = poses[-2:] # 마지막 두 pos
                        last_pos = poses[-1]
                        
                        # EF/EC로 끝나는 경우 (길이 4~5)
                        # EP+EF로 끝나는 경우 (길이 5~6)
                        
                        # 고싶 기준으로 앞 토큰 패턴 확인:
                        # 고_idx, 싶_idx 기준으로 앞 토큰들 품사 검사

                        # 고(EC) 인덱스, 싶(VX) 인덱스 기준 패턴 파악:
                        # segment 구조 예시 (길이4): [X, 고(EC), 싶(VX), EF/EC]
                        # 패턴별 토큰 수: 최소4( V* 고 싶 EF ), 최대6( N* VCP 고 싶 EP EF )
                        
                        # 공통: 고_idx와 싶_idx 확인됐음.
                        # 패턴별 앞 구조:
                        # 1: (V*) 고 싶 EF/EC -> segment 예: [V*,고,싶,EF/EC]
                        # 2: (NNG/MAG)+(XSV) 고 싶 EF/EC -> [NNG/MAG, XSV, 고, 싶, EF/EC]
                        # 3: (V*) 고 싶 EP EF -> [V*, 고, 싶, EP, EF]
                        # 4: (NNG/MAG)+(XSV) 고 싶 EP EF -> [NNG/MAG, XSV, 고, 싶, EP, EF]
                        # 5: (N*)+(VCP) 고 싶 EF/EC -> [N*, VCP, 고, 싶, EF/EC]
                        # 6: (N*)+(VCP) 고 싶 EP EF -> [N*, VCP, 고, 싶, EP, EF]

                        # 고_idx와 싶_idx는 연속이므로 길이로 패턴 식별:
                        # length=4: 가능: (V*)고싶(EF/EC)
                        # length=5: 가능: (NNG/MAG+XSV)고싶(EF/EC) or (V*)고싶(EP+EF) or (N*+VCP)고싶(EF/EC)
                        # length=6: (NNG/MAG+XSV)고싶(EP+EF) or (N*+VCP)고싶(EP+EF)

                        # 패턴 매칭 로직
                        # 끝이 EF/EC만 있으면: last_pos in [EF, EC]
                        # 끝이 EP+EF이면: last_poses = [EP, EF]

                        is_ep_ef = (length >= 5 and poses[-2] == 'EP' and poses[-1] == 'EF')
                        is_ef_ec_only = not is_ep_ef and (poses[-1] in ['EF','EC'])

                        # 앞부분 검사
                        # 고_idx,싶_idx 기준: 고_idx+1=싶_idx
                        # 고_idx,싶_idx를 이용해 패턴 판단보다는 length와 pos조건으로 구분
                        
                        # length=4 -> 패턴1 or 3 or 5 중 EP+EF 없으니 EP+EF 패턴 불가 => 패턴1 or 패턴5
                        # 하지만 EP+EF 없는 경우(길이4), EP없고 마지막 EF나 EC만.
                        # length=4 예: [X,고,싶,EF/EC]
                        # 여기서 X가 V*면 패턴1, N*+VCP면 패턴5
                        # N*+VCP+고+싶+EF/EC=5토큰 필요하므로 4토큰에는 N*+VCP 패턴 불가 
                        # 4토큰이면 앞에 1토큰: (V*),고,싶,EF/EC => 패턴1이 성립
                        
                        # length=4:
                        # [0:?, 1:고,2:싶,3:EF/EC]
                        # 고_idx=1,싶_idx=2
                        # 이 경우 (V*)여야 패턴1
                        if length == 4:
                            # segment 구조: [X,고,싶,EF/EC]
                            # X가 V*
                            if poses[0].startswith('V') and is_ef_ec_only:
                                matched = True

                        # length=5:
                        # 가능한 패턴: 2,3,5
                        # 2: (NNG/MAG)+(XSV)+고+싶+EF/EC
                        # 3: (V*)+고+싶+EP+EF
                        # 5: (N*)+(VCP)+고+싶+EF/EC
                        # is_ep_ef면 EP+EF 있으니 패턴2(EP+EF 아님), 패턴5(EP+EF아님) 제외, 패턴3 가능
                        # EP+EF아니면 2,5 중 하나
                        
                        if length == 5:
                            # [?, ?, 고, 싶, (EF/EC or EP+EF)]
                            # EP+EF면 last two pos = [EP, EF]
                            if is_ep_ef:
                                # 패턴3: (V*) 고 싶 EP EF
                                # segment[0] must be V*
                                # segment = [V*, 고, 싶, EP, EF]
                                # poses: [V*, EC, VX, EP, EF]
                                if poses[0].startswith('V'):
                                    matched = True
                            else:
                                # EF/EC만 있는경우 패턴2나5
                                # 패턴2: (NNG/MAG)+(XSV)+고+싶+(EF/EC)
                                # 패턴5: (N*)+(VCP)+고+싶+(EF/EC)
                                # 고_idx=?
                                # 길이5에서 고_idx,싶_idx 찾음 ->고_idx,싶_idx 연속
                                # segment 예: [X,X,고,싶,EF/EC]
                                # pattern2: X=NNG/MAG, X=XSV
                                # pattern5: X=N*,X=VCP
                                # 고_idx가 2, 싶_idx=3이라 가정:
                                # segment[0], segment[1]확인
                                if poses[1] == 'XSV' and (poses[0] in ['NNG','MAG','XR','XSA']):
                                    # 패턴2
                                    matched = True
                                elif poses[1] == 'VCP' and poses[0].startswith('N'):
                                    # 패턴5
                                    matched = True

                        # length=6:
                        # 가능한 패턴:4,6
                        # 4:(NNG/MAG)+(XSV)+고+싶+EP+EF
                        # 6:(N*)+(VCP)+고+싶+EP+EF
                        # is_ep_ef 반드시 True (EP+EF 끝나니까)
                        # segment: [...,고,싶,EP,EF]
                        # pattern4: (NNG/MAG, XSV, 고, 싶, EP, EF)
                        # pattern6: (N*, VCP, 고, 싶, EP, EF)
                        if length == 6:
                            if is_ep_ef:
                                # check first two tokens
                                # pattern4: (NNG/MAG, XSV)
                                # pattern6: (N*, VCP)
                                if poses[0] in ['NNG','MAG','XR','XSA'] and poses[1] == 'XSV':
                                    matched = True
                                elif poses[0].startswith('N') and poses[1] == 'VCP':
                                    matched = True

                if matched:
                    merged_token = {
                        'morpheme': ''.join(morphs),
                        'pos': '+'.join(poses),
                        'pos_desc': '고싶 패턴 (7번)',
                        'matched_items': [item for item in grammatical_items if item['번호'] == 7],
                        'start': segment[0]['start'],
                        'len': sum(t['len'] for t in segment),
                        'end': segment[-1]['end']
                    }
                    output = output[:idx] + [merged_token] + output[idx + length:]
                    idx += 1
                    break
        if not matched:
            idx += 1
    return output

def check_item_8(output):
    # 8번 패턴 인식:
    # 목표: 어딘가에 (V* 또는 (NNG/MAG+XSV)) + ㄹ/을(ETM) + 거(NNB) + 이(VCP) + (EF)이 순서대로 존재
    # 중간에 다른 토큰(조사 등) 있어도 패턴 성립.
    # 구현 방법:
    # (1) 문장 끝까지 순회, EF 토큰 찾기
    # (2) EF 이전에 이(VCP), 그 이전에 거(NNB), 그 이전에 ㄹ/을(ETM) 찾기
    # (3) ㄹ/을(ETM)보다 앞에서 (V*) 또는 (NNG/MAG+XSV) 구조 찾기
    # 찾으면 그 구간 모두 병합 후 8번 태깅.

    idx=0
    while idx < len(output):
        matched=False
        # EF 위치 찾기
        # 한 문장 내 여러 EF가 있을 수 있으니 EF 만나면 뒤로 거슬러 올라가며 패턴 확인
        if output[idx]['pos']=='EF':
            # EF 토큰 = output[idx]
            # VCP '이', NNB '거', ETM 'ㄹ/을', 그 앞 V* 또는 (NNG/MAG+XSV)
            # 뒤에서 앞으로 탐색
            ef_idx = idx
            # 이(VCP) 찾기
            i_idx = None
            for k in range(ef_idx-1, -1, -1):
                if output[k]['pos']=='VCP' and output[k]['morpheme']=='이':
                    i_idx = k
                    break
            if i_idx is not None:
                # 거(NNB) 찾기: i_idx 앞에서
                ge_idx=None
                for k in range(i_idx-1, -1, -1):
                    if output[k]['pos']=='NNB' and output[k]['morpheme'] in ['거','것']:
                        ge_idx=k
                        break
                if ge_idx is not None:
                    # ETM ㄹ/을 찾기
                    etm_idx=None
                    for k in range(ge_idx-1, -1, -1):
                        if output[k]['pos']=='ETM':
                            nm=output[k]['morpheme']
                            normalized = normalize_morpheme(nm)
                            if normalized in ['ㄹ','을','ᆯ']:
                                etm_idx=k
                                break
                    if etm_idx is not None:
                        # 이제 etm_idx 앞 부분이 (V*) 또는 (NNG/MAG+XSV)
                        # (V*): etm_idx 바로 앞에 V* 토큰이 1개이상 있어도 결국 V* 어간이 마지막에 있어야함
                        # 또는 (NNG/MAG+XSV) 구조:
                        # 간단히 etm_idx 앞쪽 토큰 중 마지막으로 접근가능한 candidates:
                        # 조건1: V* 하나라도 있으면 V*패턴 성립
                        # 조건2: NNG/MAG+XSV 연속 찾기
                        # 뒤에서 etm_idx-1 위치부터 앞으로 검사
                        front_ok=False
                        # etm_idx 앞 인덱스: etm_idx-1
                        # NNG/MAG+XSV 패턴: 최소2토큰 필요
                        # V* 패턴: etm_idx앞 한토큰이라도 V*면 가능
                        
                        # 전략:
                        # etm_idx앞 토큰들 중 끝에서부터 V*이나 (NNG/MAG+XSV)패턴 발견하면 OK
                        # 우선 NNG/MAG+XSV 패턴 먼저 찾고 없으면 V*패턴
                        
                        # NNG/MAG+XSV:
                        if etm_idx>=2:
                            if output[etm_idx-2]['pos'] in ['NNG','MAG','XR'] and output[etm_idx-1]['pos']=='XSV':
                                front_ok=True
                        # V*패턴: etm_idx앞 중 하나라도 V*이면 됨
                        # 위 패턴 우선 체크 후 없으면:
                        if not front_ok and etm_idx>=1:
                            if output[etm_idx-1]['pos'].startswith('V'):
                                front_ok=True
                        # (N*)+이(VCP)도 언급되었으나 기존패턴에 따라 V*, 또는 (NNG/MAG+XSV)형태만 적음
                        # 문제에서 (N*)+(VCP)+... 언급은 이전에 있었으나 여기서는 없음.
                        # 만약 필요하다면 비슷하게 추가

                        if front_ok:
                            # 패턴 성립
                            # etm_idx부터 ef_idx까지 segment 추출
                            # 병합 범위: front 패턴 시작 ~ ef_idx (끝)
                            # front 패턴 시작점? 최소 (etm_idx-2)까지 갈 수 있으니
                            # 안전하게 etm_idx-2까지 확인
                            # 하지만 정확히 어느 구간 병합해야 할지?
                            # 문제에서 명시하지 않았으나, 일반적으론 front 패턴 시작부터 EF까지 모두 병합
                            start_idx = 0
                            # V*일 경우 etm_idx-1이 V*일 가능성, (NNG/MAG+XSV)이면 etm_idx-2부터
                            # 그냥 etm_idx-2>=0이면 etm_idx-2 시작 가능
                            # 구체적 명세 없음 => etm_idx-2가 범위 밖이면 etm_idx-1부터
                            if etm_idx>=2 and output[etm_idx-2]['pos'] in ['NNG','MAG','XR'] and output[etm_idx-1]['pos']=='XSV':
                                start_idx = etm_idx-2
                            elif etm_idx>=1 and output[etm_idx-1]['pos'].startswith('V'):
                                start_idx = etm_idx-1
                            else:
                                start_idx = etm_idx # 이 경우 거의 없을 것
                            
                            # 이제 start_idx부터 ef_idx까지 병합
                            seg = output[start_idx:ef_idx+1]
                            mm=''.join(t['morpheme']for t in seg)
                            output=output[:start_idx]+[{
                                'morpheme':mm,
                                'pos':'+'.join(t['pos']for t in seg),
                                'pos_desc':'-(으)ㄹ 거예요 형태 (8번)',
                                'matched_items':[item for item in grammatical_items if item['번호']==8],
                                'start':seg[0]['start'],
                                'len':sum(t['len']for t in seg),
                                'end':seg[-1]['end']
                            }]+output[ef_idx+1:]
                            idx=start_idx+1
                            matched=True
        if not matched:
            idx+=1
    return output



def check_item_9(output):
    idx=0
    while idx<len(output)-3:
        t1=output[idx]
        v_pattern=t1['pos'].startswith('V')
        n_pattern=False
        if t1['pos'] in ['NNG','MAG','XR'] and idx+1<len(output) and output[idx+1]['pos']=='XSV':
            n_pattern=True
        base_idx=idx+1 if v_pattern else idx+2
        if (v_pattern or n_pattern) and base_idx+2<len(output):
            t_go=output[base_idx]
            t_it=output[base_idx+1]
            t_ef=output[base_idx+2]
            # 고(EC)+있(VX)+다/어요(EF)
            if t_go['morpheme']=='고' and t_go['pos']=='EC':
                if t_it['morpheme']=='있' and t_it['pos']=='VX':
                    if t_ef['pos']=='EF' and (t_ef['morpheme'].endswith('다') or t_ef['morpheme'].endswith('어요')):
                        merged_tokens=output[idx:base_idx+3]
                        mm=''.join(t['morpheme']for t in merged_tokens)
                        output=output[:idx]+[{
                            'morpheme':mm,
                            'pos':'+'.join(t['pos']for t in merged_tokens),
                            'pos_desc':'...고 있다(어요) 진행 형태',
                            'matched_items':[item for item in grammatical_items if item['번호']==9],
                            'start':merged_tokens[0]['start'],
                            'len':sum(t['len']for t in merged_tokens),
                            'end':merged_tokens[-1]['end']
                        }]+output[base_idx+3:]
                        idx+=1
                        continue
        idx+=1
    return output


def check_item_10(output):
    idx = 0
    while idx < len(output):
        # 패턴별 최대 길이: EP까지 포함하면 최대 4토큰 정도
        # 예: (V*)+(EP)+"어서(EC)" -> 3토큰
        # (N*)+(VCP)+(EP)+"여서(EC)" -> 4토큰
        # ...등등
        # 여기서 '여서(EC)'와 '어서(EC)'를 구분해야 한다. 패턴에 따라 '여서'인지 '어서'인지 확인.
        
        # 간단히 length 2~4 토큰까지 확인
        matched = False
        for length in [4,3,2]:
            if idx + length <= len(output):
                segment = output[idx:idx+length]
                morphs = [t['morpheme'] for t in segment]
                poses = [t['pos'] for t in segment]

                # 패턴 단순화:
                # - (V*) + 어서(EC) -> 2토큰: [V*, 어서(EC)]
                # - (V*)+(EP)+어서(EC) -> 3토큰
                # - (NNG or MAG)+(XSV or XSA)+어서(EC) -> 3토큰
                # - (N*)+(VCP)+여서(EC) -> 3토큰 이상
                # - (NNG or MAG)+(XSV or XSA)+(EP)+어서(EC) -> 4토큰
                # - (N*)+(VCP)+(EP)+여서(EC) -> 4토큰
                
                # 공통: 마지막 토큰이 '어서'(EC) 또는 '여서'(EC)
                # '어서' 또는 '여서'인지 morph에서 확인.
                
                last_morpheme = morphs[-1]
                last_pos = poses[-1]

                if last_pos == 'EC' and (last_morpheme == '어서' or last_morpheme == '여서'):
                    # 뒤에서부터 조건 확인
                    # length=2: (V*)+어서(EC)
                    if length == 2 and poses[0].startswith('V'):
                        matched = True
                    
                    # length=3:
                    # (V*)+(EP)+어서(EC)
                    # (NNG/MAG)+(XSV or XSA)+어서(EC)
                    # (N*)+(VCP)+여서(EC) 가능
                    if length == 3 and not matched:
                        # [X,X,어서/여서(EC)]
                        # 1) (V*) + (EP) + 어서(EC)
                        if poses[0].startswith('V') and poses[1] == 'EP' and last_morpheme=='어서':
                            matched = True
                        # 2) (NNG or MAG)+(XSV or XSA)+어서(EC)
                        elif (poses[0] in ['NNG','MAG','XR']) and (poses[1] in ['XSV','XSA']) and last_morpheme=='어서':
                            matched = True
                        # 3) (N*)+(VCP)+여서(EC)
                        elif poses[0].startswith('N') and poses[1]=='VCP' and last_morpheme=='여서':
                            matched = True

                    # length=4:
                    # (NNG or MAG)+(XSV or XSA)+(EP)+어서(EC)
                    # (N*)+(VCP)+(EP)+여서(EC)
                    if length == 4 and not matched:
                        # [X,X,EP,어서/여서(EC)]
                        # pattern: (NNG/MAG)+(XSV/XSA)+(EP)+어서(EC)
                        if (poses[0] in ['NNG','MAG','XR']) and (poses[1] in ['XSV','XSA']) and poses[2]=='EP' and last_morpheme=='어서':
                            matched = True
                        # (N*)+(VCP)+(EP)+여서(EC)
                        elif poses[0].startswith('N') and poses[1]=='VCP' and poses[2]=='EP' and last_morpheme=='여서':
                            matched = True

                if matched:
                    merged_token = {
                        'morpheme': ''.join(morphs),
                        'pos': '+'.join(poses),
                        'pos_desc': '어서/여서 연결형(10번)',
                        'matched_items': [item for item in grammatical_items if item['번호'] == 10],
                        'start': segment[0]['start'],
                        'len': sum(t['len'] for t in segment),
                        'end': segment[-1]['end']
                    }
                    output = output[:idx] + [merged_token] + output[idx+length:]
                    idx += 1
                    break
        if not matched:
            idx += 1
    return output

def check_item_11(output):
    idx = 0
    while idx < len(output):
        if idx < len(output):
            t1 = output[idx]
            if t1['morpheme'] == '설레' and t1['pos'].startswith('V'):
                # 다음 토큰이 EC나 EF인지 확인
                if idx+1 < len(output):
                    t2 = output[idx+1]
                    if t2['pos'] in ['EC','EF']:
                        # 설레+EC/EF
                        merged_tokens = [t1,t2]
                        mm = ''.join(t['morpheme'] for t in merged_tokens)
                        output = output[:idx]+[{
                            'morpheme':mm,
                            'pos':'+'.join(t['pos']for t in merged_tokens),
                            'pos_desc':'설레 + (EC/EF)',
                            'matched_items':[item for item in grammatical_items if item['번호']==11],
                            'start':t1['start'],
                            'len':t1['len']+t2['len'],
                            'end':t2['end']
                        }]+output[idx+2:]
                        idx+=1
                        continue
                    elif t2['pos']=='EP' and idx+2<len(output):
                        t3 = output[idx+2]
                        if t3['pos'] in ['EF','EC']:
                            # 설레+EP+EF
                            merged_tokens=[t1,t2,t3]
                            mm=''.join(t['morpheme']for t in merged_tokens)
                            output=output[:idx]+[{
                                'morpheme':mm,
                                'pos':'+'.join(t['pos']for t in merged_tokens),
                                'pos_desc':'설레 + EP + EF/EC',
                                'matched_items':[item for item in grammatical_items if item['번호']==11],
                                'start':t1['start'],
                                'len':sum(x['len']for x in merged_tokens),
                                'end':t3['end']
                            }]+output[idx+3:]
                            idx+=1
                            continue
        idx+=1
    return output


def check_item_12(output):
    idx=0
    while idx < len(output):
        matched=False
        # 패턴 핵심: ... ETM + (거/것)(NNB) + (만(JX)?) + 같(VA) + ((EC/EF) or (EP+EF))
        # 최소 길이: ETM+(거/것)(NNB)+같(VA)+EC/EF =>4토큰
        # 최대 길이: (N*)+(VCP)+ETM+(거/것)(NNB)+만(JX)+같(VA)+(EP)+(EF)=>8토큰

        # 길이 8,7,...4까지 시도
        for length in range(8,3,-1):
            if idx+length<=len(output):
                segment=output[idx:idx+length]
                morphs=[t['morpheme']for t in segment]
                poses=[t['pos']for t in segment]

                # 뒤쪽 결합형태: '같'(VA) + EC/EF 또는 EP+EF
                # EP+EF면 마지막 두 토큰이 [EP, EF]
                # 그냥 EC/EF이면 마지막 토큰이 EC나 EF

                last_pos = poses[-1]
                second_last_pos = poses[-2] if length>=2 else None
                is_ep_ef = (length>=2 and second_last_pos=='EP' and last_pos in ['EF','EC'])

                # 만(JX) optional: 있거나 없거나
                # '거/것'(NNB) 꼭 있어야 하고, ETM 앞에 반드시
                # ETM 바로 뒤에 거/것(NNB)
                # 그 뒤 만(JX) optional
                # 그 다음 같(VA)
                # 마지막이 EC/EF 또는 EP+EF

                # 패턴 앞부분:
                # 3가지 유형의 앞부분:
                # 1) (V*)+ETM ...
                # 2) (NNG or MAG)+XSV+ETM ...
                # 3) (N*)+VCP+ETM ...

                # 먼저 'ETM' 위치를 찾아 거/것(NNB)찾기
                # ETM필수, 그 뒤 (거/것)(NNB)
                # 만(JX) 있나 확인
                # 같(VA) 다음 EP+EF or EF/EC

                # 간략히 정규화:
                # front_patterns = (V*) or (NNG/MAG + XSV) or (N* + VCP)
                # middle: ETM + (거/것)(NNB) + (만(JX)?) + 같(VA)
                # end: EP+EF or EF/EC

                # ETM index 찾기
                try:
                    etm_idx = [i for i,p in enumerate(poses) if p=='ETM'][0]
                except:
                    continue

                # etm뒤에 거/것(NNB)필수
                if etm_idx+1<len(segment) and poses[etm_idx+1]=='NNB' and morphs[etm_idx+1] in ['거','것']:
                    # 만(JX) optional
                    after_nnb_idx=etm_idx+2
                    has_man=False
                    if after_nnb_idx<len(segment) and poses[after_nnb_idx]=='JX' and morphs[after_nnb_idx]=='만':
                        has_man=True
                        after_nnb_idx+=1

                    # now after_nnb_idx should point to '같'(VA)
                    if after_nnb_idx<len(segment) and poses[after_nnb_idx]=='VA' and morphs[after_nnb_idx]=='같':
                        # 뒤에 남는 토큰: EP+EF나 EF/EC
                        remain_len = length-(after_nnb_idx+1)
                        # remain_len=1 or 2
                        # if is_ep_ef: last two pos=EP,EF
                        # else last one pos=EF or EC
                        tail_idx = after_nnb_idx+1
                        if is_ep_ef:
                            # need 2 tokens left: EP, EF
                            if remain_len==2 and poses[-2]=='EP' and poses[-1] in ['EF','EC']:
                                # 앞부분 검사: front_patterns
                                # front part: segment[:etm_idx] + segment[etm_idx] is ETM
                                # front part ends before ETM
                                front_part = segment[:etm_idx]
                                if check_front_12(front_part):
                                    matched=True
                        else:
                            # no EP+EF, just EF/EC one token
                            if remain_len==1 and poses[-1] in ['EF','EC']:
                                front_part=segment[:etm_idx]
                                if check_front_12(front_part):
                                    matched=True
                if matched:
                    mm=''.join(morphs)
                    output=output[:idx]+[{
                        'morpheme':mm,
                        'pos':'+'.join(poses),
                        'pos_desc':'...거/것...만...같... 패턴(12번)',
                        'matched_items':[item for item in grammatical_items if item['번호']==12],
                        'start':segment[0]['start'],
                        'len':sum(t['len']for t in segment),
                        'end':segment[-1]['end']
                    }]+output[idx+length:]
                    idx+=1
                    break
        if not matched:
            idx+=1
    return output

def check_front_12(front_part):
    # 앞부분 (V*) or (NNG or MAG)+XSV or (N*)+VCP
    # front_part pos 체크
    # (V*) : front_part 길이=1, poses[0].startswith('V')
    # (NNG or MAG)+XSV: front_part길이=2, poses[0] in [NNG,MAG], poses[1]==XSV
    # (N*)+VCP: front_part길이=2, poses[0].startswith('N'), poses[1]=='VCP'
    poses=[f['pos']for f in front_part]
    morphs=[f['morpheme']for f in front_part]
    length=len(front_part)
    if length==1 and poses[0].startswith('V'):
        return True
    if length==2:
        if poses[0] in ['NNG','MAG'] and poses[1]=='XSV':
            return True
        if front_part[0]['pos'].startswith('N') and front_part[1]['pos']=='VCP':
            return True
    return False


def check_item_13(output):
    idx=0
    while idx<len(output):
        # 최소 2토큰: [X,거나(EC)]
        # X가 (V*), (NNG/MAG+XSV), 아니(VCN), (N*+VCP) 중 하나
        if idx+2<=len(output):
            segment=output[idx:idx+2]
            morphs=[t['morpheme']for t in segment]
            poses=[t['pos']for t in segment]
            if morphs[1]=='거나' and poses[1]=='EC':
                # 앞 토큰 확인
                # (V*), 또는 (NNG/MAG+XSV), 또는 아니(VCN), 또는 (N*)+이(VCP)
                # 길이2밖에없으니 (NNG/MAG+XSV)나 (N*+VCP)하려면 안됨. 최소3토큰 필요
                # 여기 문제점: 패턴이 최소3토큰 필요할 수도
                # 사용자 패턴 정의상 '거나(EC)' 바로 앞 토큰만 명시함.
                # (NNG/MAG+XSV)+거나 => 최소3토큰 [NNG/MAG,XSV,거나]
                # (N*)+이(VCP)+거나 => 최소3토큰 [N*,이,VCP,거나? 이(VCP)는1토큰]
                # 수정: 패턴 정의 다시 확인 필요.
                # 패턴 정의가 간단히:
                # (V*)+거나(EC)
                # (NNG or MAG)+(XSV)+거나(EC)
                # 아니(VCN)+거나(EC)
                # (N*)+이(VCP)+거나(EC)
                # 후자 둘은 최소3토큰
                # 여기서는 idx+2<=len(output) 이므로 length=2인 segment -> (V*)+거나 or 아니(VCN)+거나 만 가능
                # (NNG/MAG+XSV)+거나 3토큰 필요
                # (N*+이(VCP))+거나 3토큰 필요

                # length=2인 경우:
                # pattern: (V*)+거나, (아니(VCN)+거나)
                if poses[0].startswith('V') or (morphs[0]=='아니' and poses[0]=='VCN'):
                    # 태깅
                    merged={
                        'morpheme':''.join(morphs),
                        'pos':'+'.join(poses),
                        'pos_desc':'거나 패턴(13번)',
                        'matched_items':[item for item in grammatical_items if item['번호']==13],
                        'start':segment[0]['start'],
                        'len':sum(t['len']for t in segment),
                        'end':segment[-1]['end']
                    }
                    output=output[:idx]+[merged]+output[idx+2:]
                    idx+=1
                    continue
                # length=2에서 (NNG or MAG)+XSV+거나, (N*)+이(VCP)+거나 불가
            if idx+3<=len(output):
                segment3=output[idx:idx+3]
                morphs3=[t['morpheme']for t in segment3]
                poses3=[t['pos']for t in segment3]
                # (NNG/MAG)+XSV+거나(EC)
                if morphs3[2]=='거나' and poses3[2]=='EC':
                    if poses3[0] in ['NNG','MAG','XR'] and poses3[1]=='XSV':
                        merged={
                            'morpheme':''.join(morphs3),
                            'pos':'+'.join(poses3),
                            'pos_desc':'거나 패턴(13번)',
                            'matched_items':[item for item in grammatical_items if item['번호']==13],
                            'start':segment3[0]['start'],
                            'len':sum(t['len']for t in segment3),
                            'end':segment3[-1]['end']
                        }
                        output=output[:idx]+[merged]+output[idx+3:]
                        idx+=1
                        continue
                # (N*)+이(VCP)+거나(EC)
                if idx+3<=len(output):
                    # (N*,이,VCP,거나) 최소4토큰 필요 (N*+이(VCP) 2토큰?)
                    # 이(VCP) 1토큰이면 N*,이,거나면 3토큰
                    # 패턴정의 수정 필요: (N*)+이(VCP)+거나(EC) = N*,이,거나 total 3토큰
                    # pos check: N* means poses[0].startswith('N')
                    # 다음 '이'(VCP) 하나의 토큰: morph='이',pos='VCP'
                    # 그 다음 '거나'(EC)
                    if idx+3<=len(output):
                        seg4=output[idx:idx+3]
                        m4=[t['morpheme']for t in seg4]
                        p4=[t['pos']for t in seg4]
                        # [N*, 이(VCP), '거나'(EC)] length=3
                        if p4[0].startswith('N') and m4[1]=='이' and p4[1]=='VCP' and m4[2]=='거나' and p4[2]=='EC':
                            merged={
                                'morpheme':''.join(m4),
                                'pos':'+'.join(p4),
                                'pos_desc':'거나 패턴(13번)',
                                'matched_items':[item for item in grammatical_items if item['번호']==13],
                                'start':seg4[0]['start'],
                                'len':sum(t['len']for t in seg4),
                                'end':seg4[-1]['end']
                            }
                            output=output[:idx]+[merged]+output[idx+3:]
                            idx+=1
                            continue
        idx+=1
    return output

def check_item_14(output):
    idx=0
    while idx<len(output):
        # 최소2토큰: 같(VA)+EF/EC or 같(VA)+ETM
        # 최대3토큰: 같(VA)+EP+EF
        if idx+2<=len(output):
            segment2=output[idx:idx+2]
            if segment2[0]['morpheme']=='같' and segment2[0]['pos'].startswith('V'): # 같(VA)
                # 같(VA)+(EC/EF) or (ETM)
                if segment2[1]['pos'] in ['EC','EF','ETM']:
                    merged={
                        'morpheme':segment2[0]['morpheme']+segment2[1]['morpheme'],
                        'pos':segment2[0]['pos']+'+'+segment2[1]['pos'],
                        'pos_desc':'같...패턴(14번)',
                        'matched_items':[item for item in grammatical_items if item['번호']==14],
                        'start':segment2[0]['start'],
                        'len':segment2[0]['len']+segment2[1]['len'],
                        'end':segment2[1]['end']
                    }
                    output=output[:idx]+[merged]+output[idx+2:]
                    idx+=1
                    continue
        if idx+3<=len(output):
            segment3=output[idx:idx+3]
            if segment3[0]['morpheme']=='같' and segment3[0]['pos'].startswith('V'):
                # 같(VA)+(EP+EF)
                if segment3[1]['pos']=='EP' and segment3[2]['pos']=='EF':
                    merged={
                        'morpheme':'같'+segment3[1]['morpheme']+segment3[2]['morpheme'],
                        'pos':segment3[0]['pos']+'+'+segment3[1]['pos']+'+'+segment3[2]['pos'],
                        'pos_desc':'같+EP+EF 패턴(14번)',
                        'matched_items':[item for item in grammatical_items if item['번호']==14],
                        'start':segment3[0]['start'],
                        'len':sum(t['len']for t in segment3),
                        'end':segment3[-1]['end']
                    }
                    output=output[:idx]+[merged]+output[idx+3:]
                    idx+=1
                    continue
        idx+=1
    return output

def check_item_15(output):
    idx=0
    vowels = ['네요'] # 여기선 '네요' 고정
    # 모든 패턴 끝에 '네요'(EF) 존재
    # 패턴별로 (EP)나 (EC)+(VX) 등이 있을 수 있으니 뒤에서부터 검사
    # 전략:
    # 1) '네요'(EF) 토큰 위치 찾기.
    # 2) '네요' 앞 토큰들을 역으로 확인하며 패턴 중 하나에 맞는지 체크.

    # pos_desc: '새롭게 알게 된 사실을 나타내는 종결 표현(15번)'

    while idx<len(output):
        matched=False
        if output[idx]['pos']=='EF' and output[idx]['morpheme']=='네요':
            # EF='네요' 토큰 하나만으로는 패턴 성립 불가. 최소 앞에 하나 이상의 토큰 필요.
            ef_idx=idx
            # 최대 6토큰까지 거슬러 올라가며 패턴 확인
            for length in range(2,7): 
                # length: total tokens count from front part to '네요'
                # ef_idx가 마지막 토큰이므로 start_idx = ef_idx-(length-1)
                start_idx = ef_idx-(length-1)
                if start_idx<0:
                    continue
                segment = output[start_idx:ef_idx+1]
                p=[t['pos']for t in segment]
                m=[t['morpheme']for t in segment]

                # 패턴별 확인
                # 핵심: 마지막이 '네요'(EF)
                # 앞부분이 (V*)나 (NNG/MAG/XR+XSV/XSA)나 (N*+VCP) 형태 + (EP)들 + (EC)+(VX) 조합
                # 이 부분은 매우 복잡하므로, 간략화:
                # 규칙:
                # 1) 끝: EF='네요'
                # 2) 앞부분 최소 하나의 실질 형태소(V*, NNG/MAG/XR+(XSV/XSA), N*+VCP)
                # 3) EP,EC,VX가 중간에 올 수 있음
                # 여기서는 패턴을 단순히:
                # - 마지막 EF='네요'
                # - 앞쪽에 V* 또는 (NNG/MAG/XR+XSV/XSA) 또는 (N*+VCP)
                # - 중간에 EP,EC,VX가 0개 이상

                # pos체크 함수
                def front_check_15(front_poses, front_morphs):
                    # 최소 하나의 실질 형태:
                    # (V*) or (NNG/MAG/XR + XSV/XSA) or (N*+VCP)
                    # V*: 하나의 V* 토큰만 있어도 가능
                    # NNG/MAG/XR+XSV/XSA: 연속 2토큰 패턴 필요
                    # N*+VCP: 연속 2토큰 패턴 필요

                    # 뒤에서부터 EP,EC,VX 제외하고 나면 남는 실질 형태로 패턴 판단
                    # EP,EC,VX는 중간에 몇 번 나와도 허용
                    # strategy: front에서 EP,EC,VX 제거 후 남은 토큰 패턴매칭

                    filtered = [(pm,pp) for pm,pp in zip(front_morphs,front_poses) if pp not in ['EP','EC','VX']]
                    # filtered가 empty면 실패
                    if not filtered:
                        return False
                    # filtered 마지막 부분이 V*면 pattern ok
                    # 또는 filtered 중 2개 이상이고 [0 or ... (NNG/MAG/XR),1=(XSV/XSA)] or [N*,VCP]
                    # 여기선 단순히 가장 마지막 남은 형태로 판단:
                    # if filtered[-1][1].startswith('V'): return True (V* pattern)
                    # elif len(filtered)>=2:
                    #   check last two tokens:
                    #   if (NNG/MAG/XR)+(XSV/XSA)
                    #   or (N*)+(VCP)
                    # XR 추가됨
                    # XR도 NNG/MAG와 비슷하게 취급?

                    # XR도 NNG/MAG와 유사한 명사류로 취급
                    # front: 
                    # (NNG/MAG/XR)+(XSV/XSA)
                    # (N*)+(VCP)
                    # N* means any noun-like pos starting with 'N'

                    if filtered[-1][1].startswith('V'):
                        return True
                    if len(filtered)>=2:
                        fpos = [fp[1] for fp in filtered]
                        fpos_last2 = fpos[-2:]
                        # (NNG/MAG/XR)+(XSV/XSA)
                        if filtered[-2][1] in ['NNG','MAG','XR'] and filtered[-1][1] in ['XSV','XSA','XSA-I']:
                            return True
                        # (N*)+(VCP)
                        if filtered[-2][1].startswith('N') and filtered[-1][1]=='VCP':
                            return True
                    return False

                if m[-1]=='네요' and p[-1]=='EF':
                    # pos_desc: '새롭게 알게 된 사실을 나타내는 종결 표현(15번)'
                    # front_part = segment[:-1]
                    front_part = segment[:-1]
                    fm=[t['morpheme']for t in front_part]
                    fp=[t['pos']for t in front_part]
                    if front_check_15(fp,fm):
                        # 매칭
                        mm=''.join(m)
                        output=output[:start_idx]+[{
                            'morpheme':mm,
                            'pos':'+'.join(p),
                            'pos_desc':'새롭게 알게 된 사실을 나타내는 종결 표현(15번)',
                            'matched_items':[item for item in grammatical_items if item['번호']==15],
                            'start':segment[0]['start'],
                            'len':sum(t['len']for t in segment),
                            'end':segment[-1]['end']
                        }]+output[ef_idx+1:]
                        idx=start_idx+1
                        matched=True
                        break

            if matched:
                continue
        idx+=1
    return output

def check_item_16(output):
    vowels = ['아','어','여'] 
    idx = 0
    while idx < len(output):
        if output[idx]['pos'] == 'EF' and any(output[idx]['morpheme'].startswith(v) for v in vowels):
            # EF 토큰 찾음
            ef_idx = idx
            # 앞쪽 토큰들 확인 (최대 6~7토큰까지)
            # 패턴이 매우 다양하므로 최대 길이 7토큰 정도까지 역으로 확인
            for length in range(2,8):
                # length: EF 포함 총 토큰 수
                start_idx = ef_idx-(length-1)
                if start_idx<0:
                    continue
                segment = output[start_idx:ef_idx+1]
                m=[t['morpheme'] for t in segment]
                p=[t['pos'] for t in segment]

                # front_check 함수: EP,EC,VX 제거 후 남은 마지막 구조 확인
                def front_check_16(fm,fp):
                    # EP,EC,VX 제거
                    filtered=[(mm,pp) for mm,pp in zip(fm,fp) if pp not in ['EP','EC','VX']]
                    if not filtered:
                        return False
                    # 마지막 남은 구조가 (V*) or (NNG/MAG/XR+XSV/XSA) or (N*+VCP)
                    flen=len(filtered)
                    fpos=[pp for (mm,pp) in filtered]
                    if flen==1:
                        # V*
                        if fpos[0].startswith('V'):
                            return True
                    elif flen>=2:
                        # 마지막 두 토큰 확인
                        # (NNG/MAG/XR, XSV/XSA) 또는 (N*,VCP)
                        if filtered[-2][1] in ['NNG','MAG','XR'] and filtered[-1][1] in ['XSV','XSA']:
                            return True
                        if filtered[-2][1].startswith('N') and filtered[-1][1]=='VCP':
                            return True
                    return False

                front_part = segment[:-1] # EF 제외한 앞부분
                fm=[tt['morpheme'] for tt in front_part]
                fp=[tt['pos'] for tt in front_part]

                if front_check_16(fm,fp):
                    # 매칭
                    mm=''.join(m)
                    merged={
                        'morpheme':mm,
                        'pos':'+'.join(p),
                        'pos_desc':'해할 자리에 쓰여 어떤 사실을 서술하는 종결 어미(16번)',
                        'matched_items':[it for it in grammatical_items if it['번호']==16],
                        'start':segment[0]['start'],
                        'len':sum(x['len'] for x in segment),
                        'end':segment[-1]['end']
                    }
                    output=output[:start_idx]+[merged]+output[ef_idx+1:]
                    idx=start_idx+1
                    break
            else:
                idx+=1
        else:
            idx+=1
    return output

# def check_item_17(output):
#     idx = 0
#     while idx < len(output) - 1:
#         token = output[idx]
#         next_token = output[idx + 1]
#         if token['morpheme'] == '보' and token['pos'] == 'VX':
#             if next_token['morpheme'] in ['았', '었'] and next_token['pos'] == 'EP':
#                 # '보' + '았/었'을 병합하여 처리
#                 merged_morpheme = '보' + next_token['morpheme']
#                 merged_token = {
#                     'morpheme': merged_morpheme,
#                     'pos': 'VX+EP',
#                     'pos_desc': '보조 동사+선어말 어미',
#                     'matched_items': [item for item in grammatical_items if item['번호'] == 17],
#                     'start': token['start'],
#                     'len': token['len'] + next_token['len'],
#                     'end': next_token['end']
#                 }
#                 output = output[:idx] + [merged_token] + output[idx + 2:]
#                 idx += 1
#             else:
#                 idx += 1
#         else:
#             idx += 1
#     return output

def check_item_17(output):
    exclude_words = ['찔러보다','새겨보다','가려보다','달아보다','돌이켜보다','올려보다','들떠보다','돌려보다']
    vowels = ['아','어','여']
    pos_desc_17 = '경험을 나타내는 (아/어/여+보) 표현(17번)'

    idx=0
    while idx<len(output):
        matched=False
        # 길이 3~5 토큰 범위에서 패턴 탐색
        # 최소3토큰: (VV)+아/어/여(EC)+보(VX)+(EF/EC) 사실 최소4토큰 (VV+아/어/여(EC)+보(VX)+EC/EF)
        # 최대5토큰: EP까지 포함
        # 패턴 길이: EP가 없으면 4토큰, 있으면 5토큰
        for length in [5,4,3]:
            if idx+length<=len(output):
                seg = output[idx:idx+length]
                m=[t['morpheme']for t in seg]
                p=[t['pos']for t in seg]

                # 끝이 EF나 EC
                if p[-1] in ['EF','EC']:
                    # '보'(VX)와 아/어/여(EC) 필수
                    if '보' in m:
                        try:
                            bo_idx = m.index('보')
                        except:
                            continue
                        if bo_idx>0 and p[bo_idx]=='VX':
                            # bo_idx-1 = 아/어/여(EC)
                            if p[bo_idx-1]=='EC' and any(v in m[bo_idx-1] for v in vowels):
                                # 끝 부분 EF/EC or EP+EF 확인
                                end_ok=False
                                if length==5:
                                    # EP+EF일 때: 마지막 2토큰 EP+EF
                                    if length>=5 and p[-2]=='EP' and p[-1] in ['EF','EC']:
                                        end_ok=True
                                elif length==4:
                                    # EF/EC만
                                    if p[-1] in ['EF','EC']:
                                        end_ok=True
                                elif length==3:
                                    # 최소 3토큰은 (VV+아/어/여(EC)+보(VX)+EC/EF)가 4토큰 필요하므로
                                    # length=3인 경우 실제 패턴 불가
                                    # 그러나 혹시 EP가 없는 매우 최소한의 패턴 (VV+아/어/여(EC)+보(VX)) + EF나 EC로 4토큰 필요
                                    # length=3이면 (V*,EC,보,EF/EC) 최소4토큰 필요하므로 3토큰 불가
                                    end_ok=False

                                if not end_ok:
                                    continue

                                # 앞부분 (VV) 또는 (NNG/MAG+XSV)
                                front_part=seg[:bo_idx-1]
                                # EP,EC,VX 제거하여 실질 형태 판단
                                def front_filter(tokens):
                                    return [(tt['morpheme'],tt['pos']) for tt in tokens if tt['pos'] not in ['EP','EC','VX']]
                                filtered = front_filter(front_part)
                                flen=len(filtered)
                                fpos=[pp for (mm,pp) in filtered]

                                def check_front_17(flen,fpos):
                                    # (VV) -> flen=1, fpos[0].startswith('V')
                                    # (NNG/MAG)+XSV -> flen=2, fpos[0] in NNG/MAG, fpos[1]==XSV
                                    # XR도 NNG/MAG처럼 취급 가능하면 fpos[0] in ['NNG','MAG','XR']
                                    if flen==1 and fpos[0].startswith('V'):
                                        return True
                                    if flen==2 and fpos[0] in ['NNG','MAG','XR'] and fpos[1]=='XSV':
                                        return True
                                    return False

                                if check_front_17(flen,fpos):
                                    final_word=''.join(m)
                                    # exclude_words 검사
                                    if any(exw in final_word for exw in exclude_words):
                                        continue
                                    # 매칭
                                    merged={
                                        'morpheme':final_word,
                                        'pos':'+'.join(p),
                                        'pos_desc':pos_desc_17,
                                        'matched_items':[it for it in grammatical_items if it['번호']==17],
                                        'start':seg[0]['start'],
                                        'len':sum(t['len']for t in seg),
                                        'end':seg[-1]['end']
                                    }
                                    output=output[:idx]+[merged]+output[idx+length:]
                                    idx+=1
                                    matched=True
                                    break
        if not matched:
            idx+=1
    return output

def check_item_18(output):
    """
    특정 패턴 "그렇지 않아도 ...려고"를 찾아 전체 문장을 18번으로 태깅합니다.
    패턴:
    "그렇(VA-I)+지(EC)+않(VX)+어도(EC)" + "(*V*)"+"려고"(EC)
    """
    idx = 0
    while idx < len(output):
        # 패턴 시작 위치 검사
        if idx + 3 < len(output):
            t1 = output[idx]
            t2 = output[idx + 1]
            t3 = output[idx + 2]
            t4 = output[idx + 3]

            if (t1['morpheme'] == '그렇' and t1['pos'] == 'VA-I' and
                t2['morpheme'] == '지' and t2['pos'] == 'EC' and
                t3['morpheme'] == '않' and t3['pos'] == 'VX' and
                t4['morpheme'] == '어도' and t4['pos'] == 'EC'):
                
                # '려고'(EC) 찾기
                for j in range(idx + 4, len(output)):
                    tj = output[j]
                    if '려고' in tj['morpheme'] and 'EC' in tj['pos']:
                        # 패턴 매칭 성공, 전체 문장을 18번으로 태깅
                        merged_sentence = {
                            'morpheme': ''.join([tok['morpheme'] for tok in output]),
                            'pos': '+'.join([tok['pos'] for tok in output]),
                            'pos_desc': '전체 문장 패턴(18번)',
                            'matched_items': [{
                                '번호': 18,
                                '형태': '-려고',
                                '품사': 'EC',
                                '의미': '의지나 계획을 나타내는 표현.'
                            }],
                            'start': output[0]['start'],
                            'len': sum(tok['len'] for tok in output),
                            'end': output[-1]['end']
                        }
                        # 전체 문장을 병합된 토큰으로 교체
                        return [merged_sentence]
        idx += 1

    return output


def check_item_19(output):
    # pos_desc: '진행 중임을 나타내는 ...는 중이다 표현(19번)'
    idx=0
    while idx<len(output):
        matched=False
        # 패턴 끝: VCP+(EC or EF)
        # 중(NNB) 바로 앞에 는(ETM"6")
        # 앞부분이:
        # 1) VV
        # 2) (NNG/MAG)+(XSV or XSA)
        # 3) (V*)+(EC)+(VX)
        # 4) (XR)+(XSV or XSA)+(EC)+(VX)

        # 최대 패턴 길이:
        # 가장 긴: (XR)+(XSV or XSA)+(EC)+(VX)+는(ETM)+중(NNB)+VCP+(EC or EF)
        # 최소 토큰수: 5토큰(예: VV, 는(ETM), 중(NNB), VCP, EC/EF)
        # 최대 토큰수: 8토큰(XR,XSV/XSA,EC,VX,는,중,VCP,EC/EF)

        for length in range(8,4,-1): 
            if idx+length<=len(output):
                seg = output[idx:idx+length]
                m=[t['morpheme'] for t in seg]
                p=[t['pos'] for t in seg]

                # 끝: VCP+(EC or EF)
                if p[-2]=='VCP' and p[-1] in ['EC','EF']:
                    # '중'(NNB)와 '는'(ETM) 찾기
                    # 뒤에서부터: [ ... 는(ETM), 중(NNB), VCP, EC/EF]
                    # 는(ETM)과 중(NNB)는 연속
                    # 찾아보기
                    # 끝에서 3토큰 VCP, EC/EF 제외하면 length-2 토큰까지
                    # 중(NNB)와 는(ETM)연속
                    found=False
                    for k in range(length-3):
                        # seg[k], seg[k+1]
                        if p[k]=='ETM' and m[k]=='는':
                            if k+1<length and p[k+1]=='NNB' and m[k+1]=='중':
                                # 앞부분: seg[:k]
                                front_part=seg[:k]
                                # front patterns:
                                # VV
                                # (NNG/MAG)+(XSV or XSA)
                                # (V*)+(EC)+(VX)
                                # (XR)+(XSV or XSA)+(EC)+(VX)
                                
                                def check_front_19(fp):
                                    f_m=[x['morpheme']for x in fp]
                                    f_p=[x['pos']for x in fp]
                                    # EP,EC,VX 허용? 문제 명시 없음
                                    # 여기선 최소한 순서대로 패턴 식별

                                    # try pattern 1: VV 하나
                                    if len(fp)==1 and f_p[0].startswith('V'):
                                        return True
                                    # pattern 2:(NNG/MAG)+(XSV or XSA)
                                    if len(fp)==2 and f_p[0] in ['NNG','MAG'] and f_p[1] in ['XSV','XSA']:
                                        return True
                                    # pattern 3:(V*)+(EC)+(VX)
                                    if len(fp)==3:
                                        # Check last 3: pos[-3..]: V*, EC, VX in order?
                                        # Actually order: (V*), (EC), (VX)
                                        if f_p[0].startswith('V') and f_p[1]=='EC' and f_p[2]=='VX':
                                            return True
                                    # pattern 4:(XR)+(XSV or XSA)+(EC)+(VX)
                                    if len(fp)==4:
                                        # XR, (XSV/XSA), EC, VX 순서인지
                                        if f_p[0]=='XR' and f_p[1] in ['XSV','XSA'] and f_p[2]=='EC' and f_p[3]=='VX':
                                            return True
                                    return False

                                if check_front_19(front_part):
                                    # 매칭
                                    mm=''.join(x['morpheme']for x in seg)
                                    output=output[:idx]+[{
                                        'morpheme':mm,
                                        'pos':'+'.join(x['pos']for x in seg),
                                        'pos_desc':'진행 중임을 나타내는 ...는 중이다 표현(19번)',
                                        'matched_items':[item for item in grammatical_items if item['번호']==19],
                                        'start':seg[0]['start'],
                                        'len':sum(x['len']for x in seg),
                                        'end':seg[-1]['end']
                                    }]+output[idx+length:]
                                    idx+=1
                                    matched=True
                                    found=True
                                    break
                    if found:
                        break
        if not matched:
            idx+=1
    return output

def check_item_20(output):
    # pos_desc: '(으)ㄹ까 생각중이다 패턴(20번)'
    # ㄹ까/을까 형태 normalization 필요
    idx=0
    while idx<len(output):
        matched=False
        # 최소 패턴 길이: 
        # 최단: (VV)+ㄹ까/을까+생각+중+이+EC/EF = 6토큰
        # 최장: (XR+(XSV/XSA)+EC+VX)+ㄹ/을까+생각+중+이+EC/EF = 9토큰
        for length in range(9,5,-1): # 9~6토큰
            if idx+length<=len(output):
                seg = output[idx:idx+length]
                m=[t['morpheme']for t in seg]
                p=[t['pos']for t in seg]

                # 끝: "이"(VCP)+(EC or EF)
                if length<2:
                    continue
                if p[-2]=='VCP' and p[-1] in ['EC','EF']:
                    # 중(NNB), 생각(NNG), ㄹ/을까(EC/EF)
                    # 끝5토큰: [ㄹ/을까(EC/EF), 생각(NNG), 중(NNB), 이(VCP), EC/EF]
                    if length<5:
                        continue
                    # 인덱스: 
                    # seg[-5] = ㄹ/을까(EC/EF)
                    # seg[-4] = 생각(NNG)
                    # seg[-3] = 중(NNB)
                    # seg[-2] = 이(VCP)
                    # seg[-1] = EC/EF
                    if p[-4]=='NNG' and m[-4]=='생각' and p[-3]=='NNB' and m[-3]=='중':
                        if p[-5] in ['EC','EF']:
                            normalized_que = normalize_morpheme(m[-5])
                            if normalized_que in ['ㄹ까','을까','ᆯ까']:
                                # 앞부분 = seg[:length-5]
                                front_part = seg[:length-5]
                                # 앞부분 패턴:
                                # 1) (NNG or MAG)+(XSV)
                                # 2) (VV)
                                # 3) (V*+EC+VX)
                                # 4) (XR+(XSV or XSA)+EC+VX)

                                def check_front_20(fp):
                                    fm=[x['morpheme']for x in fp]
                                    fps=[x['pos']for x in fp]
                                    l=len(fp)
                                    # pattern1: l=2, fps[0] in NNG/MAG, fps[1]==XSV
                                    if l==2 and fps[0] in ['NNG','MAG'] and fps[1]=='XSV':
                                        return True
                                    # pattern2: l=1, fps[0].startswith('V')
                                    if l==1 and fps[0].startswith('V'):
                                        return True
                                    # pattern3: l=3, (V*,EC,VX)
                                    if l==3 and fps[0].startswith('V') and fps[1]=='EC' and fps[2]=='VX':
                                        return True
                                    # pattern4: l=4, (XR,(XSV/XSA),EC,VX)
                                    if l==4 and fps[0]=='XR' and fps[1] in ['XSV','XSA'] and fps[2]=='EC' and fps[3]=='VX':
                                        return True
                                    return False

                                if check_front_20(front_part):
                                    # 매칭
                                    mm=''.join(m)
                                    merged={
                                        'morpheme':mm,
                                        'pos':'+'.join(p),
                                        'pos_desc':'(으)ㄹ까 생각중이다 패턴(20번)',
                                        'matched_items':[it for it in grammatical_items if it['번호']==20],
                                        'start':seg[0]['start'],
                                        'len':sum(x['len']for x in seg),
                                        'end':seg[-1]['end']
                                    }
                                    output=output[:idx]+[merged]+output[idx+length:]
                                    idx+=1
                                    matched=True
                                    break
        if not matched:
            idx+=1
    return output


def check_item_21(output):
    # pos_desc_21: '어 드릴게요 패턴(21번)'
    # 패턴은 항상 "어(EC)드리(VX)ㄹ게요(EF)"로 끝남
    # 앞부분이 (VV) 또는 (NNG/MAG+XSV) 또는 (V*+EC+VX)
    idx=0
    while idx<len(output):
        matched=False
        # 최소 4토큰: (VV)+어(EC)+드리(VX)+ㄹ게요(EF)
        # 최대 6토큰: (V*+EC+VX)+어(EC)+드리(VX)+ㄹ게요(EF)
        for length in [6,5,4]:
            if idx+length<=len(output):
                seg=output[idx:idx+length]
                m=[t['morpheme']for t in seg]
                p=[t['pos']for t in seg]

                # 끝 토큰: ㄹ게요(EF)
                if m[-1].endswith('게요') and p[-1]=='EF':
                    # 바로 앞 '드리'(VX), 그 앞 '어'(EC) 필수
                    # seg[-2]=드리(VX), seg[-3]=어(EC)
                    if length<3:
                        continue
                    if p[-2].startswith('V') and m[-2]=='드리' and p[-3]=='EC' and m[-3].endswith('어'):
                        # 앞부분 = seg[:length-3]
                        front_part = seg[:length-3]
                        # 앞부분이 (VV) or (NNG/MAG+XSV) or (V*+EC+VX)
                        def check_front_21(fp):
                            fpos=[x['pos']for x in fp]
                            l=len(fp)
                            # (VV): l=1, fpos[0].startswith('V')
                            if l==1 and fpos[0].startswith('V'):
                                return True
                            # (NNG/MAG+XSV): l=2, fpos[0] in NNG/MAG, fpos[1]=='XSV'
                            if l==2 and fpos[0] in ['NNG','MAG','XR'] and fpos[1]=='XSV':
                                return True
                            # (V*+EC+VX): l=3, fpos[0].startswith('V'), fpos[1]=='EC', fpos[2]=='VX'
                            if l==3 and fpos[0].startswith('V') and fpos[1]=='EC' and fpos[2]=='VX':
                                return True
                            return False

                        if check_front_21(front_part):
                            # 매칭
                            mm=''.join(m)
                            merged={
                                'morpheme':mm,
                                'pos':'+'.join(p),
                                'pos_desc':'어 드릴게요 패턴(21번)',
                                'matched_items':[it for it in grammatical_items if it['번호']==21],
                                'start':seg[0]['start'],
                                'len':sum(x['len']for x in seg),
                                'end':seg[-1]['end']
                            }
                            output=output[:idx]+[merged]+output[idx+length:]
                            idx+=1
                            matched=True
                            break
        if not matched:
            idx+=1
    return output

def check_item_22(output):
    # pos_desc_22: '게(EC) 패턴(22번)'
    # 패턴: 
    # 1. (V*)+"게"(EC)
    # 2. (NNG/MAG+(XSV/XSA))+"게"(EC)
    # 3. (V*)+(EC)+(VX)+"게"(EC)
    # 4. (XR+(XSV/XSA)+EC+VX)+"게"(EC)
    # 제외조건:
    # - 게(EC)+하(VV/VX)/되(VV)
    # - 게(EC)+"."(SF)

    idx=0
    while idx<len(output):
        token = output[idx]
        if token['morpheme'] == '게' and token['pos'] == 'EC':
            # 패턴 확인
            # 최대 4토큰까지 앞을 확인
            matched = False
            # length = 패턴 길이(2~5)
            # "게"(EC) 혼자서는 안되고 최소 앞에 한 토큰(V*) 필요
            # (V*)+게 : length=2
            # (NNG/MAG+XSV)+게 : length=3
            # (V*+EC+VX)+게 : length=4
            # (XR+(XSV/XSA)+EC+VX)+게 : length=5
            for length in [5,4,3,2]:
                start_idx=idx-(length-1)
                if start_idx<0:
                    continue
                seg=output[start_idx:idx+1]
                # seg 마지막 토큰 = 게(EC)
                fm=[t['morpheme']for t in seg[:-1]]
                fp=[t['pos']for t in seg[:-1]]

                def check_front_22(fp, seg):
                    l=len(fp)
                    # (V*): l=1, fp[0].startswith('V')
                    if l==1 and fp[0].startswith('V'):
                        print('===1===')
                        print(l,fp)
                        return True
                    # (NNG/MAG+XSV/XSA): l=2
                    if l==2 and fp[0] in ['NNG','MAG','XR'] and fp[1] in ['XSV','XSA','XSA-I']:
                        print('===2===')
                        return True
                    # (V*+EC+VX): l=3
                    # fp[0].startswith('V'), fp[1]=='EC', fp[2]=='VX'
                    if l==3 and fp[0].startswith('V') and fp[1]=='EC' and fp[2]=='VX':
                        print('===3===')
                        return True
                    # (XR+(XSV/XSA)+EC+VX): l=4
                    # fp[0]=='XR', fp[1]in[XSV,XSA],fp[2]=='EC',fp[3]=='VX'
                    if l==4 and seg[0]['pos']=='XR' and seg[1]['pos'] in ['XSV','XSA','XSA-I'] and seg[2]['pos']=='EC' and seg[3]['pos']=='VX':
                        print('===4===')
                        return True
                    return False

                if check_front_22(fp, seg):
                    # 패턴 잠정 매칭 성공
                    # 이제 제외 조건 체크
                    exclude=False
                    # 다음 토큰 확인
                    if idx+1 < len(output):
                        next_token = output[idx+1]
                        if next_token['morpheme'] in ['하','되'] and next_token['pos'].startswith('V'):
                            print("exclude yes")
                            exclude=True
                        if next_token['morpheme']=='.' and next_token['pos']=='SF':
                            print("exclude yes")
                            exclude=True

                    # exclude가 False면 태깅
                    if not exclude:
                        mm=''.join(t['morpheme']for t in seg)
                        merged={
                            'morpheme':mm,
                            'pos':'+'.join(t['pos']for t in seg),
                            'pos_desc':'게(EC) 패턴(22번)',
                            'matched_items':[it for it in grammatical_items if it['번호']==22],
                            'start':seg[0]['start'],
                            'len':sum(x['len']for x in seg),
                            'end':seg[-1]['end']
                        }
                        output=output[:start_idx]+[merged]+output[idx+1:]
                        idx=start_idx+1
                        matched=True
                        break
            if not matched:
                idx+=1
        else:
            idx+=1
    return output

def check_item_23(output):
    pos_desc_23 = '...대신 패턴(23번)'
    etm_candidates = ['은','는','ㄴ']
    idx=0
    while idx<len(output):
        matched=False
        # 최대 길이: 
        # (XR+(XSV/XSA)+EC+VX)+(은/는/ㄴ)+대신(NNG)+에(JKB)
        # XR,XSV,EC,VX =4토큰 +1(ETM)+1(대신)+1(에) =7토큰
        # 최소 길이: (VV)+(은/는/ㄴ)+대신(NNG) =3토큰
        for length in range(7,2,-1):
            if idx+length<=len(output):
                seg = output[idx:idx+length]
                m=[t['morpheme'] for t in seg]
                p=[t['pos'] for t in seg]

                # '대신'(NNG) 필수
                try:
                    di_idx = [i for i,(mm,pp) in enumerate(zip(m,p)) if mm=='대신' and pp=='NNG'][0]
                except:
                    continue

                # ETM 바로 앞 di_idx-1
                if di_idx-1<0:
                    continue
                if p[di_idx-1]=='ETM' and m[di_idx-1] in etm_candidates:
                    # 에(JKB) optional
                    has_e=False
                    e_idx=-1
                    if di_idx+1<len(seg) and p[di_idx+1]=='JKB' and m[di_idx+1]=='에':
                        has_e=True
                        e_idx=di_idx+1

                    # 앞부분 = seg[:di_idx-1]
                    front_part = seg[:di_idx-1]
                    # remove_ep
                    core=remove_ep(front_part)
                    if check_front_pattern_basic(core):
                        # 매칭
                        mm=''.join(m)
                        merged={
                            'morpheme':mm,
                            'pos':'+'.join(p),
                            'pos_desc':pos_desc_23,
                            'matched_items':[it for it in grammatical_items if it['번호']==23],
                            'start':seg[0]['start'],
                            'len':sum(x['len']for x in seg),
                            'end':seg[-1]['end']
                        }
                        output=output[:idx]+[merged]+output[idx+length:]
                        idx+=1
                        matched=True
                        break
        if not matched:
            idx+=1
    return output


# def check_item_24(output):
#     idx = 0
#     while idx < len(output):
#         token = output[idx]
#         if (token['morpheme'] == '다가' or token['morpheme'] == '다') and token['pos'] == 'EC':
#             # 바로 앞의 토큰이 '었'(EP)이면 제외
#             if idx >= 1:
#                 prev_token = output[idx - 1]
#                 if prev_token['morpheme'] == '었' and prev_token['pos'] == 'EP':
#                     idx += 1
#                     continue
#             # 그렇지 않으면 24번 항목으로 태깅
#             token['matched_items'] = [item for item in grammatical_items if item['번호'] == 24]
#         idx += 1
#     return output

def check_item_24(output):
    # pos_desc_24: '...다/다가 패턴(24번)'
    # 패턴 정리:
    # 1. (VV) + '다'(EC) or '다가'(EC)
    # 2. (VV)+(EP) + '다'/'다가'(EC)
    # 3. (NNG/MAG)+(XSV)+'다'/'다가'(EC)
    # 4. (NNG/MAG)+(XSV)+(EP)+'다'/'다가'(EC)
    #
    # 제외: '다가'(EC) 바로 앞에 '었'(EP)이면 제외
    
    idx=0
    while idx<len(output):
        matched=False
        # 최대 패턴 길이: 4토큰 (NNG/MAG+XSV+EP+다/다가)
        # 최소 패턴 길이: 2토큰 (VV+다/다가)
        for length in [4,3,2]:
            if idx+length<=len(output):
                seg=output[idx:idx+length]
                m=[t['morpheme']for t in seg]
                p=[t['pos']for t in seg]

                # '다' 또는 '다가'(EC) 마지막 토큰
                # 마지막 토큰이 '다' or '다가'이고 pos=='EC'
                # 다/다가 중 하나여야 함 -> '다가'나 '다'
                # '다' 어미로 쓰이는 경우 pos=='EC'로 간주
                # 혹은 '다'(EC)일 수도.
                
                last_morpheme = m[-1]
                last_pos = p[-1]
                if last_morpheme in ['다','다가'] and last_pos=='EC':
                    # 제외 조건: 만약 '다가'이고 바로 앞 토큰이 '었'(EP)이면 제외
                    if last_morpheme == '다가' and length>=2:
                        # 바로 앞 토큰 seg[-2]
                        if p[-2]=='EP' and '었' in m[-2]:
                            continue  # 제외

                    # 앞부분 패턴 체크
                    # length=2: [X,다/다가]
                    # X가 VV or (NNG/MAG+XSV) or EP 들어갈 수도
                    # 패턴별:
                    # (VV)+다/다가
                    # (VV)+(EP)+다/다가
                    # (NNG/MAG)+XSV+다/다가
                    # (NNG/MAG)+XSV+(EP)+다/다가

                    # 토큰 수별 패턴 추론:
                    # length=2: 가능 패턴: (VV)+(다/다가)
                    # length=3: (VV)+(EP)+다/다가 or (NNG/MAG)+XSV+다/다가
                    # length=4: (NNG/MAG)+XSV+(EP)+다/다가

                    def check_front_24(fp, fm):
                        fl=len(fp)
                        if fl==1:
                            # (VV)+다/다가
                            return fp[0].startswith('V')
                        if fl==2:
                            # (VV)+(EP)+다/다가 or (NNG/MAG)+XSV+다/다가
                            # if EP 있으면 [V*,EP]
                            # or [NNG/MAG,XSV]
                            if fp[1]=='EP' and fp[0].startswith('V'):
                                return True
                            if fp[0] in ['NNG','MAG'] and fp[1]=='XSV':
                                return True
                        if fl==3:
                            # (NNG/MAG)+XSV+(EP)+다/다가
                            if fp[0] in ['NNG','MAG'] and fp[1]=='XSV' and fp[2]=='EP':
                                return True
                        return False

                    front_part=seg[:-1]
                    fpos=[x['pos']for x in front_part]
                    fmorph=[x['morpheme']for x in front_part]

                    if check_front_24(fpos,fmorph):
                        # 매칭
                        mm=''.join(m)
                        merged={
                            'morpheme': mm,
                            'pos': '+'.join(p),
                            'pos_desc': '...다/다가 패턴(24번)',
                            'matched_items':[it for it in grammatical_items if it['번호']==24],
                            'start': seg[0]['start'],
                            'len': sum(x['len']for x in seg),
                            'end': seg[-1]['end']
                        }
                        output=output[:idx]+[merged]+output[idx+length:]
                        idx+=1
                        matched=True
                        break
        if not matched:
            idx+=1
    return output


def check_item_25(output):
    # pos_desc_25: '대요 패턴(25번)'
    # 매우 다양한 패턴이 있으므로 정규화:
    # 마지막 부분이 '대요', 'ㄴ대요', '대'+요(JX), '는대'+요(JX) 등
    # 앞부분: (V*) 또는 (NNG/MAG/XR+(XSV/XSA)) + EP 0개 이상 + EF + (요(JX)?)
    # 뒤에 물음표(SF) 붙는 경우 제외

    # 접근:
    # 1) '대요', 'ㄴ대요', '는대'+요, '대'+요 등을 뒤에서부터 확인
    # 2) EP 0개 이상 허용: EP는 중간에 있을 수 있음
    # 3) 앞부분 (V*) or (NNG/MAG/XR+(XSV/XSA))
    # 물음표 제외: 마지막에 태깅 직전 다음 토큰이 '?'(SF)이면 제외

    idx=0
    while idx<len(output):
        matched=False
        # 최대 패턴 길이 대략 6~7토큰 (EP 많이 들어가는 경우)
        # 최소 패턴 길이 2토큰: (V*)+대요(EF)
        for length in range(7,1,-1):
            if idx+length<=len(output):
                seg=output[idx:idx+length]
                m=[t['morpheme'] for t in seg]
                p=[t['pos'] for t in seg]

                # 패턴 끝 형태:
                # EF: 대요,ㄴ대요,대,는대
                # JX: 요
                # 가능한 끝:
                # - ...대요(EF)
                # - ...ㄴ대요(EF)
                # - ...대(EF)+요(JX)
                # - ...는대(EF)+요(JX)

                # Check ending forms:
                # 끝 1~2토큰:
                # if last token EF: 대요 or ㄴ대요
                # if last two tokens EF+JX: 대+요, 는대+요
                # EP여러개 후 EF가능
                # 먼저 요(JX) 있는지 확인
                last_pos = p[-1]
                last_morph = m[-1]
                have_y = False
                end_ok = False
                end_type = None

                # 끝이 요(JX)?
                if last_pos=='JX' and len(seg)>=2:
                    # EF 바로 앞
                    if p[-2]=='EF':
                        # (V*)+"대"(EF)+"요"(JX) or (V*)+"는대"(EF)+"요"(JX)
                        # (NNG/MAG/XR+(XSV/XSA))+"대"(EF)+"요"(JX) etc.
                        end_morph = m[-2]
                        if end_morph in ['대','는대']:
                            have_y=True
                            end_ok=True
                            end_type=end_morph+'+요'
                else:
                    # last_pos=='EF':
                    # 대요, ㄴ대요 형태 체크
                    normalized_last = normalize_morpheme(last_morph)
                    if normalized_last in ['대요','ㄴ대요']:
                        end_ok=True
                        end_type=normalized_last

                if not end_ok:
                    continue

                # EP 처리: EP 0개 이상
                # front part = seg[:-1] if EF only, seg[:-2] if EF+JX
                if have_y:
                    # EF+JX case
                    front_part=seg[:-2]
                    ef_morph=m[-2]
                    ef_pos=p[-2]
                else:
                    # EF only case
                    front_part=seg[:-1]
                    ef_morph=m[-1]
                    ef_pos=p[-1]

                # EP 제거 가능: EP 0개 이상
                def front_filter_25(tokens):
                    # EP 0개 이상 허용, EF/EC는 패턴 상 EF는 끝에만, EC미사용
                    # VX? VCP?
                    # 여기서는 EP만 제거 안 함, EP허용이라 제거하지 않아도 됨.
                    # 패턴 상 EP는 중간에 올 수 있긴 하나 패턴정의가 복잡.
                    # 여기서는 EP 제거 X, 그냥 허용.
                    return tokens

                filtered=front_filter_25(front_part)
                # Now check front pattern:
                # 앞부분: (V*) or (NNG/MAG/XR+(XSV/XSA)) + EP(s)
                # EP는 중간에 낄 수 있으나 결과적으로 실질형태
                # (V*) or (NNG/MAG/XR + XSV/XSA)
                # EP는 무시해도 패턴 식별에는 문제없음
                # EP는 허용이므로 EP 제거 후 실질 확인 필요
                # 실질 패턴: 
                # (V*) alone or with EP
                # or (NNG/MAG/XR)+(XSV/XSA) with EP in between possibly

                # EP, VX, VCP... 조건 명확히 없음
                # 여기선 단순화: EP는 몇 개든 허용하되, 
                # EP 빼고 남은 실질 형태가 (V*) 1토큰 or (NNG/MAG/XR,XSV/XSA) 2토큰이면 OK

                def remove_ep_25(tokens):
                    return [(tt['morpheme'],tt['pos']) for tt in tokens if tt['pos']!='EP']

                core=remove_ep_25(filtered)
                # core 패턴:
                # l=1: (V*)
                # l=2: (NNG/MAG/XR, XSV/XSA)
                l=len(core)
                def check_core_25(l,core):
                    if l==1:
                        # (V*)
                        return core[0][1].startswith('V')
                    if l==2:
                        # (NNG/MAG/XR, XSV/XSA)
                        return core[0][1] in ['NNG','MAG','XR'] and core[1][1] in ['XSV','XSA']
                    return False

                if check_core_25(l,core):
                    # 제외: 뒤에 물음표(SF) 붙는 경우 제외
                    # 패턴 완성 후 idx+length 위치 토큰이 '?'인지 확인
                    exclude=False
                    if idx+length<len(output):
                        next_token=output[idx+length]
                        if next_token['pos']=='SF' and next_token['morpheme']=='?':
                            exclude=True

                    if not exclude:
                        mm=''.join(t['morpheme']for t in seg)
                        merged={
                            'morpheme':mm,
                            'pos':'+'.join(t['pos']for t in seg),
                            'pos_desc':'대요/ㄴ대요/는대요 패턴(25번)',
                            'matched_items':[it for it in grammatical_items if it['번호']==25],
                            'start':seg[0]['start'],
                            'len':sum(x['len']for x in seg),
                            'end':seg[-1]['end']
                        }
                        output=output[:idx]+[merged]+output[idx+length:]
                        idx+=1
                        matched=True
                        break
        if not matched:
            idx+=1
    return output



def check_item_26(output):
    # pos_desc_26: '이래요 패턴(26번)'
    # 패턴:
    # (N*)+이(VCP)+래(EF)+요(JX)
    # (N*)+이(VCP)+래요(EF)
    # 아니(VCN)+래(EF)+요(JX)
    # 아니(VCN)+래요(EF)

    idx=0
    while idx<len(output):
        matched=False
        # 길이 최소2토큰(이+래요)
        # 최대4토큰 (N*,이,VCP,래,요)
        for length in [4,3,2]:
            if idx+length<=len(output):
                seg=output[idx:idx+length]
                m=[t['morpheme']for t in seg]
                p=[t['pos']for t in seg]

                # 패턴 분해:
                # (N*)+이(VCP)+래(EF)+요(JX) -> length=4
                # (N*)+이(VCP)+래요(EF) -> '래요' 하나로 EF토큰 처리 -> length=3
                # 아니(VCN)+래(EF)+요(JX) -> length=3
                # 아니(VCN)+래요(EF) -> length=2 (아니,래요)

                normalized_last = normalize_morpheme(m[-1])

                if length==4:
                    # (N*)+이(VCP)+래(EF)+요(JX)
                    # seg: [N*, 이(VCP), 래(EF), 요(JX)]
                    if p[0].startswith('N') and m[1]=='이' and p[1]=='VCP':
                        if m[2]=='래' and p[2]=='EF' and m[3]=='요' and p[3]=='JX':
                            merged={
                                'morpheme':''.join(m),
                                'pos':'+'.join(p),
                                'pos_desc':'이래요 패턴(26번)',
                                'matched_items':[it for it in grammatical_items if it['번호']==26],
                                'start':seg[0]['start'],
                                'len':sum(x['len']for x in seg),
                                'end':seg[-1]['end']
                            }
                            output=output[:idx]+[merged]+output[idx+4:]
                            idx+=1
                            matched=True
                if length==3 and not matched:
                    # (N*)+이(VCP)+래요(EF)
                    # [N*,이(VCP),래요(EF)]
                    # or 아니(VCN)+래(EF)+요(JX)
                    # [아니(VCN),래(EF),요(JX)]
                    if p[0].startswith('N') and m[1]=='이' and p[1]=='VCP':
                        if normalize_morpheme(m[2])=='래요' and p[2]=='EF':
                            merged={
                                'morpheme':''.join(m),
                                'pos':'+'.join(p),
                                'pos_desc':'이래요 패턴(26번)',
                                'matched_items':[it for it in grammatical_items if it['번호']==26],
                                'start':seg[0]['start'],
                                'len':sum(x['len']for x in seg),
                                'end':seg[-1]['end']
                            }
                            output=output[:idx]+[merged]+output[idx+3:]
                            idx+=1
                            matched=True
                    # 아니(VCN)+래(EF)+요(JX)
                    if not matched:
                        if m[0]=='아니' and p[0]=='VCN':
                            if m[1]=='래' and p[1]=='EF' and m[2]=='요' and p[2]=='JX':
                                merged={
                                    'morpheme':''.join(m),
                                    'pos':'+'.join(p),
                                    'pos_desc':'이래요 패턴(26번)',
                                    'matched_items':[it for it in grammatical_items if it['번호']==26],
                                    'start':seg[0]['start'],
                                    'len':sum(x['len']for x in seg),
                                    'end':seg[-1]['end']
                                }
                                output=output[:idx]+[merged]+output[idx+3:]
                                idx+=1
                                matched=True
                if length==2 and not matched:
                    # 아니(VCN)+래요(EF)
                    # [아니,래요(EF)]
                    if m[0]=='아니' and p[0]=='VCN':
                        if normalize_morpheme(m[1])=='래요' and p[1]=='EF':
                            merged={
                                'morpheme':''.join(m),
                                'pos':'+'.join(p),
                                'pos_desc':'이래요 패턴(26번)',
                                'matched_items':[it for it in grammatical_items if it['번호']==26],
                                'start':seg[0]['start'],
                                'len':sum(x['len']for x in seg),
                                'end':seg[-1]['end']
                            }
                            output=output[:idx]+[merged]+output[idx+2:]
                            idx+=1
                            matched=True
                if matched:
                    break
        if not matched:
            idx+=1
    return output

def check_item_27(output):
    # pos_desc_27: '다고요 패턴(27번)'
    # 전략: 끝에서부터 "다고요" 또는 "ᆫ다고/다고"+요 형태 판단
    # EP 0개 이상 허용, 앞부분 pattern check_front_pattern_basic
    # 뒤 '?' 제외

    idx=0
    while idx<len(output):
        matched=False
        # 패턴 길이: 최소 2토큰((V*)+다고요) ~ 최대 6토큰((XR+(XSV/XSA)+(EC)+(VX)+EP+EP+...+다고요))
        for length in range(6,1,-1):
            if idx+length<=len(output):
                seg=output[idx:idx+length]
                m=[t['morpheme']for t in seg]
                p=[t['pos']for t in seg]

                # 끝 형태: 
                # case1: "다고요"(EF) or "ᆫ다고요"(EF)
                # case2: "ᆫ다고"or"다고"(EF)+"요"(JX)
                have_yo=False
                end_ok=False
                exclude=False

                normalized_end = normalize_morpheme(m[-1])
                if p[-1]=='JX' and len(seg)>=2 and p[-2] in ['EF','EC']:
                    # EF+JX ending
                    # "다고", "ᆫ다고" + 요
                    n_end2 = normalize_morpheme(m[-2])
                    if n_end2 in ['다고','ㄴ다고','ᆫ다고']:
                        have_yo=True
                        end_ok=True
                else:
                    # EF alone
                    # "다고요", "ㄴ다고요", "ᆫ다고요"
                    if p[-1] in ['EF','EC']:
                        if normalized_end in ['다고요','ㄴ다고요','ᆫ다고요']:
                            end_ok=True

                if not end_ok:
                    continue

                # front_part:
                if have_yo:
                    # EF+JX => front_part = seg[:-2]
                    front_part=seg[:-2]
                else:
                    # EF alone => seg[:-1]
                    front_part=seg[:-1]

                # remove EP
                core=remove_ep(front_part)
                if check_front_pattern_basic(core):
                    # 물음표 제외
                    if idx+length<len(output):
                        nxt=output[idx+length]
                        if nxt['pos']=='SF' and nxt['morpheme']=='?':
                            exclude=True
                    if not exclude:
                        mm=''.join(m)
                        merged={
                            'morpheme':mm,
                            'pos':'+'.join(p),
                            'pos_desc':'다고요 패턴(27번)',
                            'matched_items':[it for it in grammatical_items if it['번호']==27],
                            'start':seg[0]['start'],
                            'len':sum(x['len']for x in seg),
                            'end':seg[-1]['end']
                        }
                        output=output[:idx]+[merged]+output[idx+length:]
                        idx+=1
                        matched=True
                        break
        if not matched:
            idx+=1
    return output

def check_item_28(output):
    # pos_desc_28: '시/으시+ㅂ시오 패턴(28번)'
    # 패턴:
    # ... + "시or으시"(EP)+"ㅂ시오"(EF)
    # 앞부분: (VV) or (NNG/MAG+XSV) or (V*+EC+VX) or (XR+(XSV/XSA)+EC+VX)

    idx=0
    while idx<len(output):
        matched=False
        # 최소 2토큰: (VV)+시/으시(EP)+ㅂ시오(EF)
        # Actually min 2토큰 impossible since need EP+EF =2토큰?
        # min: VV, 시/으시(EP), ㅂ시오(EF) =3토큰
        # max: XR+(XSV/XSA)+EC+VX+시/으시(EP)+ㅂ시오(EF) =6토큰
        for length in [6,5,4,3]:
            if idx+length<=len(output):
                seg=output[idx:idx+length]
                m=[t['morpheme']for t in seg]
                p=[t['pos']for t in seg]

                # 끝 "ㅂ시오"(EF)
                if p[-1]=='EF':
                    normalized_end=normalize_morpheme(m[-1])
                    if normalized_end=='ㅂ시오' or 'ᆸ시오' in normalized_end:
                        # 바로 앞 "시"or"으시"(EP)
                        if length>=2 and p[-2]=='EP':
                            if m[-2] in ['시','으시']:
                                # 앞부분 = seg[:-2]
                                front_part=seg[:-2]
                                # remove EP?
                                # EP는 앞부분에도 있을 수 있음, 허용
                                core=remove_ep(front_part)
                                if check_front_pattern_basic(core):
                                    mm=''.join(m)
                                    merged={
                                        'morpheme':mm,
                                        'pos':'+'.join(p),
                                        'pos_desc':'시/으시+ㅂ시오 패턴(28번)',
                                        'matched_items':[it for it in grammatical_items if it['번호']==28],
                                        'start':seg[0]['start'],
                                        'len':sum(x['len']for x in seg),
                                        'end':seg[-1]['end']
                                    }
                                    output=output[:idx]+[merged]+output[idx+length:]
                                    idx+=1
                                    matched=True
                                    break
        if not matched:
            idx+=1
    return output

def check_item_31(output):
    idx = 0
    while idx < len(output) - 1:
        token1 = output[idx]
        token2 = output[idx + 1]

        # 패턴 1: '이'(VCP) + '라든가'(EC 또는 JC 또는 JX)
        if token1['morpheme'] == '이' and token1['pos'] == 'VCP':
            if token2['morpheme'] in ['라든가', '라든지'] and token2['pos'] in ['EC', 'JC', 'JX']:
                # 두 토큰을 병합하여 처리
                merged_token = {
                    'morpheme': token1['morpheme'] + token2['morpheme'],
                    'pos': token1['pos'] + '+' + token2['pos'],
                    'pos_desc': 'VCP+' + token2['pos'],
                    'matched_items': [item for item in grammatical_items if item['번호'] == 31],
                    'start': token1['start'],
                    'len': token1['len'] + token2['len'],
                    'end': token2['end']
                }
                output = output[:idx] + [merged_token] + output[idx + 2:]
                idx += 1
                continue

        # 패턴 2: '라든가'(EC 또는 JC 또는 JX)
        if token1['morpheme'] in ['라든가', '라든지'] and token1['pos'] in ['EC', 'JC', 'JX']:
            token1['matched_items'] = [item for item in grammatical_items if item['번호'] == 31]
            idx += 1
            continue

        # 패턴 3: '이라든가'(JC 또는 JX)
        if token1['morpheme'] in ['이라든가', '이라든지'] and token1['pos'] in ['JC', 'JX']:
            token1['matched_items'] = [item for item in grammatical_items if item['번호'] == 31]
            idx += 1
            continue

        idx += 1
    return output


def check_item_32(output):
    # 32번 패턴: ... "거나"(EC/JX)+"하"(VV)+(EC or EF) ...
    # 다양한 앞부분 패턴:
    # (V*), (NNG/MAG+(XSV/XSA)), (V*+EP), (V*+EC+VX), (XR+(XSV/XSA)+EC+VX)
    # 그리고 "거나"(EC/JX)+"하"(VV) 뒤에 (EP)?+(EC/EF)
    # EP 0개 이상 허용, EP 제거 후 앞부분 패턴 판단
    # 끝 형태: "거나"(EC/JX) + "하"(VV) + (EC/EF) 또는 (EP+EF)

    idx=0
    while idx<len(output):
        matched=False
        # 최소 패턴 길이 대략 3토큰(V*+거나+하+EC), 최대 ~7토큰
        for length in range(7,2,-1):
            if idx+length<=len(output):
                seg=output[idx:idx+length]
                m=[t['morpheme'] for t in seg]
                p=[t['pos'] for t in seg]

                # 끝 형태 점검:
                # 끝 2~3토큰: "하"(VV)+(EC or EF), 또는 "하"(VV)+(EP)+(EF)
                # "하"(VV) 바로 앞 "거나"(EC/JX)
                # 즉 마지막 최소 2토큰: 하(VV)+EC/EF
                # 하(VV) 이전에 EP 있을 수 있음(EP+EF)
                # "거나"(EC/JX) 바로 앞에 앞부분 패턴
                # 구조:
                # ... + "거나"(EC/JX)+"하"(VV)+(EP?) + (EC/EF)

                # 먼저 "하"(VV) 위치 찾기
                # 뒤에서부터 '하'(VV)를 찾고, 그 뒤 (EP)*, (EC/EF)인지 체크
                try:
                    ha_idx = max(i for i,(mm,pp) in enumerate(zip(m,p)) if mm=='하' and pp.startswith('V'))
                except:
                    continue

                # ha_idx 뒤에 EP 0개 이상, 마지막은 EC/EF
                tail = seg[ha_idx+1:]
                # tail 형태: [EP*, EC/EF]
                # 최소 1토큰 tail(EC/EF), 최대 2토큰 tail(EP,EF)
                if len(tail)<1:
                    continue
                # 마지막 토큰 tail[-1]은 EC나 EF
                if p[ha_idx+1:].count('EP') == len(p[ha_idx+1:-1]) and p[-1] in ['EC','EF']:
                    # tail 구조 유효
                    # "하"(VV) 바로 앞 "거나"(EC/JX)
                    if ha_idx-1<0:
                        continue
                    if m[ha_idx-1]=='거나' and p[ha_idx-1] in ['EC','JX']:
                        # 앞부분 = seg[:ha_idx-1]
                        front_part = seg[:ha_idx-1]
                        core=remove_ep(front_part)
                        if check_front_pattern_basic(core):
                            # 매칭
                            mm=''.join(m)
                            pp='+'.join(p)
                            # pos_desc 간단히 첫 토큰 desc
                            desc = seg[0]['pos_desc']
                            matched_items = [item for t in seg for item in t['matched_items']]
                            merged={
                                'morpheme': mm,
                                'pos': pp,
                                'pos_desc': desc,
                                'matched_items': matched_items+ [it for it in grammatical_items if it['번호']==32],
                                'start':seg[0]['start'],
                                'len':sum(t['len'] for t in seg),
                                'end':seg[-1]['end']
                            }
                            output = output[:idx]+[merged]+output[idx+length:]
                            idx+=1
                            matched=True
                            break
        if not matched:
            idx+=1
    return output

def check_item_34(output):
    idx = 0
    while idx < len(output):
        matched = False
        # 길이 7~4토큰 범위 내 패턴 탐색
        for length in range(7, 3, -1): 
            if idx + length <= len(output):
                seg = output[idx:idx+length]
                m = [t['morpheme'] for t in seg]
                p = [t['pos'] for t in seg]

                # 편의 함수 정의
                def is_v(pos): return pos.startswith('V')
                def is_n(pos): return pos in ['NNG','NNB','MAG','XR']
                def is_xsvxsa(pos): return pos in ['XSV','XSA','XSA-I','XSA-R']
                def is_vx(pos): return pos.startswith('VX')
                def is_etm(pos): return pos == 'ETM'
                def is_ec(pos): return pos == 'EC'
                def is_ef(pos): return pos == 'EF'
                def is_nnb(pos): return pos == 'NNB'
                def last_is_ef_or_ec(poses): return poses[-1] in ['EF','EC']

                # 8가지 패턴 (마지막 토큰 EF 또는 EC 허용)
                # 1) (V*)+(ETM)+"척"(NNB)+"하"(XSV or VV)+(EF or EC)
                if length >= 5 and not matched:
                    if (is_v(p[0]) and is_etm(p[1]) and is_nnb(p[2]) and m[2] == '척' 
                        and ((is_xsvxsa(p[3]) or p[3].startswith('V')) and m[3].startswith('하')) 
                        and last_is_ef_or_ec(p) and length == 5):
                        matched = True

                # 2) (NNG or MAG or XR)+(XSV or XSA)+(ETM)+"척"(NNB)+"하"(XSV or VV)+(EF or EC)
                if length >= 6 and not matched:
                    if (is_n(p[0]) and is_xsvxsa(p[1]) and is_etm(p[2]) and is_nnb(p[3]) and m[3] == '척'
                        and ((is_xsvxsa(p[4]) or p[4].startswith('V')) and m[4].startswith('하'))
                        and last_is_ef_or_ec(p) and length == 6):
                        matched = True

                # 3) (V*)+(ETM)+"척하"(VX)+(EF or EC)
                if length == 4 and not matched:
                    if (is_v(p[0]) and is_etm(p[1]) and p[2].startswith('VX') and m[2].startswith('척하')
                        and last_is_ef_or_ec(p)):
                        matched = True

                # 4) (NNG or MAG or XR)+(XSV or XSA)+(ETM)+"척하"(VX)+(EF or EC)
                if length == 5 and not matched:
                    if (is_n(p[0]) and is_xsvxsa(p[1]) and is_etm(p[2]) and p[3].startswith('VX') and m[3].startswith('척하')
                        and last_is_ef_or_ec(p)):
                        matched = True

                # 5) (V*)+(EC)+(VX)+"척"(NNB)+"하"(XSV or VV)+(EF or EC)
                if length == 6 and not matched:
                    if (is_v(p[0]) and is_ec(p[1]) and is_vx(p[2]) and is_nnb(p[3]) and m[3] == '척'
                        and ((is_xsvxsa(p[4]) or p[4].startswith('V')) and m[4].startswith('하'))
                        and last_is_ef_or_ec(p)):
                        matched = True

                # 6) (XR)+(XSV or XSA)+(EC)+(VX)+"척"(NNB)+"하"(XSV or VV)+(EF or EC)
                if length == 7 and not matched:
                    if (p[0] == 'XR' and is_xsvxsa(p[1]) and is_ec(p[2]) and is_vx(p[3])
                        and is_nnb(p[4]) and m[4] == '척'
                        and ((is_xsvxsa(p[5]) or p[5].startswith('V')) and m[5].startswith('하'))
                        and last_is_ef_or_ec(p)):
                        matched = True

                # 7) (V*)+(EC)+(VX)+"척하"(VX)+(EF or EC)
                if length == 5 and not matched:
                    if (is_v(p[0]) and is_ec(p[1]) and is_vx(p[2]) and p[3].startswith('VX') and m[3].startswith('척하')
                        and last_is_ef_or_ec(p)):
                        matched = True

                # 8) (XR)+(XSV or XSA)+(EC)+(VX)+"척하"(VX)+(EF or EC)
                if length == 6 and not matched:
                    if (p[0] == 'XR' and is_xsvxsa(p[1]) and is_ec(p[2]) and is_vx(p[3])
                        and p[4].startswith('VX') and m[4].startswith('척하')
                        and last_is_ef_or_ec(p)):
                        matched = True

                if matched:
                    mm = ''.join(m)
                    merged = {
                        'morpheme': mm,
                        'pos': '+'.join(p),
                        'pos_desc': '척하다 패턴(34번)',
                        'matched_items': [it for it in grammatical_items if it['번호'] == 34],
                        'start': seg[0]['start'],
                        'len': sum(t['len'] for t in seg),
                        'end': seg[-1]['end']
                    }
                    output = output[:idx] + [merged] + output[idx+length:]
                    idx += 1
                    break

        if not matched:
            idx += 1
    return output


def check_item_36(output):
    idx = 0
    while idx < len(output) - 2:
        token1 = output[idx]
        token2 = output[idx + 1]
        token3 = output[idx + 2]

        # 패턴 1: '웬만'(XR) + '하'(XSA) + '면'(EC)
        if token1['morpheme'] == '웬만' and token1['pos'] == 'XR':
            if token2['morpheme'] == '하' and token2['pos'] == 'XSA':
                if token3['morpheme'] == '면' and token3['pos'] == 'EC':
                    # 세 토큰을 병합하여 처리
                    merged_token = {
                        'morpheme': '웬만하면',
                        'pos': '+'.join([token1['pos'], token2['pos'], token3['pos']]),
                        'pos_desc': 'XR+XSA+EC',
                        'matched_items': [item for item in grammatical_items if item['번호'] == 36],
                        'start': token1['start'],
                        'len': token1['len'] + token2['len'] + token3['len'],
                        'end': token3['end']
                    }
                    output = output[:idx] + [merged_token] + output[idx + 3:]
                    idx += 1
                    continue

        # 패턴 2: '웬만하'(VA) + '면'(EC)
        if token1['morpheme'] == '웬만하' and token1['pos'] == 'VA':
            if token2['morpheme'] == '면' and token2['pos'] == 'EC':
                # 두 토큰을 병합하여 처리
                merged_token = {
                    'morpheme': '웬만하면',
                    'pos': '+'.join([token1['pos'], token2['pos']]),
                    'pos_desc': 'VA+EC',
                    'matched_items': [item for item in grammatical_items if item['번호'] == 36],
                    'start': token1['start'],
                    'len': token1['len'] + token2['len'],
                    'end': token2['end']
                }
                output = output[:idx] + [merged_token] + output[idx + 2:]
                idx += 1
                continue
        idx += 1
    return output

# def check_item_37(output):
#     idx = 0
#     while idx < len(output):
#         matched = False

#         # 패턴 개요:
#         # 끝부분에 "나"(EC or EF)+"보"(VX)+EF 형태가 반드시 등장
#         # 앞부분에 (V*) 또는 (NNG/MAG/XR+(XSV/XSA)) 뒤에 EP나 EC, VX 등이 들어갈 수 있음
#         # 다양한 EP/EC/VX 패턴 허용.

#         # 편의 함수
#         def is_v(pos): return pos.startswith('V')
#         def is_n(pos): return pos in ['NNG','MAG','XR']
#         def is_xsvxsa(pos): return (pos.startswith('XSV') or pos.startswith('XSA')) or pos in ['XSV','XSA','XSA-I','XSA-R']
#         def is_vx(pos): return pos.startswith('VX')
#         def is_ep(pos): return pos == 'EP'
#         def is_ec(pos): return pos == 'EC'
#         def is_ef(pos): return pos == 'EF'

#         def remove_ep_ec_vx(tokens):
#             result = []
#             for t in tokens:
#                 mm = t['morpheme']
#                 pp = t['pos']
#                 if pp not in ['EP','EC','VX']:
#                     result.append((mm, pp))
#             return result

#         # 최대 길이: EP,EC,VX 등이 많을 수 있으므로 넉넉히 10토큰까지 탐색
#         for length in range(10,2,-1):
#             if idx+length <= len(output):
#                 seg = output[idx:idx+length]
#                 m = [t['morpheme'] for t in seg]
#                 p = [t['pos'] for t in seg]

#                 # 마지막 종결어미(EF) 확인
#                 if not is_ef(p[-1]):
#                     continue

#                 # 끝에서 2번째 토큰이 "보(VX)"인지
#                 if length<2:
#                     continue
#                 if not (is_vx(p[-2]) and m[-2]=='보'):
#                     continue

#                 # 끝에서 3번째 토큰이 "나"인지, 나(EC or EF)인지
#                 if length<3:
#                     continue
#                 if not (m[-3]=='나' and (is_ec(p[-3]) or is_ef(p[-3]))):
#                     continue

#                 # 여기까지: ... 나(EC/EF) + 보(VX) + EF 매칭 성공

#                 # 앞부분 검사: seg[:-3]
#                 front_part = seg[:-3]
#                 core = remove_ep_ec_vx(front_part)

#                 # core가 비면 안 됨
#                 if not core:
#                     continue

#                 # core 패턴 체크: 
#                 # (V*) 또는 (N*/MAG/XR + XSV/XSA) 형태가 마지막 실질 형태로 존재해야 함
#                 # core = [(mm,pp),...]
#                 def valid_front_core(c):
#                     # 하나일 경우 V*면 OK
#                     if len(c)==1:
#                         return c[0][1].startswith('V')
#                     # 두 개 이상일 경우:
#                     # 마지막 두 토큰이 (N*/MAG/XR, XSV/XSA)면 OK
#                     if len(c)>=2:
#                         # 마지막 두 토큰
#                         if c[-2][1] in ['NNG','MAG','XR'] and is_xsvxsa(c[-1][1]):
#                             return True
#                         # 또는 마지막이 V*여도 가능
#                         if c[-1][1].startswith('V'):
#                             return True
#                     return False

#                 if valid_front_core(core):
#                     # 매칭
#                     mm=''.join(m)
#                     merged = {
#                         'morpheme': mm,
#                         'pos': '+'.join(p),
#                         'pos_desc': '...나(EC/EF)+보(VX)+EF... 패턴(37번)',
#                         'matched_items': [it for it in grammatical_items if it['번호']==37],
#                         'start': seg[0]['start'],
#                         'len': sum(t['len'] for t in seg),
#                         'end': seg[-1]['end']
#                     }
#                     output = output[:idx] + [merged] + output[idx+length:]
#                     idx += 1
#                     matched = True
#                     break

#         if not matched:
#             idx += 1
#     return output

def check_item_37(output):
    idx = 0
    while idx < len(output) - 2:
        token1 = output[idx]
        token2 = output[idx + 1]
        token3 = output[idx + 2]

        # 패턴 1: '나'(EC) + '보'(VX) + EF(모든 종결어미)
        if token1['morpheme'] == '나' and token1['pos'] == 'EC':
            if token2['morpheme'] == '보' and token2['pos'] == 'VX':
                if token3['pos'] == 'EF':
                    # 세 토큰을 병합하여 처리
                    merged_token = {
                        'morpheme': '나보' + token3['morpheme'],
                        'pos': token1['pos'] + '+' + token2['pos'] + '+' + token3['pos'],
                        'pos_desc': '연결 어미+보조 용언+종결 어미',
                        'matched_items': [item for item in grammatical_items if item['번호'] == 37],
                        'start': token1['start'],
                        'len': token1['len'] + token2['len'] + token3['len'],
                        'end': token3['end']
                    }
                    output = output[:idx] + [merged_token] + output[idx + 3:]
                    idx += 1
                    continue

        # 패턴 2: '나'(EF) + '보'(VX) + EF(모든 종결어미)
        if token1['morpheme'] == '나' and token1['pos'] == 'EF':
            if token2['morpheme'] == '보' and token2['pos'] == 'VX':
                if token3['pos'] == 'EF':
                    # 세 토큰을 병합하여 처리
                    merged_token = {
                        'morpheme': '나보' + token3['morpheme'],
                        'pos': token1['pos'] + '+' + token2['pos'] + '+' + token3['pos'],
                        'pos_desc': '종결 어미+보조 용언+종결 어미',
                        'matched_items': [item for item in grammatical_items if item['번호'] == 37],
                        'start': token1['start'],
                        'len': token1['len'] + token2['len'] + token3['len'],
                        'end': token3['end']
                    }
                    output = output[:idx] + [merged_token] + output[idx + 3:]
                    idx += 1
                    continue
        idx += 1
    return output


def check_item_38(output):
    idx = 0
    excluded_bases = ['아무', '언제', '어떻게', '무엇', '어디', '누구', '어떤', '어느']
    while idx < len(output):
        token = output[idx]

        # 패턴 1: '이'(VCP) + '라도'(EC)
        if token['morpheme'] == '이' and token['pos'] == 'VCP':
            if idx + 1 < len(output):
                next_token = output[idx + 1]
                if next_token['morpheme'] == '라도' and next_token['pos'] == 'EC':
                    # 두 토큰을 병합하여 처리
                    merged_token = {
                        'morpheme': token['morpheme'] + next_token['morpheme'],
                        'pos': token['pos'] + '+' + next_token['pos'],
                        'pos_desc': 'VCP+EC',
                        'matched_items': [item for item in grammatical_items if item['번호'] == 38],
                        'start': token['start'],
                        'len': token['len'] + next_token['len'],
                        'end': next_token['end']
                    }
                    output = output[:idx] + [merged_token] + output[idx + 2:]
                    idx += 1
                    continue

        # 패턴 2: '라도'(JX)
        if token['morpheme'] == '라도' and token['pos'] == 'JX':
            # 제외 조건 검사
            exclude = False
            if idx > 0:
                prev_token = output[idx - 1]
                combined_morpheme = prev_token['morpheme'] + token['morpheme']
                if any(combined_morpheme.startswith(base) for base in excluded_bases):
                    exclude = True
            else:
                # 이전 토큰이 없으면 제외 단어가 아님
                pass

            if not exclude:
                # 태깅
                token['matched_items'] = [item for item in grammatical_items if item['번호'] == 38]
            idx += 1
            continue

        # 패턴 3: '이라도'(JX)
        if token['morpheme'] == '이라도' and token['pos'] == 'JX':
            # 제외 조건 검사
            exclude = False
            if idx > 0:
                prev_token = output[idx - 1]
                combined_morpheme = prev_token['morpheme'] + token['morpheme']
                if any(combined_morpheme.startswith(base) for base in excluded_bases):
                    exclude = True
            else:
                # 이전 토큰이 없으면 제외 단어가 아님
                pass

            if not exclude:
                # 태깅
                token['matched_items'] = [item for item in grammatical_items if item['번호'] == 38]
            idx += 1
            continue

        idx += 1
    return output


def check_item_39(output):
    idx = 0
    while idx < len(output) - 3:
        token1 = output[idx]
        token2 = output[idx + 1]
        token3 = output[idx + 2]
        token4 = output[idx + 3]

        # 패턴 1: '에'(JKB) + '비'(NNG) + '하'(XSV) + '면'(EC)
        if token1['morpheme'] == '에' and token1['pos'] == 'JKB':
            if token2['morpheme'] == '비' and token2['pos'] == 'NNG':
                if token3['morpheme'] == '하' and token3['pos'] == 'XSV':
                    if token4['morpheme'] == '면' and token4['pos'] == 'EC':
                        # 네 토큰을 병합하여 처리
                        merged_token = {
                            'morpheme': '에비하면',
                            'pos': '+'.join([t['pos'] for t in [token1, token2, token3, token4]]),
                            'pos_desc': 'JKB+NNG+XSV+EC',
                            'matched_items': [item for item in grammatical_items if item['번호'] == 39],
                            'start': token1['start'],
                            'len': sum([t['len'] for t in [token1, token2, token3, token4]]),
                            'end': token4['end']
                        }
                        output = output[:idx] + [merged_token] + output[idx + 4:]
                        idx += 1
                        continue

        # 패턴 2: '에'(JKB) + '비하'(VV) + '면'(EC)
        if token1['morpheme'] == '에' and token1['pos'] == 'JKB':
            if token2['morpheme'] == '비하' and token2['pos'] == 'VV':
                if token3['morpheme'] == '면' and token3['pos'] == 'EC':
                    # 세 토큰을 병합하여 처리
                    merged_token = {
                        'morpheme': '에비하면',
                        'pos': '+'.join([token1['pos'], token2['pos'], token3['pos']]),
                        'pos_desc': 'JKB+VV+EC',
                        'matched_items': [item for item in grammatical_items if item['번호'] == 39],
                        'start': token1['start'],
                        'len': token1['len'] + token2['len'] + token3['len'],
                        'end': token3['end']
                    }
                    output = output[:idx] + [merged_token] + output[idx + 3:]
                    idx += 1
                    continue

        # 패턴 3: '비'(NNG) + '하'(XSV) + '면'(EC)
        if token1['morpheme'] == '비' and token1['pos'] == 'NNG':
            if token2['morpheme'] == '하' and token2['pos'] == 'XSV':
                if token3['morpheme'] == '면' and token3['pos'] == 'EC':
                    # 세 토큰을 병합하여 처리
                    merged_token = {
                        'morpheme': '비하면',
                        'pos': '+'.join([token1['pos'], token2['pos'], token3['pos']]),
                        'pos_desc': 'NNG+XSV+EC',
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

        # 기존 패턴: '다고'(EC) + '보'(VV), '라고'(EC) + '보'(VV)
        if token1['morpheme'] in ['는다고','다고', '라고'] and token1['pos'] == 'EC':
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

        # 추가 패턴: '는다'(EC) + '보'(VV)
        if token1['morpheme'] == '는다' and token1['pos'] == 'EC':
            if token2['morpheme'] == '보' and token2['pos'] == 'VV':
                # 두 토큰을 병합하여 처리
                merged_token = {
                    'morpheme': '는다보',
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
    """
    '나' 또는 '이나'(JX or JC)를 45번으로 태깅하는 규칙:

    기본 태깅 조건(세 가지 중 하나):
    1. (EC)+(N*)+"나/이나"(JX/JC)
    2. "나/이나"(JX/JC)+(VV)
    3. "나/이나"(JX/JC)+(MAG)+(V*)

    제외 조건:
    1. (N*)+"나/이나"(JX/JC)+(N*) → 제외
    2. "나/이나"(JX/JC)+(VV)+'니까'(EF) → 제외
    3. "나/이나"(JX/JC) 앞에 '아무' 있으면 제외
    4. "나/이나"(JX/JC) 앞에 '어떤' 있으면 제외
    5. SN+NNB+"나/이나"(JX/JC) → 제외
    """

    candidates = ['나', '이나']
    candidate_pos = ['JX','JC']

    def is_ec(pos): return pos == 'EC'
    def is_ef(pos): return pos == 'EF'
    def is_vv(pos): return pos.startswith('V')  # VV: 동사, VA, VX 모두 V로 시작하므로 V*
    def is_n(pos): return pos.startswith('N')   # N* : NNG, NNP, NNB, NP 등
    def is_jx_jc(pos): return pos in candidate_pos
    def is_mag(pos): return pos == 'MAG'
    def is_sn(pos): return pos == 'SN'
    def is_nnb(pos): return pos == 'NNB'

    i = 0
    while i < len(output):
        tok = output[i]
        m = tok['morpheme']
        p = tok['pos']

        if m in candidates and is_jx_jc(p):
            # 나/이나 토큰 i
            prev_tok = output[i-1] if i-1>=0 else None
            prev2_tok = output[i-2] if i-2>=0 else None
            next_tok = output[i+1] if i+1<len(output) else None
            next2_tok = output[i+2] if i+2<len(output) else None

            # 제외 조건 먼저 체크
            # (3) '아무' 앞에 있는지 확인
            if prev_tok and prev_tok['morpheme'] in ['아무','어떤']:
                i += 1
                continue

            # (5) SN+NNB+나/이나
            if prev_tok and prev2_tok and is_sn(prev2_tok['pos']) and is_nnb(prev_tok['pos']):
                i += 1
                continue

            # (1) (N*)+나/이나+(N*)
            # prev=n*, next=n*
            if prev_tok and next_tok and is_n(prev_tok['pos']) and is_n(next_tok['pos']):
                i += 1
                continue

            # 기본 조건 검사
            cond1 = False
            # (EC)+(N*)+나/이나: prev2=EC, prev=N*, cur=나/이나
            if prev_tok and prev2_tok:
                if is_n(prev_tok['pos']) and is_ec(prev2_tok['pos']):
                    cond1 = True

            cond2 = False
            # 나/이나+VV: cur=나/이나, next=VV
            if next_tok and is_vv(next_tok['pos']):
                cond2 = True

            cond3 = False
            # 나/이나+MAG+(V*): cur=나/이나, next=MAG, next2=V*
            # V* = VV, VA, VX ... 모두 pos.startswith('V')
            if next_tok and next2_tok:
                if is_mag(next_tok['pos']) and next2_tok['pos'].startswith('V'):
                    cond3 = True

            # 제외 조건2: 나/이나+VV+'니까'(EF)
            # cond2성립 시 나/이나+VV 상태, next2=EF '니까' 포함하면 제외
            if cond2:
                if i+2<len(output):
                    next2_tok = output[i+2]
                    if is_ef(next2_tok['pos']) and '니까' in next2_tok['morpheme']:
                        i += 1
                        continue

            # 조건 충족 시 태깅
            if cond1 or cond2 or cond3:
                tok['matched_items'].append({
                    '번호': 45,
                    '형태': '나/이나',
                    '품사': 'JX/JC',
                    '의미': '차선의 선택을 나타내는 조사. 만족스럽지는 않지만 차선의 선택임을 나타낸다.'
                })

        i += 1

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
    def normalize_morpheme(m):
        # 필요시 음절 정규화할 수 있으나 여기서는 그대로 반환
        return m

    # 49번 문법 항목 가져오기
    item_49 = [it for it in grammatical_items if it['번호'] == 49]
    
    idx = 0
    while idx < len(output) - 1:
        token1 = output[idx]
        token2 = output[idx + 1]

        morpheme1 = normalize_morpheme(token1['morpheme'])
        morpheme2 = normalize_morpheme(token2['morpheme'])

        # '었/았/였'(EP) + '더라면'(EC) 패턴 확인
        # EP 토큰에서 '었','았','였' 중 하나가 들어있어야 함
        if token1['pos'] == 'EP' and any(x in morpheme1 for x in ['었','았','였']):
            if token2['morpheme'] == '더라면' and token2['pos'] == 'EC':
                # 이제 문장 내에서 '었/았/였을 텐데' 패턴:
                # EP(었/았/였)+을(ETM)+터(NNB)+이(VCP)+ㄴ데(EF) 조합 찾기
                idx_search = idx + 2
                found_pattern = False
                while idx_search < len(output) - 4:
                    # 패턴 길이 최소 5토큰: EP + 을(ETM) + 터(NNB) + 이(VCP) + ㄴ데(EF)
                    e1, e2, e3, e4, e5 = output[idx_search:idx_search+5]

                    morpheme_e1 = normalize_morpheme(e1['morpheme'])
                    morpheme_e2 = normalize_morpheme(e2['morpheme'])
                    morpheme_e3 = normalize_morpheme(e3['morpheme'])
                    morpheme_e4 = normalize_morpheme(e4['morpheme'])
                    morpheme_e5 = normalize_morpheme(e5['morpheme'])

                    # EP(었/았/였), 을(ETM), 터(NNB), 이(VCP), ㄴ데(EF)
                    # 'ㄴ데', 'ᆫ데' 포함여부 확인
                    if e1['pos'] == 'EP' and any(x in morpheme_e1 for x in ['었','았','였']):
                        if morpheme_e2 == '을' and e2['pos'] == 'ETM':
                            if morpheme_e3 == '터' and e3['pos'] == 'NNB':
                                if morpheme_e4 == '이' and e4['pos'] == 'VCP':
                                    if ('ㄴ데' in morpheme_e5 or 'ᆫ데' in morpheme_e5) and e5['pos'] == 'EF':
                                        # 패턴 발견
                                        found_pattern = True
                                        # 병합 로직:
                                        # 첫 패턴: token1+token2 병합 -> "었더라면"
                                        merged_token1 = {
                                            'morpheme': token1['morpheme'] + token2['morpheme'],
                                            'pos': token1['pos'] + '+' + token2['pos'],
                                            'pos_desc': 'EP+EC',
                                            'matched_items': item_49.copy(),
                                            'start': token1['start'],
                                            'len': token1['len'] + token2['len'],
                                            'end': token2['end']
                                        }

                                        # 두 번째 패턴: e1+e2+e3+e4+e5 병합 -> "었을터인데"
                                        merged_morpheme2 = e1['morpheme'] + e2['morpheme'] + e3['morpheme'] + e4['morpheme'] + e5['morpheme']
                                        merged_pos2 = '+'.join([e1['pos'], e2['pos'], e3['pos'], e4['pos'], e5['pos']])

                                        merged_token2 = {
                                            'morpheme': merged_morpheme2,
                                            'pos': merged_pos2,
                                            'pos_desc': 'EP+ETM+NNB+VCP+EF',
                                            'matched_items': item_49.copy(),
                                            'start': e1['start'],
                                            'len': sum(x['len'] for x in [e1,e2,e3,e4,e5]),
                                            'end': e5['end']
                                        }

                                        # output 재구성
                                        # token1, token2 병합 -> merged_token1
                                        # e1~e5 병합 -> merged_token2
                                        # 중간 토큰들 제거
                                        output = output[:idx] + [merged_token1] + output[idx+2:idx_search] + [merged_token2] + output[idx_search+5:]
                                        # 재설정
                                        idx = idx_search + 1
                                        break
                    idx_search += 1
                # 패턴 못 찾으면 그냥 진행
        idx += 1
    return output



def check_item_50(output):
    idx = 0
    while idx < len(output) - 2:
        token1 = output[idx]
        token2 = output[idx + 1]
        token3 = output[idx + 2]
        if token1['morpheme'] in ['을', 'ㄹ','ᆯ'] and token1['pos'] == 'ETM':
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

# 메인 프로세스 함수
async def process_text(text):
    # 형태소 분석 수행
    analyzed_results = kiwi_analyzer.analyze(text)
    # print("==analyzed_results==",analyzed_results)
    # 문장 단위로 분리.
    output = pos_tag_print(analyzed_results)
    # print("==output==",output)
    sentences = split_sentences(output)
    # 각 문장별로 처리
    final_output = []
    for sentence_tokens in sentences:
        processed_sentence, gpt_cache = await check_logic(sentence_tokens)
        save_cache(gpt_cache) # 항상 캐쉬 저장
        final_output.extend(processed_sentence)
        
    ### 'matched_items'가 비어있으면 삭제 # 필요 시 아래 로직은 제거
    # final_output = [
    # {'morpheme': item['morpheme']} if not item['matched_items'] else item
    #     for item in final_output
    # ]
    ###
    
    return final_output

# 이하 필요한 함수들 정의
# pos_tag_print, split_sentences, check_logic 등

def pos_tag_print(results):
    output = []
    # 형태소 분석 결과와 문법 항목 매핑
    for tokens, score in results:
        for token in tokens:
            morpheme = token.form  # 형태소 (form)
            pos = token.tag        # 품사 태그 (tag)
            start = token.start    # 형태소의 시작 인덱스
            length = token.len     # 형태소의 길이
            end = start + length   # 형태소의 끝 인덱스 계산
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
                'matched_items': matched_items,
                'start': start,
                'len': length,
                'end': end
            })
    return output

async def check_logic(sentence_tokens):
    
    output = all_text = sentence_tokens # GPT에 쓰임
    output = check_item_1(output)
    
    output = check_item_4(output)
    output = check_item_6(output)
    
    output = check_item_11(output)
    output = check_item_7(output)
    
    output = check_item_8(output)
    output = check_item_9(output)
    output = check_item_2(output)   
    
    
    output = check_item_12(output)
    
    output = check_item_31(output)
    output = check_item_32(output)
    output = check_item_13(output)
    
    output = check_item_14(output)
    output = check_item_15(output)
    
    output = check_item_18(output)
    
    output = check_item_43(output)
    output = check_item_45(output)
    
    output = check_item_19(output)
    output = check_item_20(output)
    output = check_item_21(output)
    
    output = check_item_23(output)

    output = check_item_28(output)
    # output = check_item_30(output)
    
    # output = check_item_33(output)
    output = check_item_34(output)
    # output = check_item_35(output)
    output = check_item_36(output)
    output = check_item_37(output)
    output = check_item_38(output)
    output = check_item_39(output)
    output = check_item_40(output)
    output = check_item_42(output)
    
    output = check_item_44(output)
    
    output = check_item_46(output)
    output = check_item_48(output)
    output = check_item_49(output)
    output = check_item_50(output)
    
    #최저 우선순위가 되어야 하는 것들
    output = check_item_22(output)
    output = check_item_24(output)
    output = check_item_25(output)
    output = check_item_26(output)
    output = check_item_27(output)
    
    output = check_item_10(output)
    output = check_item_17(output)
    
    output = check_item_5(output) #맨 마지막
    output = check_item_16(output)
    
    assigned_indices = set()

    # 공백 없이 이어진 토큰 병합 로직(양쪽)
    output = merge_no_space_tokens_both_sides(output)
    
    # # gpt 이용 부문.
    # # @@ 여기서 gpt가 답을 고르지 못한 경우 None 태그를 만들어서 이 경우엔 기본 태그가 나오게 하자.
    # # 최종, 태그가 2개 이상 있는 경우 해당 태그를 llm모델에 맡겨서 뭐가 맞는지 판단하게 함.
    # GPT 이용 부분
    for idx, token in enumerate(output):
        if len(token["matched_items"]) >= 2:
            # 이전 토큰과 다음 토큰을 가져옵니다.
            pre_token = output[idx - 1]["morpheme"] if idx > 0 else ''
            now_token = token["morpheme"]
            after_token = output[idx + 1]["morpheme"] if idx + 1 < len(output) else ''

            # 문장 전체 텍스트를 재구성합니다.
            sentence_text = ''.join(tok['morpheme'] for tok in output)

            # GPT 입력값 생성
            gpt_input = {
                'sentence_text': sentence_text,
                'matched_items': token["matched_items"],
                'pna_token': pre_token + now_token + after_token,
                'now_token': now_token
            }
            # 0번 태그 삽입
            # token['matched_items'].insert(0,{'번호': 0,'형태': token['morpheme'],'품사': token['pos'],'의미': token['pos_desc']}) # 기존 형태의 품사(nlp가 분류한 더 큰 집합[분류]의 품사)를 넣고 비교
            # GPT 입력값을 문자열로 변환하여 캐시의 키로 사용
            gpt_input_str = json.dumps(gpt_input, ensure_ascii=False)

            # 캐시에 결과가 있는지 확인
            if gpt_input_str in gpt_cache:
                # 캐시에서 결과 가져오기
                correct_tag = gpt_cache[gpt_input_str]
                print("캐시 사용됨")
            else:
                try:
                    print("GPT 사용됨")
                    # GPT 함수 호출을 비동기적으로 처리
                    gpt_answer = await asyncio.to_thread(
                        get_correct_tag,
                        sentence_text,
                        token["matched_items"],
                        pre_token + now_token + after_token,
                        now_token
                    )
                    correct_tag = int(re.findall(r'\d+', gpt_answer)[0])  # GPT 응답에서 숫자 추출
                    print("GPT가 정답으로 만든 태그",correct_tag)
                    # 캐시에 결과 저장
                    gpt_cache[gpt_input_str] = correct_tag

                    # 캐시 파일 저장
                    # save_cache(gpt_cache)
                    
                except Exception as e:
                    print("GPT 오류:", e)
                    correct_tag = 0  # GPT 응답 없을 경우 기본 태그 사용
            ########## 답이 여전히 여러개의 경우, 90번 이후는 gpt에 도움을 주기 위한 태깅 => 0번으로 태깅 ##########
            if len(token["matched_items"]) >= 3 or correct_tag >= 90:
                print("답이 여전히 여러개의 경우 이거나, 90번 이후는 gpt에 도움을 주기 위한 태깅=> 0 번으로 태깅")
                correct_tag = 0
            ########## 답이 여전히 여러개의 경우 => 0번으로 태깅 ##########
            if correct_tag == 0: # 0번의 경우 그대로 태깅
                token['matched_items'] = []
            else:
                item = next((item for item in token['matched_items'] if item['번호'] == correct_tag), None)
                if item:
                    token['matched_items'] = [item]
        else:
            # 태그가 1개인 경우 패스
            pass

    print("output",output)
    # 최종 결과 출력
    for token in output:
        morpheme = token['morpheme']
        pos = token['pos']
        pos_desc = token['pos_desc']
        start = token['start']
        length = token['len']
        matched_items = token['matched_items']

        if matched_items and (matched_items[0]['번호'] != 0):
            for item in matched_items:
                print(f"형태소 '{morpheme}' (위치: {start}, 길이: {length}, 품사: {pos} - {pos_desc})는 문법 항목 번호 {item['번호']}에 해당합니다: {item['의미']}")
        else:
            print(f"형태소 '{morpheme}' (위치: {start}, 길이: {length}, 품사: {pos} - {pos_desc})")
            

    # print(gpt_cache)
    return output, gpt_cache  # 수정된 output 리스트 반환
