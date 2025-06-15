#!/usr/bin/env python3

import getpass
import json
import time

import click

from github import Github
from github.GithubException import GithubException
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.theme import Theme

# Constants
DEFAULT_ORG = "Kicksaw-Consulting"

# Create a custom theme for consistent styling
custom_theme = Theme(
    {
        "info": "cyan",
        "success": "green",
        "warning": "yellow",
        "error": "bold red",
        "highlight": "bold blue",
    }
)

# Create a console instance with our theme
console = Console(theme=custom_theme)


def get_github_client(token):
    """Get an authenticated GitHub client."""
    if not token:
        console.print(
            "[warning]GitHub token not found in environment or command line arguments.[/warning]"
        )
        token = getpass.getpass("Please enter your GitHub token: ")
        if not token:
            console.print("[error]Error: GitHub token is required.[/error]")
            return None
    return Github(token)


# Default access configuration for repositories in the DEFAULT_ORG organization
DEFAULT_ACCESS_CONFIG = [
    {"name": "engineering", "type": "team", "permission": "maintain"},
    {"name": "gigic31", "type": "user", "permission": "admin"},
    {"name": "kicksaw", "type": "team", "permission": "read"},
    {"name": "tsabat", "type": "user", "permission": "admin"},
]


def setup_repository_access(repo, organization, access_config=None):
    """
    Set up repository access rights for teams and users.

    Args:
        repo: The GitHub repository object
        organization: The GitHub organization object
        access_config: List of dictionaries with access configuration
                      [{"name": "name", "type": "team|user", "permission": "admin|maintain|push|triage|pull"}]

    Returns:
        bool: True if successful, False otherwise
    """
    if access_config is None:
        access_config = DEFAULT_ACCESS_CONFIG

    console.print(
        Panel.fit(
            "Setting up repository access rights...",
            title="Repository Access",
            border_style="info",
        )
    )

    # First, get all teams in the organization to validate team names
    try:
        all_teams = {team.slug: team for team in organization.get_teams()}
        console.print(
            f"Found [highlight]{len(all_teams)}[/highlight] teams in organization '[highlight]{organization.login}[/highlight]'"
        )
    except GithubException as e:
        console.print(
            f"Warning: Could not fetch teams from organization: {e.data.get('message', str(e))}"
        )
        all_teams = {}

    for entry in access_config:
        name = entry["name"]
        entry_type = entry["type"]
        permission = entry["permission"]

        try:
            if entry_type == "team":
                team_slug = name.lower()
                if team_slug in all_teams:
                    team = all_teams[team_slug]
                    try:
                        # Use the non-deprecated method
                        team.update_team_repository(repo, permission)
                        console.print(
                            f"✓ Granted {permission} access to team '@{organization.login}/{name}'"
                        )
                    except GithubException as e:
                        console.print(
                            f"✗ Failed to grant access to team '@{organization.login}/{name}': {e.data.get('message', str(e))}"
                        )
                else:
                    available_teams = (
                        ", ".join(all_teams.keys()) if all_teams else "none found"
                    )
                    console.print(
                        f"✗ Team '{name}' not found in organization '{organization.login}'. Available teams: {available_teams}"
                    )
            elif entry_type == "user":
                try:
                    # First check if user exists
                    try:
                        _user = repo._requester.requestJsonAndCheck(
                            "GET", f"/users/{name}"
                        )[1]

                        # Add collaborator
                        repo.add_to_collaborators(name, permission)
                        console.print(f"✓ Granted {permission} access to user '{name}'")
                    except GithubException as e:
                        if e.status == 404:
                            console.print(f"✗ User '{name}' not found")
                        else:
                            console.print(
                                f"✗ Failed to grant access to user '{name}': {e.data.get('message', str(e))}"
                            )
                except GithubException as e:
                    console.print(
                        f"✗ Failed to grant access to user '{name}': {e.data.get('message', str(e))}"
                    )
            else:
                console.print(f"✗ Unknown entry type '{entry_type}' for '{name}'")
        except Exception as e:
            console.print(f"✗ Error setting up access for {entry_type} '{name}': {e!s}")

    return True


