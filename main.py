from dotenv import load_dotenv
import os
import logging
load_dotenv("./ATT84439.env", override=True)
from github import (Github, Auth)
from CheckmarxPythonSDK.CxOne import (
    batch_import_repo,
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
    repos = []
    for repo in repos_from_github:
        html_url = repo.html_url
        branch = repo.default_branch
        org_repo_name = html_url.replace("https://github.com/", "")
        repo_name = org_repo_name.split("/")[1]
        repos.append({
            "id": repo_name,
            "fullName": org_repo_name,
            "url": html_url,
            "sshRepoUrl": f"git@github.com:{org_repo_name}.git",
            "defaultBranch": repo.default_branch,
        })

    if github_org and cxone_github_auth_code:
        batch_import_repo(repos=repos, origin="GITHUB", organization=github_org, auth_code=cxone_github_auth_code)
