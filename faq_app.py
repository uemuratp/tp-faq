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
from google.oauth2.service_account import Credentials

# -------------------------------
# 🔐 Googleスプレッドシート認証
# -------------------------------

import streamlit as st
import os
import json
import gspread
from google.oauth2.service_account import Credentials

@st.cache_resource
def get_worksheet(sheet_name):
    creds_info = None
    spreadsheet_id = None

    # ✅ 1. Cloud環境：secrets.toml 優先
    try:
        if "GOOGLE_CREDENTIALS" in st.secrets and "SPREADSHEET_ID" in st.secrets:
            creds_info = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
            spreadsheet_id = st.secrets["SPREADSHEET_ID"]
    except json.JSONDecodeError as e:
        st.error(f"❌ Cloud secrets の JSON 構文エラー: {e}")
        st.stop()
    except Exception as e:
        st.warning(f"⚠️ Cloud secrets の読み込み失敗: {e}")

    # ✅ 2. ローカル環境 fallback（toumei/credentials.json）
    if creds_info is None:
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            local_path = os.path.join(script_dir, "toumei", "credentials.json")

            with open(local_path, "r", encoding="utf-8") as f:
                st.write(f.read(100))
                creds_info = json.load(f)
                spreadsheet_id = creds_info.get("spreadsheet_id")
                st.write(f.read(100))


        except FileNotFoundError:
            st.error("❌ 認証ファイルが見つかりません（toumei/credentials.json）")
            st.stop()
        except json.JSONDecodeError as e:
            st.error(f"❌ credentials.json の JSON構文エラー: {e}")
            st.stop()
        except Exception as e:
            st.error(f"❌ ローカル認証情報の読み込み失敗: {e}")
            st.stop()

    # ✅ 3. 認証処理
    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
        gc = gspread.authorize(creds)
    except Exception as e:
        st.error(f"❌ 認証情報の読み取りに失敗しました（PEMエラーなど）: {e}")
        st.stop()

    # ✅ 4. スプレッドシート取得
    if not spreadsheet_id:
        st.error("❌ スプレッドシートIDが見つかりません（secrets または credentials.json に必要）")
        st.stop()

    try:
        spreadsheet = gc.open_by_key(spreadsheet_id)
        return spreadsheet.worksheet(sheet_name)
    except Exception as e:
        st.error(f"❌ スプレッドシート「{sheet_name}」の読み込み失敗: {e}")
        st.stop()








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

            # ✅ エラーを防ぐために以下は削除
            # st.session_state.query = query
            # st.session_state.search_mode = search_mode

            if not keywords:
                st.warning("検索キーワードを入力してください。")
            elif not results:
                st.info("該当するFAQはありません。")
                if "selected_category" in st.session_state:
                    log_no_hit(st.session_state.selected_category, query)

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

    
def render_patrol(df):
    st.write("### 🚧 パト指摘事項")

    def normalize_text(text):
        return str(text).strip().lower().replace('　', ' ').replace(' ', '')

    if 'search_results' not in st.session_state:
        st.session_state.search_results = []

    if st.session_state.page != "patrol_detail":
        # 検索フォーム
        with st.form(key="patrol_search_form"):
            query = st.text_input("🔍 設備名・指摘事項・対応・カテゴリで検索", value=st.session_state.get("query", ""))
            search_mode = st.radio("検索モードを選択してください", ('AND', 'OR'), index=('AND', 'OR').index(st.session_state.get("search_mode", "AND")))
            submitted = st.form_submit_button("検索")

        if submitted:
            keywords = [k for k in query.lower().split() if len(k) >= 2]
            results = []
            for _, row in df.iterrows():
                related_words_raw = [w.strip().lower() for w in row.get('関連ワード', '').split(',') if w.strip()]
                related_words = [''.join(normalize_seion(c) for c in converter.do(w)) for w in related_words_raw]
                raw_text = f"{row.get('設備名', '')} {row.get('指摘事項', '')} {row.get('対応', '')} {row.get('カテゴリ', '')}".lower()
                combined = ''.join(normalize_seion(c) for c in converter.do(raw_text))
                content = combined + " " + " ".join(related_words)

                if search_mode == 'AND' and all(k in content for k in keywords):
                    results.append({
                        '設備名': row.get('設備名', ''),
                        'カテゴリ': row.get('カテゴリ', ''),
                        '指摘事項': row.get('指摘事項', ''),
                        '対応': row.get('対応', '')
                    })
                elif search_mode == 'OR' and any(k in content for k in keywords):
                    results.append({
                        '設備名': row.get('設備名', ''),
                        'カテゴリ': row.get('カテゴリ', ''),
                        '指摘事項': row.get('指摘事項', ''),
                        '対応': row.get('対応', '')
                    })

            if not results:
                st.info("該当するパト指摘事項は見つかりませんでした。")
                if query:
                    log_no_hit("パト指摘事項", query)

            st.session_state.search_results = results
            st.session_state.query = query
            st.session_state.search_mode = search_mode
            st.session_state.page = "search"
            st.rerun()

    # 以下に一覧・詳細ページ処理が続く（省略）




    col1, col2 = st.columns(2)
    with col1:
        if st.button("📋 設備名一覧"):
            st.session_state.page = "patrol"
            st.session_state.search_results = []
            st.rerun()
    with col2:
        if st.button("📋 カテゴリ一覧"):
            st.session_state.page = "patrol_category"
            st.session_state.search_results = []
            st.rerun()

    # 検索結果表示（5）
    if st.session_state.search_results and st.session_state.page == "search":
        st.write("### 🔍 検索結果")
        seen = set()
        unique_results = []
        for row in st.session_state.search_results:
            key = (row['設備名'], row['カテゴリ'])
            if key not in seen:
                seen.add(key)
                unique_results.append(row)

        cols = st.columns(4)
        for i, row in enumerate(unique_results):
            match_rows = [r for r in st.session_state.search_results if r['設備名'] == row['設備名'] and r['カテゴリ'] == row['カテゴリ']]
            label = f"{row['設備名']} / {row['カテゴリ']} / {len(match_rows)}件"
            col = cols[i % 4]
            with col:
                if st.button(label, key=f"patrol_result_{i}"):
                    st.session_state.selected_equipment_norm = normalize_text(row['設備名'])
                    st.session_state.selected_equipment_name = row['設備名']
                    st.session_state.selected_patrol_note = row['カテゴリ']
                    st.session_state.page = "patrol_detail"
                    st.rerun()

    # 設備名一覧ページ（1）
    if st.session_state.page == "patrol":
        equipment_map = {}
        equipment_groups = {}
        for name in df['設備名']:
            norm = normalize_text(name)
            if norm not in equipment_map:
                equipment_map[norm] = name
        for _, row in df.iterrows():
            norm = normalize_text(row['設備名'])
            if norm not in equipment_groups:
                equipment_groups[norm] = []
            equipment_groups[norm].append(row)

        keys = sorted(equipment_map.items(), key=lambda x: len(equipment_groups[x[0]]), reverse=True)
        cols = st.columns(4)
        for i, (norm_key, original_name) in enumerate(keys):
            count = len(equipment_groups[norm_key])
            col = cols[i % 4]
            with col:
                if st.button(f"{original_name} / {count}件", key=f"equipment_{norm_key}"):
                    st.session_state.selected_equipment_norm = norm_key
                    st.session_state.selected_equipment_name = original_name
                    st.session_state.page = "patrol_note"
                    st.rerun()

    # カテゴリ一覧ページ（3）
    elif st.session_state.page == "patrol_category":
        categories = sorted(set(df['カテゴリ']), key=lambda c: len(df[df['カテゴリ'] == c]), reverse=True)
        cols = st.columns(4)
        for i, cat in enumerate(categories):
            count = len(df[df['カテゴリ'] == cat])
            label = f"{cat or '(カテゴリなし)'} / {count}件"
            col = cols[i % 4]
            with col:
                if st.button(label, key=f"cat_{cat}"):
                    st.session_state.selected_patrol_note = cat
                    st.session_state.page = "patrol_category_equipment"
                    st.rerun()

    # カテゴリ→設備一覧（4）
    elif st.session_state.page == "patrol_category_equipment":
        selected_note = st.session_state.selected_patrol_note
        rows = df[df['カテゴリ'] == selected_note]
        equipment_counts = rows['設備名'].value_counts()
        equipment_set = list(equipment_counts.index)
        st.markdown(f"### 「{selected_note}」に含まれる設備一覧")
        cols = st.columns(4)
        for i, eq in enumerate(equipment_set):
            count = len(rows[rows['設備名'] == eq])
            col = cols[i % 4]
            with col:
                if st.button(f"{eq} / {count}件", key=f"cat_eq_{eq}"):
                    st.session_state.selected_equipment_name = eq
                    st.session_state.selected_equipment_norm = normalize_text(eq)
                    st.session_state.page = "patrol_detail"
                    st.rerun()
        if st.button("🔙 カテゴリ一覧に戻る"):
            st.session_state.page = "patrol_category"
            st.rerun()

    # 設備→カテゴリ一覧（2）
    elif st.session_state.page == "patrol_note":
        norm_key = st.session_state.selected_equipment_norm
        equipment_name = st.session_state.selected_equipment_name
        rows = [r for _, r in df.iterrows() if normalize_text(r['設備名']) == norm_key]
        notes = {}
        for row in rows:
            note = row['カテゴリ']
            if note not in notes:
                notes[note] = []
            notes[note].append(row)
        st.markdown(f"### 「{equipment_name}」のカテゴリ一覧")
        cols = st.columns(4)
        sorted_notes = sorted(notes.items(), key=lambda item: len(item[1]), reverse=True)
        for i, (note, note_rows) in enumerate(sorted_notes):
            count = len(notes[note])
            col = cols[i % 4]
            with col:
                if st.button(f"{note or '(カテゴリなし)'} / {count}件", key=f"note_{note}"):
                    st.session_state.selected_patrol_note = note
                    st.session_state.page = "patrol_detail"
                    st.rerun()
        if st.button("🔙 設備一覧に戻る"):
            st.session_state.page = "patrol"
            st.rerun()

    # 詳細ページ
    elif st.session_state.page == "patrol_detail":
        norm_key = st.session_state.selected_equipment_norm
        equipment_name = st.session_state.selected_equipment_name
        selected_note = st.session_state.selected_patrol_note
        rows = [r for _, r in df.iterrows() if normalize_text(r['設備名']) == norm_key and r['カテゴリ'] == selected_note]
        st.markdown(f"### 詳細（設備名: {equipment_name}、カテゴリ: {selected_note}）")
        st.info(f"該当件数: {len(rows)} 件")
        for r in rows:
            st.markdown(f"- **指摘事項**: {r['指摘事項']}")
            st.markdown(f"  **対応**: {r['対応']}")
            st.markdown("---")
        if st.button("🔙 戻る"):
            prev_page = st.session_state.get("previous_page", "patrol")
            st.session_state.page = prev_page
            st.rerun()
        if st.button("🏠 ホームへ戻る"):
            st.session_state.page = "home"
            st.rerun()

