import pandas as pd
from utils.scrape_tools import WebScraper

def scrape_draftsharks(week):
    scraper = WebScraper()
    url = f"https://www.draftsharks.com/weekly-rankings/{week}/ppr"
    
    try:
        scraper.navigate_to_page(url)
        
        players = []
        rankings = scraper.page.query_selector_all('div.ranking-item')
        
        for rank in rankings:
            name = rank.query_selector('div.name').inner_text()
            position = rank.query_selector('div.position').inner_text()
            team = rank.query_selector('div.team').inner_text()
            projection = rank.query_selector('div.proj-pts').inner_text()
            
            players.append({
                'name': name,
                'position': position,
                'team': team,
                'projection': float(projection)
            })
        
        return pd.DataFrame(players)
    
    except Exception as e:
        print(f"Error scraping DraftSharks: {e}")
        return pd.DataFrame()
    finally:
        scraper.stop_browser()

def scrape_fantasynerds(week):
    scraper = WebScraper()
    url = f"https://www.fantasynerds.com/nfl/weekly-projections"
    
    try:
        scraper.navigate_to_page(url)
        
        players = []
        rows = scraper.page.query_selector_all('table#DataTables_Table_0 tbody tr')
        
        for row in rows:
            cols = row.query_selector_all('td')
            name = cols[1].inner_text()
            position = cols[2].inner_text()
            team = cols[3].inner_text()
            projection = cols[5].inner_text()  # Fantasy Points column
            
            players.append({
                'name': name,
                'position': position,
                'team': team,
                'projection': float(projection) if projection else None
            })
        
        return pd.DataFrame(players)
    
    except Exception as e:
        print(f"Error scraping FantasyNerds: {e}")
        return pd.DataFrame()
    finally:
        scraper.stop_browser()

def scrape_espn(week):
    scraper = WebScraper()
    url = f"https://fantasy.espn.com/football/players/projections"
    
    try:
        scraper.navigate_to_page(url)
        
        players = []
        rows = scraper.page.query_selector_all('table.Table tbody tr')
        
        for row in rows:
            name_elem = row.query_selector('div.player-column__athlete')
            name = name_elem.query_selector('a.AnchorLink').inner_text()
            position_team = name_elem.query_selector('span.playerinfo__playerteam').inner_text()
            position, team = position_team.split(' - ')
            projection = row.query_selector_all('td')[-1].inner_text()
            
            players.append({
                'name': name,
                'position': position,
                'team': team,
                'projection': float(projection) if projection else None
            })
        
        return pd.DataFrame(players)
    
    except Exception as e:
        print(f"Error scraping ESPN: {e}")
        return pd.DataFrame()
    finally:
        scraper.stop_browser()

def scrape_nfl(week):
    scraper = WebScraper()
    url = f"https://fantasy.nfl.com/research/projections#researchProjections=researchProjections%2C%2Fresearch%2Fprojections%253Fposition%253DO%2526sort%253DprojectedPts%2526statCategory%253DprojectedStats%2526statSeason%253D2024%2526statType%253DweekProjectedStats%2526statWeek%253D{week}%2Creplace"
    
    try:
        scraper.navigate_to_page(url)
        
        players = []
        rows = scraper.page.query_selector_all('table.tableType-player tbody tr')
        
        for row in rows:
            name_elem = row.query_selector('a.playerName')
            name = name_elem.inner_text()
            position_team = row.query_selector('em').inner_text()
            position, team = position_team.split(' - ')
            projection = row.query_selector('td.stat.projected').inner_text()
            
            players.append({
                'name': name,
                'position': position,
                'team': team,
                'projection': float(projection) if projection else None
            })
        
        return pd.DataFrame(players)
    
    except Exception as e:
        print(f"Error scraping NFL: {e}")
        return pd.DataFrame()
    finally:
        scraper.stop_browser()

def scrape_numberfire(week):
    scraper = WebScraper()
    url = f"https://www.numberfire.com/nfl/daily-fantasy/daily-football-projections"
    
    try:
        scraper.navigate_to_page(url)
        
        players = []
        rows = scraper.page.query_selector_all('table.projection-table tbody tr')
        
        for row in rows:
            cols = row.query_selector_all('td')
            name = cols[1].inner_text()
            position = cols[2].inner_text()
            team = cols[3].inner_text()
            projection = cols[-1].inner_text()
            
            players.append({
                'name': name,
                'position': position,
                'team': team,
                'projection': float(projection) if projection else None
            })
        
        return pd.DataFrame(players)
    
    except Exception as e:
        print(f"Error scraping NumberFire: {e}")
        return pd.DataFrame()
    finally:
        scraper.stop_browser()

def scrape_fftoday(week):
    scraper = WebScraper()
    url = f"https://www.fftoday.com/rankings/playerwkproj.php?Season=2024&GameWeek={week}&PosID=10&LeagueID=1"
    
    try:
        scraper.navigate_to_page(url)
        
        players = []
        rows = scraper.page.query_selector_all('table.stats tr')[2:]  # Skip header rows
        
        for row in rows:
            cols = row.query_selector_all('td')
            if len(cols) < 8:  # Skip rows without full data
                continue
            name = cols[1].inner_text()
            team = cols[2].inner_text()
            projection = cols[7].inner_text()
            
            players.append({
                'name': name,
                'position': 'QB',  # This URL is for QBs, adjust for other positions
                'team': team,
                'projection': float(projection) if projection else None
            })
        
        return pd.DataFrame(players)
    
    except Exception as e:
        print(f"Error scraping FFToday: {e}")
        return pd.DataFrame()
    finally:
        scraper.stop_browser()

def scrape_cbssports(week):
    scraper = WebScraper()
    url = f"https://www.cbssports.com/fantasy/football/stats/QB/2024/tp/projections/ppr/"
    
    try:
        scraper.navigate_to_page(url)
        
        players = []
        rows = scraper.page.query_selector_all('table.TableBase-table tbody tr')
        
        for row in rows:
            name_elem = row.query_selector('span.CellPlayerName--long')
            name = name_elem.query_selector('a').inner_text()
            team = name_elem.query_selector('span.CellPlayerName-team').inner_text()
            projection = row.query_selector_all('td')[-1].inner_text()
            
            players.append({
                'name': name,
                'position': 'QB',  # This URL is for QBs, adjust for other positions
                'team': team,
                'projection': float(projection) if projection else None
            })
        
        return pd.DataFrame(players)
    
    except Exception as e:
        print(f"Error scraping CBS Sports: {e}")
        return pd.DataFrame()
    finally:
        scraper.stop_browser()

def scrape_all(week):
    scrapers = [
        ('DraftSharks', scrape_draftsharks),
        ('FantasyNerds', scrape_fantasynerds),
        ('ESPN', scrape_espn),
        ('NFL', scrape_nfl),
        ('NumberFire', scrape_numberfire),
        ('FFToday', scrape_fftoday),
        ('CBS Sports', scrape_cbssports)
    ]
    
    results = {}
    for name, scraper_func in scrapers:
        df = scraper_func(week)
        results[name] = df
        print(f"\n{name} data:")
        print(df.head())
        print(f"Total players scraped from {name}: {len(df)}")
    
    return results

# Test all functions
if __name__ == "__main__":
    week = 1
    all_data = scrape_all(week)