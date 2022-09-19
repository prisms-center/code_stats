import inspect

import matplotlib

import code_stats as cs
import copy
import datetime
import matplotlib.pyplot as plt
import numpy as np
import os
import pandas
from code_stats import GithubStats, TravisStats

import pandas.plotting

pandas.plotting.register_matplotlib_converters()


def fromisoformat(d):
    if hasattr(datetime.date, 'fromisformat') and inspect.isfunction(datetime.date.fromisoformat):
        return datetime.date.fromisoformat(d)
    return datetime.strptime(d, "%Y-%m-%d")


# repos = {
#     "prisms-center/phaseField": "PRISMS-PF",
#     "prisms-center/plasticity": "Plasticity",
#     "prisms-center/CASMcode": "CASM",
#     "prisms-center/pbs": "PRISMS pbs",
#     "prisms-center/prisms_jobs": "PRISMS Jobs",
#     "prisms-center/IntegrationTools": "IntegrationTools",
#     "dftfeDevelopers/dftfe": "DFT-FE"}

area_plot_fmt = [
    # ("prisms-center/IntegrationTools", "IntegrationTools", 'red'),
    ("prisms-center/prisms_jobs", "PRISMS Jobs", 'orange'),
    ("prisms-center/CASMcode", "CASM", 'yellow'),
    ("prisms-center/phaseField", "PRISMS-PF", 'green'),
    ("prisms-center/plasticity", "Plasticity", 'blue'),
    ("dftfeDevelopers/dftfe", "DFT-FE", 'purple'),
    ("prisms-center/Fatigue", "Fatigue", 'red')
]
legend_values = [val[1] for val in area_plot_fmt]
legend_values.reverse()

reference_weeks = [fromisoformat(x) for x in [
    '2020-08-28',  # before
    '2020-09-04',
    '2020-09-11',
    '2020-09-18',
    '2020-09-25',
    '2020-10-02',
    '2020-10-09',
    '2020-10-16',
    '2021-05-28',  # after
    '2021-06-04',
    '2021-06-11',
    '2021-06-18',
    '2021-06-25',
    '2021-07-02',
    '2021-07-09',
    '2021-07-16']
                   ]
replacement_weeks_first = fromisoformat('2020-10-23')
replacement_weeks_last = fromisoformat('2021-05-21')

reference_weeks_2 = [fromisoformat(x) for x in [
    '2022-04-08',  # before
    '2022-04-15',
    '2022-04-22',
    '2022-04-29',
    '2022-05-06',
    '2022-05-13',
    '2022-05-20',
    '2022-05-27']
                     ]
replacement_repos_2 = [
    "prisms-center/phaseField",
    "prisms-center/plasticity",
    "prisms-center/pbs",
    "prisms-center/prisms_jobs",
    "prisms-center/IntegrationTools"
]
replacement_weeks_2_first = fromisoformat('2022-06-03')
replacement_weeks_2_last = fromisoformat('2022-09-09')

# estimate missing data due to failure of clonescraper
replacement_repos_3 = [
    "dftfeDevelopers/dftfe"
]
replacement_weeks_3_mean = {'views': 150, 'unique_views': 15, 'clones': 5, 'unique_clones': 4, 'build_count': 0}
replacement_weeks_3_first = fromisoformat('2021-04-02')
replacement_weeks_3_last = fromisoformat('2021-09-17')

# estimate missing data due to bug in code_stats
replacement_repos_4 = [
    "dftfeDevelopers/dftfe"
]
replacement_weeks_4_mean = {'views': 300, 'unique_views': 30, 'clones': 10, 'unique_clones': 8, 'build_count': 0}
replacement_weeks_4_first = fromisoformat('2021-10-29')
replacement_weeks_4_last = fromisoformat('2022-09-23')

# estimate missing data due to bug in code_stats, using last 2 weeks data
replacement_repos_5 = [
    "prisms-center/Fatigue"
]
replacement_weeks_5_mean = {'views': 150, 'unique_views': 15, 'clones': 5.5, 'unique_clones': 3.5, 'build_count': 0}
replacement_weeks_5_first = fromisoformat('2021-10-29')
replacement_weeks_5_last = fromisoformat('2022-09-23')


