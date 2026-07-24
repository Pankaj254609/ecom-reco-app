import io
import os
import pandas as pd
import plotly.express as px
import streamlit as st
from supabase import Client, create_client

# --- Page Setup & Modern CSS Styling ---
st.set_page_config(
    page_title="Learnwell Reconcile Pro | E-commerce Intelligence",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    /* Dark Slate Theme Setup */
    .stApp { background-color: #0f172a; color: #f8fafc; }
    
    /* Card Design */
    .metric-card {
        background: #1e293b;
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #334155;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
    }
    .metric-title { font-size: 13px; color: #94a3b8; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }
    .metric-value { font-size: 26px; color: #f8fafc; font-weight: 700; margin-top: 8px; }
    .metric-sub { font-size: 12px; font-weight: 500; margin-top: 4px; }
    
    .status-ok { color: #10b981; }
    .status-alert { color: #ef4444; }
    
    /* Sidebar Styling */
    [data-testid="stSidebar"] { background-color: #0b0f19 !important; border-right: 1px solid #1e293b; }
    </style>
""",
    unsafe_allow_html=True,
)


# --- Template Generator Helper ---
def generate_sample_file(file_type):
  if file_type == "settlement":
    data = {
        "order_id": [
            "OD99102931201",
            "OD99102931202",
            "OD99102931203",
            "OD99102931204",
        ],
        "channel": ["Flipkart", "Amazon", "Meesho", "Myntra"],
        "gross_sales": [1299.0, 799.0, 450.0, 1599.0],
        "commission_fee": [130.0, 80.0, 0.0, 240.0],
        "fixed_fee": [35.0, 25.0, 15.0, 40.0],
        "logistics_fee": [75.0, 60.0, 45.0, 90.0],
        "bank_payout": [1059.0, 634.0, 390.0, 1229.0],
        "settlement_date": [
            "2026-03-01",
            "2026-03-01",
            "2026-03-02",
            "2026-03-02",
        ],
  }
  else:
    data = {
        "order_id": ["OD99102931201", "OD99102931202"],
        "return_type": ["Customer Return", "RTO"],
        "claim_status": ["Pending", "Approved"],
        "claimed_amount": [450.0, 150.0],
        "approved_amount": [0.0, 150.0],
    }

  df = pd.DataFrame(data)
  buffer = io.BytesIO()
  with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
    df.to_excel(writer, index=False, sheet_name="Data")
  buffer.seek(0)
  return buffer


# --- Sidebar Setup ---
st.sidebar.markdown(
    "<h2 style='color:#38bdf8;'>⚡ Reconcile Pro</h2>", unsafe_allow_html=True
)
st.sidebar.caption("Enterprise E-commerce Financial Engine")

menu = st.sidebar.radio(
    "NAVIGATION",
    [
        "📊 Executive Financial Dashboard",
        "⚖️ Order Level Reconciliation Audit",
        "📥 Bulk Reports & Template Hub",
    ],
)

# ==================== 1. EXECUTIVE DASHBOARD ====================
if menu == "📊 Executive Financial Dashboard":
  st.title("📊 Executive Profitability & Audit Summary")

  # Filter Header
  c_col1, c_col2, c_col3 = st.columns(3)
  with c_col1:
    selected_portal = st.multiselect(
        "Select Channels",
        ["Amazon", "Flipkart", "Meesho", "Myntra", "Snapdeal"],
        default=["Amazon", "Flipkart"],
    )

  st.write("---")

  # Core KPI Cards
  k1, k2, k3, k4 = st.columns(4)

  with k1:
    st.markdown(
        """
        <div class="metric-card">
            <div class="metric-title">Gross Sales Value</div>
            <div class="metric-value">₹ 14,85,200</div>
            <div class="metric-sub status-ok">↑ 12% vs last month</div>
        </div>
    """,
        unsafe_allow_html=True,
    )

  with k2:
    st.markdown(
        """
        <div class="metric-card">
            <div class="metric-title">Net Bank Settled</div>
            <div class="metric-value">₹ 11,42,100</div>
            <div class="metric-sub status-ok">76.9% Realization Rate</div>
        </div>
    """,
        unsafe_allow_html=True,
    )

  with k3:
    st.markdown(
        """
        <div class="metric-card">
            <div class="metric-title">Marketplace Charges</div>
            <div class="metric-value">₹ 2,98,400</div>
            <div class="metric-sub status-alert">Comm + Shipping + Fixed</div>
        </div>
    """,
        unsafe_allow_html=True,
    )

  with k4:
    st.markdown(
        """
        <div class="metric-card">
            <div class="metric-title">Discrepancy / Overcharge</div>
            <div class="metric-value status-alert">₹ 44,700</div>
            <div class="metric-sub status-alert">⚠️ Action Needed (32 Orders)</div>
        </div>
    """,
        unsafe_allow_html=True,
    )

  st.write("---")

  # Visualizations
  col_chart1, col_chart2 = st.columns(2)

  chart_data = pd.DataFrame({
      "Channel": ["Amazon", "Flipkart", "Meesho", "Myntra"],
      "Gross Sales": [650000, 520000, 180000, 135200],
      "Net Settled": [510000, 390000, 145000, 97100],
  })

  with col_chart1:
    st.subheader("Payout Realization per Channel")
    fig1 = px.bar(
        chart_data,
        x="Channel",
        y=["Gross Sales", "Net Settled"],
        barmode="group",
        color_discrete_sequence=["#38bdf8", "#10b981"],
        template="plotly_dark",
    )
    st.plotly_chart(fig1, use_container_width=True)

  with col_chart2:
    st.subheader("Deduction Breakup")
    deductions = pd.DataFrame({
        "Category": ["Commission", "Shipping/Weight", "Fixed Fee", "Returns"],
        "Amount": [140000, 85000, 38000, 35400],
    })
    fig2 = px.pie(
        deductions,
        values="Amount",
        names="Category",
        color_discrete_sequence=px.colors.sequential.Darkmint,
        template="plotly_dark",
    )
    st.plotly_chart(fig2, use_container_width=True)

# ==================== 2. RECONCILIATION AUDIT ====================
elif menu == "⚖️ Order Level Reconciliation Audit":
  st.title("⚖️ Order Level Discrepancy Finder")

  st.info(
      "💡 **Algorithm Output:** System ne Marketplace Charges vs Agreement rate"
      " ko compare karke overcharges flag kiye hain."
  )

  audit_df = pd.DataFrame({
      "Order ID": [
          "OD99102931201",
          "OD99102931202",
          "OD99102931203",
          "OD99102931204",
      ],
      "Channel": ["Flipkart", "Amazon", "Meesho", "Flipkart"],
      "Expected Payout": [1120.0, 680.0, 390.0, 850.0],
      "Actual Settled": [1059.0, 680.0, 390.0, 720.0],
      "Discrepancy": [-61.0, 0.0, 0.0, -130.0],
      "Discrepancy Reason": [
          "Weight Excess Penalty Charged",
          "Perfectly Reconciled",
          "Perfectly Reconciled",
          "Commission Rate Higher Than Agreed",
      ],
  })

  st.dataframe(
      audit_df,
      use_container_width=True,
      hide_index=True,
  )

# ==================== 3. TEMPLATES & BULK UPLOADS ====================
elif menu == "📥 Bulk Reports & Template Hub":
  st.title("📥 System Templates & Bulk Integration")

  t1, t2 = st.columns(2)

  with t1:
    st.subheader("1. Download Standard Data Templates")
    st.download_button(
        "📄 Download Payment Settlement Template (.xlsx)",
        data=generate_sample_file("settlement"),
        file_name="Settlement_Template.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

  with t2:
    st.subheader("2. Upload Settlement Manifest")
    st.file_uploader(
        "Upload CSV or Excel file", type=["csv", "xlsx"], key="bulk_audit_file"
    )
