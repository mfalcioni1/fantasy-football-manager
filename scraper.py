import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
from typing import List, Dict, Any
import openpyxl
import json
from ratelimit import limits, sleep_and_retry
from utils import get_mfl_id, rename_vec, get_scrape_year, get_scrape_week
import dim
from players import player_ids
import os
from datetime import datetime, timedelta

def scrape_cbs(pos: List[str] = ["QB", "RB", "WR", "TE", "K", "DST"], season: int = None, week: int = None,
               draft: bool = True, weekly: bool = True) -> Dict[str, pd.DataFrame]:
    if season is None:
        season = get_scrape_year()
    if week is None:
        week = get_scrape_week()

    scrape_week = "restofseason" if week in [0, "ros"] else week

    print("\nThe CBS scrape uses a 2 second delay between pages")

    base_link = "https://www.cbssports.com/fantasy/football/"
    session = requests.Session()

    l_pos = {}
    for pos in pos:
        scrape_link = f"https://www.cbssports.com/fantasy/football/stats/{pos}/{season}/{scrape_week}/projections/nonppr/"

        time.sleep(2)  # Delay between requests
        print(f"Scraping {pos} projections from {scrape_link}")

        response = session.get(scrape_link)
        soup = BeautifulSoup(response.text, 'html.parser')

        # Get column names
        col_names = soup.select_one("#TableBase > div > div > table > thead > tr.TableBase-headTr").text.split()
        col_names = [name for name in col_names if re.match("[A-Z]", name)]
        col_names = rename_vec(col_names, dim.cbs_columns)

        # Get PID
        if pos == "DST":
            cbs_id = [re.sub(".*?([A-Z]{2,3}).*", r"\1", link['href']) 
                      for link in soup.select("span.TeamName a")]
        else:
            cbs_id = [re.sub(".*?([0-9]+).*", r"\1", link['href']) 
                      for link in soup.select("table > tbody > tr > td:nth-child(1) > span.CellPlayerName--long > span > a")]

        # Creating and cleaning table
        table = soup.select_one("#TableBase > div > div > table > tbody")
        out_df = pd.read_html(str(table))[0]
        out_df.columns = col_names

        if pos != "DST":
            # Extract player, pos, team
            out_df[['player', 'pos', 'team']] = out_df['player'].str.extract(r'.*?\s{2,}[A-Z]{1,3}\s{2,}[A-Z]{2,3}\s{2,}(.*?)\s{2,}(.*?)\s{2,}(.*)')
            out_df['src_id'] = cbs_id
            out_df['data_src'] = "CBS"
            out_df['id'] = get_mfl_id(cbs_id, player_name=out_df['player'], pos=out_df['pos'], team=out_df['team'])
        else:
            out_df['team'] = cbs_id
            out_df['data_src'] = "CBS"
            # Implement dst_ids logic here
            out_df['id'] = get_mfl_id(cbs_id, pos=pos)
            out_df['src_id'] = out_df['id'].map(lambda x: player_ids.loc[player_ids['id'] == x, 'cbs_id'].iloc[0])

        # Misc cleanup
        out_df = out_df.replace("—", pd.NA)
        out_df = out_df.apply(pd.to_numeric, errors='ignore')
        out_df = out_df[out_df['site_pts'] > 0]

        l_pos[pos] = out_df

    return l_pos

