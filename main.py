import streamlit as st
import os
import time
import warnings
from time import sleep
from pathlib import Path
from streamlit.components.v1 import html
from langchain.memory import ConversationSummaryBufferMemory
from langchain.chains import ConversationChain

# LangChainの非推奨警告を抑制
warnings.filterwarnings("ignore", category=DeprecationWarning, module="langchain")
from langchain.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    MessagesPlaceholder,
)
from langchain.schema import SystemMessage
from openai import OpenAI
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import functions as ft
import constants as ct


# 各種設定
load_dotenv()
st.set_page_config(
    page_title=ct.APP_NAME,
    layout="wide",
    initial_sidebar_state="expanded"
)

# サイドバーのスタイルを適用
st.markdown(ct.SIDEBAR_CSS, unsafe_allow_html=True)


# タイトル表示
st.markdown(f"## {ct.APP_NAME}")

# 初期処理
if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.start_flg = False
    st.session_state.pre_mode = ""
    st.session_state.shadowing_flg = False
    st.session_state.shadowing_button_flg = False
    st.session_state.shadowing_count = 0
    st.session_state.shadowing_first_flg = True
    st.session_state.shadowing_audio_input_flg = False
    st.session_state.shadowing_evaluation_first_flg = True
    st.session_state.dictation_flg = False
    st.session_state.dictation_button_flg = False
    st.session_state.dictation_count = 0
    st.session_state.dictation_first_flg = True
    st.session_state.dictation_chat_message = ""
    st.session_state.dictation_evaluation_first_flg = True
    st.session_state.chat_open_flg = False
    st.session_state.problem = ""
    
    # 初期音声設定（デフォルトは初級者レベル）
    initial_voice_settings = ct.VOICE_SETTINGS["初級者"]
    st.session_state.voice = initial_voice_settings["voice"]
    st.session_state.speed = initial_voice_settings["speed"]
    
    try:
        st.session_state.openai_obj = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        st.session_state.llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0.5)
    except Exception as e:
        st.error(f"OpenAI初期化エラー: {str(e)}")
        st.stop()
    
    # モード毎のメモリとメッセージ履歴を初期化
    st.session_state.mode_memories = {}
    st.session_state.mode_messages = {}
    
    # デフォルトモード（日常英会話）用のメモリとメッセージ履歴を設定
    st.session_state.mode_memories[ct.MODE_1] = ConversationSummaryBufferMemory(
        llm=st.session_state.llm,
        max_token_limit=1000,
        return_messages=True
    )
    st.session_state.mode_messages[ct.MODE_1] = []
    
    # 現在のメモリとメッセージ履歴をセッション状態に設定
    st.session_state.memory = st.session_state.mode_memories[ct.MODE_1]
    st.session_state.messages = st.session_state.mode_messages[ct.MODE_1]

    # モード「日常英会話」用のChain作成（デフォルトは初級者レベル）
    st.session_state.chain_basic_conversation = ft.create_chain(english_level="初級者")

