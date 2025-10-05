def process_basic_conversation_mode():
    """日常英会話モードの処理"""
    audio_input_file_path = f"{const.AUDIO_INPUT_DIR}/audio_input_{int(time.time())}.wav"
    record_audio(audio_input_file_path)
    
    with st.spinner('音声入力をテキストに変換中...'):
        transcript = transcribe_audio(audio_input_file_path)
        audio_input_text = transcript.text
    
    with st.chat_message("user", avatar=const.USER_ICON_PATH):
        st.markdown(audio_input_text)
    
    with st.spinner("回答の音声読み上げ準備中..."):
        improvement_analysis = analyze_user_input_improvements(audio_input_text, st.session_state.english_level)
        audio_improvement_analysis = analyze_user_audio_improvements(audio_input_file_path, audio_input_text, st.session_state.english_level)
        
        # 新しいAPIでチェーンを呼び出し
        response = st.session_state.chain_basic_conversation.invoke(
            {"input": audio_input_text},
            config={"configurable": {"session_id": "conversation_session"}}
        )
        
        # レスポンスから内容を取得
        if hasattr(response, 'content'):
            llm_response = response.content
        else:
            llm_response = str(response)
        
        llm_response_audio = st.session_state.openai_client.audio.speech.create(
            model="tts-1",
            voice=st.session_state.voice,
            input=llm_response
        )
        
        audio_output_file_path = f"{const.AUDIO_OUTPUT_DIR}/audio_output_{int(time.time())}.wav"
        save_to_wav(llm_response_audio.content, audio_output_file_path)
    
    play_wav(audio_output_file_path, speed=st.session_state.speed)
    
    with st.chat_message("assistant", avatar=const.AI_ICON_PATH):
        st.markdown(llm_response)
    
    if improvement_analysis:
        st.session_state.last_improvement_analysis = improvement_analysis
    if audio_improvement_analysis:
        st.session_state.last_audio_improvement_analysis = audio_improvement_analysis
    
    st.session_state.messages.append({"role": "user", "content": audio_input_text})
    st.session_state.messages.append({"role": "assistant", "content": llm_response})

def process_shadowing_mode():
    """シャドーイングモードの処理"""
    should_process = (st.session_state.shadowing_button_flag or 
                      st.session_state.shadowing_count == 0 or 
                      st.session_state.shadowing_audio_input_flag)
    
    if not should_process:
        return False
    
    if not st.session_state.shadowing_audio_input_flag:
        with st.spinner('AI文章生成中...'):
            st.session_state.ai_sentence, st.session_state.reference_audio_path = create_problem_and_play_audio(st.session_state.english_level, "shadowing")
    
    st.session_state.shadowing_audio_input_flag = True
    user_audio_path = f"{const.AUDIO_INPUT_DIR}/audio_input_{int(time.time())}.wav"
    record_audio(user_audio_path)
    st.session_state.shadowing_audio_input_flag = False
    
    with st.spinner('音声品質向上処理中...'):
        enhance_audio_quality(user_audio_path)
    
    with st.chat_message("assistant", avatar=const.AI_ICON_PATH):
        st.markdown(f"**AI文章:** {st.session_state.ai_sentence}")
    with st.chat_message("user", avatar=const.USER_ICON_PATH):
        st.markdown("**あなたの音声:** 録音完了")
    
    st.session_state.messages.append({"role": "assistant", "content": st.session_state.ai_sentence})
    st.session_state.messages.append({"role": "user", "content": "音声録音完了"})
    
    with st.spinner('音声比較と評価結果の生成中...'):
        evaluation = create_audio_based_evaluation(
            st.session_state.ai_sentence,
            st.session_state.reference_audio_path,
            user_audio_path,
            st.session_state.english_level
        )
    
    with st.chat_message("assistant", avatar=const.AI_ICON_PATH):
        st.markdown(evaluation)
    st.session_state.messages.append({"role": "assistant", "content": evaluation})
    st.session_state.messages.append({"role": "other"})
    
    cleanup_audio_files(
        user_audio_path,
        st.session_state.reference_audio_path if hasattr(st.session_state, 'reference_audio_path') else None
    )
    
    st.session_state.shadowing_flag = True
    st.session_state.shadowing_count += 1
    return True

