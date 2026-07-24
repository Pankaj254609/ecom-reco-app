import io
import os
import random
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime

import barcode
import pandas as pd
import qrcode
import streamlit as st
from barcode.writer import ImageWriter
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.platypus import Image as RLImage
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from supabase import Client, create_client

# --- Theme Configuration ---
st.set_page_config(
    page_title="Learnwell's E-commerce Reconcile Pro Engine", layout="wide"
)

st.markdown(
    """
    <style>
    .main { background-color: #f8f9fa; }
    h1, h2, h3 { color: #0f172a; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; font-weight: 700; }
    [data-testid="stSidebar"] { background-color: #0f172a !important; color: #ffffff !important; }
    [data-testid="stSidebar"] *.stText, [data-testid="stSidebar"] label, [data-testid="stSidebar"] h1 { color: #ffffff !important; }
    .metric-container {
        background-color: #ffffff; border-radius: 12px; padding: 20px;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); border-left: 6px solid #3b82f6; margin-bottom: 15px;
    }
    .metric-title { font-size: 13px; color: #64748b; font-weight: 600; text-transform: uppercase; }
    .metric-value { font-size: 26px; color: #1e293b; font-weight: 700; margin-top: 5px; }
    .card-blue { border-left-color: #3b82f6; }
    .card-orange { border-left-color: #f97316; }
    .card-green { border-left-color: #10b981; }
    .card-red { border-left-color: #ef4444; }
    .stButton>button {
        background-color: #2563eb !important; color: white !important;
        border-radius: 8px !important; padding: 8px 24px !important; font-weight: 600 !important; border: none !important;
    }
    .stButton>button:hover { background-color: #1d4ed8 !important; }
    </style>
""",
    unsafe_allow_html=True,
)


# --- SUPABASE CONNECTION ---
@st.cache_resource
def init_supabase() -> Client:
  url = st.secrets["supabase"]["url"]
  key = st.secrets["supabase"]["key"]
  return create_client(url, key)


try:
  supabase = init_supabase()
except Exception as e:
  st.error(f"Supabase Client Connection Error: {e}")


# --- HELPER: SAMPLE TEMPLATE GENERATOR ---
def create_sample_csv(columns_dict):
  df_sample = pd.DataFrame(columns_dict)
  return df_sample.to_csv(index=False).encode("utf-8")


def convert_df_to_csv(df):
  return df.to_csv(index=False).encode("utf-8")


def clean_sku(val):
  if pd.isna(val):
    return ""
  s = str(val).strip().upper()
  if s.endswith(".0"):
    s = s[:-2]
  return s


# --- HIGH RESOLUTION BARCODE & QR GENERATOR ---
def generate_barcode_img(text):
  code128 = barcode.get_barcode_class("code128")
  rv = io.BytesIO()
  writer_options = {
      "module_height": 10.0,
      "quiet_zone": 2.0,
      "font_size": 10,
      "text_distance": 3.0,
      "write_text": True,
      "dpi": 300,
  }
  code = code128(text, writer=ImageWriter())
  code.write(rv, options=writer_options)
  rv.seek(0)
  return rv


def generate_qrcode_img(text):
  qr = qrcode.QRCode(
      version=1,
      error_correction=qrcode.constants.ERROR_CORRECT_M,
      box_size=10,
      border=2,
  )
  qr.add_data(text)
  qr.make(fit=True)
  img = qr.make_image(fill_color="black", back_color="white")
  rv = io.BytesIO()
  img.save(rv, format="PNG")
  rv.seek(0)
  return rv


# --- PDF GENERATOR ---
def generate_codes_pdf(sku_qty_dict, code_type="barcode"):
  pdf_buffer = io.BytesIO()
  doc = SimpleDocTemplate(
      pdf_buffer,
      pagesize=A4,
      rightMargin=10,
      leftMargin=10,
      topMargin=15,
      bottomMargin=15,
  )
  elements = []
  data_matrix = []
  current_row = []
  cols = 3
  img_w = 2.4 * inch
  img_h = 1.0 * inch if code_type == "barcode" else 1.8 * inch

  expanded_sku_list = []
  for sku, qty in sku_qty_dict.items():
    clean_s = str(sku).strip().upper()
    try:
      count = int(qty)
    except:
      count = 1
    expanded_sku_list.extend([clean_s] * max(1, count))

  for clean_s in expanded_sku_list:
    img_stream = (
        generate_barcode_img(clean_s)
        if code_type == "barcode"
        else generate_qrcode_img(clean_s)
    )
    rl_img = RLImage(img_stream, width=img_w, height=img_h)
    current_row.append(rl_img)

    if len(current_row) == cols:
      data_matrix.append(current_row)
      current_row = []

  if current_row:
    while len(current_row) < cols:
      current_row.append("")
    data_matrix.append(current_row)

  if data_matrix:
    t = Table(data_matrix, colWidths=[2.55 * inch] * cols)
    t.setStyle(
        TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
        ])
    )
    elements.append(t)

  doc.build(elements)
  pdf_buffer.seek(0)
  return pdf_buffer


