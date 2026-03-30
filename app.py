"""
Streamlit 이미지 생성기
대본 입력 → 초단위 분할 → 이미지 프롬프트 생성 → 이미지 생성
"""

import streamlit as st
import re
import io
import zipfile
import base64

# ============================================================
# 기본 형식 프롬프트 (Gems System Instructions v7.0)
# ============================================================

DEFAULT_FORMAT_PROMPT = """당신은 '2D 스틱맨 애니메이션 전문 프롬프트 디렉터'입니다.
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

#### 출력 형식
반드시 아래 형식으로 출력하세요:
1) "프롬프트 내용"
2) "프롬프트 내용"
...
"""

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
    """대본을 시간(초) 기준으로 분할. 1초당 약 4.5글자 기준."""
    text = text.strip()
    if not text:
        return []

    target = int(seconds * chars_per_sec)

    # 문장 단위로 먼저 분리 (마침표, 느낌표, 물음표, 줄바꿈 기준)
    sentences = re.split(r"(?<=[.!?。！？\n])\s*", text)
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        sentences = [text]

    # 문장들을 target 글자 수에 맞게 그룹핑
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

    # 여전히 너무 긴 세그먼트는 공백 기준으로 추가 분할
    final = []
    for seg in segments:
        if len(seg) > target * 1.5:
            final.extend(_split_at_spaces(seg, target))
        else:
            final.append(seg)

    return final if final else [text]


def _split_at_spaces(text: str, target: int) -> list:
    """긴 텍스트를 공백 기준으로 target 길이에 맞게 분할."""
    result = []
    while text:
        if len(text) <= target:
            result.append(text)
            break
        pos = text.rfind(" ", 0, target + 1)
        if pos <= 0:
            pos = text.find(" ", target)
        if pos <= 0:
            result.append(text)
            break
        result.append(text[:pos].strip())
        text = text[pos:].strip()
    return result


# ============================================================
# Gemini API 함수
# ============================================================

def get_gemini_client(api_key: str):
    """Gemini API 클라이언트 생성."""
    from google import genai
    return genai.Client(api_key=api_key)


def generate_prompts(client, model: str, system_prompt: str,
                     segments: list, section_label: str, lang_instruction: str) -> list:
    """Gemini LLM을 사용하여 각 세그먼트별 이미지 프롬프트 생성."""
    from google.genai import types

    numbered = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(segments))
    user_msg = (
        f"다음은 '{section_label}'의 대본 세그먼트입니다.\n"
        f"각 세그먼트에 대해 출력 템플릿 형식에 맞는 영문 이미지 프롬프트를 생성해주세요.\n\n"
        f"[언어 지시] {lang_instruction}\n\n"
        f"대본 세그먼트:\n{numbered}\n\n"
        f"위의 각 번호에 맞춰 영문 이미지 프롬프트를 작성하세요.\n"
        f'출력 형식: 번호) "프롬프트"\n'
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


def generate_image_gc(client, model: str, prompt: str) -> bytes:
    """generate_content (IMAGE 모달리티)로 이미지 생성."""
    from google.genai import types

    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
        ),
    )

    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            data = part.inline_data.data
            if isinstance(data, str):
                return base64.b64decode(data)
            return data
    return None


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


