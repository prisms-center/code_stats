"""
Create and update sqlite databases with daily open source project stats
"""

import datetime
import dateutil.parser
import json
import os
import os.path
import requests
import sqlite3


def config_dir():
    return os.environ.get(
        "PRISMS_CODE_STATS_DIR", os.path.join(os.environ["HOME"], ".prisms_code_stats")
    )


def config_path():
    return os.path.join(config_dir(), "config.json")


def read_config():
    if not os.path.isfile(config_path()):
        with open(config_path(), "w") as f:
            json.dump({}, f)
    with open(config_path(), "r") as f:
        return json.load(f)


def write_config(config):
    with open(config_path(), "w") as f:
        json.dump(config, f)


def get_config_value(name, key):
    """
    :param name: str, i.e. "github"
    :param key: str, i.e. "token"
    """
    config = read_config()
    if name not in config:
        config[name] = {key: None}
        write_config(config)
    return config[name][key]


def set_config_value(name, token, value):
    """
    :param name: str, i.e. "github"
    :param key: str, i.e. "token"
    :param value: str, i.e. "abc123"
    """
    config = read_config()
    if name not in config:
        config[name] = {key: None}
    config[name][key] = token
    write_config(config)


def toordinal(date):
    return date.toordinal()


def fromordinal(day):
    return datetime.date.fromordinal(day)


def code_stats_prefix():
    if not os.path.exists("data"):
        os.mkdir("data")
    return os.path.join(os.getcwd(), "data")


def list_tables(conn):
    return list(
        conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()[0]
    )


def insert_str(record):
    colstr = "("
    questionstr = "("
    val = []
    for key, value in record.items():
        colstr = colstr + key + ", "
        questionstr = questionstr + "?, "
        val.append(value)
    colstr = colstr[:-2] + ")"
    questionstr = questionstr[:-2] + ")"
    return colstr, questionstr, tuple(val)


def update_str(record):
    setstr = ""
    val = []
    for key, value in record.items():
        setstr = setstr + key + "=?, "
        val.append(value)
    setstr = setstr[:-2]
    return setstr, tuple(val)


def add_defaults(record, default_values):
    for key in default_values.keys():
        if key not in record:
            record[key] = default_values[key]
    return record


# get table info:
# conn = sqlite3.connect('database.db')
# conn.row_factory = sqlite3.Row
# curs = conn.cursor()
# curs.execute("PRAGMA table_info('repos')")
# curs.fetchone().keys()
# curs.close()