# --- DATA LOAD ENGINE ---
def fetch_chunk(table_name, start, limit):
  try:
    res = (
        supabase.table(table_name)
        .select("*")
        .range(start, start + limit - 1)
        .execute()
    )
    return res.data if res.data else []
  except:
    return []


@st.cache_data(ttl=300, show_spinner="⚡ Syncing Reconcile Data...")
def load_data_cached():

  def fetch_all(table_name):
    try:
      res = supabase.table(table_name).select("*").execute()
      return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except:
      return pd.DataFrame()

  df_p = fetch_all("master_sku")
  if not df_p.empty:
    actual_cols = [
        "category_code",
        "product_code",
        "name",
        "scan_identifier",
        "color",
        "size",
        "brand",
        "type",
        "component_product_code",
        "qty",
        "image_url",
    ]
    df_p = df_p[[c for c in actual_cols if c in df_p.columns]]
    df_p.columns = [
        "Category Code",
        "Product Code",
        "Name",
        "Scan Identifier",
        "Color",
        "Size",
        "Brand",
        "Type",
        "Component Product Code",
        "QTY",
        "Image URL",
    ][: len(df_p.columns)]

  df_m = fetch_all("channel_sku_map")
  if not df_m.empty:
    df_m = df_m.drop(columns=["id", "created_at"], errors="ignore")
    df_m.columns = [
        "Seller SKU on Channel",
        "SKU Code",
        "channelName",
        "PACK OF",
        "BRAND",
    ][: len(df_m.columns)]

  df_sa = fetch_all("sale_data")
  if not df_sa.empty:
    df_sa = df_sa.drop(columns=["created_at"], errors="ignore")
    df_sa = df_sa.rename(
        columns={
            "id": "ID",
            "date": "Date",
            "channel_sku": "Channel SKU",
            "type": "Type",
            "brand": "Brand",
            "qty": "Qty",
        }
    )

  df_st = fetch_all("add_inventory")
  if not df_st.empty:
    df_st = df_st.drop(columns=["created_at"], errors="ignore")
    df_st = df_st.rename(
        columns={
            "id": "ID",
            "product_code": "Product Code",
            "added_qty": "Added QTY",
            "brand": "Brand",
        }
    )
    if "Date & Time" not in df_st.columns:
      df_st["Date & Time"] = datetime.now().strftime("%Y-%m-%d")

  return df_p, df_m, df_sa, df_st


def clear_app_cache():
  st.cache_data.clear()


# --- SMART MASTER SKU RESOLVER ---
def resolve_to_master_sku(scanned_code, df_master, df_mapping):
  clean_input = clean_sku(scanned_code)
  if not clean_input:
    return ""

  if not df_master.empty:
    if "Product Code" in df_master.columns:
      match = df_master[
          df_master["Product Code"].apply(clean_sku) == clean_input
      ]
      if not match.empty:
        return match.iloc[0]["Product Code"]
    if "Scan Identifier" in df_master.columns:
      match = df_master[
          df_master["Scan Identifier"].apply(clean_sku) == clean_input
      ]
      if not match.empty:
        return match.iloc[0]["Product Code"]

  if not df_mapping.empty and "Seller SKU on Channel" in df_mapping.columns:
    match_map = df_mapping[
        df_mapping["Seller SKU on Channel"].apply(clean_sku) == clean_input
    ]
    if not match_map.empty:
      return clean_sku(match_map.iloc[0]["SKU Code"])

  return clean_input


# --- SIDEBAR CONTROL PANEL ---
st.sidebar.markdown(
    "<h2 style='color:white; text-align:center;'>Learnwell Reconcile Pro</h2>",
    unsafe_allow_html=True,
)
if st.sidebar.button("🔄 Refresh Application Cache"):
  clear_app_cache()
  st.rerun()

