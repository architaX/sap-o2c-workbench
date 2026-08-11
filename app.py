import streamlit as st
import pandas as pd
import datetime

# -----------------------------------------------------------------------------
# 1. PAGE CONFIGURATION & STYLING
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="SAP O2C Credit Management Workbench",
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling for SAP Fiori-like visual hierarchy
st.markdown("""
    <style>
    .main-header { font-size: 24px; font-weight: bold; color: #0f3661; margin-bottom: 0px; }
    .sub-header { font-size: 14px; color: #555; margin-bottom: 20px; }
    .kpi-card { background-color: #f8f9fa; border-left: 4px solid #0f3661; padding: 10px 15px; border-radius: 4px; }
    .status-hold { color: #d9534f; font-weight: bold; }
    .status-released { color: #5cb85c; font-weight: bold; }
    .status-rejected { color: #f0ad4e; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. DATA LOADING & STATE MANAGEMENT
# -----------------------------------------------------------------------------
@st.cache_data
def load_initial_data():
    try:
        df = pd.read_csv("data/sales_orders.csv", dtype={"sales_order": str, "customer_id": str})
    except FileNotFoundError:
        # Fallback mock data if CSV is not yet uploaded
        data = {
            "sales_order": ["0090010482", "0090010483", "0090010484", "0090010485", "0090010486"],
            "customer_id": ["100293", "100411", "100852", "100105", "100334"],
            "customer_name": ["Acme Corp", "Globex Ltd", "Stark Industries", "Wayne Enterprises", "Umbrella Corp"],
            "order_value": [45000, 12500, 88000, 150000, 32000],
            "credit_limit": [100000, 50000, 200000, 300000, 40000],
            "current_exposure": [115000, 46000, 216000, 280000, 48000],
            "risk_class": ["B", "A", "C", "A", "C"],
            "block_reason": ["01 - Credit Limit Exceeded", "01 - Credit Limit Exceeded", "02 - Overdue Open Items", "01 - Credit Limit Exceeded", "03 - Oldest Open Item"],
            "status": ["HOLD", "HOLD", "HOLD", "HOLD", "HOLD"],
            "dso": [42, 28, 65, 31, 58],
            "open_receivables": [70000, 33500, 128000, 130000, 16000]
        }
        df = pd.DataFrame(data)
    
    if "dso" not in df.columns:
        df["dso"] = [42, 28, 65, 31, 58][:len(df)]
    if "open_receivables" not in df.columns:
        df["open_receivables"] = (df["current_exposure"] - df["order_value"]).clip(lower=0)
        
    return df

if "orders_df" not in st.session_state:
    st.session_state.orders_df = load_initial_data()

if "audit_log" not in st.session_state:
    st.session_state.audit_log = []

df = st.session_state.orders_df

# -----------------------------------------------------------------------------
# 3. HEADER & TOP KPI BANNER
# -----------------------------------------------------------------------------
st.markdown('<p class="main-header">SAP Order-to-Cash (O2C) Credit Management Workbench</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">VKM1 Blocked Sales Orders Release & Decision Console | SAP SD-BF-CM</p>', unsafe_allow_html=True)

# KPI Calculations
total_blocked = len(df[df["status"] == "HOLD"])
released_count = len(df[df["status"] == "RELEASED"])
at_risk_exposure = df[df["status"] == "HOLD"]["current_exposure"].sum()

col_kpi1, col_kpi2, col_kpi3 = st.columns(3)

with col_kpi1:
    st.metric(
        label="Avg Order Release Lead Time",
        value="2.1 Hours",
        delta="-22.4 hrs (Target: 91% Reduction)"
    )

with col_kpi2:
    st.metric(
        label="Pending VKM1 Block Queue",
        value=f"{total_blocked} Orders",
        delta=f"{released_count} Processed Today"
    )

with col_kpi3:
    st.metric(
        label="At-Risk Credit Exposure",
        value=f"${at_risk_exposure:,.2f}",
        delta="-82% Target",
        delta_color="inverse"
    )

st.divider()

# -----------------------------------------------------------------------------
# 4. SIDEBAR FILTERS & CONTROLS
# -----------------------------------------------------------------------------
st.sidebar.header("VKM1 Queue Filters")

risk_filter = st.sidebar.multiselect(
    "Filter by Risk Class (KNKK-CTLPC)",
    options=sorted(df["risk_class"].unique()),
    default=sorted(df["risk_class"].unique())
)

block_filter = st.sidebar.multiselect(
    "Filter by Credit Block Reason",
    options=sorted(df["block_reason"].unique()),
    default=sorted(df["block_reason"].unique())
)

search_so = st.sidebar.text_input("Search Sales Order # (VBAK-VBELN)", "")

# Apply Filters
filtered_df = df[
    (df["risk_class"].isin(risk_filter)) &
    (df["block_reason"].isin(block_filter))
]

if search_so:
    filtered_df = filtered_df[filtered_df["sales_order"].str.contains(search_so, case=False)]

# -----------------------------------------------------------------------------
# 5. BLOCKED SALES ORDER QUEUE (TABLE)
# -----------------------------------------------------------------------------
st.subheader("1. Blocked Sales Orders Queue (VKM1 Monitor)")

# Calculate Credit Exposure Percentage for visualization
filtered_df_display = filtered_df.copy()
filtered_df_display["Exposure %"] = (filtered_df_display["current_exposure"] / filtered_df_display["credit_limit"] * 100).round(1)

st.dataframe(
    filtered_df_display[[
        "sales_order", "customer_id", "customer_name", "risk_class", 
        "order_value", "credit_limit", "current_exposure", "Exposure %", 
        "block_reason", "status"
    ]],
    column_config={
        "sales_order": "Sales Doc (VBAK)",
        "customer_id": "Customer (KNA1)",
        "customer_name": "Customer Name",
        "risk_class": "Risk Class",
        "order_value": st.column_config.NumberColumn("Order Value ($)", format="$%d"),
        "credit_limit": st.column_config.NumberColumn("Credit Limit ($)", format="$%d"),
        "current_exposure": st.column_config.NumberColumn("Total Exposure ($)", format="$%d"),
        "Exposure %": st.column_config.ProgressColumn("Limit Utilization", format="%d%%", min_value=0, max_value=200),
        "block_reason": "Block Reason",
        "status": "Release Status"
    },
    use_container_width=True,
    hide_index=True
)

# -----------------------------------------------------------------------------
# 6. DECISION WORKBENCH (DETAIL & ACTION PANEL)
# -----------------------------------------------------------------------------
st.divider()
st.subheader("2. Credit Decision Workbench")

# Single Order Selection for Deep Analysis
pending_orders = filtered_df[filtered_df["status"] == "HOLD"]["sales_order"].tolist()

if not pending_orders:
    st.success("All sales orders in the current queue view have been reviewed and processed!")
else:
    selected_so = st.selectbox(
        "Select Sales Order for Deep Credit Evaluation:",
        options=pending_orders
    )

    order_row = df[df["sales_order"] == selected_so].iloc[0]

    # Two-Column Layout for SAP Master & Transactional Analysis
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("##### Customer Risk & Account Profile (KNA1 / KNKK)")
        st.write(f"**Customer Name:** {order_row['customer_name']} (`ID: {order_row['customer_id']}`)")
        st.write(f"**Risk Category:** Class {order_row['risk_class']}")
        st.write(f"**Days Sales Outstanding (DSO):** {order_row['dso']} Days")
        st.write(f"**Current Credit Block Reason:** `{order_row['block_reason']}`")

    with col_right:
        st.markdown("##### Financial Exposure Breakdown (UKM_ITEM)")
        st.write(f"**Approved Credit Limit:** ${order_row['credit_limit']:,}")
        st.write(f"**Open Receivables Balance:** ${order_row['open_receivables']:,}")
        st.write(f"**Current Order Value (VA01):** ${order_row['order_value']:,}")
        
        excess = order_row['current_exposure'] - order_row['credit_limit']
        if excess > 0:
            st.error(f"**Credit Limit Excess Violation:** ${excess:,}")
        else:
            st.info("**Credit Limit Excess Violation:** $0 (Within Limit)")

    st.markdown("---")
    st.markdown("##### Manager Decision & Audit Protocol")
    
    audit_notes = st.text_area(
        "Release Justification / Audit Log Notes (Required for SAP Governance):",
        placeholder="Enter risk justification, payment agreement details, or approval override notes..."
    )

    btn_col1, btn_col2, btn_col3 = st.columns(3)

    with btn_col1:
        if st.button("RELEASE ORDER (VA01 Unblock)", type="primary", use_container_width=True):
            if not audit_notes.strip():
                st.warning("Please provide a release justification in the audit notes field.")
            else:
                idx = df[df["sales_order"] == selected_so].index[0]
                st.session_state.orders_df.at[idx, "status"] = "RELEASED"
                st.session_state.audit_log.append({
                    "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "sales_order": selected_so,
                    "action": "RELEASED",
                    "user": "Credit Manager",
                    "notes": audit_notes
                })
                st.success(f"Sales Order {selected_so} successfully RELEASED in SAP SD!")
                st.rerun()

    with btn_col2:
        if st.button("REJECT ORDER (Cancel Document)", use_container_width=True):
            if not audit_notes.strip():
                st.warning("Please provide a rejection reason in the audit notes field.")
            else:
                idx = df[df["sales_order"] == selected_so].index[0]
                st.session_state.orders_df.at[idx, "status"] = "REJECTED"
                st.session_state.audit_log.append({
                    "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "sales_order": selected_so,
                    "action": "REJECTED",
                    "user": "Credit Manager",
                    "notes": audit_notes
                })
                st.error(f"Sales Order {selected_so} REJECTED.")
                st.rerun()

    with btn_col3:
        if st.button("TEMP LIMIT INCREASE (+15%)", use_container_width=True):
            idx = df[df["sales_order"] == selected_so].index[0]
            st.session_state.orders_df.at[idx, "credit_limit"] = int(st.session_state.orders_df.at[idx, "credit_limit"] * 1.15)
            st.info(f"Temporary credit limit increased for Customer {order_row['customer_id']}.")
            st.rerun()

# -----------------------------------------------------------------------------
# 7. AUDIT TRAIL LOG
# -----------------------------------------------------------------------------
if st.session_state.audit_log:
    st.divider()
    st.subheader("3. Governance Audit Trail (SAP Change History)")
    st.dataframe(pd.DataFrame(st.session_state.audit_log), use_container_width=True, hide_index=True)