# 左サイドバーにコントロールエリアを配置
with st.sidebar:
    st.markdown("### 🎛️ コントロールパネル")
        
    # 再生速度設定（現在の設定を反映）
    current_speed_index = ct.PLAY_SPEED_OPTION.index(st.session_state.speed) if st.session_state.speed in ct.PLAY_SPEED_OPTION else 3
    st.session_state.speed = st.selectbox(
        label="再生速度", 
        options=ct.PLAY_SPEED_OPTION, 
        index=current_speed_index
    )
    
    # モード設定
    st.session_state.mode = st.selectbox(
        label="モード", 
        options=[ct.MODE_1, ct.MODE_2, ct.MODE_3]
    )
    
    # モードを変更した際の処理
    if st.session_state.mode != st.session_state.pre_mode:
        # 自動でそのモードの処理が実行されないようにする
        st.session_state.start_flg = False
        # 「日常英会話」選択時の初期化処理
        if st.session_state.mode == ct.MODE_1:
            st.session_state.dictation_flg = False
            st.session_state.shadowing_flg = False
        # 「シャドーイング」選択時の初期化処理
        st.session_state.shadowing_count = 0
        if st.session_state.mode == ct.MODE_2:
            st.session_state.dictation_flg = False
        # 「ディクテーション」選択時の初期化処理
        st.session_state.dictation_count = 0
        if st.session_state.mode == ct.MODE_3:
            st.session_state.shadowing_flg = False
        # チャット入力欄を非表示にする
        st.session_state.chat_open_flg = False
    st.session_state.pre_mode = st.session_state.mode
    
    # 英語レベル設定
    st.session_state.englv = st.selectbox(
        label="英語レベル", 
        options=ct.ENGLISH_LEVEL_OPTION,
        index=1  # デフォルト値を「初級者」（インデックス1）に設定
    )
    
    # 【課題】 回答精度を上げるために、英語レベルが変更されたときにチェーンを再作成
    if "prev_english_level" not in st.session_state:
        st.session_state.prev_english_level = st.session_state.englv
    
    if st.session_state.englv != st.session_state.prev_english_level:
        # 英語レベルに応じたチェーンを再作成
        st.session_state.chain_basic_conversation = ft.create_chain(english_level=st.session_state.englv)
        
        # 英語レベルに応じた音声設定を更新
        voice_settings = ct.VOICE_SETTINGS[st.session_state.englv]
        st.session_state.voice = voice_settings["voice"]
        st.session_state.speed = voice_settings["speed"]
        
        st.session_state.prev_english_level = st.session_state.englv
        
        # UIを強制的に更新
        st.rerun()
    
    # 開始ボタン
    st.markdown("<br>", unsafe_allow_html=True) # 余白を空ける
    if st.session_state.start_flg:
        st.button("開始", use_container_width=True, type="primary")
    else:
        st.session_state.start_flg = st.button("開始", use_container_width=True, type="primary")
    
    st.divider()
    
    # 現在の設定表示
    st.markdown("**現在の設定**")
    st.write(f"モード: {st.session_state.mode}")
    st.write(f"再生速度: {st.session_state.speed}")
    st.write(f"英語レベル: {st.session_state.englv}")
    
    # 操作説明
    st.markdown("**操作説明**")
    st.info("""
    - モードと再生速度を選択し、「開始」ボタンを押して英会話を始めましょう
    - モードは「日常英会話」「シャドーイング」「ディクテーション」から選べます
    - 発話後、5秒間沈黙することで音声入力が完了します
    - 「一時中断」ボタンを押すことで、英会話を一時中断できます
    """)

with st.chat_message("assistant", avatar="images/ai_icon.jpg"):
    st.markdown("こちらは生成AIによる音声英会話の練習アプリです。何度も繰り返し練習し、英語力をアップさせましょう。")
    st.markdown("**左サイドバーのコントロールパネルから設定を行い、「開始」ボタンを押して英会話を始めましょう。**")

st.divider()

# メッセージリストの一覧表示
for message in st.session_state.messages:
    if message["role"] == "assistant":
        with st.chat_message(message["role"], avatar="images/ai_icon.jpg"):
            st.markdown(message["content"])
    elif message["role"] == "user":
        with st.chat_message(message["role"], avatar="images/user_icon.jpg"):
            st.markdown(message["content"])
    else:
        st.divider()

# LLMレスポンスの下部にモード実行のボタン表示
if st.session_state.shadowing_flg:
    st.session_state.shadowing_button_flg = st.button("シャドーイング開始")
if st.session_state.dictation_flg:
    st.session_state.dictation_button_flg = st.button("ディクテーション開始")

# 「ディクテーション」モードのチャット入力受付時に実行
if st.session_state.chat_open_flg:
    st.info("AIが読み上げた音声を、画面下部のチャット欄からそのまま入力・送信してください。")

st.session_state.dictation_chat_message = st.chat_input("※「ディクテーション」選択時以外は送信不可")

if st.session_state.dictation_chat_message and not st.session_state.chat_open_flg:
    st.stop()

