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
    HumanMessagePromptTemplate,
    MessagesPlaceholder,
)
from langchain.schema import SystemMessage
from langchain.memory import ConversationSummaryBufferMemory
from langchain_openai import ChatOpenAI
from langchain.chains import ConversationChain
import constants as ct

def record_audio(audio_input_file_path):
    """
    音声入力を受け取って音声ファイルを作成
    Args:
        audio_input_file_path: 音声ファイルの保存パス
    """

    # シンプルなaudiorecorderの使用（再試行なし）
    audio = audiorecorder(
        start_prompt="発話開始",
        pause_prompt="やり直す",
        stop_prompt="発話終了"
    )

    if len(audio) > 0:
        # シンプルな音声エクスポート
        audio.export(audio_input_file_path, format="wav")
    else:
        st.stop()

def transcribe_audio(audio_input_file_path, enhance_quality=True):
    """
    音声入力ファイルから文字起こしテキストを取得
    Args:
        audio_input_file_path: 音声入力ファイルのパス
        enhance_quality: 音声品質向上処理を行うかどうか
    """
    # ファイルの存在確認
    if not os.path.exists(audio_input_file_path):
        return None
    
    # ファイルサイズの確認
    file_size = os.path.getsize(audio_input_file_path)
    
    if file_size == 0:
        return None

    # 音声品質向上処理（オプション）
    if enhance_quality:
        try:
            enhanced_audio_path = enhance_audio_quality(audio_input_file_path)
        except Exception as e:
            pass

    try:
        with open(audio_input_file_path, 'rb') as audio_input_file:
            transcript = st.session_state.openai_obj.audio.transcriptions.create(
                model="whisper-1",
                file=audio_input_file,
                language="en"
            )
    except Exception as e:
        return None
    
    # 音声入力ファイルを削除
    os.remove(audio_input_file_path)

    return transcript

def save_to_wav(llm_response_audio, audio_output_file_path):
    """
    一旦mp3形式で音声ファイル作成後、wav形式に変換
    Args:
        llm_response_audio: LLMからの回答の音声データ
        audio_output_file_path: 出力先のファイルパス
    """

    temp_audio_output_filename = f"{ct.AUDIO_OUTPUT_DIR}/temp_audio_output_{int(time.time())}.mp3"
    with open(temp_audio_output_filename, "wb") as temp_audio_output_file:
        temp_audio_output_file.write(llm_response_audio)
    
    audio_mp3 = AudioSegment.from_file(temp_audio_output_filename, format="mp3")
    audio_mp3.export(audio_output_file_path, format="wav")

    # 音声出力用に一時的に作ったmp3ファイルを削除
    os.remove(temp_audio_output_filename)

def play_wav(audio_output_file_path, speed=1.0):
    """
    音声ファイルの読み上げ
    Args:
        audio_output_file_path: 音声ファイルのパス
        speed: 再生速度（1.0が通常速度、0.5で半分の速さ、2.0で倍速など）
    """
    # 音声ファイルの読み込み
    audio = AudioSegment.from_wav(audio_output_file_path)
    
    # 速度を変更
    if speed != 1.0:
        # frame_rateを変更することで速度を調整
        modified_audio = audio._spawn(
            audio.raw_data, 
            overrides={"frame_rate": int(audio.frame_rate * speed)}
        )
        # 速度変更された音声を一時ファイルに保存
        temp_audio_path = audio_output_file_path.replace('.wav', '_temp.wav')
        modified_audio.export(temp_audio_path, format="wav")

        # 一時ファイルを元のファイルに置き換え
        import shutil
        shutil.move(temp_audio_path, audio_output_file_path)

    # PyAudioで再生
    with wave.open(audio_output_file_path, 'rb') as play_target_file:
        p = pyaudio.PyAudio()
        stream = p.open(
            format=p.get_format_from_width(play_target_file.getsampwidth()),
            channels=play_target_file.getnchannels(),
            rate=play_target_file.getframerate(),
            output=True
        )

        data = play_target_file.readframes(1024)
        while data:
            stream.write(data)
            data = play_target_file.readframes(1024)

        stream.stop_stream()
        stream.close()
        p.terminate()
    
    # 音声ファイルは比較用に保持（削除しない）
    # os.remove(audio_output_file_path)