def scrape_nfl(pos: List[str] = ["QB", "RB", "WR", "TE", "K", "DST"], season: int = None, week: int = None,
               draft: bool = True, weekly: bool = True) -> Dict[str, pd.DataFrame]:
    print("\nThe NFL.com scrape uses a 2 second delay between pages")

    if season is None:
        season = get_scrape_year()
    if week is None:
        week = get_scrape_week()

    pos_scrape = [dim.nfl_pos_idx[p] for p in pos]

    base_link = f"https://fantasy.nfl.com/research/projections?position={pos_scrape[0]}&sort=projectedPts&statCategory=projectedStats&statSeason={season}&statType=seasonProjectedStats"

    session = requests.Session()

    l_pos = {}
    for pos in pos:
        pos_scrape = dim.nfl_pos_idx[pos]

        n_records = {
            "QB": 42, "RB": 100, "WR": 150, "TE": 60, "K": 64, "DST": 32
        }[pos]

        if week == 0:
            scrape_link = f"https://fantasy.nfl.com/research/projections?position={pos_scrape}&count={n_records}&sort=projectedPts&statCategory=projectedStats&statSeason={season}&statType=seasonProjectedStats"
        else:
            scrape_link = f"https://fantasy.nfl.com/research/projections?position={pos_scrape}&count={n_records}&sort=projectedPts&statCategory=projectedStats&statSeason={season}&statType=weekProjectedStats&statWeek={week}"

        time.sleep(2)  # Delay between requests
        print(f"Scraping {pos} projections from {scrape_link}")

        response = session.get(scrape_link)
        soup = BeautifulSoup(response.text, 'html.parser')

        # Get PID
        site_id = [re.sub(".*=", "", link['href']) for link in soup.select("table td:first-child a.playerName")]

        # Getting column names
        col_names = soup.select_one("table > thead").text.split()
        col_names = [col for col in col_names if col.strip()]
        col_names = rename_vec(col_names, dim.nfl_columns)

        # Creating and cleaning table
        table = soup.select_one("table > tbody")
        out_df = pd.read_html(str(table))[0]
        out_df.columns = col_names

        if pos != "DST":
            out_df[['player', 'pos', 'team']] = out_df['player'].str.extract(r'(.*?)\s+\b(QB|RB|WR|TE|K)\b.*?([A-Z]{2,3})')
        else:
            out_df['team'] = out_df['team'].str.replace(r'\s+DEF$', '', regex=True)
            out_df['pos'] = "DST"

        if pos in ["RB", "WR", "TE"] and "pass_int" in out_df.columns:
            out_df = out_df.drop(columns=["pass_int"])

        out_df['data_src'] = "NFL"
        out_df['nfl_id'] = site_id
        out_df = out_df.drop(columns=["opp"], errors='ignore')

        # Type cleanup
        out_df = out_df.replace("-", pd.NA)
        out_df = out_df.apply(pd.to_numeric, errors='ignore')

        out_df = out_df[out_df['site_pts'] > 0].dropna(subset=['site_pts'])
        out_df['id'] = get_mfl_id(out_df['nfl_id'], player_name=out_df['player'], pos=out_df['pos'], team=out_df['team'])
        out_df = out_df[['id', 'src_id', 'player', 'pos', 'team'] + [col for col in out_df.columns if col not in ['id', 'src_id', 'player', 'pos', 'team']]]

        l_pos[pos] = out_df

    return l_pos

def scrape_fantasysharks(pos: List[str] = ["QB", "RB", "WR", "TE", "K", "DST", "DL", "LB", "DB"],
                         season: int = None, week: int = None, draft: bool = True, weekly: bool = True) -> Dict[str, pd.DataFrame]:
    print("\nThe FantasySharks scrape uses a 2 second delay between pages")

    if season is None:
        season = get_scrape_year()
    if week is None:
        week = get_scrape_week()

    year = {
        2024: 810, 2023: 778, 2022: 746, 2021: 714, 2020: 682,
        2019: 650, 2018: 618, 2017: 586
    }[season]

    segment = year if week == 0 else (year + week + 8 if 1 <= week <= 22 else 813)

    l_pos = {}
    for pos in pos:
        position = {
            "QB": 1, "RB": 2, "WR": 4, "TE": 5, "K": 7, "DST": 6,
            "DL": 8, "LB": 9, "DB": 10
        }[pos]

        scrape_link = f"https://www.fantasysharks.com/apps/bert/forecasts/projections.php?csv=1&Sort=&League=-1&Position={position}&scoring=1&Segment={segment}&uid=4"

        time.sleep(2)  # Delay between requests
        print(f"Scraping {pos} projections from {scrape_link}")

        pos_df = pd.read_csv(scrape_link)
        pos_df = pos_df.drop(columns=['Rank'])

        pos_df.columns = rename_vec(pos_df.columns, dim.fantasysharks_columns)
        if 'rec_50_yds' in pos_df.columns and 'rec_100_yds' not in pos_df.columns:
            pos_df = pos_df.rename(columns={'rec_50_yds': 'rec_100_yds'})

        if pos == "K":
            pos_df = pos_df.rename(columns={'pass_att': 'fg_att'})
        if pos == "DST":
            pos_df = pos_df.rename(columns={'pass_int': 'dst_int'})
            pos_df['id'] = pos_df['id'].apply(lambda x: f"{int(x):04d}")
        if pos in ["DL", "LB", "DB"]:
            pos_df.columns = [re.sub(r'^(dst|pass)_', 'idp_', col) for col in pos_df.columns]

        pos_df['id'] = pos_df['id'].astype(str)
        pos_df['data_src'] = "FantasySharks"
        pos_df = pos_df.apply(pd.to_numeric, errors='ignore')
        pos_df = pos_df[pos_df['site_pts'] > 0]

        l_pos[pos] = pos_df

    return l_pos

