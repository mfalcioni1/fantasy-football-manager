from openai import OpenAI
import pandas as pd
import os
import random
import numpy as np

# Initialize the OpenAI client
client = OpenAI()

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
    available_players = calculate_value_over_replacement(available_players)
    scarcity_scores, roster_needs = analyze_positional_scarcity(available_players, current_roster)
    bye_week_counts, available_players = analyze_bye_weeks(current_roster, available_players)
    
    prompt = f"""
    Based on the current roster and available players, recommend the best player to draft next. 
    Current Roster: {current_roster}
    Top 10 Available Players by Value Over Replacement:
    {available_players.nlargest(10, 'value_over_replacement')[['player', 'pos', 'value_over_replacement', 'bye_week']].to_string(index=False)}
    Positional Scarcity Scores: {scarcity_scores}
    Roster Needs: {roster_needs}
    Bye Week Distribution: {bye_week_counts}
    
    Please explain your reasoning, considering positional needs, player projections, 
    value over replacement, positional scarcity, bye week distribution, and how the player's performance fits with the league's scoring system.
    """

    response = client.chat.completions.create(
        model="gpt-4-turbo-preview",
        messages=[
            {"role": "system", "content": "You are a fantasy football draft assistant."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=150
    )

    recommendation = response.choices[0].message.content.strip()
    print(f"Recommended Draft Pick: {recommendation}")
    return recommendation

# Function to analyze bye weeks
def analyze_bye_weeks(current_roster, available_players):
    roster_bye_weeks = [player.split('|')[1] for player in current_roster if '|' in player]
    bye_week_counts = {week: roster_bye_weeks.count(week) for week in set(roster_bye_weeks)}
    
    available_players['bye_week'] = available_players['team_bye_week'].str.split('|').str[1]
    
    return bye_week_counts, available_players

# Function to calculate value over replacement
def calculate_value_over_replacement(available_players):
    positions = ['QB', 'RB', 'WR', 'TE']
    baseline = {}
    
    for pos in positions:
        pos_players = available_players[available_players['pos'] == pos]
        baseline[pos] = pos_players.nlargest(12, 'pts_over_replacement')['pts_over_replacement'].min()
    
    available_players['value_over_replacement'] = available_players.apply(
        lambda row: row['pts_over_replacement'] - baseline[row['pos']], axis=1
    )
    
    return available_players

# Function to analyze positional scarcity
def analyze_positional_scarcity(available_players, current_roster):
    positions = ['QB', 'RB', 'WR', 'TE']
    scarcity_scores = {}

    for pos in positions:
        available = available_players[available_players['pos'] == pos]
        top_players = available.nlargest(10, 'pts_over_replacement')
        scarcity_scores[pos] = np.mean(top_players['pts_over_replacement'])

    roster_needs = {pos: 2 - len([p for p in current_roster if p.startswith(pos)]) for pos in positions}
    
    return scarcity_scores, roster_needs

# Function to run mock draft
def run_mock_draft(num_teams, draft_position):
    # Load initial data
    projections = pd.read_csv('../data/fantasy_rankings.csv')
    available_players = pd.read_csv('../data/player_list.csv')
    with open('../data/rules.txt', 'r') as file:
        league_rules = file.read()
    
    current_roster = []
    all_rosters = {i+1: [] for i in range(num_teams)}
    
    # Create the initial draft prompt
    draft_prompt = create_initial_draft_prompt(draft_position, num_teams, league_rules, projections, available_players, current_roster)
    
    # Draft loop
    for round in range(1, 16):  # Assuming 15 rounds in the draft
        for pick in range(1, num_teams + 1):
            current_pick = (round - 1) * num_teams + pick
            
            if pick == draft_position:
                # Our pick
                recommendation = handle_draft_round(projections, available_players, current_roster, league_rules)
                current_roster.append(recommendation)
                all_rosters[pick].append(recommendation)
                available_players = available_players[available_players['Player'] != recommendation]
                print(f"Round {round}, Pick {pick}: You drafted {recommendation}")
            else:
                # Simulate other teams' picks
                best_available = available_players.iloc[0]['Player']
                all_rosters[pick].append(best_available)
                available_players = available_players[available_players['Player'] != best_available]
                print(f"Round {round}, Pick {pick}: Team {pick} drafted {best_available}")
            
            if len(available_players) == 0:
                break
        
        if len(available_players) == 0:
            break
    
    return current_roster, all_rosters

# Function to print mock draft results
def print_mock_draft_results(current_roster, all_rosters):
    print("\nYour Team:")
    for i, player in enumerate(current_roster, 1):
        print(f"{i}. {player}")
    
    print("\nAll Teams:")
    for team, roster in all_rosters.items():
        print(f"\nTeam {team}:")
        for i, player in enumerate(roster, 1):
            print(f"{i}. {player}")

# Function to get initial pick
def get_initial_pick(draft_prompt):
    response = client.chat.completions.create(
        model="gpt-4-turbo-preview",
        messages=[
            {"role": "system", "content": "You are a fantasy football draft assistant."},
            {"role": "user", "content": draft_prompt}
        ],
        max_tokens=150
    )
    
    return response.choices[0].message.content.strip()

# Main function to run the draft
def run_draft():
    # Load initial data
    projections = pd.read_csv('../data/fantasy_rankings.csv')
    available_players = pd.read_csv('../data/player_list.csv')
    with open('../data/rules.txt', 'r') as file:
        league_rules = file.read()
    
    current_roster = []
    
    # Get draft info
    draft_position, num_teams = get_draft_info()
    
    # Create the initial draft prompt
    draft_prompt = create_initial_draft_prompt(draft_position, num_teams, league_rules, projections, available_players, current_roster)
    
    # Get the initial pick recommendation
    initial_recommendation = get_initial_pick(draft_prompt)
    print(initial_recommendation)
    
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

# Update the main function to include mock draft option
if __name__ == "__main__":
    draft_type = input("Enter 'real' for a real draft or 'mock' for a mock draft: ").lower()
    
    if draft_type == 'real':
        run_draft()
    elif draft_type == 'mock':
        draft_position = int(input("Enter your draft position: "))
        num_teams = int(input("Enter the number of teams in the league: "))
        current_roster, all_rosters = run_mock_draft(num_teams, draft_position)
        print_mock_draft_results(current_roster, all_rosters)
    else:
        print("Invalid input. Please enter 'real' or 'mock'.")