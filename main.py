from dotenv import load_dotenv
import os
import logging
from CheckmarxPythonSDK.CxOne import (
    batch_import_github_repo,
)

logger = logging.getLogger("CheckmarxPythonSDK")

if __name__ == '__main__':
    load_dotenv()
    github_org = os.getenv("GITHUB_ORG")
    logger.info(f"github organization: {github_org}")
    github_access_token = os.getenv("GITHUB_TOKEN")
    cx_one_scanners = [scanner.strip().strip("\"").strip("\'").lower()
                       for scanner in os.getenv("CXONE_SCANNERS").split(",")]
    cxone_github_auth_code = os.getenv("CXONE_GITHUB_AUTH_CODE")
    if github_org and cxone_github_auth_code:
        batch_import_github_repo(origin="GITHUB", organization=github_org, auth_code=cxone_github_auth_code)
