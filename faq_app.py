import streamlit as st
import pandas as pd
import os
import base64

def rerun():
    st.rerun()

def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if not st.session_state.authenticated:
        pwd = st.text_input("パスワードを入力してください", type="password")
        if pwd == "tp0000":
            st.session_state.authenticated = True
            rerun()
        elif pwd:
            st.error("パスワードが違います。")

@st.cache_data
def load_faq_from_excel(file_path):
    df = pd.read_excel(file_path)
    df.columns = df.columns.str.strip()
    df = df.fillna('')
    faqs = df.to_dict(orient='records')
    return faqs

def search_faqs(keywords, faqs, search_mode='AND'):
    results = []
    for faq in faqs:
        question = str(faq.get('質問', '')).lower()
        related = str(faq.get('関連ワード', '')).lower()
        content = f"{question} {related}"
        if search_mode == 'AND':
            if all(keyword in content for keyword in keywords):
                results.append(faq)
        elif search_mode == 'OR':
            if any(keyword in content for keyword in keywords):
                results.append(faq)
    return results

def run_search(query, search_mode, faqs):
    keywords = query.lower().split()
    return search_faqs(keywords, faqs, search_mode)

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

def main():
    st.title("📚 FAQ検索")

    check_password()
    if not st.session_state.get("authenticated", False):
        return

    faq_files = [
        {"label": "工事関係", "path": "faq.xlsx"},
        {"label": "事務関係", "path": "faq2.xlsx"},
        {"label": "その他（作成中）", "path": "other_faq.xlsx"},
    ]

    options = [f["label"] for f in faq_files]
    selected_label = st.selectbox("知りたい内容を選択してください", options)
    selected_file = next((f["path"] for f in faq_files if f["label"] == selected_label), None)
    if selected_file is None:
        st.error("ファイル選択が正しくありません。")
        return

    try:
        faqs = load_faq_from_excel(selected_file)
    except Exception as e:
        st.error(f"FAQの読み込みに失敗しました: {e}")
        return

    # セッションステート初期化
    if "query" not in st.session_state:
        st.session_state.query = ""
    if "run_search" not in st.session_state:
        st.session_state.run_search = False
    if "selected_faq_index" not in st.session_state:
        st.session_state.selected_faq_index = None
    if "search_results" not in st.session_state:
        st.session_state.search_results = []
    if "show_all_questions" not in st.session_state:
        st.session_state.show_all_questions = False

    def trigger_search():
        st.session_state.run_search = True
        st.session_state.selected_faq_index = None
        st.session_state.show_all_questions = False

    def show_all_questions():
        st.session_state.show_all_questions = True
        st.session_state.run_search = False
        st.session_state.selected_faq_index = None

    if st.session_state.selected_faq_index is None:
        # 入力 + ボタン表示
        st.text_input("🔍 検索キーワードを空白で区切って入力してください", key="query", on_change=trigger_search)
        search_mode = st.radio("検索モードを選択してください", ('AND', 'OR'))

        col1, col2 = st.columns(2)
        with col1:
            if st.button("検索"):
                trigger_search()
        with col2:
            if st.button("📋 一覧"):
                show_all_questions()

        # 検索結果表示
        if st.session_state.run_search:
            if not st.session_state.query.strip():
                st.warning("検索キーワードを入力してください。")
                return
            results = run_search(st.session_state.query, search_mode, faqs)
            st.session_state.search_results = results
            st.session_state.run_search = False

            if results:
                st.write(f"### 【FAQ検索結果 - {search_mode}検索】")
                for i, r in enumerate(results):
                    question = str(r.get('質問', '')).strip()
                    if st.button(question, key=f"faq_search_{i}"):
                        st.session_state.selected_faq_index = i
                        rerun()
            else:
                st.info("該当するFAQはありません。")

        # 一覧表示
        elif st.session_state.show_all_questions:
            st.write("### 【FAQ一覧】")
            st.session_state.search_results = faqs  # 全体を検索結果として保持
            for i, r in enumerate(faqs):
                question = str(r.get('質問', '')).strip()
                if st.button(question, key=f"faq_list_{i}"):
                    st.session_state.selected_faq_index = i
                    rerun()

    else:
        results = st.session_state.search_results
        idx = st.session_state.selected_faq_index
        if idx is not None and idx < len(results):
            faq = results[idx]
            st.write(f"### 質問: {faq.get('質問', '')}")
            st.write(f"**回答:** {faq.get('回答', '')}")

            related_value = faq.get('関連ワード', '')
            if not isinstance(related_value, str):
                related_value = str(related_value)
            related = related_value.strip() or 'なし'
            st.write(f"**関連ワード:** {related}")

            attachment_value = faq.get('添付ファイル', '')
            if attachment_value:
                files = [f.strip() for f in str(attachment_value).split(",") if f.strip()]
                for f in files:
                    display_attachment(f)
            else:
                st.write("**添付ファイル:** なし")

            if st.button("🔙 戻る"):
                st.session_state.selected_faq_index = None
                rerun()
        else:
            st.error("FAQの詳細を表示できません。")
            st.session_state.selected_faq_index = None

if __name__ == '__main__':
    main()