@sleep_and_retry
@limits(calls=1, period=5)
def scrape_walterfootball(pos: List[str] = ["QB", "RB", "WR", "TE", "K"],
                          season: int = None, week: int = None, draft: bool = True, weekly: bool = False) -> Dict[str, pd.DataFrame]:
    if season is None:
        season = get_scrape_year()
    if week is None:
        week = get_scrape_week()

    url = f"http://walterfootball.com/fantasy{season}rankingsexcel.xlsx"

    print(f"\nScraping WalterFootball projections from {url}")

    l_pos = {}
    for pos in pos:
        print(f"Scraping {pos} projections")

        position = {
            "QB": "QBs", "RB": "RBs", "WR": "WRs", "TE": "TEs", "K": "Ks"
        }[pos]

        df = pd.read_excel(url, sheet_name=position)
        df = df.dropna(axis=1, how='all')

        if pos in ["QB", "WR"]:
            df['First Name'] = df['First Name'].replace("Marcua", "Marcus")
            df['Player'] = df['First Name'] + ' ' + df['Last Name']
            df = df.filter(regex='^Pass|^Rush|^Catch|^Rec|^Reg TD$|^Int|^FG|^XP|name$|^player|^Team$|^Pos|^Bye')
            df = df.rename(columns={'Last Name': 'last_name', 'First Name': 'first_name', 'Pos': 'position'})
        else:
            df['Player'] = df['First Name'] + ' ' + df['Last Name']
            df = df.filter(regex='^Pass|^Rush|^Catch|^Rec|^Reg TD$|^Int|^FG|^XP|name$|^player|^Team$|^Pos|^Bye')
            df = df.rename(columns={'BYE': 'Bye', 'Last Name': 'last_name', 'First Name': 'first_name', 'Pos': 'position'})

        df['id'] = df.apply(lambda row: get_mfl_id(id_col="fantasypro_id", player_name=row['Player'], pos=row['position']), axis=1)
        df['data_src'] = "WalterFootball"
        df = df.drop(columns=['last_name', 'first_name'])

        df.columns = rename_vec(df.columns, dim.walterfootball_columns)

        if 'reg_tds' in df.columns:
            if all(col in df.columns for col in ['rush_yds', 'rec_yds']):
                df['total_yds'] = df['rush_yds'] + df['rec_yds']
                df['rush_tds'] = df.apply(lambda row: 0 if row['total_yds'] == 0 else (row['rush_yds'] / row['total_yds']) * row['reg_tds'], axis=1)
                df['rec_tds'] = df.apply(lambda row: 0 if row['total_yds'] == 0 else (row['rec_yds'] / row['total_yds']) * row['reg_tds'], axis=1)
                df = df.drop(columns=['reg_tds', 'total_yds'])
            elif any(col in df.columns for col in ['rush_yds', 'rec_yds']):
                col_name = next(col for col in df.columns if col in ['rush_yds', 'rec_yds'])
                df = df.rename(columns={'reg_tds': col_name.replace('yds', 'tds')})

        l_pos[pos] = df

    return l_pos

