"""Define GitLab class and utilities."""

import json
import os
import sys
from pathlib import Path

import gitlab


class GitlabSync:
    """A GitLab interface."""

    CONFIG = "cookiecutter.json"
    OWNER = "GITLAB_OWNER_USERNAME"
    TOKEN = "GITLAB_PRIVATE_TOKEN"
    URL = "https://gitlab.com"

    def __init__(self, *args, **kwargs):
        """Initialize the instance."""
        try:
            private_token = os.environ[self.TOKEN]
        except KeyError:
            sys.exit(f"The environment variable '{self.TOKEN}' is missing.")
        try:
            self.gl = gitlab.Gitlab(self.URL, private_token=private_token)
        except NameError:
            sys.exit("The 'python-gitlab' package is missing.")
        try:
            self.gl.auth()
        except gitlab.exceptions.GitlabAuthenticationError:
            sys.exit(f"The environment variable '{self.TOKEN}' is not correct.")
        file_path = Path(self.CONFIG)
        file_content = json.loads(file_path.read_text())
        try:
            self.group_slug = file_content["gitlab_group_slug"]
            self.project_slug = file_content["project_slug"]
            self.project_name = file_content["project_name"]
        except KeyError:
            sys.exit(f"File {file_path} is empty or incomplete.")

    def get_group(self):
        """Get gitlab group."""
        for p in self.gl.groups.list(search=self.group_slug):
            if p.path == self.group_slug:
                return p
        return None

    def create_group(self):
        """Create a GitLab group."""
        self.group = self.gl.groups.create(
            {"name": self.project_name, "path": self.group_slug}
        )
        group_link = f"https://{self.group.path}.gitlab.io"
        pipeline_badge_link = "/%{project_path}/pipelines"
        pipeline_badge_image_url = (
            "/%{project_path}/badges/%{default_branch}/pipeline.svg"
        )
        self.group.badges.create(
            {
                "link_url": f"{self.URL}{pipeline_badge_link}",
                "image_url": f"{self.URL}{pipeline_badge_image_url}",
            }
        )
        self.orchestrator = self.gl.projects.create(  # noqa
            {"name": "Orchestrator", "namespace_id": self.group.id}
        )
        self.backend = self.gl.projects.create(  # noqa
            {"name": "Backend", "namespace_id": self.group.id}
        )
        coverage_badge_image_url = (
            "/%{project_path}/badges/%{default_branch}/coverage.svg"
        )
        self.group.badges.create(
            {
                "link_url": f"{group_link}/{self.backend.path}",
                "image_url": f"{self.URL}{coverage_badge_image_url}",
            }
        )
        self.frontend = self.gl.projects.create(  # noqa
            {"name": "Frontend", "namespace_id": self.group.id}
        )

    def set_default_branch(self):
        """Set default branch."""
        self.orchestrator.default_branch = "develop"
        self.orchestrator.save()
        self.backend.default_branch = "develop"
        self.backend.save()
        self.frontend.default_branch = "develop"
        self.frontend.save()

    def set_owner(self):
        """Add gitlab user as owner to gitlab group."""
        try:
            owner = os.environ[self.OWNER]
        except KeyError:
            print(f"The environment variable '{self.OWNER}' is missing.")
        else:
            try:
                user = self.gl.users.list(username=owner.strip())[0]
            except IndexError:
                print(f"Owner {owner} doesn't exists on gitlab.")
            else:
                self.group.members.create(
                    {"user_id": user.id, "access_level": gitlab.OWNER_ACCESS}
                )
                print(f"Owner '{owner}' added to group '{self.group.name}'.")

    def set_members(self):
        """Add given gitlab users as mantainer to gitlab group."""
        members = input(
            "Insert the gitlab usernames of all mantainer you want to add to the group "
            "(separated by comma or empty to skip): "
        )
        for member in members.split(","):
            try:
                user = self.gl.users.list(username=member.strip())[0]
            except IndexError:
                print(f"{member} doesn't exists. Please add him from gitlab.com")
            else:
                self.group.members.create(
                    {"user_id": user.id, "access_level": gitlab.MAINTAINER_ACCESS}
                )
                print(f"Member '{member}' added to group '{self.group.name}'")

    def git_init(self):
        """Initialize local git repository."""
        os.system(f"./scripts/git_init.sh {self.orchestrator.ssh_url_to_repo}")
        os.system(
            "cd backend && ../scripts/git_init.sh " f"{self.backend.ssh_url_to_repo}"
        )
        os.system(
            "cd frontend && ../scripts/git_init.sh " f"{self.frontend.ssh_url_to_repo}"
        )

    def update_readme(self):
        """Update README.md replacing the Gitlab group placeholder with group slug."""
        filepath = Path("README.md")
        filedata = filepath.read_text()
        filedata = filedata.replace("__GITLAB_GROUP__", self.group_slug)
        filepath.write_text(filedata)

    def run(self):
        """Run the main process operations."""
        self.create_group()
        self.update_readme()
        self.set_owner()
        self.set_members()
        self.git_init()
        self.set_default_branch()


if __name__ == "__main__":
    gl = GitlabSync()
    gl.run()