def process_dictation_mode():
    """ディクテーションモードの処理"""
    should_process = (st.session_state.dictation_button_flag or 
                      st.session_state.dictation_count == 0 or 
                      st.session_state.dictation_user_input)
    
    if not should_process:
        return False
    
    # AI文章生成フェーズ
    if not st.session_state.chat_open_flag:
        with st.spinner('AI文章生成中...'):
            st.session_state.ai_sentence, ai_audio_path = create_problem_and_play_audio(st.session_state.english_level, "dictation")
        
        st.session_state.chat_open_flag = True
        st.session_state.dictation_flag = False
        return True
    
    # 評価フェーズ
    else:
        if not st.session_state.dictation_user_input:
            return False
        
        with st.chat_message("assistant", avatar=const.AI_ICON_PATH):
            st.markdown(f"**AI文章:** {st.session_state.ai_sentence}")
        with st.chat_message("user", avatar=const.USER_ICON_PATH):
            st.markdown(f"**あなたの回答:** {st.session_state.dictation_user_input}")
        
        st.session_state.messages.append({"role": "assistant", "content": st.session_state.ai_sentence})
        st.session_state.messages.append({"role": "user", "content": st.session_state.dictation_user_input})
        
        with st.spinner('評価結果の生成中...'):
            if st.session_state.english_level in const.SYSTEM_TEMPLATE_DICTATION_EVALUATION_BY_LEVEL:
                system_template = const.SYSTEM_TEMPLATE_DICTATION_EVALUATION_BY_LEVEL[st.session_state.english_level].format(
                    llm_text=st.session_state.ai_sentence,
                    user_text=st.session_state.dictation_user_input
                )
            else:
                system_template = const.SYSTEM_TEMPLATE_DICTATION_EVALUATION_BY_LEVEL["初級者"].format(
                    llm_text=st.session_state.ai_sentence,
                    user_text=st.session_state.dictation_user_input
                )
            st.session_state.chain_evaluation = create_chain(system_template)
            evaluation = create_evaluation(st.session_state.english_level)
        
        with st.chat_message("assistant", avatar=const.AI_ICON_PATH):
            st.markdown(evaluation)
        st.session_state.messages.append({"role": "assistant", "content": evaluation})
        st.session_state.messages.append({"role": "other"})
        
        st.session_state.dictation_flag = True
        st.session_state.dictation_user_input = ""
        st.session_state.dictation_count += 1
        st.session_state.chat_open_flag = False
        return True

import streamlit as st
import os
import time
from pathlib import Path
import wave
import pyaudio
from pydub import AudioSegment
from audiorecorder import audiorecorder
import numpy as np
from scipy.io.wavfile import write
from langchain.prompts import (
    ChatPromptTemplate,
    MessagesPlaceholder,
)
from langchain.schema import SystemMessage
from langchain_openai import ChatOpenAI
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import StreamlitChatMessageHistory
from openai import OpenAI
import constants as const

# ================== 初期化関連 ==================

def initialize_session_state():
    """セッション状態の初期化"""
    if "messages" in st.session_state:
        return
    
    # 全フラグを一括初期化
    initial_state = {
        # 基本フラグ
        "start_flag": False,
        "previous_mode": "",
        "chat_open_flag": False,
        "ai_sentence": "",  # AIが生成した文章
        # シャドーイング関連
        "shadowing_flag": False,
        "shadowing_button_flag": False,
        "shadowing_count": 0,
        "shadowing_first_flag": True,
        "shadowing_audio_input_flag": False,
        "shadowing_evaluation_first_flag": True,
        # ディクテーション関連
        "dictation_flag": False,
        "dictation_button_flag": False,
        "dictation_count": 0,
        "dictation_first_flag": True,
        "dictation_user_input": "",  # ユーザーの入力
        "dictation_evaluation_first_flag": True,
    }
    
    for key, value in initial_state.items():
        st.session_state[key] = value
    
    # 音声設定の初期化
    voice_settings = const.VOICE_SETTINGS["初級者"]
    st.session_state.voice = voice_settings["voice"]
    st.session_state.speed = voice_settings["speed"]
    
    # OpenAI初期化
    try:
        st.session_state.openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        st.session_state.llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0.5)
    except Exception as e:
        st.error(f"OpenAI初期化エラー: {str(e)}")
        st.stop()
    
    # メッセージ・チャット履歴の初期化
    st.session_state.mode_messages = {const.MODE_1: []}
    st.session_state.messages = st.session_state.mode_messages[const.MODE_1]
    st.session_state.chat_history = StreamlitChatMessageHistory(key="chat_messages")
    
    # チェーン作成
    st.session_state.chain_basic_conversation = create_chain(english_level="初級者")