def create_chain(system_template=None, english_level=None):
    """
    LLMによる回答生成用のChain作成
    """
    
    # 【課題】 回答精度を上げるために、英語レベルに応じたプロンプトを選択
    if english_level and english_level in ct.SYSTEM_TEMPLATE_BASIC_CONVERSATION:
        selected_template = ct.SYSTEM_TEMPLATE_BASIC_CONVERSATION[english_level]
    elif system_template:
        selected_template = system_template
    else:
        # デフォルトは初級者レベル
        selected_template = ct.SYSTEM_TEMPLATE_BASIC_CONVERSATION["初級者"]

    # 改善点アドバイス機能を追加したプロンプト
    improvement_context = ""
    if hasattr(st.session_state, 'last_improvement_analysis') and st.session_state.last_improvement_analysis:
        improvement_context = f"""

【前回の改善点分析結果】
{st.session_state.last_improvement_analysis}

上記の改善点を参考に、今回の会話で自然にアドバイスを織り込んでください。"""

    enhanced_template = f"""{selected_template}

【重要な追加機能】
- ユーザーの直前の入力に改善点があれば、自然に会話に織り込んでアドバイスしてください
- 改善点は会話の流れの中で自然に言及し、励ましの言葉と一緒に伝えてください
- ユーザーのレベルに応じた適切なアドバイスを心がけてください
- アドバイスは簡潔で実用的なものにしてください{improvement_context}"""

    prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content=enhanced_template),
        MessagesPlaceholder(variable_name="history"),
        HumanMessagePromptTemplate.from_template("{input}")
    ])
    chain = ConversationChain(
        llm=st.session_state.llm,
        memory=st.session_state.memory,
        prompt=prompt
    )

    return chain

def extract_vocabulary_from_sentence(sentence):
    """
    文からvocabularyを抽出する
    Args:
        sentence: 英文
    Returns:
        list: 抽出された単語のリスト
    """
    import re
    
    # 基本的な単語抽出（アルファベットのみ、2文字以上）
    words = re.findall(r'\b[a-zA-Z]{2,}\b', sentence.lower())
    
    # 一般的なストップワードを除外
    stop_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
        'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
        'will', 'would', 'could', 'should', 'may', 'might', 'can', 'this', 'that', 'these', 'those',
        'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them'
    }
    
    # ストップワードを除外
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
    
    # 新しいvocabularyを履歴に追加
    st.session_state[f'{mode}_vocabulary_history'].append(vocabulary_list)
    
    # 3世代以上前の履歴を削除（最新3世代のみ保持）
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

def get_vocabulary_history_status(mode):
    """
    vocabulary履歴の状態を取得（デバッグ用）
    Args:
        mode: "dictation" または "shadowing"
    Returns:
        dict: 履歴の状態情報
    """
    if f'{mode}_vocabulary_history' not in st.session_state:
        return {
            "total_generations": 0,
            "current_avoid_count": 0,
            "avoid_vocabulary": []
        }
    
    history = st.session_state[f'{mode}_vocabulary_history']
    avoid_vocab = get_avoid_vocabulary(mode)
    
    return {
        "total_generations": len(history),
        "current_avoid_count": len(avoid_vocab),
        "avoid_vocabulary": sorted(list(avoid_vocab)),
        "recent_vocabulary": [vocab for vocab_list in history[-1:] for vocab in vocab_list] if history else []
    }