st.sidebar.write("---")
menu = st.sidebar.radio(
    "📌 MODULE NAVIGATION:", [
        "📊 Live Executive Dashboard",
        "💰 Payment Settlement Reconciliation",
        "🚚 Return & Claims Reconciliation",
        "📦 1. MASTER SKU Manager",
        "🔗 2. CHANNEL SKU Mapping",
        "📥 3. ADD INVENTORY (Stock Inward)",
        "📤 4. SALES DATA Manifest",
    ]
)

df_prod, df_map, df_sales, df_stock = load_data_cached()

# ==================== 📊 DASHBOARD ====================
if menu == "📊 Live Executive Dashboard":
  st.markdown(
      "<h1>📊 Learnwell Reconcile Pro Dashboard</h1>", unsafe_allow_html=True
  )

  col1, col2, col3, col4 = st.columns(4)
  with col1:
    st.markdown(
        '<div class="metric-container card-blue"><div'
        ' class="metric-title">Master SKUs Linked</div><div'
        ' class="metric-value">'
        f"{len(df_prod)}</div></div>",
        unsafe_allow_html=True,
    )
  with col2:
    st.markdown(
        '<div class="metric-container card-orange"><div'
        ' class="metric-title">Total Sales Orders</div><div'
        ' class="metric-value">'
        f'{int(df_sales["Qty"].sum()) if not df_sales.empty and "Qty" in df_sales.columns else 0}</div></div>',
        unsafe_allow_html=True,
    )
  with col3:
    st.markdown(
        '<div class="metric-container card-green"><div'
        ' class="metric-title">Stock Inwarded</div><div'
        ' class="metric-value">'
        f'{int(df_stock["Added QTY"].sum()) if not df_stock.empty and "Added QTY" in df_stock.columns else 0}</div></div>',
        unsafe_allow_html=True,
    )
  with col4:
    st.markdown(
        '<div class="metric-container card-red"><div'
        ' class="metric-title">Channel Mappings</div><div'
        ' class="metric-value">'
        f"{len(df_map)}</div></div>",
        unsafe_allow_html=True,
    )

  st.write("---")
  st.subheader("📋 Recent Sales Manifest")
  st.dataframe(df_sales.head(10), use_container_width=True, hide_index=True)

# ==================== 💰 PAYMENT RECONCILIATION ====================
elif menu == "💰 Payment Settlement Reconciliation":
  st.markdown(
      "<h1>💰 Portal Payment & Deduction Reconciliation</h1>",
      unsafe_allow_html=True,
  )
  st.caption(
      "Amazon, Flipkart, Meesho Settlement CSV upload karke Sale Amount vs Net"
      " Payout verify karein."
  )

  portal = st.selectbox(
      "Choose Marketplace Portal",
      ["Amazon", "Flipkart", "Meesho", "Myntra", "Snapdeal"],
  )

  # Template Download
  p_sample = {
      "Order_ID": ["ORD1001", "ORD1002"],
      "Sale_Amount": [1200.0, 850.0],
      "Marketplace_Fee": [120.0, 85.0],
      "Shipping_Fee": [80.0, 60.0],
      "Net_Payout": [1000.0, 705.0],
  }
  st.download_button(
      "📥 Download Settlement Upload Template (CSV)",
      data=create_sample_csv(p_sample),
      file_name=f"{portal}_Settlement_Template.csv",
      mime="text/csv",
  )

  settlement_file = st.file_uploader(
      f"Upload {portal} Settlement File (CSV/Excel)", type=["csv", "xlsx"]
  )

  if settlement_file:
    df_settle = (
        pd.read_csv(settlement_file)
        if settlement_file.name.endswith(".csv")
        else pd.read_excel(settlement_file)
    )
    st.subheader("📊 Settlement Audit Summary")

    if (
        "Sale_Amount" in df_settle.columns
        and "Net_Payout" in df_settle.columns
    ):
      df_settle["Calculated_Deduction"] = (
          df_settle["Sale_Amount"] - df_settle["Net_Payout"]
      )
      st.dataframe(df_settle, use_container_width=True, hide_index=True)
      st.success("✅ Reconciliation Processed Successfully!")
    else:
      st.warning(
          "⚠️ Uploaded file me 'Sale_Amount' aur 'Net_Payout' columns hone"
          " chahiye."
      )