def sql_iter(curs, fetchsize=1000):
    """ Iterate over the results of a SELECT statement """
    while True:
        records = curs.fetchmany(fetchsize)
        if not records:
            break
        else:
            for r in records:
                yield r


def get_first_day(db):
    return db.conn.execute("SELECT day FROM stats ORDER BY day").fetchone()['day']


def get_last_day(db):
    return db.conn.execute("SELECT day FROM stats ORDER BY day DESC").fetchone()['day']


def get_weekly_dates(db, day_index=4):
    date = cs.fromordinal(get_first_day(db))
    while date.weekday() != day_index:
        date += datetime.timedelta(days=1)
    dates = [date]
    last_date = cs.fromordinal(get_last_day(db))
    while True:
        date += datetime.timedelta(weeks=1)
        dates.append(date)
        if date > last_date:
            break
    return dates


def get_weekly_stats(curs, dates, col):
    i = 0
    result = [0] * len(dates)
    count = 0
    day_i = cs.toordinal(dates[i])
    for rec in sql_iter(curs):
        try:
            day = rec['day']
            if rec[col] is None:
                n = 0
            else:
                n = rec[col]
            if day <= day_i:
                count += n
            else:
                result[i] = count
                count = n
                while day > day_i:
                    i += 1
                    day_i = cs.toordinal(dates[i])
                    if len(dates) == i:
                        return result
        except Exception as e:
            print(dict(rec))
            raise e
    return result


def get_all_weekly_stats(db, dates, col, estimate_missing=True):
    repo_names = [entry[0] for entry in area_plot_fmt]
    df = pandas.DataFrame(index=dates, columns=db.list_repo_names())
    for repo_name in db.list_repo_names():
        curs = db.conn.cursor()
        curs.execute("SELECT day, " + col + " FROM stats WHERE repo_id=? ORDER BY day", (db.get_repo_id(repo_name),))
        weekly_unique_views = get_weekly_stats(curs, dates, col)
        curs.close()
        df.loc[:, repo_name] = weekly_unique_views

        if estimate_missing:
            reference_weeks_mean = np.mean(df.loc[reference_weeks, repo_name])

            for index, row in df.iterrows():
                if index >= replacement_weeks_first and index <= replacement_weeks_last:
                    df.loc[index, repo_name] = reference_weeks_mean

            reference_weeks_2_mean = np.mean(df.loc[reference_weeks_2, repo_name])
            if repo_name in replacement_repos_2:
                for index, row in df.iterrows():
                    if index >= replacement_weeks_2_first and index <= replacement_weeks_2_last:
                        df.loc[index, repo_name] = reference_weeks_2_mean

            if repo_name in replacement_repos_3:
                for index, row in df.iterrows():
                    if index >= replacement_weeks_3_first and index <= replacement_weeks_3_last:
                        df.loc[index, repo_name] = replacement_weeks_3_mean[col]

            if repo_name in replacement_repos_4:
                for index, row in df.iterrows():
                    if index >= replacement_weeks_4_first and index <= replacement_weeks_4_last:
                        df.loc[index, repo_name] = replacement_weeks_4_mean[col]

            if repo_name in replacement_repos_5:
                for index, row in df.iterrows():
                    if index >= replacement_weeks_5_first and index <= replacement_weeks_5_last:
                        df.loc[index, repo_name] = replacement_weeks_5_mean[col]

    return df