def render_trouble(df):
    st.write("### ⚠️ トラブル事例")

    def normalize_text(text):
        return str(text).strip().lower().replace('　', ' ').replace(' ', '')

    def display_value(value, default_label):
        return value if str(value).strip() else default_label

    def trigger_rerun():
        st.rerun()

    if 'search_results' not in st.session_state:
        st.session_state.search_results = []

    if st.session_state.page != "trouble_detail":
        with st.form(key="trouble_search_form"):
            query = st.text_input("🔍 設備名・トラブル内容・対処・カテゴリ・現場名・備考で検索", value=st.session_state.get("query", ""))
            search_mode = st.radio("検索モードを選択してください", ('AND', 'OR'), index=('AND', 'OR').index(st.session_state.get("search_mode", "AND")))
            submitted = st.form_submit_button("検索")

        if submitted:
            keywords = [''.join(normalize_seion(c) for c in converter.do(k)) for k in query.lower().split() if len(k) >= 2]
            st.session_state.page = "trouble_search"
            results = []
            for _, row in df.iterrows():
                raw_text = f"{row.get('設備名', '')} {row.get('トラブル内容', '')} {row.get('対処', '')} {row.get('カテゴリ', '')} {row.get('現場名', '')} {row.get('詳細機器名', '')}".lower()
                content = ''.join(normalize_seion(c) for c in converter.do(raw_text))
                if search_mode == 'AND' and all(k in content for k in keywords):
                    results.append(dict(row))
                elif search_mode == 'OR' and any(k in content for k in keywords):
                    results.append(dict(row))

            if not results:
                st.info("該当するトラブル事例は見つかりませんでした。")
                if query:
                    log_no_hit("トラブル事例", query)

            st.session_state.search_results = results
            st.session_state.query = query
            st.session_state.search_mode = search_mode
            st.rerun()

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("📋 現場名一覧"):
            st.session_state.page = "trouble_site_list"
            st.session_state.search_results = []
            st.rerun()
    with col2:
        if st.button("📋 カテゴリ一覧"):
            st.session_state.page = "trouble_category_list"
            st.session_state.search_results = []
            st.rerun()
    with col3:
        if st.button("📝 登録"):
            st.session_state.page = "trouble_register"
            st.rerun()

    if st.session_state.page == "trouble_register":
        st.write("### 📝 トラブル事例 登録フォーム")

        st.markdown("#### 現場名")
        site_input = st.text_input("現場名を入力または選択", value=st.session_state.get("site_input", ""), placeholder="新規登録。登録済の場合は↓から選択してください。", label_visibility="collapsed", key="site_input")
        sites = sorted(set(df['現場名'].dropna().astype(str)))
        site_select = st.selectbox("登録済のワードはこちらから選択してください。", options=[""] + sites, index=0, key="site_select_trouble", on_change=trigger_rerun)
        site = site_select.strip() if site_select.strip() else site_input.strip()
        st.write(f"🪛 DEBUG: site = {site}")

        st.markdown("#### 設備名（大項目）")
        eq_input = st.text_input("設備名を入力または選択", value=st.session_state.get("eq_input", ""), placeholder="新規登録。登録済の場合は↓から選択してください。", label_visibility="collapsed", key="eq_input")
        eqs = sorted(set(df['設備名'].dropna().astype(str)))
        eq_select = st.selectbox("登録済のワードはこちらから選択してください。", options=[""] + eqs, index=0, key="eq_select_trouble", on_change=trigger_rerun)
        eq = eq_select.strip() if eq_select.strip() else eq_input.strip()
        st.write(f"🪛 DEBUG: eq = {eq}")

        st.markdown("#### カテゴリ（中項目）")
        mask = pd.Series(True, index=df.index)
        if site:
            mask &= df['現場名'].astype(str).apply(normalize_text) == normalize_text(site)
        if eq:
            mask &= df['設備名'].astype(str).apply(normalize_text) == normalize_text(eq)
        cat_df = df[mask]
        cats = sorted(set(cat_df['カテゴリ'].dropna().astype(str)))
        st.write(f"🪛 DEBUG: mask category hit count = {len(cat_df)}")
        cat_input = st.text_input("カテゴリを入力または選択", value=st.session_state.get("cat_input", ""), placeholder="新規登録。登録済の場合は↓から選択してください。", label_visibility="collapsed", key="cat_input")
        cat_select = st.selectbox("登録済のワードはこちらから選択してください。", options=[""] + cats, index=0, key="cat_select_trouble", on_change=trigger_rerun)
        category = cat_select.strip() if cat_select.strip() else cat_input.strip()
        st.write(f"🪛 DEBUG: category = {category}")

        st.markdown("#### 詳細機器名（小項目）")
        mask2 = pd.Series(True, index=df.index)
        if site:
            mask2 &= df['現場名'].astype(str).apply(normalize_text) == normalize_text(site)
        if eq:
            mask2 &= df['設備名'].astype(str).apply(normalize_text) == normalize_text(eq)
        if category:
            mask2 &= df['カテゴリ'].astype(str).apply(normalize_text) == normalize_text(category)
        detail_df = df[mask2]
        st.write(f"🪛 DEBUG: mask2 detail hit count = {len(detail_df)}")
        details = sorted(set(detail_df['詳細機器名'].dropna().astype(str)))
        detail_input = st.text_input("詳細機器名", placeholder="正式名称推奨", label_visibility="collapsed", key="detail_input")
        detail_select = st.selectbox("登録済のワードはこちらから選択してください。", options=[""] + details, index=0, key="detail_select_trouble", on_change=trigger_rerun)
        detail = detail_select.strip() if detail_select.strip() else detail_input.strip()

        st.markdown("#### トラブル内容")
        content = st.text_area("トラブル内容")

        st.markdown("#### 対処")
        response = st.text_area("対処")

        if st.button("登録する"):
            try:
                worksheet = get_worksheet("トラブル事例")
                worksheet.append_row([site, eq, detail, content, response, category])
                st.success("トラブル事例を登録しました。")
                if st.button("🏠 ホームへ戻る"):
                    st.session_state.page = "home"
                    st.rerun()
            except Exception as e:
                st.error(f"登録に失敗しました: {e}")
        return





















    # 以降、既存のカテゴリ・現場一覧・詳細処理が続く（省略）









    elif st.session_state.page == "trouble_category_detail":
        selected_cat = st.session_state.selected_trouble_category
        rows = df[df['カテゴリ'].fillna('').apply(lambda x: display_value(x, "カテゴリ登録なし")) == selected_cat]
        grouped = rows.groupby(['現場名', '設備名'])
        st.markdown(f"### 「{selected_cat}」に含まれる事例")
        cols = st.columns(4)
        for i, ((site, eq), group) in enumerate(grouped):
            site_label = display_value(site, "現場名登録なし")
            eq_label = display_value(eq, "設備名なし")
            label = f"{site_label} / {eq_label} / {len(group)}件"
            col = cols[i % 4]
            with col:
                if st.button(label, key=f"trouble_detail_btn_{site}_{eq}"):
                    st.session_state.selected_site = site
                    st.session_state.selected_equipment = eq
                    st.session_state.selected_trouble_category = selected_cat
                    st.session_state.page = "trouble_detail"
                    st.rerun()

    elif st.session_state.page == "trouble_site_list":
        sites = sorted(set(display_value(s, "現場名登録なし") for s in df['現場名']))
        cols = st.columns(4)
        for i, site in enumerate(sites):
            count = len(df[df['現場名'].fillna('').apply(lambda x: display_value(x, "現場名登録なし")) == site])
            col = cols[i % 4]
            with col:
                if st.button(f"{site} / {count}件", key=f"trouble_site_{site}"):
                    st.session_state.selected_trouble_site = site
                    st.session_state.page = "trouble_site_detail"
                    st.rerun()

    elif st.session_state.page == "trouble_site_detail":
        site = st.session_state.selected_trouble_site
        rows = df[df['現場名'].fillna('').apply(lambda x: display_value(x, "現場名登録なし")) == site]
        grouped = rows.groupby(['現場名', '設備名'])
        st.markdown(f"### 「{site}」に含まれる事例")
        cols = st.columns(4)
        for i, ((site, eq), group) in enumerate(grouped):
            site_label = display_value(site, "現場名登録なし")
            eq_label = display_value(eq, "設備名なし")
            label = f"{site_label} / {eq_label} / {len(group)}件"
            col = cols[i % 4]
            with col:
                if st.button(label, key=f"trouble_detail_btn_site_{site}_{eq}"):
                    st.session_state.selected_site = site
                    st.session_state.selected_equipment = eq
                    st.session_state.selected_trouble_category = group.iloc[0]['カテゴリ'] if 'カテゴリ' in group.columns else ''
                    st.session_state.page = "trouble_detail"
                    st.rerun()

    elif st.session_state.page == "trouble_detail":
        site = display_value(st.session_state.selected_site, "現場名登録なし")
        eq = display_value(st.session_state.selected_equipment, "設備名なし")
        cat = display_value(st.session_state.selected_trouble_category, "カテゴリ登録なし")
        rows = df[(df['現場名'].fillna('').apply(lambda x: display_value(x, "現場名登録なし")) == site) &
                  (df['設備名'].fillna('').apply(lambda x: display_value(x, "設備名なし")) == eq) &
                  (df['カテゴリ'].fillna('').apply(lambda x: display_value(x, "カテゴリ登録なし")) == cat)]
        st.markdown(f"### 詳細（現場名: {site}、設備名: {eq}、カテゴリ: {cat}）")
        st.info(f"該当件数: {len(rows)} 件")
        for r in rows.to_dict(orient='records'):
            st.markdown(f"- **詳細機器名**: {display_value(r.get('詳細機器名', ''), '詳細機器名なし')}")
            st.markdown(f"  **トラブル内容**: {display_value(r.get('トラブル内容', ''), 'トラブル内容なし')}")
            st.markdown(f"  **対処**: {display_value(r.get('対処', ''), '対処なし')}")
            st.markdown("---")

        if st.button("🔙 戻る"):
            prev_page = st.session_state.get("previous_page", "trouble_category_detail")
            st.session_state.page = prev_page
            st.rerun()
        if st.button("🏠 ホームへ戻る"):
            st.session_state.page = "home"
            st.rerun()






    