def setup_branch_protection(repo, branches_config=None):
    """
    Set up branch protection rules for specified branches.

    Args:
        repo: The GitHub repository object
        branches_config: List of dictionaries with branch protection configuration
                        [{
                            "name": "branch_name",
                            "require_pr": bool,
                            "allow_bypass": bool,
                            "require_code_owner_reviews": bool,
                            "bypass_pull_request_allowances": {
                                "users": list[str],
                                "teams": list[str]
                            }
                        }]

    Returns:
        bool: True if successful, False otherwise
    """
    if branches_config is None:
        # Default branch protection for main, staging, secure, and development
        branches_config = [
            {
                "name": "main",
                "require_pr": True,
                "allow_bypass": False,
                "require_code_owner_reviews": True,
                "teams_bypass_pull_request_allowances": ["engineering"],
            },
            {
                "name": "staging",
                "require_pr": True,
                "allow_bypass": False,
                "require_code_owner_reviews": True,
                "teams_bypass_pull_request_allowances": ["engineering"],
            },
            {
                "name": "secure",
                "require_pr": True,
                "allow_bypass": False,
                "require_code_owner_reviews": True,
                "teams_bypass_pull_request_allowances": ["engineering"],
            },
            {
                "name": "development",
                "require_pr": True,
                "allow_bypass": True,
                "require_code_owner_reviews": True,
                "teams_bypass_pull_request_allowances": ["engineering"],
            },
        ]

    console.print(
        Panel.fit(
            "Setting up branch protection rules...",
            title="Branch Protection",
            border_style="info",
        )
    )

    for branch_config in branches_config:
        branch_name = branch_config["name"]
        require_pr = branch_config["require_pr"]
        allow_bypass = branch_config["allow_bypass"]

        try:
            # Check if branch exists
            try:
                repo.get_branch(branch_name)
            except Exception:
                console.print(
                    f"[error]✗ Branch '[highlight]{branch_name}[/highlight]' not found, skipping protection setup[/error]"
                )
                continue

            console.print(
                f"Setting up protection for branch '[highlight]{branch_name}[/highlight]'..."
            )

            branch = repo.get_branch(branch_name)

            # Using the correct parameters according to PyGithub documentation
            # First, set up the basic protection with the updated signature
            branch.edit_protection(
                enforce_admins=not allow_bypass,
                required_linear_history=True,
                allow_force_pushes=False,
                allow_deletions=False,
                require_code_owner_reviews=branch_config.get(
                    "require_code_owner_reviews", False
                ),
                teams_bypass_pull_request_allowances=branch_config.get(
                    "teams_bypass_pull_request_allowances", []
                ),
            )

            # Then, if pull requests are required, set up the PR review requirements
            if require_pr:
                branch.edit_required_pull_request_reviews(
                    dismiss_stale_reviews=True,
                    require_code_owner_reviews=branch_config.get(
                        "require_code_owner_reviews", False
                    ),
                )

            if require_pr:
                console.print(
                    f"[success]✓ Branch '[highlight]{branch_name}[/highlight]' protected: Pull request required before merging[/success]"
                )
                if branch_config.get("require_code_owner_reviews", False):
                    console.print(
                        f"[success]✓ Branch '[highlight]{branch_name}[/highlight]' requires code owner reviews[/success]"
                    )
                bypass_teams = branch_config.get(
                    "teams_bypass_pull_request_allowances", []
                )
                if bypass_teams:
                    console.print(
                        f"[info]✓ Branch '[highlight]{branch_name}[/highlight]' allows bypass for teams: {', '.join(bypass_teams)}[/info]"
                    )
            if allow_bypass:
                console.print(
                    f"[warning]✓ Branch '[highlight]{branch_name}[/highlight]' allows admins to bypass restrictions[/warning]"
                )
            else:
                console.print(
                    f"[success]✓ Branch '[highlight]{branch_name}[/highlight]' enforces restrictions for all users including admins[/success]"
                )

        except Exception as e:
            console.print(
                f"[error]✗ Error setting up protection for branch '[highlight]{branch_name}[/highlight]': {e!s}[/error]"
            )

    return True