def area_plot(df, title, fontsize=None, saveas=None):
    fig, ax = plt.subplots(figsize=(10, 6))
    plt.tick_params(axis='both', which='major', labelsize=fontsize)
    fig.autofmt_xdate()
    cumsum_bottom = np.zeros(df.shape[0])
    linewidth = 2
    legend_handles = []
    for val in area_plot_fmt:
        repo_name = val[0]
        facecolor = val[2]
        cumsum_top = cumsum_bottom + df.loc[:, repo_name]
        h1 = ax.fill_between(df.index.values, cumsum_bottom, cumsum_top, facecolor=facecolor)
        h2 = ax.plot(df.index.values, cumsum_top, color='black', linewidth=1)
        h3 = ax.fill(np.NaN, np.NaN, facecolor=facecolor, linewidth=0.0)
        legend_handles.append((h3[0],))
        cumsum_bottom = copy.deepcopy(cumsum_top)
    ax.plot(df.index.values, np.zeros(df.shape[0]), color='black', linewidth=1, label=None)
    # ax.set_title(title, fontsize=fontsize)
    ax.set_ylabel(title, fontsize=fontsize)
    # ax.set_xlabel("Updated:" + str(datetime.date.today()), fontsize=fontsize)
    legend_handles.reverse()
    ax.legend(legend_handles, legend_values, loc='upper left', fontsize=fontsize)
    if saveas:
        plt.savefig(saveas)
    return ax


def make_plots(db, dates, colname, title, fontsize=None):
    df = get_all_weekly_stats(db, dates, colname)
    df.loc[:, "prisms-center/prisms_jobs"] += df.loc[:, "prisms-center/pbs"]
    df = df.drop(axis='columns', labels="prisms-center/pbs")

    area_plot(df, title, fontsize=fontsize, saveas="images/" + colname + ".png")
    print(title, colname)
    dfc = df.cumsum()
    for col in dfc.columns:
        print(dfc[col])
    area_plot(df.cumsum(), "Cumulative " + title, fontsize=fontsize, saveas="images/" + colname + "_cumulative.png")


def make_plots_excluding_travis_builds(db, dates, colname, title, fontsize=None):
    df = get_all_weekly_stats(db, dates, colname)
    df.loc[:, "prisms-center/prisms_jobs"] += df.loc[:, "prisms-center/pbs"]
    df = df.drop(axis='columns', labels="prisms-center/pbs")

    travis_db = TravisStats()
    travis_db.connect()
    travis_df = get_all_weekly_stats(travis_db, dates, "build_count")
    travis_db.close()

    # if a >= b: -> max(a-b,0)
    for repo_name in travis_df.columns:
        if repo_name in df.columns:
            df.loc[:, repo_name] = df.loc[:, repo_name] - travis_df.loc[:, repo_name]
            df.loc[df.loc[:, repo_name] < 0, repo_name] = 0

    area_plot(df, title, saveas="images/" + colname + "_exclude_travis_builds.png", fontsize=fontsize)
    area_plot(df.cumsum(), "Cumulative " + title, fontsize=fontsize,
              saveas="images/" + colname + "_cumulative_exclude_travis_builds.png")


def print_data_by_week(db, repo_name, col):
    dates = get_weekly_dates(db)
    df = pandas.DataFrame(index=dates, columns=[repo_name])
    for repo_name in [repo_name]:
        curs = db.conn.cursor()
        curs.execute("SELECT day, " + col + " FROM stats WHERE repo_id=? ORDER BY day", (db.get_repo_id(repo_name),))
        weekly_stats = get_weekly_stats(curs, dates, col)
        curs.close()
        df.loc[:, repo_name] = weekly_stats
    for i in range(df.shape[0]):
        print(dates[i], df[repo_name][i])


db = GithubStats()
db.connect()
dates = get_weekly_dates(db)

if not os.path.exists("images"):
    os.mkdir("images")

fontsize = 14

# prisms-center/CASMcode
# prisms-center/phaseField
# dftfeDevelopers/dftfe
print_data_by_week(db, "dftfeDevelopers/dftfe", 'unique_clones')

make_plots(db, dates, 'views', 'Weekly Views', fontsize=fontsize)
make_plots(db, dates, 'unique_views', 'Weekly Unique Views', fontsize=fontsize)
make_plots(db, dates, 'clones', 'Weekly Clones', fontsize=fontsize)
make_plots(db, dates, 'unique_clones', 'Weekly Unique Clones', fontsize=fontsize)
make_plots_excluding_travis_builds(db, dates, 'unique_clones', 'Weekly Unique Clones', fontsize=fontsize)

db.close()
