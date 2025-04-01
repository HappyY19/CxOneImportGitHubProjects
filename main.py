import requests
import traceback
import os
import logging
import time
from github import (Github, Auth)
from CheckmarxPythonSDK.CxOne import (
    get_a_list_of_projects,
)
from typing import List


# create logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)
time_stamp_format = "%Y-%m-%dT%H:%M:%S.%fZ"


auth_code = "17bd08aa6f0dd611bc26"
referer = "https://sng.ast.checkmarx.net/applicationsAndProjects/projects?tableConfig=%7B%22search%22%3A%7B%22text%22%3A%22%22%7D%2C%22sorting%22%3A%7B%22columnKey%22%3A%22lastScanDate%22%2C%22order%22%3A%22descend%22%7D%2C%22filters%22%3A%7B%22isDeployed%22%3A%5B%22All%22%5D%7D%2C%22pagination%22%3A%7B%22pageSize%22%3A25%2C%22currentPage%22%3A1%7D%2C%22grouping%22%3A%7B%22groups%22%3A%5B%5D%2C%22groupsState%22%3A%5B%5D%7D%7D"


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


def async_import(github_org, auth_code, bearer_token, referer, repo_name, repo_full_name, repo_url, default_branch):
    url = f"https://sng.ast.checkmarx.net/api/repos-manager/scms/1/orgs/{github_org}/asyncImport"
    params = {
        "authCode": f"{auth_code}",
        "isUser": "false",
        "isOrgWebhookEnabled": "true",
        "createAstProject": "true",
        "scanAstProject": "true"
    }

    headers = {
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
        "authorization": f"{bearer_token}",
        "cache-control": "no-cache",
        "content-type": "application/json",
        "origin": "https://sng.ast.checkmarx.net",
        "pragma": "no-cache",
        "priority": "u=1, i",
        "referer": f"{referer}",
        "sec-ch-ua": '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "strict-transport-security": "max-age=31536000; includeSubDomains",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
        "webapp": "true"
    }

    data = {
        "reposFromRequest": [
            {
                "isRepoAdmin": True,
                "id": f"{repo_name}",
                "name": f"{repo_full_name}",
                "origin": "GITHUB",
                "url": f"{repo_url}",
                "branches": [
                    {
                        "name": f"{default_branch}",
                        "isDefaultBranch": True
                    }
                ],
                "kicsScannerEnabled": True,
                "sastIncrementalScan": False,
                "sastScannerEnabled": True,
                "apiSecScannerEnabled": True,
                "scaScannerEnabled": True,
                "webhookEnabled": True,
                "prDecorationEnabled": True,
                "scaAutoPrEnabled": False,
                "sshRepoUrl": f"git@github.com:{repo_full_name}.git",
                "sshState": "SKIPPED",
                "containerScannerEnabled": True,
                "ossfSecoreCardScannerEnabled": True,
                "secretsDerectionScannerEnabled": True
            }
        ],
        "orgSshKey": "",
        "orgSshState": "SKIPPED"
    }
    response = requests.post(url, params=params, headers=headers, json=data)
    logger.info(f"status_code: {response.status_code}")


if __name__ == '__main__':
    github_org = os.getenv("GITHUB_ORG")
    logger.info(f"github organization: {github_org}")
    github_access_token = os.getenv("GITHUB_TOKEN")
    cx_one_scanners = [scanner.strip().strip("\"").strip("\'").lower()
                       for scanner in os.getenv("CXONE_SCANNERS").split(",")]
    project_list = get_projects()
    project_name_list = [project.get("project_name") for project in project_list]
    from CheckmarxPythonSDK.utilities.httpRequests import auth_header
    bearer_token = auth_header.get("Authorization")
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
            async_import(
                github_org=github_org,
                auth_code=auth_code,
                bearer_token=bearer_token,
                referer=referer,
                repo_name=org_repo_name.split("/")[1],
                repo_full_name=org_repo_name,
                repo_url=html_url,
                default_branch=branch,
            )
            time.sleep(1)
        except ValueError:
            logger.error(f"Error during importing repo: {html_url}")
            logger.error(f"traceback: {traceback.format_exc()}")