def handle_mode_change():
    """モード変更時の処理"""
    if st.session_state.mode == st.session_state.previous_mode:
        return
    
    # 共通の初期化
    st.session_state.start_flag = False
    st.session_state.chat_open_flag = False
    st.session_state.shadowing_count = 0
    st.session_state.dictation_count = 0
    
    # モード別の初期化
    mode_flags = {
        const.MODE_1: {"dictation_flag": False, "shadowing_flag": False},
        const.MODE_2: {"dictation_flag": False},
        const.MODE_3: {"shadowing_flag": False}
    }
    
    for key, value in mode_flags.get(st.session_state.mode, {}).items():
        st.session_state[key] = value
    
    st.session_state.previous_mode = st.session_state.mode

def handle_english_level_change():
    """英語レベル変更時の処理"""
    if "previous_english_level" not in st.session_state:
        st.session_state.previous_english_level = st.session_state.english_level
        return False
    
    if st.session_state.english_level != st.session_state.previous_english_level:
        st.session_state.chain_basic_conversation = create_chain(english_level=st.session_state.english_level)
        
        voice_settings = const.VOICE_SETTINGS[st.session_state.english_level]
        st.session_state.voice = voice_settings["voice"]
        st.session_state.speed = voice_settings["speed"]
        
        st.session_state.previous_english_level = st.session_state.english_level
        return True
    
    return False

# ================== 音声処理関連 ==================

def record_audio(audio_input_file_path):
    """
    音声入力を受け取って音声ファイルを作成
    Args:
        audio_input_file_path: 音声ファイルの保存パス
    """
    try:
        audio = audiorecorder(
            start_prompt="発話開始",
            pause_prompt="やり直す",
            stop_prompt="発話終了"
        )

        if len(audio) > 0:
            audio.export(audio_input_file_path, format="wav")
        else:
            st.stop()
    except Exception as e:
        print(f"音声録音エラー: {e}")
        st.error("音声録音に失敗しました。テキスト入力でお試しください。")
        st.stop()

def transcribe_audio(audio_input_file_path, enhance_quality=True):
    """
    音声入力ファイルから文字起こしテキストを取得
    Args:
        audio_input_file_path: 音声入力ファイルのパス
        enhance_quality: 音声品質向上処理を行うかどうか
    """
    if not os.path.exists(audio_input_file_path):
        return None
    
    file_size = os.path.getsize(audio_input_file_path)
    if file_size == 0:
        return None

    if enhance_quality:
        try:
            enhanced_audio_path = enhance_audio_quality(audio_input_file_path)
        except Exception as e:
            pass

    try:
        with open(audio_input_file_path, 'rb') as audio_input_file:
            transcript = st.session_state.openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_input_file,
                language="en"
            )
    except Exception as e:
        return None
    
    os.remove(audio_input_file_path)
    return transcript

def save_to_wav(llm_response_audio, audio_output_file_path):
    """
    mp3からwav形式に変換して保存
    Args:
        llm_response_audio: LLMからの回答の音声データ
        audio_output_file_path: 出力先のファイルパス
    """
    temp_audio_path = f"{const.AUDIO_OUTPUT_DIR}/temp_audio_output_{int(time.time())}.mp3"
    
    try:
        with open(temp_audio_path, "wb") as f:
            f.write(llm_response_audio)
        
        audio_mp3 = AudioSegment.from_file(temp_audio_path, format="mp3")
        audio_mp3.export(audio_output_file_path, format="wav")
    finally:
        if os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)

def play_wav(audio_output_file_path, speed=1.0):
    """
    音声ファイルの読み上げ
    Args:
        audio_output_file_path: 音声ファイルのパス
        speed: 再生速度
    """
    try:
        audio = AudioSegment.from_wav(audio_output_file_path)
        
        # 速度変更
        if speed != 1.0:
            modified_audio = audio._spawn(
                audio.raw_data, 
                overrides={"frame_rate": int(audio.frame_rate * speed)}
            )
            temp_audio_path = audio_output_file_path.replace('.wav', '_temp.wav')
            modified_audio.export(temp_audio_path, format="wav")
            
            import shutil
            shutil.move(temp_audio_path, audio_output_file_path)

        # PyAudioで再生
        with wave.open(audio_output_file_path, 'rb') as wf:
            p = pyaudio.PyAudio()
            stream = p.open(
                format=p.get_format_from_width(wf.getsampwidth()),
                channels=wf.getnchannels(),
                rate=wf.getframerate(),
                output=True
            )

            chunk = 1024
            data = wf.readframes(chunk)
            while data:
                stream.write(data)
                data = wf.readframes(chunk)

            stream.stop_stream()
            stream.close()
            p.terminate()
        
    except (OSError, Exception) as e:
        print(f"音声再生エラーをスキップしました: {e}")
        pass