@sleep_and_retry
@limits(calls=1, period=2)
def scrape_fleaflicker(pos: List[str] = ["QB", "RB", "WR", "TE", "K", "DST", "DL", "LB", "DB"],
                       season: int = None, week: int = None, draft: bool = False, weekly: bool = True) -> Dict[str, pd.DataFrame]:
    if season is None:
        season = get_scrape_year()
    if week is None:
        week = get_scrape_week()

    if "DL" in pos:
        pos = [p for p in pos if p != "DL"] + ["DE", "DT"]
    if "DB" in pos:
        pos = [p for p in pos if p != "DB"] + ["CB", "S"]

    base_link = "https://www.fleaflicker.com/nfl/leaders"
    session = requests.Session()

    l_pos = {}
    for pos in pos:
        position = {
            "QB": 4, "RB": 1, "WR": 2, "TE": 8, "K": 16, "DST": 256,
            "DE": 2048, "DT": 64, "LB": 128, "CB": 512, "S": 1024
        }[pos]

        offset = 0
        out_dfs = []

        pos_pages = {
            "K": 2, "DST": 2, "QB": 2, "DT": 4, "TE": 5,
            "DE": 6, "LB": 6, "S": 6, "RB": 6, "CB": 6, "WR": 6
        }[pos]

        print(f"Scraping {pos} projections from FleaFlicker")

        for i in range(pos_pages):
            page_link = f"https://www.fleaflicker.com/nfl/leaders?week={week}&statType=7&sortMode=7&position={position}&tableOffset={offset}"

            if i != 0:
                time.sleep(2)

            response = session.get(page_link)
            soup = BeautifulSoup(response.text, 'html.parser')

            fleaflicker_id = [link['href'].split('-')[-1] for link in soup.select("a.player-text")]

            table = soup.select_one('#body-center-main table')
            scrape = pd.read_html(str(table))[0]

            scrape = scrape[~scrape.apply(lambda row: any("Previous" in str(val) or "Next" in str(val) for val in row), axis=1)]

            col_names = [' '.join(col.split()) for col in scrape.columns]
            col_names = [re.sub(r'Week \d+|Projected', '', col).strip() for col in col_names]

            if pos == "K":
                col_names[9:13] = ['fg_att', 'fg_pct', 'xp_att', 'xp_pct']

            col_names = rename_vec(col_names, dim.fleaflicker_columns)
            col_names = [f'...{i}' if pd.isna(col) else col for i, col in enumerate(col_names)]

            scrape.columns = col_names
            scrape['id'] = fleaflicker_id
            scrape['data_src'] = "FleaFlicker"
            scrape['pos'] = pos

            out_dfs.append(scrape)

            offset += 100

        out_df = pd.concat(out_dfs)
        out_df = out_df.apply(pd.to_numeric, errors='ignore')
        out_df = out_df[out_df['site_pts'] > 0]

        l_pos[pos] = out_df

    return l_pos

