
# before running:
# wget -O dftfeDevelopers_github_stats.txt https://raw.githubusercontent.com/dftfeDevelopers/clone-scrapper/clone-scrapper/github_stats.txt

import dateutil.parser
import re
from code_stats import toordinal, GithubStats, TravisStats
from github import Github

orgs = {
    "prisms-center": {
        "repos": [
            "prisms-center/phaseField",
            "prisms-center/plasticity",
            "prisms-center/CASMcode",
            "prisms-center/pbs",
            "prisms-center/prisms_jobs",
            "prisms-center/IntegrationTools"],
        "file": "legacy_data/prisms-center_github_stats.txt"
    },
    "dftfeDevelopers": {
        "repos": [
            "dftfeDevelopers/dftfe"],
        "file": "legacy_data/dftfeDevelopers_github_stats.txt"
    }
}

def create_from_legacy(orgname, repos, f):
    print("Working on:", orgname)
    db = GithubStats()
    db.connect()
    for repo_name in repos:
        db.add_repo(repo_name)
    print(db.list_repo_names())

    repo_name = None
    repo_id = None
    for line in f.readlines():
        m = re.match("(.*) Daily Statistics:", line)
        if m:
            repo_name = orgname + "/" + m.group(1)
            repo_id = db.get_repo_id(repo_name)
            # print(repo_name, repo_id)

        # type 1:
        # 2016-02-02 19:00:00 -0500	2	2	0	0
        # type 2:
        # 2018-10-27T00	0		0		0		0
        words = line.split()
        if not len(words):
            continue
        res = None
        m = re.match("[0-9]{4}-[0-9]{2}-[0-9]{2}", words[0])
        if m:
            res = dateutil.parser.parse(words[0])
        m = re.match("[0-9]{4}-[0-9]{2}-[0-9]{2}T00", words[0])
        if m:
            res = dateutil.parser.parse(words[0])
        if res:
            try:
                day = toordinal(res.date())
                if len(words) == 7:
                    words = [words[0]] + words[3:7]
                if words[1:5] == ["0"]*4:
                    continue
                record = {
                    'views': int(words[1]),
                    'unique_views': int(words[2]),
                    'clones': int(words[3]),
                    'unique_clones': int(words[4])
                }
                # print(res.date(), repo_id, day, record, words)
                db._insert_or_update_stats(repo_id, day, record)
                db.conn.commit()
            except:
                print(line)
                print(words)
                raise Exception("parse legacy data error")

    # for repo_name in db.list_repo_names():
    #     print("Repository:", repo_name)
    #     db.print_stats(repo_name)
    db.close()

for orgname in orgs:
    org = orgs[orgname]
    with open(org["file"], 'r') as f:
        create_from_legacy(orgname, org["repos"], f)