def cleanup_audio_files(*audio_paths):
    """
    音声ファイルのクリーンアップ
    Args:
        *audio_paths: 削除する音声ファイルのパス（可変長引数）
    """
    for audio_path in audio_paths:
        try:
            if audio_path and os.path.exists(audio_path):
                os.remove(audio_path)
        except Exception as e:
            pass

def enhance_audio_quality(audio_file_path):
    """音声品質を向上させる前処理"""
    try:
        import librosa
        import soundfile as sf
        
        settings = const.AUDIO_ENHANCEMENT_SETTINGS
        
        audio, sample_rate = librosa.load(audio_file_path, sr=settings["target_sample_rate"])
        audio = librosa.effects.preemphasis(audio, coef=settings["preemphasis_coeff"])
        audio = librosa.util.normalize(audio, norm=np.inf) * settings["normalization_level"]
        audio, _ = librosa.effects.trim(audio, top_db=settings["trim_threshold"])
        
        sf.write(audio_file_path, audio, sample_rate)
        return audio_file_path
    except (ImportError, Exception):
        return audio_file_path

# ================== LLM処理関連 ==================

def create_chain(system_template=None, english_level=None):
    """
    LLMによる回答生成用のChain作成（最新のLangChain API使用）
    """
    # テンプレート選択
    selected_template = (
        const.SYSTEM_TEMPLATE_BASIC_CONVERSATION.get(english_level) or
        system_template or
        const.SYSTEM_TEMPLATE_BASIC_CONVERSATION["初級者"]
    )

    # コンテキスト構築
    contexts = []
    if hasattr(st.session_state, 'last_improvement_analysis') and st.session_state.last_improvement_analysis:
        contexts.append(const.SYSTEM_TEMPLATE_TEXT_IMPROVEMENT_INTEGRATION.format(
            text_improvement_analysis=st.session_state.last_improvement_analysis
        ))
    
    if hasattr(st.session_state, 'last_audio_improvement_analysis') and st.session_state.last_audio_improvement_analysis:
        contexts.append(const.SYSTEM_TEMPLATE_AUDIO_IMPROVEMENT_INTEGRATION.format(
            audio_improvement_analysis=st.session_state.last_audio_improvement_analysis
        ))

    enhanced_template = f"{selected_template}\n\n{const.SYSTEM_TEMPLATE_CONVERSATION_IMPROVEMENT_INTEGRATION}{''.join(contexts)}"

    # チェーン構築
    prompt = ChatPromptTemplate.from_messages([
        ("system", enhanced_template),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}")
    ])
    
    chain = prompt | st.session_state.llm
    
    return RunnableWithMessageHistory(
        chain,
        lambda session_id: st.session_state.chat_history,
        input_messages_key="input",
        history_messages_key="chat_history",
    )

def create_evaluation(english_level="初級者"):
    """
    ユーザー入力値の評価生成
    Args:
        english_level: 英語レベル
    """
    response = st.session_state.chain_evaluation.invoke(
        {"input": "上記の情報を基に、詳細な評価を提供してください。"},
        config={"configurable": {"session_id": "evaluation_session"}}
    )
    
    return response.content if hasattr(response, 'content') else str(response)

# ================== 問題生成・評価関連 ==================

def extract_vocabulary_from_sentence(sentence):
    """
    文からvocabularyを抽出する
    Args:
        sentence: 英文
    Returns:
        list: 抽出された単語のリスト
    """
    import re
    words = re.findall(r'\b[a-zA-Z]{2,}\b', sentence.lower())
    stop_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
        'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
        'will', 'would', 'could', 'should', 'may', 'might', 'can', 'this', 'that', 'these', 'those',
        'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them'
    }
    vocabulary = [word for word in words if word not in stop_words]
    return vocabulary

def update_vocabulary_history(mode, vocabulary_list):
    """
    vocabulary履歴を更新する
    Args:
        mode: "dictation" または "shadowing"
        vocabulary_list: 使用されたvocabularyのリスト
    """
    if f'{mode}_vocabulary_history' not in st.session_state:
        st.session_state[f'{mode}_vocabulary_history'] = []
    
    st.session_state[f'{mode}_vocabulary_history'].append(vocabulary_list)
    
    if len(st.session_state[f'{mode}_vocabulary_history']) > 3:
        st.session_state[f'{mode}_vocabulary_history'] = st.session_state[f'{mode}_vocabulary_history'][-3:]

