import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from gspread_dataframe import get_as_dataframe, set_with_dataframe
import base64
import os
import pykakasi
import unicodedata
import json

# -------------------------------
# 🔐 Googleスプレッドシート認証
# -------------------------------
import os
import json
import gspread
import streamlit as st
from google.oauth2.service_account import Credentials

@st.cache_resource
def get_worksheet(sheet_name):
    # ① 認証情報の読み込み（Cloud or ローカル自動判定）
    creds_json = os.getenv('GOOGLE_CREDENTIALS')
    if creds_json:
        creds_info = json.loads(creds_json)
    else:
        # ローカル用ファイルパス（必要に応じて変更可）
        local_path = os.path.join("toumei", "credentials.json")
        if os.path.exists(local_path):
            with open(local_path, "r", encoding="utf-8") as f:
                creds_info = json.load(f)
        else:
            st.error("認証情報が見つかりません。環境変数 GOOGLE_CREDENTIALS または credentials.json を確認してください。")
            st.stop()

    # ② Google APIスコープ設定
    SCOPES = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]

    # ③ 認証＆ワークシート取得
    creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    gc = gspread.authorize(creds)

    # ④ スプレッドシートIDの取得（環境変数 or credentials.json）
    spreadsheet_id = os.getenv('SPREADSHEET_ID') or creds_info.get("spreadsheet_id", "")
    if not spreadsheet_id:
        st.error("スプレッドシートIDが見つかりません。credentials.json に 'spreadsheet_id' を追加してください。")
        st.stop()

    spreadsheet = gc.open_by_key(spreadsheet_id)
    return spreadsheet.worksheet(sheet_name)





# -------------------------------
# 🌤 ふりがな変換（漢字→ひらがな）
# -------------------------------
kakasi = pykakasi.kakasi()
kakasi.setMode("J", "H")  # 漢字→ひらがな
kakasi.setMode("K", "H")  # カタカナ→ひらがな
kakasi.setMode("H", "H")  # ひらがなはそのまま
converter = kakasi.getConverter()

# 激音・半激音を正規化（例: ば → は）
def normalize_seion(char):
    decomposed = unicodedata.normalize('NFD', char)
    filtered = ''.join(c for c in decomposed if c not in ['゙', '゚'])  # 激音・半激音を除去
    return unicodedata.normalize('NFC', filtered)

# -------------------------------
# 📅 スプレッドシートからFAQを読み込む
# -------------------------------
@st.cache_data
def load_faq_from_sheet(sheet_name):
    ws = get_worksheet(sheet_name)
    df = get_as_dataframe(ws, evaluate_formulas=True).fillna('').astype(str)
    faqs = []
    for _, row in df.iterrows():
        question = row.get('質問', '')
        reading_raw = converter.do(str(question))
        normalized_reading = ''.join(normalize_seion(c) for c in reading_raw)
        faqs.append({
            '質問': question,
            '回答': row.get('回答', ''),
            '関連ワード': row.get('関連ワード', ''),
            '添付ファイル': row.get('添付ファイル', ''),
            '読み': normalized_reading
        })
    return faqs

# -------------------------------
# ❌ 検索ヒットしなかったワードをログに記録
# -------------------------------
def log_no_hit(tag, query):
    try:
        ws = get_worksheet("log")
        df = get_as_dataframe(ws).fillna('')
        df.loc[len(df)] = [tag, query]  # 新しい行を追加
        ws.clear()
        set_with_dataframe(ws, df)
    except Exception as e:
        st.warning(f"ログ保存エラー: {e}")

# -------------------------------
# 🔑 パスワード認証処理
# -------------------------------
def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if not st.session_state.authenticated:
        pwd = st.text_input("パスワードを入力してください", type="password")
        if st.button("ログイン"):
            if "password" in st.secrets and pwd == st.secrets["password"]:
                st.session_state.authenticated = True
                st.session_state.page = "home"
                st.rerun()
            else:
                st.error("パスワードが違います。")


def gojuon_sort(faqs):
    groups = {}
    for faq in faqs:
        initial = faq['読み'][0] if faq['読み'] else ''
        if initial:
            groups.setdefault(initial, [])
            if faq not in groups[initial]:
                groups[initial].append(faq)
    return dict(sorted(groups.items()))

# -------------------------------
# 📌 添付ファイルの表示（Streamlit Cloud対応）
# -------------------------------
def display_attachment(file_name):
    if not file_name:
        return
    file_path = os.path.join("files", file_name)  # Cloud上でfilesフォルダに格納想定
    if not os.path.isfile(file_path):
        st.warning(f"添付ファイル「{file_name}」が見つかりません。")
        return
    ext = file_name.lower().split('.')[-1]
    if ext in ['jpg', 'jpeg', 'png', 'gif']:
        st.image(file_path, caption=file_name)
    elif ext == 'pdf':
        with open(file_path, "rb") as f:
            pdf_bytes = f.read()
            base64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
            pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="700" height="900" type="application/pdf"></iframe>'
            st.markdown(pdf_display, unsafe_allow_html=True)
    else:
        st.markdown(f"[添付ファイルを開く]({file_path})")

