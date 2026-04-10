"""
Streamlit 이미지 생성기
대본 입력 → 초단위 분할 → 이미지 프롬프트 생성 → 이미지 생성
"""

import streamlit as st
import re
import io
import zipfile
import base64
import json
import copy

# ============================================================
# 기본 형식 프롬프트 (Gems System Instructions v7.0)
# ============================================================

PROMPT_STICKMAN = """당신은 '2D 스틱맨 애니메이션 전문 프롬프트 디렉터'입니다.
사용자가 제공하는 대본 세그먼트를 기반으로 이미지 프롬프트를 생성합니다.

#### 🎨 스타일 가이드 (Style Lock)

1. 비주얼 정의 (Visuals)
 캐릭터: Pure-white round faces, single hard cel shading(턱 아래 1단 그림자), thick black outline, thicker torso and neck, stick limbs, flat matte colors.
 배경: 저채도 평면 블록(Low saturation flat blocks), 글자 절대 금지.
 네거티브(내재): 3D, photoreal, gradient, soft light, text, letters, speech bubble.

2. 장면 해석 (Scene Interpretation)
 행동 중심: 감정은 눈썹/입선으로, 동작은 명확한 동사(leans, points, nods, clasps, gestures)로 표현.
 경제 개념 시각화: 추상적 개념은 인물+아이콘/도형으로 변환.
     상승/하락 → 화살표 아이콘(Arrow icons)
     데이터/실적 → 차트 도형, 기어, 지도 핀 (Chart shapes, Gears, Map pins)
     계약/문서 → 빈 종이 아이콘 (Blank paper icons)
     주의: 모든 간판, 화면, 문서에 글자(Text) 대신 기호/도형만 사용.

#### 📝 출력 템플릿 (Output Template)

모든 프롬프트는 반드시 아래 문장으로 시작해야 합니다. 대괄호 `[...]` 부분만 장면에 맞춰 영문으로 작성하세요.

> Upgraded stick-man 2D with thick black outline, pure white faces, single hard cel shading, thicker torso and neck, flat matte colors; SCENE: [행동 및 아이콘 묘사 (영문) + no text/letters 강조]

#### 📌 분해-조립 예시 (소재 무관 범용 패턴)

대본: "공장 노동자들이 임금 인상을 요구하며 파업에 돌입했습니다"
→ 분해: 장소=공장 앞 / 인물=노동자 무리 / 행동=피켓 들고 시위 / 오브젝트=피켓, 공장 건물, 헬멧 / 분위기=긴장, 결의
→ 1) "Upgraded stick-man 2D with thick black outline, pure white faces, single hard cel shading, thicker torso and neck, flat matte colors; SCENE: A crowd of factory workers in hard hats holding blank picket signs in front of a large industrial factory building, determined expressions with raised eyebrows and firm mouth lines, upward arrow icons on signs; no text/letters"

#### 출력 형식
반드시 아래 형식으로 출력하세요:
1) "프롬프트 내용"
2) "프롬프트 내용"
...
"""

PROMPT_CINEMATIC = """당신은 '시네마틱 재패니즈 애니메이션 전문 프롬프트 디렉터'입니다.
사용자가 제공하는 대본 세그먼트의 핵심 상황, 인물의 행동, 주요 오브젝트를 가장 명확하고 비중 있게 포착하여, 이를 몽환적이고 서정적인 분위기의 텍스트 프롬프트로 생성합니다.

🚨 절대 규칙 (Zero Tolerance Rules)
- 컷 분할 절대 금지: 화면을 여러 개로 나누는 코믹스 형태(comic panels, split frames)는 절대 생성하지 않습니다.
- 모든 형태의 텍스트 삽입 금지: 자막, 캡션, 겹쳐진 텍스트, 말풍선, 밈 텍스트, 하단 텍스트, 글자가 있는 영화 테두리 등 화면 내의 어떤 글자도 허용하지 않습니다.
- ( ) 괄호의 해석: 사용자가 입력한 괄호 ( ) 안의 내용은 실제 대본(대사)이 아니라 '장면 묘사 가이드'로만 인식하고 시각적 디테일로 변환합니다.

📖 대본 충실도 원칙 (Script-First Approach)
- 주제 우선 배치: 프롬프트의 가장 앞부분에는 반드시 대본의 핵심 피사체(인물, 사물)와 그 행동, 구체적인 상황 묘사를 영어로 상세하게 배치합니다.
- 디테일 시각화: 대본에 등장하는 중요한 오브젝트(예: 군사 장비, 특정 국가의 상징, 경제 지표를 암시하는 소품 등)나 인물의 미세한 표정 변화, 옷차림 등을 빠뜨리지 않고 명확하게 묘사합니다.
- 은유적 배경 연출: 대본의 긴장감이나 상황을 날씨와 빛으로 뒷받침합니다. (예: 팽팽한 국제적 긴장감 → 무겁게 깔린 새벽안개 속 회의실 / 복잡한 경제 위기 → 해질녘 붉은 노을 아래 얽힌 도시의 전선들)

🎨 스타일 가이드 (Style Lock)
- 비주얼: 고품질 일본 애니메이션 화풍(High-quality Japanese anime art style), 정교한 셀 셰이딩(Detailed cel-shading), 맑고 투명한 청색 위주의 파스텔 톤.
- 빛과 텍스처: 부드러운 역광(Rim lighting), 풍부한 구름 질감, 부피감 있는 햇살, 부드러운 빛 번짐, 정교한 환경 디테일.
- 분위기: 몽환적(Dreamy), 향수 어린(Nostalgic), 평화로운(Serene).

📝 범용 마스터 프롬프트 템플릿
모든 프롬프트는 반드시 아래의 영문 구조를 따릅니다. [대본의 시각적 묘사] 부분에 대본의 내용이 가장 구체적이고 생생하게 들어가야 합니다.

[대본 기반 구체적 인물, 오브젝트, 행동 및 배경 묘사 (영문 - 대본 내용 100% 반영)]. The scene is rendered in a high-quality Japanese anime art style, reminiscent of cinematic background art, with clean line work and detailed cel-shading. The lighting is defined by ethereal glowing highlights, soft volumetric sun rays, and a gentle bloom effect that softens the edges. The color palette mainly features vibrant blues, soft purples, and warm sunset-tinted clouds in the distance. The overall environment has a feeling of intricate environmental details, crisp textures, and a polished digital paint finish. The atmosphere is dreamy, nostalgic, and serene. High resolution, 8k, highly detailed. --no multiple panels, split frames, text, letters, subtitles, speech bubbles, captions, bottom text, meme text, cinematic borders with text

경제 콘텐츠 특화 지침:
- 경제/금융 개념은 시각적 메타포로 변환합니다: 주가 상승 → 치솟는 빛의 기둥, 경제 위기 → 갈라진 대지 위의 도시, 투자 → 씨앗에서 자라는 황금빛 나무
- 인물은 정장 차림의 비즈니스 전문가, 정책 입안자, 투자자 등으로 묘사합니다.
- 배경에 증권거래소, 도시 스카이라인, 회의실, 금융 차트(글자 없이 선과 도형만) 등을 활용합니다.

#### 📌 분해-조립 예시 (소재 무관 범용 패턴)

대본: "사우디아라비아에 주둔 중인 미군 공군기지가 미사일에 맞았습니다"
→ 분해: 장소=사막 위 미군 공군기지 / 인물=미군 병사 / 행동=미사일 피격 순간 / 오브젝트=활주로, 전투기, 미사일, 폭발 연기 / 분위기=긴박, 전쟁
→ 1) "A US military airbase in the vast Saudi desert under a dawn sky, a missile streaking toward the runway with a massive explosion erupting near parked fighter jets, soldiers running for cover amid billowing smoke and debris. The scene is rendered in a high-quality Japanese anime art style, reminiscent of cinematic background art, with clean line work and detailed cel-shading. The lighting is defined by the fiery orange glow of the explosion contrasting with the cool blue pre-dawn sky. High resolution, 8k, highly detailed. --no multiple panels, split frames, text, letters, subtitles"

#### 출력 형식
반드시 아래 형식으로 출력하세요:
1) "프롬프트 내용"
2) "프롬프트 내용"
...
"""

PROMPT_PRESETS = {
    "🎯 스틱맨 (경제)": PROMPT_STICKMAN,
    "🎬 시네마틱 애니메이션 (경제)": PROMPT_CINEMATIC,
    "✏️ 커스텀": "",
}

# ============================================================
# 캐릭터 프로필 시스템
# ============================================================

CHARACTER_FIXED_FIELDS = {
    "얼굴": "얼굴형, 피부색, 눈 모양/색, 코, 입 등",
    "머리": "머리카락 스타일, 색상, 길이, 질감 등",
    "체형": "등신 비율, 체형, 키, 특징적 신체 구조",
    "나이대": "어린이/청소년/성인/노인 등",
    "성별": "남성/여성/중성적/해당없음 등",
    "색상 팔레트": "캐릭터의 전체적 색감, 주요 컬러",
    "고유 특징": "눈에 띄는 식별 특징 (점, 흉터, 날개 등)",
    "스타일": "그림체, 질감, 외곽선 스타일 등",
}

CHARACTER_ADAPTIVE_FIELDS = {
    "의상": "기본 의상 (장면 주제에 따라 적응: 경제→정장, 군사→군복, 과학→연구복 등)",
    "액세서리": "기본 액세서리 (장면에 따라 변형 가능: 안경, 모자, 소지품 등)",
}

CHARACTER_VARIABLE_FIELDS = {
    "표정": "기본 표정 (기쁨/슬픔/놀람/무심 등)",
    "포즈": "기본 자세 (서있기/앉기/팔짱 등)",
    "앵글": "기본 촬영 앵글 (정면/측면/클로즈업 등)",
    "감정 이펙트": "감정 표현 소품 (땀방울/하트/느낌표 등)",
    "환경 반응": "환경에 따른 반응 (바람에 흔들림, 추위에 움츠림 등)",
}

EMPTY_CHARACTER_PROFILE = {
    "name": "",
    "fixed": {k: "" for k in CHARACTER_FIXED_FIELDS},
    "adaptive": {k: "" for k in CHARACTER_ADAPTIVE_FIELDS},
    "variable": {k: "" for k in CHARACTER_VARIABLE_FIELDS},
    "extra_notes": "",
}