def scrape_numberfire(pos: List[str] = ["QB", "RB", "WR", "TE", "K", "DST", "LB", "DB", "DL"],
                      season: int = None, week: int = None, draft: bool = True, weekly: bool = True) -> Dict[str, pd.DataFrame]:
    print("\nThe NumberFire scrape uses a 2 second delay between pages")

    if season is None:
        season = get_scrape_year()
    if week is None:
        week = get_scrape_week()

    base_link = "https://www.numberfire.com/nfl/fantasy/fantasy-football-projections"
    session = requests.Session()

    site_pos = [p for p in pos if p not in ["LB", "DB", "DL"]] + (["LB"] if any(p in ["LB", "DB", "DL"] for p in pos) else [])

    l_pos = {}
    for pos in site_pos:
        position = {
            "QB": "qb", "RB": "rb", "WR": "wr", "TE": "te", "K": "k", "DST": "d", "LB": "idp"
        }[pos]

        scrape_link = (f"https://www.numberfire.com/nfl/fantasy/remaining-projections/{position}" 
                       if week in [0, "ros"] else 
                       f"https://www.numberfire.com/nfl/fantasy/fantasy-football-projections/{position}")

        time.sleep(2)  # Delay between requests
        print(f"Scraping {pos} projections from {scrape_link}")

        response = session.get(scrape_link)
        soup = BeautifulSoup(response.text, 'html.parser')

        numfire_id = [link['href'].split('/')[-1] for link in soup.select("td.player a")]

        tables = soup.select('table.projection-table')
        players_table = pd.read_html(str(tables[0]))[0]
        data_table = pd.read_html(str(tables[1]))[0]

        players = players_table.iloc[:, 0].str.extract(r"(.*?)\n.*\n.*?([A-Z]{1,3}),\s*([A-Z]{2,3})")
        players.columns = ["Player", "position", "team"]

        data_table.columns = [f"{data_table.columns[i]} {data_table.iloc[0, i]}" for i in range(len(data_table.columns))]
        data_table = data_table.iloc[1:]

        if pos == "QB":
            data_table['numberFire CI'] = data_table['numberFire CI'].str.replace(r"(\d|\.)\-", r"\1,", regex=True)
            data_table[['Lower', 'Upper']] = data_table['numberFire CI'].str.split(',', expand=True)
            data_table[['pass_comp', 'pass_att']] = data_table['Passing C/A'].str.split('/', expand=True)
            data_table = data_table.replace(r"#", "", regex=True)
        elif pos in ["LB", "DB"]:
            pass
        else:
            data_table['numberFire CI'] = data_table['numberFire CI'].str.replace(r"(\d|\.)\-", r"\1,", regex=True)
            data_table[['Lower', 'Upper']] = data_table['numberFire CI'].str.split(',', expand=True)
            data_table = data_table.replace(r"#", "", regex=True)

        pos_df = pd.concat([players, data_table], axis=1)
        pos_df['id'] = pos_df.apply(lambda row: get_mfl_id(numfire_id[row.name], player_name=row['Player'], pos=row['position'], team=row['team']), axis=1)
        pos_df['src_id'] = numfire_id
        pos_df['data_src'] = "NumberFire"
        pos_df = pos_df[['id', 'src_id'] + list(pos_df.columns[:-2])]

        if pos in ["DB", "LB", "DL"]:
            pos_df.columns = rename_vec(pos_df.columns, dim.numberfire_idp_columns)
        else:
            pos_df.columns = rename_vec(pos_df.columns, dim.numberfire_columns)

        pos_df = pos_df.replace(r"N/A|\$", "", regex=True)
        pos_df = pos_df.apply(pd.to_numeric, errors='ignore')

        if 'site_pts' in pos_df.columns:
            pos_df = pos_df[pos_df['site_pts'] > 0]

        l_pos[pos] = pos_df

    if any(p in ["LB", "DB", "DL"] for p in pos):
        idp_idx = site_pos.index("LB")
        df_idp = l_pos.pop("LB")
        l_idp = {p: df_idp[df_idp['pos'] == p] for p in ["LB", "DB", "DL"] if p in pos}
        l_pos.update(l_idp)

    return l_pos

def scrape_fftoday(pos: List[str] = ["QB", "RB", "WR", "TE", "K", "DST", "DL", "LB", "DB"],
                   season: int = None, week: int = None, draft: bool = True, weekly: bool = True) -> Dict[str, pd.DataFrame]:
    print("\nThe FFToday scrape uses a 2 second delay between pages")

    if season is None:
        season = get_scrape_year()
    if week is None:
        week = get_scrape_week()

    if week > 18:
        week += 2
    if week > 0:
        pos = [p for p in pos if p not in ["DST", "DL", "LB", "DB"]]

    base_link = "https://www.fftoday.com/rankings/index.html"
    session = requests.Session()

    position_map = {
        "QB": 10, "RB": 20, "WR": 30, "TE": 40, "DL": 50, "LB": 60, "DB": 70, "K": 80, "DST": 99
    }

    pos_pages = {
        "QB": 1, "TE": 1, "K": 1, "DST": 1,
        "RB": 2,
        "WR": 3, "DL": 3, "DB": 3, "LB": 3
    }

    l_pos = {}
    for pos in pos:
        position = position_map[pos]
        out_dfs = []

        for cur_page in range(pos_pages[pos]):
            time.sleep(2)  # Delay between requests

            if week == 0:
                page_link = f"https://www.fftoday.com/rankings/playerproj.php?Season={season}&PosID={position}&LeagueID=1&order_by=FFPts&sort_order=DESC&cur_page={cur_page}"
            else:
                page_link = f"https://www.fftoday.com/rankings/playerwkproj.php?Season={season}&GameWeek={week}&PosID={position}&LeagueID=1&order_by=FFPts&sort_order=DESC&cur_page={cur_page}"

            print(f"Scraping {pos} projections from {page_link}")

            response = session.get(page_link)
            soup = BeautifulSoup(response.text, 'html.parser')

            if pos == "DST":
                fftoday_id = [re.search(r'=(\d{4})', link['href']).group(1) for link in soup.select("a[href*='stats/players']") if re.search(r'\d{4}', link['href'])]
            else:
                fftoday_id = [link['href'].split('/')[-2] for link in soup.select("a[href*='stats/players/']")]

            tables = soup.select("table table table")
            if not tables:
                continue

            df = pd.read_html(str(tables[0]))[0]
            df = df.replace(",", "", regex=True)

            col_names = [f"{df.iloc[0, i]} {df.iloc[1, i]}".strip() for i in range(len(df.columns))]
            col_names = rename_vec(col_names, dim.fftoday_columns)

            if pos in ["DL", "DB", "LB"]:
                col_names = [re.sub(r"(dst|pass)_", "idp_", col) for col in col_names]

            df = df.iloc[2:].reset_index(drop=True)
            df.columns = col_names

            df['pos'] = pos
            df['data_src'] = "FFToday"
            df['src_id'] = fftoday_id

            if week > 0:
                df['opp'] = df['opp'].str.replace("@", "", regex=False)

            if pos == "DST":
                df['id'] = df.apply(lambda row: get_mfl_id(row['src_id'], pos=row['pos']), axis=1)
            else:
                df['id'] = df.apply(lambda row: get_mfl_id(row['src_id'], player_name=row['player'], team=row['team'], pos=row['pos']), axis=1)

            if 'bye' in df.columns:
                df['bye'] = df['bye'].replace("-", "").astype(int)

            df = df.apply(pd.to_numeric, errors='ignore')
            out_dfs.append(df)

        l_pos[pos] = pd.concat(out_dfs, ignore_index=True)

    return l_pos