def get_avoid_vocabulary(mode):
    """
    避けるべきvocabularyのリストを取得
    Args:
        mode: "dictation" または "shadowing"
    Returns:
        set: 避けるべきvocabularyのセット
    """
    if f'{mode}_vocabulary_history' not in st.session_state:
        return set()
    
    avoid_vocab = set()
    for vocab_list in st.session_state[f'{mode}_vocabulary_history']:
        avoid_vocab.update(vocab_list)
    
    return avoid_vocab

def create_problem_and_play_audio(english_level="初級者", mode="shadowing"):
    """
    AI文章生成と音声ファイルの再生
    Args:
        english_level: 英語レベル
        mode: "dictation" または "shadowing"
    Returns:
        tuple: (AIが生成した文章, 音声ファイルパス)
    """
    import random
    
    # プロンプト選択
    base_prompt = const.SYSTEM_TEMPLATE_SHADOWING_PROBLEM_BY_LEVEL.get(
        english_level,
        const.SYSTEM_TEMPLATE_SHADOWING_PROBLEM_BY_LEVEL["初級者"]
    )
    
    # 避けるべき語彙を取得
    avoid_vocab = get_avoid_vocabulary(mode)
    avoid_vocab_str = ", ".join(sorted(avoid_vocab)) if avoid_vocab else "None"
    
    # ランダム化プロンプト構築
    random_prompt = f"""{base_prompt}

RANDOMIZATION PARAMETERS:
- Random seed: {random.randint(1, 10000)}
- Timestamp: {int(time.time())}
- English Level: {english_level}

VOCABULARY AVOIDANCE:
- Avoid using these words from recent sessions: {avoid_vocab_str}
- Use completely different vocabulary to ensure variety

Generate a completely unique sentence appropriate for {english_level} level learners."""
    
    # AI文章生成
    response = st.session_state.llm.invoke([SystemMessage(content=random_prompt)])
    ai_sentence = response.content

    # 語彙履歴を更新
    sentence_vocabulary = extract_vocabulary_from_sentence(ai_sentence)
    update_vocabulary_history(mode, sentence_vocabulary)

    # 音声生成と保存
    ai_audio = st.session_state.openai_client.audio.speech.create(
        model="tts-1",
        voice=st.session_state.voice,
        input=ai_sentence
    )

    audio_output_path = f"{const.AUDIO_OUTPUT_DIR}/audio_output_{int(time.time())}.wav"
    save_to_wav(ai_audio.content, audio_output_path)
    play_wav(audio_output_path, st.session_state.speed)

    return ai_sentence, audio_output_path

def compare_audio_files(reference_audio_path, user_audio_path):
    """
    音声ファイル同士を比較して発音の類似度を分析
    Args:
        reference_audio_path: 参考音声のパス
        user_audio_path: ユーザー音声のパス
    Returns:
        dict: 音声比較結果
    """
    try:
        import librosa
        import numpy as np
        from scipy.spatial.distance import cosine
        
        ref_audio, ref_sr = librosa.load(reference_audio_path, sr=16000)
        user_audio, user_sr = librosa.load(user_audio_path, sr=16000)
        
        min_length = min(len(ref_audio), len(user_audio))
        ref_audio = ref_audio[:min_length]
        user_audio = user_audio[:min_length]
        
        ref_mfcc = librosa.feature.mfcc(y=ref_audio, sr=ref_sr, n_mfcc=13)
        user_mfcc = librosa.feature.mfcc(y=user_audio, sr=user_sr, n_mfcc=13)
        
        ref_mfcc_mean = np.mean(ref_mfcc, axis=1)
        user_mfcc_mean = np.mean(user_mfcc, axis=1)
        
        similarity = 1 - cosine(ref_mfcc_mean, user_mfcc_mean)
        
        ref_spectral_centroid = np.mean(librosa.feature.spectral_centroid(y=ref_audio, sr=ref_sr))
        user_spectral_centroid = np.mean(librosa.feature.spectral_centroid(y=user_audio, sr=user_sr))
        
        ref_zcr = np.mean(librosa.feature.zero_crossing_rate(ref_audio))
        user_zcr = np.mean(librosa.feature.zero_crossing_rate(user_audio))
        
        spectral_similarity = 1 - abs(ref_spectral_centroid - user_spectral_centroid) / max(ref_spectral_centroid, user_spectral_centroid)
        zcr_similarity = 1 - abs(ref_zcr - user_zcr) / max(ref_zcr, user_zcr)
        
        ref_energy = librosa.feature.rms(y=ref_audio)[0]
        user_energy = librosa.feature.rms(y=user_audio)[0]
        energy_similarity = 1 - cosine(ref_energy, user_energy)
        
        overall_score = (similarity * 0.5 + spectral_similarity * 0.2 + zcr_similarity * 0.2 + energy_similarity * 0.1) * 100
        
        result = {
            "similarity": similarity,
            "mfcc_similarity": similarity,
            "spectral_similarity": spectral_similarity,
            "zcr_similarity": zcr_similarity,
            "energy_similarity": energy_similarity,
            "overall_score": overall_score,
            "reference_duration": len(ref_audio) / ref_sr,
            "user_duration": len(user_audio) / user_sr
        }
        
        return result
        
    except ImportError as e:
        return None
    except Exception as e:
        return None