def create_zip(images: list) -> bytes:
    """(파일명, 바이트) 리스트를 ZIP으로 묶기."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in images:
            zf.writestr(name, data)
    return buf.getvalue()


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
}
for _k, _val in _defaults.items():
    if _k not in st.session_state:
        st.session_state[_k] = _val

# ============================================================
# 사이드바
# ============================================================

with st.sidebar:
    st.header("⚙️ 설정")

    api_key = st.text_input("Gemini API Key", type="password")

    st.divider()
    st.subheader("프롬프트 생성 (LLM)")
    prompt_model = st.text_input("모델명", value="gemini-2.5-flash-preview-05-20")

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

    st.divider()
    st.subheader("언어")
    language = st.selectbox("이미지 내 언어", list(LANGUAGE_MAP.keys()), index=3)

    st.divider()
    st.subheader("형식 프롬프트")
    format_prompt = st.text_area(
        "System Prompt (수정 가능)",
        value=DEFAULT_FORMAT_PROMPT,
        height=400,
    )

# ============================================================
# 메인 영역
# ============================================================

st.title("🎨 이미지 생성기")

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
    st.session_state.intro_segments = segment_text(intro_text, intro_sec)
    st.session_state.body_segments = segment_text(body_text, body_sec)
    st.session_state.v += 1
    st.session_state.prompts_ready = False
    st.session_state.images_ready = False
    st.session_state.intro_prompts = []
    st.session_state.body_prompts = []
    st.session_state.images = []
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
                secs = chars / 4.5
                if secs > 6:
                    st.error(f"⚠️ {chars}글자 / ~{secs:.1f}초  — 6초 초과!")
                else:
                    st.info(f"{chars}글자 / ~{secs:.1f}초")

            # 액션 버튼
            bc1, bc2, bc3, _ = st.columns(4)

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

            st.markdown("---")

        if st.button("➕ 도입부 컷 추가"):
            st.session_state.intro_segments.append("")
            st.session_state.v += 1
            st.rerun()

    # ===== 본문 =====
    if st.session_state.body_segments:
        st.subheader("📌 본문")
        ver = st.session_state.v

        for i in range(len(st.session_state.body_segments)):
            seg = st.session_state.body_segments[i]
            val = st.text_area(
                f"본문 컷 {i + 1}",
                value=seg,
                height=68,
                key=f"be_{i}_{ver}",
            )
            st.session_state.body_segments[i] = val
            chars = len(val)
            secs = chars / 4.5
            st.caption(f"{chars}글자 / ~{secs:.1f}초")

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
                            format_prompt,
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
                            format_prompt,
                            body_segs,
                            "본문",
                            lang_inst,
                        )
                    else:
                        st.session_state.body_prompts = []

                st.session_state.prompts_ready = True
                st.session_state.images_ready = False
                st.session_state.images = []
                st.rerun()

            except Exception as e:
                st.error(f"프롬프트 생성 실패: {e}")

    # 프롬프트 표시 / 편집
    if st.session_state.prompts_ready:
        ver = st.session_state.v

        if st.session_state.intro_prompts:
            st.subheader("📌 도입부 프롬프트")
            for i, p in enumerate(st.session_state.intro_prompts):
                val = st.text_area(
                    f"도입부 프롬프트 {i + 1}",
                    value=p,
                    height=120,
                    key=f"ip_{i}_{ver}",
                )
                st.session_state.intro_prompts[i] = val

        if st.session_state.body_prompts:
            st.subheader("📌 본문 프롬프트")
            for i, p in enumerate(st.session_state.body_prompts):
                val = st.text_area(
                    f"본문 프롬프트 {i + 1}",
                    value=p,
                    height=120,
                    key=f"bp_{i}_{ver}",
                )
                st.session_state.body_prompts[i] = val

# ────────────────────────────────────────────────────────────
# 4단계: 이미지 생성
# ────────────────────────────────────────────────────────────

if st.session_state.prompts_ready:
    st.divider()
    st.header("4단계: 이미지 생성")

    if st.button("🖼️ 이미지 생성", type="primary", use_container_width=True):
        if not api_key:
            st.error("API Key를 입력해주세요.")
        elif not image_model:
            st.error("사이드바에서 이미지 모델명을 입력해주세요.")
        else:
            try:
                client = get_gemini_client(api_key)

                all_prompts = []
                for i, p in enumerate(st.session_state.intro_prompts):
                    all_prompts.append((f"intro_{i + 1:03d}", p))
                for i, p in enumerate(st.session_state.body_prompts):
                    all_prompts.append((f"body_{i + 1:03d}", p))

                if not all_prompts:
                    st.warning("생성할 프롬프트가 없습니다.")
                else:
                    images = []
                    progress = st.progress(0, text="이미지 생성 준비 중...")

                    for idx, (label, prompt) in enumerate(all_prompts):
                        progress.progress(
                            idx / len(all_prompts),
                            text=f"이미지 생성 중... ({idx + 1}/{len(all_prompts)})",
                        )

                        try:
                            img_data = generate_image_gc(
                                client, image_model, prompt
                            )

                            if img_data:
                                images.append((label, img_data))
                            else:
                                st.warning(f"{label}: 이미지 생성 결과 없음")
                        except Exception as e:
                            st.warning(f"{label} 생성 실패: {e}")

                    progress.progress(1.0, text="완료!")
                    st.session_state.images = images
                    st.session_state.images_ready = True
                    st.rerun()

            except Exception as e:
                st.error(f"이미지 생성 실패: {e}")

    # 이미지 표시 & 다운로드
    if st.session_state.images_ready and st.session_state.images:
        st.subheader("생성된 이미지")

        # 도입부 / 본문 구분 표시
        intro_imgs = [
            (l, d) for l, d in st.session_state.images if l.startswith("intro_")
        ]
        body_imgs = [
            (l, d) for l, d in st.session_state.images if l.startswith("body_")
        ]

        if intro_imgs:
            st.markdown("**📌 도입부**")
            cols = st.columns(min(3, len(intro_imgs)))
            for idx, (label, img_data) in enumerate(intro_imgs):
                with cols[idx % len(cols)]:
                    st.image(img_data, caption=label, use_container_width=True)
                    st.download_button(
                        f"📥 {label}.png",
                        data=img_data,
                        file_name=f"{label}.png",
                        mime="image/png",
                        key=f"dl_i_{idx}",
                    )

        if body_imgs:
            st.markdown("**📌 본문**")
            cols = st.columns(min(3, len(body_imgs)))
            for idx, (label, img_data) in enumerate(body_imgs):
                with cols[idx % len(cols)]:
                    st.image(img_data, caption=label, use_container_width=True)
                    st.download_button(
                        f"📥 {label}.png",
                        data=img_data,
                        file_name=f"{label}.png",
                        mime="image/png",
                        key=f"dl_b_{idx}",
                    )

        # 전체 ZIP 다운로드
        st.divider()
        zip_data = create_zip(
            [(f"{label}.png", data) for label, data in st.session_state.images]
        )
        st.download_button(
            "📦 전체 ZIP 다운로드",
            data=zip_data,
            file_name="generated_images.zip",
            mime="application/zip",
            type="primary",
            use_container_width=True,
        )
