import os
import git


def get_git_infos():
    try:
        repo = git.Repo(path=os.getcwd(), search_parent_directories=True)
    except git.InvalidGitRepositoryError:
        return None, None, None, None, False
    try:
        active_branch = str(repo.active_branch.name)
    except TypeError:
        active_branch = 'DETACHED'
    sha = str(repo.head.object.hexsha)
    short_sha = str(repo.git.rev_parse(sha, short=7))
    try:
        origin = str(repo.git.execute(['git',
                                       'config',
                                       '--get',
                                       'remote.origin.url']))
    except git.exc.GitCommandError:
        origin = None
    uncommitted_changes = repo.is_dirty()
    return active_branch, short_sha, sha, origin, uncommitted_changes


def add_git_infos_to_dict(metadata_dict):
    git_infos = {
        'GitActiveBranch': active_branch,
        'GitShortSHA': short_sha,
        'GitUncommittedChanges': uncommitted_changes    
    }
    metadata_dict.update(git_infos)
    return metadata_dict


active_branch, short_sha, sha, origin, uncommitted_changes = get_git_infos()

if __name__ == '__main__':
    print(f'Active branch: {active_branch}')
    print(f'Short SHA: {short_sha}')
    print(f'SHA: {sha}')
    print(f'Origin: {origin}')
    print(f'Uncommitted changes: {uncommitted_changes}')

