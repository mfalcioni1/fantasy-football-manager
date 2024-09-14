import pandas as pd
import numpy as np
from typing import List, Dict, Union, Optional
import re
from datetime import datetime
from dim import pos_corrections, team_corrections
from players import player_ids
from functools import lru_cache

def get_mfl_id(id_col: Optional[Union[str, List[str]]] = None,
               player_name: Optional[Union[str, List[str]]] = None,
               first: Optional[Union[str, List[str]]] = None,
               last: Optional[Union[str, List[str]]] = None,
               pos: Optional[Union[str, List[str]]] = None,
               team: Optional[Union[str, List[str]]] = None) -> List[Optional[str]]:
    
    # Initialize player info dictionary
    player_info = {
        'player_name': player_name,
        'first': first,
        'last': last,
        'pos': pos,
        'team': team,
        'id': None
    }

    # Determine max length of input lists
    max_len = max(len(v) if isinstance(v, list) else 1 for v in player_info.values() if v is not None)

    # Extend single values to lists
    for key, value in player_info.items():
        if value is not None and not isinstance(value, list):
            player_info[key] = [value] * max_len

    # Extract first and last names if not provided
    if player_name is not None:
        if first is None:
            player_info['first'] = [re.sub(r'\s+.*$', '', pn) for pn in player_info['player_name']]
        if last is None:
            player_info['last'] = [re.sub(r'.*?\s+', '', pn) for pn in player_info['player_name']]

    # Remove None entries
    player_info = {k: v for k, v in player_info.items() if v is not None}
    
    # Process player info
    for key in player_info:
        player_info[key] = [rename_vec(x.upper(), pos_corrections) for x in player_info[key]]
        player_info[key] = [rename_vec(x, team_corrections) for x in player_info[key]]
        player_info[key] = [re.sub(r'\s+(defense|jr|sr|[iv]+)\.?$', '', x.lower()) for x in player_info[key]]
        player_info[key] = [re.sub(r'[^\w]+|\s+', '', x) for x in player_info[key]]

    # Check id_col if provided
    if id_col is not None:
        col_name = id_col if isinstance(id_col, str) else 'id_col'
        player_info['id'] = player_ids['id'][player_ids[col_name].isin(id_col)].tolist()
        if all(player_info['id']):
            return player_info['id']

    # Prepare reference table
    ref_table = prepare_reference_table(player_table)

    # Handle DST positions
    if 'pos' in player_info:
        player_info['id'] = [
            ref_table.loc[ref_table['team'] == team, 'id'].iloc[0] if pos == 'dst' else id_
            for pos, team, id_ in zip(player_info['pos'], player_info['team'], player_info['id'])
        ]

    # Define column combinations for matching
    col_combos = [
        ['player_name', 'pos', 'team'],
        ['last', 'pos', 'team'],
        ['player_name', 'team'],
        ['player_name', 'pos'],
        ['first', 'pos', 'team']
    ]

    # Perform matching
    for combo in col_combos:
        if all(c in player_info for c in combo):
            match_ids(player_info, ref_table, combo)

    return player_info['id']

def prepare_reference_table(player_table: pd.DataFrame) -> pd.DataFrame:
    return (player_table
            .apply(lambda x: x.str.lower() if x.dtype == 'object' else x)
            .assign(
                player_name=lambda df: (df['first_name'] + ' ' + df['last_name'])
                    .apply(lambda x: re.sub(r'\s+(defense|jr|sr|[iv]+)\.?$', '', x))
                    .apply(lambda x: re.sub(r'[^\w]+|\s+', '', x)),
                last=lambda df: df['last_name']
                    .apply(lambda x: re.sub(r'\s+(defense|jr|sr|[iv]+)\.?$', '', x))
                    .apply(lambda x: re.sub(r'[^\w]+|\s+', '', x)),
                first=lambda df: df['first_name']
                    .apply(lambda x: re.sub(r'\s+(defense|jr|sr|[iv]+)\.?$', '', x))
                    .apply(lambda x: re.sub(r'[^\w]+|\s+', '', x)),
                pos=lambda df: df['position']
                    .apply(lambda x: rename_vec(x.upper(), pos_corrections))
                    .str.lower(),
                team=lambda df: df['team']
                    .apply(lambda x: rename_vec(x.upper(), team_corrections))
                    .str.lower()
            ))

def match_ids(player_info: dict, ref_table: pd.DataFrame, combo: List[str]):
    id_idx = [i for i, x in enumerate(player_info['id']) if x is None]
    
    player_info_vec = [''.join(str(player_info[c][i]) for c in combo) for i in id_idx]
    ref_table_vec = [''.join(str(x) for x in row) for _, row in ref_table[combo].iterrows()]

    # Remove duplicates from ref_table
    ref_dups = set([x for x in ref_table_vec if ref_table_vec.count(x) > 1])
    keep_in_ref = [x not in ref_dups for x in ref_table_vec]
    ref_table_vec = [x for i, x in enumerate(ref_table_vec) if keep_in_ref[i]]

    match_vec = [ref_table_vec.index(y) if y in ref_table_vec else None for y in player_info_vec]

    for i, match in zip(id_idx, match_vec):
        if match is not None:
            player_info['id'][i] = ref_table.loc[keep_in_ref, 'id'].iloc[match]

