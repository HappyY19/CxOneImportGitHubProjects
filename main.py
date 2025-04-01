import json
import traceback
import os
import logging
import time
from github import (Github, Auth)
from CheckmarxPythonSDK.CxOne import (
    get_a_list_of_projects,
)
from urllib3.util import Retry
from requests import Session
from requests.adapters import HTTPAdapter
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

chunk_size = 1
auth_code = "17bd08aa6f0dd611bc26"
referer = "https://sng.ast.checkmarx.net/applicationsAndProjects/projects?tableConfig=%7B%22search%22%3A%7B%22text%22%3A%22%22%7D%2C%22sorting%22%3A%7B%22columnKey%22%3A%22lastScanDate%22%2C%22order%22%3A%22descend%22%7D%2C%22filters%22%3A%7B%22isDeployed%22%3A%5B%22All%22%5D%7D%2C%22pagination%22%3A%7B%22pageSize%22%3A25%2C%22currentPage%22%3A1%7D%2C%22grouping%22%3A%7B%22groups%22%3A%5B%5D%2C%22groupsState%22%3A%5B%5D%7D%7D"


s = Session()
retries = Retry(
    total=3,
    backoff_factor=0.1,
    status_forcelist=[502, 503, 504],
    allowed_methods={'GET', 'POST'},
)
s.mount('https://', HTTPAdapter(max_retries=retries))
s.mount('http://', HTTPAdapter(max_retries=retries))


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


def construct_repo_request(repo):
    html_url = repo.html_url
    branch = repo.default_branch
    org_repo_name = html_url.replace("https://github.com/", "")
    repo_name = org_repo_name.split("/")[1]
    return {
        "isRepoAdmin": True,
        "id": f"{repo_name}",
        "name": f"{org_repo_name}",
        "origin": "GITHUB",
        "url": f"{html_url}",
        "branches": [
            {
                "name": f"{branch}",
                "isDefaultBranch": True
            }
        ],
        "kicsScannerEnabled": True,
        "sastIncrementalScan": True,
        "sastScannerEnabled": True,
        "apiSecScannerEnabled": True,
        "scaScannerEnabled": True,
        "webhookEnabled": True,
        "prDecorationEnabled": True,
        "scaAutoPrEnabled": True,
        "sshRepoUrl": f"git@github.com:{org_repo_name}.git",
        "sshState": "SKIPPED",
        "containerScannerEnabled": True,
        "ossfSecoreCardScannerEnabled": True,
        "secretsDerectionScannerEnabled": True
    }


def async_import(github_org, auth_code, bearer_token, referer, repo_chuncks, project_name_list):
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

    repo_requests = []
    for repo in repo_chuncks:
        org_repo_name = repo.html_url.replace("https://github.com/", "")
        if org_repo_name in project_name_list:
            logger.info(f"repo {org_repo_name} already imported, ignore")
            continue
        logger.info(f"add repo name into this batch: {org_repo_name}")
        repo_requests.append(repo)
    data = {
        "reposFromRequest": [construct_repo_request(repo) for repo in repo_requests],
        "orgSshKey": "",
        "orgSshState": "SKIPPED"
    }
    if not repo_requests:
        return -1
    response = s.post(url, params=params, headers=headers, json=data, verify=False)
    logger.info(f"async import status_code: {response.status_code}")
    logger.info(f"async import request data: {data}")
    logger.info(f"async import response message: {response.content}")
    return response.status_code


def get_job_status(bearer_token):
    url = "https://sng.ast.checkmarx.net/api/ssegateway/job-status"

    headers = {
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
        "authorization": f"{bearer_token}",
        "cache-control": "no-cache",
        "pragma": "no-cache",
        "priority": "u=1, i",
        "referer": f"{referer}",
        "sec-ch-ua": '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
    }

    response = s.get(url, headers=headers, verify=False)

    # You can then work with the response
    logger.info(f"job_status, status_code: {response.status_code}")
    data_list = [json.loads(item.replace("data:", "")) for item in response.text.split("\n") if item != ""]
    job_percentage = data_list[-1].get("percentage")
    logger.info(f"current batch process: {job_percentage}")
    return job_percentage


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
    total_count = repos.totalCount
    logger.info(f"GitHub Org: {github_org}, repo total count: {total_count}")
    round_of_requests = total_count / chunk_size + 1
    round_i = 0
    while round_i < round_of_requests:
        repo_chunks = repos[round_i * chunk_size: (round_i + 1) * chunk_size]
        round_i += 1
        response_status = async_import(
            github_org=github_org,
            auth_code=auth_code,
            bearer_token=bearer_token,
            referer=referer,
            repo_chuncks=repo_chunks,
            project_name_list=project_name_list
        )
        if response_status == -1:
            continue
        percentage = 0
        while percentage < 100:
            percentage = get_job_status(bearer_token)
            time.sleep(10)
        time.sleep(120)

