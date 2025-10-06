import streamlit as st
import os
import warnings
from dotenv import load_dotenv
import functions as func
import constants as const

# 警告を抑制
warnings.filterwarnings("ignore", category=DeprecationWarning, module="langchain")

# ================== 初期化 ==================

def initialize_app():
    """アプリケーションの初期設定"""
    load_dotenv()
    st.set_page_config(
        page_title=const.APP_NAME,
        layout="wide",
        initial_sidebar_state="expanded"
    )
    st.markdown(const.SIDEBAR_CSS, unsafe_allow_html=True)

# ================== サイドバーUI ==================

def render_sidebar():
    """サイドバーの描画"""
    with st.sidebar:
        st.markdown("### 🎛️ コントロールパネル")
        
        # 再生速度設定
        current_speed_index = const.PLAY_SPEED_OPTION.index(st.session_state.speed) if st.session_state.speed in const.PLAY_SPEED_OPTION else 3
        st.session_state.speed = st.selectbox(
            label="再生速度", 
            options=const.PLAY_SPEED_OPTION, 
            index=current_speed_index
        )
        
        # モード設定
        st.session_state.mode = st.selectbox(
            label="モード", 
            options=[const.MODE_1, const.MODE_2, const.MODE_3]
        )
        
        # モード変更時の処理
        func.handle_mode_change()
        
        # 英語レベル設定
        st.session_state.english_level = st.selectbox(
            label="英語レベル", 
            options=const.ENGLISH_LEVEL_OPTION,
            index=1
        )
        
        # 英語レベル変更時の処理
        if func.handle_english_level_change():
            st.rerun()
        
        # 開始ボタン
        st.markdown("<br>", unsafe_allow_html=True)
        if st.session_state.start_flag:
            st.button("開始", use_container_width=True, type="primary")
        else:
            st.session_state.start_flag = st.button("開始", use_container_width=True, type="primary")
        
        st.divider()
        
        # 現在の設定表示
        display_current_settings()
        
        # 操作説明
        display_instructions()

def display_current_settings():
    """現在の設定を表示"""
    st.markdown("**現在の設定**")
    st.write(f"モード: {st.session_state.mode}")
    st.write(f"再生速度: {st.session_state.speed}")
    st.write(f"英語レベル: {st.session_state.english_level}")

def display_instructions():
    """操作説明を表示"""
    st.markdown("**操作説明**")
    st.info("""
    - モードと再生速度を選択し、「開始」ボタンを押して英会話を始めましょう
    - モードは「日常英会話」、「シャドーイング」、「ディクテーション」から選べます
    - 発話後、5秒間沈黙することで音声入力が完了します
    - 「一時中断」ボタンを押すことで、英会話を一時中断できます
    """)

# ================== メインコンテンツUI ==================

def display_welcome_message():
    """ウェルカムメッセージの表示"""
    with st.chat_message("assistant", avatar="images/ai_icon.jpg"):
        st.markdown("こちらは生成AIによる音声英会話の練習アプリです。何度も繰り返し練習し、英語力をアップさせましょう。")
        st.markdown("**左サイドバーのコントロールパネルから設定を行い、「開始」ボタンを押して英会話を始めましょう。**")

def display_message_history():
    """メッセージ履歴の表示"""
    for message in st.session_state.messages:
        if message["role"] == "assistant":
            with st.chat_message(message["role"], avatar="images/ai_icon.jpg"):
                st.markdown(message["content"])
        elif message["role"] == "user":
            with st.chat_message(message["role"], avatar="images/user_icon.jpg"):
                st.markdown(message["content"])
        else:
            st.divider()

def display_mode_buttons():
    """モード実行ボタンの表示"""
    if st.session_state.shadowing_flag:
        st.session_state.shadowing_button_flag = st.button("シャドーイング開始")
    if st.session_state.dictation_flag:
        st.session_state.dictation_button_flag = st.button("ディクテーション開始")

def display_dictation_input_info():
    """ディクテーション用の入力案内表示"""
    if st.session_state.chat_open_flag:
        st.info("AIが読み上げた音声を、画面下部のチャット欄からそのまま入力・送信してください。")

# ================== メイン処理 ==================

def main():
    """メイン処理"""
    # 初期化
    initialize_app()
    func.initialize_session_state()
    
    # タイトル
    st.markdown(f"## {const.APP_NAME}")
    
    # サイドバー描画
    render_sidebar()
    
    # ウェルカムメッセージ
    display_welcome_message()
    st.divider()
    
    # メッセージ履歴表示
    display_message_history()
    
    # モードボタン表示
    display_mode_buttons()
    
    # ディクテーション用の入力案内
    display_dictation_input_info()
    
    # チャット入力欄
    st.session_state.dictation_user_input = st.chat_input("※「ディクテーション」選択時以外は送信不可")
    
    if st.session_state.dictation_user_input and not st.session_state.chat_open_flag:
        st.stop()
    
    # 開始ボタン押下時の処理
    if st.session_state.start_flag:
        should_rerun = False
        
        if st.session_state.mode == const.MODE_1:
            func.process_basic_conversation_mode()
        elif st.session_state.mode == const.MODE_2:
            should_rerun = func.process_shadowing_mode()
        elif st.session_state.mode == const.MODE_3:
            should_rerun = func.process_dictation_mode()
        
        if should_rerun:
            st.rerun()

if __name__ == "__main__":
    main()
