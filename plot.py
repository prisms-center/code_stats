import matplotlib

import code_stats as cs
import copy
import datetime
import matplotlib.pyplot as plt
import numpy as np
import os
import pandas
from code_stats import GithubStats, TravisStats

# repos = {
#     "prisms-center/phaseField": "PRISMS-PF",
#     "prisms-center/plasticity": "Plasticity",
#     "prisms-center/CASMcode": "CASM",
#     "prisms-center/pbs": "PRISMS pbs",
#     "prisms-center/prisms_jobs": "PRISMS Jobs",
#     "prisms-center/IntegrationTools": "IntegrationTools",
#     "dftfeDevelopers/dftfe": "DFT-FE"}

area_plot_fmt = [
    ("prisms-center/IntegrationTools", "IntegrationTools", 'red'),
    ("prisms-center/prisms_jobs", "PRISMS Jobs", 'orange'),
    ("prisms-center/CASMcode", "CASM", 'yellow'),
    ("prisms-center/phaseField", "PRISMS-PF", 'green'),
    ("prisms-center/plasticity", "Plasticity", 'blue'),
    ("dftfeDevelopers/dftfe", "DFT-FE", 'purple')
]
legend_values = [val[1] for val in area_plot_fmt]
legend_values.reverse()

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

def get_all_weekly_stats(db, dates, col):
    df = pandas.DataFrame(index=dates, columns=db.list_repo_names())
    for repo_name in db.list_repo_names():
        curs = db.conn.cursor()
        curs.execute("SELECT day, " + col + " FROM stats WHERE repo_id=? ORDER BY day", ( db.get_repo_id(repo_name),))
        weekly_unique_views = get_weekly_stats(curs, dates, col)
        curs.close()
        df.loc[:, repo_name] = weekly_unique_views
    return df

def area_plot(df, title, fontsize=None, saveas=None):
    fig, ax = plt.subplots(figsize=(8,6))
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
    #ax.set_title(title, fontsize=fontsize)
    ax.set_ylabel(title, fontsize=fontsize)
    #ax.set_xlabel("Updated:" + str(datetime.date.today()), fontsize=fontsize)
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
            df.loc[df.loc[:, repo_name]<0, repo_name] = 0

    area_plot(df, title, saveas="images/" + colname + "_exclude_travis_builds.png", fontsize=fontsize)
    area_plot(df.cumsum(), "Cumulative " + title, fontsize=fontsize, saveas="images/" + colname + "_cumulative_exclude_travis_builds.png")


db = GithubStats()
db.connect()
dates = get_weekly_dates(db)

if not os.path.exists("images"):
    os.mkdir("images")

fontsize = 14

make_plots(db, dates, 'views', 'Weekly Views', fontsize=fontsize)
make_plots(db, dates, 'unique_views', 'Weekly Unique Views', fontsize=fontsize)
make_plots(db, dates, 'clones', 'Weekly Clones', fontsize=fontsize)
make_plots(db, dates, 'unique_clones', 'Weekly Unique Clones', fontsize=fontsize)
make_plots_excluding_travis_builds(db, dates, 'unique_clones', 'Weekly Unique Clones', fontsize=fontsize)

db.close()