def scrape_fantasypros(pos: List[str] = ["QB", "RB", "WR", "TE", "K", "DST"],
                       season: int = None, week: int = None, draft: bool = True, weekly: bool = True) -> Dict[str, pd.DataFrame]:
    print("\nThe FantasyPros scrape uses a 2 second delay between pages")

    if season is None:
        season = get_scrape_year()
    if week is None:
        week = get_scrape_week()

    scrape_week = f".php?week={week}" if week > 0 else ".php?week=draft"

    base_link = "https://www.fantasypros.com/nfl/projections"
    session = requests.Session()

    l_pos = {}
    for pos in pos:
        scrape_link = f"https://www.fantasypros.com/nfl/projections/{pos.lower()}{scrape_week}"

        time.sleep(2)  # Delay between requests
        print(f"Scraping {pos} projections from {scrape_link}")

        response = session.get(scrape_link)
        soup = BeautifulSoup(response.text, 'html.parser')

        # Getting column names
        if pos in ["K", "DST"]:
            col_names = soup.select_one("table > thead").text.split()
            col_names = rename_vec(col_names, dim.fantasypros_columns)
        else:
            col_names = soup.select_one("table > thead").find_all("tr")
            col_names = [f"{col_names[0].find_all('th')[i].text.strip()} {col_names[1].find_all('th')[i].text.strip()}" for i in range(len(col_names[0].find_all('th')))]
            col_names = rename_vec(col_names, dim.fantasypros_columns)

        # Get PID
        fantasypro_num_id = [re.search(r'\d{4,6}', tr['class'][0]).group() for tr in soup.select("table > tbody > tr") if re.search(r'\d{4,6}', tr['class'][0])]

        # Creating and cleaning table
        table = soup.select_one("table > tbody")
        out_df = pd.read_html(str(table))[0]
        out_df = out_df.replace(",", "", regex=True)

        out_df.columns = col_names

        # Adding a few columns
        if pos == "DST":
            out_df['src_id'] = fantasypro_num_id
            out_df['data_src'] = "FantasyPros"
            out_df['pos'] = pos
            out_df['id'] = out_df['src_id'].apply(get_mfl_id)
        else:
            out_df[['player', 'team']] = out_df['player'].str.extract(r'(.+)\s+([A-Z]{2,3})')
            out_df['src_id'] = fantasypro_num_id
            out_df['data_src'] = "FantasyPros"
            out_df['pos'] = pos
            out_df['id'] = out_df.apply(lambda row: get_mfl_id(row['src_id'], player_name=row['player'], team=row['team'], pos=pos), axis=1)

        # Misc cleanup before done
        out_df = out_df.apply(pd.to_numeric, errors='ignore')
        out_df = out_df[out_df['site_pts'] > 0]

        l_pos[pos] = out_df

    return l_pos

