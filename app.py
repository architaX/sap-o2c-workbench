import streamlit as st
import pandas as pd
import datetime

# -----------------------------------------------------------------------------
# PAGE CONFIGURATION & STYLING
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="SAP O2C Credit Release Cockpit",
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    .main-title {
        font-size: 26px;
        font-weight: 700;
        color: #0f3661;
        margin-bottom: 2px;
    }
    .sub-title {
        font-size: 14px;
        color: #555555;
        margin-bottom: 20px;
    }
    .ai-box {
        background-color: #e6f7ff;
        border-left: 4px solid #1890ff;
        padding: 12px 16px;
        border-radius: 4px;
        margin-bottom: 15px;
    }
    </style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# DATA LOADING & SESSION STATE
# -----------------------------------------------------------------------------
@st.cache_data
def load_data():
    return pd.read_csv("data/sales_orders.csv")

if "df" not in st.session_state:
    st.session_state.df = load_data()

if "audit_trail" not in st.session_state:
    st.session_state.audit_trail = []

df = st.session_state.df

# -----------------------------------------------------------------------------
# GROUNDED AI ENGINE (STRICT RULE-BASED / NO HALLUCINATIONS)
# -----------------------------------------------------------------------------
def get_grounded_ai_insight(order):
    credit_limit = float(order["credit_limit"])
    current_exposure = float(order["current_exposure"])
    order_value = float(order["order_value"])
    new_exposure = current_exposure + order_value
    overage = new_exposure - credit_limit
    overdue = int(order["overdue_days"])

    if overage > 0 and overdue > 30:
        tag = "🔴 HIGH RISK: LIMIT BREACH & OVERDUE RECEIVABLES"
        explanation = (
            f"Releasing {order['sales_order_id']} causes an exposure overage of ${overage:,.2f} "
            f"(Total: ${new_exposure:,.2f} vs Limit: ${credit_limit:,.2f}) with {overdue} overdue days."
        )
    elif overage > 0:
        tag = "🟠 MEDIUM RISK: CREDIT LIMIT EXCEEDED"
        explanation = (
            f"Releasing {order['sales_order_id']} exceeds credit limit by ${overage:,.2f} "
            f"(Limit: ${credit_limit:,.2f}, Post-Release Exposure: ${new_exposure:,.2f})."
        )
    elif overdue > 30:
        tag = "🟠 MEDIUM RISK: CHRONIC OVERDUE RECEIVABLES"
        explanation = (
            f"Order is within limit (Post-Release Exposure: ${new_exposure:,.2f} / ${credit_limit:,.2f}), "
            f"but customer has open receivables overdue by {overdue} days."
        )
    else:
        tag = "🟢 LOW RISK: WITHIN EXPOSURE LIMITS"
        explanation = (
            f"Order value of ${order_value:,.2f} is within limit "
            f"(Total post-release exposure ${new_exposure:,.2f} <= limit ${credit_limit:,.2f}) with {overdue} overdue days."
        )
    return tag, explanation

# -----------------------------------------------------------------------------
# HEADER & EXECUTIVE METRICS
# -----------------------------------------------------------------------------
st.markdown('<p class="main-title">SAP Order-to-Cash (O2C) Credit Release Cockpit</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Live VKM1 / VA01 Blocked Order Management Workbench | SAP SD-BF-CM</p>', unsafe_allow_html=True)

# Calculate live metrics
blocked_orders = df[df["status"] == "CREDIT_BLOCK"]
blocked_value = (blocked_orders["current_exposure"] + blocked_orders["order_value"]).sum()

m1, m2, m3, m4 = st.columns(4)

with m1:
    st.metric(label="Days Sales Outstanding (DSO)", value="28 Days", delta="-14 Days Target")

with m2:
    st.metric(label="Total Blocked Queue Value", value=f"${blocked_value:,.2f}", delta=f"{len(blocked_orders)} Orders Pending")

with m3:
    st.metric(label="On-Time In-Full (OTIF) Rate", value="94.2%", delta="+4.1% vs Benchmark")

with m4:
    st.metric(label="Avg Release Lead Time", value="15 Mins", delta="-8.7 Hours")

st.divider()

# -----------------------------------------------------------------------------
# QUEUE TABLE & STATUS FILTER
# -----------------------------------------------------------------------------
st.subheader("1. VKM1 Blocked Sales Orders Queue")

col_filter, _ = st.columns([1, 3])
with col_filter:
    status_filter = st.selectbox("Filter Status Queue", options=["CREDIT_BLOCK", "RELEASED", "ALL"])

if status_filter != "ALL":
    filtered_df = df[df["status"] == status_filter].copy()
else:
    filtered_df = df.copy()

# Render Interactive Dataframe
filtered_df["post_exposure"] = filtered_df["current_exposure"] + filtered_df["order_value"]
filtered_df["limit_utilization_%"] = ((filtered_df["post_exposure"] / filtered_df["credit_limit"]) * 100).round(1)

st.dataframe(
    filtered_df[[
        "sales_order_id", "bp_id", "customer_name", "risk_category",
        "credit_limit", "current_exposure", "order_value", "post_exposure",
        "limit_utilization_%", "overdue_days", "status"
    ]],
    column_config={
        "sales_order_id": "Sales Order #",
        "bp_id": "Business Partner",
        "customer_name": "Customer Name",
        "risk_category": "Risk Tier",
        "credit_limit": st.column_config.NumberColumn("Credit Limit ($)", format="$%d"),
        "current_exposure": st.column_config.NumberColumn("Current Exposure ($)", format="$%d"),
        "order_value": st.column_config.NumberColumn("Order Value ($)", format="$%d"),
        "post_exposure": st.column_config.NumberColumn("Post-Release ($)", format="$%d"),
        "limit_utilization_%": st.column_config.ProgressColumn("Post Utilization %", format="%d%%", min_value=0, max_value=200),
        "overdue_days": "Overdue (Days)",
        "status": "SAP Status"
    },
    use_container_width=True,
    hide_index=True
)

