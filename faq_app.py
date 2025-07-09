import streamlit as st
import pandas as pd
import os
import base64
import pykakasi
import unicodedata

# ふりがな変換セットアップ
kakasi = pykakasi.kakasi()
kakasi.setMode("J", "H")  # 漢字→ひらがな
kakasi.setMode("K", "H")  # カタカナ→ひらがな
kakasi.setMode("H", "H")  # ひらがなはそのまま
converter = kakasi.getConverter()

# 🔤 濁音を清音に正規化する関数
def normalize_seion(char):
    decomposed = unicodedata.normalize('NFD', char)
    filtered = ''.join(c for c in decomposed if c not in ['\u3099', '\u309A'])
    return unicodedata.normalize('NFC', filtered)

# 🔐 パスワード認証
def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if not st.session_state.authenticated:
        pwd = st.text_input("パスワードを入力してください", type="password")
        if st.button("ログイン"):
            if pwd == "tp0000":
                st.session_state.authenticated = True
                st.session_state.page = "home"
                st.rerun()
            else:
                st.error("パスワードが違います。")

# 📥 データ読み込み（Excel -> FAQ辞書）
@st.cache_data
def load_faq_from_excel(file_path):
    df = pd.read_excel(file_path).fillna('')
    faqs = []
    for _, row in df.iterrows():
        reading_raw = converter.do(str(row['質問']))
        normalized_reading = ''.join(normalize_seion(c) for c in reading_raw)
        faqs.append({
            '質問': row['質問'],
            '回答': row['回答'],
            '関連ワード': row['関連ワード'],
            '添付ファイル': row['添付ファイル'],
            '読み': normalized_reading
        })
    return faqs

# 🔠 五十音ごとのFAQを分類
def gojuon_sort(faqs):
    groups = {}
    for faq in faqs:
        initial = faq['読み'][0] if faq['読み'] else ''
        if initial:
            groups.setdefault(initial, []).append(faq)
    return dict(sorted(groups.items()))

# 📎 添付ファイルの表示
def display_attachment(file_name):
    if not file_name:
        return
    file_path = os.path.join(os.getcwd(), file_name)
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
        st.markdown(f"[添付ファイルを開く]({file_name})")

# 🔍 FAQ検索ロジック（AND/OR モード対応）
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

# 🔍 検索UI（キーワード入力と検索/一覧ボタン）
def search_ui(faqs, clear_query=False):
    query = st.text_input("🔍 検索キーワードを空白で区切って入力してください", value=st.session_state.get("query", ""))
    search_mode = st.radio("検索モードを選択してください", ('AND', 'OR'), index=('AND', 'OR').index(st.session_state.get("search_mode", "AND")))
    col1, col2 = st.columns(2)
    with col1:
        if st.button("検索", key=f"search_button_{'detail' if clear_query else 'home'}"):
            keywords = query.lower().split()
            results = search_faqs(keywords, faqs, search_mode)
            st.session_state.search_results = results
            st.session_state.selected_faq_index = None
            st.session_state.show_all_questions = False
            if not keywords:
                st.warning("検索キーワードを入力してください。")
            elif not results:
                st.info("該当するFAQはありません。")
            st.rerun()
    with col2:
        if st.button("📋 一覧", key=f"list_button_{'detail' if clear_query else 'home'}"):
            st.session_state.search_results = faqs
            st.session_state.selected_faq_index = None
            st.session_state.show_all_questions = True
            st.session_state.page = "list"
            st.rerun()

def render_home(faqs):
    search_ui(faqs, clear_query=False)  # ← 修正点
    if st.session_state.search_results:
        title = "【FAQ一覧】" if st.session_state.show_all_questions else f"【FAQ検索結果 - {st.session_state.search_mode}検索】"
        st.write(f"### {title}")
        for idx, faq in enumerate(st.session_state.search_results):
            question = faq.get('質問', '').strip()
            if st.button(question, key=f"faq_button_{idx}") :
                st.session_state.selected_faq_index = idx
                st.session_state.page = "detail"
                st.rerun()

def render_gojuon(faqs):
    search_ui(faqs, clear_query=True)  # ← 修正点（ページ区別用）
    groups = gojuon_sort(faqs)
    # ... 以下略（この部分はあなたの元コードと同じ）


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
    search_ui(faqs)  # ホーム画面の検索機能を追加
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

    st.markdown("---")
    # 最下部に「ホームに戻る」ボタンを追加
    if st.button("🏠 ホームへ戻る"):
        st.session_state.page = "home"
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
    st.title("📚 FAQ検索")
    check_password()
    if not st.session_state.authenticated:
        return

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

    faq_files = [
        {"label": "工事関係", "path": "faq.xlsx"},
        {"label": "事務関係", "path": "faq2.xlsx"},
        {"label": "その他（作成中）", "path": "other_faq.xlsx"},
    ]

    options = [f["label"] for f in faq_files]
    selected_label = st.selectbox("知りたい内容を選択してください", options)
    selected_file = next((f["path"] for f in faq_files if f["label"] == selected_label), None)

    try:
        faqs = load_faq_from_excel(selected_file)
    except Exception as e:
        st.error(f"FAQの読み込みに失敗しました: {e}")
        return

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