class StatsBase(object):
    """
    Requires derived class implements:
        @staticmethod _shortname(self) -> str, i.e. "github"
        @staticmethod _repos_colinfo(self) -> list of str, for ALTER TABLE
        @staticmethod _stats_colinfo(self) -> list of str, for ALTER TABLE
    """

    def _db(self):
        return os.path.join(code_stats_prefix(), self._shortname() + "_stats.db")

    def connect(self):
        if not os.path.isfile(self._db()):
            self.conn = sqlite3.connect(self._db())
            self.conn.row_factory = sqlite3.Row

            # self.conn.execute("CREATE TABLE repos (repo_id INTEGER PRIMARY KEY, name TEXT UNIQUE)")
            create_str = "CREATE TABLE repos (repo_id INTEGER PRIMARY KEY"
            for colinfo in self._repos_colinfo():
                create_str += ", " + colinfo
            create_str += ")"
            self.conn.execute(create_str)

            # self.conn.execute("CREATE TABLE stats (record_id INTEGER PRIMARY KEY, repo_id INT, day INT, views INT, unique_views INT, clones INT, unique_clones INT, stargazers_count INT, watchers_count INT, forks_count INT)")
            create_str = "CREATE TABLE stats (record_id INTEGER PRIMARY KEY"
            for colinfo in self._stats_colinfo():
                create_str += ", " + colinfo
            create_str += ")"
            self.conn.execute(create_str)

            self.conn.commit()
        else:
            self.conn = sqlite3.connect(self._db())
            self.conn.row_factory = sqlite3.Row

    def add_repos_column(self, colinfo):
        self.conn.execute("ALTER TABLE repos ADD COLUMN " + colinfo)
        self.conn.commit()

    def add_stats_column(self, colinfo):
        self.conn.execute("ALTER TABLE stats ADD COLUMN " + colinfo)
        self.conn.commit()

    def close(self):
        self.conn.close()

    def add_repo(self, repo_name):
        result = self.conn.execute(
            "SELECT * FROM repos WHERE name=?", (repo_name,)
        ).fetchall()
        if len(result):
            return
        self.conn.execute("INSERT INTO repos (name) VALUES (?)", (repo_name,))
        self.conn.commit()

    def get_repo_id(self, repo_name):
        record = self.conn.execute(
            "SELECT * FROM repos WHERE name=?", (repo_name,)
        ).fetchone()
        if record is None:
            return record
        else:
            return record["repo_id"]

    def remove_repo(self, repo_name):
        repo_id = self.get_repo_id(repo_name)
        if repo_id is None:
            raise Exception("Cannot remove repo '" + repo_name + "': does not exist")
        else:
            self.conn.execute("DELETE FROM stats WHERE repo_id=?", (repo_id,))
            self.conn.execute("DELETE FROM repos WHERE repo_id=?", (repo_id,))
            self.conn.commit()

    def list_repo_names(self):
        return [r["name"] for r in self.conn.execute("SELECT * FROM repos").fetchall()]

    def print_repos(self):
        for record in self.conn.execute("SELECT * FROM repos").fetchall():
            print(dict(record))

    def print_stats(self, repo_name):
        repo_id = self.get_repo_id(repo_name)
        for record in self.conn.execute(
            "SELECT * FROM stats WHERE repo_id=? ORDER BY day ", (repo_id,)
        ).fetchall():
            print(dict(record))

    def _insert_or_update_stats(self, repo_id, day, record):
        """
        INSERT INTO, if record with repo_id and day does not exist, otherwise UPDATE

        :param repo_id: integer, repo_id
        :param day: integer, ordinal day, as from `toordinal`
        :param record: dict, data to be inserted
        """
        existing = self.conn.execute(
            "SELECT * FROM stats WHERE repo_id=? AND day=?", (repo_id, day)
        ).fetchall()
        if len(existing) > 1:
            for existing_record in existing:
                print(str(existing_record))
            raise Exception(
                "Multiple "
                + self._shortname()
                + " stats records with same repo_id and day"
            )
        elif len(existing) == 0:
            record["repo_id"] = repo_id
            record["day"] = day
            (colstr, questionstr, valtuple) = insert_str(record)
            self.conn.execute(
                "INSERT INTO stats " + colstr + " VALUES " + questionstr, valtuple
            )
        else:
            (setstr, valtuple) = update_str(record)
            self.conn.execute(
                "UPDATE stats SET " + setstr + " WHERE record_id=?",
                valtuple + (existing[0]["record_id"],),
            )


from github import Github
from github.GithubException import GithubException

# github API:
#   traffic requires a token with "repo" scope


class GithubStats(StatsBase):
    @staticmethod
    def _shortname():
        return "github"

    @staticmethod
    def _repos_colinfo():
        return ["name TEXT UNIQUE"]

    @staticmethod
    def _stats_colinfo():
        return [
            "repo_id INT",
            "day INT",
            "views INT",
            "unique_views INT",
            "clones INT",
            "unique_clones INT",
            "stargazers_count INT",
            "watchers_count INT",
            "forks_count INT",
        ]

    def update_stats(self):
        g = Github(get_config_value(self._shortname(), "token"))

        # for each repo in 'repos' database:
        repos = [repo for repo in self.conn.execute("SELECT * FROM repos").fetchall()]
        for repo in repos:
            repo_id = repo["repo_id"]
            repo_name = repo["name"]

            repo = g.get_repo(repo_name)

            try:
                # request views traffic from GitHub
                views_traffic = repo.get_views_traffic()

                if "views" in views_traffic:
                    for view in views_traffic["views"]:
                        day = toordinal(view.timestamp.date())
                        record = {"views": view.count, "unique_views": view.uniques}
                        self._insert_or_update_stats(repo_id, day, record)
                self.conn.commit()
            except GithubException as e:
                print("error:", repo_name, e.data["message"])
                if e.data["message"] == "Must have push access to repository":
                    continue
                raise e

            try:
                # request clone traffic from Github
                clones_traffic = repo.get_clones_traffic()

                if "clones" in clones_traffic:
                    for clone in clones_traffic["clones"]:
                        day = toordinal(clone.timestamp.date())
                        record = {"clones": clone.count, "unique_clones": clone.uniques}
                        self._insert_or_update_stats(repo_id, day, record)
                self.conn.commit()
            except GithubException as e:
                print("error:", repo_name, e.data["message"])
                if e.data["message"] == "Must have push access to repository":
                    continue
                raise e

            # repo stats - today only
            repo_stats = {
                "stargazers_count": repo.stargazers_count,
                "forks_count": repo.forks_count,
                "watchers_count": repo.watchers_count,
            }
            day = toordinal(datetime.date.today())
            self._insert_or_update_stats(repo_id, day, repo_stats)
            self.conn.commit()