st.divider()

# -----------------------------------------------------------------------------
# DECISION WORKBENCH
# -----------------------------------------------------------------------------
st.subheader("2. Credit Decision Workbench")

selectable_orders = filtered_df["sales_order_id"].tolist()

if not selectable_orders:
    st.info("No orders available in the selected queue status view.")
else:
    selected_so_id = st.selectbox("Select Sales Order to Process:", options=selectable_orders)
    order_data = df[df["sales_order_id"] == selected_so_id].iloc[0]

    # Calculate Exposure Math
    c_limit = float(order_data["credit_limit"])
    c_exp = float(order_data["current_exposure"])
    o_val = float(order_data["order_value"])
    post_exp = c_exp + o_val
    overage = post_exp - c_limit
    has_overage = overage > 0

    # Grounded AI Insight
    ai_tag, ai_explanation = get_grounded_ai_insight(order_data)

    st.markdown(f"""
        <div class="ai-box">
            <b>{ai_tag}</b><br/>
            <span>{ai_explanation}</span>
        </div>
    """, unsafe_allow_html=True)

    col_details, col_exposure = st.columns(2)

    with col_details:
        st.markdown("##### Customer & Order Metadata")
        st.write(f"**Sales Document ID:** `{order_data['sales_order_id']}`")
        st.write(f"**Business Partner ID:** `{order_data['bp_id']}`")
        st.write(f"**Customer Name:** {order_data['customer_name']}")
        st.write(f"**Payment Terms:** {order_data['payment_terms']}")
        st.write(f"**Risk Category:** {order_data['risk_category']}")
        st.write(f"**Overdue Days:** {order_data['overdue_days']} Days")
        st.write(f"**Current SAP Status:** `{order_data['status']}`")

    with col_exposure:
        st.markdown("##### Exposure Breach Math Engine")
        st.write(f"**Credit Limit:** ${c_limit:,.2f}")
        st.write(f"**Current Exposure:** ${c_exp:,.2f}")
        st.write(f"**Order Value (VA01):** ${o_val:,.2f}")
        st.markdown(f"**Projected Exposure:** `${post_exp:,.2f}`")

        if has_overage:
            st.error(f"⚠️ **Credit Breach Overage:** +${overage:,.2f} above approved limit!")
        else:
            st.success(f"✅ **Within Credit Boundary:** ${abs(overage):,.2f} cushion remaining.")

    st.markdown("---")
    st.markdown("##### Governance & Action Approval")

    passcode_input = ""
    if has_overage and order_data["status"] == "CREDIT_BLOCK":
        st.warning("🔒 **Hard Business Guardrail Active:** Order breaches credit limit. Manager Passcode is strictly required to authorize release.")
        passcode_input = st.text_input("Enter Manager Authorization Passcode:", type="password", help="Passcode required for credit breaches. Default: SAP2026")

    audit_notes = st.text_area("Audit Notes / Business Justification:", placeholder="Provide business justification for credit release or rejection...")

    btn_release, btn_reject = st.columns(2)

    with btn_release:
        if st.button("RELEASE CREDIT BLOCK", type="primary", use_container_width=True, disabled=(order_data["status"] == "RELEASED")):
            if order_data["status"] == "RELEASED":
                st.info("This order is already released.")
            elif has_overage and passcode_input != "SAP2026":
                st.error("🚨 **RELEASE REJECTED:** Valid Manager Passcode ('SAP2026') is strictly required to override credit limit breaches!")
            else:
                idx = df[df["sales_order_id"] == selected_so_id].index[0]
                st.session_state.df.at[idx, "status"] = "RELEASED"
                
                st.session_state.audit_trail.append({
                    "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "sales_order_id": selected_so_id,
                    "customer_name": order_data["customer_name"],
                    "action": "RELEASED",
                    "overage": max(0.0, overage),
                    "notes": audit_notes if audit_notes else "Approved via Workbench"
                })
                st.success(f"Order {selected_so_id} successfully RELEASED in SAP SD!")
                st.rerun()

    with btn_reject:
        if st.button("REJECT SALES ORDER", use_container_width=True, disabled=(order_data["status"] == "RELEASED")):
            idx = df[df["sales_order_id"] == selected_so_id].index[0]
            st.session_state.df.at[idx, "status"] = "REJECTED"
            
            st.session_state.audit_trail.append({
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "sales_order_id": selected_so_id,
                "customer_name": order_data["customer_name"],
                "action": "REJECTED",
                "overage": max(0.0, overage),
                "notes": audit_notes if audit_notes else "Rejected during review"
            })
            st.error(f"Order {selected_so_id} REJECTED.")
            st.rerun()

# -----------------------------------------------------------------------------
# AUDIT TRAIL LOG
# -----------------------------------------------------------------------------
if st.session_state.audit_trail:
    st.divider()
    st.subheader("3. Governance Audit Log")
    st.dataframe(pd.DataFrame(st.session_state.audit_trail), use_container_width=True, hide_index=True)