# ==================== 🚚 RETURN RECONCILIATION ====================
elif menu == "🚚 Return & Claims Reconciliation":
  st.markdown(
      "<h1>🚚 Logistics Return & Claim Audit Module</h1>",
      unsafe_allow_html=True,
  )

  r_sample = {
      "Order_ID": ["ORD1001", "ORD1003"],
      "Return_Type": ["RTO", "DTO"],
      "Tracking_Number": ["AWB12345", "AWB67890"],
      "Claim_Status": ["Pending", "Approved"],
      "Claim_Amount": [0.0, 450.0],
  }
  st.download_button(
      "📥 Download Return/Claim Template (CSV)",
      data=create_sample_csv(r_sample),
      file_name="Return_Claims_Template.csv",
      mime="text/csv",
  )

  ret_file = st.file_uploader(
      "Upload Returns & Claims Report", type=["csv", "xlsx"]
  )
  if ret_file:
    df_ret = (
        pd.read_csv(ret_file)
        if ret_file.name.endswith(".csv")
        else pd.read_excel(ret_file)
    )
    st.dataframe(df_ret, use_container_width=True, hide_index=True)

# ==================== 📦 MASTER SKU MANAGER ====================
elif menu == "📦 1. MASTER SKU Manager":
  st.markdown("<h1>📦 Master SKU Catalog Engine</h1>", unsafe_allow_html=True)

  tab_m1, tab_m2 = st.tabs(["📋 View Catalog", "📁 Bulk Upload Master SKUs"])

  with tab_m1:
    st.dataframe(df_prod, use_container_width=True, hide_index=True)

  with tab_m2:
    master_template = {
        "category_code": ["CAT01"],
        "product_code": ["MSKU-RED-M"],
        "name": ["Red T-Shirt M"],
        "scan_identifier": ["BAR123456"],
        "color": ["Red"],
        "size": ["M"],
        "brand": ["VIDA LOCA"],
        "type": ["SINGLE"],
        "component_product_code": [""],
        "qty": [100],
        "image_url": [""],
    }
    st.download_button(
        "📥 Download Master SKU CSV Template",
        data=create_sample_csv(master_template),
        file_name="Master_SKU_Template.csv",
        mime="text/csv",
    )

    f_master = st.file_uploader(
        "Upload Master SKU File", type=["csv", "xlsx"], key="m_upload"
    )
    if f_master and st.button("🚀 Process Master SKU Import"):
      try:
        df_u = (
            pd.read_csv(f_master)
            if f_master.name.endswith(".csv")
            else pd.read_excel(f_master)
        )
        supabase.table("master_sku").insert(
            df_u.to_dict(orient="records")
        ).execute()
        clear_app_cache()
        st.success("Master SKUs Imported Successfully!")
        st.rerun()
      except Exception as e:
        st.error(f"Upload Error: {e}")

# ==================== 🔗 CHANNEL SKU MAPPING ====================
elif menu == "🔗 2. CHANNEL SKU Mapping":
  st.markdown(
      "<h1>🔗 Multi-Channel SKU Mapping Engine</h1>", unsafe_allow_html=True
  )

  tab_map1, tab_map2 = st.tabs(["📋 Mapped SKUs", "📁 Bulk Mapping Upload"])

  with tab_map1:
    st.dataframe(df_map, use_container_width=True, hide_index=True)

  with tab_map2:
    map_template = {
        "Seller SKU on Channel": ["AMZ-TSHIRT-RED-M"],
        "SKU Code": ["MSKU-RED-M"],
        "channelName": ["Amazon"],
        "PACK OF": [1],
        "BRAND": ["VIDA LOCA"],
    }
    st.download_button(
        "📥 Download Channel Mapping Template (CSV)",
        data=create_sample_csv(map_template),
        file_name="Channel_Mapping_Template.csv",
        mime="text/csv",
    )

    f_map = st.file_uploader(
        "Upload Mapping File", type=["csv", "xlsx"], key="map_upload"
    )
    if f_map and st.button("🚀 Process Mapping Import"):
      try:
        df_u = (
            pd.read_csv(f_map)
            if f_map.name.endswith(".csv")
            else pd.read_excel(f_map)
        )
        supabase.table("channel_sku_map").insert(
            df_u.to_dict(orient="records")
        ).execute()
        clear_app_cache()
        st.success("Channel Mapping Updated!")
        st.rerun()
      except Exception as e:
        st.error(f"Upload Error: {e}")