def get_scrape_year(date=None):
    if date is None:
        date = datetime.now()
    cal_year = date.year
    cal_month = date.month

    if cal_month in range(1, 4):
        return cal_year - 1
    else:
        return cal_year

def rename_vec(x: Union[str, List[str]], new_names: Dict[str, str], old_names: Optional[List[str]] = None) -> Union[str, List[str]]:
    if old_names is None:
        old_names = list(new_names.keys())
        if not old_names:
            raise ValueError("Must supply old_names argument, or new_names needs to be a dictionary with the old names as keys")

    if isinstance(x, str):
        return new_names.get(x, x)
    else:
        return [new_names.get(item, item) for item in x]

def omit_NA(x: List) -> List:
    return [item for item in x if item is not None and not pd.isna(item)]

def row_sd(x: Union[pd.DataFrame, np.ndarray], na_rm: bool = False) -> np.ndarray:
    if isinstance(x, pd.DataFrame):
        x = x.values

    if na_rm and np.isnan(x).any():
        n_minus_1 = x.shape[1] - np.isnan(x).sum(axis=1) - 1
    else:
        n_minus_1 = x.shape[1] - 1

    r_mean = np.nanmean(x, axis=1) if na_rm else np.mean(x, axis=1)
    r_var = np.nansum((x - r_mean[:, np.newaxis])**2, axis=1) / n_minus_1 if na_rm else np.sum((x - r_mean[:, np.newaxis])**2, axis=1) / n_minus_1
    r_sd = np.sqrt(r_var)
    r_sd[n_minus_1 <= 1] = np.nan
    return r_sd

# Add this new function
@lru_cache(maxsize=1)
def load_player_table():
    url = "https://s3.us-east-2.amazonaws.com/ffanalytics/packagedata/player_table.csv"
    dtypes = {
        "id": str, "last_name": str, "first_name": str, "position": str, "team": str,
        "weight": int, "draft_year": int, "draft_team": str, "draft_round": int,
        "draft_pick": int, "birthdate": str, "age": int, "exp": int
    }
    player_table = pd.read_csv(
        url,
        dtype=dtypes,
        parse_dates=["birthdate"],
        names=[
            "id", "last_name", "first_name", "position", "team", "weight",
            "draft_year", "draft_team", "draft_round", "draft_pick", "birthdate",
            "age", "exp"
        ],
        header=0
    )
    return player_table

# Global variable to store the player table
player_table = load_player_table()

# def impute_and_score_sources(data_result: Dict[str, pd.DataFrame], scoring_rules: Dict) -> Dict[str, pd.DataFrame]:
#     scoring_objs = make_scoring_tables(scoring_rules)
    
#     data_result = impute_via_rates_and_mean(data_result, scoring_objs)
#     data_result = impute_bonus_cols(data_result, scoring_objs['scoring_tables'])
    
#     data_result = {k: source_points(v, scoring_rules, return_data_result=True) for k, v in data_result.items()}
#     return data_result

# def update_player_id_table(player_id_table: Optional[pd.DataFrame], id_column: str, value: Any) -> pd.DataFrame:
#     # Implement the logic to update the player_id_table
#     pass

# def get_pos_src_from_scrape(data_result: Dict[str, pd.DataFrame]) -> Dict[str, List[str]]:
#     data_by_pos_src = {pos: df.groupby('data_src').groups for pos, df in data_result.items()}
#     src_pos = pd.DataFrame([(pos, src) for pos, srcs in data_by_pos_src.items() for src in srcs], columns=['pos', 'src'])
#     return src_pos.groupby('src')['pos'].apply(list).to_dict()

# def extract_src_scrapes_from_scrape(data_result: Dict[str, pd.DataFrame]) -> Dict[str, Dict[str, pd.DataFrame]]:
#     pos_src = get_pos_src_from_scrape(data_result)
#     return {
#         src: {
#             pos: data_result[pos][data_result[pos]['data_src'] == src]
#             for pos in positions
#         }
#         for src, positions in pos_src.items()
#     }

# def actual_points_scoring(nflr_player_stats_df: pd.DataFrame,
#                           nflr_pbp_data: pd.DataFrame,
#                           scoring_rules: Optional[Dict] = None,
#                           vor_baseline: Optional[Dict] = None,
#                           rename_columns: bool = True) -> pd.DataFrame:
    
#     # Fill in missing arguments
#     if scoring_rules is None:
#         scoring_rules = scoring
#     if vor_baseline is None:
#         vor_baseline = default_baseline
    
#     # Update column names
#     nflr_player_stats_df = nflr_player_stats_df.rename(columns=nflreadr_offense_cols)
    