def main():
    st.title("📚 FAQ検索")
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

    # ✅ ① カテゴリ選択（スプレッドシートのシート名と一致）
    categories = ["工事関係", "事務関係", "その他", "パト指摘事項", "トラブル事例"]
    selected_category = st.selectbox("カテゴリを選択してください", categories)
    st.session_state.selected_category = selected_category  # ← log記録にも必要

    # ✅ ② カテゴリに応じてデータ読み込み
    try:
        if selected_category in ["工事関係", "事務関係", "その他"]:
            faqs = load_faq_from_sheet(selected_category)
            st.session_state.category_type = "faq"
        elif selected_category == "パト指摘事項":
            df = get_as_dataframe(get_worksheet("パト指摘事項")).fillna('')
            st.session_state.category_type = "patrol"
        elif selected_category == "トラブル事例":
            df = get_as_dataframe(get_worksheet("トラブル事例")).fillna('')
            st.session_state.category_type = "trouble"
        else:
            st.error("未対応のカテゴリです。")
            return
    except Exception as e:
        st.error(f"データ読み込みに失敗しました: {e}")
        return

    # ✅ ③ ページ遷移処理
    if st.session_state.category_type == "faq":
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

    elif st.session_state.category_type == "patrol":
        render_patrol(df)

    elif st.session_state.category_type == "trouble":
        render_trouble(df)


if __name__ == "__main__":
    main()


