import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime, timedelta
import os

def fetch_cbs_data(positions, year):
    cbs_data = []
    base_url = f"https://www.cbssports.com/fantasy/football/depth-chart/{year}/"
    
    for position in positions:
        time.sleep(5)
        print(f"Starting {position}")
        url = base_url + position
        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        cols12 = [a['href'] for a in soup.select("table > tbody > tr > td > span.CellPlayerName--short > span > a")]
        cols3 = [a['href'] for a in soup.select("table > tbody > tr > td > div > div > span.CellPlayerName--short > span > a")]
        
        cols = list(set(cols12 + cols3))
        
        for col in cols:
            player_name = os.path.basename(os.path.dirname(col))
            player_id = os.path.basename(os.path.dirname(os.path.dirname(col)))
            cbs_data.append({
                'player_names': player_name,
                'player_id': player_id,
                'position': position
            })
    
    return pd.DataFrame(cbs_data)

def fetch_fftoday_data(positions, year):
    fft_data = []
    base_url = f"https://fftoday.com/stats/players?Pos="
    
    for position in positions:
        time.sleep(5)
        print(f"Starting {position}")
        url = f"{base_url}{position}&Year={year}"
        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        cols = [a['href'] for a in soup.select("body > center > table:nth-child(4) > tr:nth-child(2) > td.bodycontent > table:nth-child(7) > tr > td > span.smallbody > a")]
        
        for col in cols:
            player_name = os.path.basename(col)
            player_id = os.path.basename(os.path.dirname(col))
            fft_data.append({
                'player_names': player_name,
                'player_id': player_id,
                'pos': position
            })
    
    return pd.DataFrame(fft_data)

def fetch_fantasypros_data(positions, year):
    fp_data = []
    base_url = f"https://www.fantasypros.com/nfl/stats/"
    
    for position in positions:
        time.sleep(5)
        print(f"Starting {position}")
        url = f"{base_url}{position.lower()}.php?year={year}"
        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        player_elements = soup.select("td.player-label > a.player-name")
        internal_id_elements = soup.select("a.fp-player-link")
        
        for player_el, internal_el in zip(player_elements, internal_id_elements):
            name_id = player_el['href'].split('/')[-1].split('.')[0]
            internal_id = internal_el['class'][-1].split('-')[-1]
            player_name = internal_el['fp-player-name']
            
            fp_data.append({
                'player_name': player_name,
                'pos': position,
                'name_id': name_id,
                'internal_id': internal_id
            })
    
    return pd.DataFrame(fp_data)

def get_player_ids(year, week, force_update=False):
    cache_file = f'player_ids_cache_{year}_week_{week}.pkl'
    cache_expiry = timedelta(days=7)  # Cache expires after 7 days
    
    if os.path.exists(cache_file) and not force_update:
        cache_time = datetime.fromtimestamp(os.path.getmtime(cache_file))
        if datetime.now() - cache_time < cache_expiry:
            print("Loading cached player IDs...")
            return pd.read_pickle(cache_file)
    
    print(f"Fetching new player IDs for year {year}, week {week}...")
    
    # Fetch data from different sources
    cbs_positions = ['QB', 'RB', 'WR', 'TE', 'K']
    cbs_df = fetch_cbs_data(cbs_positions, year)
    
    fftoday_positions = ['QB', 'RB', 'WR', 'TE', 'K']
    fftoday_df = fetch_fftoday_data(fftoday_positions, year)
    
    fp_positions = ['QB', 'RB', 'WR', 'TE', 'K', 'DST']
    fp_df = fetch_fantasypros_data(fp_positions, year)
    
    # Process and merge data
    cbs_final = cbs_df.assign(
        cbs_id=cbs_df['player_id'],
        merge_id=cbs_df['player_names'].str.replace(r'\(-)|-', '', regex=True) + '_' + cbs_df['position'].str.lower()
    )[['cbs_id', 'merge_id']]
    
    fftoday_final = fftoday_df.assign(
        fftoday_id=fftoday_df['player_id'],
        merge_id=fftoday_df['player_names'].str.replace(r'[^\w\s]', '', regex=True).str.lower().str.replace(r'\s+', '', regex=True) + '_' + fftoday_df['pos'].str.lower()
    )[['fftoday_id', 'merge_id']]
    
    fp_final = fp_df.assign(
        fantasypro_id=fp_df['name_id'],
        fantasypro_num_id=fp_df['internal_id'],
        merge_id=fp_df['player_name'].str.replace(r'[^\w\s]', '', regex=True).str.lower().str.replace(r'\s+', '', regex=True) + '_' + fp_df['pos'].str.lower()
    )[['fantasypro_id', 'fantasypro_num_id', 'merge_id']].drop_duplicates(subset=['merge_id'])
    
    # Merge all dataframes
    player_ids = pd.merge(cbs_final, fftoday_final, on='merge_id', how='outer')
    player_ids = pd.merge(player_ids, fp_final, on='merge_id', how='outer')
    
    # Add year and week columns
    player_ids['year'] = year
    player_ids['week'] = week
    
    # Save to cache
    player_ids.to_pickle(cache_file)
    
    return player_ids

# Usage
year = 2024  # Replace with the desired year
week = 2     # Replace with the desired week
player_ids_df = get_player_ids(year, week)
print(player_ids_df.head())
