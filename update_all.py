from code_stats import GithubStats, TravisStats

repos = [
    "prisms-center/phaseField",
    "prisms-center/plasticity",
    "prisms-center/CASMcode",
    "prisms-center/pbs",
    "prisms-center/prisms_jobs",
    "prisms-center/IntegrationTools",
    "prisms-center/Fatigue"
    "dftfeDevelopers/dftfe"]

def update_all(db_cls, repos):
    print("begin update_all:", str(db_cls))
    db = db_cls()
    db.connect()
    for repo_name in repos:
        db.add_repo(repo_name)
    db.update_stats()
    # for repo_name in db.list_repo_names():
    #     print("Repository:", repo_name)
    #     db.print_stats(repo_name)
    db.close()

update_all(GithubStats, repos)
update_all(TravisStats, repos)
