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


from kiwipiepy import Kiwi

class KiwiAnalyzer:
    def __init__(self):
        self.kiwi = Kiwi(
            num_workers=0,
            model_path=None,
            load_default_dict=True,
            integrate_allomorph=True,
            model_type='sbg',
            typos=None,
            typo_cost_threshold=2.5
        )

    def analyze(self, text):
        return self.kiwi.analyze(text)