def analyze_character_image(client, model: str, image_bytes: bytes, mime_type: str = "image/png") -> dict:
    """참조 이미지를 Gemini로 분석하여 캐릭터 프로필 JSON 반환."""
    from google.genai import types
    import json as _json

    fixed_keys = list(CHARACTER_FIXED_FIELDS.keys())
    adaptive_keys = list(CHARACTER_ADAPTIVE_FIELDS.keys())
    variable_keys = list(CHARACTER_VARIABLE_FIELDS.keys())

    analysis_prompt = (
        "이 캐릭터 이미지를 분석해서 아래 JSON 형식으로 한국어로 상세하게 작성해주세요.\n"
        "각 항목을 최대한 구체적이고 시각적으로 묘사해주세요.\n"
        "fixed=절대 불변 정체성, adaptive=장면 주제에 따라 변형되는 기본값, variable=현재 표현 상태.\n\n"
        "```json\n{\n"
        '  "fixed": {\n'
    )
    for k in fixed_keys:
        analysis_prompt += f'    "{k}": "상세 묘사",\n'
    analysis_prompt += "  },\n"
    analysis_prompt += '  "adaptive": {\n'
    for k in adaptive_keys:
        analysis_prompt += f'    "{k}": "기본 설정 묘사 (장면에 따라 변형 가능)",\n'
    analysis_prompt += "  },\n"
    analysis_prompt += '  "variable": {\n'
    for k in variable_keys:
        analysis_prompt += f'    "{k}": "현재 이미지에서 보이는 상태 묘사",\n'
    analysis_prompt += "  }\n}\n```\n"
    analysis_prompt += "\n반드시 위 JSON 형식만 출력하세요. 다른 텍스트 없이 JSON만 출력."

    response = client.models.generate_content(
        model=model,
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            analysis_prompt,
        ],
    )

    # JSON 파싱
    resp_text = response.text
    json_match = re.search(r"\{[\s\S]*\}", resp_text)
    if json_match:
        try:
            parsed = _json.loads(json_match.group())
            result = copy.deepcopy(EMPTY_CHARACTER_PROFILE)
            if "fixed" in parsed:
                for k in fixed_keys:
                    if k in parsed["fixed"]:
                        result["fixed"][k] = parsed["fixed"][k]
            if "adaptive" in parsed:
                for k in adaptive_keys:
                    if k in parsed["adaptive"]:
                        result["adaptive"][k] = parsed["adaptive"][k]
            if "variable" in parsed:
                for k in variable_keys:
                    if k in parsed["variable"]:
                        result["variable"][k] = parsed["variable"][k]
            return result
        except _json.JSONDecodeError:
            pass

    # 파싱 실패 시 빈 프로필 반환
    return copy.deepcopy(EMPTY_CHARACTER_PROFILE)


def build_character_prompt_injection(characters: list) -> str:
    """등록된 캐릭터 프로필들을 프롬프트에 주입할 텍스트로 변환."""
    if not characters:
        return ""

    lines = ["\n[캐릭터 일관성 + 장면 적응 지침]"]
    lines.append("아래 캐릭터들의 '고정 특징'(얼굴/체형/머리/고유 특징)은 절대 변하지 않습니다.")
    lines.append("'장면 적응 특징'(의상/액세서리)은 현재 대본의 주제에 맞게 능동적으로 변형하세요.")
    lines.append("예: 군사 장면→군복, 경제 장면→정장, 과학 장면→연구복, 운동 장면→운동복")
    lines.append("'가변 특징'(표정/포즈/앵글)은 매 장면 자유롭게 변화시키세요.")
    lines.append("캐릭터의 '본질'은 유지하되 똑같은 모습 반복은 금지합니다.\n")

    for char in characters:
        if not char.get("name"):
            continue
        lines.append(f"### 캐릭터: {char['name']}")
        lines.append("[고정 특징 - 절대 불변]")
        for k, v in char.get("fixed", {}).items():
            if v.strip():
                lines.append(f"  - {k}: {v}")
        lines.append("[장면 적응 특징 - 주제에 맞게 변형]")
        for k, v in char.get("adaptive", {}).items():
            if v.strip():
                lines.append(f"  - {k}: 기본={v} (대본 주제에 맞게 적응)")
        lines.append("[가변 특징 - 매 장면 변화]")
        for k, v in char.get("variable", {}).items():
            if v.strip():
                lines.append(f"  - {k}: {v} (기본값, 장면에 따라 변경)")
        if char.get("extra_notes", "").strip():
            lines.append(f"[추가 메모] {char['extra_notes']}")
        lines.append("")

    return "\n".join(lines)


LANGUAGE_MAP = {
    "한국어": "이미지 내에 한국어 텍스트/라벨을 적절히 포함할 수 있습니다. 프롬프트에 Korean text 허용을 명시하세요.",
    "日本語": "이미지 내에 일본어 텍스트/라벨을 적절히 포함할 수 있습니다. 프롬프트에 Japanese text 허용을 명시하세요.",
    "English": "이미지 내에 영어 텍스트/라벨을 적절히 포함할 수 있습니다. 프롬프트에 English text 허용을 명시하세요.",
    "언어없음": "이미지에 어떠한 글자, 문자, 텍스트도 포함하지 마세요. 모든 프롬프트에 'no text, no letters, no words'를 반드시 포함하세요.",
}


# ============================================================
# 텍스트 분할 함수
# ============================================================

def segment_text(text: str, seconds: int, chars_per_sec: float = 4.5) -> list:
    """대본을 시간(초) 기준으로 분할. 1초당 약 4.5글자 기준.
    한국어 의미 단위(절, 구)를 존중하여 자연스러운 위치에서 분할."""
    text = text.strip()
    if not text:
        return []

    target = int(seconds * chars_per_sec)

    # 1차: 문장 단위 분리 (마침표, 느낌표, 물음표, 줄바꿈)
    sentences = re.split(r"(?<=[.!?。！？\n])\s*", text)
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        sentences = [text]

    # 2차: 문장들을 target 글자 수에 맞게 그룹핑
    segments = []
    current = ""
    for sent in sentences:
        candidate = f"{current} {sent}".strip() if current else sent
        if len(candidate) > target and current:
            segments.append(current)
            current = sent
        else:
            current = candidate
    if current:
        segments.append(current)

    # 3차: 여전히 긴 세그먼트는 의미 단위로 추가 분할
    final = []
    for seg in segments:
        if len(seg) > target * 1.3:
            final.extend(_split_by_meaning(seg, target))
        else:
            final.append(seg)

    return final if final else [text]


def _split_by_meaning(text: str, target: int) -> list:
    """한국어 의미 단위(절/구)를 존중하여 분할.
    우선순위: 마침표/종결부호 > 종결어미 > 쉼표 > 연결어미 > 공백"""
    result = []

    while text:
        text = text.strip()
        if len(text) <= target * 1.3:
            result.append(text)
            break

        # target 범위 내에서 가장 좋은 분할 지점 찾기
        search_end = min(len(text), int(target * 1.3))
        search_start = max(0, int(target * 0.5))
        candidate_text = text[:search_end]

        best_pos = -1

        # 1순위: 마침표/물음표/느낌표 뒤
        for m in re.finditer(r"[.!?。！？]\s*", candidate_text):
            pos = m.end()
            if search_start <= pos <= search_end:
                best_pos = pos

        # 2순위: 한국어 종결어미 뒤 + 공백
        if best_pos < search_start:
            for m in re.finditer(
                r"(?:습니다|입니다|됩니다|합니다|했습니다|됐습니다|겠습니다|했죠|됐죠|이죠)\s+",
                candidate_text
            ):
                pos = m.end()
                if search_start <= pos <= search_end:
                    best_pos = pos

        # 3순위: 쉼표 뒤
        if best_pos < search_start:
            for m in re.finditer(r",\s*", candidate_text):
                pos = m.end()
                if search_start <= pos <= search_end:
                    best_pos = pos

        # 4순위: 연결어미 뒤 + 공백
        if best_pos < search_start:
            for m in re.finditer(
                r"(?:었고|했고|되고|지만|는데|으며|하며|으나|거든요|잖아요|인데요|니까요)\s+",
                candidate_text
            ):
                pos = m.end()
                if search_start <= pos <= search_end:
                    best_pos = pos

        # 5순위: 공백 (최후 수단)
        if best_pos < search_start:
            pos = candidate_text.rfind(" ", search_start, search_end)
            if pos > 0:
                best_pos = pos + 1

        # 분할 지점을 못 찾으면 target 위치에서 강제 분할
        if best_pos < search_start:
            best_pos = target

        result.append(text[:best_pos].strip())
        text = text[best_pos:]

    return [r for r in result if r]


# ============================================================
# Gemini API 함수
# ============================================================

def get_gemini_client(api_key: str):
    """Gemini API 클라이언트 생성."""
    from google import genai
    return genai.Client(api_key=api_key)


def generate_prompts(client, model: str, system_prompt: str,
                     segments: list, section_label: str, lang_instruction: str,
                     prev_prompt: str = "") -> list:
    """Gemini LLM을 사용하여 각 세그먼트별 이미지 프롬프트 생성.
    구조화 추출 방식: 대본 → 핵심요소 분해 → 프롬프트 조립.
    System Instruction(프리셋)의 스타일/템플릿/규칙이 최우선."""
    from google.genai import types

    numbered = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(segments))

    # 구조화 추출 지시 (System Instruction 보조용)
    extraction_instruction = (
        "각 대본 세그먼트를 처리할 때 아래 순서를 따르세요:\n"
        "① 핵심 요소 추출: 장소(where), 인물(who), 행동(action), 오브젝트(objects), 분위기(mood)를 대본에서 추출\n"
        "② 누락 검증: 대본에 명시된 고유명사, 사건, 사물이 빠지지 않았는지 확인\n"
        "③ 프롬프트 조립: 위 System Instruction에 명시된 스타일 가이드와 출력 템플릿을 100% 적용하여 영문 프롬프트로 조립\n"
        "⚠️ 대본에 없는 내용을 임의로 추가하지 말 것. 대본에 있는 내용을 빠뜨리지 말 것.\n"
    )

    # 이전 씬 컨텍스트 (있으면)
    prev_context = ""
    if prev_prompt:
        prev_context = (
            f"\n[이전 씬 프롬프트 (참고용)]\n{prev_prompt}\n"
            "→ 현재 대본이 이전 씬과 같은 맥락이면 시각적 연속성을 유지하고, "
            "장면이 전환되면 새로운 장면으로 구성하세요.\n"
        )

    user_msg = (
        f"🚨 최우선 지시: 위 System Instruction의 스타일 가이드(Style Lock), "
        f"출력 템플릿(Output Template), 절대 규칙(Zero Tolerance Rules), 캐릭터 일관성 지침을 "
        f"모든 프롬프트에 빠짐없이 그대로 적용하세요. "
        f"System Instruction에 명시된 prefix/접두 문구가 있다면 모든 프롬프트의 맨 앞에 반드시 포함하세요.\n\n"
        f"다음은 '{section_label}'의 대본 세그먼트입니다.\n\n"
        f"[보조 처리 방법 — System Instruction과 충돌 시 System Instruction이 우선]\n{extraction_instruction}\n"
        f"[언어 지시] {lang_instruction}\n"
        f"{prev_context}\n"
        f"대본 세그먼트:\n{numbered}\n\n"
        f"각 번호에 맞춰 System Instruction의 스타일/템플릿을 준수하는 영문 이미지 프롬프트를 작성하세요.\n"
        f'출력 형식: 번호) "프롬프트 내용" (System Instruction에 다른 출력 형식이 명시되어 있으면 그것을 우선 따름)\n'
    )

    response = client.models.generate_content(
        model=model,
        contents=user_msg,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
        ),
    )

    return parse_prompts(response.text, len(segments))


