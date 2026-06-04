import streamlit as st
import google.generativeai as genai
import time
import os
from datetime import datetime

# --- 基本設定 ---
st.set_page_config(page_title="馬鈴薯収穫支援システム", layout="wide", page_icon="🥔")
st.title("🥔 馬鈴薯収穫支援デモシステム")

# --- APIキーの取得 (Secrets優先、なければサイドバー) ---
api_key = st.secrets.get("GEMINI_API_KEY") or st.sidebar.text_input("Gemini API Keyを入力", type="password")

if not api_key:
    st.warning("⚠️ APIキーが設定されていません。サイドバーに入力するか、StreamlitのSecretsに設定してください。")
    st.stop()

# --- Geminiの初期化 ---
genai.configure(api_key=api_key)
#try:
#    available_models = [m.name for m in genai.list_models()]
#    st.write("利用可能なモデル一覧:", available_models)
#except Exception as e:
#    st.error(f"モデル一覧の取得に失敗しました: {e}")

# システムプロンプト（指示の核）
SYSTEM_PROMPT = """
あなたは「馬鈴薯収穫支援スマートグラス」のバックエンドエンジンです。
アップロードされた動画を解析し、以下の【作業モデル】に従って現在の工程を推定してください。

### 【作業モデル】
工程①：準備
- 注意点：トラクタ，作業機の後ろに立たない
- 視界情報：トラクタ，ポテトハーベスタ全体が映っている，動いていない

工程②：掘り取り，選別
- 注意点：作業機のうね逸脱注意，小いも及び250g以上は規格外，コンベアの速度調整注意，いもの容量注意
- 視界情報：選別コンベアが映っている，いもや土塊が流れている
※補足：作業機と一体化した「貯留タンク」へ流れている間は、選別作業の一部であり「工程②」です。

工程③：いも放出
- 注意点：いもかごの結合確認
- 視界情報：外部の「いもかご（コンテナ）」が大きく映っている、またはそこへ放出している
※重要：機体の「タンク」といもかごを混同しないでください。

### 【出力ルール】
1. スマートグラス表示の遷移（デモ）: [タイムスタンプ] 工程名、およびHUD風の注意点。
2. 実際のcsvファイル: ヘッダー(timestamp, event, estimated_step, visual_evidence)を持つCSVコードブロック。
"""

# セッション状態の初期化
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "last_response" not in st.session_state:
    st.session_state.last_response = ""

# --- サイドバー操作 ---
with st.sidebar:
    st.header("設定・履歴")
    if st.button("フィードバック履歴をクリア"):
        st.session_state.chat_history = []
        st.success("履歴をリセットしました")

# --- メインコンテンツ ---
uploaded_file = st.file_uploader("収穫作業の動画をアップロードしてください", type=["mp4", "mov", "avi"])

if uploaded_file:
    st.video(uploaded_file)
    
    if st.button("🚀 動画を解析する", use_container_width=True):
        try:
            with st.spinner("1. 動画ファイルを準備中..."):
                temp_file_name = "temp_video.mp4"
                with open(temp_file_name, "wb") as f:
                    f.write(uploaded_file.getbuffer())
            
            with st.spinner("2. Google AIサーバーへ送信中（これには数十秒かかる場合があります）..."):
                video_file = genai.upload_file(path=temp_file_name)
                
                # アップロード完了を待機
                while video_file.state.name == "PROCESSING":
                    time.sleep(3)
                    video_file = genai.get_file(video_file.name)
                
                if video_file.state.name == "FAILED":
                    st.error("動画のアップロードに失敗しました。")
                    st.stop()

            with st.spinner("3. AIが映像を解析してレポートを作成中..."):
                model = genai.GenerativeModel(model_name="gemini-3-flash-preview", system_instruction=SYSTEM_PROMPT)
                
                # プロンプトの組み立て（履歴がある場合は追加）
                prompt_content = ["この動画を作業モデルに基づいて解析してください。"]
                if st.session_state.chat_history:
                    prompt_content.append("以前の修正指示（これらを最優先してください）:")
                    prompt_content.extend(st.session_state.chat_history)
                
                prompt_content.append(video_file)
                
                response = model.generate_content(prompt_content)
                st.session_state.last_response = response.text
                
                # 完了後にファイルを削除してクリーンアップ
                genai.delete_file(video_file.name)

        except Exception as e:
            st.error(f"❌ 解析中にエラーが発生しました: {str(e)}")
            st.info("ヒント: APIキーが正しいか、動画サイズが大きすぎないか確認してください。")

# 結果の表示
if st.session_state.last_response:
    st.markdown("---")
    st.markdown("### 📋 AI解析結果")
    st.markdown(st.session_state.last_response)

    # フィードバックループ
    st.markdown("---")
    st.markdown("### 🔄 判定が違いますか？（フィードバック）")
    feedback = st.text_input("AIへの修正指示", placeholder="例：xx秒における工程推定が間違っています。正しくは，XXです")
    
    if st.button("指示を保存して再学習させる"):
        if feedback:
            st.session_state.chat_history.append(f"修正指示: {feedback}")
            st.toast("指示を記憶しました。もう一度上の「解析する」ボタンを押してください。")
        else:
            st.warning("指示内容を入力してください。")