def search_faqs(keywords, faqs, search_mode='AND'):
    results = []
    for faq in faqs:
        content = f"{str(faq.get('質問', '')).lower()} {str(faq.get('関連ワード', '')).lower()}"
        if search_mode == 'AND':
            if all(keyword in content for keyword in keywords):
                results.append(faq)
        elif search_mode == 'OR':
            if any(keyword in content for keyword in keywords):
                results.append(faq)
    return results

def search_ui(faqs, clear_query=False):
    query_key = "temp_query" if clear_query else "query"
    search_mode_key = "temp_search_mode" if clear_query else "search_mode"

    query = st.text_input(
        "🔍 検索キーワードを空白で区切って入力してください",
        value="" if clear_query else st.session_state.get("query", ""),
        key=query_key
    )
    search_mode = st.radio(
        "検索モードを選択してください",
        ('AND', 'OR'),
        key=search_mode_key,
        index=0 if clear_query else ('AND', 'OR').index(st.session_state.get("search_mode", "AND"))
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("検索", key=f"search_button_{'detail' if clear_query else 'home'}"):
            keywords = query.lower().split()
            results = search_faqs(keywords, faqs, search_mode)
            st.session_state.search_results = results
            st.session_state.selected_faq_index = None
            st.session_state.show_all_questions = False
            st.session_state.query = query
            st.session_state.search_mode = search_mode

            if not keywords:
                st.warning("検索キーワードを入力してください。")
            elif not results:
                st.info("該当するFAQはありません。")
                if "selected_category" in st.session_state:
                    log_no_hit(st.session_state.selected_category, query)  # ✨ ログ保存機能を追加
            st.rerun()

    with col2:
        if st.button("📋 一覧", key=f"list_button_{'detail' if clear_query else 'home'}"):
            st.session_state.search_results = faqs
            st.session_state.selected_faq_index = None
            st.session_state.show_all_questions = True
            st.session_state.page = "list"
            st.rerun()


def render_home(faqs):
    search_ui(faqs)
    if st.session_state.search_results:
        title = "【FAQ一覧】" if st.session_state.show_all_questions else f"【FAQ検索結果 - {st.session_state.search_mode}検索】"
        st.write(f"### {title}")
        for idx, faq in enumerate(st.session_state.search_results):
            question = faq.get('質問', '').strip()
            if st.button(question, key=f"faq_button_{idx}"):
                st.session_state.selected_faq_index = idx
                st.session_state.page = "detail"
                st.rerun()

def render_list(faqs):
    if st.button("🔠 五十音表示"):
        st.session_state.page = "gojuon"
        st.session_state.selected_initial = None
        st.rerun()

    st.write("### FAQ一覧")

    faqs_to_show = st.session_state.search_results if st.session_state.search_results else faqs

    # 4列に分けてボタン表示
    cols = st.columns(4)
    for i, faq in enumerate(faqs_to_show):
        question = faq.get('質問', '').strip()
        col_idx = i % 4
        with cols[col_idx]:
            if st.button(question, key=f"list_faq_button_{i}"):
                st.session_state.selected_faq_index = i
                st.session_state.page = "detail"
                st.rerun()

    if st.button("🏠 ホームへ戻る"):
        st.session_state.page = "home"
        st.rerun()

def chunk_list(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def render_gojuon(faqs):
    groups = gojuon_sort(faqs)

    row_groups = {
        'あ行': ['あ', 'い', 'う', 'え', 'お'],
        'か行': ['か', 'き', 'く', 'け', 'こ'],
        'さ行': ['さ', 'し', 'す', 'せ', 'そ'],
        'た行': ['た', 'ち', 'つ', 'て', 'と'],
        'な行': ['な', 'に', 'ぬ', 'ね', 'の'],
        'は行': ['は', 'ひ', 'ふ', 'へ', 'ほ'],
        'ま行': ['ま', 'み', 'む', 'め', 'も'],
        'や行': ['や', 'ゆ', 'よ'],
        'ら行': ['ら', 'り', 'る', 'れ', 'ろ'],
        'わ行': ['わ', 'を', 'ん'],
    }

    ordered_row_names = [
        'あ行', 'か行', 'さ行', 'た行', 'な行', 'は行', 'ま行', 'や行', 'ら行', 'わ行'
    ]

    st.write("### 五十音グループ")

    for row_name in ordered_row_names:
        initials = row_groups[row_name]
        col_count = 3 if row_name in ['や行', 'わ行'] else 5
        row_initials = [i for i in initials if i in groups]
        if not row_initials:
            continue
        st.write(f"#### {row_name}")
        for chunk in chunk_list(row_initials, col_count):
            cols = st.columns(len(chunk), gap="small")
            for idx, initial in enumerate(chunk):
                with cols[idx]:
                    if st.button(initial, key=f"gojuon_{initial}"):
                        st.session_state.selected_initial = initial
                        st.session_state.page = "gojuon_list"
                        st.session_state.selected_faq_index = None
                        st.rerun()

    alphabet_initials = [k for k in groups.keys() if not any(k in v for v in row_groups.values())]
    if alphabet_initials:
        st.write("### アルファベット")
        for chunk in chunk_list(alphabet_initials, 10):
            cols = st.columns(len(chunk), gap="small")
            for idx, initial in enumerate(chunk):
                with cols[idx]:
                    if st.button(initial, key=f"gojuon_alpha_{initial}"):
                        st.session_state.selected_initial = initial
                        st.session_state.page = "gojuon_list"
                        st.session_state.selected_faq_index = None
                        st.rerun()

def render_gojuon_list(faqs):
    initial = st.session_state.selected_initial
    groups = gojuon_sort(faqs)
    faqs_to_show = groups.get(initial, [])
    st.write(f"### 「{initial}」のFAQ一覧")
    for idx, faq in enumerate(faqs_to_show):
        if st.button(faq['質問'], key=f"gojuon_list_faq_{idx}"):
            st.session_state.selected_faq_index = idx
            st.session_state.page = "detail_gojuon"
            st.rerun()
    if st.button("🔙 五十音グループへ戻る"):
        st.session_state.page = "gojuon"
        st.rerun()
    if st.button("🏠 ホームへ戻る"):
        st.session_state.page = "home"
        st.rerun()

def render_detail(faqs):
    if st.session_state.page == "detail":
        results = st.session_state.search_results if st.session_state.search_results else faqs
        idx = st.session_state.selected_faq_index
    elif st.session_state.page == "detail_gojuon":
        groups = gojuon_sort(faqs)
        initial = st.session_state.selected_initial
        faqs_to_show = groups.get(initial, [])
        idx = st.session_state.selected_faq_index
        results = faqs_to_show
    else:
        st.error("不正なページ状態です。")
        return

    if idx is not None and 0 <= idx < len(results):
        faq = results[idx]
        st.write(f"### 質問: {faq.get('質問', '')}")
        st.write(f"**回答:** {faq.get('回答', '')}")
        st.write(f"**関連ワード:** {faq.get('関連ワード', 'なし') or 'なし'}")
        attachment = faq.get('添付ファイル', '')
        if attachment:
            for file in map(str.strip, attachment.split(',')):
                if file:
                    display_attachment(file)
        else:
            st.write("**添付ファイル:** なし")

        if st.button("🔙 戻る"):
            if st.session_state.page == "detail":
                st.session_state.page = "list"
            else:
                st.session_state.page = "gojuon_list"
            st.rerun()
        if st.button("🏠 ホームへ戻る"):
            st.session_state.page = "home"
            st.rerun()
    else:
        st.error("FAQの詳細を表示できません。")
        if st.button("🏠 ホームへ戻る"):
            st.session_state.page = "home"
            st.rerun()

def main():
    st.title("📚 FAQ検索（スプレッドシート対応）")
    check_password()
    if not st.session_state.authenticated:
        return

    # 初期セッションステート
    if 'page' not in st.session_state:
        st.session_state.page = "home"
    if 'selected_faq_index' not in st.session_state:
        st.session_state.selected_faq_index = None
    if 'selected_initial' not in st.session_state:
        st.session_state.selected_initial = None
    if 'search_results' not in st.session_state:
        st.session_state.search_results = []
    if 'show_all_questions' not in st.session_state:
        st.session_state.show_all_questions = False
    if 'search_mode' not in st.session_state:
        st.session_state.search_mode = "AND"

    # カテゴリ選択（スプレッドシートのシート名と一致）
    categories = ["工事関係", "事務関係", "その他"]
    selected_category = st.selectbox("カテゴリを選択してください", categories)
    st.session_state.selected_category = selected_category  # ← ✅ セッションに保存（必要）

    try:
        faqs = load_faq_from_sheet(selected_category)
    except Exception as e:
        st.error(f"FAQの読み込みに失敗しました: {e}")
        return

    # 現在のページに応じた描画
    if st.session_state.page == "home":
        render_home(faqs)
    elif st.session_state.page == "list":
        render_list(faqs)
    elif st.session_state.page == "gojuon":
        render_gojuon(faqs)
    elif st.session_state.page == "gojuon_list":
        render_gojuon_list(faqs)
    elif st.session_state.page in ("detail", "detail_gojuon"):
        render_detail(faqs)
    else:
        st.session_state.page = "home"
        st.rerun()

if __name__ == "__main__":
    main()