def parse_prompts(text: str, expected_count: int) -> list:
    """LLM 응답에서 번호별 프롬프트를 파싱."""
    # 패턴 1: 번호) "..."
    prompts = re.findall(r'\d+\)\s*"((?:[^"\\]|\\.)*)"', text, re.DOTALL)
    if len(prompts) >= expected_count:
        return prompts[:expected_count]

    # 패턴 2: 번호. "..."
    prompts = re.findall(r'\d+\.\s*"((?:[^"\\]|\\.)*)"', text, re.DOTALL)
    if len(prompts) >= expected_count:
        return prompts[:expected_count]

    # 패턴 3: "Upgraded..."로 시작하는 긴 문자열
    prompts = re.findall(r'"(Upgraded[^"]+)"', text, re.DOTALL)
    if len(prompts) >= expected_count:
        return prompts[:expected_count]

    # 패턴 4: 30글자 이상의 긴 따옴표 문자열
    prompts = re.findall(r'"([^"]{30,})"', text, re.DOTALL)
    if len(prompts) >= expected_count:
        return prompts[:expected_count]

    # 폴백: 번호 패턴으로 분할
    parts = re.split(r"\n\s*\d+[.)]\s*", "\n" + text)
    parts = [p.strip().strip("\"'") for p in parts if len(p.strip()) > 20]
    if parts:
        return parts[:expected_count]

    return [text]


def _call_image_api(client, model, prompt_text, config_kwargs):
    """이미지 API 단일 호출."""
    from google.genai import types

    response = client.models.generate_content(
        model=model,
        contents=prompt_text,
        config=types.GenerateContentConfig(**config_kwargs),
    )
    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            data = part.inline_data.data
            if isinstance(data, str):
                return base64.b64decode(data)
            return data
    return None


# 우회 프롬프트 변형 패턴
_BYPASS_PREFIXES = [
    "Illustration of: ",
    "Artistic depiction: ",
    "Visual scene: ",
]


def generate_image_gc(client, model: str, prompt: str, aspect_ratio: str = "1:1",
                       negative: str = "", seed: int = None,
                       max_retries: int = 3, bypass: bool = True) -> tuple:
    """generate_content (IMAGE 모달리티)로 이미지 생성.

    Returns: (image_bytes, status_msg)
        image_bytes: 이미지 바이트 또는 None
        status_msg: 생성 과정 메시지 (재시도/우회 정보)
    """
    import time as _time

    aspect_prompt = f"[aspect ratio: {aspect_ratio}] {prompt}"
    if negative.strip():
        aspect_prompt += f" --no {negative.strip()}"
    if seed is not None:
        aspect_prompt += f" --seed {seed}"

    config_kwargs = {"response_modalities": ["IMAGE"]}
    if seed is not None:
        config_kwargs["seed"] = seed

    # 1차: 일반 재시도 (최대 max_retries회)
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            result = _call_image_api(client, model, aspect_prompt, config_kwargs)
            if result:
                if attempt > 1:
                    return result, f"✅ {attempt}차 시도에서 성공"
                return result, ""
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                _time.sleep(min(2 ** attempt, 8))  # 2s, 4s, 8s

    # 2차: 우회 생성 — 프롬프트 변형하여 재시도
    if bypass:
        for i, prefix in enumerate(_BYPASS_PREFIXES):
            bypass_prompt = f"[aspect ratio: {aspect_ratio}] {prefix}{prompt}"
            if negative.strip():
                bypass_prompt += f" --no {negative.strip()}"
            try:
                result = _call_image_api(client, model, bypass_prompt, config_kwargs)
                if result:
                    return result, f"🔄 우회 생성 성공 (변형 {i + 1})"
            except Exception:
                _time.sleep(2)

    error_msg = f"❌ {max_retries}회 재시도 + 우회 모두 실패"
    if last_error:
        error_msg += f": {last_error}"
    return None, error_msg


def generate_image_imagen(client, model: str, prompt: str) -> bytes:
    """generate_images (Imagen 방식)로 이미지 생성."""
    from google.genai import types

    response = client.models.generate_images(
        model=model,
        prompt=prompt,
        config=types.GenerateImagesConfig(
            number_of_images=1,
        ),
    )

    if response.generated_images:
        return response.generated_images[0].image.image_bytes
    return None


def _log_generation(label: str, model: str, prompt: str, seed, status: str, msg: str = ""):
    """이미지 생성 이력을 세션 로그에 기록."""
    from datetime import datetime
    if "generation_log" not in st.session_state:
        st.session_state.generation_log = []
    st.session_state.generation_log.append({
        "time": datetime.now().strftime("%H:%M:%S"),
        "label": label,
        "model": model,
        "prompt": (prompt or "")[:300],
        "seed": seed,
        "status": status,
        "msg": msg or "",
    })
    # 메모리 보호: 최대 500개
    if len(st.session_state.generation_log) > 500:
        st.session_state.generation_log = st.session_state.generation_log[-500:]


