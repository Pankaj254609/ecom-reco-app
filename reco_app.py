import streamlit as st
import pandas as pd

st.set_page_config(page_title="E-com Reco App", layout="wide")
st.title("📊 ई-कॉमर्स पेमेंट रिकॉन्सिलिएशन डैशबोर्ड")

uploaded_file = st.file_uploader("अपनी अमेज़न, मीश्रो, स्नैपडील या म्यंतरा की फाइल अपलोड करें", type=["xlsx", "csv"])

if uploaded_file is not None:
    # फाइल को रीड करना (CSV या Excel)
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)
        
    st.success("फाइल सफलतापूर्वक अपलोड हो गई है!")
    
    # ---- ऑटोमैटिक कॉलम ढूंढने का लॉजिक ----
    date_col = None
    brand_col = None
    
    # संभावित नाम जो तारीख और ब्रांड कॉलम के हो सकते हैं
    potential_date_cols = ['date', 'order date', 'posting date', 'transaction date', 'तारीख', 'invoice date']
    potential_brand_cols = ['brand', 'brand name', 'vendor', 'marketplace', 'portal', 'नाम', 'name', 'account']
    
    # कॉलम ढूंढना
    for col in df.columns:
        col_lower = str(col).lower().strip()
        if any(p_date in col_lower for p_date in potential_date_cols) and date_col is None:
            date_col = col
        if any(p_brand in col_lower for p_brand in potential_brand_cols) and brand_col is None:
            brand_col = col
            
    # अगर सीधे नाम से न मिले तो पहली तारीख जैसी दिखने वाली वैल्यू ढूंढना
    if date_col is None:
        for col in df.columns:
            if df[col].astype(str).str.contains(r'\d{2,4}[-/]\d{2}[-/]\d{2,4}').any():
                date_col = col
                break

    # ---- डेटा फिल्टरेशन और डिस्प्ले ----
    col1, col2 = st.columns(2)
    
    with col1:
        if date_col:
            st.info(f"📅 तारीख का कॉलम मिला: **{date_col}**")
            # तारीख को सही फॉर्मेट में बदलना
            df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
            
            # तारीख का फिल्टर (Sidebar या मेन पेज पर)
            min_date = df[date_col].min()
            max_date = df[date_col].max()
            
            if pd.notnull(min_date) and pd.notnull(max_date):
                start_date, end_date = st.date_input("तारीख रेंज चुनें:", [min_date.date(), max_date.date()])
                # डेटा फिल्टर करना
                df = df[(df[date_col].dt.date >= start_date) & (df[date_col].dt.date <= end_date)]
        else:
            st.warning("⚠️ फाइल में तारीख (Date) का कॉलम ऑटोमैटिक नहीं मिल पाया।")

    with col2:
        if brand_col:
            st.info(f"🏷️ ब्रांड/नाम का कॉलम मिला: **{brand_col}**")
            # यूनिक ब्रांड्स की लिस्ट निकालना
            unique_brands = df[brand_col].dropna().unique()
            selected_brand = st.selectbox("ब्रांड या पोर्टल चुनें:", ["सब (All)"] + list(unique_brands))
            
            if selected_brand != "सब (All)":
                df = df[df[brand_col] == selected_brand]
        else:
            st.warning("⚠️ फाइल में ब्रांड या नाम (Name/Brand) का कॉलम ऑटोमैटिक नहीं मिल पाया।")

    # फिल्टर किया हुआ डेटा दिखाना
    st.subheader("📋 फिल्टर किया हुआ डेटा")
    st.dataframe(df)
    
    # डाउनलोड बटन
    st.download_button(
        label="📥 फिल्टर डेटा एक्सेल में डाउनलोड करें",
        data=df.to_csv(index=False).encode('utf-8'),
        file_name='filtered_reco_data.csv',
        mime='text/csv',
    )