def scrape_rtsports(pos: List[str] = ["QB", "RB", "WR", "TE", "K", "DST"],
                    season: int = None, week: int = 0, draft: bool = True, weekly: bool = False) -> Dict[str, pd.DataFrame]:
    print("\nThe RTSports scrape uses a 5 second delay between pages")

    if season is None:
        season = get_scrape_year()
    if week is None:
        week = get_scrape_week()
    if week > 0:
        raise ValueError("RTS Sports projections are only available for week 0")

    base_url = "https://www.freedraftguide.com/football/draft-guide-rankings-provider.php"

    rts_pos_idx = {
        "QB": "QB", "RB": "RB", "WR": "WR", "TE": "TE", "K": "PK", "DST": "DST"
    }

    l_pos = {}
    for x in pos:
        if x != pos[0]:
            time.sleep(5)

        params = {"POS": rts_pos_idx[x]}
        print(f"Scraping {x} projections from {base_url}")
        response = requests.get(base_url, params=params)
        rts_json = response.json()

        p_info = pd.json_normalize(rts_json, record_path=['players'], 
                                   meta=['player_id', 'stats_id', 'name', 'nfl_team'])

        p_data = pd.json_normalize(rts_json, record_path=['players', 'stats'])

        if x in ["RB", "WR", "TE"] and "pass_yds" in p_data.columns:
            if "pass_atts" not in p_data.columns:
                p_data["pass_atts"] = 0

        out_df = pd.concat([p_info, p_data], axis=1)

        out_df.columns = rename_vec(out_df.columns, dim.rts_columns)
        if x != "DST":
            out_df = out_df[out_df['site_pts'] > 0]

        out_df = out_df.apply(pd.to_numeric, errors='ignore')
        out_df['pos'] = x
        out_df['id'] = out_df.apply(lambda row: get_mfl_id(row['stats_id'], 
                                                           player_name=row['player'], 
                                                           team=row['team'], 
                                                           pos=x), axis=1)
        out_df['src_id'] = out_df['src_id'].astype(str)
        out_df = out_df.drop(columns=['stats_id'])
        out_df['data_src'] = "RTSports"
        
        out_df = out_df[['id', 'src_id', 'pos', 'data_src'] + [col for col in out_df.columns if col not in ['id', 'src_id', 'pos', 'data_src']]]

        l_pos[x] = out_df

    return l_pos

