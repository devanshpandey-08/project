import streamlit as st
import sys
import os

# Add workspace to path
sys.path.insert(0, '/workspace')

from examples.financial_compliance_assistant import (
    LoanApplication, 
    FinancialComplianceFlow,
    RiskLevel
)

st.set_page_config(page_title="Loan Approval Dashboard", layout="wide")

st.title("🏦 Financial Compliance Assistant")
st.markdown("Real-time loan approval workflow with AI risk assessment and manager overrides.")

# Initialize session state
if 'flow' not in st.session_state:
    st.session_state.flow = FinancialComplianceFlow()
if 'applications' not in st.session_state:
    st.session_state.applications = []

# Sidebar: New Application Form
with st.sidebar:
    st.header("New Loan Application")
    with st.form("loan_form"):
        name = st.text_input("Full Name")
        email = st.text_input("Email")
        phone = st.text_input("Phone")
        ssn = st.text_input("SSN")
        income = st.number_input("Annual Income ($)", min_value=0, step=1000)
        debt = st.number_input("Monthly Debt ($)", min_value=0, step=100)
        loan_amount = st.number_input("Loan Amount ($)", min_value=1000, step=1000)
        loan_term = st.selectbox("Term (Months)", [12, 24, 36, 48, 60])
        credit_score = st.slider("Credit Score", 300, 850, 650)
        employment_years = st.slider("Years Employed", 0, 30, 2)
        
        submitted = st.form_submit_button("Submit Application")
        
        if submitted:
            app = LoanApplication(
                applicant_name=name,
                email=email,
                phone=phone,
                ssn=ssn,
                annual_income=income,
                monthly_debt=debt,
                loan_amount=loan_amount,
                loan_term_months=loan_term,
                credit_score=credit_score,
                employment_years=employment_years
            )
            st.session_state.applications.append(app)
            st.success("Application submitted for processing!")

# Main Area: Processing & Approvals
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("Pending Approvals")
    if not st.session_state.applications:
        st.info("No applications submitted yet. Use the sidebar to add one.")
    else:
        for i, app in enumerate(st.session_state.applications):
            with st.expander(f"Application: {app.applicant_name} (${app.loan_amount:,})", expanded=True):
                # Run the flow for this application
                try:
                    result = st.session_state.flow.process_application(app)
                    
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Risk Score", f"{result['risk_score']}/100")
                    c2.metric("Risk Level", result['risk_level'])
                    c3.metric("Decision", result['decision'])
                    
                    st.json({
                        "interest_rate": result.get('interest_rate'),
                        "monthly_payment": result.get('monthly_payment'),
                        "requires_approval": result.get('requires_manual_review'),
                        "redacted_pii": result.get('redacted_info', {})
                    })
                    
                    # Human-in-the-loop Action
                    if result.get('requires_manual_review'):
                        st.warning("⚠️ Manager Review Required")
                        c_act1, c_act2 = st.columns(2)
                        if c_act1.button("✅ Approve", key=f"approve_{i}"):
                            st.success("Manager approved loan.")
                        if c_act2.button("❌ Reject", key=f"reject_{i}"):
                            st.error("Manager rejected loan.")
                            
                except Exception as e:
                    st.error(f"Processing error: {str(e)}")

with col2:
    st.subheader("System Status")
    st.metric("Total Processed", len(st.session_state.applications))
    st.metric("PII Redactions", "Active")
    st.metric("Audit Mode", "Enabled")
    
    st.markdown("### How it works")
    st.markdown("""
    1. **Input**: User enters loan details.
    2. **AI Analysis**: System calculates risk based on credit, DTI, and employment.
    3. **PII Protection**: Sensitive data is automatically redacted.
    4. **Decision**: 
       - Low Risk → Auto Approved
       - High Risk → Sent to Manager (You!)
    """)
