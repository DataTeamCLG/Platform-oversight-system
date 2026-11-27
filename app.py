import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import unicodedata
import smtplib

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


# ==================================================
# CONFIG
# ==================================================

st.set_page_config(
    page_title="Time Control Platform",
    page_icon="⏱️",
    layout="wide",
)

MINIMUM_DAILY_HOURS = 8


# ==================================================
# FUNCTIONS
# ==================================================

def send_test_email(recipient, subject, body):
    try:
        smtp_server = st.secrets["SMTP_SERVER"]
        smtp_port = int(st.secrets["SMTP_PORT"])

        smtp_user = st.secrets["SMTP_USER"]
        smtp_password = st.secrets["SMTP_PASSWORD"]

        msg = MIMEMultipart()

        msg["From"] = smtp_user
        msg["To"] = recipient
        msg["Subject"] = subject

        msg.attach(MIMEText(body, "html"))

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(msg)
        server.quit()

        return True, "Email sent successfully"

    except Exception as e:
        return False, str(e)


def normalize_name(text):
    if pd.isna(text):
        return ""
    text = str(text).strip().upper()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = " ".join(text.split())
    return text


def build_user_mapping(df_names):
    mappings = []
    source_columns = ["NAME TG", "NAME CL", "NAME SB"]

    for _, row in df_names.iterrows():
        correct_name = row.get("NAME CORRECT")
        if pd.isna(correct_name):
            continue
        for col in source_columns:
            source_name = row.get(col)
            if pd.notna(source_name):
                mappings.append(
                    {
                        "SOURCE_NAME": normalize_name(source_name),
                        "NAME_CORRECT": correct_name,
                    }
                )

    if len(mappings) == 0:
        return {}

    map_df = pd.DataFrame(mappings)
    return dict(zip(map_df["SOURCE_NAME"], map_df["NAME_CORRECT"]))


def convert_duration_to_hours(duration):
    try:
        td = pd.to_timedelta(str(duration))
        return round(td.total_seconds() / 3600, 4)
    except Exception:
        return 0


def get_novelty_status(user, target_date, df_novelties):
    result = df_novelties[
        (df_novelties["Persona"] == user)
        & (df_novelties["Fecha Inicio"] <= target_date)
        & (df_novelties["Fecha Fin"] >= target_date)
    ]
    if len(result) > 0:
        return result.iloc[0]["Tipo de Novedad"]
    return None