def scrape_espn(pos: List[str] = ["QB", "RB", "WR", "TE", "K", "DST"],
                season: int = None, week: int = None,
                draft: bool = True, weekly: bool = True) -> Dict[str, pd.DataFrame]:
    print("\nThe ESPN scrape uses a 2 second delay between pages")

    if season is None:
        season = get_scrape_year()
    if week is None:
        week = get_scrape_week()

    slot_nums = {"QB": 0, "RB": 2, "WR": 4, "TE": 6, "K": 17, "DST": 16}
    position = pos

    l_pos = {}
    for pos in position:
        if pos != position[0]:
            time.sleep(2)

        pos_idx = slot_nums[pos]
        limit = {
            "QB": 42, "RB": 100, "WR": 150, "TE": 60, "K": 35, "DST": 32
        }[pos]

        base_url = f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{season}/segments/0/leaguedefaults/3?scoringPeriodId=0&view=kona_player_info"
        print(f"Scraping {pos} projections from https://fantasy.espn.com/football/players/projections")

        filter_split_id = 0 if week == 0 else 1

        fantasy_filter = {
            "players": {
                "filterSlotIds": {"value": [pos_idx]},
                "filterStatsForSourceIds": {"value": [1]},
                "filterStatsForSplitTypeIds": {"value": [filter_split_id]},
                "sortAppliedStatTotal": {"sortAsc": False, "sortPriority": 3, "value": f"11{season}{week}"},
                "sortDraftRanks": {"sortPriority": 2, "sortAsc": True, "value": "PPR"},
                "sortPercOwned": {"sortAsc": False, "sortPriority": 4},
                "limit": limit,
                "offset": 0,
                "filterRanksForScoringPeriodIds": {"value": [2]},
                "filterRanksForRankTypes": {"value": ["PPR"]},
                "filterRanksForSlotIds": {"value": [0, 2, 4, 6, 17, 16]},
                "filterStatsForTopScoringPeriodIds": {
                    "value": 2,
                    "additionalValue": [f"00{season}", f"10{season}", f"11{season}{week}", f"02{season}"]
                }
            }
        }

        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Host": "lm-api-reads.fantasy.espn.com",
            "X-Fantasy-Source": "kona",
            "X-Fantasy-Filter": json.dumps(fantasy_filter),
            "User-Agent": "ffanalytics Python package (https://github.com/FantasyFootballAnalytics/ffanalytics)"
        }

        response = requests.get(base_url, headers=headers)
        espn_json = response.json()["players"]

        l_players = []
        for player in espn_json:
            if not player["player"]["stats"]:
                continue

            player_stats = player["player"]["stats"][0]["stats"]
            player_stats = {k: v for k, v in player_stats.items() if k in dim.espn_columns}
            player_stats = {dim.espn_columns.get(k, k): round(v) for k, v in player_stats.items()}

            player_stats["espn_id"] = player["id"]
            player_stats["player_name"] = player["player"]["fullName"]
            player_stats["team"] = dim.espn_team_nums.get(str(player["player"]["proTeamId"]))
            player_stats["position"] = pos

            l_players.append(player_stats)

        out_df = pd.DataFrame(l_players)
        out_df["data_src"] = "ESPN"

        if pos == "DST":
            out_df["id"] = out_df.apply(lambda row: get_mfl_id(team=row["team"], pos=row["position"]), axis=1)
        else:
            out_df["id"] = out_df.apply(lambda row: get_mfl_id(row["espn_id"], player_name=row["player_name"], pos=row["position"], team=row["team"]), axis=1)

        out_df = out_df.rename(columns={"espn_id": "src_id", "position": "pos", "player_name": "player"})
        out_df = out_df[["id", "src_id", "pos", "player", "team"] + [col for col in out_df.columns if col not in ["id", "src_id", "pos", "player", "team"]]]

        out_df[["id", "src_id"]] = out_df[["id", "src_id"]].astype(str)
        out_df = out_df.apply(pd.to_numeric, errors='ignore')

        l_pos[pos] = out_df

    return l_pos

def run_all_scrapes(pos: List[str] = ["QB", "RB", "WR", "TE", "K", "DST"], 
                    season: int = None, week: int = None, 
                    force_update: bool = False, 
                    update_threshold: int = 24) -> Dict[str, Dict[str, pd.DataFrame]]:
    if season is None:
        season = get_scrape_year()
    if week is None:
        week = get_scrape_week()

    scrape_functions = {
        "cbs": scrape_cbs,
        "nfl": scrape_nfl,
        "fantasysharks": scrape_fantasysharks,
        "walterfootball": scrape_walterfootball,
        "fleaflicker": scrape_fleaflicker,
        "numberfire": scrape_numberfire,
        "fftoday": scrape_fftoday,
        "fantasypros": scrape_fantasypros,
        "rtsports": scrape_rtsports,
        "espn": scrape_espn
    }

    all_scrapes = {}

    for site, scrape_func in scrape_functions.items():
        file_path = f"data/{site}_projections_{season}_week{week}.json"
        
        if force_update or not file_exists_and_recent(file_path, update_threshold):
            print(f"Scraping {site} projections...")
            scrape_result = scrape_func(pos=pos, season=season, week=week)
            save_scrape_result(scrape_result, file_path)
            all_scrapes[site] = scrape_result
        else:
            print(f"Loading existing {site} projections...")
            all_scrapes[site] = load_scrape_result(file_path)

    return all_scrapes

def file_exists_and_recent(file_path: str, hours: int) -> bool:
    if not os.path.exists(file_path):
        return False
    
    file_modified_time = datetime.fromtimestamp(os.path.getmtime(file_path))
    return datetime.now() - file_modified_time < timedelta(hours=hours)

def save_scrape_result(scrape_result: Dict[str, pd.DataFrame], file_path: str):
    with open(file_path, 'w') as f:
        json.dump({k: v.to_dict(orient='records') for k, v in scrape_result.items()}, f)

def load_scrape_result(file_path: str) -> Dict[str, pd.DataFrame]:
    with open(file_path, 'r') as f:
        data = json.load(f)
    return {k: pd.DataFrame(v) for k, v in data.items()}

if __name__ == "__main__":
    all_projections = run_all_scrapes(force_update=False, update_threshold=24)