def create_audio_based_evaluation(ai_sentence, reference_audio_path, user_audio_path, english_level="初級者"):
    """
    音声比較を基にした評価生成
    Args:
        ai_sentence: AIが生成した文章
        reference_audio_path: 参考音声（AI生成）のパス
        user_audio_path: ユーザー音声のパス
        english_level: 英語レベル
    Returns:
        str: 評価結果
    """
    audio_comparison_result = compare_audio_files(reference_audio_path, user_audio_path)
    
    if audio_comparison_result:
        audio_analysis = const.AUDIO_ANALYSIS_TEMPLATE.format(
            mfcc_similarity_percent=100*audio_comparison_result['mfcc_similarity'],
            spectral_similarity_percent=100*audio_comparison_result['spectral_similarity'],
            zcr_similarity_percent=100*audio_comparison_result['zcr_similarity'],
            energy_similarity_percent=100*audio_comparison_result['energy_similarity'],
            overall_score=audio_comparison_result['overall_score'],
            reference_duration=audio_comparison_result['reference_duration'],
            user_duration=audio_comparison_result['user_duration']
        )
    else:
        audio_analysis = const.AUDIO_ANALYSIS_ERROR_MESSAGE
    
    if english_level in const.SYSTEM_TEMPLATE_SHADOWING_EVALUATION_BY_LEVEL:
        system_template = const.SYSTEM_TEMPLATE_SHADOWING_EVALUATION_BY_LEVEL[english_level].format(
            problem_text=ai_sentence,
            audio_analysis=audio_analysis
        )
    else:
        system_template = const.SYSTEM_TEMPLATE_SHADOWING_EVALUATION_BY_LEVEL["初級者"].format(
            problem_text=ai_sentence,
            audio_analysis=audio_analysis
        )

    st.session_state.chain_evaluation = create_chain(system_template)
    llm_response_evaluation = create_evaluation(english_level)

    return llm_response_evaluation

# ================== 改善点分析関連 ==================

def analyze_user_input_improvements(user_input, english_level="初級者"):
    """
    ユーザー入力の改善点を分析する
    Args:
        user_input: ユーザーの入力文
        english_level: 英語レベル
    Returns:
        str: 改善点の分析結果
    """
    if not user_input or len(user_input.strip()) < 3:
        return ""
    
    prompt = const.SYSTEM_TEMPLATE_USER_INPUT_IMPROVEMENT_ANALYSIS.get(
        english_level, 
        const.SYSTEM_TEMPLATE_USER_INPUT_IMPROVEMENT_ANALYSIS["初級者"]
    )
    analysis_prompt = prompt.format(user_input=user_input)
    
    try:
        response = st.session_state.llm.invoke([
            SystemMessage(content=analysis_prompt)
        ])
        return response.content.strip()
    except Exception as e:
        print(f"改善点分析エラー: {e}")
        return ""

def analyze_user_audio_improvements(audio_file_path, user_input_text, english_level="初級者"):
    """
    ユーザー音声の改善点を分析する
    Args:
        audio_file_path: ユーザー音声ファイルのパス
        user_input_text: ユーザー入力の文字起こしテキスト
        english_level: 英語レベル
    Returns:
        str: 音声改善点の分析結果
    """
    if not audio_file_path or not os.path.exists(audio_file_path):
        return ""
    
    audio_analysis_result = analyze_pronunciation_detailed(audio_file_path, user_input_text)
    
    prompt = const.SYSTEM_TEMPLATE_USER_AUDIO_IMPROVEMENT_ANALYSIS.get(
        english_level, 
        const.SYSTEM_TEMPLATE_USER_AUDIO_IMPROVEMENT_ANALYSIS["初級者"]
    )
    analysis_prompt = prompt.format(
        user_input=user_input_text,
        audio_analysis=audio_analysis_result
    )
    
    try:
        response = st.session_state.llm.invoke([
            SystemMessage(content=analysis_prompt)
        ])
        return response.content.strip()
    except Exception as e:
        print(f"音声改善点分析エラー: {e}")
        return ""