def create_zip(images: list) -> bytes:
    """(파일명, 바이트) 리스트를 ZIP으로 묶기."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in images:
            zf.writestr(name, data)
    return buf.getvalue()


def _make_image_filename(label, script_text, max_len=15):
    """씬번호_(대본시작)_(대본끝).png 형식 파일명 생성."""
    text = script_text.strip().replace("\n", " ")
    if not text:
        return f"{label}.png"
    # 파일명에 사용 불가한 문자 제거
    clean = re.sub(r'[\\/:*?"<>|]', '', text)
    start = clean[:max_len]
    end = clean[-max_len:] if len(clean) > max_len else ""
    if end and start != end:
        return f"{label}_{start}_{end}.png"
    return f"{label}_{start}.png"


# ============================================================
# Streamlit 앱
# ============================================================

st.set_page_config(page_title="이미지 생성기", page_icon="🎨", layout="wide")

# ---- Session State 초기화 ----
_defaults = {
    "intro_segments": [],
    "body_segments": [],
    "intro_prompts": [],
    "body_prompts": [],
    "images": [],
    "v": 0,
    "prompts_ready": False,
    "images_ready": False,
    "images_dict": {},  # {label: bytes}
    "images_history": {},  # {label: [bytes, ...]}
    "preview_images": {},  # 프롬프트 테스트 미리보기
    "characters": [],  # 캐릭터 프로필 리스트
    "char_v": 0,  # 캐릭터 UI 버전
    "api_usage": {  # API 사용량 추적
        "prompt_calls": 0,
        "image_calls": 0,
        "image_success": 0,
        "image_fail": 0,
        "char_analysis_calls": 0,
    },
    "saved_presets": {},  # {이름: System Prompt 내용} - 사용자 저장 커스텀 프리셋
    "generation_log": [],  # 이미지 생성 로그 [{label, model, prompt, seed, status, time}]
}
for _k, _val in _defaults.items():
    if _k not in st.session_state:
        st.session_state[_k] = _val

# ---- 프로젝트 저장/불러오기 시스템 ----
MAX_PROJECTS = 5
if "projects" not in st.session_state:
    st.session_state.projects = {}  # {이름: {데이터}}
if "current_project" not in st.session_state:
    st.session_state.current_project = ""


def _save_current_project(name: str):
    """현재 작업 상태를 프로젝트로 저장 (이미지 제외, 텍스트만)."""
    st.session_state.projects[name] = {
        "intro_segments": list(st.session_state.intro_segments),
        "body_segments": list(st.session_state.body_segments),
        "intro_prompts": list(st.session_state.intro_prompts),
        "body_prompts": list(st.session_state.body_prompts),
        "characters": copy.deepcopy(st.session_state.characters),
        "prompts_ready": st.session_state.prompts_ready,
    }
    st.session_state.current_project = name
    # 최대 5개 유지 - 초과 시 가장 오래된 것 삭제
    while len(st.session_state.projects) > MAX_PROJECTS:
        oldest = next(iter(st.session_state.projects))
        del st.session_state.projects[oldest]


def _load_project(name: str):
    """저장된 프로젝트를 불러오기."""
    proj = st.session_state.projects[name]
    st.session_state.intro_segments = list(proj.get("intro_segments", []))
    st.session_state.body_segments = list(proj.get("body_segments", []))
    st.session_state.intro_prompts = list(proj.get("intro_prompts", []))
    st.session_state.body_prompts = list(proj.get("body_prompts", []))
    st.session_state.characters = copy.deepcopy(proj.get("characters", []))
    st.session_state.prompts_ready = proj.get("prompts_ready", False)
    st.session_state.images_ready = False
    st.session_state.images_dict = {}
    st.session_state.v += 1
    st.session_state.char_v += 1
    st.session_state.current_project = name


def _auto_save():
    """자동저장 - 작업 내용이 있으면 현재 프로젝트명으로 저장."""
    if st.session_state.intro_segments or st.session_state.body_segments:
        name = st.session_state.current_project or "자동저장"
        _save_current_project(name)


def _export_project_json() -> str:
    """현재 프로젝트를 JSON 문자열로 내보내기."""
    data = {
        "intro_segments": list(st.session_state.intro_segments),
        "body_segments": list(st.session_state.body_segments),
        "intro_prompts": list(st.session_state.intro_prompts),
        "body_prompts": list(st.session_state.body_prompts),
        "characters": st.session_state.characters,
        "prompts_ready": st.session_state.prompts_ready,
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


def _import_project_json(json_str: str):
    """JSON 문자열에서 프로젝트를 불러오기."""
    data = json.loads(json_str)
    st.session_state.intro_segments = data.get("intro_segments", [])
    st.session_state.body_segments = data.get("body_segments", [])
    st.session_state.intro_prompts = data.get("intro_prompts", [])
    st.session_state.body_prompts = data.get("body_prompts", [])
    st.session_state.characters = data.get("characters", [])
    st.session_state.prompts_ready = data.get("prompts_ready", False)
    st.session_state.images_ready = False
    st.session_state.images_dict = {}
    st.session_state.v += 1
    st.session_state.char_v += 1


# ============================================================
# 사이드바
# ============================================================

with st.sidebar:
    st.header("⚙️ 설정")

    # ---- API Key 관리 (최대 4개 저장) ----
    MAX_KEYS = 4
    if "saved_api_keys" not in st.session_state:
        st.session_state.saved_api_keys = {}  # {이름: 키}

    st.subheader("API Key 관리")

    # 새 키 등록
    with st.expander("🔑 API Key 등록 / 관리"):
        new_key_name = st.text_input("키 이름 (예: 개인, 회사 등)", key="new_key_name")
        new_key_value = st.text_input("API Key 값", type="password", key="new_key_value")
        if st.button("💾 저장"):
            if new_key_name and new_key_value:
                if len(st.session_state.saved_api_keys) >= MAX_KEYS and new_key_name not in st.session_state.saved_api_keys:
                    st.error(f"최대 {MAX_KEYS}개까지 저장 가능합니다. 기존 키를 삭제해주세요.")
                else:
                    st.session_state.saved_api_keys[new_key_name] = new_key_value
                    st.success(f"'{new_key_name}' 저장 완료!")
                    st.rerun()
            else:
                st.warning("이름과 키를 모두 입력해주세요.")

        # 저장된 키 삭제
        if st.session_state.saved_api_keys:
            del_key = st.selectbox(
                "삭제할 키",
                ["선택..."] + list(st.session_state.saved_api_keys.keys()),
                key="del_key_select",
            )
            if st.button("🗑️ 삭제") and del_key != "선택...":
                del st.session_state.saved_api_keys[del_key]
                st.rerun()

    # 키 선택
    if st.session_state.saved_api_keys:
        key_options = list(st.session_state.saved_api_keys.keys())
        selected_key_name = st.selectbox("사용할 API Key", key_options)
        api_key = st.session_state.saved_api_keys[selected_key_name]
        st.caption(f"🔑 `{selected_key_name}` 사용 중")
    else:
        api_key = st.text_input("Gemini API Key", type="password")
        st.caption("💡 위 '등록/관리'에서 키를 저장하면 매번 입력할 필요가 없습니다.")

    st.divider()
    st.subheader("프롬프트 생성 (LLM)")
    prompt_model = st.text_input("모델명", value="gemini-2.5-flash")

    st.divider()
    st.subheader("⏱️ 분할 속도")
    chars_per_sec = st.slider(
        "1초당 글자수 (TTS 속도 기준)",
        min_value=2.0, max_value=8.0, value=4.5, step=0.1,
        help="낮을수록 느린 발화(글자 수↓), 높을수록 빠른 발화(글자 수↑). 한국어 일반적 4.5~5.5",
    )

    st.divider()
    st.subheader("이미지 생성")
    IMAGE_MODELS = {
        "나노바나나2 (Gemini 3.1 Flash Image)": "gemini-3.1-flash-image-preview",
        "나노바나나 프로 (Gemini 3 Pro Image)": "gemini-3-pro-image-preview",
    }
    image_model_label = st.selectbox(
        "이미지 모델",
        list(IMAGE_MODELS.keys()),
        index=0,
        help="나노바나나2: 빠르고 저렴, 4K 지원 / 나노바나나 프로: 고품질, 텍스트 렌더링 우수",
    )
    image_model = IMAGE_MODELS[image_model_label]
    st.caption(f"모델 ID: `{image_model}`")

    ASPECT_RATIOS = {
        "1:1 (정사각형)": "1:1",
        "16:9 (와이드)": "16:9",
        "9:16 (세로)": "9:16",
        "4:3 (표준)": "4:3",
        "3:4 (세로 표준)": "3:4",
    }
    aspect_label = st.selectbox("이미지 비율", list(ASPECT_RATIOS.keys()), index=0)
    aspect_ratio = ASPECT_RATIOS[aspect_label]

    # 시드(Seed) 옵션
    use_seed = st.checkbox("🎲 시드(Seed) 고정", value=False, help="동일한 시드로 같은 프롬프트를 재현")
    if use_seed:
        seed_value = st.number_input("시드 값", min_value=0, max_value=2147483647, value=42, step=1)
    else:
        seed_value = None

    st.divider()
    st.subheader("네거티브 프롬프트")
    negative_prompt = st.text_area(
        "제외할 요소",
        value="text, letters, words, watermark, signature, blurry, low quality, multiple panels, split frames, speech bubbles",
        height=100,
        key="negative_prompt",
        help="이미지에서 제외할 요소를 쉼표로 구분하여 입력",
    )

    st.divider()
    st.subheader("언어")
    language = st.selectbox("이미지 내 언어", list(LANGUAGE_MAP.keys()), index=3)

    st.divider()
    st.subheader("형식 프롬프트")

    # 기본 프리셋 + 사용자 저장 프리셋 합치기
    saved_keys = list(st.session_state.saved_presets.keys())
    preset_options = list(PROMPT_PRESETS.keys()) + [f"💾 {n}" for n in saved_keys]

    preset_choice = st.selectbox(
        "프리셋 선택",
        preset_options,
        index=0,
    )

    if preset_choice == "✏️ 커스텀":
        # 커스텀: 자유 편집
        if "custom_prompt" not in st.session_state:
            st.session_state.custom_prompt = "여기에 원하는 형식 프롬프트를 작성하세요."
        format_prompt = st.text_area(
            "커스텀 System Prompt",
            value=st.session_state.custom_prompt,
            height=400,
            key="custom_prompt_editor",
        )
        st.session_state.custom_prompt = format_prompt
    elif preset_choice.startswith("💾 "):
        # 저장된 사용자 프리셋
        saved_name = preset_choice[2:]
        format_prompt = st.text_area(
            f"저장된 프리셋: {saved_name}",
            value=st.session_state.saved_presets.get(saved_name, ""),
            height=400,
            key=f"saved_{saved_name}",
        )
        # 수정 내용 자동 반영
        st.session_state.saved_presets[saved_name] = format_prompt
        if st.button(f"🗑️ '{saved_name}' 삭제", key=f"del_preset_{saved_name}"):
            del st.session_state.saved_presets[saved_name]
            st.rerun()
    else:
        # 기본 프리셋: 내용 확인 가능
        format_prompt = st.text_area(
            "System Prompt (프리셋)",
            value=PROMPT_PRESETS[preset_choice],
            height=400,
            key=f"preset_{preset_choice}",
        )

    # 현재 프롬프트를 새 이름으로 저장
    with st.expander("💾 현재 프롬프트를 프리셋으로 저장", expanded=False):
        new_preset_name = st.text_input(
            "프리셋 이름",
            key="new_preset_name_input",
            placeholder="예: 군사 시네마틱, 과학 다큐 등",
        )
        if st.button("저장", key="save_preset_btn"):
            if not new_preset_name.strip():
                st.warning("프리셋 이름을 입력하세요.")
            elif new_preset_name in st.session_state.saved_presets:
                st.warning("같은 이름의 프리셋이 이미 존재합니다.")
            else:
                st.session_state.saved_presets[new_preset_name] = format_prompt
                st.success(f"'{new_preset_name}' 저장 완료!")
                st.rerun()

    st.divider()
    st.subheader("🎨 UI 테마")
    THEMES = {
        "기본 다크": {
            "bg": "#0E1117", "sidebar_bg": "#262730", "text": "#FAFAFA",
            "primary": "#FF6B6B", "card_bg": "#1E1E2E",
        },
        "라이트": {
            "bg": "#FFFFFF", "sidebar_bg": "#F0F2F6", "text": "#31333F",
            "primary": "#FF4B4B", "card_bg": "#F8F9FA",
        },
        "블루 다크": {
            "bg": "#0D1B2A", "sidebar_bg": "#1B2838", "text": "#E0E1DD",
            "primary": "#48CAE4", "card_bg": "#1B263B",
        },
        "그린 다크": {
            "bg": "#1A1A2E", "sidebar_bg": "#16213E", "text": "#E0E0E0",
            "primary": "#00B4D8", "card_bg": "#0F3460",
        },
    }
    theme_choice = st.selectbox("테마 선택", list(THEMES.keys()), index=0)
    theme = THEMES[theme_choice]

    st.markdown(f"""
    <style>
        .stApp {{
            background-color: {theme["bg"]};
            color: {theme["text"]};
        }}
        section[data-testid="stSidebar"] {{
            background-color: {theme["sidebar_bg"]};
        }}
        .stButton > button {{
            border-color: {theme["primary"]};
        }}
        .stButton > button:hover {{
            background-color: {theme["primary"]};
            color: white;
        }}
        .stProgress > div > div > div > div {{
            background-color: {theme["primary"]};
        }}
        div[data-testid="stExpander"] {{
            background-color: {theme["card_bg"]};
            border-radius: 8px;
        }}
    </style>
    """, unsafe_allow_html=True)

    # API 사용량 표시
    st.divider()
    st.subheader("📊 API 사용량")
    usage = st.session_state.api_usage
    st.markdown(f"""
    | 항목 | 횟수 |
    |------|------|
    | 프롬프트 생성 | {usage['prompt_calls']}회 |
    | 이미지 생성 요청 | {usage['image_calls']}회 |
    | 이미지 성공 | {usage['image_success']}장 |
    | 이미지 실패 | {usage['image_fail']}장 |
    | 캐릭터 분석 | {usage['char_analysis_calls']}회 |
    """)
    if st.button("🔄 사용량 초기화", key="reset_usage"):
        st.session_state.api_usage = {
            "prompt_calls": 0, "image_calls": 0,
            "image_success": 0, "image_fail": 0,
            "char_analysis_calls": 0,
        }
        st.rerun()

# ============================================================
# 메인 영역
# ============================================================

st.title("🎨 이미지 생성기")

# ────────────────────────────────────────────────────────────
# 프로젝트 관리
# ────────────────────────────────────────────────────────────

with st.expander("📁 프로젝트 관리", expanded=False):
    proj_col1, proj_col2 = st.columns(2)

    with proj_col1:
        st.markdown("**저장 / 불러오기**")
        save_name = st.text_input(
            "프로젝트 이름",
            value=st.session_state.current_project or "",
            placeholder="프로젝트 이름 입력",
            key="proj_save_name",
        )
        if st.button("💾 현재 작업 저장"):
            if save_name:
                _save_current_project(save_name)
                st.success(f"'{save_name}' 저장 완료!")
            else:
                st.warning("프로젝트 이름을 입력해주세요.")

        if st.session_state.projects:
            load_choice = st.selectbox(
                "불러올 프로젝트",
                list(st.session_state.projects.keys()),
                key="proj_load_choice",
            )
            lc1, lc2 = st.columns(2)
            with lc1:
                if st.button("📂 불러오기"):
                    _load_project(load_choice)
                    st.success(f"'{load_choice}' 불러오기 완료!")
                    st.rerun()
            with lc2:
                if st.button("🗑️ 삭제"):
                    del st.session_state.projects[load_choice]
                    st.rerun()

            st.caption(f"저장된 프로젝트: {len(st.session_state.projects)}/{MAX_PROJECTS}")

    with proj_col2:
        st.markdown("**JSON 내보내기 / 가져오기**")
        st.caption("브라우저를 닫아도 보관하려면 JSON으로 내보내세요.")

        if st.session_state.intro_segments or st.session_state.body_segments:
            json_str = _export_project_json()
            st.download_button(
                "📤 JSON 내보내기",
                data=json_str,
                file_name="project.json",
                mime="application/json",
            )

        uploaded_json = st.file_uploader("📥 JSON 가져오기", type=["json"], key="proj_import")
        if uploaded_json:
            if st.button("적용"):
                try:
                    _import_project_json(uploaded_json.read().decode("utf-8"))
                    st.success("프로젝트 가져오기 완료!")
                    st.rerun()
                except Exception as e:
                    st.error(f"가져오기 실패: {e}")

# ────────────────────────────────────────────────────────────
# 캐릭터 프로필 관리
# ────────────────────────────────────────────────────────────

with st.expander("🧑‍🎨 캐릭터 프로필 관리", expanded=False):
    st.caption("캐릭터의 고정 특징을 등록하면 모든 이미지에 일관성을 유지합니다. 가변 특징은 장면에 따라 자동 변화됩니다.")

    char_v = st.session_state.char_v

    # ---- 새 캐릭터 추가 ----
    st.subheader("캐릭터 추가")
    add_col1, add_col2 = st.columns([3, 1])
    with add_col1:
        new_char_name = st.text_input("캐릭터 이름", placeholder="예: 병아리, 주인공 등", key=f"nc_name_{char_v}")
    with add_col2:
        st.markdown("<br>", unsafe_allow_html=True)
        add_manual = st.button("✏️ 수동 추가")

    # 참조 이미지로 자동 분석
    ref_image = st.file_uploader("참조 이미지 업로드 (자동 분석)", type=["png", "jpg", "jpeg", "webp"], key=f"ref_img_{char_v}")

    if ref_image:
        st.image(ref_image, caption="업로드된 참조 이미지", width=200)

    if st.button("🔍 이미지 분석 + 캐릭터 등록", type="primary"):
        if not new_char_name:
            st.error("캐릭터 이름을 입력해주세요.")
        elif not ref_image:
            st.error("참조 이미지를 업로드해주세요.")
        elif not api_key:
            st.error("사이드바에서 API Key를 먼저 설정해주세요.")
        else:
            try:
                with st.spinner(f"'{new_char_name}' 캐릭터 분석 중..."):
                    client = get_gemini_client(api_key)
                    img_bytes = ref_image.getvalue()
                    # MIME 타입 결정
                    fname = ref_image.name.lower()
                    if fname.endswith(".jpg") or fname.endswith(".jpeg"):
                        mime = "image/jpeg"
                    elif fname.endswith(".webp"):
                        mime = "image/webp"
                    else:
                        mime = "image/png"
                    st.session_state.api_usage["char_analysis_calls"] += 1
                    profile = analyze_character_image(client, prompt_model, img_bytes, mime)
                    profile["name"] = new_char_name
                    st.session_state.characters.append(profile)
                    st.session_state.char_v += 1
                    st.success(f"'{new_char_name}' 분석 완료! 아래에서 결과를 확인/수정하세요.")
                    st.rerun()
            except Exception as e:
                st.error(f"분석 실패: {e}")

    if add_manual and new_char_name:
        new_profile = copy.deepcopy(EMPTY_CHARACTER_PROFILE)
        new_profile["name"] = new_char_name
        st.session_state.characters.append(new_profile)
        st.session_state.char_v += 1
        st.rerun()

    # ---- 등록된 캐릭터 편집 ----
    if st.session_state.characters:
        st.divider()
        st.subheader(f"등록된 캐릭터 ({len(st.session_state.characters)}명)")

        for ci, char in enumerate(st.session_state.characters):
            with st.expander(f"🎭 {char['name'] or f'캐릭터 {ci+1}'}", expanded=False):
                # 캐릭터 이름 편집
                char["name"] = st.text_input(
                    "이름", value=char["name"], key=f"cn_{ci}_{char_v}"
                )

                # 고정 특징
                st.markdown("**🔒 고정 특징** (모든 장면에서 유지)")
                for fk in CHARACTER_FIXED_FIELDS:
                    char["fixed"][fk] = st.text_area(
                        f"{fk} — {CHARACTER_FIXED_FIELDS[fk]}",
                        value=char["fixed"].get(fk, ""),
                        height=68,
                        key=f"cf_{ci}_{fk}_{char_v}",
                    )

                # 장면 적응 특징
                st.markdown("**🎯 장면 적응 특징** (대본 주제에 따라 능동 변형)")
                # 기존 데이터 호환: adaptive 키가 없으면 추가
                if "adaptive" not in char:
                    char["adaptive"] = {k: "" for k in CHARACTER_ADAPTIVE_FIELDS}
                for ak in CHARACTER_ADAPTIVE_FIELDS:
                    char["adaptive"][ak] = st.text_area(
                        f"{ak} — {CHARACTER_ADAPTIVE_FIELDS[ak]}",
                        value=char["adaptive"].get(ak, ""),
                        height=68,
                        key=f"ca_{ci}_{ak}_{char_v}",
                    )

                # 가변 특징
                st.markdown("**🔄 가변 특징** (장면마다 변화, 기본값 설정)")
                for vk in CHARACTER_VARIABLE_FIELDS:
                    char["variable"][vk] = st.text_area(
                        f"{vk} — {CHARACTER_VARIABLE_FIELDS[vk]}",
                        value=char["variable"].get(vk, ""),
                        height=68,
                        key=f"cv_{ci}_{vk}_{char_v}",
                    )

                # 추가 메모
                char["extra_notes"] = st.text_area(
                    "📝 추가 메모 (자유 기입)",
                    value=char.get("extra_notes", ""),
                    height=100,
                    key=f"ce_{ci}_{char_v}",
                    placeholder="캐릭터에 대한 추가 특징이나 주의사항을 자유롭게 작성하세요.",
                )

                # 삭제 버튼
                if st.button(f"🗑️ '{char['name']}' 삭제", key=f"cdel_{ci}_{char_v}"):
                    st.session_state.characters.pop(ci)
                    st.session_state.char_v += 1
                    st.rerun()

# ────────────────────────────────────────────────────────────
# 1단계: 대본 입력
# ────────────────────────────────────────────────────────────

st.header("1단계: 대본 입력")

col_intro, col_body = st.columns(2)

with col_intro:
    st.subheader("📌 도입부")
    intro_text = st.text_area("도입부 대본을 입력하세요", height=200, key="intro_input")
    intro_sec = st.slider("컷당 시간 (초)", min_value=1, max_value=6, value=3, step=1)

with col_body:
    st.subheader("📌 본문")
    body_text = st.text_area("본문 대본을 입력하세요", height=200, key="body_input")
    body_sec = st.select_slider(
        "컷당 시간 (초)", options=[5, 10, 15, 20, 25, 30], value=5
    )

if st.button("✂️ 자동 분할", type="primary", use_container_width=True):
    st.session_state.intro_segments = segment_text(intro_text, intro_sec, chars_per_sec)
    st.session_state.body_segments = segment_text(body_text, body_sec, chars_per_sec)
    st.session_state.v += 1
    st.session_state.prompts_ready = False
    st.session_state.images_ready = False
    # 프롬프트 리스트를 세그먼트 수에 맞게 초기화 (개별 생성 호환)
    st.session_state.intro_prompts = [""] * len(st.session_state.intro_segments)
    st.session_state.body_prompts = [""] * len(st.session_state.body_segments)
    st.session_state.intro_checks = [True] * len(st.session_state.intro_segments)
    st.session_state.body_checks = [True] * len(st.session_state.body_segments)
    st.session_state.images_dict = {}
    st.session_state.images_history = {}
    st.session_state.images = []
    _auto_save()  # 자동저장
    st.rerun()

# ────────────────────────────────────────────────────────────
# 2단계: 분할 결과 확인 / 편집
# ────────────────────────────────────────────────────────────

if st.session_state.intro_segments or st.session_state.body_segments:
    st.divider()
    st.header("2단계: 분할 결과 확인 / 편집")

    # ===== 도입부 =====
    if st.session_state.intro_segments:
        st.subheader("📌 도입부")
        st.caption(
            "💡 텍스트 안에 `|` 를 넣고 ✂️ 분할 버튼을 누르면 그 위치에서 컷이 나뉩니다."
        )

        ver = st.session_state.v

        for i in range(len(st.session_state.intro_segments)):
            seg = st.session_state.intro_segments[i]

            c_text, c_info = st.columns([5, 1])

            with c_text:
                val = st.text_area(
                    f"도입부 컷 {i + 1}",
                    value=seg,
                    height=68,
                    key=f"ie_{i}_{ver}",
                )
                st.session_state.intro_segments[i] = val

            with c_info:
                chars = len(val)
                secs = chars / chars_per_sec
                if secs > 6:
                    st.error(f"⚠️ {chars}글자 / ~{secs:.1f}초  — 6초 초과!")
                else:
                    st.info(f"{chars}글자 / ~{secs:.1f}초")

            # 액션 버튼
            bc1, bc2, bc3, bc4 = st.columns(4)

            with bc1:
                if st.button("✂️ 분할", key=f"is_{i}_{ver}"):
                    txt = st.session_state.intro_segments[i]
                    if "|" in txt:
                        parts = txt.split("|", 1)
                        st.session_state.intro_segments[i] = parts[0].strip()
                        st.session_state.intro_segments.insert(
                            i + 1, parts[1].strip()
                        )
                    else:
                        mid = len(txt) // 2
                        sp = txt.rfind(" ", 0, mid + 5)
                        if sp > 0:
                            mid = sp
                        st.session_state.intro_segments[i] = txt[:mid].strip()
                        st.session_state.intro_segments.insert(
                            i + 1, txt[mid:].strip()
                        )
                    st.session_state.v += 1
                    st.rerun()

            with bc2:
                if st.button("🗑️ 삭제", key=f"id_{i}_{ver}"):
                    st.session_state.intro_segments.pop(i)
                    st.session_state.v += 1
                    st.rerun()

            with bc3:
                can_merge = i < len(st.session_state.intro_segments) - 1
                if st.button(
                    "⬇️ 병합", key=f"im_{i}_{ver}", disabled=not can_merge
                ):
                    if can_merge:
                        merged = (
                            st.session_state.intro_segments[i]
                            + " "
                            + st.session_state.intro_segments[i + 1]
                        )
                        st.session_state.intro_segments[i] = merged
                        st.session_state.intro_segments.pop(i + 1)
                        st.session_state.v += 1
                        st.rerun()

            with bc4:
                label = f"intro_{i + 1:03d}"
                has_image = label in st.session_state.images_dict
                btn_label = "🔄 다시 생성" if has_image else "🎯 생성"
                if st.button(btn_label, key=f"igen_{i}_{ver}"):
                    if not api_key:
                        st.error("API Key를 입력해주세요.")
                    elif not val.strip():
                        st.warning("대본이 비어있습니다.")
                    else:
                        try:
                            client = get_gemini_client(api_key)
                            char_injection = build_character_prompt_injection(st.session_state.characters)
                            full_sp = format_prompt + char_injection
                            lang_inst = LANGUAGE_MAP[language]

                            # 프롬프트 리스트 크기 보정
                            while len(st.session_state.intro_prompts) < len(st.session_state.intro_segments):
                                st.session_state.intro_prompts.append("")

                            # 이전 씬 프롬프트 (연속성 참고)
                            prev_p = st.session_state.intro_prompts[i - 1] if i > 0 and st.session_state.intro_prompts[i - 1] else ""
                            with st.spinner(f"도입부 컷 {i+1} 프롬프트 생성 중..."):
                                prompts = generate_prompts(client, prompt_model, full_sp, [val], "도입부", lang_inst, prev_p)
                            if prompts:
                                st.session_state.intro_prompts[i] = prompts[0]
                                st.session_state.api_usage["prompt_calls"] += 1

                                with st.spinner(f"도입부 컷 {i+1} 이미지 생성 중..."):
                                    st.session_state.api_usage["image_calls"] += 1
                                    img_data, gen_msg = generate_image_gc(
                                        client, image_model, prompts[0], aspect_ratio, negative_prompt, seed_value
                                    )
                                if img_data:
                                    # 기존 이미지 히스토리 보관
                                    if has_image:
                                        if label not in st.session_state.images_history:
                                            st.session_state.images_history[label] = []
                                        st.session_state.images_history[label].append(
                                            st.session_state.images_dict[label]
                                        )
                                    st.session_state.images_dict[label] = img_data
                                    st.session_state.api_usage["image_success"] += 1
                                    st.session_state.prompts_ready = True
                                    st.session_state.images_ready = True
                                    _log_generation(label, image_model, prompts[0], seed_value, "✅ 성공", gen_msg)
                                    _auto_save()
                                    if gen_msg:
                                        st.toast(gen_msg)
                                    st.rerun()
                                else:
                                    st.session_state.api_usage["image_fail"] += 1
                                    _log_generation(label, image_model, prompts[0], seed_value, "❌ 실패", gen_msg)
                                    st.warning(gen_msg or "이미지 생성 실패")
                        except Exception as e:
                            st.error(f"생성 실패: {e}")

            # 개별 생성 결과 미리보기
            label = f"intro_{i + 1:03d}"
            if label in st.session_state.get("images_dict", {}):
                with st.expander(f"🖼️ 도입부 컷 {i+1} 이미지", expanded=False):
                    st.image(st.session_state.images_dict[label], use_container_width=True)
                    if i < len(st.session_state.get("intro_prompts", [])):
                        st.caption(f"프롬프트: {st.session_state.intro_prompts[i][:100]}...")

            st.markdown("---")

        if st.button("➕ 도입부 컷 추가"):
            st.session_state.intro_segments.append("")
            st.session_state.v += 1
            st.rerun()

    # ===== 본문 =====
    if st.session_state.body_segments:
        st.subheader("📌 본문")
        st.caption(
            "💡 텍스트 안에 `|` 를 넣고 ✂️ 분할 버튼을 누르면 그 위치에서 컷이 나뉩니다."
        )
        ver = st.session_state.v

        for i in range(len(st.session_state.body_segments)):
            seg = st.session_state.body_segments[i]

            c_text, c_info = st.columns([5, 1])

            with c_text:
                val = st.text_area(
                    f"본문 컷 {i + 1}",
                    value=seg,
                    height=68,
                    key=f"be_{i}_{ver}",
                )
                st.session_state.body_segments[i] = val

            with c_info:
                chars = len(val)
                secs = chars / chars_per_sec
                st.info(f"{chars}글자 / ~{secs:.1f}초")

            # 액션 버튼
            bc1, bc2, bc3, bc4 = st.columns(4)

            with bc1:
                if st.button("✂️ 분할", key=f"bs_{i}_{ver}"):
                    txt = st.session_state.body_segments[i]
                    if "|" in txt:
                        parts = txt.split("|", 1)
                        st.session_state.body_segments[i] = parts[0].strip()
                        st.session_state.body_segments.insert(
                            i + 1, parts[1].strip()
                        )
                    else:
                        # 마침표/종결어미 기준 분할
                        mid = len(txt) // 2
                        split_pos = -1
                        # 1순위: 마침표/물음표/느낌표 뒤
                        for m in re.finditer(r"[.!?。！？]\s*", txt):
                            pos = m.end()
                            if pos <= mid + 15:
                                split_pos = pos
                        # 2순위: 종결어미 뒤 공백
                        if split_pos < len(txt) * 0.2:
                            for m in re.finditer(
                                r"(?:습니다|입니다|됩니다|합니다|했습니다|됐습니다|겠습니다|었고|했고|했죠|됐죠|이죠|는데요|거든요|잖아요)\s+",
                                txt
                            ):
                                pos = m.end()
                                if pos <= mid + 15:
                                    split_pos = pos
                        # 3순위: 쉼표 뒤
                        if split_pos < len(txt) * 0.2:
                            comma_pos = txt.rfind(",", 0, mid + 10)
                            if comma_pos > len(txt) * 0.2:
                                split_pos = comma_pos + 1
                        # 최후: 공백
                        if split_pos < len(txt) * 0.2:
                            sp = txt.rfind(" ", 0, mid + 5)
                            split_pos = sp if sp > 0 else mid
                        st.session_state.body_segments[i] = txt[:split_pos].strip()
                        st.session_state.body_segments.insert(
                            i + 1, txt[split_pos:].strip()
                        )
                    st.session_state.v += 1
                    st.rerun()

            with bc2:
                if st.button("🗑️ 삭제", key=f"bd_{i}_{ver}"):
                    st.session_state.body_segments.pop(i)
                    st.session_state.v += 1
                    st.rerun()

            with bc3:
                can_merge = i < len(st.session_state.body_segments) - 1
                if st.button(
                    "⬇️ 병합", key=f"bm_{i}_{ver}", disabled=not can_merge
                ):
                    if can_merge:
                        merged = (
                            st.session_state.body_segments[i]
                            + " "
                            + st.session_state.body_segments[i + 1]
                        )
                        st.session_state.body_segments[i] = merged
                        st.session_state.body_segments.pop(i + 1)
                        st.session_state.v += 1
                        st.rerun()

            with bc4:
                label = f"body_{i + 1:03d}"
                has_image = label in st.session_state.images_dict
                btn_label = "🔄 다시 생성" if has_image else "🎯 생성"
                if st.button(btn_label, key=f"bgen_{i}_{ver}"):
                    if not api_key:
                        st.error("API Key를 입력해주세요.")
                    elif not val.strip():
                        st.warning("대본이 비어있습니다.")
                    else:
                        try:
                            client = get_gemini_client(api_key)
                            char_injection = build_character_prompt_injection(st.session_state.characters)
                            full_sp = format_prompt + char_injection
                            lang_inst = LANGUAGE_MAP[language]

                            # 프롬프트 리스트 크기 보정
                            while len(st.session_state.body_prompts) < len(st.session_state.body_segments):
                                st.session_state.body_prompts.append("")

                            # 이전 씬 프롬프트 (연속성 참고)
                            prev_p = st.session_state.body_prompts[i - 1] if i > 0 and st.session_state.body_prompts[i - 1] else ""
                            with st.spinner(f"본문 컷 {i+1} 프롬프트 생성 중..."):
                                prompts = generate_prompts(client, prompt_model, full_sp, [val], "본문", lang_inst, prev_p)
                            if prompts:
                                st.session_state.body_prompts[i] = prompts[0]
                                st.session_state.api_usage["prompt_calls"] += 1

                                with st.spinner(f"본문 컷 {i+1} 이미지 생성 중..."):
                                    st.session_state.api_usage["image_calls"] += 1
                                    img_data, gen_msg = generate_image_gc(
                                        client, image_model, prompts[0], aspect_ratio, negative_prompt, seed_value
                                    )
                                if img_data:
                                    if has_image:
                                        if label not in st.session_state.images_history:
                                            st.session_state.images_history[label] = []
                                        st.session_state.images_history[label].append(
                                            st.session_state.images_dict[label]
                                        )
                                    st.session_state.images_dict[label] = img_data
                                    st.session_state.api_usage["image_success"] += 1
                                    st.session_state.prompts_ready = True
                                    st.session_state.images_ready = True
                                    _log_generation(label, image_model, prompts[0], seed_value, "✅ 성공", gen_msg)
                                    _auto_save()
                                    if gen_msg:
                                        st.toast(gen_msg)
                                    st.rerun()
                                else:
                                    st.session_state.api_usage["image_fail"] += 1
                                    _log_generation(label, image_model, prompts[0], seed_value, "❌ 실패", gen_msg)
                                    st.warning(gen_msg or "이미지 생성 실패")
                        except Exception as e:
                            st.error(f"생성 실패: {e}")

            # 개별 생성 결과 미리보기
            label = f"body_{i + 1:03d}"
            if label in st.session_state.get("images_dict", {}):
                with st.expander(f"🖼️ 본문 컷 {i+1} 이미지", expanded=False):
                    st.image(st.session_state.images_dict[label], use_container_width=True)
                    if i < len(st.session_state.get("body_prompts", [])):
                        st.caption(f"프롬프트: {st.session_state.body_prompts[i][:100]}...")

            st.markdown("---")

        if st.button("➕ 본문 컷 추가"):
            st.session_state.body_segments.append("")
            st.session_state.v += 1
            st.rerun()

# ────────────────────────────────────────────────────────────
# 3단계: 이미지 프롬프트 생성
# ────────────────────────────────────────────────────────────

if st.session_state.intro_segments or st.session_state.body_segments:
    st.divider()
    st.header("3단계: 이미지 프롬프트 생성")

    if st.button("🎯 프롬프트 생성", type="primary", use_container_width=True):
        if not api_key:
            st.error("사이드바에서 Gemini API Key를 입력해주세요.")
        elif not prompt_model:
            st.error("프롬프트 생성 모델명을 입력해주세요.")
        else:
            try:
                client = get_gemini_client(api_key)
                lang_inst = LANGUAGE_MAP[language]

                # 캐릭터 정보를 system prompt에 주입
                char_injection = build_character_prompt_injection(st.session_state.characters)
                full_system_prompt = format_prompt + char_injection

                with st.spinner("프롬프트 생성 중..."):
                    intro_segs = [
                        s for s in st.session_state.intro_segments if s.strip()
                    ]
                    body_segs = [
                        s for s in st.session_state.body_segments if s.strip()
                    ]

                    if intro_segs:
                        st.session_state.intro_prompts = generate_prompts(
                            client,
                            prompt_model,
                            full_system_prompt,
                            intro_segs,
                            "도입부",
                            lang_inst,
                        )
                    else:
                        st.session_state.intro_prompts = []

                    if body_segs:
                        st.session_state.body_prompts = generate_prompts(
                            client,
                            prompt_model,
                            full_system_prompt,
                            body_segs,
                            "본문",
                            lang_inst,
                        )
                    else:
                        st.session_state.body_prompts = []

                st.session_state.api_usage["prompt_calls"] += 1
                st.session_state.prompts_ready = True
                st.session_state.images_ready = False
                st.session_state.images = []
                _auto_save()  # 자동저장
                st.rerun()

            except Exception as e:
                st.error(f"프롬프트 생성 실패: {e}")

    # 프롬프트 표시 / 편집 (체크박스 포함)
    if st.session_state.prompts_ready:
        ver = st.session_state.v

        # 체크박스 상태 초기화
        if "intro_checks" not in st.session_state or len(st.session_state.intro_checks) != len(st.session_state.intro_prompts):
            st.session_state.intro_checks = [True] * len(st.session_state.intro_prompts)
        if "body_checks" not in st.session_state or len(st.session_state.body_checks) != len(st.session_state.body_prompts):
            st.session_state.body_checks = [True] * len(st.session_state.body_prompts)

        # 전체 선택/해제
        sel_col1, sel_col2 = st.columns(2)
        with sel_col1:
            if st.button("☑️ 전체 선택"):
                st.session_state.intro_checks = [True] * len(st.session_state.intro_prompts)
                st.session_state.body_checks = [True] * len(st.session_state.body_prompts)
                st.rerun()
        with sel_col2:
            if st.button("⬜ 전체 해제"):
                st.session_state.intro_checks = [False] * len(st.session_state.intro_prompts)
                st.session_state.body_checks = [False] * len(st.session_state.body_prompts)
                st.rerun()

        # 프롬프트 미리보기 상태
        # preview_images는 _defaults에서 초기화됨

        def _prompt_row(section, i, p, check_list, check_key_prefix, text_key_prefix):
            chk_col, txt_col, test_col = st.columns([0.5, 8.5, 1])
            with chk_col:
                check_list[i] = st.checkbox(
                    "선택", value=check_list[i],
                    key=f"{check_key_prefix}_{i}_{ver}", label_visibility="collapsed"
                )
            with txt_col:
                val = st.text_area(
                    f"{section} 프롬프트 {i + 1}",
                    value=p,
                    height=120,
                    key=f"{text_key_prefix}_{i}_{ver}",
                )
            with test_col:
                preview_key = f"{text_key_prefix}_{i}"
                if st.button("🔍", key=f"test_{text_key_prefix}_{i}", help="1장 테스트 생성"):
                    if not api_key:
                        st.error("API Key 필요")
                    elif not image_model:
                        st.error("이미지 모델 필요")
                    else:
                        try:
                            client = get_gemini_client(api_key)
                            st.session_state.api_usage["image_calls"] += 1
                            with st.spinner("테스트 생성 중... (실패 시 자동 재시도)"):
                                test_img, test_msg = generate_image_gc(client, image_model, val, aspect_ratio, negative_prompt, seed_value)
                            if test_img:
                                st.session_state.api_usage["image_success"] += 1
                                st.session_state.preview_images[preview_key] = test_img
                                if test_msg:
                                    st.toast(test_msg)
                                st.rerun()
                            else:
                                st.session_state.api_usage["image_fail"] += 1
                                st.error(test_msg or "이미지 생성 결과 없음")
                        except Exception as e:
                            st.session_state.api_usage["image_fail"] += 1
                            st.error(f"실패: {e}")
                if preview_key in st.session_state.preview_images:
                    st.image(st.session_state.preview_images[preview_key], width=150)
                    if st.button("✖️", key=f"clr_{text_key_prefix}_{i}", help="미리보기 닫기"):
                        del st.session_state.preview_images[preview_key]
                        st.rerun()
            return val

        if st.session_state.intro_prompts:
            st.subheader("📌 도입부 프롬프트")
            for i, p in enumerate(st.session_state.intro_prompts):
                val = _prompt_row("도입부", i, p, st.session_state.intro_checks, "ic", "ip")
                st.session_state.intro_prompts[i] = val

        if st.session_state.body_prompts:
            st.subheader("📌 본문 프롬프트")
            for i, p in enumerate(st.session_state.body_prompts):
                val = _prompt_row("본문", i, p, st.session_state.body_checks, "bc", "bp")
                st.session_state.body_prompts[i] = val

        selected_count = sum(st.session_state.intro_checks) + sum(st.session_state.body_checks)
        total_count = len(st.session_state.intro_prompts) + len(st.session_state.body_prompts)
        st.info(f"✅ {selected_count} / {total_count} 프롬프트 선택됨")

# ────────────────────────────────────────────────────────────
# 4단계: 이미지 생성
# ────────────────────────────────────────────────────────────

if st.session_state.prompts_ready:
    st.divider()
    st.header("4단계: 이미지 생성")

    # images_dict, images_history는 _defaults에서 초기화됨

    if st.button("🖼️ 선택된 이미지 생성", type="primary", use_container_width=True):
        if not api_key:
            st.error("API Key를 입력해주세요.")
        elif not image_model:
            st.error("사이드바에서 이미지 모델명을 입력해주세요.")
        else:
            try:
                client = get_gemini_client(api_key)

                # 체크된 프롬프트만 수집
                selected = []
                intro_checks = st.session_state.get("intro_checks", [])
                body_checks = st.session_state.get("body_checks", [])

                for i, p in enumerate(st.session_state.intro_prompts):
                    if i < len(intro_checks) and intro_checks[i]:
                        selected.append((f"intro_{i + 1:03d}", p))
                for i, p in enumerate(st.session_state.body_prompts):
                    if i < len(body_checks) and body_checks[i]:
                        selected.append((f"body_{i + 1:03d}", p))

                if not selected:
                    st.warning("선택된 프롬프트가 없습니다. 체크박스를 선택해주세요.")
                else:
                    import time as _time
                    progress = st.progress(0, text="이미지 생성 준비 중...")
                    status_text = st.empty()
                    total = len(selected)
                    start_time = _time.time()
                    success_count = 0
                    fail_count = 0

                    for idx, (label, prompt) in enumerate(selected):
                        elapsed = _time.time() - start_time
                        if idx > 0:
                            avg_per_image = elapsed / idx
                            remaining = avg_per_image * (total - idx)
                            remaining_min = int(remaining // 60)
                            remaining_sec = int(remaining % 60)
                            eta_str = f"{remaining_min}분 {remaining_sec}초" if remaining_min > 0 else f"{remaining_sec}초"
                        else:
                            eta_str = "계산 중..."

                        elapsed_min = int(elapsed // 60)
                        elapsed_sec = int(elapsed % 60)
                        elapsed_str = f"{elapsed_min}분 {elapsed_sec}초" if elapsed_min > 0 else f"{elapsed_sec}초"

                        progress.progress(
                            idx / total,
                            text=f"이미지 생성 중... ({idx + 1}/{total})",
                        )
                        status_text.caption(f"⏱️ 경과: {elapsed_str} | 남은 예상: {eta_str} | ✅ {success_count} ❌ {fail_count}")

                        try:
                            st.session_state.api_usage["image_calls"] += 1
                            img_data, gen_msg = generate_image_gc(
                                client, image_model, prompt, aspect_ratio, negative_prompt, seed_value
                            )
                            if img_data:
                                st.session_state.images_dict[label] = img_data
                                st.session_state.api_usage["image_success"] += 1
                                success_count += 1
                                _log_generation(label, image_model, prompt, seed_value, "✅ 성공", gen_msg)
                                if gen_msg:
                                    st.caption(f"  {label}: {gen_msg}")
                            else:
                                st.warning(f"{label}: {gen_msg or '이미지 생성 결과 없음'}")
                                st.session_state.api_usage["image_fail"] += 1
                                fail_count += 1
                                _log_generation(label, image_model, prompt, seed_value, "❌ 실패", gen_msg)
                        except Exception as e:
                            st.warning(f"{label} 생성 실패: {e}")
                            st.session_state.api_usage["image_fail"] += 1
                            fail_count += 1
                            _log_generation(label, image_model, prompt, seed_value, "❌ 예외", str(e))

                    total_elapsed = _time.time() - start_time
                    total_min = int(total_elapsed // 60)
                    total_sec = int(total_elapsed % 60)
                    total_str = f"{total_min}분 {total_sec}초" if total_min > 0 else f"{total_sec}초"
                    progress.progress(1.0, text="완료!")
                    status_text.success(f"🎉 완료! 총 {total_str} 소요 | ✅ {success_count}장 성공, ❌ {fail_count}장 실패")
                    st.session_state.images_ready = True
                    st.rerun()

            except Exception as e:
                st.error(f"이미지 생성 실패: {e}")

    # 타임라인 요약 뷰 (씬 한눈에 보기)
    has_segments = (st.session_state.intro_segments or st.session_state.body_segments)
    if has_segments:
        with st.expander("📊 타임라인 요약 (전체 씬 한눈에 보기)", expanded=False):
            def _timeline_summary(section_label, prefix, segments_list):
                if not segments_list:
                    return
                total_chars = sum(len(s) for s in segments_list)
                total_secs = total_chars / chars_per_sec
                done = sum(
                    1 for i in range(len(segments_list))
                    if f"{prefix}_{i + 1:03d}" in st.session_state.images_dict
                )
                st.markdown(
                    f"**{section_label}** — {len(segments_list)}컷 / "
                    f"{total_chars}글자 / ~{total_secs:.1f}초 / "
                    f"이미지 {done}/{len(segments_list)}"
                )
                rows = []
                for i, seg in enumerate(segments_list):
                    label = f"{prefix}_{i + 1:03d}"
                    chars = len(seg)
                    secs = chars / chars_per_sec
                    has_img = "🖼️" if label in st.session_state.images_dict else "⬜"
                    preview = seg.strip().replace("\n", " ")
                    if len(preview) > 50:
                        preview = preview[:50] + "…"
                    rows.append({
                        "씬": i + 1,
                        "상태": has_img,
                        "글자": chars,
                        "초": f"{secs:.1f}",
                        "대본": preview,
                    })
                st.dataframe(rows, use_container_width=True, hide_index=True)

            _timeline_summary("📌 도입부", "intro", st.session_state.intro_segments)
            _timeline_summary("📌 본문", "body", st.session_state.body_segments)

    # 생성 로그 표시
    if st.session_state.get("generation_log"):
        with st.expander(f"📜 생성 로그 ({len(st.session_state.generation_log)}건)", expanded=False):
            log_rows = []
            for entry in reversed(st.session_state.generation_log[-100:]):
                log_rows.append({
                    "시각": entry["time"],
                    "라벨": entry["label"],
                    "상태": entry["status"],
                    "모델": entry["model"],
                    "시드": entry.get("seed") if entry.get("seed") is not None else "-",
                    "프롬프트": entry["prompt"][:80] + ("…" if len(entry["prompt"]) > 80 else ""),
                    "메시지": entry.get("msg", ""),
                })
            st.dataframe(log_rows, use_container_width=True, hide_index=True)
            if st.button("🗑️ 로그 비우기", key="clear_log_btn"):
                st.session_state.generation_log = []
                st.rerun()

    # 이미지 표시 + 개별 재생성 버튼
    if st.session_state.images_ready and st.session_state.images_dict:
        st.subheader("생성된 이미지")

        def _swap_scene(prefix, i, j):
            """씬 i와 j의 세그먼트, 프롬프트, 이미지를 교환"""
            if prefix == "intro":
                segs = st.session_state.intro_segments
                prompts = st.session_state.intro_prompts
                checks = st.session_state.intro_checks
            else:
                segs = st.session_state.body_segments
                prompts = st.session_state.body_prompts
                checks = st.session_state.body_checks
            # 세그먼트, 프롬프트, 체크 교환
            segs[i], segs[j] = segs[j], segs[i]
            prompts[i], prompts[j] = prompts[j], prompts[i]
            checks[i], checks[j] = checks[j], checks[i]
            # 이미지 교환
            label_i = f"{prefix}_{i + 1:03d}"
            label_j = f"{prefix}_{j + 1:03d}"
            img_i = st.session_state.images_dict.get(label_i)
            img_j = st.session_state.images_dict.get(label_j)
            if img_i is not None and img_j is not None:
                st.session_state.images_dict[label_i], st.session_state.images_dict[label_j] = img_j, img_i
            elif img_i is not None:
                st.session_state.images_dict[label_j] = img_i
                del st.session_state.images_dict[label_i]
            elif img_j is not None:
                st.session_state.images_dict[label_i] = img_j
                del st.session_state.images_dict[label_j]

        def _show_images(section_label, prefix, prompts_list, segments_list):
            section_imgs = {k: v for k, v in st.session_state.images_dict.items() if k.startswith(prefix)}
            if not section_imgs and not prompts_list:
                return
            st.markdown(f"**📌 {section_label}**")
            total = len(prompts_list)
            for i, p in enumerate(prompts_list):
                label = f"{prefix}_{i + 1:03d}"
                # 해당 씬의 대본 텍스트
                script_text = segments_list[i] if i < len(segments_list) else ""
                chars = len(script_text)
                secs = chars / chars_per_sec

                st.markdown(f"---")
                # 씬 헤더 + 순서 이동 버튼
                hdr_col, up_col, down_col = st.columns([8, 1, 1])
                with hdr_col:
                    st.markdown(f"**씬 {i + 1}** — {chars}글자 / ~{secs:.1f}초")
                with up_col:
                    if i > 0:
                        if st.button("⬆️", key=f"up_{prefix}_{i}"):
                            _swap_scene(prefix, i, i - 1)
                            st.rerun()
                with down_col:
                    if i < total - 1:
                        if st.button("⬇️", key=f"down_{prefix}_{i}"):
                            _swap_scene(prefix, i, i + 1)
                            st.rerun()

                if script_text.strip():
                    st.info(f"📝 {script_text.strip()}")

                img_col, ctrl_col = st.columns([3, 1])
                with img_col:
                    if label in st.session_state.images_dict:
                        st.image(st.session_state.images_dict[label], caption=label, use_container_width=True)
                    else:
                        st.info(f"{label}\n(미생성)")
                with ctrl_col:
                    if label in st.session_state.images_dict:
                        dl_filename = _make_image_filename(label, script_text)
                        st.download_button(
                            f"📥 저장",
                            data=st.session_state.images_dict[label],
                            file_name=dl_filename,
                            mime="image/png",
                            key=f"dl_{label}",
                        )
                        if st.button(f"🔄 재생성", key=f"regen_{label}"):
                            try:
                                client = get_gemini_client(api_key)
                                # 현재 이미지를 히스토리에 저장
                                if label not in st.session_state.images_history:
                                    st.session_state.images_history[label] = []
                                st.session_state.images_history[label].append(
                                    st.session_state.images_dict[label]
                                )
                                st.session_state.api_usage["image_calls"] += 1
                                with st.spinner(f"{label} 재생성 중... (실패 시 자동 재시도)"):
                                    new_img, regen_msg = generate_image_gc(client, image_model, p, aspect_ratio, negative_prompt, seed_value)
                                if new_img:
                                    st.session_state.api_usage["image_success"] += 1
                                    st.session_state.images_dict[label] = new_img
                                    _log_generation(label, image_model, p, seed_value, "🔄 재생성", regen_msg)
                                    if regen_msg:
                                        st.toast(regen_msg)
                                    st.rerun()
                                else:
                                    _log_generation(label, image_model, p, seed_value, "❌ 재생성 실패", regen_msg)
                                    st.warning(regen_msg or "재생성 결과 없음")
                            except Exception as e:
                                st.error(f"재생성 실패: {e}")
                        # 이전 버전 비교 뷰
                        history = st.session_state.images_history.get(label, [])
                        if history:
                            with st.expander(f"📊 이전 버전 ({len(history)}장)"):
                                for hi, old_img in enumerate(reversed(history)):
                                    cmp_cur, cmp_old = st.columns(2)
                                    with cmp_cur:
                                        st.caption("현재")
                                        st.image(st.session_state.images_dict[label], use_container_width=True)
                                    with cmp_old:
                                        st.caption(f"이전 v{len(history) - hi}")
                                        st.image(old_img, use_container_width=True)
                                        if st.button(f"↩️ 복원", key=f"restore_{label}_{hi}"):
                                            st.session_state.images_history[label].append(
                                                st.session_state.images_dict[label]
                                            )
                                            st.session_state.images_dict[label] = old_img
                                            st.rerun()
                    with st.expander("프롬프트 보기"):
                        st.code(p, language=None)

        _show_images("도입부", "intro", st.session_state.intro_prompts, st.session_state.intro_segments)
        _show_images("본문", "body", st.session_state.body_prompts, st.session_state.body_segments)

        # 전체 ZIP 다운로드
        if st.session_state.images_dict:
            st.divider()
            # 대본 기반 파일명으로 ZIP 생성
            zip_items = []
            for label, data in sorted(st.session_state.images_dict.items()):
                # label에서 prefix와 index 추출
                if label.startswith("intro_"):
                    idx = int(label.split("_")[1]) - 1
                    segs = st.session_state.intro_segments
                else:
                    idx = int(label.split("_")[1]) - 1
                    segs = st.session_state.body_segments
                seg_text = segs[idx] if idx < len(segs) else ""
                zip_items.append((_make_image_filename(label, seg_text), data))
            zip_data = create_zip(zip_items)
            st.download_button(
                "📦 전체 ZIP 다운로드",
                data=zip_data,
                file_name="generated_images.zip",
                mime="application/zip",
                type="primary",
                use_container_width=True,
            )