def create_problem_and_play_audio(english_level="初級者", mode="shadowing"):
    """
    問題生成と音声ファイルの再生
    Args:
        english_level: 英語レベル（"キッズ", "初級者", "中級者", "上級者"）
        mode: "dictation" または "shadowing"
    """

    # ランダムな問題を生成するために、毎回異なるプロンプトを作成
    import random
    import time
    
    # より多様なランダム化のための複数の要素を組み合わせ
    random_seed = random.randint(1, 10000)
    timestamp = int(time.time())
    
    # 英語レベルに応じたプロンプトを選択
    if english_level in ct.SYSTEM_TEMPLATE_SHADOWING_PROBLEM_BY_LEVEL:
        base_prompt = ct.SYSTEM_TEMPLATE_SHADOWING_PROBLEM_BY_LEVEL[english_level]
    else:
        # デフォルトは初級者レベル
        base_prompt = ct.SYSTEM_TEMPLATE_SHADOWING_PROBLEM_BY_LEVEL["初級者"]
    
    # 避けるべきvocabularyを取得
    avoid_vocab = get_avoid_vocabulary(mode)
    avoid_vocab_str = ", ".join(sorted(avoid_vocab)) if avoid_vocab else "None"
    
    # ランダム化パラメータを追加
    random_prompt = f"""{base_prompt}

RANDOMIZATION PARAMETERS:
- Random seed: {random_seed}
- Timestamp: {timestamp}
- English Level: {english_level}

VOCABULARY AVOIDANCE:
- Avoid using these words from recent sessions: {avoid_vocab_str}
- Use completely different vocabulary to ensure variety

Generate a completely unique sentence appropriate for {english_level} level learners."""
    
    # 問題文生成用のプロンプトを直接LLMに送信（会話履歴を使わない）
    response = st.session_state.llm.invoke([
        SystemMessage(content=random_prompt)
    ])
    problem = response.content

    # 生成された問題文からvocabularyを抽出して履歴に追加
    problem_vocabulary = extract_vocabulary_from_sentence(problem)
    update_vocabulary_history(mode, problem_vocabulary)

    # LLMからの回答を音声データに変換
    llm_response_audio = st.session_state.openai_obj.audio.speech.create(
        model="tts-1",
        voice=st.session_state.voice,
        input=problem
    )

    # 音声ファイルの作成（比較用に保存）
    audio_output_file_path = f"{ct.AUDIO_OUTPUT_DIR}/audio_output_{int(time.time())}.wav"
    save_to_wav(llm_response_audio.content, audio_output_file_path)

    # 音声ファイルの読み上げ
    play_wav(audio_output_file_path, st.session_state.speed)

    return problem, audio_output_file_path

def create_evaluation(english_level="初級者"):
    """
    ユーザー入力値の評価生成
    Args:
        english_level: 英語レベル（"キッズ", "初級者", "中級者", "上級者"）
    """
    # 評価用のプロンプトを明示的に渡す
    evaluation_prompt = "上記の情報を基に、詳細な評価を提供してください。"
    llm_response_evaluation = st.session_state.chain_evaluation.predict(input=evaluation_prompt)
    return llm_response_evaluation

def create_audio_based_evaluation(problem_text, reference_audio_path, user_audio_path, english_level="初級者"):
    """
    音声比較を基にした評価生成（文字起こし不要）
    Args:
        problem_text: 問題文
        reference_audio_path: 参考音声（LLM生成）のパス
        user_audio_path: ユーザー音声のパス
        english_level: 英語レベル（"キッズ", "初級者", "中級者", "上級者"）
    Returns:
        str: 評価結果
    """
    
    # 音声比較を実行
    audio_comparison_result = compare_audio_files(reference_audio_path, user_audio_path)
    
    # 音声比較結果を基に評価プロンプトを作成
    if audio_comparison_result:
        audio_analysis = ct.AUDIO_ANALYSIS_TEMPLATE.format(
            mfcc_similarity_percent=100*audio_comparison_result['mfcc_similarity'],
            spectral_similarity_percent=100*audio_comparison_result['spectral_similarity'],
            zcr_similarity_percent=100*audio_comparison_result['zcr_similarity'],
            energy_similarity_percent=100*audio_comparison_result['energy_similarity'],
            overall_score=audio_comparison_result['overall_score'],
            reference_duration=audio_comparison_result['reference_duration'],
            user_duration=audio_comparison_result['user_duration']
        )
    else:
        audio_analysis = ct.AUDIO_ANALYSIS_ERROR_MESSAGE
    
    # 英語レベルに応じた評価プロンプトを選択
    if english_level in ct.SYSTEM_TEMPLATE_SHADOWING_EVALUATION_BY_LEVEL:
        system_template = ct.SYSTEM_TEMPLATE_SHADOWING_EVALUATION_BY_LEVEL[english_level].format(
            problem_text=problem_text,
            audio_analysis=audio_analysis
        )
    else:
        # デフォルトは初級者レベル
        system_template = ct.SYSTEM_TEMPLATE_SHADOWING_EVALUATION_BY_LEVEL["初級者"].format(
            problem_text=problem_text,
            audio_analysis=audio_analysis
        )

    st.session_state.chain_evaluation = create_chain(system_template)
    
    # 評価結果を生成
    llm_response_evaluation = create_evaluation(english_level)

    return llm_response_evaluation