def wait_with_spinner(seconds, message):
    """Display a spinner while waiting."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task(description=message, total=None)
        time.sleep(seconds)


def set_repo_variables(repo, variables: dict):
    """
    Add GitHub Actions repository variables using PyGithub's proper methods.

    Args:
        repo: The GitHub repository object
        variables: Dictionary of variable names and values to set
    """
    for name, value in variables.items():
        try:
            # Use PyGithub's create_variable method
            repo.create_variable(name, str(value))
            console.print(f"[success]✓ Variable '{name}' set successfully[/success]")

        except GithubException as e:
            # If variable already exists, we might need to update it
            if e.status == 409:  # Conflict - variable already exists
                try:
                    # Get the existing variable and update it
                    existing_var = repo.get_variable(name)
                    existing_var.edit(str(value))
                    console.print(
                        f"[success]✓ Variable '{name}' updated successfully[/success]"
                    )
                except GithubException as update_error:
                    console.print(
                        f"[error]✗ Failed to update variable '{name}': {update_error.data.get('message', str(update_error))}[/error]"
                    )
            else:
                console.print(
                    f"[error]✗ Failed to set variable '{name}': {e.data.get('message', str(e))}[/error]"
                )
        except Exception as e:
            console.print(
                f"[error]✗ Unexpected error setting variable '{name}': {e!s}[/error]"
            )


@click.group()
def cli():
    """GitHub repository and branch management tools."""
    pass


@cli.command()
@click.option(
    "--org",
    default=DEFAULT_ORG,
    help=f"GitHub organization name (default: {DEFAULT_ORG})",
)
@click.option(
    "--token",
    envvar="GITHUB_TOKEN",
    help="GitHub personal access token (can also be set via GITHUB_TOKEN env var)",
)
@click.option(
    "--repo-name",
    required=True,
    help="Repository name (required)",
)
@click.option("--description", default="", help="Repository description")
@click.option(
    "--setup-access/--no-setup-access",
    default=True,
    help="Set up repository access rights (default: True)",
)
@click.option(
    "--access-config",
    help="JSON string with access configuration (overrides default)",
)
@click.option(
    "--setup-protection/--no-setup-protection",
    default=True,
    help="Set up branch protection rules (default: True)",
)
@click.option(
    "--protection-config",
    help="JSON string with branch protection configuration (overrides default)",
)
@click.option(
    "--aws-region",
    required=True,
    help="AWS region for repository variables (required)",
)
@click.option(
    "--aws-account-id",
    required=True,
    help="AWS account ID for repository variables (required)",
)
def create_repo(
    org,
    token,
    repo_name,
    description,
    setup_access,
    access_config,
    setup_protection,
    protection_config,
    aws_region,
    aws_account_id,
):
    """
    Create a new GitHub repository in the specified organization.

    The repository will be created as private with auto-initialization enabled.

    Example:
        python create_repos_and_branches.py create-repo my-new-repo --description "My new project repository"
    """
    g = get_github_client(token)
    if not g:
        return 1

    try:
        organization = g.get_organization(org)

        console.print(
            Panel.fit(
                f"Creating repository '[highlight]{repo_name}[/highlight]' in organization '[highlight]{org}[/highlight]'...",
                title="Repository Creation",
                border_style="info",
            )
        )

        repo = organization.create_repo(
            name=repo_name,
            description=description,
            private=True,
            has_issues=True,
            has_wiki=True,
            has_projects=True,
            auto_init=True,
        )

        console.print(
            f"[success]✓ Repository created successfully:[/success] [link={repo.html_url}]{repo.html_url}[/link]"
        )
        set_repo_variables(
            repo,
            {"AWS_REGION": aws_region, "AWS_ACCOUNT_ID": aws_account_id},
        )

        # Set up access rights if requested
        if setup_access:
            config = None
            if access_config:
                try:
                    config = json.loads(access_config)
                except json.JSONDecodeError:
                    console.print("[error]Error: Invalid JSON in access_config[/error]")
                    return 1

            # Wait a moment for GitHub to fully initialize the repository
            wait_with_spinner(
                3, "Waiting for repository initialization before setting up access..."
            )
            setup_repository_access(repo, organization, config)

        # Set up branch protection if requested
        if setup_protection:
            config = None
            if protection_config:
                try:
                    config = json.loads(protection_config)
                except json.JSONDecodeError:
                    console.print(
                        "[error]Error: Invalid JSON in protection_config[/error]"
                    )
                    return 1

            # Wait a moment for GitHub to fully initialize the repository
            wait_with_spinner(
                3,
                "Waiting for repository initialization before setting up branch protection...",
            )
            setup_branch_protection(repo, config)

        # Final success message
        console.print(
            Panel.fit(
                f"[success]✓ Repository '[highlight]{repo_name}[/highlight]' successfully created[/success]",
                title="Setup Complete",
                border_style="success",
            )
        )
        return 0

    except GithubException as e:
        console.print(f"Error creating repository: {e.data.get('message', str(e))}")
        return 1
    except Exception as e:
        console.print(f"Unexpected error: {e!s}")
        return 1


@cli.command()
@click.option(
    "--org",
    default=DEFAULT_ORG,
    help=f"GitHub organization name (default: {DEFAULT_ORG})",
)
@click.option(
    "--token",
    envvar="GITHUB_TOKEN",
    help="GitHub personal access token (can also be set via GITHUB_TOKEN env var)",
)
@click.option(
    "--repo-name",
    required=True,
    help="Repository name (required)",
)
@click.option(
    "--source-branch",
    default="main",
    help="Source branch to create new branches from (default: main)",
)
@click.option(
    "--branches",
    default="staging,development,production,secure",
    help="Comma-separated list of branches to create (default: staging,development,production,secure)",
)
@click.option(
    "--setup-protection/--no-setup-protection",
    default=True,
    help="Set up branch protection rules (default: True)",
)
@click.option(
    "--protection-config",
    help="JSON string with branch protection configuration (overrides default)",
)
@click.option(
    "--aws-region",
    required=True,
    help="AWS region for repository variables (required)",
)
@click.option(
    "--aws-account-id",
    required=True,
    help="AWS account ID for repository variables (required)",
)
def create_branches(  # noqa: PLR0911
    org,
    token,
    repo_name,
    source_branch,
    branches,
    setup_protection,
    protection_config,
    aws_region,
    aws_account_id,
):
    """
    Create multiple branches in an existing repository.

    By default, creates staging, development, and production branches from the main branch.

    Example:
        python create_repos_and_branches.py create-branches my-repo
        python create_repos_and_branches.py create-branches my-repo --source-branch master --branches "qa,dev,prod"
    """
    g = get_github_client(token)
    if not g:
        return 1

    try:
        organization = g.get_organization(org)

        try:
            repo = organization.get_repo(repo_name)
        except GithubException:
            console.print(
                f"[error]Error: Repository '[highlight]{repo_name}[/highlight]' not found in organization '[highlight]{org}[/highlight]'[/error]"
            )
            return 1

        console.print(
            f"Fetching source branch '[highlight]{source_branch}[/highlight]'..."
        )
        try:
            source_ref = repo.get_git_ref(f"heads/{source_branch}")
        except GithubException:
            console.print(
                f"[error]Error: Source branch '[highlight]{source_branch}[/highlight]' not found in repository '[highlight]{repo_name}[/highlight]'[/error]"
            )
            return 1

        source_sha = source_ref.object.sha

        # Parse the comma-separated list of branches
        branch_list = [b.strip() for b in branches.split(",") if b.strip()]
        if not branch_list:
            console.print("[error]Error: No valid branches specified[/error]")
            return 1

        console.print(
            Panel.fit(
                f"Creating branches in repository '[highlight]{repo_name}[/highlight]'",
                title="Branch Creation",
                border_style="info",
            )
        )

        for branch in branch_list:
            try:
                try:
                    repo.get_git_ref(f"heads/{branch}")
                    console.print(
                        f"[warning]Branch '[highlight]{branch}[/highlight]' already exists, skipping...[/warning]"
                    )
                    continue
                except GithubException:
                    # Branch doesn't exist, we can create it
                    pass

                console.print(
                    f"Creating branch '[highlight]{branch}[/highlight]' from '[highlight]{source_branch}[/highlight]'..."
                )
                repo.create_git_ref(f"refs/heads/{branch}", source_sha)
                console.print(
                    f"[success]✓ Branch '[highlight]{branch}[/highlight]' created successfully[/success]"
                )

                # Small delay to avoid rate limiting
                time.sleep(0.5)

            except GithubException as e:
                console.print(
                    f"[error]✗ Error creating branch '[highlight]{branch}[/highlight]': {e.data.get('message', str(e))}[/error]"
                )

        console.print(
            f"[success]✓ Branch creation completed for repository:[/success] [link={repo.html_url}]{repo.html_url}[/link]"
        )

        # Set up branch protection if requested
        if setup_protection:
            config = None
            if protection_config:
                try:
                    config = json.loads(protection_config)
                except json.JSONDecodeError:
                    console.print("Error: Invalid JSON in protection_config")
                    return 1

            # Wait a moment for GitHub to fully initialize the branches
            wait_with_spinner(
                3, "Waiting for branch initialization before setting up protection..."
            )
            setup_branch_protection(repo, config)

        # Final success message
        console.print(
            Panel.fit(
                f"[success]✓ Branches successfully created in repository:[/success] [link={repo.html_url}]{repo.html_url}[/link]",
                title="Setup Complete",
                border_style="success",
            )
        )

        set_repo_variables(
            repo,
            {"AWS_REGION": aws_region, "AWS_ACCOUNT_ID": aws_account_id},
        )

        return 0

    except GithubException as e:
        console.print(f"Error: {e.data.get('message', str(e))}")
        return 1
    except Exception as e:
        console.print(f"Unexpected error: {e!s}")
        return 1


@cli.command()
@click.option(
    "--org",
    default=DEFAULT_ORG,
    help=f"GitHub organization name (default: {DEFAULT_ORG})",
)
@click.option(
    "--token",
    envvar="GITHUB_TOKEN",
    help="GitHub personal access token (can also be set via GITHUB_TOKEN env var)",
)
@click.option(
    "--repo-name",
    required=True,
    help="Repository name (required)",
)
@click.option("--description", default="", help="Repository description")
@click.option(
    "--branches",
    default="staging,development,production,secure",
    help="Comma-separated list of branches to create (default: staging,development,production,secure)",
)
@click.option(
    "--setup-access/--no-setup-access",
    default=True,
    help="Set up repository access rights (default: True)",
)
@click.option(
    "--access-config",
    help="JSON string with access configuration (overrides default)",
)
@click.option(
    "--setup-protection/--no-setup-protection",
    default=True,
    help="Set up branch protection rules (default: True)",
)
@click.option(
    "--protection-config",
    help="JSON string with branch protection configuration (overrides default)",
)
@click.option(
    "--aws-region",
    required=True,
    help="AWS region for repository variables (required)",
)
@click.option(
    "--aws-account-id",
    required=True,
    help="AWS account ID for repository variables (required)",
)
def create_repo_with_branches(  # noqa: PLR0911
    org,
    token,
    repo_name,
    description,
    branches,
    setup_access,
    access_config,
    setup_protection,
    protection_config,
    aws_region,
    aws_account_id,
):
    """Create a new GitHub repository with branches in the specified organization."""
    g = get_github_client(token)
    if not g:
        return 1

    try:
        organization = g.get_organization(org)

        console.print(
            Panel.fit(
                f"Creating repository '[highlight]{repo_name}[/highlight]' in organization '[highlight]{org}[/highlight]'...",
                title="Repository Creation",
                border_style="info",
            )
        )

        repo = organization.create_repo(
            name=repo_name,
            description=description,
            private=True,
            has_issues=True,
            has_wiki=True,
            has_projects=True,
            auto_init=True,
        )

        console.print(
            f"[success]✓ Repository created successfully:[/success] [link={repo.html_url}]{repo.html_url}[/link]"
        )
        set_repo_variables(
            repo,
            {"AWS_REGION": aws_region, "AWS_ACCOUNT_ID": aws_account_id},
        )

        # Set up access rights if requested
        if setup_access:
            config = None
            if access_config:
                try:
                    config = json.loads(access_config)
                except json.JSONDecodeError:
                    console.print("[error]Error: Invalid JSON in access_config[/error]")
                    return 1

            # Wait a moment for GitHub to fully initialize the repository
            wait_with_spinner(
                3, "Waiting for repository initialization before setting up access..."
            )
            setup_repository_access(repo, organization, config)

    except GithubException as e:
        console.print(
            f"[error]Error creating repository: {e.data.get('message', str(e))}[/error]"
        )
        return 1
    except Exception as e:
        console.print(f"[error]Unexpected error: {e!s}[/error]")
        return 1

    # Wait a moment for GitHub to fully initialize the repository
    wait_with_spinner(
        3, "Waiting for repository initialization before creating branches..."
    )

    # Then create the branches
    try:
        source_branch = "main"
        console.print(
            f"Fetching source branch '[highlight]{source_branch}[/highlight]'..."
        )
        try:
            source_ref = repo.get_git_ref(f"heads/{source_branch}")
        except GithubException:
            console.print(
                f"[error]Error: Source branch '[highlight]{source_branch}[/highlight]' not found in repository '[highlight]{repo_name}[/highlight]'[/error]"
            )
            return 1

        source_sha = source_ref.object.sha

        # Parse the comma-separated list of branches
        branch_list = [b.strip() for b in branches.split(",") if b.strip()]
        if not branch_list:
            console.print("[error]Error: No valid branches specified[/error]")
            return 1

        console.print(
            Panel.fit(
                f"Creating branches in repository '[highlight]{repo_name}[/highlight]'",
                title="Branch Creation",
                border_style="info",
            )
        )

        for branch in branch_list:
            try:
                try:
                    repo.get_git_ref(f"heads/{branch}")
                    console.print(
                        f"[warning]Branch '[highlight]{branch}[/highlight]' already exists, skipping...[/warning]"
                    )
                    continue
                except GithubException:
                    # Branch doesn't exist, we can create it
                    pass

                console.print(
                    f"Creating branch '[highlight]{branch}[/highlight]' from '[highlight]{source_branch}[/highlight]'..."
                )
                repo.create_git_ref(f"refs/heads/{branch}", source_sha)
                console.print(
                    f"[success]✓ Branch '[highlight]{branch}[/highlight]' created successfully[/success]"
                )

                # Small delay to avoid rate limiting
                time.sleep(0.5)

            except GithubException as e:
                console.print(
                    f"[error]✗ Error creating branch '[highlight]{branch}[/highlight]': {e.data.get('message', str(e))}[/error]"
                )

        console.print(
            f"[success]✓ Branch creation completed for repository:[/success] [link={repo.html_url}]{repo.html_url}[/link]"
        )

        # Set up branch protection if requested
        if setup_protection:
            config = None
            if protection_config:
                try:
                    config = json.loads(protection_config)
                except json.JSONDecodeError:
                    console.print(
                        "[error]Error: Invalid JSON in protection_config[/error]"
                    )
                    return 1

            # Wait a moment for GitHub to fully initialize the branches
            wait_with_spinner(
                3, "Waiting for branch initialization before setting up protection..."
            )
            setup_branch_protection(repo, config)

        # Final success message
        console.print(
            Panel.fit(
                f"[success]✓ Repository '[highlight]{repo_name}[/highlight]' successfully created with branches and protection rules[/success]",
                title="Setup Complete",
                border_style="success",
            )
        )

        set_repo_variables(
            repo,
            {"AWS_REGION": aws_region, "AWS_ACCOUNT_ID": aws_account_id},
        )

        return 0

    except GithubException as e:
        console.print(f"[error]Error: {e.data.get('message', str(e))}[/error]")
        return 1
    except Exception as e:
        console.print(f"[error]Unexpected error: {e!s}[/error]")
        return 1


@cli.command()
@click.option(
    "--org",
    default=DEFAULT_ORG,
    help=f"GitHub organization name (default: {DEFAULT_ORG})",
)
@click.option(
    "--token",
    envvar="GITHUB_TOKEN",
    help="GitHub personal access token (can also be set via GITHUB_TOKEN env var)",
)
@click.option(
    "--repo-name",
    required=True,
    help="Repository name (required)",
)
@click.option(
    "--access-config",
    help="JSON string with access configuration (overrides default)",
)
def setup_access(org, token, repo_name, access_config):
    """Set up repository access rights for an existing repository."""
    g = get_github_client(token)
    if not g:
        return 1

    try:
        organization = g.get_organization(org)
        try:
            repo = organization.get_repo(repo_name)
        except GithubException:
            console.print(
                f"[error]Error: Repository '[highlight]{repo_name}[/highlight]' not found in organization '[highlight]{org}[/highlight]'[/error]"
            )
            return 1

        config = None
        if access_config:
            try:
                config = json.loads(access_config)
            except json.JSONDecodeError:
                console.print("[error]Error: Invalid JSON in access_config[/error]")
                return 1

        setup_repository_access(repo, organization, config)

        # Final success message
        console.print(
            Panel.fit(
                f"[success]✓ Access rights successfully configured for repository '[highlight]{repo_name}[/highlight]'[/success]",
                title="Setup Complete",
                border_style="success",
            )
        )
        return 0

    except GithubException as e:
        console.print(f"[error]Error: {e.data.get('message', str(e))}[/error]")
        return 1
    except Exception as e:
        console.print(f"[error]Unexpected error: {e!s}[/error]")
        return 1


@cli.command()
@click.option(
    "--org",
    default=DEFAULT_ORG,
    help=f"GitHub organization name (default: {DEFAULT_ORG})",
)
@click.option(
    "--token",
    envvar="GITHUB_TOKEN",
    help="GitHub personal access token (can also be set via GITHUB_TOKEN env var)",
)
def list_teams(org, token):
    """List all teams in the specified organization."""
    g = get_github_client(token)
    if not g:
        return 1

    try:
        organization = g.get_organization(org)

        console.print(
            Panel.fit(
                f"Teams in organization '[highlight]{org}[/highlight]'",
                title="Team Listing",
                border_style="info",
            )
        )

        teams = list(organization.get_teams())

        if not teams:
            console.print("[warning]No teams found.[/warning]")
            return 0

        # Create a table
        table = Table(show_header=True, header_style="bold")
        table.add_column("Team Name")
        table.add_column("Slug")
        table.add_column("Description")

        for team in teams:
            description = team.description or ""
            if len(description) > 50:
                description = description[:47] + "..."
            table.add_row(team.name, team.slug, description)

        console.print(table)
        console.print(
            "\n[info]Use the 'slug' value in the access configuration.[/info]"
        )
        return 0

    except GithubException as e:
        console.print(f"[error]Error: {e.data.get('message', str(e))}[/error]")
        return 1
    except Exception as e:
        console.print(f"[error]Unexpected error: {e!s}[/error]")
        return 1


@cli.command()
@click.option(
    "--org",
    default=DEFAULT_ORG,
    help=f"GitHub organization name (default: {DEFAULT_ORG})",
)
@click.option(
    "--token",
    envvar="GITHUB_TOKEN",
    help="GitHub personal access token (can also be set via GITHUB_TOKEN env var)",
)
@click.option(
    "--repo-name",
    required=True,
    help="Repository name (required)",
)
@click.option(
    "--protection-config",
    help="JSON string with branch protection configuration (overrides default)",
)
def setup_protection(org, token, repo_name, protection_config):
    """Set up branch protection rules for an existing repository."""
    g = get_github_client(token)
    if not g:
        return 1

    try:
        organization = g.get_organization(org)
        try:
            repo = organization.get_repo(repo_name)
        except GithubException:
            console.print(
                f"[error]Error: Repository '[highlight]{repo_name}[/highlight]' not found in organization '[highlight]{org}[/highlight]'[/error]"
            )
            return 1

        config = None
        if protection_config:
            try:
                config = json.loads(protection_config)
            except json.JSONDecodeError:
                console.print("[error]Error: Invalid JSON in protection_config[/error]")
                return 1

        setup_branch_protection(repo, config)

        # Final success message
        console.print(
            Panel.fit(
                f"[success]✓ Branch protection rules successfully configured for repository '[highlight]{repo_name}[/highlight]'[/success]",
                title="Setup Complete",
                border_style="success",
            )
        )
        return 0

    except GithubException as e:
        console.print(f"[error]Error: {e.data.get('message', str(e))}[/error]")
        return 1
    except Exception as e:
        console.print(f"[error]Unexpected error: {e!s}[/error]")
        return 1


@cli.command()
@click.option(
    "--org",
    default=DEFAULT_ORG,
    help=f"GitHub organization name (default: {DEFAULT_ORG})",
)
@click.option(
    "--token",
    envvar="GITHUB_TOKEN",
    help="GitHub personal access token (can also be set via GITHUB_TOKEN env var)",
)
@click.option(
    "--repo-name",
    required=True,
    help="Repository name (required)",
)
@click.option(
    "--confirm/--no-confirm",
    default=True,
    help="Require confirmation before deletion (default: True)",
)
def delete_repo(org, token, repo_name, confirm):
    """Delete a GitHub repository from the specified organization.

    WARNING: This action is irreversible. Use with caution.
    """
    g = get_github_client(token)
    if not g:
        return 1

    try:
        organization = g.get_organization(org)

        try:
            repo = organization.get_repo(repo_name)
        except GithubException:
            console.print(
                f"[error]Error: Repository '[highlight]{repo_name}[/highlight]' not found in organization '[highlight]{org}[/highlight]'[/error]"
            )
            return 1

        # Show warning and ask for confirmation
        console.print(
            Panel.fit(
                f"[error]WARNING: You are about to delete the repository '[highlight]{repo_name}[/highlight]' from organization '[highlight]{org}[/highlight]'.[/error]\n"
                f"[error]This action is IRREVERSIBLE and all repository data will be permanently lost.[/error]",
                title="⚠️ DANGER: Repository Deletion ⚠️",
                border_style="error",
            )
        )

        if confirm:
            confirmation = input(
                f"To confirm deletion, type the repository name '{repo_name}': "
            )
            if confirmation != repo_name:
                console.print(
                    "[warning]Deletion cancelled: Repository name did not match.[/warning]"
                )
                return 1

        # Perform the deletion
        console.print(f"Deleting repository '[highlight]{repo_name}[/highlight]'...")
        repo.delete()

        # Final success message
        console.print(
            Panel.fit(
                f"[success]✓ Repository '[highlight]{repo_name}[/highlight]' has been permanently deleted from organization '[highlight]{org}[/highlight]'[/success]",
                title="Deletion Complete",
                border_style="success",
            )
        )
        return 0

    except GithubException as e:
        console.print(
            f"[error]Error deleting repository: {e.data.get('message', str(e))}[/error]"
        )
        return 1
    except Exception as e:
        console.print(f"[error]Unexpected error: {e!s}[/error]")
        return 1


if __name__ == "__main__":
    cli()