def generate_email_html(
    employee_name,
    compliance_df,
    attendance_df,
    start_date,
    end_date,
):
    """
    Genera el HTML corporativo del correo a partir de los DataFrames
    de compliance y attendance ya filtrados por empleado.
    """

    # -------- Helpers internos --------
    def _status_class(status):
        s = str(status).lower()
        if "insuficiente" in s or "no registró" in s or "review" in s:
            return "status-warning"
        return "status-success"

    def _status_badge(status):
        return f'<span class="{_status_class(status)}">{status}</span>'

    # -------- Compliance rows --------
    compliance_rows = ""
    for _, row in compliance_df.iterrows():
        compliance_rows += f"""
        <tr>
            <td>{row['Date']}</td>
            <td class="num">{float(row['Hours Required']):.2f}</td>
            <td class="num">{float(row['Hours Worked']):.2f}</td>
            <td>{_status_badge(row['Status'])}</td>
        </tr>
        """

    # -------- Attendance rows --------
    attendance_rows = ""
    for _, row in attendance_df.iterrows():
        diff = row.get("Difference_Hours", 0)
        try:
            diff_val = float(diff) if pd.notna(diff) else 0.0
        except Exception:
            diff_val = 0.0
        attendance_rows += f"""
        <tr>
            <td>{row['Date']}</td>
            <td class="num">{float(row['Platform_Hours']):.2f}</td>
            <td class="num">{float(row['Attendance_Hours']):.2f}</td>
            <td class="num diff">{diff_val:.2f}</td>
            <td>{_status_badge(row['Status'])}</td>
        </tr>
        """

    # -------- KPIs --------
    total_incidents = len(compliance_df) + len(attendance_df)

    compliance_block = ""
    if compliance_rows:
        compliance_block = f"""
        <div class="sub-block">
            <div class="sub-title">📋 Compliance Incidents</div>
            <div class="table-wrap">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th class="num">Required</th>
                            <th class="num">Reported</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>{compliance_rows}</tbody>
                </table>
            </div>
        </div>
        """

    attendance_block = ""
    if attendance_rows:
        attendance_block = f"""
        <div class="sub-block">
            <div class="sub-title">🔄 Platform vs Attendance</div>
            <div class="table-wrap">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th class="num">Platform</th>
                            <th class="num">Attendance</th>
                            <th class="num">Difference</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>{attendance_rows}</tbody>
                </table>
            </div>
        </div>
        """

    # -------- HTML final (mismo template corporativo) --------
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Time Control Platform - Incident Report</title>
    <style>
        * {{ margin:0; padding:0; box-sizing:border-box; }}
        body {{
            font-family: 'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif;
            background-color:#eef2f6;
            line-height:1.5;
            color:#1a2a3a;
            padding:32px 20px;
        }}
        .email-container {{
            max-width:1100px;
            margin:0 auto;
            background:#ffffff;
            border-radius:14px;
            overflow:hidden;
            box-shadow:0 6px 24px rgba(15,35,60,0.10);
        }}
        .email-header {{
            background:linear-gradient(135deg,#1a3a5c 0%,#2a5a8c 100%);
            color:#ffffff;
            padding:32px 40px 28px 40px;
        }}
        .logo {{ font-size:24px; font-weight:700; letter-spacing:-0.3px; }}
        .logo span {{ font-weight:400; opacity:0.85; }}
        .report-subtitle {{ font-size:14px; opacity:0.85; margin-top:6px; }}
        .header-meta {{
            margin-top:18px; display:flex; gap:28px; flex-wrap:wrap; font-size:12px;
        }}
        .header-meta div {{ display:flex; align-items:baseline; gap:6px; }}
        .header-meta .k {{ text-transform:uppercase; letter-spacing:0.8px; opacity:0.75; font-size:11px; }}
        .header-meta .v {{ font-weight:600; font-size:13px; }}

        .greeting {{
            padding:28px 40px; background:#f8fafc; border-bottom:1px solid #e2e8f0;
        }}
        .greeting h2 {{ font-size:20px; font-weight:600; margin-bottom:10px; }}
        .greeting p {{ font-size:14px; color:#3f5a78; line-height:1.65; margin-bottom:8px; }}
        .greeting .highlight {{ font-weight:600; color:#1a2a3a; }}

        .kpi-row {{
            display:flex; gap:16px; padding:24px 40px; background:#ffffff;
            border-bottom:1px solid #e2e8f0; flex-wrap:wrap;
        }}
        .kpi-card {{
            flex:1; min-width:160px; background:#f0f4f8; border:1px solid #dbe3ee;
            border-radius:10px; padding:16px 18px;
        }}
        .kpi-value {{ font-size:26px; font-weight:700; color:#1a3a5c; }}
        .kpi-label {{
            font-size:11px; text-transform:uppercase; letter-spacing:0.8px;
            color:#6a7e9e; margin-top:4px; font-weight:600;
        }}

        .employee-section {{ padding:24px 40px 8px 40px; }}
        .employee-card {{
            border:1px solid #e2e8f0; border-radius:12px;
            margin-bottom:24px; overflow:hidden; background:#ffffff;
        }}
        .employee-header {{
            background:#f0f4f8; padding:14px 22px; border-bottom:1px solid #e2e8f0;
            display:flex; justify-content:space-between; align-items:center;
            flex-wrap:wrap; gap:8px;
        }}
        .employee-name {{ font-size:15px; font-weight:700; color:#1a2a3a; }}
        .employee-meta {{ font-size:12px; color:#6a7e9e; font-weight:500; }}

        .sub-block {{ padding:18px 22px 4px 22px; }}
        .sub-title {{
            font-size:13px; font-weight:700; color:#1a3a5c;
            text-transform:uppercase; letter-spacing:0.6px; margin-bottom:10px;
        }}

        .table-wrap {{
            border:1px solid #e2e8f0; border-radius:10px;
            overflow:hidden; margin-bottom:18px;
        }}
        .data-table {{ width:100%; border-collapse:collapse; font-size:13px; }}
        .data-table th {{
            background:#1a3a5c; color:#ffffff; font-weight:600;
            padding:10px 14px; text-align:left; font-size:11px;
            letter-spacing:0.6px; text-transform:uppercase;
        }}
        .data-table td {{
            padding:11px 14px; border-bottom:1px solid #eef2f6; color:#2a3a4a;
        }}
        .data-table tr:last-child td {{ border-bottom:none; }}
        .data-table tr:nth-child(even) td {{ background:#fafbfd; }}
        .data-table .num {{ text-align:right; font-variant-numeric:tabular-nums; }}
        .data-table .diff {{ font-weight:600; color:#c0392b; }}

        .status-warning {{
            color:#92400e; background:#fef3c7; padding:3px 10px;
            border-radius:20px; font-weight:700; display:inline-block; font-size:11px;
        }}
        .status-success {{
            color:#1e8449; background:#d5f5e3; padding:3px 10px;
            border-radius:20px; font-weight:700; display:inline-block; font-size:11px;
        }}

        .notes-section {{
            margin:8px 40px 28px 40px; background:#f8fafc;
            border-left:4px solid #2a5a8c; border-radius:8px; padding:18px 22px;
        }}
        .notes-section strong {{
            font-size:13px; color:#1a2a3a; text-transform:uppercase; letter-spacing:0.6px;
        }}
        .notes-section ul {{
            margin:10px 0 0 18px; color:#4a6a8a; font-size:13px; line-height:1.8;
        }}
        .notes-section li {{ margin-bottom:4px; }}

        .email-footer {{
            background:#1a3a5c; color:#ffffff; padding:22px 40px; text-align:center;
        }}
        .footer-text {{ font-size:12px; opacity:0.9; margin-bottom:4px; }}
        .footer-note {{ font-size:10px; opacity:0.65; margin-top:6px; }}

        @media (max-width:700px) {{
            .email-header, .greeting, .kpi-row, .employee-section, .notes-section, .email-footer {{
                padding-left:20px; padding-right:20px;
            }}
            .notes-section {{ margin-left:20px; margin-right:20px; }}
            .data-table th, .data-table td {{ padding:8px 10px; font-size:11px; }}
            .kpi-card {{ min-width:100%; }}
            .header-meta {{ gap:14px; }}
        }}
    </style>
</head>
<body>
    <div class="email-container">

        <div class="email-header">
            <div class="logo">⏱️ TIME CONTROL PLATFORM <span>· INCIDENT REPORT</span></div>
            <div class="report-subtitle">Time Tracking Compliance Report</div>
            <div class="header-meta">
                <div><span class="k">Date</span><span class="v">{pd.Timestamp.today().strftime('%m/%d/%Y')}</span></div>
                <div><span class="k">Period</span><span class="v">{start_date} — {end_date}</span></div>
                <div><span class="k">Responsible</span><span class="v">{employee_name}</span></div>
            </div>
        </div>

        <div class="greeting">
            <h2>Hello {employee_name.split()[0] if employee_name.split() else "Team"},</h2>
            <p>
                As part of our continuous effort to improve time management, reporting accuracy,
                and compliance across all tracking platforms, we are sharing the results identified
                by the <strong>Time Control Platform</strong> for the period under review.
            </p>
            <p>
                The purpose of this report is to help team members identify and correct any
                time-tracking inconsistencies within <strong>24 hours</strong>, ensuring accurate
                operational reporting and compliance with company standards.
            </p>
            <p class="highlight">
                If corrections have already been completed, please disregard the corresponding observations.
            </p>
        </div>

        <div class="kpi-row">
            <div class="kpi-card">
                <div class="kpi-value">{total_incidents}</div>
                <div class="kpi-label">Total Incidents</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-value">{len(compliance_df)}</div>
                <div class="kpi-label">Compliance Issues</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-value">{len(attendance_df)}</div>
                <div class="kpi-label">Attendance Mismatches</div>
            </div>
        </div>

        <div class="employee-section">
            <div class="employee-card">
                <div class="employee-header">
                    <div class="employee-name">👤 {employee_name}</div>
                    <div class="employee-meta">{total_incidents} incidents</div>
                </div>
                {compliance_block}
                {attendance_block}
            </div>
        </div>

        <div class="notes-section">
            <strong>📌 Notes</strong>
            <ul>
                <li>Employees not listed in this report are considered <strong>fully compliant</strong> for the evaluated period.</li>
                <li>Approved novelties, scheduled holidays, vacations, and authorized exceptions are <strong>automatically considered</strong> by the system when calculating compliance.</li>
                <li>This report is generated automatically by the <strong>Time Control Platform</strong>.</li>
            </ul>
        </div>

        <div class="email-footer">
            <div class="footer-text">Time Control Platform · This report has been automatically generated</div>
            <div class="footer-text">Quality Control & Efficiency · Community Law Group</div>
            <div class="footer-note">© {pd.Timestamp.today().year} Community Law Group · All rights reserved</div>
        </div>

    </div>
</body>
</html>
"""


@st.cache_data
def process_files(
    toggl_file,
    camplegal_file,
    smokeball_file,
    resources_file,
    novelties_file,
    clg_novelties_file,
    start_date,
    end_date,
):
    # =========================================
    # READ FILES
    # =========================================

    df_toggl = pd.read_excel(toggl_file, sheet_name="DataBaseToggl", engine="openpyxl")
    df_camplegal = pd.read_excel(camplegal_file, sheet_name="Time entries", engine="openpyxl")
    df_smokeball = pd.read_excel(smokeball_file, sheet_name="Entries", engine="openpyxl")
    df_names = pd.read_excel(resources_file, sheet_name="Names", engine="openpyxl")
    df_novelties = pd.read_excel(novelties_file, sheet_name="Novedades", engine="openpyxl")
    df_clg_novelties = pd.read_excel(clg_novelties_file, sheet_name="Novedades", engine="openpyxl")
    df_special_days = pd.read_excel(novelties_file, sheet_name="Novedades 2", engine="openpyxl")
    df_clg_special_days = pd.read_excel(clg_novelties_file, sheet_name="Novedades 2", engine="openpyxl")

    # =========================================
    # PARSE NOVELTIES
    # =========================================

    df_novelties["Fecha Inicio"] = pd.to_datetime(df_novelties["Fecha Inicio"], errors="coerce")
    df_novelties["Fecha Fin"] = pd.to_datetime(df_novelties["Fecha Fin"], errors="coerce")
    df_clg_novelties["Fecha Inicio"] = pd.to_datetime(df_clg_novelties["Fecha Inicio"], errors="coerce")
    df_clg_novelties["Fecha Fin"] = pd.to_datetime(df_clg_novelties["Fecha Fin"], errors="coerce")

    # =========================================
    # PARSE SPECIAL DAYS
    # =========================================

    df_special_days["Fecha"] = pd.to_datetime(df_special_days["Fecha"], errors="coerce")
    df_clg_special_days["Fecha"] = pd.to_datetime(df_clg_special_days["Fecha"], errors="coerce")

    df_special_days["PERSONA_NORMALIZADA"] = df_special_days["Persona"].astype(str).apply(normalize_name)
    df_special_days["TIPO_NORMALIZADO"] = df_special_days["Tipo de Novedad"].astype(str).str.upper().str.strip()

    df_clg_special_days["PERSONA_NORMALIZADA"] = df_clg_special_days["Persona"].astype(str).apply(normalize_name)
    df_clg_special_days["TIPO_NORMALIZADO"] = df_clg_special_days["Tipo de Novedad"].astype(str).str.upper().str.strip()

    df_clg_novelties["PERSONA_NORMALIZADA"] = df_clg_novelties["Persona"].astype(str).apply(normalize_name)

    # =========================================
    # USER MAP
    # =========================================

    user_map = build_user_mapping(df_names)

    # =========================================
    # NORMALIZE USERS
    # =========================================

    df_toggl["NORMALIZED_MEMBER"] = df_toggl["Member"].astype(str).apply(normalize_name)
    df_toggl["USER_CORRECT"] = df_toggl["NORMALIZED_MEMBER"].map(user_map).fillna(df_toggl["Member"])

    df_camplegal["NORMALIZED_MEMBER"] = df_camplegal["Staff Name"].astype(str).apply(normalize_name)
    df_camplegal["USER_CORRECT"] = df_camplegal["NORMALIZED_MEMBER"].map(user_map).fillna(df_camplegal["Staff Name"])

    df_smokeball["NORMALIZED_MEMBER"] = df_smokeball["Name"].astype(str).apply(normalize_name)
    df_smokeball["USER_CORRECT"] = df_smokeball["NORMALIZED_MEMBER"].map(user_map).fillna(df_smokeball["Name"])

    # =========================================
    # DATE
    # =========================================

    df_toggl["Date1"] = pd.to_datetime(df_toggl["Date1"], errors="coerce")
    df_camplegal["Date1"] = pd.to_datetime(df_camplegal["Date"], errors="coerce")
    df_smokeball["Date1"] = pd.to_datetime(df_smokeball["Date"], errors="coerce")

    # =========================================
    # FILTER DATES
    # =========================================

    start_dt = pd.to_datetime(start_date)

    end_dt = (
        pd.to_datetime(end_date)
        + pd.Timedelta(days=1)
        - pd.Timedelta(seconds=1)
    )

    df_toggl = df_toggl[(df_toggl["Date1"] >= start_dt) & (df_toggl["Date1"] <= end_dt)]
    df_camplegal = df_camplegal[(df_camplegal["Date1"] >= start_dt) & (df_camplegal["Date1"] <= end_dt)]
    df_smokeball = df_smokeball[(df_smokeball["Date1"] >= start_dt) & (df_smokeball["Date1"] <= end_dt)]

    # =========================================
    # HOURS
    # =========================================

    df_toggl["Hours"] = df_toggl["Duration"].apply(convert_duration_to_hours)
    df_camplegal["Hours"] = pd.to_numeric(df_camplegal["Hours Spent"], errors="coerce").fillna(0)
    df_smokeball["Hours"] = pd.to_numeric(df_smokeball["Hours"], errors="coerce").fillna(0)

    # =========================================
    # STANDARDIZE COLUMNS
    # =========================================

    df_toggl["Activity"] = df_toggl["Project (Activity)"]
    df_toggl["Source"] = "Toggl"

    df_camplegal["Activity"] = df_camplegal["Activity"].astype(str)
    df_camplegal["Source"] = "Camp Legal"

    df_smokeball["Activity"] = df_smokeball["Subject"].astype(str)
    df_smokeball["Source"] = "Smokeball"

    # =========================================
    # SELECT COLUMNS
    # =========================================

    df_toggl_std = df_toggl[["Date1", "USER_CORRECT", "Hours", "Activity", "Source"]].copy()
    df_camplegal_std = df_camplegal[["Date1", "USER_CORRECT", "Hours", "Activity", "Source"]].copy()
    df_smokeball_std = df_smokeball[["Date1", "USER_CORRECT", "Hours", "Activity", "Source"]].copy()

    # =========================================
    # CONCATENATE
    # =========================================

    df_all_time = pd.concat(
        [df_toggl_std, df_camplegal_std, df_smokeball_std],
        ignore_index=True,
    )

    # =========================================
    # DAILY REPORT
    # =========================================

    df_all_time["Work_Date"] = pd.to_datetime(df_all_time["Date1"]).dt.floor("D")

    daily_report = (
        df_all_time
        .groupby(["Work_Date", "USER_CORRECT"], as_index=False)
        .agg(Total_Hours=("Hours", "sum"))
    )

    daily_report["Total_Hours"] = daily_report["Total_Hours"].round(2)
    daily_report["Status"] = "See Compliance Engine"

    # =========================================
    # EMPLOYEE INFO
    # =========================================

    employee_info = (
        df_names[["NAME CORRECT", "COMPANY", "DEPARTMENT", "TEAM", "EMAIL", "COPY_EMAIL_SB", "COPY_EMAIL_TG", "COPY_EMAIL_CL"]]
        .drop_duplicates(subset=["NAME CORRECT"])
    )

    daily_report = daily_report.merge(
        employee_info,
        left_on="USER_CORRECT",
        right_on="NAME CORRECT",
        how="left",
    )

    # =========================================
    # USER SUMMARY
    # =========================================

    users_summary = (
        df_all_time
        .groupby("USER_CORRECT")
        .agg(Total_Hours=("Hours", "sum"), Entries=("Hours", "count"))
        .reset_index()
    )

    users_summary["Total_Hours"] = users_summary["Total_Hours"].round(2)

    users_summary = users_summary.merge(
        employee_info,
        left_on="USER_CORRECT",
        right_on="NAME CORRECT",
        how="left",
    )

    users_summary = users_summary.sort_values("Total_Hours", ascending=False)

    # =========================================
    # DETAIL REPORT
    # =========================================

    detail_report = df_all_time.copy()

    # =========================================
    # COMPLIANCE ENGINE
    # =========================================

    active_users = df_names[
        df_names["USER STATUS"].astype(str).str.upper().eq("ACTIVE")
    ]["NAME CORRECT"].dropna().unique()

    company_map = dict(zip(df_names["NAME CORRECT"], df_names["COMPANY"]))
    contract_map = dict(zip(df_names["NAME CORRECT"], df_names["TYPE OF CONTRACT"]))

    all_dates = pd.date_range(start=start_date, end=end_date, freq="D")

    compliance_records = []

    for current_day in all_dates:
        weekday = current_day.weekday()

        for user in active_users:
            normalized_user = normalize_name(user)
            user_company = str(company_map.get(user, "")).upper().strip()
            user_contract = normalize_name(contract_map.get(user, ""))
            required_hours = 0
            holiday_assignments = pd.DataFrame()

            # VERIFICAR SI EL USUARIO ESTÁ EN FESTIVO (NO TRABAJA)
            holiday_user = df_special_days[
                (df_special_days["PERSONA_NORMALIZADA"] == normalized_user)
                & (df_special_days["TIPO_NORMALIZADO"] == "FESTIVO")
                & (df_special_days["Fecha"].dt.date == current_day.date())
            ]

            if len(holiday_user) > 0:
                continue

            # VERIFICAR DÍA FESTIVO (PARA TODOS)
            holiday_assignments = df_special_days[
                (df_special_days["PERSONA_NORMALIZADA"] == "TODOS")
                & (df_special_days["TIPO_NORMALIZADO"] == "FESTIVO")
                & (df_special_days["Fecha"].dt.date == current_day.date())
            ]

            is_holiday = len(holiday_assignments) > 0

            if is_holiday:
                holiday_worker = df_special_days[
                    (df_special_days["PERSONA_NORMALIZADA"] == normalized_user)
                    & (df_special_days["TIPO_NORMALIZADO"] == "FESTIVO_PROGRAMADO")
                    & (df_special_days["Fecha"].dt.date == current_day.date())
                ]
                if len(holiday_worker) > 0:
                    required_hours = 8
                else:
                    required_hours = 0
            else:
                # LUNES A VIERNES
                if weekday <= 4:
                    required_hours = 8

                # SÁBADOS
                elif weekday == 5:
                    if user_company == "MAX":
                        saturday_user = df_special_days[
                            (df_special_days["PERSONA_NORMALIZADA"] == normalized_user)
                            & (df_special_days["Fecha"].dt.date == current_day.date())
                        ]
                        if len(saturday_user) > 0:
                            required_hours = 4
                        else:
                            required_hours = 0

                    elif user_company == "CLG":
                        clg_saturday_user = df_clg_special_days[
                            (df_clg_special_days["PERSONA_NORMALIZADA"] == normalized_user)
                            & (df_clg_special_days["TIPO_NORMALIZADO"] == "SABADO")
                            & (df_clg_special_days["Fecha"].dt.date == current_day.date())
                        ]
                        if len(clg_saturday_user) > 0:
                            required_hours = 8
                        else:
                            required_hours = 0
                    else:
                        required_hours = 0

                # DOMINGOS
                else:
                    required_hours = 0

            # PRESTACIÓN DE SERVICIO
            is_service_contract = "PRESTACION" in user_contract

            # SI NO HAY HORAS REQUERIDAS, SALTAR
            if required_hours == 0:
                continue

            # OBTENER HORAS TRABAJADAS
            day_record = daily_report[
                (daily_report["USER_CORRECT"] == user)
                & (daily_report["Work_Date"].dt.date == current_day.date())
            ]

            worked_hours = 0.0
            if len(day_record) > 0:
                worked_hours = float(day_record["Total_Hours"].sum())

            # OBTENER NOVEDAD
            novelty = get_novelty_status(user, current_day, df_novelties)

            if novelty is None and user_company == "CLG":
                clg_novelty = df_clg_novelties[
                    (df_clg_novelties["PERSONA_NORMALIZADA"] == normalized_user)
                    & (current_day >= df_clg_novelties["Fecha Inicio"])
                    & (current_day <= df_clg_novelties["Fecha Fin"])
                ]
                if len(clg_novelty) > 0:
                    novelty = str(clg_novelty.iloc[0]["Tipo de Novedad"])

            # LÓGICA DE STATUS
            if is_service_contract:
                status = "🟣 Prestación de servicio"
            elif novelty is not None:
                status = f"🟡 {novelty}"
            elif worked_hours == 0:
                status = "❌ No registró tiempo"
            elif required_hours == 4:
                if worked_hours >= 3.5:
                    status = "✅ Cumple"
                else:
                    status = "❌ Horas insuficientes"
            elif worked_hours < required_hours:
                status = "❌ Horas insuficientes"
            else:
                status = "✅ Cumple"

            compliance_records.append(
                {
                    "Date": current_day.date(),
                    "Weekday": weekday,
                    "User": user,
                    "Hours Worked": round(worked_hours, 2),
                    "Hours Required": required_hours,
                    "Novelty": novelty,
                    "Status": status,
                    "Holiday Count": len(holiday_assignments),
                    "Current Day": current_day.date(),
                }
            )

    compliance_engine = pd.DataFrame(compliance_records)

    compliance_summary = (
        compliance_engine
        .groupby("User")
        .agg(
            Total_Hours=("Hours Worked", "sum"),
            Days_Evaluated=("Date", "count"),
        )
        .reset_index()
    )

    success_counts = (
        compliance_engine[
            compliance_engine["Status"].isin(["✅ Cumple", "🟣 Prestación de servicio"])
        ]
        .groupby("User")
        .size()
    )

    failure_counts = (
        compliance_engine[
            compliance_engine["Status"].isin(["❌ No registró tiempo", "❌ Horas insuficientes"])
        ]
        .groupby("User")
        .size()
    )

    novelty_counts = (
        compliance_engine[
            compliance_engine["Status"].astype(str).str.startswith("🟡")
        ]
        .groupby("User")
        .size()
    )

    compliance_summary["Compliant_Days"] = compliance_summary["User"].map(success_counts).fillna(0)
    compliance_summary["Non_Compliant_Days"] = compliance_summary["User"].map(failure_counts).fillna(0)
    compliance_summary["Justified_Days"] = compliance_summary["User"].map(novelty_counts).fillna(0)

    daily_status = (
        compliance_engine
        .sort_values("Date")
        .groupby("User")
        .apply(
            lambda df: " | ".join(
                [f"{d.strftime('%m/%d')} {s}" for d, s in zip(df["Date"], df["Status"])]
            )
        )
    )

    compliance_summary["Daily_Status"] = compliance_summary["User"].map(daily_status).fillna("")

    failed_dates = (
        compliance_engine[
            compliance_engine["Status"].isin(["❌ No registró tiempo", "❌ Horas insuficientes"])
        ]
        .groupby("User")["Date"]
        .apply(lambda dates: ", ".join(d.strftime("%m/%d") for d in dates))
    )

    compliance_summary["Failed_Dates"] = compliance_summary["User"].map(failed_dates).fillna("Ninguna")

    return daily_report, detail_report, users_summary, compliance_engine, compliance_summary, employee_info, user_map


# ==================================================
# HEADER
# ==================================================

st.title("⏱️ Time Control Platform")
st.markdown("### Final Phase - Toggl - Camp Legal - Smokeball Validation")


# ==================================================
# SIDEBAR
# ==================================================

st.sidebar.header("Upload Files")

resources_file = st.sidebar.file_uploader("Power BI Resources", type=["xlsx"])
toggl_file = st.sidebar.file_uploader("Toggl File", type=["xlsx"])
novelties_file = st.sidebar.file_uploader("Novedades RRHH", type=["xlsx"])
clg_novelties_file = st.sidebar.file_uploader("Novedades CLG", type=["xlsx"])
camplegal_file = st.sidebar.file_uploader("Camp Legal", type=["xlsx"])
smokeball_file = st.sidebar.file_uploader("Smokeball", type=["xlsx"])
attendance_file = st.sidebar.file_uploader("ADP & UAttend", type=["xlsx"])

st.sidebar.divider()

start_date = st.sidebar.date_input("Start Date")
end_date = st.sidebar.date_input("End Date")


# ==================================================
# PROCESS
# ==================================================

if (
    resources_file
    and toggl_file
    and novelties_file
    and camplegal_file
    and smokeball_file
    and clg_novelties_file
    and attendance_file
):
    (
        daily_report,
        detail_report,
        users_summary,
        compliance_engine,
        compliance_summary,
        employee_info,
        user_map,
    ) = process_files(
        toggl_file,
        camplegal_file,
        smokeball_file,
        resources_file,
        novelties_file,
        clg_novelties_file,
        start_date,
        end_date,
    )

    # =========================================
    # ATTENDANCE COMPARISON
    # =========================================

    attendance_comparison = pd.DataFrame()
    justified_records = pd.DataFrame()

    df_uatt = pd.read_excel(attendance_file, sheet_name="NewUATT", engine="openpyxl")
    df_adp = pd.read_excel(attendance_file, sheet_name="NewADP", engine="openpyxl")

    attendance_uatt = df_uatt[["DATE", "Corrected Name", "Hours worked"]].copy()
    attendance_uatt.columns = ["Date", "User", "Attendance_Hours"]

    attendance_adp = df_adp[["Date", "Corrected Name", "Hours worked"]].copy()
    attendance_adp.columns = ["Date", "User", "Attendance_Hours"]

    attendance_all = pd.concat([attendance_uatt, attendance_adp], ignore_index=True)

    attendance_all["Date"] = pd.to_datetime(attendance_all["Date"], errors="coerce").dt.floor("D")
    attendance_all["Attendance_Hours"] = pd.to_numeric(attendance_all["Attendance_Hours"], errors="coerce").fillna(0)

    attendance_all = attendance_all[
        (attendance_all["Date"] >= pd.to_datetime(start_date))
        & (
            attendance_all["Date"]
            <= (pd.to_datetime(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1))
        )
    ]

    platform_hours = daily_report[["Work_Date", "USER_CORRECT", "Total_Hours"]].copy()
    platform_hours["Date"] = pd.to_datetime(platform_hours["Work_Date"]).dt.floor("D")
    platform_hours = platform_hours[["Date", "USER_CORRECT", "Total_Hours"]].rename(
        columns={"USER_CORRECT": "User", "Total_Hours": "Platform_Hours"}
    )

    attendance_all["NORMALIZED_USER"] = attendance_all["User"].astype(str).apply(normalize_name)
    attendance_all["USER_CORRECT"] = attendance_all["NORMALIZED_USER"].map(user_map).fillna(attendance_all["User"])

    platform_hours["NORMALIZED_USER"] = platform_hours["User"].astype(str).apply(normalize_name)
    platform_hours["USER_CORRECT"] = platform_hours["NORMALIZED_USER"].map(user_map).fillna(platform_hours["User"])

    attendance_comparison = attendance_all.merge(
        platform_hours,
        on=["Date", "USER_CORRECT"],
        how="left",
    )

    attendance_comparison.rename(columns={"USER_CORRECT": "User"}, inplace=True)

    attendance_comparison["Platform_Hours"] = attendance_comparison["Platform_Hours"].fillna(0)

    attendance_comparison["Difference_Hours"] = (
        attendance_comparison["Platform_Hours"] - attendance_comparison["Attendance_Hours"]
    )

    attendance_comparison["Difference_Pct"] = (
        attendance_comparison["Difference_Hours"]
        .abs()
        .div(attendance_comparison["Attendance_Hours"].replace(0, np.nan))
        * 100
    )

    attendance_comparison["Status"] = np.where(
        attendance_comparison["Difference_Pct"] <= 10,
        "✅ Match",
        "🚨 Review",
    )

    attendance_comparison["Justified"] = "NO"

    justified_records = compliance_engine[
        compliance_engine["Status"].isin(["🟣 Prestación de servicio"])
        | (compliance_engine["Status"].astype(str).str.startswith("🟡"))
    ].copy()

    justified_records = justified_records[["Date", "User", "Status", "Hours Worked"]].drop_duplicates()
    justified_records["Date"] = pd.to_datetime(justified_records["Date"], errors="coerce").dt.floor("D")
    justified_records["USER_KEY"] = (
        justified_records["User"]
        .astype(str)
        .apply(normalize_name)
    )

    attendance_comparison["Date"] = pd.to_datetime(attendance_comparison["Date"], errors="coerce").dt.floor("D")
    attendance_comparison["USER_KEY"] = (
        attendance_comparison["User"]
        .astype(str)
        .apply(normalize_name)
    )

    attendance_comparison = attendance_comparison.merge(
        justified_records.assign(Justified="YES"),
        on=["Date", "USER_KEY"],
        how="left",
        suffixes=("", "_RRHH"),
    )

    attendance_comparison["Justified"] = np.where(
        attendance_comparison["Justified_RRHH"] == "YES",
        "YES",
        "NO",
    )

    justified_lookup = (
        justified_records
        .drop_duplicates(subset=["Date", "User"])
        .set_index(["Date", "User"])["Status"]
        .to_dict()
    )

    attendance_comparison["Justification_Status"] = attendance_comparison.apply(
        lambda row: justified_lookup.get((row["Date"], normalize_name(row["User"]))),
        axis=1,
    )

    attendance_comparison["Status"] = np.where(
        attendance_comparison["Justified"] == "YES",
        attendance_comparison["Justification_Status"],
        attendance_comparison["Status"],
    )

    attendance_comparison.drop(columns=["Justified_RRHH"], inplace=True, errors="ignore")

    # Justified records sin horas de attendance
    attendance_justified = justified_records.copy()
    attendance_justified["Attendance_Hours"] = np.nan
    attendance_justified["Platform_Hours"] = attendance_justified["Hours Worked"]
    attendance_justified["Difference_Hours"] = np.nan
    attendance_justified["Difference_Pct"] = np.nan
    attendance_justified["Justified"] = "YES"

    attendance_justified.drop(
        columns=["Hours Worked"],
        inplace=True,
        errors="ignore",
    )

    attendance_justified = attendance_justified[
        [
            "Date",
            "User",
            "Attendance_Hours",
            "Platform_Hours",
            "Difference_Hours",
            "Difference_Pct",
            "Status",
            "Justified",
        ]
    ]

    attendance_comparison = pd.concat(
        [attendance_comparison, attendance_justified],
        ignore_index=True,
    )

    attendance_comparison = (
        attendance_comparison
        .sort_values(["Date", "User"])
        .drop_duplicates(subset=["Date", "User"], keep="last")
    )

    # =========================================
    # CÁLCULO DE MÉTRICAS
    # =========================================

    total_users = users_summary["USER_CORRECT"].nunique()

    compliant_days = len(compliance_engine[compliance_engine["Status"] == "✅ Cumple"])

    non_compliant_days = len(
        compliance_engine[
            compliance_engine["Status"].isin(["❌ No registró tiempo", "❌ Horas insuficientes"])
        ]
    )

    justified_days = len(
        compliance_engine[compliance_engine["Status"].astype(str).str.startswith("🟡")]
    )

    total_hours = round(users_summary["Total_Hours"].sum(), 2)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("👥 Users", total_users)
    c2.metric("✅ Compliant Days", compliant_days)
    c3.metric("❌ Non Compliant Days", non_compliant_days)
    c4.metric("🟡 Justified", justified_days)
    c5.metric("⏱️ Total Hours", total_hours)

    # =====================================
    # NON COMPLIANCE
    # =====================================

    non_compliance = compliance_engine[
        compliance_engine["Status"].isin(
            ["❌ No registró tiempo", "❌ Horas insuficientes"]
        )
    ]

    attendance_issues = attendance_comparison[
        (attendance_comparison["Status"] == "🚨 Review")
        & (attendance_comparison["Justified"] == "NO")
    ].copy()

    attendance_issues["Incident_Type"] = "🚨 Attendance Mismatch"
    attendance_issues = attendance_issues.rename(columns={"Status": "Incident_Status"})
    attendance_issues = attendance_issues[["Date", "User", "Incident_Type", "Incident_Status"]]

    compliance_issues = non_compliance.copy()
    compliance_issues["Incident_Type"] = "🚨 Compliance Issue"
    compliance_issues = compliance_issues.rename(columns={"Status": "Incident_Status"})
    compliance_issues = compliance_issues[["Date", "User", "Incident_Type", "Incident_Status"]]

    all_incidents = pd.concat([compliance_issues, attendance_issues], ignore_index=True)
    all_incidents["Date"] = pd.to_datetime(all_incidents["Date"], errors="coerce").dt.floor("D")

    incident_source = all_incidents.groupby("User")["Incident_Type"].agg(lambda x: sorted(set(x)))

    source_map = {}
    for user, incident_types in incident_source.items():
        has_compliance = "🚨 Compliance Issue" in incident_types
        has_attendance = "🚨 Attendance Mismatch" in incident_types

        if has_compliance and has_attendance:
            source_map[user] = "Mixed"
        elif has_compliance:
            source_map[user] = "Compliance"
        elif has_attendance:
            source_map[user] = "Attendance"
        else:
            source_map[user] = "Unknown"

    # =====================================
    # NOTIFICATION QUEUE
    # =====================================

    notification_queue = (
        all_incidents
        .groupby("User")
        .agg(Incidents=("Date", "count"))
        .reset_index()
    )

    notification_queue["Source"] = notification_queue["User"].map(source_map)

    notification_queue = notification_queue.merge(
        employee_info,
        left_on="User",
        right_on="NAME CORRECT",
        how="left",
    )

    # =====================================
    # TABS
    # =====================================

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
        [
            "🚨 Compliance Engine",
            "📋 Activity Detail",
            "👥 Users Summary",
            "📊 Compliance Summary",
            "🕒 Attendance Match",
            "📧 Notifications Center",
        ]
    )

    # =====================================
    # TAB 1 - COMPLIANCE ENGINE
    # =====================================

    with tab1:
        st.subheader("Compliance Engine")

        compliance_filter = st.selectbox(
            "Compliance Status",
            ["All", "✅ Cumple", "❌ No registró tiempo", "❌ Horas insuficientes"],
        )

        compliance_users = sorted(compliance_engine["User"].dropna().unique().tolist())
        selected_compliance_user = st.selectbox("Search User", ["All Users"] + compliance_users)

        engine = compliance_engine.copy()
        if compliance_filter != "All":
            engine = engine[engine["Status"] == compliance_filter]
        if selected_compliance_user != "All Users":
            engine = engine[engine["User"] == selected_compliance_user]

        st.dataframe(
            engine[["Date", "User", "Hours Worked", "Novelty", "Status"]],
            use_container_width=True,
        )

        st.markdown("---")

        st.subheader("🚨 Non Compliant Records")

        st.dataframe(
            non_compliance[
                [
                    "Date",
                    "User",
                    "Hours Worked",
                    "Status",
                ]
            ],
            use_container_width=True,
        )

    # =====================================
    # TAB 2 - ACTIVITY DETAIL
    # =====================================

    with tab2:
        st.subheader("Activity Detail")

        users_list = sorted(detail_report["USER_CORRECT"].dropna().unique().tolist())
        selected_user = st.selectbox("Search User", ["All Users"] + users_list)

        detail_view = detail_report.copy()
        if selected_user != "All Users":
            detail_view = detail_view[detail_view["USER_CORRECT"] == selected_user]

        st.dataframe(
            detail_view[["Date1", "USER_CORRECT", "Activity", "Hours", "Source"]],
            use_container_width=True,
        )

    # =====================================
    # TAB 3 - USERS SUMMARY
    # =====================================

    with tab3:
        st.subheader("Total Hours by User")
        st.dataframe(
            users_summary[["USER_CORRECT", "COMPANY", "DEPARTMENT", "TEAM", "Entries", "Total_Hours"]],
            use_container_width=True,
        )

        fig_users = px.bar(
            users_summary.head(25),
            x="USER_CORRECT",
            y="Total_Hours",
            title="Top Users by Hours",
        )
        st.plotly_chart(fig_users, use_container_width=True)

    # =====================================
    # TAB 4 - COMPLIANCE SUMMARY
    # =====================================

    with tab4:
        st.subheader("Compliance Summary By User")
        summary_view = compliance_summary.copy()

        summary_users = sorted(summary_view["User"].dropna().unique().tolist())
        selected_summary_user = st.selectbox("Search User (Summary)", ["All Users"] + summary_users)

        if selected_summary_user != "All Users":
            summary_view = summary_view[summary_view["User"] == selected_summary_user]

        cols_per_row = 6

        for i in range(0, len(summary_view), cols_per_row):
            cols = st.columns(cols_per_row)

            for j in range(cols_per_row):
                if i + j >= len(summary_view):
                    continue

                row = summary_view.iloc[i + j]
                non_compliant = int(row["Non_Compliant_Days"])
                icon = "❌" if non_compliant > 0 else "✅"

                with cols[j]:
                    card_background = "#e8f5e9" if non_compliant == 0 else "#fdeaea"
                    card_border = "#2e7d32" if non_compliant == 0 else "#d32f2f"

                    st.markdown(
                        f"""
                        <div style="
                            background: {card_background};
                            border: 2px solid {card_border};
                            border-radius: 12px;
                            padding: 10px;
                            margin-bottom: 10px;
                        ">
                            <b>{icon} {row['User']}</b><br><br>
                            ⏱️ {row['Total_Hours']:.2f} hrs<br>
                            📅 {int(row['Days_Evaluated'])} días<br>
                            ✅ {int(row['Compliant_Days'])}<br>
                            ❌ {int(row['Non_Compliant_Days'])}<br>
                            🟡 {int(row['Justified_Days'])}<br>
                            <hr>
                            <b>Incidencias:</b><br>
                            {row['Failed_Dates']}
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

    # =====================================
    # TAB 5 - ATTENDANCE MATCH
    # =====================================

    with tab5:
        st.subheader("Platform vs Attendance")

        if len(attendance_comparison) > 0:
            attendance_users = sorted(
                attendance_comparison["User"]
                .dropna()
                .unique()
                .tolist()
            )

            selected_attendance_user = st.selectbox(
                "Search User",
                ["All Users"] + attendance_users,
                key="attendance_user_filter",
            )

            attendance_view = attendance_comparison.copy()

            if selected_attendance_user != "All Users":
                attendance_view = attendance_view[
                    attendance_view["User"] == selected_attendance_user
                ]

            st.dataframe(
                attendance_view[
                    [
                        "Date",
                        "User",
                        "Attendance_Hours",
                        "Platform_Hours",
                        "Difference_Hours",
                        "Difference_Pct",
                        "Status",
                        "Justified",
                    ]
                ],
                use_container_width=True,
            )
        else:
            st.info("Upload ADP & UAttend file to enable comparison.")

    # =====================================
    # TAB 6 - NOTIFICATIONS CENTER
    # =====================================

    with tab6:
        st.subheader("📧 Notifications Center")

        test_mode = st.checkbox("🧪 Test Mode (Data Team)", value=True)

        if len(notification_queue) == 0:
            st.success("🎉 No users require notifications.")
        else:
            excluded_users = st.multiselect(
                "Exclude users from notifications",
                sorted(notification_queue["User"].dropna().unique().tolist()),
            )

            notification_view = notification_queue[
                ~notification_queue["User"].isin(excluded_users)
            ]

            st.dataframe(
                notification_view[["User", "Incidents", "Source", "EMAIL"]],
                use_container_width=True,
            )

            st.divider()

            selected_notification_user = st.selectbox(
                "Preview Email",
                sorted(notification_view["User"].dropna().unique().tolist()),
            )

            preview_record = notification_view[
                notification_view["User"] == selected_notification_user
            ].iloc[0]

            st.info(f"Source: {preview_record['Source']}")

            TEST_EMAIL = "data.analyst7@communitylawgroup.com"

            cc_list = []
            for col in ["COPY_EMAIL_SB", "COPY_EMAIL_TG", "COPY_EMAIL_CL"]:
                value = preview_record.get(col)
                if pd.notna(value):
                    value = str(value).strip()
                    if value != "":
                        cc_list.append(value)
            cc_list = sorted(list(set(cc_list)))

            user_incidents = all_incidents[
                all_incidents["User"] == selected_notification_user
            ].sort_values("Date")

            # =====================================
            # DATAFRAMES FILTRADOS PARA EL TEMPLATE
            # =====================================

            compliance_df_for_email = compliance_engine[
                (compliance_engine["User"] == selected_notification_user)
                & (
                    compliance_engine["Status"].isin(
                        ["❌ No registró tiempo", "❌ Horas insuficientes"]
                    )
                )
            ].copy()

            attendance_df_for_email = attendance_comparison[
                (attendance_comparison["User"] == selected_notification_user)
                & (attendance_comparison["Status"] == "🚨 Review")
            ].copy()

            # =====================================
            # BUILD INCIDENT DETAILS (para el asunto / lógica previa)
            # =====================================

            incident_details = []

            for _, row in user_incidents.iterrows():
                incident_date = row["Date"]

                if row["Incident_Type"] == "🚨 Compliance Issue":
                    compliance_row = compliance_engine[
                        (compliance_engine["User"] == selected_notification_user)
                        & (
                            pd.to_datetime(compliance_engine["Date"])
                            == pd.to_datetime(incident_date)
                        )
                    ]

                    if len(compliance_row) > 0:
                        compliance_row = compliance_row.iloc[0]
                        incident_details.append(
                            f"""
Date: {incident_date}
Type: Compliance
Hours Worked: {compliance_row['Hours Worked']}
Hours Required: {compliance_row['Hours Required']}
Issue: {compliance_row['Status']}
"""
                        )

                elif row["Incident_Type"] == "🚨 Attendance Mismatch":
                    attendance_row = attendance_comparison[
                        (attendance_comparison["User"] == selected_notification_user)
                        & (
                            pd.to_datetime(attendance_comparison["Date"])
                            == pd.to_datetime(incident_date)
                        )
                    ]

                    if len(attendance_row) > 0:
                        attendance_row = attendance_row.iloc[0]
                        incident_details.append(
                            f"""
Date: {incident_date}
Type: Attendance
Attendance Hours: {attendance_row['Attendance_Hours']}
Platform Hours: {attendance_row['Platform_Hours']}
Difference Hours: {attendance_row['Difference_Hours']}
Issue: {attendance_row['Incident_Status'] if 'Incident_Status' in attendance_row.index else '🚨 Review'}
"""
                        )

            incident_text = "\n----------------------------------------\n".join(incident_details)

            if test_mode:
                subject = "[TEST] Time Control Platform - Non Compliance Alert"
            else:
                subject = "Time Control Platform - Non Compliance Alert"

            # =====================================
            # GENERAR CUERPO CORPORATIVO
            # =====================================

            body = generate_email_html(
                employee_name=selected_notification_user,
                compliance_df=compliance_df_for_email,
                attendance_df=attendance_df_for_email,
                start_date=start_date,
                end_date=end_date,
            )

            if test_mode:
                destination_email = TEST_EMAIL
            else:
                destination_email = preview_record["EMAIL"]

            st.markdown("### Email Preview")

            st.text_input("TO", value=destination_email, disabled=True)

            if test_mode:
                st.info(f"Original recipient: {preview_record['EMAIL']}")

            st.text_area("CC", value="; ".join(cc_list), height=80, disabled=True)
            st.text_input("SUBJECT", value=subject, disabled=True)
            st.text_area("BODY", value=body, height=250)

            st.divider()

            if st.button("🧪 Send Test Email"):
                success, message = send_test_email(
                    recipient="data.analyst7@communitylawgroup.com",
                    subject=subject,
                    body=body,
                )

                if success:
                    st.success("✅ Test email sent successfully.")
                else:
                    st.error(f"❌ SMTP Error: {message}")


else:
    st.info("📌 Upload all files to begin.")
