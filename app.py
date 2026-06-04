import streamlit as st
import google.generativeai as genai
import time
import pandas as pd
from datetime import datetime

# --- 設定 ---
st.set_page_config(page_title="馬鈴薯収穫支援システム", layout="wide")
st.title("🥔 馬鈴薯収穫支援システム")

# サイドバーでAPIキーと設定
with st.sidebar:
    api_key = st.secrets["GEMINI_API_KEY"]
    st.info("フィードバック履歴はセッション内で保持されます。")
    if st.button("履歴をクリア"):
        st.session_state.chat_history = []
        st.rerun()

# セッション状態の初期化（フィードバックループ用）
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# --- システムプロンプトの定義 ---
SYSTEM_PROMPT = """
あなたは「馬鈴薯収穫支援スマートグラス」のバックエンドエンジンです。
動画を解析し、以下の【作業モデル】に従って現在の工程を推定してください。

### 【作業モデル】
工程①：準備
- 注意点：トラクタ，作業機の後ろに立たない
- 視界情報：トラクタ，ポテトハーベスタ全体が映っている，動いていない

工程②：掘り取り，選別
- 注意点：作業機のうね逸脱注意，小いも及び250g以上は規格外，コンベアの速度調整注意，いもの容量注意
- 視界情報：選別コンベアが映っている，いもや土塊が流れている

工程③：いも放出
- 注意点：いもかごの結合確認
- 視界情報：いもかご（タンク）が大きく映っている
※注意：作業機と一体化した「貯留タンク」へ流れている間は「工程②」です。外部の「いもかご」へ移し替える際が「工程③」です。

### 【出力ルール】
1. スマートグラス表示の遷移（デモ）: [タイムスタンプ] 工程名、およびHUD風の注意点。
2. 実際のcsvファイル: ヘッダー(timestamp, event, estimated_step, visual_evidence)を持つCSVコードブロック。
"""

# --- メイン機能 ---
if api_key:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name="gemini-1.5-flash", system_instruction=SYSTEM_PROMPT)

    uploaded_file = st.file_uploader("収穫作業の動画をアップロードしてください", type=["mp4", "mov", "avi"])

    if uploaded_file:
        st.video(uploaded_file)
        
        if st.button("動画を解析する"):
            with st.spinner("AIが映像を解析中..."):
                # 動画のアップロードと解析
                tfile = st.empty()
                with open("temp_video.mp4", "wb") as f:
                    f.write(uploaded_file.read())
                
                video_file = genai.upload_file(path="temp_video.mp4")
                while video_file.state.name == "PROCESSING":
                    time.sleep(2)
                    video_file = genai.get_file(video_file.name)

                # 解析リクエスト（過去のフィードバック履歴をコンテキストに含める）
                prompt_parts = [video_file, "この動画を解析してください。"]
                if st.session_state.chat_history:
                    prompt_parts.append("過去の修正指示を考慮してください：")
                    for history in st.session_state.chat_history:
                        prompt_parts.append(history)

                response = model.generate_content(prompt_parts)
                st.session_state.last_response = response.text

        # 結果表示
        if "last_response" in st.session_state:
            st.markdown("### 📋 解析結果")
            st.write(st.session_state.last_response)

            # フィードバック入力（ループの核）
            st.divider()
            st.markdown("### 🔄 フィードバックループ")
            feedback = st.text_input("AIの判定に誤りがあれば指示を入力してください（例：9秒以降はタンクなので工程2です）")
            
            if st.button("修正して再学習させる"):
                if feedback:
                    st.session_state.chat_history.append(f"ユーザーの修正指示: {feedback}")
                    st.success("指示を記憶しました。もう一度「動画を解析する」を押すと、この指示を反映して再解析します。")
                else:
                    st.warning("指示内容を入力してください。")

else:
    st.warning("サイドバーにGemini API Keyを入力してください。")