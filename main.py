import traceback
import os
import logging
import time
from github import (Github, Auth)
from CheckmarxPythonSDK.CxOne import (
    get_a_list_of_projects,
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


def extract_project_info_from_api_response(project_collection):
    return [
        {
            "project_id": project.id,
            "project_name": project.name,
        }
        for project in project_collection.projects
    ]


def get_projects() -> List[dict]:
    projects = []
    offset = 0
    limit = 100
    page = 1
    project_collection = get_a_list_of_projects(offset=offset, limit=limit)
    total_count = int(project_collection.totalCount)
    projects.extend(extract_project_info_from_api_response(project_collection))
    if total_count > limit:
        while True:
            offset = page * limit
            if offset >= total_count:
                break
            project_collection = get_a_list_of_projects(offset=offset, limit=limit)
            page += 1
            projects.extend(extract_project_info_from_api_response(project_collection))
    return projects


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
                       for scanner in os.getenv("CXONE_SCANNERS").split(",")]
    project_list = get_projects()
    project_name_list = [project.get("project_name") for project in project_list]
    repos = get_github_repos_by_org(organization=github_org, access_token=github_access_token)
    for repo in repos:
        html_url = repo.html_url
        branch = repo.default_branch
        org_repo_name = html_url.replace("https://github.com/", "")
        if org_repo_name in project_name_list:
            logger.info(f"repo {org_repo_name} already imported, ignore")
            continue
        logger.info(f"processing github repo, url: {html_url}, default branch: {branch}, project_name: {org_repo_name}")
        try:
            import_github_project_into_cx_one(
                github_token=github_access_token,
                organization=github_org,
                scanners=cx_one_scanners,
                url=html_url,
                master_branch=branch
            )
        except ValueError:
            logger.error(f"Error during importing repo: {html_url}")
            logger.error(f"traceback: {traceback.format_exc()}")
