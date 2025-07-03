import streamlit as st
import pandas as pd
import os
import base64

def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if not st.session_state.authenticated:
        pwd = st.text_input("パスワードを入力してください", type="password", key="password_input")
        if st.button("ログイン"):
            if pwd == "tp0000":
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("パスワードが違います。")

@st.cache_data
def load_faq_from_excel(file_path):
    df = pd.read_excel(file_path)
    df.columns = df.columns.str.strip()
    df = df.fillna('')
    return df.to_dict(orient='records')

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
            if not keywords:
                st.warning("検索キーワードを入力してください。")
            elif not results:
                st.info("該当するFAQはありません。")
            else:
                if not clear_query:
                    pass
                st.rerun()
    with col2:
        if st.button("📋 一覧", key=f"list_button_{'detail' if clear_query else 'home'}"):
            st.session_state.search_results = faqs
            st.session_state.selected_faq_index = None
            st.session_state.show_all_questions = True
            st.rerun()

def main():
    st.title("📚 FAQ検索")

    check_password()
    if not st.session_state.authenticated:
        return

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

    for key, default in [
        ("query", ""), ("search_mode", "AND"),
        ("search_results", []), ("selected_faq_index", None),
        ("show_all_questions", False)
    ]:
        st.session_state.setdefault(key, default)

    if st.session_state.selected_faq_index is None:
        search_ui(faqs)

        if st.session_state.search_results:
            title = "【FAQ一覧】" if st.session_state.show_all_questions else f"【FAQ検索結果 - {st.session_state.search_mode}検索】"
            st.write(f"### {title}")
            for idx, faq in enumerate(st.session_state.search_results):
                question = faq.get('質問', '').strip()
                if st.button(question, key=f"faq_button_{idx}"):
                    st.session_state.selected_faq_index = idx
                    st.rerun()
    else:
        results = st.session_state.search_results
        idx = st.session_state.selected_faq_index
        if idx is not None and idx < len(results):
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
                st.session_state.selected_faq_index = None
                st.rerun()

            st.markdown("---")
            st.subheader("🔎 新しく検索する")
            search_ui(faqs, clear_query=True)
        else:
            st.error("FAQの詳細を表示できません。")
            st.session_state.selected_faq_index = None

if __name__ == '__main__':
    main()
