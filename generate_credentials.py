with open("toumei/credentials.json", "rb") as f:
    raw_bytes = f.read(100)
st.code(raw_bytes)