# ==================== 📥 3. ADD INVENTORY ====================
elif menu == "📥 3. ADD INVENTORY (Stock Inward)":
  st.markdown(
      "<h1>📥 Stock Inward & Barcode Generator</h1>", unsafe_allow_html=True
  )

  tab1, tab2, tab3 = st.tabs([
      "📸 Auto-Push Scan",
      "🖨️ Bulk Barcode & QR Generator",
      "📁 Bulk Stock Upload",
  ])

  with tab1:
    st.subheader("📷 Auto-Push Stock Inward Scanner")
    raw_code = st.text_input("Focus & Scan Barcode/QR Code")
    if raw_code:
      m_sku = resolve_to_master_sku(raw_code, df_prod, df_map)
      try:
        supabase.table("add_inventory").insert(
            {"product_code": m_sku, "added_qty": 1, "brand": "VIDA LOCA"}
        ).execute()
        clear_app_cache()
        st.toast(f"✅ Inwarded: {m_sku}", icon="🚀")
      except Exception as e:
        st.error(f"Error: {e}")

  with tab2:
    st.subheader("🖨️ Generate Printable Labels")
    p_code_list = (
        sorted(list(df_prod["Product Code"].dropna().unique()))
        if not df_prod.empty
        else []
    )
    selected_skus = st.multiselect("Select SKUs", p_code_list)
    if selected_skus:
      sku_qty_map = {sku: 1 for sku in selected_skus}
      pdf_bytes = generate_codes_pdf(sku_qty_map, code_type="barcode")
      st.download_button(
          "📄 Download PDF Barcodes",
          data=pdf_bytes,
          file_name="Barcodes.pdf",
          mime="application/pdf",
      )

  with tab3:
    inv_template = {
        "product_code": ["MSKU-RED-M"],
        "added_qty": [50],
        "brand": ["VIDA LOCA"],
    }
    st.download_button(
        "📥 Download Inventory Template (CSV)",
        data=create_sample_csv(inv_template),
        file_name="Inventory_Inward_Template.csv",
        mime="text/csv",
    )

    f_inv = st.file_uploader(
        "Upload Stock Inward File", type=["csv", "xlsx"], key="inv_upload"
    )
    if f_inv and st.button("🚀 Process Stock Inward"):
      try:
        df_u = (
            pd.read_csv(f_inv)
            if f_inv.name.endswith(".csv")
            else pd.read_excel(f_inv)
        )
        supabase.table("add_inventory").insert(
            df_u.to_dict(orient="records")
        ).execute()
        clear_app_cache()
        st.success("Stock Added!")
        st.rerun()
      except Exception as e:
        st.error(f"Upload Error: {e}")

# ==================== 📤 4. SALES DATA MANIFEST ====================
elif menu == "📤 4. SALES DATA Manifest":
  st.markdown("<h1>📤 Sales Manifest Engine</h1>", unsafe_allow_html=True)

  tab_s1, tab_s2 = st.tabs(["📸 Scan Sale", "📁 Bulk Sales Upload"])

  with tab_s1:
    raw_s_code = st.text_input("Scan Barcode for Sale")
    if raw_s_code:
      m_sku = resolve_to_master_sku(raw_s_code, df_prod, df_map)
      try:
        supabase.table("sale_data").insert({
            "date": date.today().strftime("%Y-%m-%d"),
            "channel_sku": m_sku,
            "type": "SINGLE",
            "brand": "VIDA LOCA",
            "qty": 1,
        }).execute()
        clear_app_cache()
        st.toast(f"📦 Sale Recorded: {m_sku}", icon="✅")
      except Exception as e:
        st.error(f"Error: {e}")

  with tab_s2:
    sales_template = {
        "date": ["2026-03-31"],
        "channel_sku": ["AMZ-TSHIRT-RED-M"],
        "type": ["SINGLE"],
        "brand": ["VIDA LOCA"],
        "qty": [1],
    }
    st.download_button(
        "📥 Download Sales Upload Template (CSV)",
        data=create_sample_csv(sales_template),
        file_name="Sales_Upload_Template.csv",
        mime="text/csv",
    )

    f_sales = st.file_uploader(
        "Upload Sales Manifest", type=["csv", "xlsx"], key="sales_upload"
    )
    if f_sales and st.button("🚀 Process Sales Import"):
      try:
        df_u = (
            pd.read_csv(f_sales)
            if f_sales.name.endswith(".csv")
            else pd.read_excel(f_sales)
        )
        supabase.table("sale_data").insert(
            df_u.to_dict(orient="records")
        ).execute()
        clear_app_cache()
        st.success("Sales Imported!")
        st.rerun()
      except Exception as e:
        st.error(f"Upload Error: {e}")
