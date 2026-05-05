"""
Application configuration — all settings loaded from environment variables.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Application
    app_env: str = "development"
    app_secret_key: str = "change-me-in-production"
    log_level: str = "INFO"

    # Database
    database_url: str = "postgresql+asyncpg://daca_ops:password@localhost:5432/daca_ops"

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # Google APIs
    google_service_account_json: str = ""
    gmail_delegated_user: str = "daca@rho.co"

    # Google Drive — production folder/file IDs
    drive_client_files_folder_id: str = "121c4-xohOHgK8J_-vX-I-Mfoc7nTR3mX"
    drive_ops_manual_folder_id: str = "1uB1PnEMnGhrrvDzO-jZXnwVYKBfr0I8C"
    drive_webster_reports_folder_id: str = "1tlhEB2u3Xn-3chFJ-8l8eb4PS58-SbEP"
    drive_daca_template_file_id: str = "1yzdpW6V-jSC_R-CBl2wev7QlDXCUAWzI"

    # Google Sheets — production IDs
    typeform_sheet_id: str = "1Oog92OTZ5w4Lss-CSVJ-jos8d4Or3K8qu6EQe0EuvtE"
    typeform_sheet_gid: str = "1055296310"
    daca_summary_sheet_id: str = "140z-O_ZoRyY97w4W5hBYBsUylQPJysj8rVXbzRJzRls"

    # Slack
    slack_bot_token: str = ""
    slack_daca_ops_channel_id: str = "C0APFKNF8SY"  # #daca-ops
    slack_daca_applications_channel: str = "daca-applications"
    slack_daca_transactions_channel: str = "daca-transactions"
    slack_tm_channel: str = "transactionmonitoring"

    # Jira
    jira_base_url: str = "https://rho.atlassian.net"
    jira_api_token: str = ""
    jira_user_email: str = ""
    jira_project_key: str = "CS"

    # DocuSign (Phase 2)
    docusign_integration_key: str = ""
    docusign_account_id: str = ""
    docusign_private_key_path: str = ""
    docusign_sender_email: str = "contracts@docusign.rho.co"
    docusign_base_url: str = "https://na4.docusign.net"

    # Salesforce (Phase 2)
    salesforce_client_id: str = ""
    salesforce_private_key_path: str = ""
    salesforce_username: str = ""
    salesforce_instance_url: str = "https://rho.my.salesforce.com"

    # Zendesk
    zendesk_subdomain: str = "https://rho.zendesk.com"
    zendesk_email: str = ""
    zendesk_api_token: str = ""

    # AI
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"

    # Encryption
    field_encryption_key: str = ""

    # Authentication
    auth_mode: str = "NONE"  # NONE | GOOGLE_SSO
    google_sso_client_id: str = ""
    google_sso_client_secret: str = ""
    google_sso_allowed_domain: str = "rho.co"

    # Webster Bank Reporting
    webster_report_recipients: str = "stoliveira@websterbank.com"
    webster_report_cc: str = "shani.abrahams@rho.co,mike.szarowicz@rho.co,jeff.pasquerella@rho.co"

    # Scheduled Tasks
    gmail_poll_interval_seconds: int = 60
    typeform_poll_interval_minutes: int = 10
    sla_check_interval_minutes: int = 15
    weekly_update_day: str = "tuesday"
    weekly_update_time_et: str = "10:00"
    ops_manual_sync_day: str = "monday"

    # Internal contacts (used for DocuSign pre-fill, Slack alerts, etc.)
    rho_docusign_signer_email: str = "mike.szarowicz@rho.co"
    rho_docusign_signer_name: str = "Mike Szarowicz"
    rho_docusign_cc_1_email: str = "zorica.tasic@rho.co"
    webster_docusign_signer_email: str = "mesantos@websterbank.com"
    webster_docusign_signer_name: str = "Melissa Santos"
    webster_submission_emails: str = (
        "webster_rho_daca@websterbank.com,"
        "kjamison@websterbank.com,"
        "shickey@websterbank.com,"
        "stoliveira@websterbank.com"
    )

    @property
    def webster_submission_email_list(self) -> list[str]:
        return [e.strip() for e in self.webster_submission_emails.split(",")]

    @property
    def webster_report_recipient_list(self) -> list[str]:
        return [e.strip() for e in self.webster_report_recipients.split(",")]

    @property
    def webster_report_cc_list(self) -> list[str]:
        return [e.strip() for e in self.webster_report_cc.split(",")]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