# 「開始」ボタンが押された場合の処理
if st.session_state.start_flg:

    # モード：「ディクテーション」
    # 「ディクテーション」ボタン押下時か、「英会話開始」ボタン押下時か、チャット送信時
    if st.session_state.mode == ct.MODE_3 and (st.session_state.dictation_button_flg or st.session_state.dictation_count == 0 or st.session_state.dictation_chat_message):
        # ディクテーションモードでは会話履歴を使わずに問題文を生成
        # if st.session_state.dictation_first_flg:
        #     st.session_state.chain_create_problem = ft.create_chain(ct.SYSTEM_TEMPLATE_CREATE_PROBLEM)
        #     st.session_state.dictation_first_flg = False
        # チャット入力以外
        if not st.session_state.chat_open_flg:
            with st.spinner('問題文生成中...'):
                st.session_state.problem, llm_response_audio = ft.create_problem_and_play_audio(st.session_state.englv, "dictation")

            st.session_state.chat_open_flg = True
            st.session_state.dictation_flg = False
            st.rerun()
        # チャット入力時の処理
        else:
            # チャット欄から入力された場合にのみ評価処理が実行されるようにする
            if not st.session_state.dictation_chat_message:
                st.stop()
            
            # AIメッセージとユーザーメッセージの画面表示
            with st.chat_message("assistant", avatar=ct.AI_ICON_PATH):
                st.markdown(f"**問題文:** {st.session_state.problem}")
            with st.chat_message("user", avatar=ct.USER_ICON_PATH):
                st.markdown(f"**あなたの回答:** {st.session_state.dictation_chat_message}")

            # LLMが生成した問題文とチャット入力値をメッセージリストに追加
            st.session_state.messages.append({"role": "assistant", "content": st.session_state.problem})
            st.session_state.messages.append({"role": "user", "content": st.session_state.dictation_chat_message})
            
            with st.spinner('評価結果の生成中...'):
                
                # 英語レベルに応じた評価プロンプトを選択
                if st.session_state.englv in ct.SYSTEM_TEMPLATE_DICTATION_EVALUATION_BY_LEVEL:
                    system_template = ct.SYSTEM_TEMPLATE_DICTATION_EVALUATION_BY_LEVEL[st.session_state.englv].format(
                        llm_text=st.session_state.problem,
                        user_text=st.session_state.dictation_chat_message
                    )
                else:
                    # デフォルトは初級者レベル
                    system_template = ct.SYSTEM_TEMPLATE_DICTATION_EVALUATION_BY_LEVEL["初級者"].format(
                        llm_text=st.session_state.problem,
                        user_text=st.session_state.dictation_chat_message
                    )
                st.session_state.chain_evaluation = ft.create_chain(system_template)
                # 問題文と回答を比較し、評価結果の生成を指示するプロンプトを作成
                llm_response_evaluation = ft.create_evaluation(st.session_state.englv)
            
            # 評価結果のメッセージリストへの追加と表示
            with st.chat_message("assistant", avatar=ct.AI_ICON_PATH):
                st.markdown(llm_response_evaluation)
            st.session_state.messages.append({"role": "assistant", "content": llm_response_evaluation})
            st.session_state.messages.append({"role": "other"})
            
            # 各種フラグの更新
            st.session_state.dictation_flg = True
            st.session_state.dictation_chat_message = ""
            st.session_state.dictation_count += 1
            st.session_state.chat_open_flg = False

            st.rerun()

    
    # モード：「日常英会話」
    if st.session_state.mode == ct.MODE_1:
        # 音声入力を受け取って音声ファイルを作成
        audio_input_file_path = f"{ct.AUDIO_INPUT_DIR}/audio_input_{int(time.time())}.wav"
        ft.record_audio(audio_input_file_path)

        # 音声入力ファイルから文字起こしテキストを取得
        with st.spinner('音声入力をテキストに変換中...'):
            transcript = ft.transcribe_audio(audio_input_file_path)
            audio_input_text = transcript.text

        # 音声入力テキストの画面表示
        with st.chat_message("user", avatar=ct.USER_ICON_PATH):
            st.markdown(audio_input_text)

        with st.spinner("回答の音声読み上げ準備中..."):
            # ユーザー入力のテキスト改善点を分析（バックグラウンドで実行）
            improvement_analysis = ft.analyze_user_input_improvements(audio_input_text, st.session_state.englv)
            
            # ユーザー音声の改善点を分析（バックグラウンドで実行）
            audio_improvement_analysis = ft.analyze_user_audio_improvements(audio_input_file_path, audio_input_text, st.session_state.englv)
            
            # ユーザー入力値をLLMに渡して回答取得
            llm_response = st.session_state.chain_basic_conversation.predict(input=audio_input_text)
            
            # LLMからの回答を音声データに変換
            llm_response_audio = st.session_state.openai_obj.audio.speech.create(
                model="tts-1",
                voice=st.session_state.voice,
                input=llm_response
            )

            # 一旦mp3形式で音声ファイル作成後、wav形式に変換
            audio_output_file_path = f"{ct.AUDIO_OUTPUT_DIR}/audio_output_{int(time.time())}.wav"
            ft.save_to_wav(llm_response_audio.content, audio_output_file_path)

        # 音声ファイルの読み上げ
        ft.play_wav(audio_output_file_path, speed=st.session_state.speed)

        # AIメッセージの画面表示とリストへの追加
        with st.chat_message("assistant", avatar=ct.AI_ICON_PATH):
            st.markdown(llm_response)

        # 改善点分析結果をセッション状態に保存（次の会話で活用）
        if improvement_analysis:
            st.session_state.last_improvement_analysis = improvement_analysis
        
        if audio_improvement_analysis:
            st.session_state.last_audio_improvement_analysis = audio_improvement_analysis
        
        # ユーザー入力値とLLMからの回答をメッセージ一覧に追加
        st.session_state.messages.append({"role": "user", "content": audio_input_text})
        st.session_state.messages.append({"role": "assistant", "content": llm_response})


    # モード：「シャドーイング」
    # 「シャドーイング」ボタン押下時か、「英会話開始」ボタン押下時
    if st.session_state.mode == ct.MODE_2 and (st.session_state.shadowing_button_flg or st.session_state.shadowing_count == 0 or st.session_state.shadowing_audio_input_flg):
        # シャドーイングモードでは会話履歴を使わずに問題文を生成
        # if st.session_state.shadowing_first_flg:
        #     st.session_state.chain_create_problem = ft.create_chain(ct.SYSTEM_TEMPLATE_CREATE_PROBLEM)
        #     st.session_state.shadowing_first_flg = False
        
        if not st.session_state.shadowing_audio_input_flg:
            with st.spinner('問題文生成中...'):
                st.session_state.problem, st.session_state.reference_audio_path = ft.create_problem_and_play_audio(st.session_state.englv, "shadowing")

        # 音声入力を受け取って音声ファイルを作成
        st.session_state.shadowing_audio_input_flg = True
        audio_input_file_path = f"{ct.AUDIO_INPUT_DIR}/audio_input_{int(time.time())}.wav"
        ft.record_audio(audio_input_file_path)
        st.session_state.shadowing_audio_input_flg = False

        with st.spinner('音声品質向上処理中...'):
            # 音声品質向上処理のみ実行（文字起こしは不要）
            ft.enhance_audio_quality(audio_input_file_path)

        # AIメッセージの画面表示
        with st.chat_message("assistant", avatar=ct.AI_ICON_PATH):
            st.markdown(f"**問題文:** {st.session_state.problem}")
        with st.chat_message("user", avatar=ct.USER_ICON_PATH):
            st.markdown("**あなたの音声:** 録音完了")
        
        # LLMが生成した問題文をメッセージリストに追加
        st.session_state.messages.append({"role": "assistant", "content": st.session_state.problem})
        st.session_state.messages.append({"role": "user", "content": "音声録音完了"})

        with st.spinner('音声比較と評価結果の生成中...'):
            # 音声比較を基にした評価を生成（文字起こし不要）
            llm_response_evaluation = ft.create_audio_based_evaluation(
                st.session_state.problem,
                st.session_state.reference_audio_path,
                audio_input_file_path,
                st.session_state.englv
            )
            st.session_state.shadowing_evaluation_first_flg = False

        # 評価結果のメッセージリストへの追加と表示
        with st.chat_message("assistant", avatar=ct.AI_ICON_PATH):
            st.markdown(llm_response_evaluation)
        st.session_state.messages.append({"role": "assistant", "content": llm_response_evaluation})
        st.session_state.messages.append({"role": "other"})
        
        # 音声ファイルのクリーンアップ
        ft.cleanup_audio_files(
            audio_input_file_path,
            st.session_state.reference_audio_path if hasattr(st.session_state, 'reference_audio_path') else None
        )
        
        # 各種フラグの更新
        st.session_state.shadowing_flg = True
        st.session_state.shadowing_count += 1

        # 「シャドーイング」ボタンを表示するために再描画
        st.rerun()