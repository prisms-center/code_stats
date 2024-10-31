import copy
import matplotlib.pyplot as plt
import numpy as np
import os
import pandas
from code_stats import GithubStats, TravisStats
from code_stats_data import (
    area_plot_fmt,
    get_all_weekly_stats,
    get_weekly_dates,
    get_weekly_stats,
    legend_values,
)

import pandas.plotting

pandas.plotting.register_matplotlib_converters()


def area_plot(df, title, fontsize=None, saveas=None):
    fig, ax = plt.subplots(figsize=(10, 6))
    plt.tick_params(axis="both", which="major", labelsize=fontsize)
    fig.autofmt_xdate()
    cumsum_bottom = np.zeros(df.shape[0])
    linewidth = 2
    legend_handles = []
    date = np.array(df.index.values, dtype=np.datetime64)
    for val in area_plot_fmt:
        repo_name = val[0]
        facecolor = val[2]
        cumsum_top = cumsum_bottom + np.array(df.loc[:, repo_name], dtype=np.float64)

        h1 = ax.fill_between(date, cumsum_bottom, cumsum_top, facecolor=facecolor)
        h2 = ax.plot(date, cumsum_top, color="black", linewidth=1)
        h3 = ax.fill(np.NaN, np.NaN, facecolor=facecolor, linewidth=0.0)
        legend_handles.append((h3[0],))
        cumsum_bottom = copy.deepcopy(cumsum_top)
    ax.plot(date, np.zeros(df.shape[0]), color="black", linewidth=1, label=None)
    # ax.set_title(title, fontsize=fontsize)
    ax.set_ylabel(title, fontsize=fontsize)
    # ax.set_xlabel("Updated:" + str(datetime.date.today()), fontsize=fontsize)
    legend_handles.reverse()
    ax.legend(legend_handles, legend_values, loc="upper left", fontsize=fontsize)
    if saveas:
        plt.savefig(saveas)
    return ax


def make_plots(db, dates, colname, title, fontsize=None, estimate_missing=True):
    df = get_all_weekly_stats(db, dates, colname, estimate_missing=estimate_missing)
    df.loc[:, "prisms-center/prisms_jobs"] += df.loc[:, "prisms-center/pbs"]
    df = df.drop(axis="columns", labels="prisms-center/pbs")
    area_plot(df, title, fontsize=fontsize, saveas="images/" + colname + ".png")
    dfc = df.cumsum()

    # print(title, colname)
    # for col in dfc.columns:
    #     print(dfc[col])
    #     print(f"~~~ {col} ~~~")
    #     for i in range(df.shape[0]):
    #         print(dfc.index[i], df[col][i], sum(df[col][:i]))
    #     print()

    header = f"Cumulative {title} {dfc.index[-1]}"
    print(header)
    print("~" * len(header))
    for col in dfc.columns:
        print(f"{col}: ", dfc[col].iloc[-1])
    print("--> Sum:", sum(dfc.iloc[-1, :]))
    print()

    area_plot(
        df.cumsum(),
        "Cumulative " + title,
        fontsize=fontsize,
        saveas="images/" + colname + "_cumulative.png",
    )


def make_plots_excluding_travis_builds(
    db, dates, colname, title, fontsize=None, estimate_missing=True
):
    df = get_all_weekly_stats(db, dates, colname, estimate_missing=estimate_missing)
    df.loc[:, "prisms-center/prisms_jobs"] += df.loc[:, "prisms-center/pbs"]
    df = df.drop(axis="columns", labels="prisms-center/pbs")

    travis_db = TravisStats()
    travis_db.connect()
    travis_df = get_all_weekly_stats(travis_db, dates, "build_count")
    travis_db.close()

    # if a >= b: -> max(a-b,0)
    for repo_name in travis_df.columns:
        if repo_name in df.columns:
            df.loc[:, repo_name] = df.loc[:, repo_name] - travis_df.loc[:, repo_name]
            df.loc[df.loc[:, repo_name] < 0, repo_name] = 0

    area_plot(
        df,
        title,
        saveas="images/" + colname + "_exclude_travis_builds.png",
        fontsize=fontsize,
    )

    dfc = df.cumsum()
    area_plot(
        dfc,
        "Cumulative " + title,
        fontsize=fontsize,
        saveas="images/" + colname + "_cumulative_exclude_travis_builds.png",
    )

    header = f"Cumulative {title} (Excluding travis builds) {dfc.index[-1]}"
    print(header)
    print("~" * len(header))
    for col in dfc.columns:
        print(f"{col}: ", dfc[col].iloc[-1])
    print("--> Sum:", sum(dfc.iloc[-1, :]))
    print()
    with open('stats.html', 'w') as f:
        f.write('<div class="software-area">\n')
        f.write('    <img src="assets/code_stats/unique_clones_cumulative_exclude_travis_builds.png">\n')
        f.write(f"    <h3>{header}</h3>\n")
        f.write("<ul>\n")
        for col in dfc.columns:
            count = int(dfc[col].iloc[-1])
            f.write(f"   <li>{col}:{count}</li>\n")
        f.write("</ul>\n")
        total_count = int(sum(dfc.iloc[-1, :]))
        f.write(f"<span>Total: {total_count}</span>\n")
        f.write('</div>\n')

def print_data_by_week(db, repo_name, col):
    dates = get_weekly_dates(db)
    df = pandas.DataFrame(index=dates, columns=[repo_name])
    for repo_name in [repo_name]:
        curs = db.conn.cursor()
        curs.execute(
            "SELECT day, " + col + " FROM stats WHERE repo_id=? ORDER BY day",
            (db.get_repo_id(repo_name),),
        )
        weekly_stats = get_weekly_stats(curs, dates, col)
        curs.close()
        df.loc[:, repo_name] = weekly_stats
    for i in range(df.shape[0]):
        print(dates[i], df[repo_name][i], sum(df[repo_name][:i]))


db = GithubStats()
db.connect()
dates = get_weekly_dates(db)

if not os.path.exists("images"):
    os.mkdir("images")

fontsize = 14

# prisms-center/CASMcode
# prisms-center/phaseField
# dftfeDevelopers/dftfe
# print_data_by_week(db, "dftfeDevelopers/dftfe", 'unique_clones')
# print_data_by_week(db, "prisms-center/Fatigue", 'views')
# exit()

make_plots(db, dates, "views", "Weekly Views", fontsize=fontsize)
make_plots(db, dates, "unique_views", "Weekly Unique Views", fontsize=fontsize)
make_plots(db, dates, "clones", "Weekly Clones", fontsize=fontsize)
make_plots(db, dates, "unique_clones", "Weekly Unique Clones", fontsize=fontsize)
make_plots_excluding_travis_builds(
    db, dates, "unique_clones", "Weekly Unique Clones", fontsize=fontsize
)

db.close()
