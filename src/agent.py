from openai import OpenAI
import pandas as pd
import os

# Initialize the OpenAI client
client = OpenAI()

# Function to load the initial prompt
def load_prompt():
    with open('prompts/draft.txt', 'r') as file:
        return file.read()

# Function to create the initial draft prompt
def create_initial_draft_prompt(draft_position, num_teams, league_rules, projections, available_players, current_roster):
    prompt = f"""
    You are participating in a fantasy football draft. Here are the key details:
    
    - Draft Position: {draft_position}
    - Number of Teams: {num_teams}
    - League Rules: {league_rules}
    - Current Roster: {current_roster}
    - Available Players: {available_players.to_string(index=False)}
    - Player Projections: {projections.to_string(index=False)}
    
    Based on the information provided, recommend the best player to draft next. 
    Please explain your reasoning, considering positional needs, player projections, 
    and how the player's performance fits with the league's scoring system.

    Here are the definitions for the player projection columns:
    player - The player's name
    team_bye_week - Their 3 character team abbreviation | bye week
    pos - Position
    depth_chart - Position on team's depth chart
    adp - Average draft position
    expert_consensus_rank - Expert rankings
    pts_over_replacement - Number of points this player is expected to score over a replacement level player in the position
    position_score - How valuable this player is relative to the other players at their position.
    """
    return prompt

# Function to get user input on draft position and number of teams
def get_draft_info():
    draft_position = int(input("Enter your draft position: "))
    num_teams = int(input("Enter the number of teams in the league: "))
    return draft_position, num_teams

# Function to handle each draft round
def handle_draft_round(projections, available_players, current_roster, league_rules):
    prompt = f"""
    Based on the current roster and available players, recommend the best player to draft next. 
    Current Roster: {current_roster}
    Available Players: {available_players.to_string(index=False)}
    
    Please explain your reasoning, considering positional needs, player projections, 
    and how the player's performance fits with the league's scoring system.
    """

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",  # Or another suitable model
        messages=[
            {"role": "system", "content": "You are a fantasy football draft assistant."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=150  # Adjust based on the level of detail you want
    )

    recommendation = response.choices[0].message.content.strip()
    print(f"Recommended Draft Pick: {recommendation}")
    return recommendation

# Main function to run the draft
def run_draft():
    # Load initial data
    projections = pd.read_csv('data/fantasy_rankings.csv')
    available_players = pd.read_csv('data/player_list.csv')
    with open('data/rules.txt', 'r') as file:
        league_rules = file.read()
    
    current_roster = []
    
    # Get draft info
    draft_position, num_teams = get_draft_info()
    
    # Load initial prompt
    initial_prompt = load_prompt()
    
    # Create the initial draft prompt
    draft_prompt = create_initial_draft_prompt(draft_position, num_teams, league_rules, projections, available_players, current_roster)
    
    # Example call to the LLM for the initial pick
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",  # Or another suitable model
        messages=[
            {"role": "system", "content": "You are a fantasy football draft assistant."},
            {"role": "user", "content": draft_prompt}
        ],
        max_tokens=150  # Adjust based on the level of detail you want
    )
    
    print(response.choices[0].message.content.strip())
    
    # Draft loop
    while len(available_players) > 0:
        # Show available players and ask which ones to remove (drafted by others)
        print("\nAvailable Players:")
        print(available_players[['player', 'pos']])
        
        drafted_players = input("Enter the names of players drafted by other teams (comma-separated, or type 'end' to finish the draft): ").split(",")
        
        if "end" in drafted_players:
            print("Ending the draft.")
            break
        
        drafted_players = [player.strip() for player in drafted_players]
        
        # Remove drafted players from available_players
        available_players = available_players[~available_players['player'].isin(drafted_players)]
        
        # Handle draft round and get the recommendation for the next pick
        recommendation = handle_draft_round(projections, available_players, current_roster, league_rules)
        
        # Add the recommended player to the current roster
        current_roster.append(recommendation)
        
        # Optionally save the recommendation to update the roster file
        with open('data/roster.txt', 'a') as file:
            file.write(f"{recommendation}\n")

        # Update available players
        available_players = available_players[available_players['player'] != recommendation]
        
        # Check if the draft is over
        if len(current_roster) >= num_teams * len(current_roster):
            break

# Run the draft
if __name__ == "__main__":
    run_draft()