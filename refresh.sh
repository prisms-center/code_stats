wget -O legacy_data/dftfeDevelopers_github_stats.txt https://raw.githubusercontent.com/dftfeDevelopers/clone-scrapper/clone-scrapper/github_stats.txt
python create_from_legacy_data.py
python update_all.py
python plot.py
