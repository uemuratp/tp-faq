import streamlit as st
import pandas as pd
import os

# ExcelからFAQを読み込む
def load_faq_from_excel(file_path):
    df = pd.read_excel(file_path)
    df.columns = df.columns.str.strip()
    df = df.fillna('')
    faqs = df.to_dict(orient='records')
    return faqs

# 質問と関連ワードだけを対象に検索
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

# 検索実行関数
def run_search(query, search_mode, faqs):
    keywords = query.lower().split()
    return search_faqs(keywords, faqs, search_mode)

# メインアプリ
def main():
    st.title("📚 FAQ検索")

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

    if "query" not in st.session_state:
        st.session_state.query = ""
    if "run_search" not in st.session_state:
        st.session_state.run_search = False

    def trigger_search():
        st.session_state.run_search = True

    st.text_input(
        "🔍 検索キーワードを空白で区切って入力してください",
        key="query",
        on_change=trigger_search
    )

    search_mode = st.radio("検索モードを選択してください", ('AND', 'OR'))

    if st.button("検索（ボタン）を押してもOK") or st.session_state.run_search:
        if not st.session_state.query.strip():
            st.warning("検索キーワードを入力してください。")
            return

        results = run_search(st.session_state.query, search_mode, faqs)

        st.write(f"### 【FAQ検索結果 - {search_mode}検索】")
        if results:
            for r in results:
                question = str(r.get('質問', '')).strip()
                answer = str(r.get('回答', '')).strip()
                
                related_value = r.get('関連ワード', '')
                if not isinstance(related_value, str):
                    related_value = str(related_value)
                related = related_value.strip()
                if related == '':
                    related = 'なし'

                st.write(f"**質問:** {question}")
                st.write(f"**回答:** {answer}")
                st.write(f"**関連ワード:** {related}")
                st.markdown("---")
        else:
            st.info("該当するFAQはありません。")

        st.session_state.run_search = False

if __name__ == '__main__':
    main()
