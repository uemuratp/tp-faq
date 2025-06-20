import streamlit as st
import pandas as pd

# ExcelからFAQを読み込む
def load_faq_from_excel(file_path):
    df = pd.read_excel(file_path)
    df.columns = df.columns.str.strip()  # 列名の空白除去
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
    st.title("FAQ検索アプリ")

    # ファイルとラベルの対応表
    faq_files = [
        {"label": "工事関係", "path": "faq.xlsx"},
        {"label": "事務関係", "path": "faq2.xlsx"},
        {"label": "その他（作成中）", "path": "other_faq.xlsx"}
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

    # 検索状態管理
    if "query" not in st.session_state:
        st.session_state.query = ""
    if "run_search" not in st.session_state:
        st.session_state.run_search = False

    # エンターキーで検索実行
    def trigger_search():
        st.session_state.run_search = True

    st.text_input(
        "検索キーワードを空白で区切って入力してください",
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
                st.write(f"**検索ワード:** {r.get('質問', '').strip()}")
                answer = r.get('回答', '')
                if pd.isna(answer):
                    answer = ''
                st.write(f"**回答:** {answer.strip()}")
                st.write(f"**関連ワード:** {r.get('関連ワード', '').strip()}")
                st.markdown("---")
        else:
            st.info("該当するFAQはありません。")

        # 検索後に状態をリセット
        st.session_state.run_search = False

if __name__ == '__main__':
    main()