def analyze_pronunciation_detailed(audio_file_path, text):
    """
    音声の発音詳細分析
    Args:
        audio_file_path: 音声ファイルのパス
        text: 対応するテキスト
    Returns:
        str: 発音分析結果
    """
    try:
        import librosa
        import numpy as np
        
        audio, sr = librosa.load(audio_file_path, sr=16000)
        
        rms_energy = np.mean(librosa.feature.rms(y=audio)[0])
        word_count = len(text.split())
        duration = len(audio) / sr
        speaking_rate = word_count / duration if duration > 0 else 0
        spectral_centroid = np.mean(librosa.feature.spectral_centroid(y=audio, sr=sr)[0])
        
        frame_length = 2048
        hop_length = 512
        frames = librosa.util.frame(audio, frame_length=frame_length, hop_length=hop_length)
        energy = np.mean(frames**2, axis=0)
        silence_threshold = np.percentile(energy, 20)
        silence_ratio = np.sum(energy < silence_threshold) / len(energy)
        volume_stability = 1.0 - np.std(librosa.feature.rms(y=audio)[0])
        
        analysis_result = f"""
【音声分析結果】
- 音量レベル: {'適切' if 0.01 < rms_energy < 0.5 else '調整が必要'}
- 話速: {speaking_rate:.1f}語/秒 ({'適切' if 1.5 < speaking_rate < 3.5 else '調整が必要'})
- 音の明瞭度: {'良好' if spectral_centroid > 1000 else '改善の余地あり'}
- 無音部分: {silence_ratio*100:.1f}% ({'適切' if silence_ratio < 0.3 else '多い'})
- 音量安定性: {'良好' if volume_stability > 0.7 else '改善が必要'}
"""
        
        return analysis_result
        
    except ImportError:
        return "音声分析ライブラリが利用できません。"
    except Exception as e:
        return f"音声分析中にエラーが発生しました: {str(e)}"

# ================== モード処理関連 ==================

def process_basic_conversation_mode():
    """日常英会話モードの処理"""
    audio_input_file_path = f"{ct.AUDIO_INPUT_DIR}/audio_input_{int(time.time())}.wav"
    record_audio(audio_input_file_path)
    
    with st.spinner('音声入力をテキストに変換中...'):
        transcript = transcribe_audio(audio_input_file_path)
        audio_input_text = transcript.text
    
    with st.chat_message("user", avatar=ct.USER_ICON_PATH):
        st.markdown(audio_input_text)
    
    with st.spinner("回答の音声読み上げ準備中..."):
        improvement_analysis = analyze_user_input_improvements(audio_input_text, st.session_state.englv)
        audio_improvement_analysis = analyze_user_audio_improvements(audio_input_file_path, audio_input_text, st.session_state.englv)
        
        # 新しいAPIでチェーンを呼び出し
        response = st.session_state.chain_basic_conversation.invoke(
            {"input": audio_input_text},
            config={"configurable": {"session_id": "conversation_session"}}
        )
        
        # レスポンスから内容を取得
        if hasattr(response, 'content'):
            llm_response = response.content
        else:
            llm_response = str(response)
        
        llm_response_audio = st.session_state.openai_obj.audio.speech.create(
            model="tts-1",
            voice=st.session_state.voice,
            input=llm_response
        )
        
        audio_output_file_path = f"{ct.AUDIO_OUTPUT_DIR}/audio_output_{int(time.time())}.wav"
        save_to_wav(llm_response_audio.content, audio_output_file_path)
    
    play_wav(audio_output_file_path, speed=st.session_state.speed)
    
    with st.chat_message("assistant", avatar=ct.AI_ICON_PATH):
        st.markdown(llm_response)
    
    if improvement_analysis:
        st.session_state.last_improvement_analysis = improvement_analysis
    if audio_improvement_analysis:
        st.session_state.last_audio_improvement_analysis = audio_improvement_analysis
    
    st.session_state.messages.append({"role": "user", "content": audio_input_text})
    st.session_state.messages.append({"role": "assistant", "content": llm_response})