class TravisStats(StatsBase):

    def __init__(self, domain="https://api.travis-ci.org"):
        self.domain = domain
        self.token = get_config_value(self._shortname(), "token")

    @staticmethod
    def _shortname():
        return "travis"

    @staticmethod
    def _repos_colinfo():
        return ["name TEXT UNIQUE", "travis_id INT"]

    @staticmethod
    def _stats_colinfo():
        return ["repo_id INT", "day INT", "build_count INT"]

    def get_travis_ids(self):
        """
        :return repo_ids: dict of {slug: travis_id}
        """
        r = requests.get(
            self.domain + "/repos",
            headers={"Travis-API-Version": "3", "Authorization": "token " + self.token},
        )
        res = r.json()
        repo_ids = {}
        for repo in res["repositories"]:
            repo_ids[repo["slug"]] = str(repo["id"])
        return repo_ids

    def _check_travis_ids(self):
        # for each repo in 'repos' database:
        repos = [repo for repo in self.conn.execute("SELECT * FROM repos").fetchall()]
        travis_ids = None
        for repo in repos:
            name = repo["name"]
            repo_id = repo["repo_id"]
            if repo["travis_id"] is None:
                if travis_ids is None:
                    travis_ids = self.get_travis_ids()
                # maybe some repos don't get tracked by travis...
                if name not in travis_ids:
                    continue
                travis_id = int(travis_ids[name])
                (setstr, valtuple) = update_str({"travis_id": travis_id})
                self.conn.execute(
                    "UPDATE repos SET " + setstr + " WHERE repo_id=?",
                    valtuple + (repo_id,),
                )
                self.conn.commit()
                break
        return

    def get_build_counts(self, travis_id):
        href = "/repo/" + str(travis_id) + "/builds"
        build_counts = {}
        # handle pagination
        while True:
            r = requests.get(
                self.domain + href,
                headers={
                    "Travis-API-Version": "3",
                    "Authorization": "token " + self.token,
                },
            )
            res = r.json()
            for build in res["builds"]:
                if build["started_at"] is not None:
                    started_at = dateutil.parser.parse(build["started_at"])
                    if started_at.date() not in build_counts:
                        build_counts[started_at.date()] = 0
                    build_counts[started_at.date()] += 1

            if "@pagination" not in res:
                print(r.text)
                raise Exception("travis builds pagination unexpected behavior")
            if res["@pagination"]["is_last"] == True:
                break
            else:
                href = res["@pagination"]["next"]["@href"]
        return build_counts

    def update_stats(self):
        self._check_travis_ids()
        repos = [repo for repo in self.conn.execute("SELECT * FROM repos").fetchall()]

        for repo in repos:
            name = repo["name"]
            repo_id = repo["repo_id"]
            travis_id = repo["travis_id"]

            if travis_id is None:
                continue

            build_counts = self.get_build_counts(repo["travis_id"])
            if build_counts is None:
                print(name, " build_counts:", build_counts)
                continue

            for date in build_counts:
                build_count = build_counts[date]
                day = toordinal(date)
                self._insert_or_update_stats(repo_id, day, {"build_count": build_count})
            self.conn.commit()


def anaconda_org_stats_db():
    return os.path.join(code_stats_prefix(), "anaconda_org_stats.db")
