# GitHub MCP policy

Normative under `designer`. Read before using a GitHub MCP tool.

Evaluation order, exact-match semantics, and the meaning of each
classification are defined in the profile's MCP policy section. This file
supplies one thing: the classification of exact tool handles.

Groupings and ordering follow the tool inventory published by the
`github/github-mcp-server` project. A handle absent from this file is
classified `Ask` by the evaluation order. This file records a maintained
policy, not live capability discovery, so a listed handle is not a claim that
the provider currently exposes it.

## Classification basis

| Classification | Covers |
| :--- | :--- |
| Allowed | Reads of repository content, code, history, issues, pull requests, discussions, and platform metadata, plus ordinary issue, pull-request, and discussion comment operations |
| Ask | Formal pull-request review operations that do more than ordinary discussion |
| Forbidden | Mutation of repository content, branches and refs, pull-request lifecycle, merges, and other platform state |

## Actions

| Tool | Classification |
| :--- | :--- |
| `actions_get` | Allowed |
| `actions_list` | Allowed |
| `actions_run_trigger` | Forbidden |
| `get_job_logs` | Allowed |

## Code Quality

| Tool | Classification |
| :--- | :--- |
| `get_code_quality_finding` | Allowed |

## Code Security

| Tool | Classification |
| :--- | :--- |
| `get_code_scanning_alert` | Allowed |
| `list_code_scanning_alerts` | Allowed |

## Context

| Tool | Classification |
| :--- | :--- |
| `get_me` | Allowed |
| `get_team_members` | Allowed |
| `get_teams` | Allowed |

## Copilot

| Tool | Classification |
| :--- | :--- |
| `assign_copilot_to_issue` | Forbidden |
| `request_copilot_review` | Forbidden |

## Copilot Issue Intents

| Tool | Classification |
| :--- | :--- |
| `assign_copilot_to_issue_with_intent` | Forbidden |

## Dependabot

| Tool | Classification |
| :--- | :--- |
| `get_dependabot_alert` | Allowed |
| `list_dependabot_alerts` | Allowed |

## Discussions

| Tool | Classification |
| :--- | :--- |
| `discussion_comment_write` | Allowed |
| `get_discussion` | Allowed |
| `get_discussion_comments` | Allowed |
| `list_discussion_categories` | Allowed |
| `list_discussions` | Allowed |

## Gists

| Tool | Classification |
| :--- | :--- |
| `create_gist` | Forbidden |
| `get_gist` | Allowed |
| `list_gists` | Allowed |
| `update_gist` | Forbidden |

## Git

| Tool | Classification |
| :--- | :--- |
| `get_repository_tree` | Allowed |

## Issues

| Tool | Classification |
| :--- | :--- |
| `add_issue_comment` | Allowed |
| `get_label` | Allowed |
| `issue_read` | Allowed |
| `issue_write` | Forbidden |
| `list_issue_fields` | Allowed |
| `list_issue_types` | Allowed |
| `list_issues` | Allowed |
| `search_issues` | Allowed |
| `sub_issue_write` | Forbidden |

## Labels

| Tool | Classification |
| :--- | :--- |
| `get_label` | Allowed |
| `label_write` | Forbidden |
| `list_label` | Allowed |

## Notifications

| Tool | Classification |
| :--- | :--- |
| `dismiss_notification` | Forbidden |
| `get_notification_details` | Allowed |
| `list_notifications` | Allowed |
| `manage_notification_subscription` | Forbidden |
| `manage_repository_notification_subscription` | Forbidden |
| `mark_all_notifications_read` | Forbidden |

## Organizations

| Tool | Classification |
| :--- | :--- |
| `search_orgs` | Allowed |

## Projects

| Tool | Classification |
| :--- | :--- |
| `projects_get` | Allowed |
| `projects_list` | Allowed |
| `projects_write` | Forbidden |

## Pull Requests

| Tool | Classification |
| :--- | :--- |
| `add_comment_to_pending_review` | Ask |
| `add_reply_to_pull_request_comment` | Allowed |
| `create_pull_request` | Forbidden |
| `list_pull_requests` | Allowed |
| `merge_pull_request` | Forbidden |
| `pull_request_read` | Allowed |
| `pull_request_review_write` | Ask |
| `search_pull_requests` | Allowed |
| `update_pull_request` | Forbidden |
| `update_pull_request_branch` | Forbidden |

## Repositories

| Tool | Classification |
| :--- | :--- |
| `create_branch` | Forbidden |
| `create_or_update_file` | Forbidden |
| `create_repository` | Forbidden |
| `delete_file` | Forbidden |
| `delete_repository` | Forbidden |
| `fork_repository` | Forbidden |
| `get_commit` | Allowed |
| `get_file_contents` | Allowed |
| `get_latest_release` | Allowed |
| `get_release_by_tag` | Allowed |
| `get_tag` | Allowed |
| `list_branches` | Allowed |
| `list_commits` | Allowed |
| `list_releases` | Allowed |
| `list_repository_collaborators` | Allowed |
| `list_tags` | Allowed |
| `push_files` | Forbidden |
| `search_code` | Allowed |
| `search_commits` | Allowed |
| `search_repositories` | Allowed |

## Secret Protection

| Tool | Classification |
| :--- | :--- |
| `get_secret_scanning_alert` | Allowed |
| `list_secret_scanning_alerts` | Allowed |

## Security Advisories

| Tool | Classification |
| :--- | :--- |
| `get_global_security_advisory` | Allowed |
| `list_global_security_advisories` | Allowed |
| `list_org_repository_security_advisories` | Allowed |
| `list_repository_security_advisories` | Allowed |

## Stargazers

| Tool | Classification |
| :--- | :--- |
| `list_starred_repositories` | Allowed |
| `star_repository` | Forbidden |
| `unstar_repository` | Forbidden |

## Users

| Tool | Classification |
| :--- | :--- |
| `search_users` | Allowed |

## Additional tools in the remote server

### Copilot

| Tool | Classification |
| :--- | :--- |
| `create_pull_request_with_copilot` | Forbidden |

### Copilot Spaces

| Tool | Classification |
| :--- | :--- |
| `get_copilot_space` | Allowed |
| `list_copilot_spaces` | Allowed |

### GitHub Support Docs Search

| Tool | Classification |
| :--- | :--- |
| `github_support_docs_search` | Allowed |

## Classification notes

`issue_write` is `Forbidden` because the same handle creates and updates pull
requests, and pull-request lifecycle mutation is forbidden.

`add_comment_to_pending_review` and `pull_request_review_write` are `Ask`
because a formal review carries a verdict beyond ordinary discussion.
`add_issue_comment` and `add_reply_to_pull_request_comment` are the narrower
handles that supply the ordinary discussion operation, so approval is required
only when the formal form is genuinely needed.

`get_label` is published in two toolsets. Both entries carry the same
classification, so no handle is classified more than one way.
