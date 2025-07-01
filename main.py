from dotenv import load_dotenv
import os
import logging
load_dotenv("./happy.env", override=True)
from github import (Github, Auth)
from CheckmarxPythonSDK.CxOne import (
    batch_import_repo,
    get_all_projects,
    get_a_project_by_id,
    get_repo_by_id,
    update_repo_by_id,
)

logger = logging.getLogger("CheckmarxPythonSDK")


def get_github_repos_by_org(organization: str, access_token: str):
    # using an access token
    auth = Auth.Token(access_token)
    # Public Web Github
    g = Github(auth=auth)
    org = g.get_organization(organization)
    return org.get_repos()


if __name__ == '__main__':
    github_org = os.getenv("GITHUB_ORG")
    logger.info(f"github organization: {github_org}")
    github_access_token = os.getenv("GITHUB_TOKEN")
    cx_one_scanners = [scanner.strip().strip("\"").strip("\'").lower()
                       for scanner in os.getenv("CXONE_SCANNERS").split(",")]
    cxone_github_auth_code = os.getenv("CXONE_GITHUB_AUTH_CODE")

    repos_from_github = get_github_repos_by_org(organization=github_org, access_token=github_access_token)
    project_list = get_all_projects()
    project_name_list = [project.name for project in project_list]
    project_id_list = [project.id for project in project_list]

    repos = []
    for repo in repos_from_github:
        html_url = repo.html_url
        branch = repo.default_branch
        org_repo_name = html_url.replace("https://github.com/", "")
        repo_name = org_repo_name.split("/")[1]
        if org_repo_name in project_name_list:
            logger.info(f"repo {org_repo_name} already exist in cx one, update repo settings")
            index = project_name_list.index(org_repo_name)
            project_id = project_id_list[index]
            try:
                logger.info("get a project by id")
                project = get_a_project_by_id(project_id=project_id)
                logger.info("get a repo by id")
                repo = get_repo_by_id(repo_id=project.repoId)
                logger.info(f"turn off project {project.name} scaAutoPrEnabled")
                update_repo_by_id(repo_id=project.repoId, project_id=project_id, pay_load={
                    "branches": repo.get("branches"),
                    "kicsScannerEnabled": repo.get("kicsScannerEnabled"),
                    "sastIncrementalScan": repo.get("sastIncrementalScan"),
                    "sastScannerEnabled": repo.get("sastScannerEnabled"),
                    "scaScannerEnabled": repo.get("scaScannerEnabled"),
                    "apiSecScannerEnabled": repo.get("apiSecScannerEnabled"),
                    "url": repo.get("url"),
                    "webhookEnabled": repo.get("webhookEnabled"),
                    "prDecorationEnabled": repo.get("prDecorationEnabled"),
                    "secretsDerectionScannerEnabled": repo.get("secretsDerectionScannerEnabled"),
                    "ossfSecoreCardScannerEnabled": repo.get("ossfSecoreCardScannerEnabled"),
                    "scaAutoPrEnabled": False,
                    "webhookId": repo.get("webhookId"),
                    "sshRepoUrl": repo.get("sshRepoUrl"),
                    "sshState": "SKIPPED",
                    "isRepoAdmin": True,
                    "containerScannerEnabled": repo.get("containerScannerEnabled")
                })
            except Exception:
                logger.info(f"Failed to update project {org_repo_name} repo settings")
                continue
        else:
            repos.append({
                "id": repo_name,
                "fullName": org_repo_name,
                "url": html_url,
                "sshRepoUrl": f"git@github.com:{org_repo_name}.git",
                "defaultBranch": repo.default_branch,
            })
    if github_org and cxone_github_auth_code:
        batch_import_repo(repos=repos, origin="GITHUB", organization=github_org, auth_code=cxone_github_auth_code)
