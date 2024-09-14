import os
import json
import requests
import pandas as pd

# Constants
DATA_DIR = "data/"
PLAYER_IDS_FILE = os.path.join(DATA_DIR, "player_ids.csv")
MFL_API_URL = "https://api.myfantasyleague.com/2024/export?TYPE=players&L=&APIKEY=&DETAILS=1&SINCE=&PLAYERS=&JSON=1"

# Load player IDs from local CSV if available, otherwise get from API
def load_player_ids():
    if not os.path.exists(PLAYER_IDS_FILE):
        # Fetch data from MyFantasyLeague API
        response = requests.get(MFL_API_URL)
        data = response.json()["players"]["player"]

        # Convert to DataFrame
        df = pd.json_normalize(data)

        # Extract first and last names
        df[['last_name', 'first_name']] = df['name'].str.extract(r'(.+),\s(.+)')

        # Clean up the data
        df = df.applymap(lambda x: str(x).replace("[^a-zA-Z0-9.-]", "") if isinstance(x, str) else x)
        df["name"] = df["first_name"] + " " + df["last_name"]

        # Save to local file
        df.to_csv(PLAYER_IDS_FILE, index=False)
        return df
    else:
        return pd.read_csv(PLAYER_IDS_FILE)

# Perform necessary transformations on the data
def update_player_ids(curr_ids, new_ids, updated_ids):
    curr_cols = [col for col in curr_ids.columns if col.endswith("_id") and col != "id"]
    
    # Ensure we're using the correct 'id' column
    id_col = 'id' if 'id' in curr_ids.columns else 'id_x'
    
    # Create 'merge_id' column if it doesn't exist in new_ids
    if 'merge_id' not in new_ids.columns:
        new_ids['merge_id'] = new_ids['first_name'] + new_ids['last_name']
    
    for j in curr_cols:
        if j in updated_ids.columns and j in new_ids.columns:
            df_updated = updated_ids[[id_col, "merge_id", j]].copy()
            df_new = new_ids.dropna(subset=[j, id_col])[[id_col, 'merge_id', j]].copy()
            
            # Merge df_updated and df_new
            merged = df_updated.merge(df_new, on='merge_id', how='outer', suffixes=('', '_new'))
            
            # Update the column values
            merged[j] = merged[f'{j}_new'].fillna(merged[j])
            
            # Merge with curr_ids
            curr_ids = curr_ids.merge(merged[[id_col, j]], on=id_col, how="left", suffixes=('', '_new'))
            
            # Update the column in curr_ids
            curr_ids[j] = curr_ids[f'{j}_new'].fillna(curr_ids[j])
            curr_ids = curr_ids.drop(columns=[f'{j}_new'])
            
            # Convert NA to -1 for integer columns
            if curr_ids[j].dtype == 'float64':
                curr_ids[j] = curr_ids[j].fillna(-1).astype('int64')

    return curr_ids.drop_duplicates()

# Main logic to load, update, and save player IDs
def load_and_update_player_ids():
    player_ids = load_player_ids()

    # Example: Dummy updated/new data to show process
    # Replace these with actual fetches/logic similar to the original R code
    updated_ids = player_ids.copy()
    updated_ids['merge_id'] = updated_ids['first_name'] + updated_ids['last_name']
    new_ids = player_ids.copy()

    # Process the update logic
    player_ids = update_player_ids(player_ids, new_ids, updated_ids)

    # Ensure all ID columns are integers
    id_columns = [col for col in player_ids.columns if col.endswith('_id') or col == 'id']
    for col in id_columns:
        player_ids[col] = player_ids[col].fillna(-1).astype('int64')

    # Save the updated data back
    player_ids.to_csv(PLAYER_IDS_FILE, index=False)
    
    return player_ids

# Load player_ids when the module is imported
player_ids = load_and_update_player_ids()

if __name__ == "__main__":
    # This will run only if the script is executed directly
    print("Player IDs loaded and updated.")