def process_shadowing_mode():
    """シャドーイングモードの処理"""
    should_process = (st.session_state.shadowing_button_flg or 
                      st.session_state.shadowing_count == 0 or 
                      st.session_state.shadowing_audio_input_flg)
    
    if not should_process:
        return False
    
    if not st.session_state.shadowing_audio_input_flg:
        with st.spinner('AI文章生成中...'):
            st.session_state.ai_sentence, st.session_state.reference_audio_path = create_problem_and_play_audio(st.session_state.englv, "shadowing")
    
    st.session_state.shadowing_audio_input_flg = True
    user_audio_path = f"{ct.AUDIO_INPUT_DIR}/audio_input_{int(time.time())}.wav"
    record_audio(user_audio_path)
    st.session_state.shadowing_audio_input_flg = False
    
    with st.spinner('音声品質向上処理中...'):
        enhance_audio_quality(user_audio_path)
    
    with st.chat_message("assistant", avatar=ct.AI_ICON_PATH):
        st.markdown(f"**AI文章:** {st.session_state.ai_sentence}")
    with st.chat_message("user", avatar=ct.USER_ICON_PATH):
        st.markdown("**あなたの音声:** 録音完了")
    
    st.session_state.messages.append({"role": "assistant", "content": st.session_state.ai_sentence})
    st.session_state.messages.append({"role": "user", "content": "音声録音完了"})
    
    with st.spinner('音声比較と評価結果の生成中...'):
        evaluation = create_audio_based_evaluation(
            st.session_state.ai_sentence,
            st.session_state.reference_audio_path,
            user_audio_path,
            st.session_state.englv
        )
    
    with st.chat_message("assistant", avatar=ct.AI_ICON_PATH):
        st.markdown(evaluation)
    st.session_state.messages.append({"role": "assistant", "content": evaluation})
    st.session_state.messages.append({"role": "other"})
    
    cleanup_audio_files(
        user_audio_path,
        st.session_state.reference_audio_path if hasattr(st.session_state, 'reference_audio_path') else None
    )
    
    st.session_state.shadowing_flg = True
    st.session_state.shadowing_count += 1
    return True

def process_dictation_mode():
    """ディクテーションモードの処理"""
    should_process = (st.session_state.dictation_button_flg or 
                      st.session_state.dictation_count == 0 or 
                      st.session_state.dictation_user_input)
    
    if not should_process:
        return False
    
    # AI文章生成フェーズ
    if not st.session_state.chat_open_flg:
        with st.spinner('AI文章生成中...'):
            st.session_state.ai_sentence, ai_audio_path = create_problem_and_play_audio(st.session_state.englv, "dictation")
        
        st.session_state.chat_open_flg = True
        st.session_state.dictation_flg = False
        return True
    
    # 評価フェーズ
    else:
        if not st.session_state.dictation_user_input:
            return False
        
        with st.chat_message("assistant", avatar=ct.AI_ICON_PATH):
            st.markdown(f"**AI文章:** {st.session_state.ai_sentence}")
        with st.chat_message("user", avatar=ct.USER_ICON_PATH):
            st.markdown(f"**あなたの回答:** {st.session_state.dictation_user_input}")
        
        st.session_state.messages.append({"role": "assistant", "content": st.session_state.ai_sentence})
        st.session_state.messages.append({"role": "user", "content": st.session_state.dictation_user_input})
        
        with st.spinner('評価結果の生成中...'):
            if st.session_state.englv in ct.SYSTEM_TEMPLATE_DICTATION_EVALUATION_BY_LEVEL:
                system_template = ct.SYSTEM_TEMPLATE_DICTATION_EVALUATION_BY_LEVEL[st.session_state.englv].format(
                    llm_text=st.session_state.ai_sentence,
                    user_text=st.session_state.dictation_user_input
                )
            else:
                system_template = ct.SYSTEM_TEMPLATE_DICTATION_EVALUATION_BY_LEVEL["初級者"].format(
                    llm_text=st.session_state.ai_sentence,
                    user_text=st.session_state.dictation_user_input
                )
            st.session_state.chain_evaluation = create_chain(system_template)
            evaluation = create_evaluation(st.session_state.englv)
        
        with st.chat_message("assistant", avatar=ct.AI_ICON_PATH):
            st.markdown(evaluation)
        st.session_state.messages.append({"role": "assistant", "content": evaluation})
        st.session_state.messages.append({"role": "other"})
        
        st.session_state.dictation_flg = True
        st.session_state.dictation_user_input = ""
        st.session_state.dictation_count += 1
        st.session_state.chat_open_flg = False
        return True