#     scoring_objs = make_scoring_tables(scoring_rules)
    
#     # Calculate specific data from PBP data
#     df_pass_40_yds = (nflr_pbp_data[nflr_pbp_data['passer_player_id'].notna()]
#                       .groupby(['season', 'week', 'passer_player_id'])
#                       .agg({'passing_yards': lambda x: (x >= 40).sum()})
#                       .rename(columns={'passing_yards': 'pass_40_yds'})
#                       .reset_index()
#                       .rename(columns={'season': 'season_year', 'passer_player_id': 'gsis_id'}))
    
#     df_rush_40_yds = (nflr_pbp_data[nflr_pbp_data['rusher_player_id'].notna()]
#                       .groupby(['season', 'week', 'rusher_player_id'])
#                       .agg({'rushing_yards': lambda x: (x >= 40).sum()})
#                       .rename(columns={'rushing_yards': 'rush_40_yds'})
#                       .reset_index()
#                       .rename(columns={'season': 'season_year', 'rusher_player_id': 'gsis_id'}))
    
#     df_rec_40_yds = (nflr_pbp_data[nflr_pbp_data['receiver_player_id'].notna()]
#                      .groupby(['season', 'week', 'receiver_player_id'])
#                      .agg({'receiving_yards': lambda x: (x >= 40).sum()})
#                      .rename(columns={'receiving_yards': 'rec_40_yds'})
#                      .reset_index()
#                      .rename(columns={'season': 'season_year', 'receiver_player_id': 'gsis_id'}))
    
#     df_return_yds = (nflr_pbp_data.assign(gsis_id=lambda x: x['punt_returner_player_id'].fillna(x['kickoff_returner_player_name']))
#                      [lambda x: x['gsis_id'].notna()]
#                      .groupby(['season', 'week', 'gsis_id'])
#                      .agg({'return_yards': 'sum'})
#                      .reset_index()
#                      .rename(columns={'season': 'season_year'}))
    
#     # Join and calculate additional stats
#     nflr_player_stats_df = (nflr_player_stats_df
#         .merge(df_pass_40_yds, on=['season_year', 'week', 'gsis_id'], how='left')
#         .merge(df_rush_40_yds, on=['season_year', 'week', 'gsis_id'], how='left')
#         .merge(df_rec_40_yds, on=['season_year', 'week', 'gsis_id'], how='left')
#         .merge(df_return_yds, on=['season_year', 'week', 'gsis_id'], how='outer')
#         .assign(
#             pass_inc=lambda x: x['pass_att'] - x['pass_comp'],
#             pass_comp_pct=lambda x: round(x['pass_comp'] / x['pass_att'], 5),
#             fumbles=lambda x: x[['pass_sack_fumbles', 'rush_fumbles', 'rec_fumbles']].sum(axis=1),
#             two_pts=lambda x: x[['pass_two_pts', 'rush_two_pts', 'rec_two_pts']].sum(axis=1),
#             pass_300_yds=lambda x: (x['pass_yds'] >= 300).astype(int),
#             pass_350_yds=lambda x: (x['pass_yds'] >= 350).astype(int),
#             pass_400_yds=lambda x: (x['pass_yds'] >= 400).astype(int),
#             rush_100_yds=lambda x: (x['rush_yds'] >= 100).astype(int),
#             rush_150_yds=lambda x: (x['rush_yds'] >= 150).astype(int),
#             rush_200_yds=lambda x: (x['rush_yds'] >= 200).astype(int),
#             rec_100_yds=lambda x: (x['rec_yds'] >= 100).astype(int),
#             rec_150_yds=lambda x: (x['rec_yds'] >= 150).astype(int),
#             rec_200_yds=lambda x: (x['rec_yds'] >= 200).astype(int)
#         ))
    
#     data_result = {pos: group for pos, group in nflr_player_stats_df.groupby('pos')}
    
#     # Set attributes
#     for df in data_result.values():
#         df.attrs['season'] = nflr_player_stats_df['season_year'].unique()[0]
#         df.attrs['week'] = 1 if len(nflr_player_stats_df['week'].unique()) > 1 else nflr_player_stats_df['week'].unique()[0]
    
#     data_result = {k: source_points(v, scoring_rules, return_data_result=True) for k, v in data_result.items()}
    
#     nflr_player_stats_df = pd.concat(data_result.values())
    
#     # Restore original attributes
#     for attr in ['nflfastR_version', '.internal.selfref', 'nflverse_type', 'nflverse_timestamp']:
#         if attr in nflr_player_stats_df.attrs:
#             nflr_player_stats_df.attrs[attr] = nflr_player_stats_df.attrs[attr]
    
#     if not rename_columns:
#         switch_back_names = {v: k for k, v in nflreadr_offense_cols.items()}
#         nflr_player_stats_df = nflr_player_stats_df.rename(columns=switch_back_names)
    
#     return nflr_player_stats_df