def compare_audio_files(reference_audio_path, user_audio_path):
    """
    音声ファイル同士を比較して発音の類似度を分析
    Args:
        reference_audio_path: 参考音声（LLM生成）のパス
        user_audio_path: ユーザー音声のパス
    Returns:
        dict: 音声比較結果
    """
    try:
        import librosa
        import numpy as np
        from scipy.spatial.distance import cosine
        
        # 音声ファイルの読み込み
        ref_audio, ref_sr = librosa.load(reference_audio_path, sr=16000)
        user_audio, user_sr = librosa.load(user_audio_path, sr=16000)
        
        # 1. 音声の長さを正規化（短い方に合わせる）
        min_length = min(len(ref_audio), len(user_audio))
        ref_audio = ref_audio[:min_length]
        user_audio = user_audio[:min_length]
        
        # 2. MFCC特徴量の抽出
        ref_mfcc = librosa.feature.mfcc(y=ref_audio, sr=ref_sr, n_mfcc=13)
        user_mfcc = librosa.feature.mfcc(y=user_audio, sr=user_sr, n_mfcc=13)
        
        # 3. 特徴量の平均を計算
        ref_mfcc_mean = np.mean(ref_mfcc, axis=1)
        user_mfcc_mean = np.mean(user_mfcc, axis=1)
        
        # 4. コサイン類似度を計算
        similarity = 1 - cosine(ref_mfcc_mean, user_mfcc_mean)
        
        # 5. スペクトラル重心の比較
        ref_spectral_centroid = np.mean(librosa.feature.spectral_centroid(y=ref_audio, sr=ref_sr))
        user_spectral_centroid = np.mean(librosa.feature.spectral_centroid(y=user_audio, sr=user_sr))
        
        # 6. ゼロクロッシングレートの比較
        ref_zcr = np.mean(librosa.feature.zero_crossing_rate(ref_audio))
        user_zcr = np.mean(librosa.feature.zero_crossing_rate(user_audio))
        
        # 7. 結果の計算
        spectral_similarity = 1 - abs(ref_spectral_centroid - user_spectral_centroid) / max(ref_spectral_centroid, user_spectral_centroid)
        zcr_similarity = 1 - abs(ref_zcr - user_zcr) / max(ref_zcr, user_zcr)
        
        # 8. 単語レベルの分析（音声の区切りを検出）
        # 音声のエネルギー変化を分析して単語の境界を推定
        ref_energy = librosa.feature.rms(y=ref_audio)[0]
        user_energy = librosa.feature.rms(y=user_audio)[0]
        
        # エネルギー変化の類似度を計算
        energy_similarity = 1 - cosine(ref_energy, user_energy)
        
        # 9. 総合スコアの計算（単語レベル分析も含める）
        overall_score = (similarity * 0.5 + spectral_similarity * 0.2 + zcr_similarity * 0.2 + energy_similarity * 0.1) * 100
        
        result = {
            "similarity": similarity,  # 問題文との一致度として使用
            "mfcc_similarity": similarity,
            "spectral_similarity": spectral_similarity,
            "zcr_similarity": zcr_similarity,
            "energy_similarity": energy_similarity,  # 単語レベル分析
            "overall_score": overall_score,
            "reference_duration": len(ref_audio) / ref_sr,
            "user_duration": len(user_audio) / user_sr
        }
        
        
        return result
        
    except ImportError as e:
        return None
    except Exception as e:
        return None

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
                pass
        except Exception as e:
            pass


# 【課題】 回答精度を上げるためのアイデア  ***使うかどうかは試してみてから決める***
#  音声前処理の改善
def enhance_audio_quality(audio_file_path):
    """音声品質を向上させる前処理"""
    try:
        import librosa
        import soundfile as sf
        import numpy as np
        
        # 設定を取得
        settings = ct.AUDIO_ENHANCEMENT_SETTINGS
        
        # 音声を読み込み（設定されたサンプルレートにリサンプリング）
        audio, sr = librosa.load(audio_file_path, sr=settings["target_sample_rate"])
        
        # 1. 前処理（高周波成分の強調）
        audio_preemphasized = librosa.effects.preemphasis(audio, coef=settings["preemphasis_coeff"])
        
        # 2. 音量正規化（設定されたレベルに調整）
        audio_normalized = librosa.util.normalize(audio_preemphasized, norm=np.inf)
        audio_normalized = audio_normalized * settings["normalization_level"]
        
        # 3. 無音部分の除去（設定された閾値で短縮）
        audio_trimmed, _ = librosa.effects.trim(audio_normalized, top_db=settings["trim_threshold"])
        
        # 4. 処理済み音声を保存
        sf.write(audio_file_path, audio_trimmed, sr)
        
        return audio_file_path
        
    except ImportError as e:
        return audio_file_path
    except Exception as e:
        return audio_file_path

