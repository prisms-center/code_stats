import code_stats as cs
import dateutil.parser
import json
import requests

# curl -H "Travis-API-Version: 3" -H "User-Agent: API Explorer" \
#   -H "Authorization: token PtlqkkHx9sNVjQr35_Wz7g" \
#   https://api.travis-ci.com/user

travis_token = cs.get_config_value("travis", "token")
print(travis_token)

domain = "https://api.travis-ci.org"

r = requests.get(
    domain + "/repos",
    headers={
        "Travis-API-Version": "3",
        "Authorization": "token " + travis_token
    })
res = r.json()
repo_ids = {}
for repo in res['repositories']:
    repo_ids[repo['slug']] = str(repo['id'])
    print(repo['slug'], repo['id'])

repos = [
    "prisms-center/phaseField",
    "prisms-center/CASMcode",
    "prisms-center/pbs",
    "prisms-center/prisms_jobs",
    "prisms-center/IntegrationTools"]

for repo_name in repos:
    print("\n\nrepo:", repo_name)
    href = "/repo/" + repo_ids[repo_name] + "/builds"
    count = 1
    build_count = {}
    # handle pagination
    while True:
        r = requests.get(
            domain + href,
            headers={
                "Travis-API-Version": "3",
                "Authorization": "token " + travis_token
            })
        res = r.json()
        for build in res['builds']:
            if build['started_at'] is not None:
                started_at = dateutil.parser.parse(build['started_at'])
                print(count, started_at.date())
                if started_at.date() not in build_count:
                    build_count[started_at.date()] = 0
                build_count[started_at.date()] += 1
                count += 1

        if '@pagination' not in res:
            print(r.text)
            raise Exception("travis builds pagination error")
        if res['@pagination']['is_last'] == True:
            break
        else:
            href = res['@pagination']['next']['@href']
    print("\nbuild count:")
    for day in sorted(build_count):
        print(day, build_count[day])
