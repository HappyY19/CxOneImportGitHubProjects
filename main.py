"""
Prerequisites for the script, you need to set the following environment variables
    a. GITHUB_ORG: your GitHub organization name, which is case-sensitive
    b. GITHUB_TOKEN: your GitHub personal access token
    c. CX_ONE_SCANNERS: comma separated value, for example: sast,sca,apisec,kics

"""
import os
import logging
import time
from github import (Github, Auth)
from CheckmarxPythonSDK.CxOne import (
    import_code_repository,
    retrieve_import_status,
)
from typing import List
from CheckmarxPythonSDK.CxOne.dto import (
    SCMImportInput,
    Scm,
    ScmOrganization,
    ProjectSettings,
    ScmProject,
    Scanner,
)

# create logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)
time_stamp_format = "%Y-%m-%dT%H:%M:%S.%fZ"


def get_github_repos_by_org(organization: str, access_token: str):
    # using an access token
    auth = Auth.Token(access_token)
    # Public Web Github
    g = Github(auth=auth)
    org = g.get_organization(organization)
    return org.get_repos()


def import_github_project_into_cx_one(
        github_token: str,
        organization: str,
        scanners: List[str],
        url: str,
        master_branch: str
):
    scanner_list = []
    for scanner in scanners:
        if scanner.strip().lower() == "sast":
            scanner_list.append(Scanner(scanner_type="sast", incremental=True))
        if scanner.strip().lower() == "sca":
            scanner_list.append(Scanner(scanner_type="sca", auto_pr_enabled=True))
        else:
            scanner_list.append(Scanner(scanner_type=scanner))
    scm_import_input = SCMImportInput(
        scm=Scm(token=github_token),
        organization=ScmOrganization(org_identity=organization, monitor_for_new_projects=True),
        default_project_settings=ProjectSettings(
            web_hook_enabled=True,
            decorate_pull_requests=True,
            scanners=scanner_list
        ),
        scan_projects_after_import=True,
        projects=[
            ScmProject(
                scm_repository_url=url,
                protected_branches=[master_branch],
                branch_to_scan_upon_creation=master_branch
            )
        ]
    )
    logger.info("finish prepare the request")
    import_response = import_code_repository(scm_import_input)
    process_id = import_response.get("processId")
    logger.info(f"request send, processId: {process_id}")
    process_percent = 0.0
    while process_percent < 100.0:
        status_response = retrieve_import_status(process_id=process_id)
        process_percent = status_response.get("percentage")
        logger.info(f"current status: {status_response}")
        time.sleep(2)


if __name__ == '__main__':
    github_org = os.getenv("GITHUB_ORG")
    logger.info(f"github organization: {github_org}")
    github_access_token = os.getenv("GITHUB_TOKEN")
    cx_one_scanners = [scanner.strip().strip("\"").strip("\'").lower()
                       for scanner in os.getenv("CX_ONE_SCANNERS").split(",")]
    repos = get_github_repos_by_org(organization=github_org, access_token=github_access_token)
    for repo in repos:
        html_url = repo.html_url
        branch = repo.default_branch
        logger.info(f"processing github repo, url: {html_url}, default branch: {branch}")
        try:
            import_github_project_into_cx_one(
                github_token=github_access_token,
                organization=github_org,
                scanners=cx_one_scanners,
                url=html_url,
                master_branch=branch
            )
        except ValueError:
            logger.error(f"Fail to import repo: {html_url}")
            continue