# 【課題】 回答精度を上げるためのアイデア  ***使うかどうかは試してみてから決める***
#  複数の音声認識エンジンの使用
def transcribe_audio_with_fallback(audio_file_path):
    """複数の音声認識エンジンでフォールバック"""
    try:
        # メインの音声認識
        transcript = st.session_state.openai_obj.audio.transcriptions.create(
            model="whisper-1",
            file=open(audio_file_path, 'rb'),
            language="en",
            response_format="verbose_json"
        )
        return transcript.text
    except Exception as e:
        # フォールバック処理
        st.warning("音声認識でエラーが発生しました。再試行します。")
        # 別の音声認識サービスや再試行ロジック
        return retry_transcription(audio_file_path)

def retry_transcription(audio_file_path):
    """音声認識の再試行"""
    # 実装例
    return "音声認識に失敗しました"

# 【課題】 回答精度を上げるためのアイデア  ***使うかどうかは試してみてから決める***
#  ユーザーレベルと過去のパフォーマンスに基づく段階的評価
def create_progressive_evaluation(user_level, performance_history):
    """ユーザーレベルと過去のパフォーマンスに基づく段階的評価"""
    
    if user_level == "キッズ":
        focus_areas = ["やさしい単語", "簡単なフレーズ", "発音の基礎", "リスニング力"]
    elif user_level == "初級者":
        focus_areas = ["基本的な文法", "基本的な語彙", "発音の基礎"]
    elif user_level == "中級者":
        focus_areas = ["複雑な文法構造", "語彙の豊富さ", "自然な表現"]
    else:  # 上級者
        focus_areas = ["微妙なニュアンス", "文化的適切性", "高度な表現"]
    
    return focus_areas

# 【課題】 回答精度を上げるためのアイデア  ユーザーの直前の回答に対して、改善点を分析する
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
    
    # 英語レベルに応じた改善点分析プロンプトを定数から取得
    prompt = ct.SYSTEM_TEMPLATE_USER_INPUT_IMPROVEMENT_ANALYSIS.get(english_level, ct.SYSTEM_TEMPLATE_USER_INPUT_IMPROVEMENT_ANALYSIS["初級者"])
    analysis_prompt = prompt.format(user_input=user_input)
    
    try:
        response = st.session_state.llm.invoke([
            SystemMessage(content=analysis_prompt)
        ])
        return response.content.strip()
    except Exception as e:
        print(f"改善点分析エラー: {e}")
        return ""

# 【課題】 回答精度を上げるためのアイデア  ***使うかどうかは試してみてから決める***
#  会話履歴を考慮したチェーン作成
def create_context_aware_chain(conversation_history, user_level):
    """会話履歴を考慮したチェーン作成"""
    
    context_summary = summarize_conversation_history(conversation_history)
    #     # 簡単な会話履歴の要約（実装例）
    # context_summary = "Previous conversation context"
    
    # enhanced_prompt = f"""
    # {SYSTEM_TEMPLATE_BASIC_CONVERSATION_IMPROVED}
    enhanced_prompt = f"""
    You are a helpful English conversation partner.
    
    【会話コンテキスト】
    これまでの会話の要約: {context_summary}
    ユーザーレベル: {user_level}
    
    【指示】
    上記のコンテキストを考慮して、自然で一貫性のある会話を続けてください。
    """
    
    return create_chain(enhanced_prompt)

# 【課題】 回答精度を上げるためのアイデア  ***使うかどうかは試してみてから決める***
#  リアルタイムフィードバック提供
def provide_immediate_feedback(user_input, corrected_input):
    """即座のフィードバック提供"""
    
    if user_input != corrected_input:
        st.info(f"💡 より自然な表現: {corrected_input}")
        
        # 音声で訂正を読み上げ
        play_correction_audio(corrected_input)

# 【課題】 回答精度を上げるためのアイデア  ***使うかどうかは試してみてから決める***
#  学習進捗の追跡と可視化
def track_learning_progress():
    """学習進捗の追跡と可視化"""
    
    # 実装例（実際の計算関数は別途実装が必要）
    progress_data = {
        "grammar_accuracy": calculate_grammar_accuracy(),
        "vocabulary_richness": calculate_vocabulary_score(),
        "fluency_score": calculate_fluency_score(),
        "improvement_trend": calculate_improvement_trend()
    }
    
    # 進捗チャートの表示（実装例）
    # display_progress_chart(progress_data)
    return progress_data